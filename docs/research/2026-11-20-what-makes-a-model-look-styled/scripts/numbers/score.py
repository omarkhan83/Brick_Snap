"""Question 6: a "how modern does the parts list look" score, 0 to 100, from a parts list alone.

usage: uv run --project <repo> python -I score.py OUTDIR   (reads OUTDIR/feat.pkl from analyse.py)

Each measure is turned into a sub-score: 0 at the median of official sets of 1994-1996, 100 at the
median of official sets of 2021-2023 (straight line between, clipped to 0..100). The score is the
weighted mean of the sub-scores. The anchors are printed so the formula can be applied by hand.
"""
import collections
import csv
import os
import pickle
import statistics
import sys

OUT = sys.argv[1]
X = pickle.load(open(OUT + "/feat.pkl", "rb"))
F, MF = X["F"], X["MF"]

# measure: (function of a feature dict, weight)
MEASURES = {
    "age": (lambda f: f["age_mean"], 0.25),         # mean first year of the parts' designs (by parts)
    "smooth": (lambda f: f["smooth"], 0.20),        # tiles + studless small slopes + curved slopes
    "sideways": (lambda f: f["g_sideways"], 0.25),  # brackets + bricks with side studs
    "palette": (lambda f: f["c_later"], 0.15),      # share of parts in the later solid colours (not classic, not bluish greys)
    "bricks": (lambda f: f["g_brick"], 0.15),       # share of plain bricks (lower = modern)
}

old = [f for f in F.values() if 1994 <= f["year"] <= 1996]
new = [f for f in F.values() if 2021 <= f["year"] <= 2023]
ANCH = {k: (statistics.median(fn(f) for f in old), statistics.median(fn(f) for f in new)) for k, (fn, _w) in MEASURES.items()}


def subs(f):
    out = {}
    for k, (fn, _w) in MEASURES.items():
        a, b = ANCH[k]
        v = (fn(f) - a) / (b - a) if b != a else 0
        out[k] = 100 * min(1, max(0, v))
    return out


def score(f):
    s = subs(f)
    return sum(MEASURES[k][1] * s[k] for k in MEASURES) / sum(w for _fn, w in MEASURES.values())


def auc(xs, ys):
    """probability that a random new set scores above a random old one"""
    n = 0
    for x in xs:
        for y in ys:
            n += 1 if y > x else 0.5 if y == x else 0
    return n / (len(xs) * len(ys))


lines = []


def P(s=""):
    lines.append(s)


P("## Q6. A 'how modern does the parts list look' score\n")
P(f"Anchors: medians of {len(old)} official sets of 1994-1996 (score 0) and {len(new)} of 2021-2023 (score 100).\n")
P("| measure | weight | 0 at | 100 at | separation of 1995 vs 2022 sets (AUC of the measure alone) |")
P("|---|---:|---:|---:|---:|")
for k, (fn, w) in MEASURES.items():
    a, b = ANCH[k]
    o95 = [fn(f) for f in F.values() if f["year"] == 1995]
    n22 = [fn(f) for f in F.values() if f["year"] == 2022]
    A = auc(o95, n22)
    fmt = (lambda v: f"{v:.0f}") if k == "age" else (lambda v: f"{100 * v:.1f}%")
    P(f"| {k} | {w} | {fmt(a)} | {fmt(b)} | {max(A, 1 - A):.2f} |")
o95 = [score(f) for f in F.values() if f["year"] == 1995]
n22 = [score(f) for f in F.values() if f["year"] == 2022]
P(f"\nScore: 1995 sets median {statistics.median(o95):.0f} (n={len(o95)}), 2022 sets median {statistics.median(n22):.0f} "
  f"(n={len(n22)}); AUC {auc(o95, n22):.3f}.\n")

P("### Median score by year, all sets and aircraft+cars\n")
P("| year | sets | median score | 10th-90th percentile | aircraft+cars | their median |")
P("|---:|---:|---:|---|---:|---:|")
rows = []
for y in range(1990, 2027):
    fs = [f for f in F.values() if f["year"] == y]
    sc = sorted(score(f) for f in fs)
    vs = [score(f) for f in fs if f["subset"] in ("aircraft", "car")]
    q = statistics.quantiles(sc, n=10) if len(sc) >= 10 else [sc[0]] * 9
    rows.append([y, len(fs), round(statistics.median(sc)), round(q[0]), round(q[-1]), len(vs),
                 round(statistics.median(vs)) if vs else ""])
    if y % 2 == 0 or y == 1995 or y == 2026:
        P(f"| {y} | {len(fs)} | {statistics.median(sc):.0f} | {q[0]:.0f}-{q[-1]:.0f} | {len(vs)} | {rows[-1][6]} |")
with open(OUT + "/tables/q6_score_by_year.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["year", "sets", "median", "p10", "p90", "vehicle_sets", "vehicle_median"])
    w.writerows(rows)

# 20 official sets across the years: per year, the aircraft or car (else any set) of 150-600 parts nearest 250 parts
YRS = sorted({round(1990 + i * 36 / 19) for i in range(20)})
pick = []
for y in YRS:
    fs = [f for f in F.values() if f["year"] == y and f["subset"] in ("aircraft", "car")]
    if not fs:
        fs = [f for f in F.values() if f["year"] == y and 150 <= f["n"] <= 600]
    if fs:
        pick.append(min(fs, key=lambda f: (abs(f["n"] - 250), f["set"])))
P("\n### 20 official sets across the years\n")
P("| year | set | name | parts | age | smooth | sideways | palette | bricks | score |")
P("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|")
for f in pick:
    s = subs(f)
    P(f"| {f['year']} | {f['set']} | {f['name']} | {f['n']} | " + " | ".join(f"{s[k]:.0f}" for k in MEASURES) + f" | {score(f):.0f} |")

P("\n### Our builds and the 18 official models\n")
P("| model | parts | age | smooth | sideways | palette | bricks | score |")
P("|---|---:|---:|---:|---:|---:|---:|---:|")
allrows = []
for f in sorted(MF.values(), key=lambda f: (f["label"].startswith("omr"), -score(f))):
    s = subs(f)
    lab = f["label"] + ("" if not f["label"].startswith("omr") else f" {f['name']} ({f['year']})")
    P(f"| {lab} | {f['n']} | " + " | ".join(f"{s[k]:.0f}" for k in MEASURES) + f" | {score(f):.0f} |")
    allrows.append([lab, f["n"]] + [round(s[k]) for k in MEASURES] + [round(score(f))])
with open(OUT + "/tables/q6_scores_our_models.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["model", "parts"] + list(MEASURES) + ["score"])
    w.writerows(allrows)
ai = [score(f) for f in MF.values() if not f["label"].startswith("omr")]
om = [score(f) for f in MF.values() if f["label"].startswith("omr")]
P(f"\nMedian: our AI builds {statistics.median(ai):.0f} ({len(ai)}), the 18 official models {statistics.median(om):.0f}.")
ces = MF["free:cessna-172-skyhawk"]
pct = sum(1 for f in F.values() if 2018 <= f["year"] and f["subset"] == "aircraft" and score(f) < score(ces))
na = sum(1 for f in F.values() if 2018 <= f["year"] and f["subset"] == "aircraft")
P(f"Cessna {score(ces):.0f}: below {na - pct} of {na} official aircraft of 2018 onward.")
by = collections.defaultdict(list)
for f in F.values():
    by[f["year"]].append(score(f))
near = min(by, key=lambda y: abs(statistics.median(by[y]) - score(ces)))
P(f"The year whose median set scores closest to the Cessna: {near}.")
open(OUT + "/score.md", "w").write("\n".join(lines) + "\n")
print("\n".join(lines))
