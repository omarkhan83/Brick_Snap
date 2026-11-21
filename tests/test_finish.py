"""Tests for the finishing pass (bricksnap/finish.py).

Every result is checked by ``assert_finished`` below, which is written here from the contract
and uses only bricksnap.connect and the catalogue: the same cells covered in the same
colours, real part and colour pairs, no new loose pieces, valid steps, slopes facing downhill,
nothing standing on a tile or a slanted face, and no less sturdy than the input, seen as the
input's parts (the largest load in cells no higher, no more lone links; see
``groups_as_input``).
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

import networkx as nx
import numpy as np
import pytest
import shapes

import bricksnap.finish as finish_module
from bricksnap.catalog import Catalog
from bricksnap.connect import connection_graph, lone_links, occupancy
from bricksnap.finish import finish
from bricksnap.layout import solve
from bricksnap.types import (
    DEFAULT_COLOUR,
    EMPTY,
    FINISH_SLOPED,
    FINISH_SMOOTH,
    FINISH_STUDS,
    Build,
    Design,
    Detail,
    Placement,
    plain,
)

RED, WHITE = 4, 15
NOUGAT = 92  # no 3039 and no 54200 in this colour
BRIGHT_LIGHT_YELLOW = 226  # cheese slopes only, no 45-degree slopes
DIRECTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]


# ---- helpers ----------------------------------------------------------------------------------


def design_of(filled: np.ndarray, colour: int = DEFAULT_COLOUR) -> Design:
    return Design(colors=np.where(filled, colour, EMPTY).astype(np.int16))


def from_heights(heights: np.ndarray, nz: int | None = None, colour=DEFAULT_COLOUR) -> Design:
    """A Design of columns: heights[x, y] filled plates from the ground."""
    nz = nz or int(heights.max())
    z = np.arange(nz)
    return design_of(z[None, None, :] < heights[:, :, None], colour)


def fin(design: Design) -> np.ndarray:
    assert design.finish is not None
    return design.finish


def open_mask(design: Design) -> np.ndarray:
    filled = design.filled
    above = np.ones_like(filled)
    above[:, :, :-1] = ~filled[:, :, 1:]
    return filled & above


def mark_open(design: Design, value: int) -> Design:
    assert design.finish is not None
    fin(design)[open_mask(design)] = value
    return design


def pieces(build: Build, catalog) -> list[set[int]]:
    return list(nx.connected_components(connection_graph(build, catalog)))


def kind(catalog, p: Placement) -> str:
    return catalog.parts[p.part].kind


def low_edge(catalog, p: Placement) -> list[tuple[int, int]]:
    w, d, _ = catalog.footprint(p)
    dx, dy = catalog.low_side(p)
    return [
        (p.x + i, p.y + j)
        for i in range(w)
        for j in range(d)
        if not (0 <= i + dx < w and 0 <= j + dy < d)
    ]


def slanted_cells(catalog, p: Placement) -> list[tuple[int, int, int]]:
    w, d, h = catalog.footprint(p)
    studs = set(catalog.stud_cells(p))
    top = p.z + h - 1
    return [
        (p.x + i, p.y + j, top)
        for i in range(w)
        for j in range(d)
        if (p.x + i, p.y + j) not in studs
    ]


def underside_mask(design: Design) -> np.ndarray:
    """Underside cells: filled, an empty cell below (not in the bottom layer), filled above."""
    filled = design.filled
    out = np.zeros_like(filled)
    out[:, :, 1:-1] = filled[:, :, 1:-1] & ~filled[:, :, :-2] & filled[:, :, 2:]
    return out


def cut_cells(catalog, p: Placement) -> list[tuple[int, int, int]]:
    """The bottom cells of an inverted slope's slanted columns (those it does not grip under)."""
    w, d, _ = catalog.footprint(p)
    grips = set(catalog.grip_cells(p))
    return [
        (p.x + i, p.y + j, p.z)
        for i in range(w)
        for j in range(d)
        if (p.x + i, p.y + j) not in grips
    ]


def assert_inverted_slopes(
    before: Build, after: Build, design: Design, catalog, occ1: np.ndarray
) -> None:
    """The stage 4 addition on undersides, checked from the contract: each inverted slope's
    slanted columns stand over an empty cell on a sloped underside cell, outward is clear
    below its top level, no open top it covers wants a tile or a slope, and it holds where
    the input parts it was cut from were held (a random layout may have loose ones)."""
    nx_, ny_, nz_ = design.shape
    above = np.zeros_like(design.filled)
    above[:, :, :-1] = design.filled[:, :, 1:]
    wanted_top = design.filled & ~above & (fin(design) != FINISH_STUDS)
    for q in detail_parts(after, design):  # a cell under a detail keeps its stud
        if q.face == "top":
            w, d, _ = catalog.footprint(q)
            wanted_top[q.x : q.x + w, q.y : q.y + d, q.z - 1] = False
    graph = connection_graph(after, catalog)
    graph0 = connection_graph(before, catalog)
    occ0 = occupancy(before, catalog)[0]
    for i, p in enumerate(after.parts):
        if kind(catalog, p) != "slope_inverted":
            continue
        was = {int(j) for j in np.unique(occ0[catalog.cells(p)]) if j >= 0}
        if all(graph0.degree[j] > 0 for j in was):
            assert graph.degree[i] > 0, f"{p} holds nothing and is held by nothing"
        w, d, h = catalog.footprint(p)
        assert not wanted_top[catalog.cells(p)].any(), f"{p} covers a top that wants a part"
        for x, y, z in cut_cells(catalog, p):
            assert z > 0 and not design.filled[x, y, z - 1], f"{p} has something under its slant"
            assert fin(design)[x, y, z] == FINISH_SLOPED
        thin = tuple(-v for v in catalog.low_side(p))
        for i_ in range(w):
            for j in range(d):
                x, y = p.x + i_, p.y + j
                if p.x <= x + thin[0] < p.x + w and p.y <= y + thin[1] < p.y + d:
                    continue  # not on the thin edge
                ox, oy = x + thin[0], y + thin[1]
                if 0 <= ox < nx_ and 0 <= oy < ny_:
                    for z in range(p.z, p.z + h - 1):
                        assert not design.filled[ox, oy, z], f"{p} faces into the model"
                        assert occ1[ox, oy, z] < 0, f"{p} faces into a detail part"


def assert_finished(before: Build, after: Build, design: Design, catalog) -> dict:
    """Independent check of sections 1, 5 and 6 of the contract. Returns some counts."""
    assert after is not before
    assert after.shape == before.shape
    assert after.report is None
    assert after.design_id == before.design_id
    assert after.notes[: len(before.notes)] == before.notes
    occ0, col0, oob0, unk0 = occupancy(before, catalog)
    occ1, col1, oob1, unk1 = occupancy(after, catalog)
    assert len(col1) <= len(col0) and len(oob1) <= len(oob0) and len(unk1) <= len(unk0)
    details = detail_parts(after, design)
    for p in after.parts:
        assert catalog.exists(p.part, p.color), f"{p.part} does not exist in colour {p.color}"
        assert p.part != "2412b" or p in details, "the grille tile is only a detail part"
    # the same cells, each in its colour; new cells only where details stand
    base = occ0 >= 0
    assert np.array_equal(base, design.filled)
    assert np.all(occ1[base] >= 0), "a cell of the model is no longer covered"
    new = (occ1 >= 0) & ~base
    assert not design.filled[new].any()
    colour1 = np.array([p.color for p in after.parts], dtype=np.int64)
    assert np.array_equal(colour1[occ1[base]], design.colors[base])
    detail_ids = {i for i, p in enumerate(after.parts) if p in details}
    assert {int(i) for i in np.unique(occ1[new])} == detail_ids
    # pieces: not more, and the main piece stays together
    g0 = pieces(before, catalog)
    g1 = pieces(after, catalog)
    assert len(g1) <= len(g0), f"{len(g0)} pieces became {len(g1)}"
    main0 = max(g0, key=len)
    main_cells = np.isin(occ0, list(main0))
    label = {n: k for k, comp in enumerate(g1) for n in comp}
    assert len({label[int(i)] for i in np.unique(occ1[main_cells])}) == 1
    # nothing stands on a tile or on a slanted face; details really hold
    nz = design.shape[2]
    for p in after.parts:
        if kind(catalog, p) in ("tile", "slope") and p not in details:
            w, d, h = catalog.footprint(p)
            if p.z + h < nz:
                for x, y, _ in slanted_cells(catalog, p):
                    assert occ1[x, y, p.z + h] < 0, f"something stands on the face of {p}"
    graph = connection_graph(after, catalog)
    for i in detail_ids:
        assert graph.degree[i] > 0, f"detail {after.parts[i]} does not hold on"
    # slopes: downhill clear above the bottom level, slanted tops open and marked sloped
    for p in after.parts:
        if kind(catalog, p) != "slope" or p in details:
            continue
        dx, dy = catalog.low_side(p)
        _, _, h = catalog.footprint(p)
        for x, y in low_edge(catalog, p):
            for z in range(p.z + 1, p.z + h):
                nx_, ny_ = x + dx, y + dy
                inside = 0 <= nx_ < design.shape[0] and 0 <= ny_ < design.shape[1]
                assert not inside or not design.filled[nx_, ny_, z], f"{p} faces into the model"
                assert not inside or occ1[nx_, ny_, z] < 0, f"{p} faces into a detail part"
        for x, y, z in slanted_cells(catalog, p):
            assert fin(design)[x, y, z] == FINISH_SLOPED
            assert z + 1 == nz or not design.filled[x, y, z + 1]
    # steps: 1..n, none before a part it stands on, details last in groups of up to eight
    steps = sorted({p.step for p in after.parts})
    assert steps == list(range(1, len(steps) + 1)) or not after.parts
    for p in after.parts:
        if p.z == 0:
            continue
        w, d, _ = catalog.footprint(p)
        below = occ1[p.x : p.x + w, p.y : p.y + d, p.z - 1]
        for j in np.unique(below[below >= 0]):
            assert after.parts[int(j)].step <= p.step, f"{p} comes before the part under it"
    assert_steps_follow_the_input(before, after, details, occ0, occ1, catalog)
    if details:
        last = max((p.step for i, p in enumerate(after.parts) if i not in detail_ids), default=0)
        dsteps = Counter(after.parts[i].step for i in detail_ids)
        assert min(dsteps) == last + 1
        assert max(dsteps.values()) <= 8
        ordered = sorted(detail_ids, key=lambda i: after.parts[i].step)
        keys = [(after.parts[i].z, after.parts[i].y, after.parts[i].x) for i in ordered]
        steps_in_order = [after.parts[i].step for i in ordered]
        assert all(
            not (steps_in_order[a] < steps_in_order[b] and keys[a] > keys[b])
            for a in range(len(ordered))
            for b in range(len(ordered))
        )
    assert_inverted_slopes(before, after, design, catalog, occ1)
    assert_no_less_sturdy(before, after, design, catalog)
    c = counts(after, design, catalog)
    assert_summary_note(before, after, design, c, len(details))
    return c


def cells_of(build: Build, members, catalog) -> int:
    return sum(int(np.prod(catalog.footprint(build.parts[i]))) for i in members)


def groups_as_input(
    build: Build, catalog, before: Build | None = None
) -> dict[frozenset, tuple[int, int]]:
    """The lone links of ``build`` seen as the input's parts: {the input parts in the group:
    (how many, cells)}.

    Each part stands for the parts of ``before`` (the input; without it, ``build`` is its own
    input) whose cells it covers, a part covering none of them (a detail) for itself. When
    the part a group hangs on was cut from one input part, the group leaves out the other
    pieces of it: a brick cut into plates and a slope hangs on its own bottom plate, and that
    is still the one brick, which hung on nothing. Groups of the same input parts are one; a
    group holding fewer than 3 input parts is none. The cells are those of the parts left in
    the group.
    """
    links = lone_links(build, catalog)
    occ0 = occupancy(before if before is not None else build, catalog)[0]

    def stands_for(i: int) -> set:
        p = build.parts[i]
        own = {("own", p.part, p.color, p.x, p.y, p.z, p.rot)}
        if p.part not in catalog.parts or min(p.x, p.y, p.z) < 0:
            return own
        region = occ0[catalog.cells(p)]
        return {int(j) for j in region[region >= 0]} or own

    groups: dict[frozenset, tuple[int, int]] = {}
    for ln in links:
        assert ln.cells == cells_of(build, ln.members, catalog)
        assert ln.load == len(ln.members) >= 3
        if ln.joint is None:
            on = ln.part
        else:
            on = ln.joint[0] if ln.joint[1] in ln.members else ln.joint[1]
        assert on not in ln.members
        base = stands_for(on)
        kept = [m for m in ln.members if len(base) > 1 or stands_for(m) != base]
        held = frozenset().union(*(stands_for(m) for m in kept))
        if len(held) >= 3:
            cells = cells_of(build, kept, catalog)
            groups[held] = (len(held), max(cells, groups.get(held, (0, 0))[1]))
    return groups


def heavy_as_checks(build: Build, catalog, before: Build | None = None) -> int:
    """The lone links of 40 cells or more counted as the checks count them (in the build's
    own parts), two that would take away the same parts of ``before`` (the input) counting
    once: the stage 4 part of the rule allows no more of them than the input had."""
    occ0 = occupancy(before if before is not None else build, catalog)[0]

    def stands_for(i: int) -> frozenset:
        p = build.parts[i]
        own = frozenset({("own", p.part, p.color, p.x, p.y, p.z, p.rot)})
        if p.part not in catalog.parts or min(p.x, p.y, p.z) < 0:
            return own
        region = occ0[catalog.cells(p)]
        return frozenset(int(j) for j in region[region >= 0]) or own

    keys = set()
    for ln in lone_links(build, catalog):
        if ln.cells >= 40:
            assert ln.cells == cells_of(build, ln.members, catalog)
            keys.add(frozenset().union(*(stands_for(m) for m in ln.members)))
    return len(keys)


def sturdiness_in_cells(build: Build, catalog, before: Build | None = None) -> tuple[int, int]:
    """(largest load in cells, number of lone links), seen as the input's parts."""
    groups = groups_as_input(build, catalog, before)
    return max((cells for _, cells in groups.values()), default=0), len(groups)


def assert_no_less_sturdy(before: Build, after: Build, design: Design, catalog) -> None:
    """The stage 3 rule: compared with the input with the detail parts standing on it, and
    seen as the input's parts (``groups_as_input``), the largest load in cells is no higher
    and there are no more lone links; and (stage 4) counted as the checks count them, no
    more lone links of 40 cells or more (``heavy_as_checks``)."""
    base = Build(shape=before.shape, parts=[*before.parts, *detail_parts(after, design)])
    most0, count0 = sturdiness_in_cells(base, catalog, before)
    most1, count1 = sturdiness_in_cells(after, catalog, before)
    assert most1 <= most0, f"the heaviest load went from {most0} to {most1} cells"
    assert count1 <= count0, f"the lone links went from {count0} to {count1}"
    heavy0, heavy1 = heavy_as_checks(base, catalog, before), heavy_as_checks(after, catalog, before)
    assert heavy1 <= heavy0, f"the lone links of 40+ cells went from {heavy0} to {heavy1}"


def hanging_on_one_part(build: Build, catalog, before: Build | None = None) -> int:
    """The most cells cut off from the ground by taking out one part, worked out here from
    the connection graph alone: an independent check of the measure on small builds.

    With ``before`` (the input), ``build`` is seen as the input's parts, as in
    ``groups_as_input``: what is cut off leaves out the other pieces of the part taken out
    when that part was cut from one input part, and counts only if it holds at least 3 input
    parts."""
    graph = connection_graph(build, catalog)
    ground = -1
    graph.add_node(ground)
    graph.add_edges_from((ground, i) for i, p in enumerate(build.parts) if p.z == 0)
    reach = nx.node_connected_component(graph, ground)
    occ0 = occupancy(before if before is not None else build, catalog)[0]

    def stands_for(i: int) -> frozenset:
        p = build.parts[i]
        region = occ0[catalog.cells(p)] if min(p.x, p.y, p.z) >= 0 else np.empty(0, int)
        return frozenset(int(j) for j in region[region >= 0]) or frozenset({("own", i)})

    worst = 0
    for i, p in enumerate(build.parts):
        if p.z == 0 or i not in reach:
            continue
        rest = graph.copy()
        rest.remove_node(i)
        cut = reach - {i} - nx.node_connected_component(rest, ground)
        base = stands_for(i)
        kept = [m for m in cut if len(base) > 1 or stands_for(m) != base]
        if len(frozenset().union(*(stands_for(m) for m in kept))) >= 3:
            worst = max(worst, cells_of(build, kept, catalog))
    return worst


def assert_steps_follow_the_input(before, after, details, occ0, occ1, catalog) -> None:
    """Section 6: a part kept from the input keeps its step, a new part takes the latest step
    of the input parts whose cells it covers, and a part is then moved up only as far as the
    part it stands on. Steps are compared after numbering both 1..n, since gaps close up."""
    if not after.parts or before.parts == after.parts:
        return
    kept = {(p.part, p.color, p.x, p.y, p.z, p.rot): p.step for p in before.parts}
    step0 = np.array([p.step for p in before.parts] + [0], dtype=np.int64)
    want: dict[int, int] = {}
    for i, p in enumerate(after.parts):
        if p in details:
            continue
        key = (p.part, p.color, p.x, p.y, p.z, p.rot)
        if key in kept:
            want[i] = kept[key]
        else:
            want[i] = int(step0[occ0[catalog.cells(p)]].max())
    changed = True
    while changed:  # no part before a part it stands on: raise until nothing moves
        changed = False
        for i in want:
            p = after.parts[i]
            if p.z == 0:
                continue
            w, d, _ = catalog.footprint(p)
            below = occ1[p.x : p.x + w, p.y : p.y + d, p.z - 1]
            for j in np.unique(below[below >= 0]):
                j = int(j)
                if j in want and want[j] > want[i]:
                    want[i] = want[j]
                    changed = True
    dense = {s: n + 1 for n, s in enumerate(sorted(set(want.values())))}
    got = {i: after.parts[i].step for i in want}
    assert got == {i: dense[s] for i, s in want.items()}, "the steps do not follow the input's"


SUMMARY = re.compile(
    r"Finishing placed (\d+) tiles?, (\d+) slopes?(?:, (\d+) inverted slopes?)? and "
    r"(\d+) detail parts?\.$"
)
REASON = re.compile(
    r"(\d+) cells? marked (smooth|sloped on the underside|sloped) (at x=\d|in \d+ places \(x=\d)"
)
MERGED = re.compile(
    r"And (\d+) more cells? in other places (?:was|were) left as (?:it was|they were)\.$"
)


def reason_notes(before: Build, after: Build) -> list[str]:
    """This pass's sentences about cells left as they were."""
    own = after.notes[len(before.notes) :]
    return [n for n in own[1:] if not n.startswith("Detail part ")]


def assert_summary_note(before, after, design, c, n_details) -> None:
    """The input's notes, then one summary sentence whose counts are right, then at most six
    sentences saying why cells were left as they were (which add up to every smooth cell that
    kept its stud and every sloped cell that got no slope, plus marked cells under a detail),
    then one sentence per skipped detail; nothing at all when there was nothing to do."""
    own = after.notes[len(before.notes) :]
    if c["smooth"] == 0 and c["sloped"] == 0 and c["underside"] == 0 and not design.details:
        assert own == []
        return
    m = SUMMARY.match(own[0])
    assert m, own[0]
    tiles, slopes, inverted, placed = m.groups()
    assert [int(tiles), int(slopes), int(placed)] == [
        c["tiles"],
        sum(c["slopes"].values()),
        n_details,
    ]
    # inverted slopes are counted exactly when some underside cell is marked sloped
    assert (inverted is not None) == (c["underside"] > 0), own[0]
    assert int(inverted or 0) == sum(c["inverted"].values())
    reasons = reason_notes(before, after)
    assert own[1 : 1 + len(reasons)] == reasons, "the reasons come before the detail notes"
    assert len(own) == 1 + len(reasons) + len(design.details) - n_details
    assert len(reasons) <= 6
    by_name = Counter()
    for n, text in enumerate(reasons):
        merged = MERGED.match(text)
        if merged:
            assert n == len(reasons) - 1 == 5, "only a sixth, last sentence merges"
            by_name["merged"] += int(merged.group(1))
            continue
        r = REASON.match(text)
        assert r, text
        by_name[r.group(2)] += int(r.group(1))
    want = {
        "smooth": c["smooth_left"] + c["smooth_held"],
        "sloped": c["sloped_left"] + c["sloped_held"],
        "sloped on the underside": c["underside_left"],
    }
    if by_name["merged"]:
        assert sum(by_name.values()) == sum(want.values()), (reasons, want)
    else:
        assert all(by_name[k] == want[k] for k in want), (reasons, want)


def detail_parts(build: Build, design: Design) -> list[Placement]:
    """Parts of ``build`` standing in cells that are empty in the Design."""
    out = []
    for p in build.parts:
        inside = p.x < design.shape[0] and p.y < design.shape[1] and p.z < design.shape[2]
        if inside and not design.filled[p.x, p.y, p.z]:
            out.append(p)
    return out


def counts(build: Build, design: Design, catalog) -> dict:
    """How many open smooth and sloped cells got a tile or a slanted face."""
    occ = occupancy(build, catalog)[0]
    details = detail_parts(build, design)
    under = np.zeros(design.shape, dtype=bool)
    for p in details:
        w, d, _ = catalog.footprint(p)
        under[p.x : p.x + w, p.y : p.y + d, p.z - 1] = True
    opened = open_mask(design) & ~under
    smooth = opened & (fin(design) == FINISH_SMOOTH)
    sloped = opened & (fin(design) == FINISH_SLOPED)
    underside = underside_mask(design) & (fin(design) == FINISH_SLOPED)
    tiled = np.zeros(design.shape, dtype=bool)
    slanted = np.zeros(design.shape, dtype=bool)
    for p in build.parts:
        if p in details:
            continue
        if kind(catalog, p) == "tile":
            tiled[catalog.cells(p)] = True
        if kind(catalog, p) == "slope":
            for c in slanted_cells(catalog, p):
                slanted[c] = True
        if kind(catalog, p) == "slope_inverted":
            for c in cut_cells(catalog, p):
                slanted[c] = True
    assert not (tiled & ~smooth).any(), "a tile where no smooth open cell was"
    assert np.all(occ[under] >= 0)
    held = open_mask(design) & under
    return {
        "smooth_held": int((held & (fin(design) == FINISH_SMOOTH)).sum()),
        "sloped_held": int((held & (fin(design) == FINISH_SLOPED)).sum()),
        "smooth": int(smooth.sum()),
        "smooth_left": int((smooth & ~tiled).sum()),
        "sloped": int(sloped.sum()),
        "sloped_left": int((sloped & ~slanted).sum()),
        "underside": int(underside.sum()),
        "underside_left": int((underside & ~slanted).sum()),
        "inverted": Counter(p.part for p in build.parts if kind(catalog, p) == "slope_inverted"),
        "slopes": Counter(
            p.part for p in build.parts if kind(catalog, p) == "slope" and p not in details
        ),
        "tiles": sum(1 for p in build.parts if kind(catalog, p) == "tile" and p not in details),
    }


def run(design: Design, catalog, build: Build | None = None):
    before = build if build is not None else solve(design, catalog)
    # an earlier pass's note and a fingerprint, which the result must carry over
    before = replace(
        before,
        notes=[*before.notes, "Made buildable: nothing needed changing."],
        design_id=before.design_id or "fingerprint-0001",
    )
    snapshot = list(before.parts)
    after = finish(before, design, catalog)
    assert before.parts == snapshot, "the input Build was changed"
    return before, after, assert_finished(before, after, design, catalog)


def has_stud(build: Build, catalog, x: int, y: int, z: int) -> bool:
    """True if the part covering (x, y, z) has its top there with a stud at (x, y)."""
    occ = occupancy(build, catalog)[0]
    i = int(occ[x, y, z])
    p = build.parts[i]
    return p.z + catalog.parts[p.part].h - 1 == z and (x, y) in catalog.stud_cells(p)


def staircase(
    downhill: tuple[int, int], rise: int, steps: int = 4, width: int = 2, colour=None, base=3
):
    """Steps of one stud rising ``rise`` plates each, then a two-stud landing at the top.

    The stairs stand on a ``base`` plates thick (a slope on the ground with nothing above it
    would be a loose part). The steps' open cells are marked sloped; the landing keeps its
    studs. ``downhill`` is the grid direction the stairs go down towards.
    """
    n = steps + 2
    h = np.array([base + rise * (min(k, steps) + 1) for k in range(n)])  # rising along +x
    heights = np.repeat(h[:, None], width, axis=1)
    if downhill == (1, 0):
        heights = heights[::-1, :]
    elif downhill in ((0, -1), (0, 1)):
        heights = heights.T
        if downhill == (0, 1):
            heights = heights[:, ::-1]
    design = from_heights(heights, colour=colour or DEFAULT_COLOUR)
    stepped = heights < heights.max()
    opened = open_mask(design) & stepped[:, :, None]
    fin(design)[opened] = FINISH_SLOPED
    return design


def pitched_roof(span: int = 8, length: int = 6) -> Design:
    """A triangular prism lying along y: rises one brick per stud from both eaves."""
    h = np.array([3 * (min(k, span - 1 - k) + 1) for k in range(span)])
    return from_heights(np.repeat(h[:, None], length, axis=1))


# ---- tiles ------------------------------------------------------------------------------------


def test_flat_slab_becomes_all_tiles(catalog):
    design = mark_open(design_of(np.ones((4, 4, 1), dtype=bool)), FINISH_SMOOTH)
    before, after, c = run(design, catalog)
    assert all(kind(catalog, p) == "tile" for p in after.parts)
    assert c["smooth_left"] == 0 and c["smooth"] == 16
    assert len(after.parts) == len(before.parts)  # one tile per plate, the same size
    assert after.notes[-1].startswith(f"Finishing placed {len(after.parts)} tiles, 0 slopes")


def test_a_loose_plate_with_no_tile_of_its_size_keeps_its_studs(catalog):
    """A 2x6 plate standing alone would come apart into two tiles: more pieces, so no."""
    design = mark_open(design_of(np.ones((6, 2, 1), dtype=bool)), FINISH_SMOOTH)
    build = Build(shape=design.shape, parts=[Placement("3795", DEFAULT_COLOUR, 0, 0, 0, 0, 1)])
    assert catalog.find("tile", 6, 2) is None
    _, after, c = run(design, catalog, build)
    assert after.parts == build.parts and c["smooth_left"] == 12


def test_solid_box_top_bricks_become_two_plates_and_a_tile(catalog):
    design = mark_open(shapes.box(6, 4, 2), FINISH_SMOOTH)
    before, after, c = run(design, catalog)
    assert c["smooth_left"] == 0
    occ = occupancy(after, catalog)[0]
    for z, want in ((3, "plate"), (4, "plate"), (5, "tile")):
        layer = {int(i) for i in np.unique(occ[:, :, z])}
        assert {kind(catalog, after.parts[i]) for i in layer} == {want}, z
    # the lower course keeps its bricks
    assert {kind(catalog, after.parts[int(i)]) for i in np.unique(occ[:, :, 0])} == {"brick"}
    # largest tiles: no 1x1 tiles on a plain 6x4 top
    assert all(p.part != "3070b" for p in after.parts)


def test_only_open_cells_of_a_partly_covered_top_get_tiles(catalog):
    filled = np.zeros((4, 4, 6), dtype=bool)
    filled[:, :, :3] = True
    filled[2:4, 2:4, 3:6] = True  # a 2x2 brick standing on the corner
    design = mark_open(design_of(filled), FINISH_SMOOTH)
    fin(design)[2:4, 2:4, 2] = FINISH_SMOOTH  # covered cells marked smooth too: ignored
    before, after, c = run(design, catalog)
    assert c["smooth"] == 16 and c["smooth_left"] == 0
    occ = occupancy(after, catalog)[0]
    for x in (2, 3):
        for y in (2, 3):
            # a stud there, or the part goes on up into the 2x2 (merging may join them)
            p = after.parts[int(occ[x, y, 2])]
            assert kind(catalog, p) in ("brick", "plate"), "a covered cell got a tile"
            assert has_stud(after, catalog, x, y, 2) or p.z + catalog.parts[p.part].h - 1 > 2, (
                "the cells under the 2x2 lost their studs"
            )
    tiles = [p for p in after.parts if kind(catalog, p) == "tile"]
    assert sum(int(np.prod(catalog.footprint(p)[:2])) for p in tiles) == 16
    assert len(pieces(after, catalog)) == 1
    assert occ.max() >= 0


def test_tiles_respect_colours_and_never_use_the_grille(catalog):
    design = mark_open(shapes.striped(shapes.box(4, 4, 1), (RED, WHITE), 1), FINISH_SMOOTH)
    design.colors[:2, :, 2] = RED
    design.colors[2:, :, 2] = WHITE
    _, after, c = run(design, catalog)
    assert c["smooth_left"] == 0
    assert not any(p.part == "2412b" for p in after.parts)


# ---- slopes -----------------------------------------------------------------------------------


@pytest.mark.parametrize("downhill", DIRECTIONS)
def test_brick_staircase_gets_45_degree_slopes_facing_downhill(catalog, downhill):
    design = staircase(downhill, rise=3)
    _, after, c = run(design, catalog)
    slopes = [p for p in after.parts if kind(catalog, p) == "slope"]
    assert c["sloped"] == 8 and c["sloped_left"] == 0
    assert slopes and all(catalog.low_side(p) == downhill for p in slopes)
    assert all(catalog.parts[p.part].h == 3 for p in slopes), "a brick step takes 45-degree slopes"
    assert c["slopes"]["3039"] == 4, "two-wide steps take the two-wide slope"
    assert len(pieces(after, catalog)) == 1


@pytest.mark.parametrize("downhill", DIRECTIONS)
def test_two_plate_staircase_gets_slopes_facing_downhill(catalog, downhill):
    design = staircase(downhill, rise=2, steps=5)
    _, after, c = run(design, catalog)
    slopes = [p for p in after.parts if kind(catalog, p) == "slope"]
    assert c["sloped"] == 10 and c["sloped_left"] <= 2, c
    # where the slope facing down the stairs would leave parts hanging on one part, the
    # next best one may slope off the side instead: at most one such
    assert sum(catalog.low_side(p) != downhill for p in slopes) <= 1
    assert len(pieces(after, catalog)) == 1


@pytest.mark.parametrize("downhill", DIRECTIONS)
def test_one_plate_steps_take_cheese_slopes_where_they_hold(catalog, downhill):
    """One-plate steps, in a colour made only in cheese slopes. Each step's slope is two
    plates tall and so cuts through the plates the steps are built from, which overlap like
    shingles; it goes in only where the model still holds together, which here is everywhere,
    and where it leaves no new group of three parts hanging on one part, which here is all
    but one or two cells (the notes say which). The first two rows take the two-wide cheese
    slope facing down the stairs. The third row may slope off the side of the stairs instead
    (the side is a cliff, so the surface drops further there), but the middle row has steps
    on both sides and must face downhill."""
    design = staircase(downhill, rise=1, steps=4, width=3, colour=BRIGHT_LIGHT_YELLOW)
    before, after, c = run(design, catalog)
    assert c["sloped"] == 12 and c["sloped_left"] <= 2, c
    notes = reason_notes(before, after)
    assert sum(int(note.split()[0]) for note in notes) == c["sloped_left"]
    assert all("hanging on a single part" in n or "would come loose" in n for n in notes)
    slopes = [p for p in after.parts if kind(catalog, p) == "slope"]
    assert all(catalog.parts[p.part].h == 2 for p in slopes)
    two_wide = [p for p in slopes if p.part == "85984"]
    assert len(two_wide) == 4, "one two-wide cheese slope on each step"
    assert all(catalog.low_side(p) == downhill for p in two_wide)
    # every sloped cell of the middle row is the face of a slope facing down the stairs
    occ = occupancy(after, catalog)[0]
    sloped = np.argwhere(open_mask(design) & (fin(design) == FINISH_SLOPED))
    middle = [(x, y, z) for x, y, z in sloped if (y if downhill[0] else x) == 1]
    assert len(middle) == 4
    for x, y, z in middle:
        p = after.parts[int(occ[x, y, z])]
        assert kind(catalog, p) == "slope" and catalog.low_side(p) == downhill, (x, y, z, p)
    assert len(pieces(after, catalog)) == 1


def test_cheese_slope_on_a_brick_stands_on_a_plate(catalog):
    heights = np.array([[3], [6], [6]])  # one brick step down towards -x at x=0
    design = from_heights(heights)
    fin(design)[0, 0, 2] = FINISH_SLOPED
    # a 45-degree slope would fit here too; make it impossible by colour
    design.colors[1, 0, :] = WHITE
    _, after, c = run(design, catalog)
    assert c["sloped_left"] == 0
    (slope,) = [p for p in after.parts if kind(catalog, p) == "slope"]
    assert slope.part == "54200" and (slope.x, slope.y, slope.z) == (0, 0, 1)
    occ = occupancy(after, catalog)[0]
    assert kind(catalog, after.parts[int(occ[0, 0, 0])]) == "plate"


def test_pitched_roof_loses_its_staircase(catalog):
    design = mark_open(pitched_roof(8, 6), FINISH_SLOPED)
    _, after, c = run(design, catalog)
    slopes = [p for p in after.parts if kind(catalog, p) == "slope"]
    assert c["sloped"] == 48
    # every row but the ridge slopes; at the ridge one of the two rows carries the studs
    assert c["sloped_left"] <= 6
    for p in slopes:  # away from the ridge, except at the two open gable ends
        if p.y > 0 and p.y + catalog.footprint(p)[1] < 6:
            assert catalog.low_side(p) in ((-1, 0), (1, 0))
    print(f"pitched roof: {c['sloped'] - c['sloped_left']} of {c['sloped']} sloped cells slanted")


@pytest.mark.parametrize("diameter", [12, 16])
def test_sphere_with_every_open_cell_sloped(catalog, diameter):
    design = mark_open(shapes.sphere(diameter), FINISH_SLOPED)
    _, after, c = run(design, catalog)
    done = c["sloped"] - c["sloped_left"]
    assert done >= 0.75 * c["sloped"], c
    print(f"sphere {diameter}: {done} of {c['sloped']} sloped cells slanted")


def test_two_colours_meeting_on_a_slope(catalog):
    design = staircase((-1, 0), rise=3, steps=4, width=1)
    design.colors[design.colors[:, :, :] != EMPTY] = RED
    design.colors[2:, :, :][design.colors[2:, :, :] != EMPTY] = WHITE
    _, after, c = run(design, catalog)
    assert c["sloped_left"] == 0
    by_x = {p.x: p for p in after.parts if kind(catalog, p) == "slope"}
    # at x=1 a 45-degree slope would need white studs behind red: a red cheese slope instead
    assert by_x[1].part == "54200" and by_x[1].color == RED
    assert by_x[0].part == "3040b" and by_x[0].color == RED
    assert all(p.color == WHITE for x, p in by_x.items() if x >= 2)


def test_colour_without_the_slope_part_is_left_as_it_was(catalog):
    assert not catalog.exists("54200", NOUGAT) and catalog.exists("3005", NOUGAT)
    heights = np.array([[2], [3], [3]])  # one plate down towards -x: only 54200 would fit
    design = from_heights(heights, colour=NOUGAT)
    fin(design)[0, 0, 1] = FINISH_SLOPED
    before, after, c = run(design, catalog)
    assert c["sloped_left"] == 1
    assert sorted(map(repr, after.parts)) == sorted(map(repr, before.parts))
    assert after.notes[-1].startswith("1 cell marked sloped at x=0, y=0, z=1 got no slope")
    assert "54200" in after.notes[-1] and "is not made in Nougat" in after.notes[-1]


def test_colour_with_only_cheese_slopes_uses_them(catalog):
    for pid in ("3039", "3040b", "4286"):
        assert not catalog.exists(pid, BRIGHT_LIGHT_YELLOW)
    design = staircase((-1, 0), rise=3, colour=BRIGHT_LIGHT_YELLOW)
    _, after, c = run(design, catalog)
    assert c["sloped_left"] == 0
    assert set(c["slopes"]) <= {"85984", "54200"}
    assert all(p.color == BRIGHT_LIGHT_YELLOW for p in after.parts)


def test_slope_never_takes_a_smooth_cell_for_its_studs(catalog):
    # a 1x2 bar two bricks tall: x=0 sloped, x=1 smooth. A 3040b would fit, with its stud
    # on the smooth cell; a cheese slope and a tile give both cells what they want. (The
    # cheese slope, a plate and the tile then stand on the 1x2 plate left of the top brick:
    # that is still the one brick, standing on one brick as before, so it is no less sturdy.)
    design = from_heights(np.array([[6], [6]]))
    fin(design)[0, 0, 5] = FINISH_SLOPED
    fin(design)[1, 0, 5] = FINISH_SMOOTH
    _, after, c = run(design, catalog)
    assert c["smooth_left"] == 0 and c["sloped_left"] == 0
    assert c["slopes"] == Counter({"54200": 1})


def test_a_tile_of_the_same_size_replaces_a_whole_plate(catalog):
    """Two loose 3x2 plates side by side: the largest tile (2x4) would straddle them and
    leave a loose 2x2 plate, but a 3x2 tile on each keeps them as they were."""
    design = mark_open(design_of(np.ones((6, 2, 1), dtype=bool)), FINISH_SMOOTH)
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[Placement("3021", c, 0, 0, 0, 0, 1), Placement("3021", c, 3, 0, 0, 0, 1)],
    )
    _, after, counted = run(design, catalog, build)
    assert counted["smooth_left"] == 0
    assert sorted((p.part, p.x) for p in after.parts) == [("26603", 0), ("26603", 3)]


@pytest.mark.parametrize("shape", [(8, 8, 2), (16, 16, 2), (8, 16, 4)])
def test_thin_smooth_slab_becomes_all_large_tiles(catalog, shape):
    """Two plates thick: the top plates hold the bottom ones together, so the tiles that
    replace them must cross the same joints. The largest tiles straddle the top plates the
    wrong way and are refused; each top plate is then tiled on its own, lengthwise or across,
    instead of falling back to 1x1 tiles."""
    design = mark_open(design_of(np.ones(shape, dtype=bool)), FINISH_SMOOTH)
    before, after, c = run(design, catalog)
    assert c["smooth_left"] == 0, c
    assert not any(p.part == "3070b" for p in after.parts), "no 1x1 tiles on a plain slab"
    assert len(pieces(after, catalog)) == 1
    # the bottom layer is untouched where only plates are
    if shape[2] == 2:
        assert [p for p in after.parts if p.z == 0] == [p for p in before.parts if p.z == 0]


def test_a_tile_refused_whole_still_takes_its_cells_one_by_one(catalog):
    """The 1x3 plate on top joins the 1x2 plate under its left end to the 1x1 plate under its
    right end, which carries a plate above. Tiles over its two open cells would leave the
    right end hanging from nothing, but a single 1x1 tile on the far left keeps a 1x2 plate
    across the joint."""
    filled = np.zeros((3, 1, 3), dtype=bool)
    filled[:, 0, 0:2] = True
    filled[2, 0, 2] = True
    design = design_of(filled)
    fin(design)[0:2, 0, 1] = FINISH_SMOOTH
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[
            Placement("3023b", c, 0, 0, 0, 0, 1),
            Placement("3024", c, 2, 0, 0, 0, 1),
            Placement("3623", c, 0, 0, 1, 0, 2),
            Placement("3024", c, 2, 0, 2, 0, 3),
        ],
    )
    assert catalog.footprint(build.parts[2])[:2] == (3, 1)
    _, after, counted = run(design, catalog, build)
    tiles = [p for p in after.parts if kind(catalog, p) == "tile"]
    assert [(p.part, p.x) for p in tiles] == [("3070b", 0)]
    assert counted["smooth_left"] == 1
    assert len(pieces(after, catalog)) == 1


def test_a_refused_slope_is_tried_again_once_its_neighbour_is_in(catalog):
    """Two 45-degree slopes side by side on a 2x2 tower. The first one tried alone would cut
    the brick at the back loose; with its neighbour in place it holds."""
    shape = (2, 2, 6)
    c = NOUGAT
    parts = [
        Placement("3004", c, 0, 0, 0, 0, 1),
        Placement("3023b", c, 0, 1, 1, 0, 2),
        Placement("3023b", c, 0, 1, 2, 0, 3),
        Placement("3005", c, 1, 1, 3, 0, 4),
        Placement("3023b", c, 0, 0, 3, 90, 4),
        Placement("3024", c, 1, 0, 3, 0, 4),
        Placement("3024", c, 0, 1, 4, 0, 5),
    ]
    build = Build(shape=shape, parts=parts)
    colors = np.full(shape, EMPTY, dtype=np.int16)
    for p in parts:
        colors[catalog.cells(p)] = c
    design = Design(colors=colors)
    fin(design)[0:2, 0, 3] = FINISH_SLOPED
    _, after, counted = run(design, catalog, build)
    assert counted["sloped_left"] == 0
    slopes = sorted((p.part, p.x) for p in after.parts if kind(catalog, p) == "slope")
    assert slopes == [("3040b", 0), ("3040b", 1)]


def test_a_45_degree_slope_leaves_the_rest_of_the_brick_a_brick(catalog):
    design = from_heights(np.full((4, 2), 4))
    fin(design)[0, :, 3] = FINISH_SLOPED
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[Placement("3020", c, 0, 0, 0, 0, 1), Placement("3001", c, 0, 0, 1, 0, 2)],
    )
    assert catalog.footprint(build.parts[1])[:2] == (4, 2)
    _, after, counted = run(design, catalog, build)
    assert counted["sloped_left"] == 0
    rest = sorted((p.part, p.x, p.z) for p in after.parts if kind(catalog, p) != "slope")
    assert rest == [("3003", 2, 1), ("3020", 0, 0)], "two whole columns stay one 2x2 brick"
    assert counted["slopes"] == Counter({"3039": 1})


def test_a_cheese_slope_on_a_brick_keeps_a_whole_plate_at_its_bottom(catalog, monkeypatch):
    """Swapping a brick for plates keeps one plate the size of the brick at the bottom, so
    the brick's grip on what is under it is not split. (Merging afterwards may join the
    plates beside the slope into a 1 x 1 brick, which is just as sturdy by the measure; it is
    switched off here to see the swap itself.)"""
    without_merging(monkeypatch)
    design = from_heights(np.array([[4], [4]]))
    fin(design)[0, 0, 3] = FINISH_SLOPED
    fin(design)[1, 0, 3] = FINISH_STUDS
    design.colors[:, :, :] = BRIGHT_LIGHT_YELLOW  # cheese slopes only
    c = BRIGHT_LIGHT_YELLOW
    build = Build(
        shape=design.shape,
        parts=[Placement("3023b", c, 0, 0, 0, 0, 1), Placement("3004", c, 0, 0, 1, 0, 2)],
    )
    _, after, counted = run(design, catalog, build)
    assert counted["slopes"] == Counter({"54200": 1})
    occ = occupancy(after, catalog)[0]
    assert occ[0, 0, 1] == occ[1, 0, 1], "one plate under the slope and the column beside it"
    assert after.parts[int(occ[0, 0, 1])].part == "3023b"


@pytest.mark.parametrize("with_detail", [False, True])
def test_a_slope_never_faces_into_a_detail_part(catalog, with_detail):
    """A round brick standing on the lower step, right in front of the upper step's face."""
    design = from_heights(np.array([[3], [6], [6]]))
    fin(design)[1, 0, 5] = FINISH_SLOPED
    if with_detail:
        design.details = [Detail("3062b", RED, 0, 0, 3)]
    _, after, counted = run(design, catalog)
    slopes = [p for p in after.parts if kind(catalog, p) == "slope"]
    facing = [catalog.low_side(p) for p in slopes]
    if with_detail:
        assert (-1, 0) not in facing, "the slope would run into the round brick"
        assert any(p.part == "3062b" for p in after.parts)
    else:
        assert facing == [(-1, 0)] and counted["slopes"] == Counter({"3040b": 1})


# ---- details ----------------------------------------------------------------------------------


def slab_with(details: list[Detail], smooth: bool = False) -> Design:
    design = shapes.box(6, 6, 1)
    design.colors = np.pad(design.colors, ((0, 0), (0, 0), (0, 3)), constant_values=EMPTY)
    design.finish = np.zeros(design.colors.shape, dtype=np.uint8)
    design.details = list(details)
    if smooth:
        mark_open(design, FINISH_SMOOTH)
    return design


def test_round_tile_on_a_stud(catalog):
    design = slab_with([Detail("98138", RED, 2, 3, 3)])
    before, after, _ = run(design, catalog)
    assert after.parts[-1] == Placement("98138", RED, 2, 3, 3, 0, after.parts[-1].step)
    assert len(after.parts) == len(before.parts) + 1
    assert "1 detail part" in after.notes[-1]


def test_two_by_two_detail_on_four_studs(catalog):
    design = slab_with([Detail("14769", WHITE, 1, 1, 3)])
    _, after, _ = run(design, catalog)
    assert after.parts[-1].part == "14769"
    g = connection_graph(after, catalog)
    assert sum(d["studs"] for _, _, d in g.edges(len(after.parts) - 1, data=True)) == 4


def test_cheese_slope_as_a_detail(catalog):
    design = slab_with([Detail("54200", RED, 4, 4, 3, rot=90)])
    _, after, _ = run(design, catalog)
    p = after.parts[-1]
    assert (p.part, p.rot, p.x, p.y, p.z) == ("54200", 90, 4, 4, 3)


def test_a_detail_turned_by_a_float_from_json_gets_a_whole_number(catalog):
    design = slab_with([Detail("54200", RED, 4, 4, 3, rot=450.0)])  # ty: ignore[invalid-argument-type]
    _, after, _ = run(design, catalog)
    p = after.parts[-1]
    assert (p.part, p.rot) == ("54200", 90) and type(p.rot) is int


def test_detail_over_an_empty_cell_is_skipped_with_a_note(catalog):
    design = slab_with([Detail("98138", RED, 2, 2, 5)])  # floating two plates up
    before, after, _ = run(design, catalog)
    assert after.parts == before.parts
    assert after.notes[-1].startswith("Detail part 98138")
    assert "x=2, y=2, z=5" in after.notes[-1] and "nothing under it" in after.notes[-1]
    assert "Traceback" not in " ".join(after.notes)


def test_second_detail_in_the_same_cell_is_skipped(catalog):
    design = slab_with([Detail("98138", RED, 2, 2, 3), Detail("6141", WHITE, 2, 2, 3)])
    _, after, _ = run(design, catalog)
    assert [p.part for p in after.parts if p.z == 3] == ["98138"]
    assert "6141" in after.notes[-1] and "earlier detail" in after.notes[-1]


def test_detail_wins_over_a_smooth_cell_which_keeps_its_stud(catalog):
    design = slab_with([Detail("98138", RED, 2, 2, 3)], smooth=True)
    _, after, c = run(design, catalog)
    assert has_stud(after, catalog, 2, 2, 2)
    assert c["smooth"] == 35 and c["smooth_left"] == 0
    assert after.parts[-1].part == "98138"


def test_other_detail_mistakes_are_explained(catalog):
    design = slab_with(
        [
            Detail("nonsense", RED, 0, 0, 3),
            Detail("98138", 999, 0, 1, 3),
            Detail("98138", RED, 5, 5, 3, rot=45),
            Detail("6143", RED, 5, 5, 3),  # 2x2 sticks out of the 6x6 grid
            Detail("98138", RED, 1, 1, 1),  # inside the slab
        ]
    )
    before, after, _ = run(design, catalog)
    assert after.parts == before.parts
    text = after.notes[len(before.notes) + 1 :]
    assert len(text) == 5
    assert "not a part in the parts table" in text[0]
    assert "not made in" in text[1]
    assert "90" in text[2]
    assert "stick out" in text[3]
    assert "not empty" in text[4]


def test_details_come_last_in_steps_of_up_to_eight(catalog):
    details = [Detail("98138", RED, x, y, 3) for y in (0, 2, 4) for x in range(5)]
    design = slab_with(details)
    _, after, _ = run(design, catalog)
    placed = [p for p in after.parts if p.z == 3]
    assert len(placed) == 15
    assert Counter(p.step for p in placed).most_common(1)[0][1] <= 8


# ---- never worse ------------------------------------------------------------------------------


def bridge() -> tuple[Design, Build]:
    """Two one-stud towers joined only by a 1x4 plate, with a brick standing on it at x=1."""
    filled = np.zeros((4, 1, 7), dtype=bool)
    filled[0, 0, 0:3] = filled[3, 0, 0:3] = True
    filled[:, 0, 3] = True
    filled[1, 0, 4:7] = True
    design = design_of(filled)
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[
            Placement("3005", c, 0, 0, 0, 0, 1),
            Placement("3005", c, 3, 0, 0, 0, 1),
            Placement("3710", c, 0, 0, 3, 0, 2),
            Placement("3005", c, 1, 0, 4, 0, 3),
        ],
    )
    return design, build


def test_a_tile_that_would_cut_the_model_in_two_is_not_made(catalog):
    design, build = bridge()
    assert len(pieces(build, catalog)) == 1
    for x in (0, 2, 3):
        fin(design)[x, 0, 3] = FINISH_SMOOTH
    # what a careless pass would do: tiles over the open cells, a plate under the brick
    c = DEFAULT_COLOUR
    careless = Build(
        shape=build.shape,
        parts=[
            *build.parts[:2],
            Placement("3070b", c, 0, 0, 3),
            Placement("3024", c, 1, 0, 3),
            Placement("3069b", c, 2, 0, 3),
            build.parts[3],
        ],
    )
    assert len(pieces(careless, catalog)) == 3
    _, after, counted = run(design, catalog, build)
    assert counted["smooth_left"] == 3
    assert after.parts == build.parts


def test_a_slope_that_would_cut_the_model_in_two_gives_way_to_a_cheese_slope(catalog):
    filled = np.zeros((4, 1, 9), dtype=bool)
    filled[0:2, 0, 0:3] = True  # a 1x2 base
    filled[:, 0, 3:6] = True  # a 1x4 brick overhanging to x=3
    filled[3, 0, 6:9] = True  # a tower standing on the overhang
    design = design_of(filled)
    fin(design)[0, 0, 5] = FINISH_SLOPED
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[
            Placement("3004", c, 0, 0, 0, 0, 1),
            Placement("3010", c, 0, 0, 3, 0, 2),
            Placement("3005", c, 3, 0, 6, 0, 3),
        ],
    )
    _, after, counted = run(design, catalog, build)
    assert counted["sloped_left"] == 0
    assert counted["slopes"] == Counter({"54200": 1}), "the 45-degree slope would cut the tower off"
    assert len(pieces(after, catalog)) == 1


def test_new_parts_take_the_step_of_the_brick_they_replace(catalog):
    """A two-course box with a smooth top: the top bricks become plates and tiles in the
    top bricks' step; the lower course keeps its own."""
    design = mark_open(shapes.box(4, 2, 2), FINISH_SMOOTH)
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[Placement("3001", c, 0, 0, 0, 0, 1), Placement("3001", c, 0, 0, 3, 0, 2)],
    )
    _, after, counted = run(design, catalog, build)
    assert counted["smooth_left"] == 0
    assert after.parts[0] == build.parts[0]
    assert sorted((p.z, kind(catalog, p), p.step) for p in after.parts[1:]) == [
        (3, "plate", 2),
        (4, "plate", 2),
        (5, "tile", 2),
    ]


def test_a_slope_through_three_plates_takes_the_latest_step(catalog):
    """A 45-degree slope replaces three stacked 1x2 plates in steps 2, 3 and 4. It takes
    step 4, the latest, which comes after the white brick beside it (step 2)."""
    shape = (2, 2, 4)
    c = DEFAULT_COLOUR
    parts = [
        Placement("3022", c, 0, 0, 0, 0, 1),
        Placement("3023b", c, 0, 0, 1, 0, 2),
        Placement("3023b", c, 0, 0, 2, 0, 3),
        Placement("3023b", c, 0, 0, 3, 0, 4),
        Placement("3004", WHITE, 0, 1, 1, 0, 2),
    ]
    build = Build(shape=shape, parts=parts)
    colors = np.full(shape, EMPTY, dtype=np.int16)
    for p in parts:
        colors[catalog.cells(p)] = p.color
    design = Design(colors=colors)
    fin(design)[0, 0, 3] = FINISH_SLOPED
    _, after, counted = run(design, catalog, build)
    assert counted["slopes"] == Counter({"3040b": 1})
    by_part = {p.part: p.step for p in after.parts}
    assert by_part == {"3022": 1, "3004": 2, "3040b": 3}


def test_summary_sentence_counts_what_was_left(catalog):
    design, build = bridge()
    for x in (0, 2, 3):
        fin(design)[x, 0, 3] = FINISH_SMOOTH
    before, after, _ = run(design, catalog, build)
    assert after.notes == [
        *before.notes,
        "Finishing placed 0 tiles, 0 slopes and 0 detail parts.",
        "3 cells marked smooth in 2 places (x=2 to 3, y=0, z=3; x=0, y=0, z=3) kept their "
        "studs because a tile there would let go of parts that are held on only through these "
        "cells, so part of the model would come loose. Making that part of the model thicker, "
        "or joining it more firmly to the rest, could change that; otherwise leave studs there.",
    ]


# ---- notes: why cells were left as they were ----------------------------------------------------


def without_colour(catalog, kinds: tuple[str, ...], colour: int) -> Catalog:
    """A copy of the catalogue in which no part of these kinds is made in ``colour``."""
    parts = [
        dataclasses.replace(p, colours=p.colours - {colour}) if p.kind in kinds else p
        for p in catalog.parts.values()
    ]
    return Catalog(parts, catalog.colours.values())


def test_everything_done_gives_one_sentence(catalog):
    design = mark_open(design_of(np.ones((2, 2, 1), dtype=bool)), FINISH_SMOOTH)
    before, after, c = run(design, catalog)
    assert c["smooth_left"] == 0
    assert after.notes == [*before.notes, "Finishing placed 1 tile, 0 slopes and 0 detail parts."]


def test_why_a_detail_keeps_a_stud(catalog):
    design = slab_with([Detail("98138", RED, 2, 2, 3)], smooth=True)
    before, after, _ = run(design, catalog)
    assert reason_notes(before, after) == [
        "1 cell marked smooth at x=2, y=2, z=2 keeps its stud because a detail part stands on "
        "it; that is as it should be, nothing to change."
    ]


def test_why_a_flat_top_gets_no_slope(catalog):
    design = shapes.box(5, 5, 1)
    fin(design)[2, 2, 2] = FINISH_SLOPED
    before, after, _ = run(design, catalog)
    (note,) = reason_notes(before, after)
    assert note.startswith("1 cell marked sloped at x=2, y=2, z=2 got no slope because the ")
    assert "does not step down beside it" in note
    assert 'Mark it "smooth" for tiles, or "studs" to stop asking.' in note


def test_why_a_one_plate_step_is_too_small(catalog):
    """Nougat has 45-degree slopes, which need a step of two plates, but not the 1 x 1 cheese
    slope that would fit a step of one plate."""
    design = from_heights(np.array([[3], [4], [5], [5]]), colour=NOUGAT)
    fin(design)[1, 0, 3] = FINISH_SLOPED
    before, after, c = run(design, catalog)
    assert c["sloped_left"] == 1
    (note,) = reason_notes(before, after)
    assert note.startswith("1 cell marked sloped at x=1, y=0, z=3 got no slope because the step ")
    assert "too small for the slope parts made in Nougat" in note
    assert "1 x 1 cheese slope (54200) would fit that step, but it is not made in Nougat" in note
    assert "Make the step deeper" in note


def test_why_a_part_one_plate_thick_gets_no_slope(catalog):
    filled = np.zeros((3, 1, 3), dtype=bool)
    filled[0:2, 0, :] = True
    filled[2, 0, 2] = True  # one plate sticking out at the top
    design = design_of(filled)
    fin(design)[2, 0, 2] = FINISH_SLOPED
    before, after, c = run(design, catalog)
    assert c["sloped_left"] == 1
    (note,) = reason_notes(before, after)
    assert note.startswith("1 cell marked sloped at x=2, y=0, z=2 got no slope because the model")
    assert "too thin there" in note and "at least 2 plates tall" in note and "only 1" in note
    assert 'Make it thicker there, or mark it "smooth".' in note


def test_why_a_colour_gets_no_slope_or_tile(catalog):
    # the slope that would fit is not made in the colour (Nougat has no 54200)
    design = from_heights(np.array([[2], [3], [3]]), colour=NOUGAT)
    fin(design)[0, 0, 1] = FINISH_SLOPED
    before, after, _ = run(design, catalog)
    (note,) = reason_notes(before, after)
    assert note == (
        "1 cell marked sloped at x=0, y=0, z=1 got no slope because the slope that would fit "
        "there, a 1 x 1 cheese slope (54200), is not made in Nougat: a different colour there "
        "would allow one."
    )
    # no slope part at all, and no tile at all, in red (a made-up catalogue)
    trimmed = without_colour(catalog, ("slope", "tile"), RED)
    design = from_heights(np.array([[3, 3], [6, 6]]), colour=RED)
    fin(design)[0, :, 2] = FINISH_SLOPED
    fin(design)[1, :, 5] = FINISH_SMOOTH
    before, after, c = run(design, trimmed)
    assert c["sloped_left"] == 2 and c["smooth_left"] == 2
    assert sorted(reason_notes(before, after)) == [
        "2 cells marked sloped at x=0, y=0 to 1, z=2 got no slope because the slope that would "
        "fit there, a 2 x 2 45-degree slope (3039), is not made in Red: a different colour "
        "there would allow one.",
        "2 cells marked smooth at x=1, y=0 to 1, z=5 kept their studs because no tile that fits "
        "there is made in Red: a different colour there would allow one.",
    ]
    design = from_heights(np.array([[1], [3]]), colour=RED)  # nothing would fit in any colour
    fin(design)[0, 0, 0] = FINISH_SLOPED
    before, after, _ = run(design, trimmed)
    (note,) = reason_notes(before, after)
    assert note.startswith("1 cell marked sloped at x=0, y=0, z=0 got no slope because the model")
    assert "too thin" in note
    # nothing would fit in any colour either (see the round brick case below): just say so
    heights = np.full((3, 3), 6)
    heights[0, 1] = 3
    design = from_heights(heights, colour=RED)
    design.details = [Detail("3062b", RED, 0, 1, 3)]
    fin(design)[1, 1, 5] = FINISH_SLOPED
    before, after, _ = run(design, trimmed)
    assert reason_notes(before, after) == [
        "1 cell marked sloped at x=1, y=1, z=5 got no slope because no slope part is made in Red."
    ]


def test_why_a_slope_that_would_loosen_a_part_is_not_made(catalog):
    """A 1 x 2 plate holds a plate on each end. A cheese slope over the left end would take
    the 1 x 2 plate away, and the right-hand plate would come loose with its half."""
    design = design_of(np.ones((2, 1, 2), dtype=bool))
    fin(design)[0, 0, 1] = FINISH_SLOPED
    c = DEFAULT_COLOUR
    build = Build(
        shape=design.shape,
        parts=[
            Placement("3023b", c, 0, 0, 0, 0, 1),
            Placement("3024", c, 0, 0, 1, 0, 2),
            Placement("3024", c, 1, 0, 1, 0, 2),
        ],
    )
    before, after, counted = run(design, catalog, build)
    assert counted["sloped_left"] == 1 and after.parts == build.parts
    (note,) = reason_notes(before, after)
    assert note.startswith("1 cell marked sloped at x=0, y=0, z=1 got no slope because a slope ")
    assert "held on only through this cell" in note and "would come loose" in note
    assert "thicker" in note


def test_why_the_high_side_of_a_slope_keeps_its_stud(catalog):
    design = from_heights(np.array([[6], [6]]))
    fin(design)[:, 0, 5] = FINISH_SLOPED
    before, after, c = run(design, catalog)
    assert c["slopes"] == Counter({"3040b": 1}) and c["sloped_left"] == 1
    (note,) = reason_notes(before, after)
    assert re.match(r"1 cell marked sloped at x=[01], y=0, z=5 keeps its stud because it is ", note)
    assert "the high side of a slope placed next to it" in note and "nothing to change" in note


def test_why_a_slope_that_lost_out_to_its_neighbours_is_not_made(catalog):
    """At the top of a small ball the slopes that fit overlap each other; the ones placed
    first win and the cells left say so, rather than that nothing fits."""
    design = mark_open(shapes.sphere(8), FINISH_SLOPED)
    before, after, _ = run(design, catalog)
    notes = [n for n in reason_notes(before, after) if "overlap" in n]
    assert len(notes) == 1
    assert re.match(r"\d+ cells marked sloped at x=\d+ to \d+, y=\d+ to \d+, z=\d+", notes[0])
    assert "every slope that fits there would overlap a slope already placed beside" in notes[0]
    assert "nothing to change" in notes[0]


def test_why_nothing_fits_says_so_plainly(catalog):
    """The only open side of the cell is taken by a round brick standing beside it."""
    heights = np.full((3, 3), 6)
    heights[0, 1] = 3
    design = from_heights(heights)
    design.details = [Detail("3062b", RED, 0, 1, 3)]
    fin(design)[1, 1, 5] = FINISH_SLOPED
    before, after, c = run(design, catalog)
    assert c["sloped_left"] == 1
    assert reason_notes(before, after) == [
        "1 cell marked sloped at x=1, y=1, z=5 got no slope: no slope part fits there."
    ]


def test_three_reasons_at_once(catalog):
    """A slab three plates thick, its top plates 2 x 6 (no tile is that size), so a few of
    its smooth cells would have to be tiled in a way that leaves parts hanging on one part:
    three reasons, biggest first."""
    design = slab_with([Detail("98138", RED, 1, 1, 3)], smooth=True)
    fin(design)[4, 4, 2] = FINISH_SLOPED  # on the flat top
    fin(design)[3, 4, 2] = FINISH_SLOPED
    before, after, c = run(design, catalog)
    assert c["smooth_left"] == 3
    notes = reason_notes(before, after)
    assert len(notes) == 3
    assert notes[0].startswith("3 cells marked smooth at x=2 to 4, y=1, z=2 kept their studs ")
    assert "would leave up to 4 parts hanging on a single part" in notes[0]
    assert notes[1].startswith("2 cells marked sloped at x=3 to 4, y=4, z=2 got no slope because ")
    assert "does not step down beside them" in notes[1]
    assert notes[2].startswith("1 cell marked smooth at x=1, y=1, z=2 keeps its stud because a ")
    assert after.notes[len(before.notes)].startswith("Finishing placed ")


def test_at_most_six_reason_sentences(catalog):
    reasons = {
        ("sloped", finish_module._FLAT): [(x, 0, 0) for x in range(9)],
        ("sloped", finish_module._THIN, 2): [(x, 2, 0) for x in range(8)],
        ("smooth", finish_module._LOOSE): [(x, 4, 0) for x in range(7)],
        ("sloped", finish_module._LOOSE): [(x, 6, 0) for x in range(6)],
        ("smooth", finish_module._DETAIL): [(x, 8, 0) for x in range(5)],
        ("sloped", finish_module._STUD_ROW): [(0, 10, 0), (5, 10, 0)],
        ("sloped", finish_module._OTHER): [(0, 12, 0)],
        ("smooth", finish_module._OTHER): [(0, 14, 0), (0, 15, 0)],
    }
    notes = finish_module._reason_notes(reasons, catalog)
    assert len(notes) == 6
    assert [n.split(" cell")[0] for n in notes[:5]] == ["9", "8", "7", "6", "5"]
    assert notes[5] == "And 5 more cells in other places were left as they were."
    # places: one box for touching cells, then up to three boxes
    assert "at x=0 to 8, y=0, z=0 " in notes[0]
    far = {("sloped", finish_module._FLAT): [(x, 0, 0) for x in range(0, 10, 2)]}
    (note,) = finish_module._reason_notes(far, catalog)
    assert note.startswith(
        "5 cells marked sloped in 5 places (x=0, y=0, z=0; x=2, y=0, z=0; x=4, y=0, z=0; "
        "and 2 more places) got no slope"
    )


def without_merging(monkeypatch) -> None:
    """Switch off merging: the pass then gives what it gave before merging was added."""
    monkeypatch.setattr(finish_module, "_MERGE_ROUNDS", 0)


def without_the_sturdiness_rule(monkeypatch) -> None:
    """Switch off the stage 3 rule: the pass then works exactly as it did before it."""
    monkeypatch.setattr(finish_module._Sturdy, "check", lambda self, state, start, broad: None)
    monkeypatch.setattr(finish_module._Sturdy, "holds", lambda self, parts: True)


def no_undersides(cases: dict[str, list[tuple[Design, Build]]]) -> dict:
    """The cases with every underside cell marked sloped marked "studs" instead."""
    out: dict[str, list[tuple[Design, Build]]] = {}
    for name, group in cases.items():
        out[name] = []
        for design, build in group:
            plainer = copy.deepcopy(design)
            under = underside_mask(design) & (fin(design) == FINISH_SLOPED)
            fin(plainer)[under] = FINISH_STUDS
            out[name].append((plainer, build))
    return out


# The fingerprints of ``test_the_notes_change_nothing_in_the_build`` with inverted slopes
# (stage 4 addition on undersides): only the random blobs mark undersides sloped.
WITH_UNDERSIDES = {
    "unmerged": "b6196c2c4328c551",
    "unmerged, no rule": "48cac275d357020e",
    "merged": "55e8e727a12c3d35",
    "merged, no rule": "62b7bd5385c34675",
}


def test_the_notes_change_nothing_in_the_build(catalog, monkeypatch):
    """Finding the reasons must not change what the pass builds: these fingerprints of the
    parts (with their steps and order) were recorded before the reasons were added, and
    before the sturdiness rule, so they hold with the rule switched off; with it, the
    first set (recorded when the rule took its present form) holds. Both are of the pass
    with merging switched off (it came later and changes no tile or slope); the last two
    sets, with merging, were recorded when it was added (and the "shaped" ones again when
    merges were held to the rule's limit on new groups of 40 cells or more). They were
    recorded before inverted slopes too, so they hold for the cases with no underside cell
    marked sloped (byte for byte); the random blobs mark some, and their fingerprints with
    them are recorded in ``WITH_UNDERSIDES``."""
    full = mixed_cases(catalog)
    cases = no_undersides(full)
    blobs = full["blobs"]
    assert not any(
        (underside_mask(d) & (fin(d) == FINISH_SLOPED)).any() for g in cases.values() for d, _ in g
    )
    assert all(
        not (underside_mask(d) & (fin(d) == FINISH_SLOPED)).any()
        for d, _ in full["stairs"] + full["shaped"]
    )

    def blob_print() -> str:
        return parts_fingerprint([finish(build, design, catalog) for design, build in blobs])

    with monkeypatch.context() as m:
        without_merging(m)
        want = {
            "blobs": "4065d63c1a5f67d1",
            "stairs": "676fa78ad0305f1d",
            "shaped": "37f0220c77db87ab",
        }
        for name, group in cases.items():
            builds = [finish(build, design, catalog) for design, build in group]
            assert parts_fingerprint(builds) == want[name], name
        # and these cases do have tiles, slopes, details and cells left for every sort of reason
        notes = " ".join(n for b in builds for n in b.notes)
        assert "detail part stands on" in notes and "would come loose" in notes
        assert blob_print() == WITH_UNDERSIDES["unmerged"]
        without_the_sturdiness_rule(m)
        want = {
            "blobs": "cb27a5fdc520506e",
            "stairs": "a8f3dbbf410b6548",
            "shaped": "89ca68ebcee90301",
        }
        for name, group in cases.items():
            builds = [finish(build, design, catalog) for design, build in group]
            assert parts_fingerprint(builds) == want[name], name
        assert blob_print() == WITH_UNDERSIDES["unmerged, no rule"]
    want = {"blobs": "9975c0dfc0f3508a", "stairs": "6ed0b4d017052265", "shaped": "02621d56e12f83b7"}
    for name, group in cases.items():
        builds = [finish(build, design, catalog) for design, build in group]
        assert parts_fingerprint(builds) == want[name], name
    assert blob_print() == WITH_UNDERSIDES["merged"]
    without_the_sturdiness_rule(monkeypatch)
    want = {"blobs": "a4dfcb839870ddf1", "stairs": "5e3974e110b7e9c4", "shaped": "4170c57cad16e362"}
    for name, group in cases.items():
        builds = [finish(build, design, catalog) for design, build in group]
        assert parts_fingerprint(builds) == want[name], name
    assert blob_print() == WITH_UNDERSIDES["merged, no rule"]
    # the blobs do get inverted slopes
    assert any(
        kind(catalog, p) == "slope_inverted"
        for design, build in blobs
        for p in finish(build, design, catalog).parts
    )


def test_a_swap_may_not_trade_a_small_weak_spot_for_a_new_heavy_one():
    """Counted as the checks count them (in the build's own parts), the input had one lone
    link of 40 cells or more (89 cells, its parts 0 and 1 hanging). A finished build with a
    second one, 45 cells, keeps the old two numbers (no heavier than 89, no more groups) but
    has two of 40 cells or more: the new one breaks the rule. One under 40 cells, or a new
    heavy one that replaced the input's, does not."""
    from bricksnap.connect import LoneLink

    rule = object.__new__(finish_module._Sturdy)
    originals = [(n,) for n in range(6)]  # each part stands for the input part it was
    rule.most, rule.count, rule.known = 89, 3, set()
    rule.heavy = {frozenset({0, 1})}
    old = LoneLink(2, 9, None, False, 1, (0, 1), 89)
    new = LoneLink(2, 9, None, False, 1, (2, 3), 45)
    small = LoneLink(2, 9, None, False, 1, (4, 5), 39)
    assert finish_module._HEAVY_CELLS == 40
    assert rule._offenders({}, [old], originals) == {}
    traded = rule._offenders({}, [old, new], originals)
    assert [g[2] for g in traded.values()] == [new]
    assert rule._offenders({}, [old, small], originals) == {}
    assert rule._offenders({}, [new], originals) == {}


def test_nothing_changes_where_no_swap_threatens_sturdiness(catalog, monkeypatch):
    """Where the pass without the rule already leaves the build as sturdy as the rule asks
    (checked here, before merging), the rule changes nothing: the same parts, order and
    steps, merged the same way."""
    cases = [case for group in mixed_cases(catalog).values() for case in group]
    with monkeypatch.context() as m:
        without_the_sturdiness_rule(m)
        merged = [finish(build, design, catalog) for design, build in cases]
        without_merging(m)
        plain = [finish(build, design, catalog) for design, build in cases]
    calm = 0
    for (design, build), was, joined in zip(cases, plain, merged, strict=True):
        try:
            assert_no_less_sturdy(build, was, design, catalog)
        except AssertionError:
            continue  # the rule has something to refuse here
        calm += 1
        assert finish(build, design, catalog).parts == joined.parts
        with monkeypatch.context() as m:
            without_merging(m)
            assert finish(build, design, catalog).parts == was.parts
    assert 10 <= calm < len(cases), (calm, len(cases))


def test_nothing_to_do_gives_back_the_same_parts(catalog):
    design = shapes.sphere(8)
    fin(design)[4, 4, 10] = FINISH_SMOOTH  # buried deep inside: not open
    before = solve(design, catalog)
    before.notes = ["made buildable"]
    after = finish(before, design, catalog)
    assert after.parts == before.parts
    assert after.notes == ["made buildable"]
    assert after.report is None and after.shape == before.shape
    assert after.design_id == before.design_id


def test_does_not_change_its_input_and_is_deterministic(catalog):
    design = mark_open(shapes.sphere(10), FINISH_SLOPED)
    build = solve(design, catalog)
    copy = Build.from_json(build.to_json())
    a = finish(build, design, catalog)
    b = finish(build, design, catalog)
    assert build.to_json() == copy.to_json()
    assert a.to_json() == b.to_json()


def random_blob(rng: np.random.Generator) -> Design:
    nx_, ny_, nz_ = (int(v) for v in rng.integers([3, 3, 4], [8, 8, 13]))
    noise = rng.random((nx_, ny_, nz_))
    for axis in range(3):
        noise = (noise + np.roll(noise, 1, axis) + np.roll(noise, -1, axis)) / 3
    filled = noise > np.quantile(noise, rng.uniform(0.25, 0.6))
    filled[:, :, 0] |= rng.random((nx_, ny_)) < 0.5
    colours = rng.choice([DEFAULT_COLOUR, RED, WHITE, BRIGHT_LIGHT_YELLOW, NOUGAT], size=2)
    colors = np.where(rng.random(filled.shape) < 0.8, colours[0], colours[1])
    design = Design(colors=np.where(filled, colors, EMPTY).astype(np.int16))
    design.finish = rng.choice(
        [FINISH_STUDS, FINISH_SMOOTH, FINISH_SLOPED], size=filled.shape, p=[0.2, 0.3, 0.5]
    ).astype(np.uint8)
    for _ in range(int(rng.integers(0, 4))):
        part = str(rng.choice(["98138", "6141", "14769", "54200", "3062b", "4740"]))
        x, y, z = (int(rng.integers(0, n)) for n in filled.shape)
        design.details.append(Detail(part, int(colours[0]), x, y, z, int(rng.choice([0, 90]))))
    return design


def random_layout(design: Design, catalog, rng: np.random.Generator) -> Build:
    """A quick random tiling with bricks (full courses of one colour) and plates.

    It covers exactly the filled cells, like the layout solver, but in random rectangles
    and with no care for holding together, so the finishing pass meets every awkward case
    (the real solver takes about a second on a messy blob; this takes a millisecond).
    """
    filled = design.filled
    colors = design.colors
    nx_, ny_, nz_ = design.shape
    sizes = {
        k: [(p.sx, p.sz, p.id, 0) for p in catalog.of_kind(k)]
        + [(p.sz, p.sx, p.id, 90) for p in catalog.of_kind(k) if p.sx != p.sz]
        for k in ("brick", "plate")
    }
    taken = np.zeros(design.shape, dtype=bool)
    parts: list[Placement] = []
    for z0 in range(0, nz_, 3):
        course = [z for z in range(z0, min(z0 + 3, nz_))]
        brick = np.zeros((nx_, ny_), dtype=bool)
        if len(course) == 3:
            brick = filled[:, :, z0] & np.all(
                colors[:, :, z0 : z0 + 3] == colors[:, :, z0 : z0 + 1], axis=2
            )
        layers = [("brick", z0, brick)] + [("plate", z, filled[:, :, z] & ~brick) for z in course]
        for kind_, z, mask in layers:
            for x, y in zip(*np.nonzero(mask), strict=True):
                if taken[x, y, z]:
                    continue
                c = int(colors[x, y, z])
                options = list(sizes[kind_])
                rng.shuffle(options)
                options.sort(key=lambda o: o[0] * o[1] > 1)  # 1x1 last
                options = options[::-1]
                for w, d, pid, rot in options:
                    h = 3 if kind_ == "brick" else 1
                    sl = (slice(x, x + w), slice(y, y + d), slice(z, z + h))
                    if x + w > nx_ or y + d > ny_ or not catalog.exists(pid, c):
                        continue
                    if not (mask[x : x + w, y : y + d].all() and not taken[sl].any()):
                        continue
                    if not np.all(colors[sl] == c):
                        continue
                    taken[sl] = True
                    parts.append(Placement(pid, c, int(x), int(y), z, rot, z + 1))
                    break
    return Build(shape=design.shape, parts=parts)


def never_fall_back(why: str) -> None:
    raise AssertionError(f"the pass had to fall back on its safety net ({why})")


@pytest.mark.thorough
def test_random_blobs_keep_every_promise(catalog, monkeypatch):
    # the pass checks its own result and falls back to the input if it ever broke a promise
    # (section 5 or the sturdiness rule); here that must never be needed
    verify = finish_module._verify

    def strict(*args):
        assert verify(*args), "the pass had to fall back on its safety net"
        return True

    monkeypatch.setattr(finish_module, "_verify", strict)
    monkeypatch.setattr(finish_module, "_fell_back", never_fall_back)
    rng = np.random.default_rng(2026)
    totals = Counter()
    for n in range(300):
        design = random_blob(rng)
        # the real solver on a few, a quick random tiling on the rest
        build = solve(design, catalog) if n < 2 else random_layout(design, catalog, rng)
        _, after, c = run(design, catalog, build)
        totals["smooth"] += c["smooth"] - c["smooth_left"]
        totals["sloped"] += c["sloped"] - c["sloped_left"]
        totals["details"] += len(detail_parts(after, design))
    assert totals["smooth"] > 1000 and totals["sloped"] > 300 and totals["details"] > 20, totals


def mixed_cases(catalog) -> dict[str, list[tuple[Design, Build]]]:
    """Designs and builds of every sort, made without the layout solver (so a change there
    does not move them): random blobs, staircases of each kind, a roof, a sphere, the bridge,
    a slab with details and smooth cells around them."""
    rng = np.random.default_rng(77)
    blobs = []
    for _ in range(40):
        design = random_blob(rng)
        blobs.append((design, random_layout(design, catalog, rng)))
    stairs = []
    for downhill in DIRECTIONS:
        for rise, colour in ((3, None), (2, NOUGAT), (1, BRIGHT_LIGHT_YELLOW)):
            design = staircase(downhill, rise=rise, colour=colour)
            stairs.append((design, random_layout(design, catalog, rng)))
    shaped = []
    for design in (
        mark_open(pitched_roof(8, 6), FINISH_SLOPED),
        mark_open(shapes.sphere(12), FINISH_SLOPED),
        mark_open(shapes.box(6, 4, 2), FINISH_SMOOTH),
        slab_with([Detail("98138", RED, 2, 2, 3), Detail("14769", WHITE, 3, 3, 3)], smooth=True),
    ):
        shaped.append((design, random_layout(design, catalog, rng)))
    design, build = bridge()
    for x in (0, 2, 3):
        fin(design)[x, 0, 3] = FINISH_SMOOTH
    shaped.append((design, build))
    return {"blobs": blobs, "stairs": stairs, "shaped": shaped}


def parts_fingerprint(builds: list[Build]) -> str:
    # written as before parts had a face, so the recorded fingerprints still apply
    text = json.dumps([[tuple(plain(p).values()) for p in b.parts] for b in builds])
    return hashlib.sha256(text.encode()).hexdigest()[:16]


@pytest.mark.thorough
def test_speed_3000_parts(catalog):
    design = mark_open(shapes.sphere(36), FINISH_SLOPED)
    fin(design)[:18][fin(design)[:18] == FINISH_SLOPED] = FINISH_SMOOTH  # left half smooth
    build = solve(design, catalog)
    assert len(build.parts) >= 3000
    start = time.perf_counter()
    after = finish(build, design, catalog)
    elapsed = time.perf_counter() - start
    # about 3.3 s on the lead's machine (2 s before merging): the limit allows a slower or
    # busy one
    # (3.5 s measured in stage 4, with the larger measuring budget: the limit is about three
    # times that)
    assert elapsed < 11.0, f"{elapsed:.1f} s"
    c = assert_finished(build, after, design, catalog)
    assert c["tiles"] > 0 and sum(c["slopes"].values()) > 0


@pytest.mark.thorough
def test_speed_3000_parts_with_undersides(catalog):
    """The same sphere with its underside marked sloped too: the inverted slopes are measured
    on a budget, so the pass still takes about 4.3 s (3.2 s without them) on the lead's
    machine; the limit, as above, allows a slower or busy one."""
    design = mark_open(shapes.sphere(36), FINISH_SLOPED)
    fin(design)[:18][fin(design)[:18] == FINISH_SLOPED] = FINISH_SMOOTH
    fin(design)[underside_mask(design)] = FINISH_SLOPED
    build = solve(design, catalog)
    assert len(build.parts) >= 3000
    start = time.perf_counter()
    after = finish(build, design, catalog)
    elapsed = time.perf_counter() - start
    assert elapsed < 13.5, f"{elapsed:.1f} s"  # 4.4 s measured in stage 4: about three times
    c = assert_finished(build, after, design, catalog)
    assert sum(c["inverted"].values()) > 0


class CountingAdjacency(dict):
    """The working state's connection graph, counting how many parts a search looks at."""

    looked = 0

    def __getitem__(self, key):
        self.looked += 1
        return super().__getitem__(key)


def test_a_refusal_searches_only_the_piece_that_would_come_loose(catalog):
    """Whether a swap leaves the model in one piece is searched from every part involved at
    once, stopping as soon as one search runs out. On a large model a refusal then costs
    about as much as the small piece that would come loose, not the whole model."""
    design = mark_open(design_of(np.ones((40, 40, 2), dtype=bool)), FINISH_SMOOTH)
    build = solve(design, catalog)
    state = finish_module._State(build, design, catalog)
    assert len(state.adj) > 200
    adj = CountingAdjacency(state.adj)
    # a loose island of three parts (ids no real part has), joined only to each other
    adj[-1], adj[-2], adj[-3] = {-2}, {-1, -3}, {-2}
    state.adj = adj
    assert state._joined([{0}, {-1}]) is False
    assert adj.looked <= 8, adj.looked
    adj.looked = 0
    assert state._joined([{0}, {-3}, {-1}]) is False  # two of them meet, still loose
    assert adj.looked <= 8, adj.looked
    # two parts of the main piece are found together, with no need to search all of it
    adj.looked = 0
    neighbour = min(state.adj[0])
    assert state._joined([{0}, {neighbour}]) is True
    assert adj.looked <= 2, adj.looked
    far = max(i for i in range(len(build.parts)) if build.parts[i].z == 1)
    assert state._joined([{0}, {far}]) is True


@pytest.mark.thorough
def test_speed_thin_slab_3000_parts(catalog):
    """A smooth slab two plates thick, where many tiles are refused because they would
    loosen a plate: each refusal must be decided without searching the whole model. The
    input has no lone link at all, and tiles that split its 2 x 8 top plates easily leave a
    big part of the slab hanging on one part (before the sturdiness rule, 2,265 parts on
    one), so the rule refuses some: almost all of the top still gets tiles. The finishing
    takes about 4 s on the lead's machine: the limit allows a slower or busy one."""
    design = mark_open(design_of(np.ones((153, 153, 2), dtype=bool)), FINISH_SMOOTH)
    build = solve(design, catalog)
    assert len(build.parts) >= 3000
    start = time.perf_counter()
    after = finish(build, design, catalog)
    elapsed = time.perf_counter() - start
    assert elapsed < 12.0, f"{elapsed:.1f} s"  # 3.8 s measured in stage 4: about three times
    c = assert_finished(build, after, design, catalog)  # includes the sturdiness rule
    assert c["smooth_left"] <= 0.02 * c["smooth"], c["smooth_left"]


# ---- stage 3: never less sturdy ----------------------------------------------------------------


def column(middle_course: list[Placement]) -> tuple[Design, Build]:
    """A 1 x 2 column three bricks tall with a smooth top: a 1 x 2 brick on the ground, then
    the middle course, then a 1 x 2 brick on top."""
    design = mark_open(from_heights(np.array([[9], [9]])), FINISH_SMOOTH)
    c = DEFAULT_COLOUR
    parts = [Placement("3004", c, 0, 0, 0, 0, 1), *middle_course, Placement("3004", c, 0, 0, 6)]
    parts[-1] = replace(parts[-1], step=3)
    return design, Build(shape=design.shape, parts=parts)


def test_a_tile_on_a_brick_standing_on_one_brick_is_made(catalog):
    """The top brick stands on the middle brick alone. A tile on top means two plates and a
    tile there instead: three parts on the middle brick, and the measure counts that as a
    lone link where the input had none. But they are the top brick cut up, hanging on the
    same brick as before with the same 6 cells: splitting a brick does not count against a
    swap by itself, so the tile is made."""
    design, build = column([Placement("3004", DEFAULT_COLOUR, 0, 0, 3, 0, 2)])
    assert lone_links(build, catalog) == []
    _, after, counted = run(design, catalog, build)
    assert counted["smooth_left"] == 0 and counted["tiles"] == 1
    assert hanging_on_one_part(after, catalog) == 6  # cells of two plates and a tile
    assert len(lone_links(after, catalog)) == 1
    assert groups_as_input(after, catalog, build) == {}


BRICK_1X4 = "3010"


def tied(section: list[Placement]) -> tuple[Design, Build]:
    """Two sections tied together by two 1 x 4 bricks lying side by side on top.

    x runs 0..3 and y 0..1. On the left (x=0..1) two 2 x 2 bricks stand on the ground; on
    the right (x=2..3) ``section`` hangs at z=3..5 with nothing under it. On top (z=6..8) a
    nougat 1 x 4 brick at y=0 and a red one at y=1 each lie across both sections, so the
    section hangs on both. The cell at x=3, y=0, z=8 is marked sloped: in nougat only a
    1 x 2 45-degree slope fits there, and it cuts the nougat brick in two (a slope on the
    section, a 1 x 2 brick on the left), so the section then hangs on the red brick alone.
    """
    g = DEFAULT_COLOUR
    colors = np.full((4, 2, 9), EMPTY, dtype=np.int16)
    colors[0:2, :, 0:6] = g
    colors[2:4, :, 3:6] = g
    colors[:, 0, 6:9] = NOUGAT
    colors[:, 1, 6:9] = RED
    design = Design(colors=colors)
    design.finish = np.full(design.shape, FINISH_STUDS, dtype=np.uint8)
    design.finish[3, 0, 8] = FINISH_SLOPED
    parts = [
        Placement("3003", g, 0, 0, 0, 0, 1),
        Placement("3003", g, 0, 0, 3, 0, 2),
        *section,
        Placement(BRICK_1X4, NOUGAT, 0, 0, 6, 0, 3),
        Placement(BRICK_1X4, RED, 0, 1, 6, 0, 3),
    ]
    return design, Build(shape=design.shape, parts=parts)


def cut_in_two(build: Build) -> Build:
    """What a careless pass makes of ``tied``: the nougat brick cut by the slope."""
    rest = [p for p in build.parts if p.color != NOUGAT]
    return Build(
        shape=build.shape,
        parts=[
            *rest,
            Placement("3004", NOUGAT, 0, 0, 6, 0, 3),
            Placement("3040b", NOUGAT, 2, 0, 6, 90, 3),
        ],
    )


def test_a_slope_that_would_leave_a_section_hanging_on_one_part_is_not_made(catalog):
    """The section is three plates: cut the nougat brick and those three plates and the
    slope hang on the red brick alone (four of the input's parts: a new lone link), where
    they hung on two bricks before. So the slope is not made, and the note says why and
    where, counting the input's parts."""
    g = DEFAULT_COLOUR
    design, build = tied([Placement("3022", g, 2, 0, z, 0, 2) for z in (3, 4, 5)])
    careless = cut_in_two(build)
    red = careless.parts.index(Placement(BRICK_1X4, RED, 0, 1, 6, 0, 3))
    graph = connection_graph(careless, catalog)
    graph.remove_node(red)
    away = [
        c for c in nx.connected_components(graph) if not any(careless.parts[i].z == 0 for i in c)
    ]
    assert [len(c) for c in away] == [4]  # the three plates and the slope
    assert (
        len(groups_as_input(careless, catalog, build)) == len(groups_as_input(build, catalog)) + 1
    )
    # the pass
    before, after, counted = run(design, catalog, build)
    assert counted["sloped_left"] == 1 and after.parts == build.parts
    assert reason_notes(before, after) == [
        "1 cell marked sloped at x=3, y=0, z=8 got no slope because a slope there would leave "
        "4 parts hanging on a single part, so that part of the model would come off too "
        "easily. Making that part of the model thicker, or joining it more firmly to the "
        "rest, could change that; otherwise leave studs there."
    ]


def test_the_same_slope_is_made_where_the_section_is_one_brick(catalog):
    """The same, with the section one 2 x 2 brick: after the cut the brick and the slope hang
    on the red brick, but two parts are not a weak spot, so the slope is made."""
    design, build = tied([Placement("3003", DEFAULT_COLOUR, 2, 0, 3, 0, 2)])
    assert sturdiness_in_cells(cut_in_two(build), catalog, build) == sturdiness_in_cells(
        build, catalog
    )
    _, after, counted = run(design, catalog, build)
    assert counted["sloped_left"] == 0 and counted["slopes"] == Counter({"3040b": 1})
    assert sorted(map(dataclasses.astuple, after.parts)) == sorted(
        map(dataclasses.astuple, cut_in_two(build).parts)
    )


def test_the_same_tile_is_made_where_nothing_would_hang(catalog):
    """The same column with its middle course made of two 1 x 1 bricks: the plate at the
    bottom of the new top stands on both, so nothing hangs on a single part and the tile
    goes in."""
    c = DEFAULT_COLOUR
    design, build = column(
        [Placement("3005", c, 0, 0, 3, 0, 2), Placement("3005", c, 1, 0, 3, 0, 2)]
    )
    _, after, counted = run(design, catalog, build)
    assert counted["smooth_left"] == 0 and counted["tiles"] == 1
    assert hanging_on_one_part(after, catalog) == 0
    assert lone_links(after, catalog) == []


MODELS = Path(__file__).resolve().parent.parent / "samples" / "models"


def sample_builds(
    studs: int, directory, catalog, names: tuple[str, ...] = ()
) -> dict[str, tuple[Design, Build]]:
    """Every sample model (or those named) as the pipeline hands it to the finishing pass."""
    from bricksnap.buildable import make_buildable
    from bricksnap.pipeline import create_project

    out = {}
    for path in sorted(MODELS.iterdir()):
        if path.suffix not in (".glb", ".stl") or (names and path.stem not in names):
            continue
        name = f"{path.stem}{studs}"
        project = create_project(path, studs=studs, directory=directory, name=name)
        fixed = make_buildable(project.load_design(), catalog)
        fixed.build.notes = list(fixed.notes)
        out[path.stem] = (fixed.design, fixed.build)
    return out


class _ByStuds(dict):
    """Sample builds by size, each size made the first time a test asks for it."""

    def __init__(self, root, catalog) -> None:
        super().__init__()
        self.root, self.catalog = root, catalog

    def __missing__(self, studs: int) -> dict[str, tuple[Design, Build]]:
        self[studs] = sample_builds(studs, self.root, self.catalog)
        return self[studs]


@pytest.fixture(scope="module")
def samples(tmp_path_factory, catalog) -> dict[int, dict[str, tuple[Design, Build]]]:
    """At 12 and 16 studs; the 12-stud ones are made only when asked for (by the thorough
    run), so the quick run does not pay for them."""
    return _ByStuds(tmp_path_factory.mktemp("samples"), catalog)


def test_the_pawn_is_no_less_sturdy_after_finishing(catalog, samples):
    """The case that started this: at 16 studs finishing used to leave 48 parts (170 cells)
    hanging on one 2 x 2 plate, where the solver's own build had at most 6 (16 cells).

    The rule is about the heaviest weak spot and the number of them, not each one: a weak
    spot lighter than the input's heaviest may grow. Checked here also from the connection
    graph alone, seen as the input's parts: no single part of the result carries more than
    the input's heaviest weak spot. (With the coverage fill one 2 x 4 brick of the head
    carries 20 cells after finishing, 14 before: slopes cut the two 1 x 2 bricks that
    straddle it and its neighbour, and their outer halves now stand on it alone; the
    heaviest weak spot is 24 cells, 33 before. Merging, added later, makes that 25 cells and
    23 weak spots 6, seen as the input's parts, and no part then carries more than 10.)"""
    design, build = samples[16]["pawn"]
    before, after, counted = run(design, catalog, build)
    most0, count0 = sturdiness_in_cells(build, catalog)
    most1, count1 = sturdiness_in_cells(after, catalog, build)
    assert most1 <= most0 and count1 <= count0
    assert hanging_on_one_part(build, catalog) <= most0
    assert hanging_on_one_part(after, catalog, build) <= most0
    assert sum(counted["slopes"].values()) >= 40, "the pawn keeps most of its slopes"


# Fingerprints of the finished parts of the samples (16 studs) that no swap made less
# sturdy, recorded before the rule was added: the rule must leave them exactly as they were.
# They depend on the voxeliser, the solver and the make-buildable pass too.
# Recorded again for the coverage fill with the pass as it was before the rule (360ac0d).
# The same with merging switched off; and with it, recorded when merging was added (the
# bottle's and the cat's again when the solver's sturdiness step got more work: their layouts
# changed).
UNCHANGED_AT_16 = {"bottle": "d466da8574c8370c", "cat": "918511820b46e859"}
MERGED_AT_16 = {"bottle": "96e3dcdc4bffecda", "cat": "7be2b60f5a723ff5"}


# every sample is a thorough sweep; the pawn test below is its quick representative
@pytest.mark.thorough
@pytest.mark.parametrize("studs", [12, 16])
def test_every_sample_is_no_less_sturdy_after_finishing(catalog, samples, monkeypatch, studs):
    for name, (design, build) in samples[studs].items():
        _, after, _ = run(design, catalog, build)  # run checks the rule, among the rest
        with monkeypatch.context() as m:
            without_the_sturdiness_rule(m)
            joined = finish(build, design, catalog)
            without_merging(m)
            was = finish(build, design, catalog)
        try:
            assert_no_less_sturdy(build, was, design, catalog)
        except AssertionError:
            continue  # the rule had something to refuse in this model
        assert after.parts == joined.parts, name
        if studs == 16 and name in MERGED_AT_16:
            text = json.dumps([tuple(plain(p).values()) for p in after.parts])
            assert hashlib.sha256(text.encode()).hexdigest()[:16] == MERGED_AT_16[name], name
        if studs == 16 and name in UNCHANGED_AT_16:
            text = json.dumps([tuple(plain(p).values()) for p in was.parts])
            assert hashlib.sha256(text.encode()).hexdigest()[:16] == UNCHANGED_AT_16[name], name


def test_the_rule_holds_also_when_judged_in_rounds(catalog, samples, monkeypatch):
    """The swaps to blame are found from the weak spots and refused, in rounds, and then
    tried again one by one while the measuring budget lasts. With no budget at all the
    rounds' refusals stand: the rule must hold that way too."""
    monkeypatch.setattr(finish_module, "_MEASURE_BUDGET", 0)
    for design, build in samples[16].values():
        run(design, catalog, build)
    rng = np.random.default_rng(7)
    for _ in range(60):
        design = random_blob(rng)
        layout = random_layout(design, catalog, rng)
        # its steps are z + 1, so a level with no part leaves a gap the solver never leaves
        dense = {s: n + 1 for n, s in enumerate(sorted({p.step for p in layout.parts}))}
        layout.parts = [replace(p, step=dense[p.step]) for p in layout.parts]
        run(design, catalog, layout)


def test_the_quick_measure_is_the_shared_measure(catalog, samples, monkeypatch):
    """While it works the pass measures from its own cells; that must give exactly what
    ``connect.lone_links`` gives for the same parts in the same order."""
    measure = finish_module._Sturdy._measure
    seen = []

    def compare(self, state):
        ids, parts, links = measure(self, state)
        assert links == lone_links(Build(shape=self.shape, parts=parts), catalog)
        seen.append(len(links))
        return ids, parts, links

    monkeypatch.setattr(finish_module._Sturdy, "_measure", compare)
    for name in ("pawn", "duck"):
        design, build = samples[16][name]
        finish(build, design, catalog)
    rng = np.random.default_rng(11)
    for _ in range(40):
        design = random_blob(rng)
        finish(random_layout(design, catalog, rng), design, catalog)
    assert len(seen) > 50 and max(seen) > 0


def test_the_number_in_the_note_is_what_the_refused_swap_leaves(catalog, samples, monkeypatch):
    """A swap refused by the rule is noted with how many parts it would leave hanging on one
    part: the largest of the groups the swap itself made or changed (worked out here from the
    build before and after it; the build before it kept the rule, so one of them broke it),
    never a weak spot elsewhere that earlier swaps changed."""
    keeps = finish_module._Sturdy.keeps
    check = finish_module._Sturdy.check
    restore = finish_module._State.restore
    last: list = [None]
    seen = []

    def judged(self, state, key):
        parts = [*state.final_parts(), *self.details]
        budget = self.budget
        ok = keeps(self, state, key)
        if ok:
            last[0] = parts
        elif self.budget < budget and last[0] is not None:  # measured, after a known state
            seen.append((self, last[0], parts, self.hanging))
        return ok

    def forget(original):
        def wrapped(*args, **kwargs):
            last[0] = None
            return original(*args, **kwargs)

        return wrapped

    monkeypatch.setattr(finish_module._Sturdy, "keeps", judged)
    monkeypatch.setattr(finish_module._Sturdy, "check", forget(check))
    monkeypatch.setattr(finish_module._State, "restore", forget(restore))
    for name in ("duck", "teapot", "pawn", "pineapple", "knight"):
        design, build = samples[16][name]
        finish(build, design, catalog)
    assert len(seen) >= 10, len(seen)
    for guard, prev, now, said in seen:
        before = Build(shape=guard.shape, parts=list(guard.input))
        base = Build(shape=guard.shape, parts=[*guard.input, *guard.details])
        input_groups = groups_as_input(base, catalog, before)
        most = max((cells for _, cells in input_groups.values()), default=0)
        groups = groups_as_input(Build(shape=guard.shape, parts=now), catalog, before)
        old = groups_as_input(Build(shape=guard.shape, parts=prev), catalog, before)
        heavy0 = heavy_as_checks(base, catalog, before)
        heavy_old = heavy_as_checks(Build(shape=guard.shape, parts=prev), catalog, before)
        heavy_now = heavy_as_checks(Build(shape=guard.shape, parts=now), catalog, before)
        assert max((c for _, c in old.values()), default=0) <= most
        assert len(old) <= len(input_groups), "the build before the swap kept the rule"
        assert heavy_old <= heavy0, "the build before the swap kept the rule"
        assert (
            max((c for _, c in groups.values()), default=0) > most
            or len(groups) > len(input_groups)
            or heavy_now > heavy0
        ), "the swap broke the rule"
        made = [n for held, (n, _) in groups.items() if held not in old]
        if made:  # (a swap that broke only the 40-cell part may have made no new group)
            assert said == max(made), (said, sorted(made))


def test_a_part_sticking_out_of_the_grid_does_not_stop_the_pass(catalog, monkeypatch):
    """Parts the input already had problems with are left alone (section 4) and the rest is
    finished as usual. A part sticking out of the grid still holds the parts on its studs
    inside the grid: the pass must count that when it measures, or it believes the rule
    holds where it does not and has to throw all its work away at the end."""
    monkeypatch.setattr(finish_module, "_fell_back", never_fall_back)
    rng = np.random.default_rng(5)
    placed = 0
    for _ in range(60):
        design = random_blob(rng)
        build = random_layout(design, catalog, rng)
        colour = build.parts[0].color if build.parts else DEFAULT_COLOUR
        build.parts.append(Placement("3001", colour, design.shape[0] - 1, 0, 0, 0, 1))
        assert occupancy(build, catalog)[2] == [len(build.parts) - 1]
        after = finish(build, design, catalog)
        new = [p for p in after.parts if p not in build.parts]
        placed += sum(kind(catalog, p) in ("tile", "slope") for p in new)
        details = [p for p in detail_parts(after, design) if p not in build.parts]
        base = Build(shape=build.shape, parts=[*build.parts, *details])
        most0, count0 = sturdiness_in_cells(base, catalog, build)
        most1, count1 = sturdiness_in_cells(after, catalog, build)
        assert most1 <= most0 and count1 <= count0
    assert placed > 300, placed


@pytest.fixture(scope="module")
def samples_at_24(tmp_path_factory, catalog) -> dict[str, tuple[Design, Build]]:
    root = tmp_path_factory.mktemp("samples24")
    return sample_builds(24, root, catalog, names=("duck", "knight", "pineapple"))


@pytest.mark.thorough
def test_larger_builds_keep_what_the_rule_allows(catalog, samples_at_24, monkeypatch):
    """A class of swaps that breaks the rule is judged in rounds, refusing the swaps found
    from the weak spots, which refuses more than the rule needs; the swaps refused that way
    are then tried again one by one, measured, while the budget allows. At 24 studs the
    pass must keep nearly all the slopes it keeps with no limit on measuring (the rounds
    alone once kept 28 of 43 on the pineapple) wherever the budget let it try them all again,
    and a cell gets the note "a slope there would leave N parts hanging" only if its own swap
    was measured. Which builds the budget covers depends on the conversion: with the coverage
    fill the duck (1,088 parts) missed it by 4% in one class with a budget of 150,000 parts
    and kept 189 slopes of 225; at 200,000 it is covered."""
    measured: set[tuple[int, int, int]] = set()
    reasons: dict = {}
    afforded: list[bool] = []
    mark = finish_module._Sturdy._mark
    why_left = finish_module._why_left
    affords = finish_module._Sturdy.affords

    def judged(self, swaps, parts):
        afforded.append(affords(self, swaps, parts))
        return afforded[-1]

    def marked(self, key, load, how):
        if how == "measured":
            measured.update(c for q in key for c in finish_module._face_cells(catalog, q))
        return mark(self, key, load, how)

    def why(*args):
        why_left(*args)
        reasons.clear()
        reasons.update(args[-1])

    tried_all = []
    for name, (design, build) in samples_at_24.items():
        measured.clear()
        afforded.clear()
        with monkeypatch.context() as m:
            m.setattr(finish_module._Sturdy, "_mark", marked)
            m.setattr(finish_module._Sturdy, "affords", judged)
            m.setattr(finish_module, "_why_left", why)
            run(design, catalog, build)
            after = finish(build, design, catalog)
        with monkeypatch.context() as m:
            m.setattr(finish_module, "_MEASURE_BUDGET", 10**12)
            every = finish(build, design, catalog)
        got = sum(counts(after, design, catalog)["slopes"].values())
        want = sum(counts(every, design, catalog)["slopes"].values())
        if all(afforded):
            assert got >= 0.95 * want, (name, got, want)
            tried_all.append(name)
        said = {
            c for key, cells in reasons.items() if key[1] == finish_module._STURDY for c in cells
        }
        assert said <= measured, (name, sorted(said - measured)[:5])
    assert len(tried_all) >= 2 and "duck" in tried_all, tried_all


def test_the_designed_cat_keeps_its_tiles(catalog):
    """The cat in samples/projects, as the AI designer left it: tiles on bricks that carry two
    parts, and a tile on the brick under the tail, cut those bricks into plates and a tile
    that hang on the brick's own bottom plate. That is still the one brick, so it is no less
    sturdy, and every tile the pass made before the sturdiness rule (19) is made."""
    from bricksnap.buildable import make_buildable
    from bricksnap.project import Project

    project = Project(
        Path(__file__).resolve().parent.parent / "samples" / "projects" / "cat-designed"
    )
    fixed = make_buildable(project.load_design(), catalog)
    _, after, counted = run(fixed.design, catalog, fixed.build)
    assert counted["tiles"] == 19, counted
    assert not any("hanging on a single part" in note for note in after.notes)


def test_how_the_sturdiness_sentences_read(catalog):
    """Measured on its own, a refused swap gives its own number ("up to" when the cells of a
    sentence differ); refused in rounds and never measured on its own, the sentence says
    the number came from the others tried around it."""
    reasons = {
        ("sloped", finish_module._TOGETHER, 8, False): [(1, 2, 3), (1, 3, 3)],
        ("smooth", finish_module._STURDY, 4, True): [(5, 5, 5)],
    }
    advice = (
        "so that part of the model would come off too easily. Making that part of the model "
        "thicker, or joining it more firmly to the rest, could change that; otherwise leave "
        "studs there."
    )
    assert finish_module._reason_notes(reasons, catalog) == [
        "2 cells marked sloped at x=1, y=2 to 3, z=3 got no slope because a slope there, with "
        "the others tried around them at the same time, would leave up to 8 parts hanging on "
        f"a single part, {advice}",
        "1 cell marked smooth at x=5, y=5, z=5 kept its stud because a tile there would leave "
        f"4 parts hanging on a single part, {advice}",
    ]


# ---- stage 4: merging what the swaps leave ------------------------------------------------


INVERTED_PARTS = finish_module.INVERTED_SLOPE_PARTS


def shaped_parts(build: Build, catalog) -> Counter:
    """Every part that is not a plain brick or plate, as placed (steps aside)."""
    return Counter(
        (p.part, p.color, p.x, p.y, p.z, p.rot, p.face)
        for p in build.parts
        if kind(catalog, p) not in ("brick", "plate")
    )


def checks_weak_spots(build: Build, catalog) -> tuple[int, int]:
    """(heaviest weak spot in cells, how many), counted as the checks count them."""
    links = lone_links(build, catalog)
    return max((ln.cells for ln in links), default=0), len(links)


def test_merging_joins_the_remnants_of_a_sloped_sphere(catalog, monkeypatch):
    """The slopes of a sphere cut the bricks under them into smaller bricks and plates;
    merging joins them into fewer, larger ones, keeping every promise of the pass, every
    tile and slope where it was, and no weak spot heavier or more of them."""
    design = mark_open(shapes.sphere(12), FINISH_SLOPED)
    build = solve(design, catalog)
    with monkeypatch.context() as m:
        without_merging(m)
        unmerged = finish(build, design, catalog)
    _, after, _ = run(design, catalog, build)  # run checks every promise
    assert len(after.parts) < len(unmerged.parts) - 10, (len(after.parts), len(unmerged.parts))
    assert shaped_parts(after, catalog) == shaped_parts(unmerged, catalog)
    most, count = checks_weak_spots(after, catalog)
    most0, count0 = checks_weak_spots(unmerged, catalog)
    assert most <= most0 and count <= count0


def test_merging_needs_a_part_the_pass_made(catalog):
    """A build the swaps did not touch is left as the solver made it, even where two of its
    plates could be one (a flat top marked sloped: no slope fits)."""
    filled = np.zeros((4, 2, 1), dtype=bool)
    filled[:, :, 0] = True
    design = mark_open(design_of(filled), FINISH_SLOPED)
    c = int(design.colors[0, 0, 0])
    build = Build(
        shape=design.shape,
        parts=[Placement("3022", c, 0, 0, 0, 0, 1), Placement("3022", c, 2, 0, 0, 0, 1)],
    )
    assert finish(build, design, catalog).parts == build.parts


@pytest.mark.thorough
def test_merging_on_the_samples(catalog, samples, monkeypatch):
    """At 16 studs merging takes the duck under 450 parts (503 before it) and the eleven
    samples from 2,809 to about 2,400, moving no tile, slope or detail part, and leaving no
    model with a heavier weak spot or more of them, counted as the checks count. (Inverted
    slopes are placed after the merges, in the build the merges left, so with merging
    switched off they go elsewhere: they are left out of the comparison.)"""

    def on_top(build: Build) -> Counter:
        shaped = shaped_parts(build, catalog)
        return Counter({k: n for k, n in shaped.items() if k[0] not in INVERTED_PARTS})

    total = 0
    for name, (design, build) in samples[16].items():
        after = finish(build, design, catalog)
        with monkeypatch.context() as m:
            without_merging(m)
            unmerged = finish(build, design, catalog)
        assert len(after.parts) <= len(unmerged.parts), name
        assert on_top(after) == on_top(unmerged), name
        most, count = checks_weak_spots(after, catalog)
        most0, count0 = checks_weak_spots(unmerged, catalog)
        assert most <= most0 and count <= count0, (name, most, most0, count, count0)
        if name == "duck":
            assert len(after.parts) < 450, len(after.parts)
        total += len(after.parts)
    assert total < 2500, total


# ---- stage 4: sideways details ----------------------------------------------------------


def test_a_sideways_detail_is_put_on_the_side_stud_brick_after_it(catalog):
    from bricksnap.types import Detail

    colors = np.full((8, 6, 12), EMPTY, dtype=np.int16)
    colors[1:7, 1:5, :9] = 71
    finish_marks = np.zeros(colors.shape, dtype=np.uint8)
    finish_marks[:, :, 8] = FINISH_SMOOTH  # tiles on top, the pinned brick stays as it is
    design = Design(
        colors=colors, finish=finish_marks, details=[Detail("98138", 0, 2, 0, 3, 0, "front")]
    )
    pin = catalog.side_stud_brick("front", 71, 2, 1, 3)
    build = solve(design, catalog, pinned=[pin])
    out = finish(build, design, catalog)
    eye = [p for p in out.parts if p.part == "98138"]
    assert [(p.x, p.y, p.z, p.rot, p.face) for p in eye] == [(2, 0, 3, 0, "front")]
    brick = [p for p in out.parts if p.part == "87087"]
    assert [(p.x, p.y, p.z, p.rot) for p in brick] == [(2, 1, 3, 0)]
    assert eye[0].step > brick[0].step
    assert "1 detail part" in out.notes[0]
    g = connection_graph(out, catalog)
    i, j = out.parts.index(eye[0]), out.parts.index(brick[0])
    assert g.has_edge(i, j)


def test_a_sideways_detail_with_no_side_stud_behind_it_is_skipped_with_a_note(catalog):
    from bricksnap.types import Detail

    colors = np.full((8, 6, 12), EMPTY, dtype=np.int16)
    colors[1:7, 1:5, :9] = 71
    design = Design(colors=colors, details=[Detail("98138", 0, 2, 0, 3, 0, "front")])
    out = finish(solve(design, catalog), design, catalog)  # nothing pinned
    assert not [p for p in out.parts if p.part == "98138"]
    assert any(
        "at x=2, y=0, z=3 on the front face was not placed" in n and "no stud on that side" in n
        for n in out.notes
    )


def test_two_details_in_one_column_put_on_only_the_first(catalog):
    from bricksnap.types import Detail

    colors = np.full((8, 6, 12), EMPTY, dtype=np.int16)
    colors[1:7, 1:5, :9] = 71
    colors[1:7, 0, :3] = 71  # a ledge in front
    details = [Detail("98138", 0, 2, 0, 3, 0, "front"), Detail("98138", 4, 2, 0, 3)]
    design = Design(colors=colors, details=details)
    pin = catalog.side_stud_brick("front", 71, 2, 1, 3)
    out = finish(solve(design, catalog, pinned=[pin]), design, catalog)
    placed = [p for p in out.parts if p.part == "98138"]
    assert [p.face for p in placed] == ["front"]
    assert any("an earlier detail part already takes that space" in n for n in out.notes)
    design.details.reverse()
    out = finish(solve(design, catalog, pinned=[pin]), design, catalog)
    assert [p.face for p in out.parts if p.part == "98138"] == ["top"]
    assert any("on the front face was not placed: an earlier detail" in n for n in out.notes)


def test_a_smooth_top_on_a_side_stud_brick_says_why_it_keeps_its_stud(catalog):
    from bricksnap.types import Detail

    colors = np.full((8, 6, 12), EMPTY, dtype=np.int16)
    colors[1:7, 1:5, :9] = 71
    marks = np.zeros(colors.shape, dtype=np.uint8)
    marks[:, :, 8] = FINISH_SMOOTH
    design = Design(colors=colors, finish=marks, details=[Detail("98138", 0, 2, 0, 6, 0, "front")])
    pin = catalog.side_stud_brick("front", 71, 2, 1, 6)
    out = finish(solve(design, catalog, pinned=[pin]), design, catalog)
    assert [p for p in out.parts if p.part == "87087"]
    (note,) = [n for n in out.notes if "x=2, y=1, z=8" in n]
    assert (
        "top of a brick with a stud on its side (87087)" in note and "one brick course down" in note
    )


# ---- stage 4: inverted slopes under overhangs -----------------------------------------------


def overhang_cross(arm: int = 2, width: int = 2) -> Design:
    """A grey column standing on the ground with an arm of its own colour reaching out on
    each side a brick above the ground, all under a grey cap that holds them; the outer cells
    of each arm's underside are marked sloped (all but the cell next to the column)."""
    n = 2 + 2 * arm
    colors = np.full((n, n, 10), EMPTY, dtype=np.int16)
    lo, hi = arm, arm + 2
    colors[lo:hi, lo:hi, 0:9] = DEFAULT_COLOUR
    colors[:, :, 9] = DEFAULT_COLOUR
    across = slice(lo, lo + width)
    colors[0:lo, across, 3:9] = RED
    colors[hi:n, across, 3:9] = 1  # blue
    colors[across, 0:lo, 3:9] = 14  # yellow
    colors[across, hi:n, 3:9] = 2  # green
    design = Design(colors=colors)
    under = underside_mask(design)
    under[lo - 1 : hi + 1, lo - 1 : hi + 1] = False  # not next to the column
    fin(design)[under] = FINISH_SLOPED
    return design


@pytest.mark.parametrize(
    ("arm", "width", "part"), [(2, 2, "3660b"), (2, 1, "3665b"), (3, 1, "4287c")]
)
def test_inverted_slopes_go_under_an_overhang_on_every_side(catalog, arm, width, part):
    design = overhang_cross(arm, width)
    before, after, c = run(design, catalog)
    inverted = [p for p in after.parts if kind(catalog, p) == "slope_inverted"]
    assert sorted(p.part for p in inverted) == [part] * 4
    thin = {tuple(-v for v in catalog.low_side(p)) for p in inverted}
    assert thin == set(DIRECTIONS)  # each faces down and outwards, one on each side
    assert c["underside_left"] == 0
    assert after.notes[-1] == (
        "Finishing placed 0 tiles, 0 slopes, 4 inverted slopes and 0 detail parts."
    )


def test_an_inverted_slope_is_held_only_where_it_grips(catalog):
    """Nothing is under the slanted cells (they hold nothing below), and every part on its
    studs, the slanted cells' included, holds it: here the arm above, hung from the cap."""
    design = overhang_cross(2, 2)
    _, after, _ = run(design, catalog)
    g = connection_graph(after, catalog)
    occ = occupancy(after, catalog)[0]
    for i, p in enumerate(after.parts):
        if kind(catalog, p) != "slope_inverted":
            continue
        for x, y, z in cut_cells(catalog, p):
            assert occ[x, y, z - 1] < 0
        w, d, h = catalog.footprint(p)
        on_top = occ[p.x : p.x + w, p.y : p.y + d, p.z + h]
        above = {int(j) for j in np.unique(on_top) if j >= 0}
        assert above <= set(g.adj[i]) and above  # what stands on its studs holds it


def test_no_underside_marks_no_change(catalog):
    """With no underside cell marked sloped the pass gives exactly what it gave before inverted
    slopes existed: here, the build of the same Design with the marks taken off, which has
    none, and no count of inverted slopes in its note."""
    design = overhang_cross(2, 2)
    marks = mark_open(overhang_cross(2, 2), FINISH_SLOPED)
    fin(marks)[underside_mask(marks)] = FINISH_STUDS
    build = solve(design, catalog)
    out = finish(build, marks, catalog)
    assert not any(kind(catalog, p) == "slope_inverted" for p in out.parts)
    assert "inverted" not in " ".join(out.notes)
    plain_design = overhang_cross(2, 2)
    fin(plain_design)[...] = FINISH_STUDS
    same = finish(build, plain_design, catalog)
    assert same.parts == build.parts and same.notes == build.notes


def test_a_flat_bottom_marked_sloped_says_so(catalog):
    """A slab held up by a column, its whole underside marked sloped: the cells in the middle
    of a flat bottom get the note that the underside does not step up beside them."""
    colors = np.full((10, 10, 9), EMPTY, dtype=np.int16)
    colors[4:6, 4:6, 0:6] = RED
    colors[:, :, 6:9] = RED
    design = Design(colors=colors)
    fin(design)[underside_mask(design)] = FINISH_SLOPED
    _, after, c = run(design, catalog)
    notes = " ".join(after.notes)
    assert "marked sloped on the underside" in notes
    assert "the underside does not step up beside" in notes
    assert c["underside"] > 0


def test_an_inverted_slope_that_would_cut_parts_into_pieces_is_not_placed(catalog, monkeypatch):
    """At most one part more than it took out: with that limit at zero, none goes in where
    the bricks around it would be cut, and the note says why."""
    design = overhang_cross(2, 2)
    monkeypatch.setattr(finish_module, "_INVERTED_MOST_NEW", -10)
    _, after, c = run(design, catalog)
    assert not any(kind(catalog, p) == "slope_inverted" for p in after.parts)
    assert "cut the parts around it into more pieces" in " ".join(after.notes)


@pytest.mark.thorough
def test_inverted_slopes_never_add_a_weak_spot_on_the_samples(catalog, samples):
    """Counted as the checks count them, no sample has a heavier weak spot or more of them
    than with no underside marked sloped; the duck, the teapot and the pawn get inverted
    slopes; and no model needs more than a few more parts."""
    got = {}
    for name, (design, build) in samples[16].items():
        after = finish(build, design, catalog)
        plainer = copy.deepcopy(design)
        fin(plainer)[underside_mask(design) & (fin(design) == FINISH_SLOPED)] = FINISH_STUDS
        was = finish(build, plainer, catalog)
        most, count = checks_weak_spots(after, catalog)
        most0, count0 = checks_weak_spots(was, catalog)
        assert most <= most0 and count <= count0, (name, most, most0, count, count0)
        # the duck needs 8 more for its 16 (5 more for 15 before the solver's sturdiness step
        # got more work, on a build that ties more and so leaves fewer plates to merge)
        assert len(after.parts) <= len(was.parts) + 8, (name, len(after.parts), len(was.parts))
        got[name] = sum(1 for p in after.parts if kind(catalog, p) == "slope_inverted")
    assert got["duck"] >= 8 and got["teapot"] >= 4 and got["pawn"] >= 2, got


def _thin_there(name: str, studs: int, build: Build, link) -> bool:
    """The place where a sample model really is too thin to tie, as narrow as the one
    section it excuses (the bottle at 12 studs was excused here until the model came to sit
    where its build comes out best: see bricksnap/pipeline.py):

    - The pineapple at 24 studs, one leaf of its crown (at most 61 cells, in x 5 to 11, y 11
      and up, z 44 and up): a wall one cell thick joined to the crown along one row, with
      no cell of its colour beside it, so no part can give it a second hold (the
      make-buildable pass says so in its notes; the solver alone, with fifty times its work,
      still leaves 80 cells there). The crown's other leaves, which hung 89, 73, 49 and 41
      cells on single parts before the task on weak spots in thin models, are not excused.
    """
    p = build.parts[link.part]
    group = [p, *(build.parts[i] for i in link.members)]
    if (name, studs) == ("pineapple", 24):
        return link.cells <= 61 and all(5 <= q.x <= 11 and q.y >= 11 and q.z >= 44 for q in group)
    return False


@pytest.mark.thorough
def test_no_sample_hangs_forty_cells_on_one_part(catalog, samples, tmp_path_factory):
    """The task on weak spots in thin models: at 12, 16 and 24 studs, no finished sample has
    a section of 40 cells or more hanging on a single part or stud, except where the model
    really is that thin."""
    by_studs = {12: samples[12], 16: samples[16]}
    by_studs[24] = sample_builds(24, tmp_path_factory.mktemp("samples24all"), catalog)
    heavy = []
    for studs, builds in by_studs.items():
        assert len(builds) >= 11
        for name, (design, build) in builds.items():
            after = finish(build, design, catalog)
            for link in lone_links(after, catalog):
                if link.cells >= 40 and not _thin_there(name, studs, after, link):
                    heavy.append((name, studs, link.cells, after.parts[link.part]))
    assert heavy == []
