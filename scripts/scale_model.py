"""규모 S -> 3축 요구치(인원/개인하한/총능력합) 및 초기 성공확률 모델 산출."""
import math

# 실측 학력별 스탯 (developer.py 4,000명 샘플)
EDU = {  # 주분야, 부분야, CA
    "None": (11.0, 4.6, 34),
    "BD":   (27.8, 9.6, 76),
    "MD":   (49.4, 14.1, 120),
    "PhD":  (50.0, 26.1, 180),
}

# ── 규모 -> 요구치 공식 ────────────────────────────────────────
def work(S):        return 20 * S ** 1.10          # 총 요구 공수
def crew(S):        return 0.5 * S ** 0.60         # 권장 인원
def floor_stat(S):  return 10 * math.log10(S)      # 개인 주력필드 스탯 하한
def ace_count(S):   return round(crew(S) * 0.15)   # 스탯 45+ 에이스 요구 수
def ca_avg(S):      return 74 + 4 * math.log10(S)  # 권장 평균 CA
def total_ca(S):    return crew(S) * ca_avg(S)     # 총 능력치 합(ΣCA)
def fields(S):
    for lim, f in [(20, 2), (50, 3), (150, 4), (500, 5)]:
        if S < lim: return f
    return 6

TIERS = [(10, "프로토타입/외주"), (30, "MVP"), (100, "정식 제품 v1"),
         (300, "스케일업 플랫폼"), (1000, "전사 대형")]

# ── 초기 성공 확률 모델 ────────────────────────────────────────
W_N, W_F, W_T = 0.25, 0.35, 0.40   # 인원 / 개인하한 충족률 / 총능력합
P_MAX, CENTER, K = 0.95, 0.80, 7.0
CLAMP_HI  = 1.20                    # 과잉 투입 보상 상한
UNDER_PEN = 1.0                     # 인원 부족 페널티 계수
OVER_PEN  = 0.5                     # 인원 과잉 페널티 계수 (Brooks)


def r_headcount(n, n_req):
    """인원 적합도 — 권장치에서 1.0, 부족/과잉 양방향으로 감소."""
    x = n / n_req
    return max(0.0, 1 - max(0, 1 - x) * UNDER_PEN - max(0, x - 1) * OVER_PEN)


def score(r_n, r_f, r_t):
    return W_N * min(r_n, CLAMP_HI) + W_F * min(r_f, 1.0) + W_T * min(r_t, CLAMP_HI)


def prob(sc):
    return P_MAX / (1 + math.exp(-K * (sc - CENTER)))


def eval_team(S, comp):
    """comp: {학력: 인원수} -> 3축 비율, 종합점수, 초기확률"""
    n = sum(comp.values())
    n_req, f_req, t_req = crew(S), floor_stat(S), total_ca(S)
    tca  = sum(EDU[e][2] * c for e, c in comp.items())
    meet = sum(c for e, c in comp.items() if EDU[e][0] >= f_req)
    aces = sum(c for e, c in comp.items() if EDU[e][0] >= 45)
    r_n, r_f, r_t = r_headcount(n, n_req), meet / n, tca / t_req
    sc = score(r_n, r_f, r_t)
    return dict(n=n, tca=tca, meet=meet, aces=aces, r_n=r_n, r_f=r_f, r_t=r_t,
                sc=sc, p=prob(sc), gate_ace=aces >= ace_count(S),
                gate_n=n >= math.ceil(n_req * 0.70))


print("=" * 112)
print(" [표 A] 규모별 요구치 원본 산출  (권장 기준 = 100%)")
print("=" * 112)
print(f"{'규모':>6}  {'등급':<18}{'요구공수':>10}{'필드수':>7}{'권장인원':>9}"
      f"{'개인하한':>9}{'에이스45+':>10}{'권장평균CA':>11}{'총능력합ΣCA':>13}")
for S, name in TIERS:
    print(f"{S:>6}  {name:<18}{work(S):>10,.0f}{fields(S):>7}{crew(S):>9.1f}"
          f"{floor_stat(S):>9.1f}{ace_count(S):>10}{ca_avg(S):>11.0f}{total_ca(S):>13,.0f}")

print("\n" + "=" * 112)
print(" [표 B] 3단계 요구치  (권장 100% / 양호 85% / 최소 70%)")
print("=" * 112)
print(f"{'규모':>6}  {'등급':<18}{'인원 최소/양호/권장':>22}"
      f"{'개인하한 최소/양호/권장':>26}{'ΣCA 최소/양호/권장':>28}")
for S, name in TIERS:
    n, f_, t = crew(S), floor_stat(S), total_ca(S)
    n3 = f"{math.ceil(n*0.70)} / {math.ceil(n*0.85)} / {math.ceil(n)}"
    f3 = f"{f_*0.70:.0f} / {f_*0.85:.0f} / {f_:.0f}"
    t3 = f"{t*0.70:,.0f} / {t*0.85:,.0f} / {t:,.0f}"
    print(f"{S:>6}  {name:<18}{n3:>22}{f3:>26}{t3:>28}")

print("\n" + "=" * 112)
print(" [표 C] 종합점수 -> 초기 성공확률")
print("=" * 112)
for sc in [0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20]:
    p = prob(sc)
    v = ("무모" if p < .30 else "위험" if p < .50 else
         "양호" if p < .65 else "권장 안정권" if p < .82 else "과잉")
    print(f"  Score {sc:>5.2f}  ->  초기 성공확률 {p*100:>5.1f}%   {v}")

print("\n" + "=" * 112)
print(" [표 D] 균등 충족 수준별 초기 성공확률")
print("=" * 112)
for label, r in [("최소만 충족 (70%)", .70), ("양호 (85%)", .85), ("권장 (100%)", 1.00),
                 ("권장 +20%", 1.20)]:
    sc = score(r if r >= 1 else r, r, r)
    print(f"  {label:<22} r=({r:.2f}, {r:.2f}, {r:.2f})  Score {sc:>5.3f}  ->  {prob(sc)*100:>5.1f}%")

print("\n" + "=" * 112)
print(" [표 E] 팀 구성 사례별 초기 성공확률 — 규모 100 (정식 제품 v1)")
print("=" * 112)
S = 100
print(f" 권장: 인원 {crew(S):.0f}명 / 개인 주력필드 하한 {floor_stat(S):.0f} / "
      f"ΣCA {total_ca(S):,.0f} / 에이스 45+ {ace_count(S)}명\n")
print(f"{'팀 구성':<34}{'인원':>5}{'하한충족':>9}{'ΣCA':>7}{'r_N':>6}{'r_F':>6}"
      f"{'r_T':>6}{'Score':>8}{'초기확률':>10}  게이트")
CASES = [
    ("BD 8 (표준)",              {"BD": 8}),
    ("BD 6 + MD 2 (권장형)",     {"BD": 6, "MD": 2}),
    ("BD 5 + PhD 2",            {"BD": 5, "PhD": 2}),
    ("MD 5 (소수정예)",          {"MD": 5}),
    ("PhD 4 (초소수정예)",       {"PhD": 4}),
    ("BD 5 (인원부족)",          {"BD": 5}),
    ("None 8 (저학력)",          {"None": 8}),
    ("BD 4 + None 12 (물량)",   {"BD": 4, "None": 12}),
    ("BD 20 (대군)",            {"BD": 20}),
]
for label, comp in CASES:
    r = eval_team(S, comp)
    g = "OK" if (r["gate_ace"] and r["gate_n"]) else (
        "X 에이스부족" if not r["gate_ace"] else "X 인원미달")
    print(f"{label:<34}{r['n']:>5}{r['meet']:>9}{r['tca']:>7,}{r['r_n']:>6.2f}"
          f"{r['r_f']:>6.2f}{r['r_t']:>6.2f}{r['sc']:>8.3f}{r['p']*100:>9.1f}%  {g}")

print("\n" + "=" * 112)
print(" [표 F] 스케일 상수 조정 — 규모 100에서 원하는 인원별 계수 a  (N = a × S^0.6)")
print("=" * 112)
print(f"{'규모100 인원':>12}{'계수 a':>9}{'S=10':>8}{'S=30':>8}{'S=300':>9}{'S=1000':>9}"
      f"{'커뮤효율(S=100)':>18}")
for target in [8, 12, 20, 30, 50]:
    a = target / 100 ** 0.6
    eff = max(0.60, 1 - 0.02 * max(0, target - 7))
    print(f"{target:>12}{a:>9.2f}{a*10**0.6:>8.1f}{a*30**0.6:>8.1f}"
          f"{a*300**0.6:>9.1f}{a*1000**0.6:>9.1f}{eff*100:>17.0f}%")
