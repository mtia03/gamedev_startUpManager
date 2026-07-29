"""숫자를 자연어로 바꾸는 계층.

두 곳에서 쓴다.
1. LLM에 넘기기 전 — 숫자를 아예 주지 않으면 유출될 수가 없다.
   프롬프트 규칙("숫자를 말하지 마")으로 막는 방식은 한 번 어기면 뚫린다.
2. 플레이어에게 보여줄 때 — 지원자의 정확한 스탯은 채용 전까지 알 수 없고,
   면접을 통해 추정 구간이 좁혀진다.

구간 기준은 docs/llm-prompt-design.md §2 (4,000명 실측 분포 기반).
"""
import random

# ── 세부 능력치 (0~50) ────────────────────────────────────────
# 40~49 구간이 실측 3.4%뿐이라 문서 권고대로 40 이상을 하나로 합쳤다.
STAT_BANDS = [
    (0, 9, "문외한", "거의 손도 못 댐"),
    (10, 19, "입문", "기본기 정도는 있음"),
    (20, 29, "실무급", "실무는 무리 없이 함"),
    (30, 39, "상위권", "주변에서 잘한다고 인정받음"),
    (40, 50, "최상위", "업계에서 알아주는 수준"),
]

CA_BANDS = [
    (0, 49, "이제 시작하는 단계"),
    (50, 99, "한 사람 몫은 하는"),
    (100, 149, "고급 인력"),
    (150, 10 ** 9, "핵심 인력"),
]

MORALE_BANDS = [
    (80, 100, "지금 일할 의욕이 넘침"),
    (50, 79, "그럭저럭 다닐 만함"),
    (20, 49, "많이 지쳐 있고 회의감이 듦"),
    (0, 19, "당장이라도 그만두고 싶음"),
]

FATIGUE_BANDS = [
    (0, 29, "컨디션 좋음"),
    (30, 59, "슬슬 피곤함"),
    (60, 84, "과로 상태, 번아웃 직전"),
    (85, 100, "완전히 소진됨"),
]

PSYCH_BANDS = [
    (0, 4, "무난하고 원만한 성격"),
    (5, 9, "약간 예민한 편"),
    (10, 14, "자기중심적이고 팀에 마찰을 일으킴"),
    (15, 20, "심각한 성격적 결함, 주변을 망침"),
]


def _band(value, bands, idx=-1):
    for row in bands:
        if row[0] <= value <= row[1]:
            return row[idx]
    return bands[-1][idx]


def stat_phrase(value):
    return _band(value, STAT_BANDS, 3)


def stat_label(value):
    return _band(value, STAT_BANDS, 2)


def ca_phrase(value):
    return _band(value, CA_BANDS)


def morale_phrase(value):
    return _band(value, MORALE_BANDS)


def fatigue_phrase(value):
    return _band(value, FATIGUE_BANDS)


def psych_phrase(value):
    return _band(value, PSYCH_BANDS)


def describe_for_llm(dev):
    """LLM에 넘길 지원자 상태. 숫자는 연봉을 빼고 전부 제거한다."""
    circ = getattr(dev, "circumstance", None)
    needs = getattr(dev, "needs", [])
    extra = {}
    if circ:
        extra["your_situation"] = CIRCUMSTANCES[circ]["phrase"]
    extra["what_you_care_about"] = (
        [NEEDS[n]["phrase"] for n in needs] if needs
        else ["연봉 조건 외에는 딱히 따지지 않는다"])
    return {**extra,
        "name": f"{dev.first_name} {dev.last_name}",
        "education": dev.education,
        "specialty": dev.main_field,
        "skill_in_specialty": stat_phrase(dev.stats[dev.main_field]),
        "overall_class": ca_phrase(dev.CA),
        "other_skills": {
            f: stat_phrase(v) for f, v in dev.stats.items() if f != dev.main_field
        },
        "mood": morale_phrase(dev.morale),
        "condition": fatigue_phrase(dev.fatigue),
        "personality": psych_phrase(dev.psychological_issue),
        # 연봉만 숫자로 남긴다. 협상의 대상이라 유저가 알아야 한다.
        "current_demand": dev.current_demand,
    }


# ── 지원자 속성 (3개 독립 축) ─────────────────────────────────
# 설계 근거: docs/llm-prompt-design.md §보류 중인 설계 (A)

# ① 자금 사정 — 연봉 하한과 한 턴 양보 폭을 결정한다
CIRCUMSTANCES = {
    "stable":      {"label": "현직에 만족", "weight": 55, "floor": 0.80, "max_drop": 0.06,
                    "phrase": "지금 다니는 곳에 큰 불만은 없다"},
    "career":      {"label": "경력 전환 희망", "weight": 15, "floor": 0.72, "max_drop": 0.08,
                    "phrase": "새로운 기술을 다뤄보고 싶어 옮기려 한다"},
    "long_search": {"label": "장기 구직 중", "weight": 15, "floor": 0.65, "max_drop": 0.10,
                    "phrase": "구직이 길어져 조바심이 난다"},
    "urgent":      {"label": "무직 · 자금 압박", "weight": 10, "floor": 0.55, "max_drop": 0.12,
                    "phrase": "당장 들어갈 곳이 필요할 만큼 사정이 급하다"},
    "courted":     {"label": "여러 곳에서 러브콜", "weight": 5, "floor": 0.90, "max_drop": 0.04,
                    "phrase": "다른 회사들에서도 제안을 받고 있어 아쉬울 게 없다"},
}

# ② 원하는 것 — 돈 이외의 설득 수단. 충족 여부는 코드가 게임 상태로 판정한다.
NEEDS = {
    "growth":    {"label": "성장 기회", "phrase": "성장할 수 있는 환경을 중요하게 본다"},
    "stability": {"label": "안정성", "phrase": "회사가 오래 버틸 수 있는지를 신경 쓴다"},
    "worklife":  {"label": "워라밸", "phrase": "과로하지 않는 환경을 원한다"},
    "prestige":  {"label": "간판", "phrase": "이름이 알려진 회사에서 일하고 싶어 한다"},
    "team":      {"label": "좋은 동료", "phrase": "뛰어난 동료와 함께 일하길 원한다"},
}
NEED_COUNT_WEIGHTS = [(0, 15), (1, 50), (2, 25), (3, 10)]   # 0개 = 오직 돈
NEED_FLOOR_BONUS = 0.04       # 니즈 1개당 충족 시 하한 인하
NEED_WALKAWAY_PENALTY = 0.03  # 니즈 1개당 미충족 시 이탈 확률 가산

# ③ 파악 난이도 — 추정 구간의 폭에 배율을 건다
READABILITY = {
    "open":    {"label": "솔직함", "weight": 25, "scale": 0.7, "steps": 3},
    "normal":  {"label": "보통", "weight": 50, "scale": 1.0, "steps": 4},
    "guarded": {"label": "과묵함", "weight": 20, "scale": 1.4, "steps": 6},
    "opaque":  {"label": "속을 모르겠음", "weight": 5, "scale": 1.8, "steps": 6},
}


def _weighted(table, rng=random):
    keys = list(table)
    return rng.choices(keys, weights=[table[k]["weight"] for k in keys], k=1)[0]


def roll_attributes(rng=random):
    """지원자 생성 시 세 축을 각각 굴린다. 서로 독립이다."""
    counts, weights = zip(*NEED_COUNT_WEIGHTS)
    n = rng.choices(counts, weights=weights, k=1)[0]
    return {
        "circumstance": _weighted(CIRCUMSTANCES, rng),
        "needs": rng.sample(list(NEEDS), n),
        "readability": _weighted(READABILITY, rng),
    }


# ── 스탯 추정 구간 (플레이어에게 보여줄 값) ──────────────────────
# 처음에는 넓은 구간만 보이고, 면접을 진행할수록 좁혀진다.
BASE_STEPS = [40, 24, 14, 8, 4]        # 파악 단계별 기준 폭
ACE_THRESHOLD = 45                     # 이 이상이면 '에이스'로 표시
MIN_OPAQUE_WIDTH = 6                   # 읽기 어려운 사람의 최소 구간 폭


def reveal_steps(readability):
    """파악 난이도에 맞춰 단계별 구간 폭 표를 만든다."""
    cfg = READABILITY.get(readability, READABILITY["normal"])
    total = cfg["steps"]
    out = []
    for i in range(total + 1):
        # 기준 표를 단계 수에 맞춰 늘리거나 줄여서 보간
        pos = i / total * (len(BASE_STEPS) - 1)
        lo, hi = int(pos), min(int(pos) + 1, len(BASE_STEPS) - 1)
        base = BASE_STEPS[lo] + (BASE_STEPS[hi] - BASE_STEPS[lo]) * (pos - lo)
        out.append(max(0, round(base * cfg["scale"])))
    out[-1] = 0 if readability != "opaque" else MIN_OPAQUE_WIDTH
    return out


def estimate_range(true_value, turns, seed_key, readability="normal"):
    """면접 횟수에 따라 좁혀지는 추정 구간을 만든다.

    같은 지원자·같은 필드면 항상 같은 구간이 나오도록 시드를 고정한다.
    (호출할 때마다 흔들리면 플레이어가 정보를 신뢰할 수 없다)
    """
    steps = reveal_steps(readability)
    step = steps[min(turns, len(steps) - 1)]
    if step <= 0:
        return {"low": true_value, "high": true_value, "exact": True}

    rng = random.Random(f"{seed_key}:{step}")
    offset = rng.randint(0, step)
    low = max(0, min(true_value - offset, 50 - step))
    high = min(50, low + step)
    if not (low <= true_value <= high):      # 경계 보정
        low, high = max(0, true_value - step // 2), min(50, true_value + step // 2)
    return {"low": low, "high": high, "exact": False}


def describe_for_player(dev, turns, known=()):
    """플레이어에게 보여줄 지원자 정보.

    정확한 스탯 대신 추정 구간을 준다. 다만 '에이스인지 아닌지'는
    처음부터 보여준다 — 아무 정보도 없으면 누구와 면접할지 고를 수가 없다.
    `known`에 담긴 항목만 사정·니즈가 공개된다.
    """
    readability = getattr(dev, "readability", "normal")
    steps = reveal_steps(readability)
    ranges = {
        f: estimate_range(v, turns, f"{dev.tag}:{f}", readability)
        for f, v in dev.stats.items()
    }
    circ = getattr(dev, "circumstance", None)
    needs = getattr(dev, "needs", [])
    return {
        "stat_ranges": ranges,
        "is_ace": max(dev.stats.values()) >= ACE_THRESHOLD,
        "class_hint": ca_phrase(dev.CA),
        "specialty_hint": stat_label(dev.stats[dev.main_field]),
        "reveal_level": min(turns, len(steps) - 1),
        "max_reveal_level": len(steps) - 1,
        "circumstance": (
            {"key": circ, "label": CIRCUMSTANCES[circ]["label"]}
            if circ and "circumstance" in known else None),
        "needs": (
            [{"key": n, "label": NEEDS[n]["label"]} for n in needs]
            if "needs" in known else None),
        "needs_known": "needs" in known,
    }
