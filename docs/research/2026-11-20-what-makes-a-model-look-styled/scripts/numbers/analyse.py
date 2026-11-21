"""Questions 1 to 5 of the style-numbers study.

usage: uv run --project <repo> python -I analyse.py rb.pkl ldraw_index.json models.json OUTDIR

Writes OUTDIR/tables/*.csv (full tables), OUTDIR/tables.md (compact tables) and OUTDIR/feat.pkl
(per-set and per-model features, for score.py). Credit: set inventories from the Rebrickable
catalogue (rebrickable.com), November 2026.
"""
import collections
import csv
import json
import os
import pickle
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import GROUPS, GROUP_KEYS, base_ok, make_part_group, med, subset_of  # noqa: E402
from features import features, model_tally  # noqa: E402

d = pickle.load(open(sys.argv[1], "rb"))
IDX = json.load(open(sys.argv[2]))
M = json.load(open(sys.argv[3]))
OUT = sys.argv[4]
os.makedirs(OUT + "/tables", exist_ok=True)
pg = make_part_group(d["parts"])
colors = d["colors"]
LAST = 2026
YEARS = list(range(1990, LAST + 1))
md = open(OUT + "/tables.md", "w")


def P(*a):
    print(*a, file=md)


def pct(x, nd=1):
    return "" if x is None else f"{100 * x:.{nd}f}"


def write_csv(name, header, rows):
    with open(f"{OUT}/tables/{name}.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def cname(c):
    return colors[c][0] if c in colors else str(c)


# ------------------------------------------------------------ features of every set in the population
F = {}
for s, (name, year, tid, _n) in d["sets"].items():
    if not (1990 <= year <= LAST) or not base_ok(s, d) or s not in d["tally"]:
        continue
    num, _, ver = s.rpartition("-")
    if ver != "1" and num + "-1" in d["sets"]:  # a variant (other airline, other print) of a set already counted
        continue
    f = features(d["tally"][s], d, pg)
    if f is None or f["n"] < 25:
        continue
    f["year"], f["name"], f["set"] = year, name, s
    f["subset"] = subset_of(s, d, f["n"])
    if f["subset"] in ("aircraft", "car") and f["g_technic"] + f["g_technic_other"] > 0.3:
        f["subset"] = None  # Technic-built racers (radio-control and similar), not studded models
    F[s] = f
by_year = collections.defaultdict(list)
for f in F.values():
    by_year[f["year"]].append(f)

# ------------------------------------------------------------ our models
DUP = {"early:hybrid/duck", "early:with-tools/car", "early:with-tools/cat", "early:with-tools/car-by-opus",
       "early:with-tools/flower", "early:with-tools/our-car", "early:with-tools/our-cat", "early:with-tools/our-duck"}
MF = {}
for k, e in M.items():
    if k in DUP:
        continue
    f = features(model_tally(e), d, pg)
    f["label"] = k
    f["unmapped"] = sum(e["unmapped"].values())
    f["dropped"] = e["dropped_sticker_minifig"]
    if k.startswith("omr:"):
        s = k[4:] + "-1"
        f["year"] = d["sets"][s][1] if s in d["sets"] else None
        f["name"] = d["sets"][s][0] if s in d["sets"] else k
    MF[k] = f
AI = [f for k, f in MF.items() if not k.startswith("omr:")]
OMR = [f for k, f in MF.items() if k.startswith("omr:")]


def agg(fs, key):
    """parts-weighted share (sum over sets) of a share-type feature"""
    tot = sum(f["n"] for f in fs)
    return sum(f[key] * f["n"] for f in fs) / tot if tot else None


# ------------------------------------------------------------ Q1
P("# Tables of the style-numbers study\n")
P("Set inventories from the Rebrickable catalogue (rebrickable.com), November 2026. Totals only.\n")
P(f"Population: {len(F)} sets of {YEARS[0]} to {LAST} (system themes, at least 25 building parts; see the report).\n")
P("## Q1. Mix of parts by year (parts-weighted share, %)\n")
gk = GROUP_KEYS
rows = []
for y in YEARS:
    fs = by_year[y]
    rows.append([y, len(fs), sum(f["n"] for f in fs)] + [pct(agg(fs, "g_" + k), 2) for k in gk]
                + [pct(med([f["g_" + k] for f in fs]), 2) for k in gk] + [pct(agg(fs, "smooth"), 2)])
write_csv("q1_mix_by_year", ["year", "sets", "parts"] + ["w_" + k for k in gk] + ["med_" + k for k in gk]
          + ["w_smooth"], rows)
show = ["brick", "plate", "tile", "slope", "smooth_slope", "curved", "wedge", "sideways", "jumper", "clipbar",
        "hinge", "technic"]
SHOWY = [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025, LAST]
SHOWY = sorted(set(SHOWY))
P("| year | sets | " + " | ".join(show) + " | smooth (tile+studless+curved) |")
P("|---" * (len(show) + 3) + "|")
for y in SHOWY:
    fs = by_year[y]
    P(f"| {y} | {len(fs)} | " + " | ".join(pct(agg(fs, 'g_' + k)) for k in show) + f" | {pct(agg(fs, 'smooth'))} |")
P("\nMedian set (median of per-set shares, %):\n")
P("| year | " + " | ".join(show) + " | smooth |")
P("|---" * (len(show) + 2) + "|")
for y in SHOWY:
    fs = by_year[y]
    P(f"| {y} | " + " | ".join(pct(med([f['g_' + k] for f in fs])) for k in show)
      + f" | {pct(med([f['smooth'] for f in fs]))} |")

# ------------------------------------------------------------ Q2
PERIODS = [("1990-1999", 1990, 1999), ("2000-2004", 2000, 2004), ("2005-2011", 2005, 2011), ("2012-2017", 2012, 2017),
           ("2018-" + str(LAST), 2018, LAST)]
NEWP = PERIODS[4]


def in_period(f, a, b):
    return a <= f["year"] <= b


P("\n## Q2. The kinds of set closest to our builds\n")
P("aircraft: 90 to 600 building parts (old aircraft were small); cars: 150 to 600; creatures: Creator animals 50 to 1,500, BrickHeadz and Botanicals 20 to 1,500.\n")
q2rows = []
for sub in ("aircraft", "car", "vehicle", "creature"):
    P(f"\n### {sub}\n")
    P("| period | sets | " + " | ".join(show) + " | smooth |")
    P("|---" * (len(show) + 3) + "|")
    for lab, a, b in PERIODS:
        fs = [f for f in F.values() if (f["subset"] == sub or sub == "vehicle" and f["subset"] in ("aircraft", "car"))
              and in_period(f, a, b)]
        if not fs:
            continue
        P(f"| {lab} | {len(fs)} | " + " | ".join(pct(agg(fs, 'g_' + k)) for k in show) + f" | {pct(agg(fs, 'smooth'))} |")
        P(f"| {lab} median set | | " + " | ".join(pct(med([f['g_' + k] for f in fs])) for k in show)
          + f" | {pct(med([f['smooth'] for f in fs]))} |")
        q2rows.append([sub, lab, len(fs)] + [pct(agg(fs, "g_" + k), 2) for k in gk] + [pct(agg(fs, "smooth"), 2)]
                      + [pct(med([f["g_" + k] for f in fs]), 2) for k in gk])
write_csv("q2_mix_by_subset_period", ["subset", "period", "sets"] + ["w_" + k for k in gk] + ["w_smooth"]
          + ["med_" + k for k in gk], q2rows)


def typical(fs, k=5):
    keys = ["g_" + x for x in show] + ["age_ge2005", "c_classic"]
    mean = {x: statistics.mean(f[x] for f in fs) for x in keys}
    sd = {x: (statistics.pstdev(f[x] for f in fs) or 1) for x in keys}
    return sorted(fs, key=lambda f: sum(((f[x] - mean[x]) / sd[x]) ** 2 for x in keys))[:k]


P("\n### Representative sets (closest to their group's average on the part-mix, age and colour numbers)\n")
P("| group | period | set | name | year | parts |")
P("|---|---|---|---|---:|---:|")
reps = []
for sub in ("aircraft", "car", "creature"):
    for lab, a, b in (PERIODS[0], NEWP) if sub != "creature" else (("2001-2010", 2001, 2010), NEWP):
        fs = [f for f in F.values() if f["subset"] == sub and in_period(f, a, b)]
        for f in typical(fs) if len(fs) >= 5 else fs:
            P(f"| {sub} | {lab} | {f['set']} | {f['name']} | {f['year']} | {f['n']} |")
            reps.append([sub, lab, f["set"], f["name"], f["year"], f["n"]])
write_csv("q2_representative_sets", ["subset", "period", "set", "name", "year", "parts"], reps)
# full membership lists, so the selection can be checked
write_csv("q2_membership", ["subset", "set", "name", "year", "parts"],
          sorted([[f["subset"], f["set"], f["name"], f["year"], f["n"]] for f in F.values() if f["subset"]],
                 key=lambda r: (r[0], r[3])))

# ------------------------------------------------------------ Q3
P("\n## Q3. Parts' age\n")
P("Median first-year = median (by parts) of the first year each part design appears in any set; shares are of parts.\n")
rows = []
for y in YEARS:
    fs = by_year[y]
    vs = [f for f in fs if f["subset"] in ("aircraft", "car")]
    rows.append([y, len(fs), med([f["age_median"] for f in fs]), med([y - f["age_median"] for f in fs])]
                + [pct(agg(fs, f"age_ge{c}"), 1) for c in (2000, 2005, 2010, 2015)]
                + [len(vs), med([f["age_median"] for f in vs])] + [pct(agg(vs, f"age_ge{c}"), 1) if vs else "" for c in (2000, 2005, 2010, 2015)])
write_csv("q3_age_by_year", ["year", "sets", "median_first_year", "median_age_gap", "ge2000", "ge2005", "ge2010", "ge2015",
                             "vehicle_sets", "veh_median_first_year", "veh_ge2000", "veh_ge2005", "veh_ge2010", "veh_ge2015"], rows)
P("| year | sets | median first-year (median set) | set year minus it | % parts 2000+ | 2010+ | 2015+ | aircraft+cars: sets | median first-year | 2000+ | 2010+ | 2015+ |")
P("|---" * 12 + "|")
for r in rows:
    if r[0] in SHOWY:
        P(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[6]} | {r[7]} | {r[8]} | {r[9] or ''} | {r[10]} | {r[12]} | {r[13]} |")

# usage rates: modern vehicles vs our AI builds
modern_veh = [s for s, f in F.items() if f["subset"] in ("aircraft", "car") and f["year"] >= 2018]
old_veh = [s for s, f in F.items() if f["subset"] in ("aircraft", "car") and f["year"] <= 1999]


def usage(tallies):
    c = collections.Counter()
    nsets = collections.Counter()
    tot = 0
    for t in tallies:
        seen = set()
        for (p, col), q in t.items():
            if pg.get(p, "other") is None:
                continue
            c[p] += q
            tot += q
            seen.add(p)
        for p in seen:
            nsets[p] += 1
    return {p: 1000 * q / tot for p, q in c.items()}, nsets, tot


mod_rate, mod_sets, mod_tot = usage([d["tally"][s] for s in modern_veh])
old_rate, old_sets, old_tot = usage([d["tally"][s] for s in old_veh])
ai_rate, ai_sets, ai_tot = usage([model_tally(M[f["label"]]) for f in AI])
rev = collections.defaultdict(list)
for stem, v in IDX.items():
    for k in v["rb"]:
        rev[k].append(stem)


def ldraw_of(p):
    if p in IDX and not IDX[p]["moved"]:
        return p + ".dat"
    if rev.get(p):
        return rev[p][0] + ".dat"
    for suf in ("b", "a", "c"):
        if p + suf in IDX and not IDX[p + suf]["moved"]:
            return p + suf + ".dat"
    if p in IDX:
        return p + ".dat (moved to " + (IDX[p]["moved"] or "") + ")"
    return ""


cands = []
for p, r in mod_rate.items():
    y = d["first_year"].get(p)
    if y is None or y < 2005:
        continue
    a = ai_rate.get(p, 0.0)
    if a < 0.25 * r:
        cands.append((r, p))
cands.sort(reverse=True)
P(f"\n### 40 designs introduced since 2005, most used in modern aircraft and cars ({len(modern_veh)} sets, 2018-{LAST}) and rare in our {len(AI)} AI builds\n")
P("Rates are parts per 1,000 building parts. 'AI' pools all our AI builds (duplicates removed).\n")
P("| # | Rebrickable | LDraw file | name | first year | group | modern per 1000 | % of modern sets | AI per 1000 | AI builds using |")
P("|---:|---|---|---|---:|---|---:|---:|---:|---:|")
rows = []
for i, (r, p) in enumerate(cands[:40], 1):
    nm, _c = d["parts"][p]
    row = [i, p, ldraw_of(p), nm, d["first_year"][p], pg[p], f"{r:.1f}", pct(mod_sets[p] / len(modern_veh), 0),
           f"{ai_rate.get(p, 0):.1f}", ai_sets.get(p, 0)]
    rows.append(row)
    P("| " + " | ".join(map(str, row)) + " |")
write_csv("q3_new_parts_missing_from_ai", ["rank", "rebrickable", "ldraw", "name", "first_year", "group", "modern_per1000",
                                           "pct_modern_sets", "ai_per1000", "ai_builds_using"], rows)

old_lean = []
for p, a in ai_rate.items():
    y = d["first_year"].get(p)
    if y is None or y >= 2005 or pg.get(p) is None:
        continue
    r = mod_rate.get(p, 0.0)
    if a >= 2 * r and a - r >= 3:
        old_lean.append((a - r, p))
old_lean.sort(reverse=True)
P(f"\n### 20 designs from before 2005 that our AI builds lean on, used much less in modern aircraft and cars\n")
P("| # | Rebrickable | LDraw file | name | first year | group | AI per 1000 | AI builds using | modern per 1000 | 1990s vehicles per 1000 |")
P("|---:|---|---|---|---:|---|---:|---:|---:|---:|")
rows = []
for i, (_x, p) in enumerate(old_lean[:20], 1):
    nm, _c = d["parts"][p]
    row = [i, p, ldraw_of(p), nm, d["first_year"][p], pg[p], f"{ai_rate[p]:.1f}", ai_sets[p], f"{mod_rate.get(p, 0):.1f}",
           f"{old_rate.get(p, 0):.1f}"]
    rows.append(row)
    P("| " + " | ".join(map(str, row)) + " |")
write_csv("q3_old_parts_ai_leans_on", ["rank", "rebrickable", "ldraw", "name", "first_year", "group", "ai_per1000",
                                       "ai_builds_using", "modern_per1000", "old_vehicles_per1000"], rows)

# ------------------------------------------------------------ Q4
P("\n## Q4. Colour\n")
CLS = ["classic", "new_grey", "later", "old_other", "trans", "metal"]
NAMED = [0, 15, 4, 1, 14, 7, 8, 71, 72, 2, 19, 28, 70, 272, 320, 288, 379, 378, 84, 191, 484, 25, 322, 321, 326, 31, 30, 27, 226, 308]
rows = []
for y in YEARS:
    fs = by_year[y]
    tot = sum(f["n"] for f in fs)
    cc = collections.Counter()
    for f in fs:
        for c, q in f["colours"].items():
            cc[c] += q
    rows.append([y, len(fs)] + [pct(agg(fs, "c_" + k), 2) for k in CLS] + [pct(agg(fs, "primaries"), 2),
                med([f["n_colours5"] for f in fs]), pct(med([f["primaries"] for f in fs]), 1)]
                + [pct(cc[c] / tot, 2) for c in NAMED])
write_csv("q4_colour_by_year", ["year", "sets"] + ["w_" + k for k in CLS] + ["w_primaries", "med_n_colours_ge5pct",
          "med_primaries"] + [cname(c) for c in NAMED], rows)
P("Classes: classic = black, white, red, blue, yellow, light gray, dark gray; new greys = light and dark bluish gray; later = the later solid colours (list in the report); old other = other solid colours on sale before 1994 (green, brown, ...).\n")
P("| year | sets | classic % | of which R+B+Y % | new greys % | later colours % | old other % | trans % | metallic % | colours with 5%+ (median set) | R+B+Y share (median set) % |")
P("|---" * 11 + "|")
for r in rows:
    if r[0] in SHOWY:
        P(f"| {r[0]} | {r[1]} | {r[2]} | {r[8]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} | {r[9]} | {r[10]} |")
P("\nSelected colours, share of all parts (%):\n")
sel = [0, 15, 4, 1, 14, 7, 8, 71, 72, 19, 28, 70, 272, 320, 288, 191, 484, 322]
P("| year | " + " | ".join(cname(c) for c in sel) + " |")
P("|---" * (len(sel) + 1) + "|")
for r in rows:
    if r[0] in SHOWY:
        P(f"| {r[0]} | " + " | ".join(str(r[11 + NAMED.index(c)]) for c in sel) + " |")

P("\n### Colour in the sets of question 2\n")
P("| group | period | sets | classic % | R+B+Y % | new greys % | later % | colours 5%+ (median) | R+B+Y (median set) % | designs (median) | colours used (median) |")
P("|---" * 11 + "|")
q4b = []
for sub in ("aircraft", "car", "vehicle", "creature"):
    for lab, a, b in PERIODS:
        fs = [f for f in F.values() if (f["subset"] == sub or sub == "vehicle" and f["subset"] in ("aircraft", "car"))
              and in_period(f, a, b)]
        if not fs:
            continue
        row = [sub, lab, len(fs), pct(agg(fs, "c_classic")), pct(agg(fs, "primaries")), pct(agg(fs, "c_new_grey")),
               pct(agg(fs, "c_later")), med([f["n_colours5"] for f in fs]), pct(med([f["primaries"] for f in fs])),
               med([f["n_designs"] for f in fs]), med([f["n_colours"] for f in fs])]
        q4b.append(row)
        P("| " + " | ".join(map(str, row)) + " |")
write_csv("q4_colour_by_subset_period", ["subset", "period", "sets", "classic", "primaries", "new_grey", "later",
          "med_n_colours5", "med_primaries", "med_designs", "med_colours"], q4b)

P("\n### Commonest colour schemes (largest two / three colours, ignoring black, greys, transparent and metallic silver)\n")
srows = []
for lab, a, b in (PERIODS[0], ("2000-2009", 2000, 2009), NEWP):
    fs = [f for f in F.values() if f["subset"] in ("aircraft", "car") and in_period(f, a, b)]
    for kind in ("scheme2", "scheme3"):
        c = collections.Counter(f[kind] for f in fs if f[kind])
        tot = sum(c.values())
        top = c.most_common(8)
        P(f"\n**Aircraft and cars {lab}, {kind[-1]} colours** ({tot} sets): " + "; ".join(
            f"{' + '.join(cname(x) for x in k)} {v} ({100 * v / tot:.0f}%)" for k, v in top))
        for k, v in c.most_common(20):
            srows.append([lab, kind, " + ".join(cname(x) for x in k), v, f"{100 * v / tot:.1f}"])
    c = collections.Counter(f["main_colour"] for f in fs if f["main_colour"] is not None)
    tot = sum(c.values())
    P(f"\n**Aircraft and cars {lab}, main colour**: " + "; ".join(f"{cname(k)} {100 * v / tot:.0f}%" for k, v in c.most_common(8)))
write_csv("q4_schemes", ["period", "kind", "scheme", "sets", "pct"], srows)

# ------------------------------------------------------------ Q5
P("\n## Q5. Our builds and the 18 official models, scored the same way\n")
cols5 = ["n", "g_brick", "g_plate", "g_tile", "g_slope", "smooth", "g_curved", "g_wedge", "g_sideways", "g_jumper",
         "g_clipbar", "g_hinge", "g_technic", "age_median", "age_ge2000", "age_ge2010", "age_ge2015", "c_classic",
         "primaries", "c_new_grey", "c_later", "n_colours5"]
hdr = ["model", "year"] + cols5 + ["unmapped", "dropped"]
rows = []
for f in sorted(MF.values(), key=lambda f: (f["label"].startswith("omr"), f["label"])):
    r = [f["label"] if not f["label"].startswith("omr") else f"{f['label']} {f['name']}", f.get("year") or ""]
    for k in cols5:
        v = f[k]
        r.append(v if k in ("n", "age_median", "n_colours5") else pct(v))
    r += [f["unmapped"], f["dropped"]]
    rows.append(r)
write_csv("q5_our_models", hdr, rows)
short = ["n", "g_brick", "g_plate", "g_tile", "smooth", "g_sideways", "g_jumper", "g_clipbar", "age_median",
         "age_ge2010", "c_classic", "primaries", "c_later", "n_colours5"]
P("| model | " + " | ".join(short) + " |")
P("|---" * (len(short) + 1) + "|")
for r in rows:
    P(f"| {r[0]} | " + " | ".join(str(r[2 + cols5.index(k)]) for k in short) + " |")


def summary(fs, lab):
    return [lab, len(fs)] + [pct(med([f[k] for f in fs])) if k not in ("n", "age_median", "n_colours5")
                             else med([f[k] for f in fs]) for k in short]


P("\n### Medians by group\n")
P("| group | models | " + " | ".join(short) + " |")
P("|---" * (len(short) + 2) + "|")
groups5 = [(AI, f"our AI builds ({len(AI)})"), (OMR, "the 18 official models")]
for sub in ("aircraft", "car", "vehicle", "creature"):
    for lab, a, b in PERIODS:
        fs = [f for f in F.values() if (f["subset"] == sub or sub == "vehicle" and f["subset"] in ("aircraft", "car"))
              and in_period(f, a, b)]
        if fs:
            groups5.append((fs, f"official {sub} {lab}"))
for fs, lab in groups5:
    P("| " + " | ".join(map(str, summary(fs, lab))) + " |")

# Cessna against official aircraft of similar size, by decade
ces = MF["free:cessna-172-skyhawk"]
DEC = [("1990s", 1990, 1999), ("2000s", 2000, 2009), ("2010s", 2010, 2019), ("2020s", 2020, LAST)]
metrics = ["g_brick", "g_plate", "g_tile", "smooth", "g_slope", "g_curved", "g_wedge", "g_sideways", "g_jumper",
           "age_median", "age_ge2005", "age_ge2010", "c_classic", "primaries", "c_later", "n_colours5"]
P(f"\n### cessna-172-skyhawk ({ces['n']} parts) against official aircraft of 90 to 600 parts, by decade (medians)\n")
P("| measure | Cessna | " + " | ".join(f"{x[0]} ({len([f for f in F.values() if f['subset'] == 'aircraft' and in_period(f, x[1], x[2])])})" for x in DEC) + " | nearest decade | Cessna's distance from 2020s in 1990s-to-2020s gaps |")
P("|---" * (len(DEC) + 4) + "|")
crow = []
for k in metrics:
    meds = []
    for lab, a, b in DEC:
        fs = [f for f in F.values() if f["subset"] == "aircraft" and in_period(f, a, b)]
        meds.append(med([f[k] for f in fs]))
    near = DEC[min(range(len(DEC)), key=lambda i: abs(meds[i] - ces[k]))][0]
    span = (meds[3] - meds[0]) or 1e-9
    pos = (ces[k] - meds[0]) / span  # 0 = like the 1990s, 1 = like the 2020s
    fmt = (lambda v: f"{v:.0f}" if k in ("age_median", "n_colours5") else pct(v))
    P(f"| {k} | {fmt(ces[k])} | " + " | ".join(fmt(v) for v in meds) + f" | {near} | {pos:.2f} |")
    crow.append([k, ces[k]] + meds + [near, pos])
write_csv("q5_cessna_by_decade", ["measure", "cessna", "1990s", "2000s", "2010s", "2020s", "nearest", "position_0old_1new"], crow)

pickle.dump(dict(F=F, MF=MF), open(OUT + "/feat.pkl", "wb"))
md.close()
print(open(OUT + "/tables.md").read())
