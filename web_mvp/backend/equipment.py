"""설비(유형자산) 모델.

설계 근거: docs/finance-model.md §4

- 설비는 **분야(필드)** 단위로 필요하다. AI 업무를 하려면 GPU 서버가 있어야 한다.
- 수용량은 **동시에 진행 중인 해당 필드 업무 수**로 계산한다.
  한 사업 안에서는 필드가 중복되지 않으므로, 사업을 여러 건 굴릴 때 부족해진다.
- 없으면 막히는 게 아니라 **처리량이 깎인다** (착수 게이트와 같은 "경고 후 강행" 철학).
- 구매하면 자산이 되고 매주 감가상각된다. 리스는 자산이 아니고 매주 리스료만 낸다.
"""
import math

# 분야별 전문 설비
EQUIPMENT = {
    "UIUX":   {"label": "디자인 툴 · 사용성 테스트실", "cost": 25000,  "life": 52, "penalty": 0.10},
    "FE":     {"label": "크로스브라우징 테스트 환경",   "cost": 30000,  "life": 52, "penalty": 0.15},
    "BE":     {"label": "DB · 부하 테스트 서버",       "cost": 55000,  "life": 78, "penalty": 0.15},
    "Mobile": {"label": "실기기 테스트 랩",            "cost": 70000,  "life": 52, "penalty": 0.20},
    "Ops":    {"label": "스테이징 · 모니터링 인프라",   "cost": 110000, "life": 78, "penalty": 0.25},
    "AI":     {"label": "GPU 학습 서버",              "cost": 180000, "life": 78, "penalty": 0.35},
}

# 공통 인프라 — 분야와 무관하게 동시 사업 수를 감당한다
DEV_SERVER = {"label": "개발 서버", "cost": 40000, "life": 78, "penalty": 0.10}
SERVER_KEY = "_server"

# 사무실 집기 — 사무실 확장 비용을 자산으로 계상할 때 쓴다.
# 수용량 계산에는 쓰지 않는다 (책상 수는 office_level이 따로 관리).
OFFICE_KEY = "_office"
OFFICE_LIFE = 104
OFFICE = {"label": "사무실 집기", "cost": 0, "life": OFFICE_LIFE, "penalty": 0.0}

# 등급이 페널티 강도를 정한다. 초반(T1)은 설비 없이도 굴러간다.
TIER_PENALTY_SCALE = {"T1": 0.0, "T2": 0.4, "T3": 0.7, "T4": 1.0, "T5": 1.3}

CAPACITY_PER_UNIT = 2      # 설비 1대가 감당하는 동시 업무(또는 사업) 수
LEASE_MULTIPLIER = 1.4     # 리스 총액은 취득가의 1.4배
RESALE_RATE = 0.6          # 되팔면 장부가의 60%만 회수
AGED_CAPACITY = 0.5        # 장부가 0인 노후 설비는 절반 몫만 한다

_seq = 0


def spec_of(key):
    if key == SERVER_KEY:
        return DEV_SERVER
    if key == OFFICE_KEY:
        return OFFICE
    return EQUIPMENT[key]


def lease_fee(key):
    """주당 리스료."""
    s = spec_of(key)
    return int(s["cost"] / s["life"] * LEASE_MULTIPLIER)


class Unit:
    """설비 1대. 구매(own)면 장부가를 갖고 감가상각된다."""

    def __init__(self, key, mode):
        global _seq
        _seq += 1
        self.id = f"EQ{_seq:04d}"
        self.key = key
        self.mode = mode                    # own / lease
        spec = spec_of(key)
        self.cost = spec["cost"]
        self.life = spec["life"]
        self.book = float(spec["cost"]) if mode == "own" else 0.0

    @property
    def aged(self):
        return self.mode == "own" and self.book <= 0

    def depreciate(self):
        """1주치 감가상각. 감가상각비를 돌려준다."""
        if self.mode != "own" or self.book <= 0:
            return 0
        amount = min(self.book, self.cost / self.life)
        self.book -= amount
        # 부동소수점 잔여값이 남으면 노후 판정(book <= 0)이 영영 안 걸린다
        if self.book < 1:
            amount += self.book
            self.book = 0.0
        return amount

    def to_dict(self):
        spec = spec_of(self.key)
        return {
            "id": self.id, "key": self.key, "label": spec["label"],
            "mode": self.mode, "book": int(self.book), "cost": self.cost,
            "aged": self.aged,
            "weekly": lease_fee(self.key) if self.mode == "lease"
                      else int(self.cost / self.life),
        }


# ── 보유량 계산 ──────────────────────────────────────────────
def capacity(units, key):
    """해당 설비의 유효 대수. 노후 설비는 절반 몫만 한다."""
    total = 0.0
    for u in units:
        if u.key != key:
            continue
        total += AGED_CAPACITY if u.aged else 1.0
    return total


def required_units(count):
    """동시 부하 count건을 감당하는 데 필요한 대수."""
    return max(1, math.ceil(count / CAPACITY_PER_UNIT)) if count else 0


def shortage_penalty(units, key, load, tier):
    """부족분에 비례한 처리량 감소율 (0.0 ~).

    load: 이 설비가 감당해야 하는 동시 건수
    """
    need = required_units(load)
    if need <= 0:
        return 0.0
    have = capacity(units, key)
    shortage = max(0.0, (need - have) / need)
    if shortage <= 0:
        return 0.0
    base = spec_of(key)["penalty"]
    return base * TIER_PENALTY_SCALE.get(tier, 1.0) * shortage
