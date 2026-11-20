"""Experiment 2: measure a model against the guide's rules, the same way for every model.

usage: uv run python -I exp_measures.py OUT.json MODEL1.ldr [MODEL2.ldr ...]

Each MODEL is one flat LDraw file (an AI build, or an official set flattened by
exp_flatten.py); part lines in file order are the build order. It prints one line per model
and writes every number to OUT.json. All measures are rough in the ways said below.

Which parts count
- A "stud part" is one whose library geometry has studs or a socket underneath
  (``Part.studs`` or ``Part.has_sockets()``): bricks, plates, tiles, slopes, brackets...
  Wheels, tyres, bars, pins, axles, clips without studs, minifigure accessories are not.

1. Facing. A stud part's facing is its own up (-y of its matrix) in the world: "up" (within
   about 25 degrees of world up), "down", "sideways" (within 25 degrees of level), or
   "angled". Shares are of all stud parts; then of the stud parts in the first and in the
   last third of the part lines. (The study's numbers used the same up vector, by step
   rather than by line, and Rebrickable's categories rather than the geometry.)
2. Variety: kinds of part (file names), colours, both also per 100 parts.
3. Size: a stud part's footprint is its body's extent in its own x and z, in whole studs
   (rounded); "small" means 1 x 1 or 1 x 2. Mean footprint in studs (x * z) and mean count of
   studs it carries (any direction).
4. Uncovered seams. Two upright stud parts (facing up, turned a whole quarter) form a seam
   when their bottoms are at the same height (within 1 LDU), their bodies touch side to side
   (gap at most 1 LDU) along at least 10 LDU, and they do not overlap. The seam is covered
   when some third part is joined by studs (the checker's own links) to both of them, from
   above or from below. Counted: seams, uncovered seams, and uncovered seams per 100 parts.
5. Hanging sections. The model as a graph: parts joined by the checker's stud links, by the
   joints it lists as "not checked", and (so that official sets are not split by the
   checker's false alarms) by any pair it names in a stud or overlap problem. Parts with no
   path to a part on the ground are left out and counted. A part whose removal splits the
   rest into pieces holds a hanging section: what would come away is every piece but the
   largest. Reported: how many parts hold one, the largest section (parts), and how many
   sections are of 5 parts or more. A section of one part (a single detail on a single
   part) counts; a part held by one stud of a part that is itself well held does not make
   that holder a cut unless the detail has no other joint.
6. Core first. For the first quarter of the part lines: what it is made of (by the first
   word of the part's description), the median height percentile of its parts (0 = the
   lowest part of the model, 100 = the highest) and their median percentile of horizontal
   distance from the model's centre (0 = the innermost). Also Spearman's rho between line
   order and height, and line order and distance (as the study's numbers report did).
7. Mirrors. Of all parts, the share that has a twin of the same kind and colour at the
   mirror position (within 2 LDU) across the best plane x = c or z = c (the plane that gives
   the most twins), the part on the plane itself counting as its own twin. A left part and
   its right counterpart (different file names) are not counted, so this is a lower bound.
"""

from __future__ import annotations

import collections
import json
import math
import os
import re
import sys

import numpy as np

from bricksnap.lab.validate import check

UP = np.array([0.0, -1.0, 0.0])
COS25 = math.cos(math.radians(25))
SIN25 = math.sin(math.radians(25))


def facing(m: np.ndarray) -> str:
    u = m @ UP
    d = float(u @ UP)
    if d > COS25:
        return "up"
    if d < -COS25:
        return "down"
    if abs(d) < SIN25:
        return "sideways"
    return "angled"


def quarter_turn(m: np.ndarray) -> bool:
    return bool(np.all(np.isclose(np.abs(m), np.round(np.abs(m)), atol=0.02)))


def world_box(p) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = p.part.bbox_min, p.part.bbox_max
    c = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    w = p.to_world(c)
    return w.min(0), w.max(0)


def spearman(x: list[float], y: list[float]) -> float:
    n = len(x)
    if n < 5:
        return float("nan")

    def rank(v):
        o = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r

    rx, ry = rank(x), rank(y)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def percentile_ranks(v: list[float]) -> list[float]:
    """0 for the smallest value, 100 for the largest; ties share their average rank."""
    n = len(v)
    o = sorted(range(n), key=lambda i: v[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(v[o[j + 1]] - v[o[i]]) < 0.5:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = 100.0 * ((i + j) / 2) / max(1, n - 1)
        i = j + 1
    return r


def word(desc: str) -> str:
    d = desc.lstrip("~=_").lower()
    if re.search(r"studs? on (\w+ )?sides?|side studs?|\bbracket\b|with stud on|headlight", d):
        return "side-stud brick or bracket"
    w = d.split()[0] if d else "?"
    return {"technic": "technic", "minifig": "minifig/accessory", "plant": "plant",
            "bar": "bar/clip", "tile": "tile", "plate": "plate", "brick": "brick", "slope": "slope",
            "wedge": "wedge", "wheel": "wheel/tyre", "tyre": "wheel/tyre", "hinge": "hinge",
            "cone": "round", "dish": "round", "cylinder": "round", "panel": "panel/window",
            "windscreen": "panel/window", "window": "panel/window", "door": "panel/window"}.get(w, "other")


def hanging_sections(adj: dict[int, set[int]], nodes: set[int]) -> dict[int, int]:
    """For each part whose removal splits the parts graph (restricted to ``nodes``): how many
    parts would come away, i.e. all the pieces it leaves except the largest one (iterative
    DFS, Tarjan's articulation points, with subtree sizes)."""
    out: dict[int, int] = {}
    left = set(nodes)
    while left:
        root = min(left)
        disc = {root: 0}
        low = {root: 0}
        size = {root: 1}
        pieces: dict[int, list[int]] = collections.defaultdict(list)
        t = 0
        stack = [(root, -1, iter(sorted(adj[root] & nodes)))]
        while stack:
            v, parent, it = stack[-1]
            advanced = False
            for w in it:
                if w == parent:
                    continue
                if w not in disc:
                    t += 1
                    disc[w] = low[w] = t
                    size[w] = 1
                    stack.append((w, v, iter(sorted(adj[w] & nodes))))
                    advanced = True
                    break
                low[v] = min(low[v], disc[w])
            if advanced:
                continue
            stack.pop()
            if stack:
                u = stack[-1][0]
                low[u] = min(low[u], low[v])
                size[u] += size[v]
                if low[v] >= disc[u]:
                    pieces[u].append(size[v])
        comp = size[root]
        for u, ps in pieces.items():
            if u == root and len(ps) < 2:
                continue
            rest = comp - 1 - sum(ps)
            allp = sorted(ps + ([rest] if rest > 0 else []), reverse=True)
            if len(allp) >= 2:
                out[u] = sum(allp[1:])
        left -= set(disc)
    return out


def mirror_share(placed) -> tuple[float, str]:
    best = (0, "")
    pts = [(p.key, p.colour, p.pos) for p in placed]
    for axis in (0, 2):
        # candidate planes: midpoints of same-kind pairs, weighted by votes
        votes: collections.Counter = collections.Counter()
        by = collections.defaultdict(list)
        for k, c, pos in pts:
            by[(k, c)].append(pos)
        for group in by.values():
            for i in range(len(group)):
                for j in range(i, len(group)):
                    a, b = group[i], group[j]
                    other = [q for q in range(3) if q != axis]
                    if all(abs(a[q] - b[q]) <= 2 for q in other):
                        votes[round((a[axis] + b[axis]) / 2)] += 1
        for c, _ in votes.most_common(3):
            twins = 0
            for k, col, pos in pts:
                mpos = pos.copy()
                mpos[axis] = 2 * c - pos[axis]
                if any(np.all(np.abs(q - mpos) <= 2) for q in by[(k, col)]):
                    twins += 1
            if twins > best[0]:
                best = (twins, f"{'xz'[axis // 2]} = {c}")
    return best[0] / max(1, len(placed)), best[1]


def measure(path: str) -> dict:
    text = open(path).read()
    r = check(text)
    placed = r.placed
    n = len(placed)
    by_line = {p.line: p for p in placed}
    stud_parts = [p for p in placed if p.part.studs or p.part.has_sockets()]
    out: dict = dict(name="/".join(path.split("/")[-2:]).rsplit(".", 1)[0], parts=n, stud_parts=len(stud_parts),
                     summary=r.summary())
    # 1 facing
    face = {p.line: facing(p.m) for p in stud_parts}
    order = [p.line for p in placed]
    third = max(1, n // 3)
    first = set(order[:third])
    last = set(order[-third:])

    def shares(sel):
        c = collections.Counter(face[p.line] for p in stud_parts if p.line in sel)
        tot = sum(c.values()) or 1
        return {k: round(c[k] / tot, 3) for k in ("up", "sideways", "down", "angled")} | {"n": sum(c.values())}

    out["facing"] = shares(set(order))
    out["facing_first_third"] = shares(first)
    out["facing_last_third"] = shares(last)
    # 2 variety
    kinds = len({p.key for p in placed})
    colours = len({p.colour for p in placed})
    out["kinds"] = kinds
    out["colours"] = colours
    # 3 size
    foot = []
    small = 0
    studs = []
    for p in stud_parts:
        span = p.part.bbox_max - p.part.bbox_min
        fx, fz = max(1, round(span[0] / 20)), max(1, round(span[2] / 20))
        foot.append(fx * fz)
        if sorted((fx, fz)) in ([1, 1], [1, 2]):
            small += 1
        studs.append(len(p.part.studs))
    out["small_share"] = round(small / max(1, len(stud_parts)), 3)
    out["mean_footprint"] = round(float(np.mean(foot)), 2) if foot else None
    out["mean_studs"] = round(float(np.mean(studs)), 2) if studs else None
    # links
    linked: dict[int, set[int]] = collections.defaultdict(set)
    for k in r.links:
        linked[k.holder].add(k.held)
        linked[k.held].add(k.holder)
    # 4 seams
    upright = [p for p in stud_parts if face[p.line] == "up" and quarter_turn(p.m) and p.part.has_body()]
    boxes = {p.line: world_box(p) for p in upright}
    seams = uncovered = 0
    for i, a in enumerate(upright):
        alo, ahi = boxes[a.line]
        for b in upright[i + 1:]:
            blo, bhi = boxes[b.line]
            if abs(ahi[1] - bhi[1]) > 1:  # bottoms (largest y) at the same height
                continue
            # touching side to side: gap <= 1 on one horizontal axis, overlap >= 10 on the other
            ok = False
            for ax, other in ((0, 2), (2, 0)):
                gap = max(alo[ax] - bhi[ax], blo[ax] - ahi[ax])
                share = min(ahi[other], bhi[other]) - max(alo[other], blo[other])
                if -1 <= gap <= 1 and share >= 10:
                    ok = True
            if not ok:
                continue
            seams += 1
            if not (linked[a.line] & linked[b.line]):
                uncovered += 1
    out["seams"] = seams
    out["uncovered_seams"] = uncovered
    out["uncovered_share"] = round(uncovered / seams, 3) if seams else None
    out["uncovered_per_100_parts"] = round(100 * uncovered / max(1, n), 1)
    # 5 hanging sections
    adj: dict[int, set[int]] = collections.defaultdict(set)
    for p in placed:
        adj[p.line]
    for a, bs in linked.items():
        for b in bs:
            adj[a].add(b)
    for i in r.issues:
        if (i.severity == "not checked" and i.kind == "joint") or (
            i.severity == "problem" and i.kind in ("stud", "overlap")
        ):
            if len(i.lines) == 2:
                a, b = i.lines
                adj[a].add(b)
                adj[b].add(a)
    GROUND = 0
    adj[GROUND] = set(r.grounded)
    for g in r.grounded:
        adj[g].add(GROUND)
    seen = {GROUND}
    todo = [GROUND]
    while todo:
        v = todo.pop()
        for w in adj[v]:
            if w not in seen:
                seen.add(w)
                todo.append(w)
    out["not_joined_to_ground"] = n - (len(seen) - 1)
    joined = seen - {GROUND}
    part_adj = {v: adj[v] - {GROUND} for v in joined}
    cut = hanging_sections(part_adj, joined)
    sections = sorted(cut.values(), reverse=True)
    out["hanging_holders"] = len(sections)
    out["largest_hanging"] = sections[0] if sections else 0
    out["largest_hanging_share"] = round(sections[0] / max(1, n), 3) if sections else 0.0
    out["hanging_5plus"] = sum(1 for s in sections if s >= 5)
    # 6 core first
    ys = [-float(world_box(p)[1][1]) for p in placed]  # height of the bottom (up = -y)
    centre = np.mean([p.pos for p in placed], axis=0)
    hd = [float(math.hypot(p.pos[0] - centre[0], p.pos[2] - centre[2])) for p in placed]
    hp = percentile_ranks(ys)
    dp = percentile_ranks(hd)
    q = max(1, n // 4)
    out["first_quarter_height_pct"] = round(float(np.median(hp[:q])), 0)
    out["first_quarter_distance_pct"] = round(float(np.median(dp[:q])), 0)
    out["rho_height"] = round(spearman(list(range(n)), ys), 2)
    out["rho_distance"] = round(spearman(list(range(n)), hd), 2)
    comp = collections.Counter(word(p.part.description) for p in placed[:q])
    out["first_quarter"] = {k: round(v / q, 2) for k, v in comp.most_common()}
    comp_all = collections.Counter(word(p.part.description) for p in placed)
    out["all"] = {k: round(v / n, 2) for k, v in comp_all.most_common()}
    # 7 mirrors
    share, plane = mirror_share(placed)
    out["mirror_share"] = round(share, 3)
    out["mirror_plane"] = plane
    return out


def main(argv: list[str]) -> None:
    rows = []
    for path in argv[1:]:
        try:
            m = measure(path)
        except Exception as e:  # record and go on
            m = dict(name=os.path.basename(path), crash=f"{type(e).__name__}: {e}")
            print(m)
            rows.append(m)
            continue
        rows.append(m)
        f = m["facing"]
        print(f"{m['name']}: {m['parts']} parts, {m['kinds']} kinds, {m['colours']} colours; side {f['sideways']:.0%} "
              f"down {f['down']:.0%} (side first/last third {m['facing_first_third']['sideways']:.0%}/"
              f"{m['facing_last_third']['sideways']:.0%}); small {m['small_share']:.0%}, footprint {m['mean_footprint']}; "
              f"seams {m['uncovered_seams']}/{m['seams']} uncovered; hanging holders {m['hanging_holders']}, largest "
              f"{m['largest_hanging']}, 5+ {m['hanging_5plus']}; first quarter h {m['first_quarter_height_pct']} "
              f"d {m['first_quarter_distance_pct']}; mirror {m['mirror_share']:.0%} ({m['mirror_plane']})")
    json.dump(rows, open(argv[0], "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
