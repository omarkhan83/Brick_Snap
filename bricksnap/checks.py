"""Build to Report: does it hold together, and if not, why not, in plain words.

CONTRACT (tests go in tests/test_checks.py)

``check(build, catalog) -> Report`` fills every field of ``bricksnap.types.Report``.
Use ``bricksnap.connect.occupancy`` and ``connection_graph``; do not redefine "connected".

- ``collisions``, ``out_of_bounds``, ``unknown_parts``: straight from ``occupancy``.
- ``components``: number of connected pieces in the connection graph.
- The main piece is the piece with the most cells among those that touch the ground
  (have a part at z = 0); if none touches the ground, simply the piece with the most cells.
  ``loose`` is every part not in the main piece, sorted. ``grounded`` says whether the main
  piece touches the ground.
- ``centre_of_mass``: of the main piece, weighted by cells covered, in cell units, measured
  to cell centres (a part covering only cell (0, 0, 0) has its centre at (0.5, 0.5, 0.5)).
- ``stands``: the centre of mass, dropped straight down, lies inside or on the convex hull
  of the main piece's ground contact (the corners of its cells at z = 0). False when it is
  not grounded.
- ``weak_spots``: at most ten sentences, the most serious first, each naming a place as
  "x=…, y=…, z=…" (x and y in studs, z in plates) and what is at stake, for example
  "37 parts above x=4, y=2, z=12 hang on a single stud." Find them from the graph: a part
  whose removal would detach others (an articulation point), and a connection that is the
  only link to a group and engages just one stud. Ignore anything with fewer than 3 parts
  at stake.
- ``ok`` is True only when there are parts, no collisions, nothing out of bounds, no
  unknown parts, exactly one piece, grounded, and it stands. Weak spots do not make a
  build fail.
- ``text``: a few lines a person or an AI model can act on. Start with the verdict
  ("OK: 143 parts in one connected piece; it stands." or "NOT BUILDABLE: …"), then each
  problem with counts and up to five example parts by name and position, then weak spots.
  An empty build says "The build has no parts."
- Speed: a 5,000-part build in under 2 seconds.

Implementation notes
--------------------
- Ties for the main piece (same number of cells) go to the piece holding the lowest part
  index, so the result is deterministic.
- A part whose id is not in the catalogue covers no known cells: it weighs nothing in the
  centre of mass and gives no ground contact, even at z = 0 (it is still a node, so it is
  always loose unless it is alone).
- A known part turned by an angle that is not a quarter turn (``rot`` not a multiple of 90)
  cannot be placed, and ``connect`` would raise on it. ``check`` hands ``connect`` a copy of
  the build in which such parts carry an id that is not in the catalogue, so they are
  treated exactly like unknown parts: listed in ``unknown_parts`` (so ``ok`` is False),
  covering nothing, connected to nothing. The text names them as badly turned parts.
- Weak spots are measured against the ground. The main piece is given a virtual "ground"
  node joined to every part at z = 0 (or, if the piece floats, to its lowest parts), and
  one depth-first search from that node finds, in linear time, every part and every
  connection whose loss would cut a group of parts off from the ground, and the size of
  that group. Parts that rest on the ground themselves are not reported as weak spots
  (they are held by the table, not by other parts). When a part and a single-stud joint
  would cut off exactly the same group, only the single-stud sentence is kept.
- That search cannot see a group that rests on the ground itself but is joined to the rest
  of the model by one single-stud joint or one part (a leg, a tower, one side of an arch):
  the model stands, but comes apart there when it is lifted. A second depth-first search,
  over the plain connection graph of the main piece (no ground node), finds those: every
  single-stud joint with parts on the ground on both sides, where the smaller side comes
  away; and every part not on the ground whose removal leaves two or more pieces on the
  ground, where all but the biggest of those come away. On a tie, the side holding the
  lowest part index stays. Groups the first search already covers (with nothing on the
  ground) are left to it, so nothing is reported twice. The 3-part threshold, merging and
  runs apply to these too; their sentences say the group comes away when the model is lifted.
- Ranking: single-stud joints come first (they are the fragile ones), then parts that are
  the only link for a group; within each kind, more parts at stake first, then lowest
  position. A run of parts each carrying everything beyond it alone (each one's group is
  the previous one's minus that part, as in a plain column of bricks) is one weak spot,
  named by its first part, with the run's length and last part in the sentence.
- When there are more than ten weak spots, ``text`` says how many were left out.
- The tip-over sentence describes the standing area by its span when that area is a
  rectangle, and otherwise by the corners of its outline; either way it gives the point
  of the outline nearest the centre of mass, so it is clear which way to widen the base.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import networkx as nx
import numpy as np
from scipy.spatial import ConvexHull, QhullError

from bricksnap.catalog import Catalog
from bricksnap.connect import connection_graph, occupancy
from bricksnap.types import Build, Placement, Report

MAX_WEAK_SPOTS = 10
MAX_EXAMPLES = 5
MIN_AT_STAKE = 3
MAX_CORNERS = 8
_EPS = 1e-9
_UNPLACEABLE = "\x00turned by an impossible angle"  # never a catalogue id


# ---- small text helpers ----------------------------------------------------------------------


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _span(lo: int, hi: int) -> str:
    return f"{lo}" if lo == hi else f"{lo} to {hi}"


def _pos(p: Placement) -> str:
    return f"x={p.x}, y={p.y}, z={p.z}"


def _num(v: float) -> str:
    return f"{v:.2f}"


def _coord(v: float) -> str:
    """A corner coordinate: whole numbers without decimals, others to two places."""
    r = round(v)
    return f"{r}" if abs(v - r) < 1e-6 else f"{v:.2f}"


class _Namer:
    """Turns part indices into plain descriptions such as 'Red Brick 2 x 2 (3003) at x=…'."""

    def __init__(self, build: Build, catalog: Catalog) -> None:
        self.build = build
        self.catalog = catalog

    def what(self, i: int) -> str:
        p = self.build.parts[i]
        part = self.catalog.parts.get(p.part)
        colour = self.catalog.colours.get(p.color)
        if part is None:
            colour_text = colour.name if colour else f"colour {p.color}"
            return f'unknown part "{p.part}" in {colour_text}'
        if colour is None:
            return f"{part.name} ({part.id}) in unknown colour {p.color}"
        return f"{colour.name} {part.name} ({part.id})"

    def at(self, i: int) -> str:
        return f"{self.what(i)} at {_pos(self.build.parts[i])}"

    def examples(self, indices: list[int]) -> str:
        shown = [self.at(i) for i in indices[:MAX_EXAMPLES]]
        text = "; ".join(shown)
        extra = len(indices) - len(shown)
        if extra > 0:
            text += f"; and {extra} more"
        return text


# ---- geometry --------------------------------------------------------------------------------


def _nearest_on_segment(q: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ab = b - a
    denom = float(ab @ ab)
    t = 0.0 if denom == 0.0 else float(np.clip((q - a) @ ab / denom, 0.0, 1.0))
    return a + t * ab


@dataclass
class _Footprint:
    distance: float  # from the point to the hull; 0 when inside or on it
    nearest: np.ndarray  # the point of the hull nearest to it (the point itself when inside)
    corners: np.ndarray  # the hull's corners, counter-clockwise (one or two when degenerate)


def _footprint(points: np.ndarray, q: np.ndarray) -> _Footprint:
    """Where 2-D point ``q`` lies against the convex hull of ``points``.

    Handles degenerate hulls: a single point, or points all on one line.
    """
    pts = np.unique(np.asarray(points, dtype=float).reshape(-1, 2), axis=0)
    q = np.asarray(q, dtype=float)
    if len(pts) == 0:
        return _Footprint(float("inf"), q, pts)
    if len(pts) == 1:
        return _Footprint(float(np.linalg.norm(q - pts[0])), pts[0], pts)
    try:
        hull = ConvexHull(pts)
    except QhullError:
        hull = None
    if hull is None:
        # all on one line: the hull is the segment between the two extreme points
        direction = pts[-1] - pts[0]
        t = (pts - pts[0]) @ direction
        a, b = pts[int(np.argmin(t))], pts[int(np.argmax(t))]
        near = _nearest_on_segment(q, a, b)
        return _Footprint(float(np.linalg.norm(q - near)), near, np.stack([a, b]))
    verts = pts[hull.vertices]
    if np.all(hull.equations[:, :2] @ q + hull.equations[:, 2] <= _EPS):
        return _Footprint(0.0, q, verts)
    candidates = [
        _nearest_on_segment(q, verts[k], verts[(k + 1) % len(verts)]) for k in range(len(verts))
    ]
    near = min(candidates, key=lambda c: float(np.linalg.norm(q - c)))
    return _Footprint(float(np.linalg.norm(q - near)), near, verts)


def _footprint_distance(points: np.ndarray, q: np.ndarray) -> float:
    """Distance from 2-D point ``q`` to the convex hull of ``points``; 0 when inside or on it."""
    return _footprint(points, q).distance


# ---- weak spots ------------------------------------------------------------------------------


@dataclass
class _Spot:
    at_stake: int
    kind: int  # 0 single stud (more serious at equal size), 1 single part
    key: tuple[tuple[int, int], ...]  # the cut-off group, as merged ranges of ``order``
    sort_pos: tuple[int, int, int]
    order: list[int]  # the preorder of the search that found it, which ``key`` indexes
    # True when the group rests on the base itself, so it only comes away when the model is
    # lifted (found by the second search, over the plain connection graph)
    lifted: bool = False
    # what the sentence needs; built only for the spots that are reported
    lower: int = -1  # single stud: the part with the stud
    upper: int = -1  # single stud: the part pressed onto it
    detached_upper: bool = True  # single stud: the cut-off group is the upper side
    part: int = -1  # single part: the part they all depend on
    part_pos: int = -1  # single part: its place in ``order``
    run: int = 1  # single part: how many parts in a row each carry everything beyond them
    run_end: int = -1  # single part: the last part of that run

    def members(self) -> list[int]:
        """The parts of the cut-off group."""
        return [self.order[k] for a, b in self.key for k in range(a, b)]


def _merge_ranges(ranges: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for a, b in sorted(ranges):
        if a == b:
            continue
        if merged and merged[-1][1] == a:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return tuple(merged)


@dataclass
class _Search:
    order: list[int]  # nodes in preorder; a subtree is a contiguous range of it
    disc: dict[int, int]  # place in ``order``
    low: dict[int, int]  # lowest place reachable from the subtree by one back edge
    parent: dict[int, int]
    size: dict[int, int]  # nodes in the subtree


def _search(adj: dict[int, list[int]], root: int) -> _Search:
    """Iterative depth-first search (Tarjan) from ``root``: preorder, low links, sizes."""
    disc: dict[int, int] = {root: 0}
    low: dict[int, int] = {root: 0}
    parent: dict[int, int] = {}
    size: dict[int, int] = {}
    order: list[int] = [root]
    stack = [(root, iter(adj[root]))]
    while stack:
        v, it = stack[-1]
        advanced = False
        for w in it:
            if w not in disc:
                parent[w] = v
                disc[w] = low[w] = len(order)
                order.append(w)
                stack.append((w, iter(adj[w])))
                advanced = True
                break
            if w != parent.get(v):
                low[v] = min(low[v], disc[w])
        if advanced:
            continue
        stack.pop()
        size[v] = len(order) - disc[v]
        p = parent.get(v)
        if p is not None:
            low[p] = min(low[p], low[v])
    return _Search(order, disc, low, parent, size)


def _find_spots(
    build: Build,
    catalog: Catalog,
    occ: np.ndarray,
    graph: nx.Graph,
    main: list[int],
    anchors: set[int],
) -> list[_Spot]:
    """Every part and every single-stud joint of the main piece whose loss cuts 3 or more
    parts off, before merging, ranking and wording. ``main`` is sorted; ``anchors`` are its
    parts that rest on the base (the ground, or the lowest layer of a floating piece)."""
    parts = build.parts
    spots: list[_Spot] = []
    if len(main) < MIN_AT_STAKE + 1 or not anchors:
        return spots

    def joint(
        p: int, v: int, at: int, key: tuple[tuple[int, int], ...], order: list[int], lifted: bool
    ) -> _Spot:
        lower, upper = (p, v) if parts[p].z < parts[v].z else (v, p)
        top = parts[upper].z
        stud = next(
            (
                (x, y)
                for x, y in catalog.stud_cells(parts[lower])
                if 0 <= x < occ.shape[0] and 0 <= y < occ.shape[1] and occ[x, y, top] == upper
            ),
            (parts[upper].x, parts[upper].y),
        )
        return _Spot(at, 0, key, (top, stud[0], stud[1]), order, lifted, lower, upper, v == upper)

    def single_stud(p: int, v: int) -> bool:
        return graph.edges[p, v].get("studs", 0) == 1

    # First search: against the base. A virtual root is joined to every anchor; a part or
    # joint whose loss cuts a group off from that root leaves the group with no support.
    plain: dict[int, list[int]] = {i: list(graph.adj[i]) for i in main}
    root = -1
    adj = {i: list(nbrs) for i, nbrs in plain.items()}
    adj[root] = sorted(anchors)
    for i in anchors:
        adj[i].append(root)
    s = _search(adj, root)
    cut_children: dict[int, list[int]] = {}
    for v, p in s.parent.items():
        if p == root:
            continue
        a, b = s.disc[v], s.disc[v] + s.size[v]
        if s.low[v] >= s.disc[p]:
            cut_children.setdefault(p, []).append(v)
        if s.low[v] > s.disc[p] and single_stud(p, v) and b - a >= MIN_AT_STAKE:
            spots.append(joint(p, v, b - a, ((a, b),), s.order, lifted=False))
    for c_part, children in cut_children.items():
        if c_part in anchors:
            continue  # rests on the base itself
        key = _merge_ranges([(s.disc[c], s.disc[c] + s.size[c]) for c in children])
        n = sum(b - a for a, b in key)
        if n >= MIN_AT_STAKE:
            pc = parts[c_part]
            spots.append(
                _Spot(n, 1, key, (pc.z, pc.x, pc.y), s.order, part=c_part, part_pos=s.disc[c_part])
            )

    # Second search: the plain connection graph, no root. It finds what the first cannot
    # see: groups that rest on the base themselves but are joined to the rest of the model
    # by one single-stud joint or one part, so they come away when the model is lifted.
    total = len(anchors)
    if total < 2:
        return spots
    n_main = len(main)
    ps = _search(plain, main[0])
    flags = np.fromiter((i in anchors for i in ps.order), dtype=np.int64, count=n_main)
    prefix = np.concatenate([[0], np.cumsum(flags)])

    def on_base(a: int, b: int) -> int:
        return int(prefix[b] - prefix[a])

    def lowest_part(ranges: tuple[tuple[int, int], ...]) -> int:
        return min(ps.order[k] for a, b in ranges for k in range(a, b))

    children_of: dict[int, list[int]] = {}
    separated: dict[int, list[int]] = {}
    for v, p in ps.parent.items():
        children_of.setdefault(p, []).append(v)
        a, b = ps.disc[v], ps.disc[v] + ps.size[v]
        if ps.low[v] >= ps.disc[p]:
            separated.setdefault(p, []).append(v)
        if ps.low[v] > ps.disc[p] and single_stud(p, v) and 0 < on_base(a, b) < total:
            # both sides rest on the base (otherwise the first search has it): the smaller
            # side comes away; on a tie, the side holding the lowest part index stays, which
            # is never the subtree (the search starts from the lowest index)
            if b - a <= n_main - (b - a):
                at, key = b - a, ((a, b),)
            else:
                at, key = n_main - (b - a), _merge_ranges([(0, a), (b, n_main)])
            if at >= MIN_AT_STAKE:
                spots.append(joint(p, v, at, key, ps.order, lifted=True))
    for v, seps in separated.items():
        if v in anchors:
            continue
        # the pieces left when v is taken away: (parts, ranges of order, parts on the base)
        comps: list[tuple[int, tuple[tuple[int, int], ...], int]] = []
        for c in seps:
            a, b = ps.disc[c], ps.disc[c] + ps.size[c]
            comps.append((b - a, ((a, b),), on_base(a, b)))
        rest_size = n_main - 1 - sum(c[0] for c in comps)
        if rest_size > 0:
            dv, ev = ps.disc[v], ps.disc[v] + ps.size[v]
            sep_set = set(seps)
            rest = [(0, dv), (ev, n_main)] + [
                (ps.disc[c], ps.disc[c] + ps.size[c])
                for c in children_of.get(v, [])
                if c not in sep_set
            ]
            comps.append((rest_size, _merge_ranges(rest), total - sum(c[2] for c in comps)))
        grounded = [c for c in comps if c[2] > 0]
        if len(grounded) < 2:
            continue  # ungrounded pieces are the first search's
        biggest = max(c[0] for c in grounded)
        tied = [k for k, c in enumerate(grounded) if c[0] == biggest]
        stays = tied[0] if len(tied) == 1 else min(tied, key=lambda k: lowest_part(grounded[k][1]))
        away = [c for k, c in enumerate(grounded) if k != stays]
        at = sum(c[0] for c in away)
        if at < MIN_AT_STAKE:
            continue
        key = _merge_ranges([r for c in away for r in c[1]])
        pv = parts[v]
        spots.append(
            _Spot(at, 1, key, (pv.z, pv.x, pv.y), ps.order, True, part=v, part_pos=ps.disc[v])
        )
    return spots


def _weak_spots(
    build: Build,
    catalog: Catalog,
    occ: np.ndarray,
    graph: nx.Graph,
    main: list[int],
    grounded: bool,
    known: np.ndarray,
    namer: _Namer,
) -> tuple[list[str], int, str]:
    """Weak-spot sentences for the main piece, most serious first, how many there were, and
    the word ("smaller" or "less serious") that describes the ones left out."""
    parts = build.parts
    main_known = [i for i in main if known[i]]
    if not main_known:
        return [], 0, "smaller"
    base_z = 0 if grounded else min(parts[i].z for i in main_known)
    anchors = {i for i in main_known if parts[i].z == base_z}
    spots = _find_spots(build, catalog, occ, graph, main, anchors)

    def group_extent(s: _Spot) -> str:
        members = [i for i in s.members() if known[i]]
        if not members:
            return ""
        lo = np.array([[parts[i].x, parts[i].y, parts[i].z] for i in members])
        hi = lo + np.array([catalog.footprint(parts[i]) for i in members]) - 1
        mn, mx = lo.min(axis=0), hi.max(axis=0)
        return (
            f"the group spans x={_span(int(mn[0]), int(mx[0]))}, "
            f"y={_span(int(mn[1]), int(mx[1]))}, z={_span(int(mn[2]), int(mx[2]))}"
        )

    target = "the ground" if grounded else "the rest of the model"
    lifted_note = (
        " They stand on the ground themselves, so the model holds while it stands, but they "
        "come away when it is lifted."
        if grounded
        else " They come away from the rest when the model is lifted."
    )

    def sentence(s: _Spot) -> str:
        n = s.at_stake
        extent = group_extent(s)
        tail = f" ({extent})." if extent else "."
        if s.kind == 0:
            top, sx, sy = s.sort_pos
            place = f"x={sx}, y={sy}, z={top}"
            if s.lifted:
                text = (
                    f"{n} parts are joined to the rest by a single stud at {place}: the "
                    f"{namer.at(s.upper)} sits on only one stud of the {namer.at(s.lower)}"
                    + tail
                    + lifted_note
                )
            elif s.detached_upper:
                text = (
                    f"{n} parts above {place} hang on a single stud: the {namer.at(s.upper)} "
                    f"sits on only one stud of the {namer.at(s.lower)}" + tail
                )
            else:
                text = (
                    f"{n} parts below {place} hang from a single stud: the "
                    f"{namer.at(s.lower)} is held by only one of its studs, pressed into the "
                    f"{namer.at(s.upper)}" + tail
                )
            return text + " Overlap that joint with more studs or a part that spans it."
        if s.lifted:
            text = (
                f"{n} parts depend on the {namer.at(s.part)} to stay joined to the rest"
                + tail
                + lifted_note
            )
            row = "are each the only link for everything beyond them"
        else:
            text = (
                f"{n} parts depend on the {namer.at(s.part)}: it is their only link to "
                f"{target}, so they come away with it" + tail
            )
            row = "each carry everything beyond them alone"
        if s.run == 1:
            return text + " Give them a second connection that does not pass through this part."
        return (
            text + f" It is the first of {s.run} parts in a row that {row}, ending at the "
            f"{namer.at(s.run_end)}. Give them a second connection that does not pass through "
            "these parts."
        )

    # one sentence per group: a single-stud joint wins over a part that cuts off the same group
    best: dict[tuple[bool, tuple[tuple[int, int], ...]], _Spot] = {}
    for s in spots:
        kept = best.get((s.lifted, s.key))
        if kept is None or (s.kind, s.sort_pos) < (kept.kind, kept.sort_pos):
            best[(s.lifted, s.key)] = s

    # Runs of single parts: t follows s when t's group is s's group minus t's own part.
    successor: dict[tuple[bool, int], _Spot] = {}
    has_predecessor: set[tuple[bool, int]] = set()
    for t in best.values():
        if t.kind != 1:
            continue
        d = t.part_pos
        s = best.get((t.lifted, _merge_ranges([*t.key, (d, d + 1)])))
        if s is not None and s.kind == 1:
            successor[(s.lifted, s.part)] = t
            has_predecessor.add((t.lifted, t.part))
    reported: list[_Spot] = []
    for s in best.values():
        if s.kind == 1:
            if (s.lifted, s.part) in has_predecessor:
                continue
            end = s
            while (end.lifted, end.part) in successor:
                end = successor[(end.lifted, end.part)]
                s.run += 1
            s.run_end = end.part
        reported.append(s)

    ranked = sorted(reported, key=lambda s: (s.kind, -s.at_stake, s.sort_pos, s.lifted))
    shown, rest = ranked[:MAX_WEAK_SPOTS], ranked[MAX_WEAK_SPOTS:]
    smallest_shown = min((s.at_stake for s in shown), default=0)
    word = "smaller" if all(s.at_stake <= smallest_shown for s in rest) else "less serious"
    return [sentence(s) for s in shown], len(ranked), word


# ---- the check -------------------------------------------------------------------------------


def check(build: Build, catalog: Catalog) -> Report:
    parts = build.parts
    n_parts = len(parts)
    if n_parts == 0:
        return Report(ok=False, part_count=0, text="The build has no parts.")

    namer = _Namer(build, catalog)
    # parts turned by an impossible angle are handed to connect as unknown parts
    bad_turn = [i for i, p in enumerate(parts) if p.part in catalog.parts and p.rot % 90 != 0]
    placeable = build
    if bad_turn:
        placed = list(parts)
        for i in bad_turn:
            placed[i] = replace(parts[i], part=_UNPLACEABLE)
        placeable = Build(shape=build.shape, parts=placed)
    occ, collisions, out_of_bounds, unknown = occupancy(placeable, catalog)
    graph = connection_graph(placeable, catalog, occ)

    # per-part geometry (unknown part ids and badly turned parts cover nothing)
    known = np.array([p.part in catalog.parts for p in placeable.parts], dtype=bool)
    dims = np.array(
        [catalog.footprint(p) if k else (0, 0, 0) for p, k in zip(parts, known, strict=True)],
        dtype=float,
    )
    corner = np.array([[p.x, p.y, p.z] for p in parts], dtype=float)
    volume = dims.prod(axis=1)
    on_ground = known & np.array([p.z == 0 for p in parts], dtype=bool)

    pieces = [sorted(c) for c in nx.connected_components(graph)]
    n_components = len(pieces)

    def piece_rank(piece: list[int]) -> tuple[bool, float, int]:
        return (bool(on_ground[piece].any()), float(volume[piece].sum()), -piece[0])

    main = max(pieces, key=piece_rank)
    main_set = set(main)
    grounded = bool(on_ground[main].any())
    loose = [i for i in range(n_parts) if i not in main_set]

    weights = volume[main]
    total = float(weights.sum())
    if total > 0:
        centres = corner[main] + dims[main] / 2.0
        com_arr = (centres * weights[:, None]).sum(axis=0) / total
        com = (float(com_arr[0]), float(com_arr[1]), float(com_arr[2]))
    else:
        com = (0.0, 0.0, 0.0)

    # grounded means a known part of the main piece is at z = 0, so the base is not empty
    stands = False
    foot: _Footprint | None = None
    base_box = (0.0, 0.0, 0.0, 0.0)
    if grounded:
        base = [i for i in main if on_ground[i]]
        x0, y0 = corner[base, 0], corner[base, 1]
        x1, y1 = x0 + dims[base, 0], y0 + dims[base, 1]
        pts = np.concatenate(
            [np.stack(c, axis=1) for c in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
        )
        foot = _footprint(pts, np.array(com[:2]))
        stands = foot.distance <= _EPS
        base_box = (float(x0.min()), float(x1.max()), float(y0.min()), float(y1.max()))

    weak, n_weak, more_word = _weak_spots(build, catalog, occ, graph, main, grounded, known, namer)

    ok = (
        not collisions
        and not out_of_bounds
        and not unknown
        and n_components == 1
        and grounded
        and stands
    )

    # ---- words ---------------------------------------------------------------------------
    summary: list[str] = []
    details: list[str] = []

    bad_turn_set = set(bad_turn)
    missing_id = [i for i in unknown if parts[i].part not in catalog.parts]
    wrong_colour = [i for i in unknown if parts[i].part in catalog.parts and i not in bad_turn_set]
    if bad_turn:
        summary.append(
            f"{_count(len(bad_turn), 'part is', 'parts are')} turned by an angle parts "
            "cannot be turned by"
        )
        shown = [f"{namer.at(i)} (turned {parts[i].rot} degrees)" for i in bad_turn]
        extra = len(shown) - MAX_EXAMPLES
        text = "; ".join(shown[:MAX_EXAMPLES]) + (f"; and {extra} more" if extra > 0 else "")
        details.append(
            f"{_count(len(bad_turn), 'part is', 'parts are')} turned by an angle that is not "
            f"a quarter turn, so {'it' if len(bad_turn) == 1 else 'they'} cannot be placed or "
            f"checked: {text}. Turn parts only by "
            "0, 90, 180 or 270 degrees."
        )
    if missing_id:
        summary.append(f"{_count(len(missing_id), 'part is', 'parts are')} not in the parts table")
        details.append(
            f"{_count(len(missing_id), 'part has', 'parts have')} an id that is not in the "
            f"parts table, so it cannot be built or checked: {namer.examples(missing_id)}. "
            "Use a part from the parts table instead."
        )
    if wrong_colour:
        summary.append(
            f"{_count(len(wrong_colour), 'part is', 'parts are')} in a colour that does not exist"
        )
        lines = []
        for i in wrong_colour[:MAX_EXAMPLES]:
            p = parts[i]
            colour = catalog.colours.get(p.color)
            why = (
                f"colour {p.color} is not in the colour table"
                if colour is None
                else f"{catalog.parts[p.part].name} is not made in {colour.name}"
            )
            lines.append(f"{namer.at(i)} ({why})")
        extra = len(wrong_colour) - len(lines)
        text = "; ".join(lines) + (f"; and {extra} more" if extra > 0 else "")
        details.append(
            f"{_count(len(wrong_colour), 'part is', 'parts are')} in a colour the real part "
            f"is not made in: {text}. Pick a colour the part exists in."
        )
    if collisions:
        summary.append(
            f"{_count(len(collisions), 'pair')} of parts "
            + ("overlaps" if len(collisions) == 1 else "overlap")
        )
        lines = []
        for i, j in collisions[:MAX_EXAMPLES]:
            lo = np.maximum(corner[i], corner[j]).astype(int)
            lines.append(
                f"the {namer.at(i)} and the {namer.at(j)} both fill x={lo[0]}, y={lo[1]}, z={lo[2]}"
            )
        extra = len(collisions) - len(lines)
        text = "; ".join(lines) + (f"; and {extra} more pairs" if extra > 0 else "")
        details.append(
            f"{_count(len(collisions), 'pair')} of parts "
            + ("overlaps" if len(collisions) == 1 else "overlap")
            + " (two parts cannot share a "
            f"cell): {text}."
        )
    if out_of_bounds:
        nx_, ny_, nz_ = build.shape
        summary.append(
            f"{_count(len(out_of_bounds), 'part sticks', 'parts stick')} out of the grid"
        )
        lines = []
        for i in out_of_bounds[:MAX_EXAMPLES]:
            hi = (corner[i] + dims[i] - 1).astype(int)
            p = parts[i]
            lines.append(
                f"{namer.at(i)}, covering x={_span(p.x, int(hi[0]))}, "
                f"y={_span(p.y, int(hi[1]))}, z={_span(p.z, int(hi[2]))}"
            )
        extra = len(out_of_bounds) - len(lines)
        text = "; ".join(lines) + (f"; and {extra} more" if extra > 0 else "")
        details.append(
            f"{_count(len(out_of_bounds), 'part sticks', 'parts stick')} out of the "
            f"{nx_} x {ny_} x {nz_} grid (cells x=0 to {nx_ - 1}, y=0 to {ny_ - 1}, "
            f"z=0 to {nz_ - 1}): {text}."
        )
    if n_components > 1:
        summary.append(
            f"the parts form {n_components} separate pieces with {_count(len(loose), 'loose part')}"
        )
        details.append(
            f"The parts form {n_components} separate pieces. "
            f"{_count(len(loose), 'part is', 'parts are')} not attached through studs to the "
            f"main piece of {_count(len(main), 'part')}: {namer.examples(loose)}. "
            "Parts only hold when one sits on another's studs; parts side by side in a layer "
            "do not hold each other."
        )
    if not grounded and total > 0:
        lowest = min((i for i in main if known[i]), key=lambda i: (parts[i].z, i))
        summary.append("the main piece does not touch the ground")
        details.append(
            f"The main piece ({_count(len(main), 'part')}) does not touch the ground (z=0): "
            f"its lowest part is the {namer.at(lowest)}. Nothing holds it up."
        )
    elif grounded and not stands and foot is not None:
        summary.append("it would tip over")
        bx0, bx1, by0, by1 = base_box
        corners = np.asarray(foot.corners, dtype=float)
        box_area = (bx1 - bx0) * (by1 - by0)
        hull_area = 0.0
        if len(corners) >= 3:
            cx, cy = corners[:, 0], corners[:, 1]
            hull_area = 0.5 * abs(float(cx @ np.roll(cy, -1) - cy @ np.roll(cx, -1)))
        if abs(hull_area - box_area) <= 1e-6:
            outline = (
                f"whose outline spans x={_num(bx0)} to {_num(bx1)}, y={_num(by0)} to {_num(by1)}"
            )
        else:
            # counter-clockwise, starting from the corner with the smallest x (then y)
            start = min(range(len(corners)), key=lambda k: (corners[k, 0], corners[k, 1]))
            corners = np.roll(corners, -start, axis=0)
            named = [f"({_coord(cx_)}, {_coord(cy_)})" for cx_, cy_ in corners[:MAX_CORNERS]]
            extra = len(corners) - len(named)
            outline = "whose outline has corners at " + ", ".join(named)
            if extra > 0:
                outline += f" and {extra} more"
            outline += " (as x, y)"
        near = foot.nearest
        details.append(
            f"It would tip over: the centre of mass, at x={_num(com[0])}, "
            f"y={_num(com[1])}, z={_num(com[2])} (measured from the grid corner), is "
            f"{_num(foot.distance)} studs outside the area the main piece stands on, "
            f"{outline} at z=0; the nearest point of the outline is at x={_num(near[0])}, "
            f"y={_num(near[1])}. Widen the base under the heavy side or move weight back "
            "over the base."
        )

    if ok:
        verdict = f"OK: {_count(n_parts, 'part')} in one connected piece; it stands."
    else:
        verdict = f"NOT BUILDABLE: {_count(n_parts, 'part')}; " + "; ".join(summary) + "."
    lines = [verdict, *details]
    if weak:
        heading = (
            f"{_count(n_weak, 'weak spot')} to strengthen "
            "(they do not fail the checks on their own):"
        )
        lines.append(heading)
        lines.extend(f"- {s}" for s in weak)
        if n_weak > len(weak):
            left_out = _count(n_weak - len(weak), f"{more_word} weak spot")
            lines.append(f"- and {left_out} not listed.")

    return Report(
        ok=ok,
        part_count=n_parts,
        collisions=list(collisions),
        out_of_bounds=list(out_of_bounds),
        unknown_parts=list(unknown),
        components=n_components,
        loose=loose,
        grounded=grounded,
        stands=stands,
        centre_of_mass=com,
        weak_spots=weak,
        text="\n".join(lines),
    )
