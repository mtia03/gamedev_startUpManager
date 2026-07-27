"""사업(Business)과 업무(Task) 모델.

설계 근거는 docs/project-scale-spec.md, docs/project-requirement-model.md.
- 사업은 등급(T1~T5)을 가지며, 등급의 '요구 필드 수'가 곧 업무 개수가 된다.
- 업무는 필드 1개와 요구 공수를 가지며, 선행 업무를 둘 수 있다 (테크트리).
- 업무마다 인원을 전담 배치하고, 주당 처리량만큼 진행된다.
- 완료 시 성공 확률로 등급(실패/양호/좋음)을 판정하고 보상이 갈린다.
"""
import random

FIELDS = ["FE", "BE", "Mobile", "AI", "Ops", "UIUX"]

# ── 등급 정의 (project-scale-spec.md §3) ──────────────────────
# fields = 업무 개수, req_per_field = 업무 1개의 요구 공수
TIERS = {
    "T1": {"name": "프로토타입 / 외주", "fields": 2, "req_per_field": 112,
           "target_weeks": 4, "crew": 2, "layers": 1,
           "gate": {"field_min": 0, "ace_stat": 0, "ace_count": 0}},
    "T2": {"name": "MVP", "fields": 3, "req_per_field": 275,
           "target_weeks": 8, "crew": 4, "layers": 2,
           "gate": {"field_min": 10, "ace_stat": 25, "ace_count": 1}},
    "T3": {"name": "정식 제품 v1", "fields": 4, "req_per_field": 800,
           "target_weeks": 12, "crew": 8, "layers": 2,
           "gate": {"field_min": 15, "ace_stat": 45, "ace_count": 1}},
    "T4": {"name": "스케일업 플랫폼", "fields": 5, "req_per_field": 1680,
           "target_weeks": 20, "crew": 15, "layers": 3,
           "gate": {"field_min": 25, "ace_stat": 45, "ace_count": 2}},
    "T5": {"name": "전사 대형", "fields": 6, "req_per_field": 4480,
           "target_weeks": 32, "crew": 32, "layers": 3,
           "gate": {"field_min": 25, "ace_stat": 45, "ace_count": 6}},
}

# 등급이 올라갈수록 고위험 고수익. 보상 = 예상 인건비 × 배율
REWARD_MULTIPLIER = {"T1": 1.2, "T2": 1.5, "T3": 1.8, "T4": 2.2, "T5": 3.0}
REPUTATION_GAIN = {"T1": 150, "T2": 400, "T3": 900, "T4": 1800, "T5": 3500}

# 보상 산정 기준: BD 개발자(CA 76)의 주급. main.py의 연봉 공식과 맞춘 값.
BASELINE_WEEKLY_SALARY = 1345

# 처리량 파라미터 (project-scale-spec.md §2)
# 부분야 계수는 등급이 낮을수록 관대하다. 가벼운 외주는 전공이 달라도 어느 정도
# 해내지만, 대형 프로젝트는 전문가가 아니면 사실상 기여하지 못한다.
SUB_FIELD_COEF_BY_TIER = {
    "T1": 0.60, "T2": 0.45, "T3": 0.35, "T4": 0.28, "T5": 0.25,
}
SUB_FIELD_COEF = 0.25   # 기본값 (문서 §2 기준, T5와 동일)
COMM_FREE = 7
COMM_PENALTY = 0.02
COMM_FLOOR = 0.60


def sub_field_coef(tier):
    return SUB_FIELD_COEF_BY_TIER.get(tier, SUB_FIELD_COEF)

# 성공 확률 모델 (project-requirement-model.md §4)
W_CREW, W_FLOOR, W_TOTAL = 0.25, 0.35, 0.40
PROB_CAP = 0.95
PROB_SLOPE = 7.0
PROB_CENTER = 0.80
GATE_FAIL_PENALTY = 0.6   # 게이트 미충족 강행 시 확률 배율
BASELINE_CA = 76          # BD 1명 기준 CA

# 결과 등급별 보상 배율
GRADE_REWARD = {"fail": 0.0, "good": 1.0, "great": 1.25}
GRADE_LABEL = {"fail": "실패", "good": "양호", "great": "좋음"}

# 사업 포기 위약금: 남은 보상의 일부를 물어내고 명성이 깎인다.
ABANDON_PENALTY_RATE = 0.15
ABANDON_REPUTATION_RATE = 0.5

# 명성이 오르면 상위 등급이 열리지만, 하위 등급도 계속 들어온다.
# 상위 등급만 남기면 인원을 감당 못 하는 사업뿐이라 게임이 막힌다.
TIER_ORDER = ["T1", "T2", "T3", "T4", "T5"]
REPUTATION_UNLOCK = {"T1": 0, "T2": 0, "T3": 4000, "T4": 8000, "T5": 12000}


def tiers_for_reputation(reputation):
    """수주 가능한 등급 목록. 명성이 해금 기준을 넘긴 등급만."""
    return [t for t in TIER_ORDER if reputation >= REPUTATION_UNLOCK[t]]


def pick_tier(reputation, desk_count):
    """제안할 등급을 고른다.

    감당 가능한 인원(책상 수)을 크게 넘는 등급은 뽑힐 확률을 낮춰서,
    수주 목록이 수행 불가능한 사업으로만 채워지는 것을 막는다.
    """
    tiers = tiers_for_reputation(reputation)
    weights = []
    for t in tiers:
        crew = TIERS[t]["crew"]
        # 책상 수로 감당 가능하면 높은 등급일수록 선호, 벅차면 급감
        weights.append(3.0 if crew <= desk_count else max(0.15, desk_count / crew))
    return random.choices(tiers, weights=weights, k=1)[0]


BUSINESS_NAMES = [
    "사내 관리 도구", "쇼핑몰 리뉴얼", "예약 시스템", "구독 결제 모듈",
    "물류 추적 대시보드", "사내 메신저", "추천 엔진", "결제 게이트웨이",
    "헬스케어 앱", "교육 플랫폼", "게임 백오피스", "실시간 협업 도구",
]
TASK_NAME_BY_FIELD = {
    "FE": "프론트엔드 구현", "BE": "백엔드 API 구축", "Mobile": "모바일 앱 개발",
    "AI": "추천/AI 모델 개발", "Ops": "인프라 및 배포 구성", "UIUX": "UI/UX 설계",
}


class Task:
    """사업을 구성하는 단위 업무."""

    def __init__(self, tag, field, required, requires):
        self.tag = tag
        self.field = field
        self.name = TASK_NAME_BY_FIELD[field]
        self.required = required        # 요구 공수
        self.requires = requires        # 선행 업무 태그 목록
        self.assigned = []              # 배치된 개발자 태그
        self.progress = 0.0
        self.status = "locked"          # locked / ready / active / done
        self.grade = None               # fail / good / great
        self.weeks_worked = 0

    @property
    def ratio(self):
        return min(1.0, self.progress / self.required) if self.required else 1.0

    def to_dict(self):
        return {
            "tag": self.tag, "name": self.name, "field": self.field,
            "required": self.required, "progress": round(self.progress, 1),
            "ratio": round(self.ratio, 3), "requires": self.requires,
            "assigned": list(self.assigned), "status": self.status,
            "grade": self.grade, "grade_label": GRADE_LABEL.get(self.grade),
            "weeks_worked": self.weeks_worked,
        }


class Business:
    """여러 업무로 구성된 사업."""

    _seq = 0

    def __init__(self, tier):
        Business._seq += 1
        self.tag = f"B{Business._seq:03d}"
        spec = TIERS[tier]
        self.tier = tier
        self.tier_name = spec["name"]
        self.name = random.choice(BUSINESS_NAMES)
        self.target_weeks = spec["target_weeks"]
        self.crew = spec["crew"]
        self.gate = spec["gate"]
        self.status = "offered"         # offered / active / completed
        self.started_week = None
        self.completed_week = None
        self.payout = 0

        self.tasks = self._build_tasks(spec)
        self.reward = int(spec["crew"] * BASELINE_WEEKLY_SALARY
                          * spec["target_weeks"] * REWARD_MULTIPLIER[tier])
        self.reputation_gain = REPUTATION_GAIN[tier]

    def _build_tasks(self, spec):
        """업무를 만들고 계층(layer) 단위로 선행 관계를 건다.

        같은 계층끼리는 병렬, 다음 계층은 이전 계층 전체가 끝나야 열린다.
        T1은 계층이 1개뿐이라 전부 병렬이고 개수도 1~2개로 가볍다.
        """
        count = spec["fields"]
        if self.tier == "T1":
            count = random.randint(1, 2)

        fields = random.sample(FIELDS, count)
        layers = min(spec["layers"], count)
        # 업무를 계층에 최대한 고르게 배분
        buckets = [[] for _ in range(layers)]
        for i, f in enumerate(fields):
            buckets[i % layers].append(f)

        tasks, prev_tags = [], []
        for bucket in buckets:
            current_tags = []
            for f in bucket:
                # 같은 등급 안에서도 변화가 생기도록 요구 공수에 ±20%
                required = int(spec["req_per_field"] * random.uniform(0.8, 1.2))
                t = Task(f"{self.tag}-{len(tasks) + 1}", f, required, list(prev_tags))
                t.status = "ready" if not prev_tags else "locked"
                tasks.append(t)
                current_tags.append(t.tag)
            prev_tags = current_tags
        return tasks

    # ── 조회 헬퍼 ────────────────────────────────────────────
    def task(self, tag):
        for t in self.tasks:
            if t.tag == tag:
                return t
        return None

    def assigned_tags(self):
        out = []
        for t in self.tasks:
            out += t.assigned
        return out

    def is_complete(self):
        return all(t.status == "done" for t in self.tasks)

    def refresh_locks(self):
        """선행 업무가 모두 끝난 업무를 ready로 연다."""
        done = {t.tag for t in self.tasks if t.status == "done"}
        for t in self.tasks:
            if t.status == "locked" and all(r in done for r in t.requires):
                t.status = "ready"

    def settle(self):
        """완료된 사업의 보상을 업무별 요구 공수 비중 × 등급 배율로 정산한다."""
        total = sum(t.required for t in self.tasks) or 1
        ratio = sum((t.required / total) * GRADE_REWARD.get(t.grade, 0.0)
                    for t in self.tasks)
        self.payout = int(self.reward * ratio)
        return self.payout

    def to_dict(self):
        return {
            "tag": self.tag, "name": self.name, "tier": self.tier,
            "tier_name": self.tier_name, "status": self.status,
            "reward": self.reward, "payout": self.payout,
            "reputation_gain": self.reputation_gain,
            "target_weeks": self.target_weeks, "crew": self.crew,
            "gate": self.gate, "started_week": self.started_week,
            "completed_week": self.completed_week,
            "tasks": [t.to_dict() for t in self.tasks],
        }


# ── 계산 함수 ────────────────────────────────────────────────
def comm_efficiency(n):
    """Brooks's Law 근사. 7명까지는 손실 없음."""
    return max(COMM_FLOOR, 1.0 - COMM_PENALTY * max(0, n - COMM_FREE))


def condition_factor(dev):
    """사기·피로 반영 컨디션 계수. main.productivity()와 같은 식."""
    return (0.5 + 0.5 * dev.morale / 100) * (1 - 0.4 * dev.fatigue / 100)


def throughput(devs, field, tier=None):
    """해당 필드에 배치된 팀의 주당 처리량.

    tier를 주면 등급별 부분야 계수를 적용한다 (낮은 등급일수록 관대).
    """
    if not devs:
        return 0.0
    coef = sub_field_coef(tier) if tier else SUB_FIELD_COEF
    raw = sum(d.stats[field] * (1.0 if d.main_field == field else coef)
              for d in devs)
    condition = sum(condition_factor(d) for d in devs) / len(devs)
    return raw * comm_efficiency(len(devs)) * condition


def check_gate(devs, task, gate):
    """착수 게이트 판정. 통과 여부와 사유를 돌려준다."""
    reasons = []
    if not devs:
        reasons.append("배치된 인원이 없습니다.")
        return False, reasons
    if gate["field_min"] and not any(d.stats[task.field] >= gate["field_min"] for d in devs):
        reasons.append(f"{task.field} 스탯 {gate['field_min']} 이상인 인원이 없습니다.")
    if gate["ace_count"]:
        aces = sum(1 for d in devs if max(d.stats.values()) >= gate["ace_stat"])
        if aces < gate["ace_count"]:
            reasons.append(
                f"에이스(최고 스탯 {gate['ace_stat']}+)가 {gate['ace_count']}명 필요한데 {aces}명입니다.")
    return not reasons, reasons


def success_score(devs, task, business):
    """3축(인원/하한/능력합) 충족도를 가중 합산한 Score."""
    if not devs:
        return 0.0
    # 업무 1개에 권장되는 인원 = 사업 권장 인원 / 업무 수
    rec_crew = max(1, round(business.crew / len(business.tasks)))
    rec_total_ca = rec_crew * BASELINE_CA
    floor = business.gate["field_min"]

    x = len(devs) / rec_crew
    r_n = max(0.0, 1 - max(0, 1 - x) * 1.0 - max(0, x - 1) * 0.5)
    r_f = (sum(1 for d in devs if d.stats[task.field] >= floor) / len(devs)
           if floor else 1.0)
    r_t = sum(d.CA for d in devs) / rec_total_ca if rec_total_ca else 1.0

    return (W_CREW * min(r_n, 1.20)
            + W_FLOOR * min(r_f, 1.00)
            + W_TOTAL * min(r_t, 1.20))


def success_probability(devs, task, business):
    """Score를 로지스틱으로 확률 변환. 게이트 미충족이면 페널티를 곱한다."""
    import math
    score = success_score(devs, task, business)
    p = PROB_CAP / (1 + math.exp(-PROB_SLOPE * (score - PROB_CENTER)))
    passed, _ = check_gate(devs, task, business.gate)
    if not passed:
        p *= GATE_FAIL_PENALTY
    return max(0.02, min(PROB_CAP, p))


def roll_grade(p):
    """완료 판정. 실패 = 1-p, 나머지를 좋음/양호로 반씩 가른다."""
    r = random.random()
    if r >= p:
        return "fail"
    return "great" if r < p / 2 else "good"
