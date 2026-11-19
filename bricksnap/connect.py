"""Which cell belongs to which part, which parts hold which, and where a build is weak.

Shared by the layout solver, the finishing pass, the checks and the renderer so they all
agree on what "connected" means: part B is held by part A when B's underside sits directly
on at least one of A's studs. Parts side by side in the same layer do not hold each other.

Sturdiness is measured here too, so the solver and the finishing pass share one definition
of it. ``lone_links(build, catalog)`` lists a Build's *lone links*, heaviest first, and
``sturdiness(build, catalog)`` gives (largest load, number of lone links, sum of their
loads); lower is sturdier. Both work on any Build, finished ones too, and agree with
``bricksnap.checks``: the number of lone links is the number of weak spots it reports.

- Give the connection graph a "ground" node joined to every part at z = 0. A lone link is
  a part (not on the ground) whose removal would cut other parts off from the ground, or a
  joint between two parts that is a group's only connection and engages a single stud.
  Its ``load`` is the number of parts it would cut off, and ``cells`` the number of cells
  those parts cover. A group that stands on the ground itself but is joined to the rest by
  one part or one stud (a leg) is a lone link too ("lifted": it comes away when the model
  is lifted). Groups of fewer than ``MIN_LOAD`` (3) parts do not count; a part and a joint
  that cut off the same group count once; and a run of parts each carrying everything
  beyond it (a plain column) counts once.
- A ``LoneLink`` gives ``load``, ``part``, ``joint`` as (lower, upper) for a single-stud
  joint, ``lifted``, ``run``, ``members`` (indices into ``build.parts``) and ``cells``.

``lone_links_of_graph`` is the same search on a plain graph of parts; the layout solver
feeds it from its own cells while it works.

Implementation notes: the main piece, its base and the searches are exactly those of
``bricksnap.checks`` (see its implementation notes): one depth-first search from a root
joined to every part on the base (parts and single-stud joints whose loss cuts a group off
it), and one over the plain graph of the main piece (groups standing on the base that come
away when lifted), then the same merging of groups and runs.

STAGE 4 ADDITION TO THE CONTRACT: sideways parts
A part with ``Placement.face`` other than "top" lies on its side in the column of three cells
in front of a brick (see ``Placement``).
- ``occupancy``: it covers its column (``Catalog.cells``), for collisions and bounds alike.
- ``connection_graph``: it is joined to the part directly behind its column, one stud
  engaged, when that part is upright, starts at the same z, and has a side stud on that face
  (``Catalog.side_stud_faces``). Otherwise it holds nothing and is held by nothing: it is
  loose. It never sits on studs below it and nothing sits on it (it has no stud on top and
  its underside faces the brick).
- ``on_base_z(p)``: the level at which a part counts as standing on the ground or the base:
  its own z, or z + 1 for a sideways part, which never rests on the ground (its lower edge
  is above the bottom of its column). The checks and the lone links use it.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from bricksnap.catalog import Catalog
from bricksnap.types import FACE_OUT, Build, Placement

MIN_LOAD = 3
"""A lone link carrying fewer parts than this is not a weak spot."""


def on_base_z(p: Placement) -> int:
    """The z at which ``p`` counts as resting on the ground or the base: its own, or one
    above it for a sideways part, which never rests on the ground."""
    return p.z if p.face == "top" else p.z + 1


def side_stud_holder(build: Build, catalog: Catalog, occ: np.ndarray, i: int) -> int | None:
    """The part whose side stud holds the sideways part ``i``, or None when nothing does."""
    p = build.parts[i]
    if p.face not in FACE_OUT or p.part not in catalog.parts:
        return None
    ox, oy = FACE_OUT[p.face]
    bx, by = p.x - ox, p.y - oy
    if not (0 <= bx < occ.shape[0] and 0 <= by < occ.shape[1] and 0 <= p.z < occ.shape[2]):
        return None
    j = int(occ[bx, by, p.z])
    if j < 0 or j == i:
        return None
    q = build.parts[j]
    if q.part not in catalog.parts or q.z != p.z or p.face not in catalog.side_stud_faces(q):
        return None
    return j


def occupancy(
    build: Build, catalog: Catalog
) -> tuple[np.ndarray, list[tuple[int, int]], list[int], list[int]]:
    """Map every cell to the part that covers it.

    Returns ``(occ, collisions, out_of_bounds, unknown)``:

    - ``occ``: int32 array of ``build.shape``, the index into ``build.parts`` of the part
      covering each cell, or -1 where the cell is empty.
    - ``collisions``: pairs ``(i, j)`` with ``i < j`` of parts that share at least one cell.
      Where two parts collide, ``occ`` keeps the lower index.
    - ``out_of_bounds``: indices of parts that stick out of the grid (they are not written
      into ``occ``).
    - ``unknown``: indices of parts whose part id or colour is not in the catalogue, or whose
      colour does not exist for that part (parts with an unknown id are not written into
      ``occ``; a known part in a wrong colour still is).
    """
    nx_, ny_, nz_ = build.shape
    occ = np.full(build.shape, -1, dtype=np.int32)
    collisions: set[tuple[int, int]] = set()
    out_of_bounds: list[int] = []
    unknown: list[int] = []
    for i, p in enumerate(build.parts):
        if p.part not in catalog.parts:
            unknown.append(i)
            continue
        if not catalog.exists(p.part, p.color):
            unknown.append(i)
        w, d, h = catalog.footprint(p)
        if p.x < 0 or p.y < 0 or p.z < 0 or p.x + w > nx_ or p.y + d > ny_ or p.z + h > nz_:
            out_of_bounds.append(i)
            continue
        region = occ[catalog.cells(p)]
        taken = region[region >= 0]
        for j in np.unique(taken):
            collisions.add((int(j), i))
        region[region < 0] = i
    return occ, sorted(collisions), out_of_bounds, unknown


def connection_graph(build: Build, catalog: Catalog, occ: np.ndarray | None = None) -> nx.Graph:
    """Graph of which parts hold which.

    Nodes are indices into ``build.parts`` (every part is a node, even if nothing touches it).
    An edge ``(a, b)`` means one sits directly on the other's studs; its ``studs`` attribute
    is how many studs are engaged. Pass ``occ`` from :func:`occupancy` to avoid recomputing it.
    """
    if occ is None:
        occ = occupancy(build, catalog)[0]
    nz_ = build.shape[2]
    g = nx.Graph()
    g.add_nodes_from(range(len(build.parts)))
    for i, p in enumerate(build.parts):
        part = catalog.parts.get(p.part)
        if part is None:
            continue
        if p.face != "top":
            holder = side_stud_holder(build, catalog, occ, i)
            if holder is not None:
                g.add_edge(holder, i, studs=1)
            continue
        top = p.z + part.h
        if top >= nz_:
            continue
        counts: dict[int, int] = {}
        for x, y in catalog.stud_cells(p):
            if not (0 <= x < occ.shape[0] and 0 <= y < occ.shape[1]):
                continue
            j = int(occ[x, y, top])
            if j < 0 or j == i:
                continue
            above = build.parts[j]
            above_part = catalog.parts.get(above.part)
            # the part above must start exactly on this layer and accept studs underneath
            if above_part is None or above.z != top or not above_part.antistuds_bottom:
                continue
            if above.face != "top":  # a sideways part's underside faces its brick
                continue
            counts[j] = counts.get(j, 0) + 1
        for j, n in counts.items():
            g.add_edge(i, j, studs=n)
    return g


# ---- sturdiness: lone links --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LoneLink:
    """A place a group of parts depends on alone (a weak spot in the check report)."""

    load: int  # parts that would come away
    part: int  # the part they depend on; for a single-stud joint, the part that comes away
    joint: tuple[int, int] | None  # (lower, upper) of a single-stud joint, None for a part
    lifted: bool  # the group stands on the ground itself and only comes away when lifted
    run: int  # parts in a row that each carry everything beyond them (1 for a joint)
    members: tuple[int, ...]  # the parts that would come away, sorted
    cells: int  # cells those parts cover


@dataclass(slots=True)
class _Spot:
    at: int
    kind: int  # 0 single-stud joint, 1 part
    key: tuple[tuple[int, int], ...]  # the group, as merged ranges of ``order``
    order: list[int]
    lifted: bool
    part: int
    part_pos: int = -1
    joint: tuple[int, int] | None = None
    run: int = 1


def _merge(ranges: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for a, b in sorted(ranges):
        if a == b:
            continue
        if merged and merged[-1][1] == a:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return tuple(merged)


def _dfs(
    adj: list[list[int]], root: int
) -> tuple[list[int], list[int], list[int], list[int], list[int]]:
    """Iterative depth-first search (Tarjan): preorder, place in it, low links, parent, size."""
    n = len(adj)
    disc = [-1] * n
    low = [0] * n
    parent = [-1] * n
    size = [0] * n
    order = [root]
    disc[root] = 0
    stack = [(root, iter(adj[root]))]
    while stack:
        v, it = stack[-1]
        advanced = False
        for w in it:
            if disc[w] < 0:
                parent[w] = v
                disc[w] = low[w] = len(order)
                order.append(w)
                stack.append((w, iter(adj[w])))
                advanced = True
                break
            if w != parent[v]:
                low[v] = min(low[v], disc[w])
        if advanced:
            continue
        stack.pop()
        size[v] = len(order) - disc[v]
        p = parent[v]
        if p >= 0:
            low[p] = min(low[p], low[v])
    return order, disc, low, parent, size


def lone_links_of_graph(
    n: int,
    edges: list[tuple[int, int, int]],
    z: list[int],
    volume: list[float],
    known: list[bool],
) -> tuple[list[LoneLink], int]:
    """The lone links of a graph of ``n`` parts, and the sum of their loads.

    ``edges`` are (lower, upper, studs engaged); ``volume`` is the cells each part covers
    (0 for a part not in the catalogue), ``known`` whether it is in the catalogue. The main
    piece, its base and the two searches are exactly those of ``bricksnap.checks`` (see its
    implementation notes), so the links found here are its weak spots: groups of fewer than
    ``MIN_LOAD`` parts are left out, a joint and a part that cut off the same group count
    once, and a run of parts each carrying everything beyond it counts once.
    """
    nbrs: list[list[int]] = [[] for _ in range(n)]
    studs: dict[tuple[int, int], int] = {}
    for a, b, s in edges:
        nbrs[a].append(b)
        nbrs[b].append(a)
        studs[(a, b) if a < b else (b, a)] = s
    if n == 0:
        return [], 0
    rows = [a for a, _, _ in edges]
    cols = [b for _, b, _ in edges]
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    on_ground = [known[i] and z[i] == 0 for i in range(n)]
    best_label, best_rank = -1, None
    vol = np.bincount(labels, weights=volume, minlength=int(labels.max()) + 1)
    grounded_l = np.zeros(len(vol), dtype=bool)
    first = np.full(len(vol), n, dtype=np.int64)
    for i in range(n - 1, -1, -1):
        first[labels[i]] = i
        if on_ground[i]:
            grounded_l[labels[i]] = True
    for lab in range(len(vol)):
        rank = (bool(grounded_l[lab]), float(vol[lab]), -int(first[lab]))
        if best_rank is None or rank > best_rank:
            best_label, best_rank = lab, rank
    main = [i for i in range(n) if labels[i] == best_label]
    main_known = [i for i in main if known[i]]
    if not main_known or len(main) < MIN_LOAD + 1:
        return [], 0
    base_z = 0 if grounded_l[best_label] else min(z[i] for i in main_known)
    is_anchor = [False] * n
    for i in main_known:
        if z[i] == base_z:
            is_anchor[i] = True
    anchors = [i for i in main_known if is_anchor[i]]

    def lower_upper(p: int, v: int) -> tuple[int, int]:
        return (p, v) if z[p] < z[v] else (v, p)

    def single(p: int, v: int) -> bool:
        return studs[(p, v) if p < v else (v, p)] == 1

    spots: list[_Spot] = []
    # first search: against the base, through a root joined to every part resting on it
    root = n
    adj = [list(nb) for nb in nbrs] + [anchors]
    for i in anchors:
        adj[i].append(root)
    order, disc, low, parent, size = _dfs(adj, root)
    cut_children: dict[int, list[int]] = {}
    for v in order[1:]:
        p = parent[v]
        if p == root:
            continue
        a, b = disc[v], disc[v] + size[v]
        if low[v] >= disc[p]:
            cut_children.setdefault(p, []).append(v)
        if low[v] > disc[p] and single(p, v) and b - a >= MIN_LOAD:
            spots.append(_Spot(b - a, 0, ((a, b),), order, False, v, joint=lower_upper(p, v)))
    for c_part, children in cut_children.items():
        if is_anchor[c_part]:
            continue
        at = sum(size[c] for c in children)  # the subtrees never overlap
        if at >= MIN_LOAD:
            key = _merge([(disc[c], disc[c] + size[c]) for c in children])
            spots.append(_Spot(at, 1, key, order, False, c_part, disc[c_part]))

    # second search: the plain graph of the main piece, for groups that stand on the base
    # themselves but come away when the model is lifted
    total = len(anchors)
    if total >= 2:
        n_main = len(main)
        order, disc, low, parent, size = _dfs(nbrs, main[0])
        prefix = [0]
        for i in order:
            prefix.append(prefix[-1] + is_anchor[i])
        children_of: dict[int, list[int]] = {}
        separated: dict[int, list[int]] = {}
        for v in order[1:]:
            p = parent[v]
            children_of.setdefault(p, []).append(v)
            a, b = disc[v], disc[v] + size[v]
            if low[v] >= disc[p]:
                separated.setdefault(p, []).append(v)
            if low[v] > disc[p] and single(p, v) and 0 < prefix[b] - prefix[a] < total:
                if b - a <= n_main - (b - a):
                    at, key, away = b - a, ((a, b),), v
                else:
                    at, key, away = n_main - (b - a), _merge([(0, a), (b, n_main)]), p
                if at >= MIN_LOAD:
                    spots.append(_Spot(at, 0, key, order, True, away, joint=lower_upper(p, v)))
        for v, seps in separated.items():
            if is_anchor[v] or n_main - 1 - max(size[c] for c in seps) < MIN_LOAD:
                continue  # whichever piece stays, fewer than MIN_LOAD parts come away
            comps: list[tuple[int, tuple[tuple[int, int], ...], int]] = []
            for c in seps:
                a, b = disc[c], disc[c] + size[c]
                comps.append((b - a, ((a, b),), prefix[b] - prefix[a]))
            rest_size = n_main - 1 - sum(c[0] for c in comps)
            if rest_size > 0:
                dv, ev = disc[v], disc[v] + size[v]
                sep_set = set(seps)
                rest = [(0, dv), (ev, n_main)] + [
                    (disc[c], disc[c] + size[c]) for c in children_of.get(v, []) if c not in sep_set
                ]
                comps.append((rest_size, _merge(rest), total - sum(c[2] for c in comps)))
            grounded = [c for c in comps if c[2] > 0]
            if len(grounded) < 2:
                continue
            biggest = max(c[0] for c in grounded)
            tied = [k for k, c in enumerate(grounded) if c[0] == biggest]
            stays = tied[0]
            if len(tied) > 1:
                stays = min(
                    tied,
                    key=lambda k: min(order[i] for a, b in grounded[k][1] for i in range(a, b)),
                )
            away_c = [c for k, c in enumerate(grounded) if k != stays]
            at = sum(c[0] for c in away_c)
            if at >= MIN_LOAD:
                key = _merge([r for c in away_c for r in c[1]])
                spots.append(_Spot(at, 1, key, order, True, v, disc[v]))

    # one per group (a joint wins over a part), then runs of parts count once
    best: dict[tuple[bool, tuple[tuple[int, int], ...]], _Spot] = {}
    for s in spots:
        kept = best.get((s.lifted, s.key))
        if kept is None or s.kind < kept.kind:
            best[(s.lifted, s.key)] = s
    successor: dict[tuple[bool, int], _Spot] = {}
    has_predecessor: set[tuple[bool, int]] = set()
    for t in best.values():
        if t.kind != 1:
            continue
        d = t.part_pos
        s = best.get((t.lifted, _merge([*t.key, (d, d + 1)])))
        if s is not None and s.kind == 1:
            successor[(s.lifted, s.part)] = t
            has_predecessor.add((t.lifted, t.part))
    out: list[LoneLink] = []
    for s in best.values():
        if s.kind == 1:
            if (s.lifted, s.part) in has_predecessor:
                continue
            end = s
            while (end.lifted, end.part) in successor:
                end = successor[(end.lifted, end.part)]
                s.run += 1
        members = tuple(sorted(s.order[k] for a, b in s.key for k in range(a, b)))
        cells = round(sum(volume[m] for m in members))
        out.append(LoneLink(s.at, s.part, s.joint, s.lifted, s.run, members, cells))
    out.sort(key=lambda ln: (-ln.load, ln.joint is None, ln.lifted, ln.members))
    return out, sum(s.at for s in best.values())


def lone_links(build: Build, catalog: Catalog) -> list[LoneLink]:
    """The weak spots of ``build`` as ``bricksnap.checks`` finds them, heaviest first."""
    return _lone_links_of_build(build, catalog)[0]


def sturdiness(build: Build, catalog: Catalog) -> tuple[int, int, int]:
    """(largest load, number of lone links, sum of their loads): lower is sturdier."""
    links, total = _lone_links_of_build(build, catalog)
    return (links[0].load if links else 0, len(links), total)


def _lone_links_of_build(build: Build, catalog: Catalog) -> tuple[list[LoneLink], int]:
    occ = occupancy(build, catalog)[0]
    graph = connection_graph(build, catalog, occ)
    known = [p.part in catalog.parts for p in build.parts]
    volume = [
        float(np.prod(catalog.footprint(p))) if k else 0.0
        for p, k in zip(build.parts, known, strict=True)
    ]
    edges = []
    for a, b, s in graph.edges(data="studs"):
        lo, hi = (a, b) if on_base_z(build.parts[a]) < on_base_z(build.parts[b]) else (b, a)
        edges.append((int(lo), int(hi), int(s)))
    z = [on_base_z(p) for p in build.parts]
    return lone_links_of_graph(len(build.parts), edges, z, volume, known)
