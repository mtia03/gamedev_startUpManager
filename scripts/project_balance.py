"""프로젝트 규모별 요구 공수 / 적정 인원 밸런스 검증 시뮬레이터.

실측 기준값 (developer.py 4,000명 샘플):
  학력별 주분야 스탯: None 11 / BD 28 / MD 49 / PhD 50
  학력별 부분야 스탯: None 4.6 / BD 9.6 / MD 14.1 / PhD 26.1
"""
import sys, os, io, contextlib, statistics

# developer.py가 'resources/...' 상대경로를 쓰므로 리포 루트로 이동해야 한다
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from developer import Developer

FIELDS = ["FE", "BE", "Mobile", "AI", "Ops", "UIUX"]

# ── 튜닝 파라미터 ────────────────────────────────────────────────
SUB_FIELD_COEF = 0.25   # 부분야 기여 계수
COMM_FREE      = 7      # 이 인원까지는 커뮤니케이션 손실 없음
COMM_PENALTY   = 0.02   # 초과 1명당 처리량 감소
COMM_FLOOR     = 0.60   # 커뮤니케이션 효율 하한

# ── 프로젝트 등급 정의 ──────────────────────────────────────────
# req_per_field = 기준인원(BD 주력) × 28 × 목표주차
TIERS = [
    # name,             인원, 목표주, 필드수, 필드당요구, 게이트(필드당최소, 에이스스탯, 에이스수)
    ("T1 프로토타입/외주",  2,   4,  2,    112,  (0,  0,  0)),
    ("T2 MVP",             4,   8,  3,    275,  (10, 25, 1)),
    ("T3 정식 제품 v1",     8,  12,  4,    800,  (15, 45, 1)),
    ("T4 스케일업 플랫폼", 15,  20,  5,   1680,  (25, 45, 2)),
    ("T5 전사 대형",       32,  32,  6,   4480,  (25, 45, 6)),
]


def make_devs(n, reputation, force_edu=None):
    """개발자 n명 생성. force_edu 지정 시 해당 학력만 채택."""
    out, buf = [], io.StringIO()
    with contextlib.redirect_stdout(buf):
        while len(out) < n:
            d = Developer(True, reputation)
            if force_edu is None or d.education == force_edu:
                out.append(d)
    return out


def build_team(size, active_fields, edu_mix, reputation=8000):
    """active_fields에 균등 분배되도록 주분야를 강제 배정한 팀 구성.
    edu_mix: [(학력, 비율), ...]"""
    team = []
    for edu, ratio in edu_mix:
        cnt = round(size * ratio)
        team += make_devs(cnt, reputation, force_edu=edu)
    while len(team) < size:
        team += make_devs(1, reputation, force_edu=edu_mix[-1][0])
    team = team[:size]
    # 주분야를 요구 필드에 라운드로빈 재배정 (플레이어가 최적 배치했다고 가정)
    for i, d in enumerate(team):
        target = active_fields[i % len(active_fields)]
        old = d.main_field
        if old != target:
            d.stats[old], d.stats[target] = d.stats[target], d.stats[old]
            d.main_field = target
    return team


def throughput(team, field):
    """팀의 해당 필드 주당 처리량."""
    raw = sum(d.stats[field] * (1.0 if d.main_field == field else SUB_FIELD_COEF)
              for d in team)
    n = len(team)
    comm = max(COMM_FLOOR, 1.0 - COMM_PENALTY * max(0, n - COMM_FREE))
    morale_eff = statistics.mean(
        (0.5 + 0.5 * d.morale / 100) * (1 - 0.4 * d.fatigue / 100) for d in team)
    return raw * comm * morale_eff


def weeks_to_finish(team, active_fields, req_per_field):
    """가장 느린 필드가 전체 기간을 결정."""
    return max(req_per_field / throughput(team, f) for f in active_fields)


def check_gate(team, active_fields, gate):
    per_field_min, ace_stat, ace_cnt = gate
    for f in active_fields:
        if not any(d.stats[f] >= per_field_min for d in team):
            return False, f"{f} 필드에 스탯 {per_field_min}+ 인원 없음"
    if ace_cnt:
        aces = sum(1 for d in team if max(d.stats.values()) >= ace_stat)
        if aces < ace_cnt:
            return False, f"스탯 {ace_stat}+ 에이스 {ace_cnt}명 필요 (현재 {aces}명)"
    return True, "통과"


MIXES = {
    "전원 BD (표준)":        [("BD", 1.0)],
    "BD+MD 반반":            [("MD", 0.5), ("BD", 0.5)],
    "PhD 25% + BD":          [("PhD", 0.25), ("BD", 0.75)],
    "None 50% + BD (저렴)":  [("None", 0.5), ("BD", 0.5)],
}

print("=" * 100)
print(" 프로젝트 등급별 밸런스 검증  (부분야계수 %.2f / 팀%d명초과 시 %.0f%%씩 감소, 하한 %.0f%%)"
      % (SUB_FIELD_COEF, COMM_FREE, COMM_PENALTY * 100, COMM_FLOOR * 100))
print("=" * 100)

for name, size, target_w, nfield, req, gate in TIERS:
    active = FIELDS[:nfield]
    total_req = req * nfield
    print(f"\n■ {name}")
    print(f"   기준 인원 {size}명 / 목표 {target_w}주 / 요구 필드 {nfield}개 "
          f"/ 필드당 {req:,} / 총 {total_req:,} 공수")
    print(f"   {'팀 구성':<22}{'인원':>5}{'필드당 주간처리량':>18}{'완료주차':>10}{'목표대비':>10}   게이트")
    for mix_name, mix in MIXES.items():
        team = build_team(size, active, mix)
        tp = statistics.mean(throughput(team, f) for f in active)
        w = weeks_to_finish(team, active, req)
        ok, msg = check_gate(team, active, gate)
        ratio = w / target_w
        verdict = "빠름" if ratio < 0.85 else ("적정" if ratio <= 1.15 else "느림")
        print(f"   {mix_name:<22}{size:>5}{tp:>18.1f}{w:>10.1f}"
              f"{ratio:>9.2f}x {verdict}   {'OK' if ok else 'X ' + msg}")

# ── 인원 증감 민감도 (T3 기준) ─────────────────────────────────
print("\n" + "=" * 100)
print(" 인원 투입 대비 기간 단축 (T3 정식제품 v1, 요구 800/필드 × 4필드, 전원 BD)")
print("=" * 100)
active = FIELDS[:4]
print(f" {'인원':>5}{'필드당 처리량':>16}{'커뮤효율':>10}{'완료주차':>10}{'인·주 총비용':>14}{'한계효율':>12}")
prev_w = None
for n in [4, 6, 8, 10, 12, 16, 20, 24, 32, 40]:
    team = build_team(n, active, [("BD", 1.0)])
    tp = statistics.mean(throughput(team, f) for f in active)
    comm = max(COMM_FLOOR, 1.0 - COMM_PENALTY * max(0, n - COMM_FREE))
    w = weeks_to_finish(team, active, 800)
    cost = n * w
    delta = f"{(prev_w - w):>11.1f}주" if prev_w else f"{'-':>12}"
    print(f" {n:>5}{tp:>16.1f}{comm:>10.2f}{w:>10.1f}{cost:>14.0f}{delta}")
    prev_w = w


print("\n" + "=" * 100)
print(" 등급별 비용최적 인원 탐색 (전원 BD, 인·주 총비용 최소 지점 = 적정 인원)")
print("=" * 100)
print(f" {'등급':<20}{'적정인원':>9}{'그때 주차':>10}{'최소비용':>10}{'>=1.15x 느려지는 하한':>22}{'추가효과 소멸(+1명<0.3주)':>26}")
for name, size, target_w, nfield, req, gate in TIERS:
    active = FIELDS[:nfield]
    rows = []
    for n in range(1, 61):
        team = build_team(n, active, [("BD", 1.0)])
        w = weeks_to_finish(team, active, req)
        rows.append((n, w, n * w))
    best = min(rows, key=lambda r: r[2])
    slow = [n for n, w, c in rows if w <= target_w * 1.15]
    floor_n = min(slow) if slow else None
    dead = None
    for i in range(1, len(rows)):
        if rows[i-1][1] - rows[i][1] < 0.3 and rows[i][0] >= best[0]:
            dead = rows[i][0]; break
    print(f" {name:<20}{best[0]:>9}{best[1]:>10.1f}{best[2]:>10.0f}"
          f"{(str(floor_n) + '명'):>22}{(str(dead) + '명 이후'):>26}")
