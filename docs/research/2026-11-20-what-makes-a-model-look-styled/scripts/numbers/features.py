"""Per-set and per-model features for the style-numbers study (imported by analyse.py and score.py).

features(tally, d, pg) takes a tally {(rebrickable part, rebrickable colour): qty} and returns a dict:
n (building parts counted), groups (share by group), age numbers, colour numbers.
"""
import collections

from common import GROUP_KEYS, PRIMARIES, SMOOTH, colour_class, scheme_colour_ok, wmedian


def features(tally, d, pg):
    fy = d["first_year"]
    colors = d["colors"]
    g = collections.Counter()
    ages = []
    cols = collections.Counter()
    n = 0
    no_year = 0
    for (p, c), q in tally.items():
        grp = pg.get(p, "other") if not str(p).startswith("LD:") else "other"
        if grp is None:
            continue
        n += q
        g[grp] += q
        y = fy.get(p)
        if y is None:
            no_year += q
        else:
            ages.append((y, q))
        cols[c] += q
    if n == 0:
        return None
    f = {"n": n, "no_year": no_year}
    for k in GROUP_KEYS:
        f["g_" + k] = g[k] / n
    f["smooth"] = sum(g[k] for k in SMOOTH) / n
    na = sum(q for _y, q in ages) or 1
    f["age_median"] = wmedian(ages)
    f["age_mean"] = sum(y * q for y, q in ages) / na
    for cut in (2000, 2005, 2010, 2015):
        f[f"age_ge{cut}"] = sum(q for y, q in ages if y >= cut) / na
    cls = collections.Counter()
    for c, q in cols.items():
        cls[colour_class(c, colors)] += q
    for k in ("classic", "new_grey", "trans", "metal", "later", "old_other", "unknown"):
        f["c_" + k] = cls[k] / n
    f["primaries"] = sum(q for c, q in cols.items() if c in PRIMARIES) / n
    f["n_colours5"] = sum(1 for c, q in cols.items() if q / n >= 0.05)
    f["n_colours"] = len(cols)
    f["n_designs"] = len({p for (p, c) in tally if pg.get(p, "other") is not None})
    sch = sorted(((q, c) for c, q in cols.items() if scheme_colour_ok(c, colors)), reverse=True)
    f["scheme2"] = tuple(sorted(c for _q, c in sch[:2])) if len(sch) >= 2 else None
    f["scheme3"] = tuple(sorted(c for _q, c in sch[:3])) if len(sch) >= 3 else None
    f["main_colour"] = sch[0][1] if sch else None
    f["colours"] = dict(cols)
    return f


def set_tally(s, d):
    return d["tally"].get(s, {})


def model_tally(entry):
    return {(p, int(c)): q for p, c, q in entry["tally"]}
