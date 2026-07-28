"""회계 원장.

설계 근거: docs/finance-model.md

**발생주의 라이트** — 수익은 진행기준으로 인식하고, 현금은 따로 움직인다.
그래서 "손익은 흑자인데 현금이 없다"(흑자도산)가 성립한다.

항등식이 항상 성립해야 한다:
    현금 + 미청구공사 + 설비장부가 = 미지급급여 + 선수금 + 차입금 + 자본금 + 이익잉여금

설비 장부가는 equipment 모듈이 들고 있으므로 원장은 그 값을 참조만 한다.
"""

# 손익 항목 (결산 화면 순서대로)
REVENUE_KEYS = ["사업 수익"]
EXPENSE_KEYS = ["노무비", "설비 리스료", "감가상각비", "이자비용", "위약금", "퇴직금"]

SETTLEMENT_WEEKS = 8       # 결산 주기


class Loan:
    """차입금 1건."""

    _seq = 0

    def __init__(self, principal, rate, weeks, label):
        Loan._seq += 1
        self.id = f"L{Loan._seq:03d}"
        self.principal = principal
        self.rate = rate              # 주당 이자율
        self.weeks_left = weeks
        self.label = label

    def to_dict(self):
        return {
            "id": self.id, "label": self.label,
            "principal": self.principal,
            "weekly_interest": int(self.principal * self.rate),
            "weeks_left": self.weeks_left,
            "rate": round(self.rate * 100, 3),
        }


LOAN_PRODUCTS = {
    "short": {"label": "단기 운전자금", "weeks": 26, "rate": 0.0035},
    "long":  {"label": "장기 시설자금", "weeks": 78, "rate": 0.0018},
}
LOAN_LIMIT_RATE = 0.5          # 자산총계의 이 비율까지 빌릴 수 있다
REPUTATION_RATE_CUT = 0.0005   # 명성 12,000 이상이면 이자율 인하
ADVANCE_RATE = 0.30            # 수주 시 계약금 비율


class Ledger:
    """회사의 재무 상태."""

    def __init__(self, capital):
        # 자산
        self.cash = capital
        self.unbilled = 0.0        # 미청구공사 — 일했지만 아직 못 받은 돈
        # 부채
        self.accrued_wages = 0.0   # 미지급급여
        self.advances = 0.0        # 선수금 — 받았지만 아직 일 안 한 몫
        self.loans = []
        # 자본
        self.capital = capital     # 자본금 (창업 시 고정)
        self.retained = 0.0        # 이익잉여금

        # 이번 결산 기간 손익
        self.period = {k: 0.0 for k in REVENUE_KEYS + EXPENSE_KEYS}
        self.week_net = 0.0        # 이번 주 순이익
        self.history = []          # 결산 이력
        self.last_settled_week = 1

    # ── 조회 ────────────────────────────────────────────────
    @property
    def debt(self):
        return sum(l.principal for l in self.loans)

    def assets(self, equipment_book):
        return self.cash + self.unbilled + equipment_book

    def liabilities(self):
        return self.accrued_wages + self.advances + self.debt

    def equity(self):
        return self.capital + self.retained

    def check(self, equipment_book):
        """항등식이 깨졌는지 확인한다 (버그 검출용)."""
        return round(self.assets(equipment_book)
                     - self.liabilities() - self.equity(), 2)

    # ── 손익 기록 ───────────────────────────────────────────
    def revenue(self, key, amount):
        self.period[key] = self.period.get(key, 0.0) + amount
        self.retained += amount
        self.week_net += amount

    def expense(self, key, amount):
        self.period[key] = self.period.get(key, 0.0) + amount
        self.retained -= amount
        self.week_net -= amount

    # ── 현금 거래 ───────────────────────────────────────────
    def pay(self, key, amount):
        """비용을 현금으로 지출한다."""
        self.cash -= amount
        self.expense(key, amount)

    def accrue_wages(self, amount):
        """급여를 못 줬다. 비용은 발생하고 부채로 남는다."""
        self.accrued_wages += amount
        self.expense("노무비", amount)

    def buy_asset(self, amount):
        """설비 구매 — 현금이 자산으로 바뀔 뿐 손익은 없다."""
        self.cash -= amount

    def sell_asset(self, book, refund):
        """설비 매각 — 장부가와 회수액의 차이가 손익이 된다."""
        self.cash += refund
        diff = refund - book
        if diff >= 0:
            self.revenue("사업 수익", diff)
        else:
            self.expense("위약금", -diff)

    def depreciate(self, amount):
        """감가상각 — 설비 장부가가 줄어든 만큼 비용."""
        if amount:
            self.expense("감가상각비", amount)

    # ── 수주 대금 ───────────────────────────────────────────
    def receive_advance(self, amount):
        """착수금 수령 — 현금이 늘고 같은 액수의 선수금(부채)이 생긴다."""
        self.cash += amount
        self.advances += amount

    def recognize(self, amount):
        """진행률만큼 수익을 인식한다.

        선수금이 남아 있으면 거기서 먼저 털고, 모자라면 미청구공사로 쌓인다.
        """
        if amount <= 0:
            return
        from_advance = min(self.advances, amount)
        self.advances -= from_advance
        self.unbilled += amount - from_advance
        self.revenue("사업 수익", amount)

    def reverse_revenue(self, amount):
        """인식했던 수익을 되돌린다.

        업무가 실패해 진행률이 깎였거나 사업을 포기했을 때 쓴다.
        recognize()의 정확한 역연산이다.
        """
        if amount <= 0:
            return
        self.period["사업 수익"] -= amount
        self.retained -= amount
        self.week_net -= amount
        from_unbilled = min(self.unbilled, amount)
        self.unbilled -= from_unbilled
        self.advances += amount - from_unbilled

    def refund_advance(self, amount):
        """미수행분 착수금을 돌려준다 (사업 포기)."""
        if amount <= 0:
            return
        give = min(amount, self.advances)
        self.advances -= give
        self.cash -= give

    def collect(self, amount):
        """잔금 수령 — 미청구공사가 현금으로 바뀐다."""
        self.cash += amount
        self.unbilled = max(0.0, self.unbilled - amount)

    # ── 차입 ────────────────────────────────────────────────
    def loan_limit(self, equipment_book):
        return max(0, int(self.assets(equipment_book) * LOAN_LIMIT_RATE - self.debt))

    def borrow(self, product, amount, reputation):
        p = LOAN_PRODUCTS[product]
        rate = p["rate"] - (REPUTATION_RATE_CUT if reputation >= 12000 else 0)
        loan = Loan(amount, max(0.0005, rate), p["weeks"], p["label"])
        self.loans.append(loan)
        self.cash += amount
        return loan

    def weekly_interest(self):
        return sum(int(l.principal * l.rate) for l in self.loans)

    def tick_loans(self):
        """1주치 이자를 물고, 만기가 된 대출을 상환한다.

        상환 자금이 모자라면 갚지 못한 금액을 돌려준다 (파산 판정용).
        """
        events, unpaid = [], 0
        interest = self.weekly_interest()
        if interest:
            self.pay("이자비용", interest)
            events.append(f"대출 이자 ${interest:,} 지출")

        for loan in list(self.loans):
            loan.weeks_left -= 1
            if loan.weeks_left > 0:
                continue
            if self.cash >= loan.principal:
                self.cash -= loan.principal
                self.loans.remove(loan)
                events.append(f"{loan.label} ${loan.principal:,} 만기 상환")
            else:
                unpaid += loan.principal
                events.append(
                    f"{loan.label} ${loan.principal:,} 만기인데 상환 자금이 없습니다.")
        return events, unpaid

    # ── 결산 ────────────────────────────────────────────────
    def settle(self, week, equipment_book):
        """결산 — 손익을 확정하고 대차대조표를 기록한다."""
        revenue = sum(self.period[k] for k in REVENUE_KEYS)
        expense = sum(self.period.get(k, 0.0) for k in EXPENSE_KEYS)
        row = {
            "week": week,
            "revenue": int(revenue),
            "expense": int(expense),
            "net": int(revenue - expense),
            "breakdown": {k: int(v) for k, v in self.period.items() if v},
            "balance": self.balance_sheet(equipment_book),
        }
        self.history.insert(0, row)
        del self.history[12:]
        self.period = {k: 0.0 for k in REVENUE_KEYS + EXPENSE_KEYS}
        self.last_settled_week = week
        return row

    def balance_sheet(self, equipment_book):
        return {
            "assets": {
                "현금": int(self.cash),
                "미청구공사": int(self.unbilled),
                "설비": int(equipment_book),
                "합계": int(self.assets(equipment_book)),
            },
            "liabilities": {
                "미지급급여": int(self.accrued_wages),
                "선수금": int(self.advances),
                "차입금": int(self.debt),
                "합계": int(self.liabilities()),
            },
            "equity": {
                "자본금": int(self.capital),
                "이익잉여금": int(self.retained),
                "합계": int(self.equity()),
            },
        }

    def to_dict(self, equipment_book, week):
        revenue = sum(self.period[k] for k in REVENUE_KEYS)
        expense = sum(self.period.get(k, 0.0) for k in EXPENSE_KEYS)
        return {
            "balance": self.balance_sheet(equipment_book),
            "period": {
                "revenue": int(revenue),
                "expense": int(expense),
                "net": int(revenue - expense),
                "breakdown": {k: int(v) for k, v in self.period.items() if v},
                "weeks_elapsed": week - self.last_settled_week,
                "weeks_to_settle": max(
                    0, SETTLEMENT_WEEKS - (week - self.last_settled_week)),
            },
            "week_net": int(self.week_net),
            "loans": [l.to_dict() for l in self.loans],
            "loan_limit": self.loan_limit(equipment_book),
            "weekly_interest": self.weekly_interest(),
            "imbalance": self.check(equipment_book),
            "history": self.history,
        }
