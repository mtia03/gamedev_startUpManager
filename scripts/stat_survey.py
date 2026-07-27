"""현재 developer.py가 실제로 생성하는 스탯 분포 측정."""
import sys, os, io, statistics, contextlib

# developer.py가 'resources/...' 상대경로를 쓰므로 리포 루트로 이동해야 한다
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from developer import Developer

N = 4000
FIELDS = ["FE", "BE", "Mobile", "AI", "Ops", "UIUX"]


def gen(n, reputation, first=True):
    devs = []
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        for _ in range(n):
            devs.append(Developer(first, reputation))
    return devs


def pct(vals, p):
    vals = sorted(vals)
    return vals[min(len(vals) - 1, int(len(vals) * p / 100))]


def report(title, devs):
    print(f"\n{'='*70}\n{title}  (n={len(devs)})\n{'='*70}")
    # 학력 분포
    edu_count = {}
    for d in devs:
        edu_count[d.education] = edu_count.get(d.education, 0) + 1
    print("학력 분포:", {k: f"{v/len(devs)*100:.1f}%" for k, v in
                      sorted(edu_count.items(), key=lambda x: -x[1])})

    print(f"\n{'학력':<6}{'n':>6}{'CA평균':>9}{'CA p10':>8}{'CA p50':>8}{'CA p90':>8}"
          f"{'주분야평균':>11}{'주분야p50':>10}{'부분야평균':>11}{'PA-CA평균':>11}")
    for edu in ["None", "BD", "MD", "PhD"]:
        sub = [d for d in devs if d.education == edu]
        if not sub:
            continue
        ca = [d.CA for d in sub]
        main = [d.stats[d.main_field] for d in sub]
        sec = [d.stats[f] for d in sub for f in FIELDS if f != d.main_field]
        gap = [d.PA - d.CA for d in sub]
        print(f"{edu:<6}{len(sub):>6}{statistics.mean(ca):>9.1f}{pct(ca,10):>8}"
              f"{pct(ca,50):>8}{pct(ca,90):>8}{statistics.mean(main):>11.1f}"
              f"{pct(main,50):>10}{statistics.mean(sec):>11.1f}{statistics.mean(gap):>11.1f}")

    # 주분야 캡(50) 도달 비율
    print("\n주분야 50 캡 도달률:", end=" ")
    for edu in ["None", "BD", "MD", "PhD"]:
        sub = [d for d in devs if d.education == edu]
        if sub:
            capped = sum(1 for d in sub if d.stats[d.main_field] >= 50)
            print(f"{edu}={capped/len(sub)*100:.0f}%", end="  ")
    print()

    # 전체 CA 분포
    ca_all = [d.CA for d in devs]
    print(f"전체 CA: 평균 {statistics.mean(ca_all):.1f} / "
          f"p10 {pct(ca_all,10)} / p50 {pct(ca_all,50)} / p90 {pct(ca_all,90)} / "
          f"max {max(ca_all)}")

    # 특정 분야 기준: 그 분야 스탯이 X 이상인 인원 비율
    print("\n임의 1개 분야(예: BE) 스탯 구간별 인원 비율:")
    be = [d.stats["BE"] for d in devs]
    for th in [10, 20, 30, 40, 50]:
        print(f"  BE >= {th:>2}: {sum(1 for v in be if v >= th)/len(be)*100:>5.1f}%", end="")
    print()


for rep, label in [(3000, "명성 3,000 (초기 스타트업 풀)"),
                   (8000, "명성 8,000 (성장 스타트업 풀)"),
                   (15000, "명성 15,000 (대기업급 풀)")]:
    report(label, gen(N, rep))

report("firstGen=False (일반 시장 풀)", gen(N, 0, first=False))
