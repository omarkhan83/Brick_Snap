"""Cover free studs with flat parts: the builder's ``cap`` and ``skin`` tools (guide mode only;
``tools``) (research prototype, EXPERIMENTAL).

CONTRACT (tests in tests/test_lab_cap_skin.py)

The style guide asks for every upward face capped and every flank skinned (rules 1 and 3). With
``place`` that is dozens of exactly placed parts, so builders fell back to ``fill``, whose
stacked slabs read as old. These two do each technique in one call, deterministically, from the
parts' real data (``place.sockets``, ``validate.numbered_studs``) and the checker's own tests.

A stud is FREE when ``looks.studs`` calls it showing: no stud link of the checker to it and no
other part's filled body on it, over its tip or under whose underside it is.

- ``cap(text, colour, lines=None, box=None, use="tiles", keep=())``: the free studs that point
  up, of the parts on ``lines`` and/or with their base in ``box`` (``(lo, hi)`` in LDU; both
  given: studs meeting both), except those in ``keep`` (``(line, stud)``, numbered as
  ``part_info`` numbers them), grouped by height and stud grid. Each group is covered greedily,
  largest part first (area, then the wider, then the list's order), by ``TILES`` (or
  ``PLATES`` with ``use="plates"``), turned 0 or 1 quarter turn: a part goes where every one of
  its grid sockets lands on a free stud of the group not yet covered, and it fits: no stud of
  the model hits it and none of its studs hits the model (``validate._stud_hits``, both ways),
  and where its filled body and another's share ``IGNORE_OVERLAP`` or more the real shapes do
  not confirm it (``validate._really_overlap``). A stud left uncovered is reported with why (a
  part in the way, named by its line). The line of each new part is the one ``place`` would
  write for socket 1 on its anchor stud with that turn (``New.via``).
  With ``edges="curved"`` each group first gets curved slopes (``CURVES``: 15068 where two
  edge cells pair along the edge, else 11477; two plates tall, two studs deep) along every
  edge that ends in a DROP, sloping down and outward, but never where a curve's side would
  face a drop (its high half is open underneath for one plate at the sides, ``_side_open``):
  those edge cells stay flat, tiled and not lifted. An edge cell is one whose neighbour
  outward is not a stud of the group, has no stud of the model at that height, and has no
  part's filled body beside the cover's height there (``_drop``); a run of the group's cells
  inward from it must be at least 4 long when its far end drops too (so curves from both sides
  meet or leave a middle) and 2 when it does not. The same rules hold: every socket on a free
  stud, and it fits. When a group has curves, the rest of it is covered with ``PLATES`` and
  their studs with ``TILES`` (16 LDU, level with the curves' crests); cells no plate fits get
  tiles. ``Height.curved`` names the ways its curves slope down.
- ``skin(text, colour, lines=None, box=None, facing=None, finish="tiles")``: the free studs
  that do not point up (or only those pointing ``facing``: "+x", "-x", "+z", "-z", "down"),
  grouped by the way they point and the plane their bases lie in: one panel each, the one
  with the fewest studs first (an end before a flank, so the flank's plates can reach over
  the end panel's edges and close the corner). A panel's plates (``PLATES``) go on its side
  studs as ``place`` puts a part on a side stud (its underside against the side); every cell
  of a plate holds one of the studs or has the model's core within ``BEHIND`` (2 to 6 LDU)
  behind it, so a panel reaches out to the face's outline wherever nothing is in the way. The
  plate that catches the most studs not yet caught (then the largest) and fits goes first,
  until every stud is caught or none fits; nothing may go below the ground. A plate held by
  one stud is listed as able to turn. With ``finish="tiles"`` the plates' outward studs are
  then capped with ``TILES`` as ``cap`` does, in that plane. Each panel says which lines of
  the model it now lies over (``Panel.over``) and how much of its face's core (the parts whose
  front is within a plate behind the panel's back, sampled every ``FACE_STEP``) still shows
  beside it, and where (``Panel.bare``, ``bare_box``). With no ``facing``, the side faces
  (-z, +z, -x, +x) with no free side stud among the parts named are ``Result.no_studs``.
- ``core(at, size, colour, sides)`` (guide mode's ``fill`` with "sides"): the box ``edit.fill``
  would fill, built as a core whose named outer faces ("-z", "+z", "-x", "+x" or "all") carry
  side studs facing out, ready for ``skin``: a layer of brackets (``BRACKETS``: 99781, and
  36841 for an odd cell; flange hanging 20 LDU outside the face, side studs 10 LDU below the
  layer's top) along those faces' edge cells at the top plate and every ``COURSE`` (5) plates
  below it while at least 3 plates up, so one 2-wide plate on each row of side studs covers
  two courses; plates (``edit.fill``) inside that layer and ``edit.fill`` boxes between.
  Corner cells belong to the z faces. It returns the lines (``0 STEP`` between groups), the
  free top studs, which lines carry each face's side studs and the height of their rows.
- Both then check the model with the new lines (``validate.check``, no movement): a new part
  with a problem is dropped with the checker's words (and so is what stood on it), and the check
  is repeated, at most ``ROUNDS`` times. They return a ``Result``: the new lines (appended in
  order after the model's last line, so their numbers are ``numbers``), the model with them,
  the last report, what was covered, kept, already covered, left and dropped, and each panel
  (``Panel``) or height (``Height``). Bad input raises ``CoverError`` in plain words.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from typing import Any

import numpy as np

from bricksnap.lab.ldraw_lib import Library, Part, fmt, library
from bricksnap.lab.place import QUARTER, _clean, _rot_between, ldraw_line, sockets
from bricksnap.lab.validate import (
    IGNORE_OVERLAP,
    Placed,
    Report,
    _overlap,
    _really_overlap,
    _stud_hits,
    _world_bbox,
    check,
    numbered_studs,
)

TILES = ("3070b", "3069b", "63864", "2431", "6636", "4162", "3068b", "26603", "87079", "69729")
PLATES = (
    "3024",
    "3023b",
    "3623",
    "3710",
    "3666",
    "3460",
    "4477",
    "60479",
    "3022",
    "3021",
    "3020",
    "3795",
    "3034",
    "3832",
    "2445",
)
ROUNDS = 3
UP = np.array([0.0, -1.0, 0.0])
AXES = {
    "+x": np.array([1.0, 0, 0]),
    "-x": np.array([-1.0, 0, 0]),
    "+z": np.array([0, 0, 1.0]),
    "-z": np.array([0, 0, -1.0]),
    "up": UP,
    "down": np.array([0, 1.0, 0]),
}


class CoverError(ValueError):
    pass


@dataclass(eq=False)
class Stud:
    line: int
    number: int
    pos: np.ndarray  # world base
    way: np.ndarray  # world direction

    def where(self) -> str:
        return f"({', '.join(fmt(round(float(v), 1)) for v in self.pos)})"


@dataclass(eq=False)
class New:
    key: str
    description: str
    pos: np.ndarray
    m: np.ndarray
    line: str
    studs: list[Stud]  # the free studs it covers (cap) or catches (skin)
    held: int  # studs of the model in it
    via: tuple[int, int, int, int]  # place's line, stud, socket, turn for the same line
    on: int = -1  # skin's tiles: index of the plate it stands on


@dataclass
class Height:
    facing: str
    depth: float  # y for a top
    studs: int
    parts: list[New]
    curved: list[str] = field(default_factory=list)  # the ways its curved edges slope down


@dataclass
class Panel:
    facing: str
    back: float  # where the plates' undersides lie, along the facing axis
    face: float  # the outermost face of what was added
    across: float  # LDU, in the plane
    up: float
    held: int
    plates: list[New]
    tiles: list[New]
    turnable: list[New]
    over: list[int] = field(default_factory=list)  # lines of the model now behind it
    bare: float = 0.0  # LDU^2 of the face's core beside it still showing
    bare_box: tuple[float, float, float, float] = (0, 0, 0, 0)  # u lo, u hi, v lo, v hi


@dataclass
class Result:
    text: str
    lines: list[str]
    numbers: list[int]
    report: Report
    covered: int = 0
    kept: list[Stud] = field(default_factory=list)
    taken: int = 0  # studs named that were already covered
    other_way: int = 0  # free studs named that point the other way (side studs for cap)
    no_studs: list[str] = field(default_factory=list)  # skin: side faces with no free stud
    left: list[tuple[Stud, str]] = field(default_factory=list)
    dropped: list[tuple[New, str]] = field(default_factory=list)
    heights: list[Height] = field(default_factory=list)
    panels: list[Panel] = field(default_factory=list)


# ---- studs ---------------------------------------------------------------------------------


def _axis_name(d: np.ndarray) -> str | None:
    for name, a in AXES.items():
        if float(np.dot(d, a)) > 0.999:
            return name
    return None


def _plane(d: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Two axes across a plane facing d (d along a world axis)."""
    k = int(np.argmax(np.abs(d)))
    if k == 1:
        return np.array([1.0, 0, 0]), np.array([0, 0, 1.0])
    if k == 0:
        return np.array([0, 0, 1.0]), np.array([0, 1.0, 0])
    return np.array([1.0, 0, 0]), np.array([0, 1.0, 0])


def _phase(x: float) -> float:
    return round(round(float(x), 1) % 20.0, 1) % 20.0


def studs_of(report: Report) -> list[tuple[Stud, bool]]:
    """Every male stud of the model and whether it is free (``looks.studs``'s order)."""
    from bricksnap.lab import looks

    st = looks.studs(report)
    numbers = [
        (p.line, k) for p in report.placed for k in range(1, len(numbered_studs(p.part)) + 1)
    ]
    return [
        (Stud(line, k, st.pos[i].copy(), st.way[i].copy()), bool(st.showing[i]))
        for i, (line, k) in enumerate(numbers)
    ]


def _select(
    report: Report,
    lines: list[int] | None,
    box: tuple[np.ndarray, np.ndarray] | None,
) -> list[tuple[Stud, bool]]:
    if lines is None and box is None:
        raise CoverError("say which studs: lines (a list of line numbers), a box, or both.")
    if lines is not None:
        have = {p.line for p in report.placed}
        bad = [n for n in lines if n not in have]
        if bad:
            raise CoverError(
                f"line{'s' if len(bad) > 1 else ''} {', '.join(map(str, bad[:10]))} "
                "is not a part the checker can read."
            )
    out = []
    for s, free in studs_of(report):
        if lines is not None and s.line not in lines:
            continue
        if box is not None and not (
            np.all(s.pos >= box[0] - 0.5) and np.all(s.pos <= box[1] + 0.5)
        ):
            continue
        out.append((s, free))
    return out


# ---- fitting -------------------------------------------------------------------------------


class _Near:
    """The model's parts (and the new ones as they come), with their boxes."""

    def __init__(self, placed: list[Placed]) -> None:
        self.parts = list(placed)
        boxes = [_world_bbox(p, 1.0) for p in self.parts]
        self.lo = np.array([b[0] for b in boxes]).reshape(-1, 3)
        self.hi = np.array([b[1] for b in boxes]).reshape(-1, 3)

    def add(self, p: Placed) -> None:
        lo, hi = _world_bbox(p, 1.0)
        self.parts.append(p)
        self.lo = np.vstack([self.lo, lo])
        self.hi = np.vstack([self.hi, hi])

    def around(self, p: Placed) -> list[Placed]:
        lo, hi = _world_bbox(p, 1.0)
        if not self.parts:
            return []
        ok = np.all(self.lo <= hi, axis=1) & np.all(self.hi >= lo, axis=1)
        return [self.parts[i] for i in np.nonzero(ok)[0]]


def _name(p: Placed) -> str:
    return f"line {p.line} ({p.key})" if p.line > 0 else f"a new {p.key}"


def fits(cand: Placed, near: _Near) -> tuple[str | None, int]:
    """None and how many studs of the model hold it when the part fits there; else why not."""
    held = 0
    for o in near.around(cand):
        for holder, other in ((o, cand), (cand, o)):
            for h in _stud_hits(holder, other):
                if h.ok:
                    held += holder is o
                elif h.joint is None:
                    if holder is o:
                        return f"a stud of {_name(o)} is in the way", 0
                    return f"its own studs would hit {_name(o)}", 0
        vol = max(_overlap(cand, o)[0], _overlap(o, cand)[0])
        if vol >= IGNORE_OVERLAP and _really_overlap(cand, o):
            return f"{_name(o)} is in the way", 0
    if held == 0:
        return "nothing would hold it", 0
    lo, hi = cand.part.bbox_min, cand.part.bbox_max
    corners = np.array(
        [[a, b, c] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for c in (lo[2], hi[2])]
    )
    if float(cand.to_world(corners)[:, 1].max()) > 0.5:
        return "it would go below the ground", 0
    return None, held


def _placed(key: str, part: Part, colour: int, pos: np.ndarray, m: np.ndarray, line: int) -> Placed:
    m = _clean(m)
    return Placed(line, colour, pos, m, key, key, part, 0, np.linalg.inv(m))


# ---- covering a plane of studs --------------------------------------------------------------


@dataclass
class _Shape:
    key: str
    part: Part
    turn: int
    m: np.ndarray
    rel: list[tuple[int, int]]  # cells of its grid sockets, from its first
    first: np.ndarray  # its first grid socket, in its own frame
    area: int
    wide: int
    order: int


def _grid(part: Part) -> list[np.ndarray]:
    return [s.pos for s in sockets(part) if s.kind == "grid"]


def _shapes(keys: tuple[str, ...], d: np.ndarray, lib: Library) -> list[_Shape]:
    u, v = _plane(d)
    out: list[_Shape] = []
    for order, k in enumerate(keys):
        found = lib.resolve(k + ".dat")
        if found is None or found[0] != "part":
            continue
        part = lib.part(found[1])
        grid = _grid(part)
        if not grid:
            continue
        seen: set[frozenset[tuple[int, int]]] = set()
        for turn in (0, 1):
            m = _clean(_rot_between(UP, d) @ np.linalg.matrix_power(QUARTER, turn))
            rel = []
            for g in grid:
                off = m @ (g - grid[0])
                a, b = float(off @ u) / 20, float(off @ v) / 20
                if abs(a - round(a)) > 0.05 or abs(b - round(b)) > 0.05 or abs(off @ d) > 0.5:
                    rel = []
                    break
                rel.append((round(a), round(b)))
            if not rel or frozenset(rel) in seen:
                continue
            seen.add(frozenset(rel))
            us, vs = [r[0] for r in rel], [r[1] for r in rel]
            w, h = max(us) - min(us) + 1, max(vs) - min(vs) + 1
            if w * h != len(rel):
                continue  # not a full rectangle of sockets
            out.append(_Shape(found[1], part, turn, m, rel, grid[0], len(rel), min(w, h), order))
    out.sort(key=lambda s: (-s.area, -s.wide, s.order, s.turn))
    return out


def _cells(studs: list[Stud], d: np.ndarray) -> dict[tuple, dict[tuple[int, int], Stud]]:
    """The studs pointing d, by plane and grid: {(depth, phase u, phase v): {cell: stud}}."""
    u, v = _plane(d)
    groups: dict[tuple, dict[tuple[int, int], Stud]] = {}
    for s in studs:
        pu, pv, depth = float(s.pos @ u), float(s.pos @ v), round(float(s.pos @ d), 1)
        key = (depth, _phase(pu), _phase(pv))
        cell = (round((pu - key[1]) / 20), round((pv - key[2]) / 20))
        groups.setdefault(key, {})[cell] = s
    return groups


def _fill_cells(
    cells: dict[tuple[int, int], Stud],
    open_: set[tuple[int, int]],
    shapes: list[_Shape],
    colour: int,
    near: _Near,
    next_line: int,
    new: list[New],
    why: dict[tuple[int, int], str],
) -> list[New]:
    """The greedy cover of the open cells (taken out of ``open_``); appends to ``new``."""
    mine: list[New] = []
    for sh in shapes:
        for cell in sorted(open_, key=lambda c: (c[1], c[0])):
            if cell not in open_:
                continue
            need = [(cell[0] + a, cell[1] + b) for a, b in sh.rel]
            if not all(c in open_ for c in need):
                continue
            n = _try(sh, cells, cell, need, colour, near, next_line + len(new), why)
            if n is not None:
                new.append(n)
                mine.append(n)
                open_ -= set(need)
    return mine


def _try(
    sh: _Shape,
    cells: dict[tuple[int, int], Stud],
    cell: tuple[int, int],
    need: list[tuple[int, int]],
    colour: int,
    near: _Near,
    line: int,
    why: dict[tuple[int, int], str],
) -> New | None:
    """The shape with its first grid socket on the stud of ``cell``, if it fits."""
    anchor = cells[cell]
    pos = anchor.pos - sh.m @ sh.first
    cand = _placed(sh.key, sh.part, colour, pos, sh.m, line)
    no, held = fits(cand, near)
    if no:
        for c in need:
            if sh.area == 1 or c not in why:
                why[c] = no
        return None
    near.add(cand)
    return New(
        sh.key,
        sh.part.description,
        cand.pos,
        cand.m,
        ldraw_line(colour, pos, sh.m, sh.key),
        [cells[c] for c in need],
        held,
        (anchor.line, anchor.number, 1, sh.turn),
    )


@cache
def _downhill(key: str) -> np.ndarray | None:
    """A curved slope's way down, in its own frame: from its high end to its low end."""
    part = library().part(key)
    if part.top is None:
        return None
    top = part.top
    best = None
    for k, axis in ((0, np.array([1.0, 0, 0])), (1, np.array([0, 0, 1.0]))):
        means = np.nanmean(top, axis=1 - k)
        drop = float(means[-1] - means[0])  # y down: positive when the + end is lower
        if best is None or abs(drop) > abs(best[0]):
            best = (drop, axis)
    assert best is not None
    return best[1] * np.sign(best[0]) if abs(best[0]) > 4 else None


def _curve(key: str, d: np.ndarray, o: np.ndarray, lib: Library) -> _Shape | None:
    """A curved slope turned so it slopes down along ``o`` (world), as a shape."""
    found = lib.resolve(key + ".dat")
    down = _downhill(key + ".dat") if found else None
    if found is None or down is None:
        return None
    part = lib.part(found[1])
    grid = _grid(part)
    u, v = _plane(d)
    for turn in range(4):
        m = _clean(_rot_between(UP, d) @ np.linalg.matrix_power(QUARTER, turn))
        if float((m @ down) @ o) < 0.99:
            continue
        rel = []
        for g in grid:
            off = m @ (g - grid[0])
            rel.append((round(float(off @ u) / 20), round(float(off @ v) / 20)))
        return _Shape(found[1], part, turn, m, rel, grid[0], len(rel), 1, 0)
    return None


def _drop(stud: Stud, o: np.ndarray, d: np.ndarray, near: _Near, level: set) -> bool:
    """Whether the top ends in a drop beyond this stud, the way o: no stud at its height there
    and nothing beside it at the height of what would cover it."""
    beyond = stud.pos + 20 * o
    if (round(float(beyond @ d), 1), *np.round(beyond, 0)) in level:
        return False
    pts = np.array([stud.pos + k * o + h * d for k in (12.0, 20.0) for h in (2.0, 6.0, 12.0)])
    ok = np.all(near.lo <= pts.max(0), axis=1) & np.all(near.hi >= pts.min(0), axis=1)
    return not any(
        near.parts[i].part.inside(near.parts[i].to_local(pts)).any() for i in np.nonzero(ok)[0]
    )


CURVES = ("15068", "11477")  # 2 x 2 and 1 x 2: two plates tall, two studs deep


def _edges(
    cells: dict[tuple[int, int], Stud],
    open_: set[tuple[int, int]],
    d: np.ndarray,
    colour: int,
    near: _Near,
    lib: Library,
    next_line: int,
    new: list[New],
    why: dict[tuple[int, int], str],
    level: set,
) -> tuple[list[New], list[str], set[tuple[int, int]]]:
    """Curved slopes along the edges of this top that end in a drop (see the contract).
    Returns them, the ways they slope down, and the edge cells that got no curve (left flat:
    lifted, they would stand up as a block at the edge)."""
    u, v = _plane(d)
    mine: list[New] = []
    facing: list[str] = []
    flat: set[tuple[int, int]] = set()
    for du, dv in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        o = du * u + dv * v
        wide = _curve(CURVES[0], d, o, lib)
        one = _curve(CURVES[1], d, o, lib)
        if one is None:
            continue
        across = (dv, du) if du == 0 else (0, 1)  # along the edge
        across = (abs(across[0]), abs(across[1]))
        edge = []
        for c in sorted(open_, key=lambda c: (c[1], c[0]) if du else (c[0], c[1])):
            if (c[0] + du, c[1] + dv) in cells or not _drop(cells[c], o, d, near, level):
                continue
            run = 0
            while (c[0] - run * du, c[1] - run * dv) in cells:
                run += 1
            far = cells[(c[0] - (run - 1) * du, c[1] - (run - 1) * dv)]
            far_drop = _drop(far, -o, d, near, level)
            if run >= (4 if far_drop else 2):
                edge.append(c)
        done = set()
        for c in edge:
            if c in done or c not in open_:
                continue
            inward = [c, (c[0] - du, c[1] - dv)]
            pair = (c[0] + across[0], c[1] + across[1])
            tries = []
            if wide is not None and pair in edge and pair not in done:
                side = [(p[0] + across[0], p[1] + across[1]) for p in inward]
                tries.append((wide, inward + side))
            tries.append((one, inward))
            placed = False
            for sh, need in tries:
                if not all(x in open_ for x in need):
                    continue
                if _side_open(need, across, cells, u, v, d, near, level):
                    continue  # its side would face a drop: the notch under its high end shows
                a0 = (min(x[0] for x in need), min(x[1] for x in need))
                r0 = (min(r[0] for r in sh.rel), min(r[1] for r in sh.rel))
                anchor = (a0[0] - r0[0], a0[1] - r0[1])
                if {(anchor[0] + a, anchor[1] + b) for a, b in sh.rel} != set(need):
                    continue
                n = _try(sh, cells, anchor, need, colour, near, next_line + len(new), why)
                if n is None:
                    continue
                new.append(n)
                mine.append(n)
                open_ -= set(need)
                done |= {x for x in need if x in edge}
                name = _axis_name(o)
                if name and name not in facing:
                    facing.append(name)
                placed = True
                break
            if not placed:
                flat |= {x for x in inward if x in open_}
    return mine, facing, flat - {c for n in mine for c in _cells_of(n, cells)}


def _cells_of(n: New, cells: dict[tuple[int, int], Stud]) -> list[tuple[int, int]]:
    ids = {id(s) for s in n.studs}
    return [c for c, s in cells.items() if id(s) in ids]


def _side_open(
    need: list[tuple[int, int]],
    across: tuple[int, int],
    cells: dict[tuple[int, int], Stud],
    u: np.ndarray,
    v: np.ndarray,
    d: np.ndarray,
    near: _Near,
    level: set,
) -> bool:
    """Whether a curve on these cells would have a side facing a drop. Its high half is open
    underneath for one plate (8 LDU) at the sides: a tile, plate or curve beside it, or a
    wall, hides that; a drop does not."""
    for x in need:
        for sgn in (1, -1):
            nb = (x[0] + sgn * across[0], x[1] + sgn * across[1])
            if nb in need or nb in cells:
                continue
            if _drop(cells[x], sgn * (across[0] * u + across[1] * v), d, near, level):
                return True
    return False


def _cover(
    studs: list[Stud],
    d: np.ndarray,
    keys: tuple[str, ...],
    colour: int,
    near: _Near,
    lib: Library,
    next_line: int,
    curved: bool = False,
    level: set | None = None,
) -> tuple[list[New], list[tuple[Stud, str]], list[Height]]:
    """Cover these free studs (all pointing d) with the fewest of these parts (see the
    contract). Returns the new parts, the studs left with why, and one Height per group.
    ``curved``: curved slopes along the edges that end in a drop first, then the rest raised
    by a plate to their height and tiled (``level``: every stud of the model, for the drop)."""
    shapes = _shapes(keys, d, lib)
    facing = _axis_name(d) or "?"
    new: list[New] = []
    left: list[tuple[Stud, str]] = []
    heights: list[Height] = []
    for (depth, _, _), cells in sorted(_cells(studs, d).items(), key=lambda kv: kv[0]):
        open_ = set(cells)
        why: dict[tuple[int, int], str] = {}
        curves: list[New] = []
        dirs: list[str] = []
        flat: set[tuple[int, int]] = set()
        if curved:
            curves, dirs, flat = _edges(
                cells, open_, d, colour, near, lib, next_line, new, why, level or set()
            )
        lift = open_ - flat
        if curves and lift:
            # the middle goes up a plate first, so its tiles are level with the curves' crests
            plates = _fill_cells(
                cells, lift, _shapes(PLATES, d, lib), colour, near, next_line, new, why
            )
            open_ = lift | (open_ & flat)
            first = len(new)
            owner: dict[int, int] = {}
            on_plates = []
            for pl in plates:
                for k, c in enumerate(numbered_studs(lib.part(pl.key)), 1):
                    st = Stud(next_line + new.index(pl), k, pl.m @ c.pos + pl.pos, pl.m @ c.axis)
                    owner[id(st)] = new.index(pl)
                    on_plates.append(st)
            tiles, tleft, _ = _cover(on_plates, d, TILES, colour, near, lib, next_line + first)
            for t in tiles:
                t.on = owner[id(t.studs[0])]
                t.studs = []  # the studs it covers are the plates' own
            new += tiles
            left += tleft
            mine = curves + plates + tiles
        else:
            mine = curves
        mine += _fill_cells(cells, open_, shapes, colour, near, next_line, new, why)
        for c in sorted(open_, key=lambda c: (c[1], c[0])):
            left.append((cells[c], why.get(c, "no part fits there")))
        if mine:
            heights.append(Height(facing, depth, sum(len(n.studs) for n in mine), mine, dirs))
    return new, left, heights


# ---- the panel of a skin ---------------------------------------------------------------------


def _footprint(part: Part, pos: np.ndarray, m: np.ndarray, d: np.ndarray) -> np.ndarray:
    """(u lo, u hi, v lo, v hi) of the part's body in the plane facing d."""
    u, v = _plane(d)
    lo, hi = part.bbox_min, part.bbox_max
    c = np.array(
        [[a, b, e] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for e in (lo[2], hi[2])]
    )
    w = c @ m.T + pos
    pu, pv = w @ u, w @ v
    return np.array([pu.min(), pu.max(), pv.min(), pv.max()])


def _apart(a: np.ndarray, b: np.ndarray) -> bool:
    return bool(
        a[1] <= b[0] + 0.5 or b[1] <= a[0] + 0.5 or a[3] <= b[2] + 0.5 or b[3] <= a[2] + 0.5
    )


BEHIND = (2.0, 6.0)  # LDU behind a panel's back where the core it may cover must be


def _core(w: np.ndarray, d: np.ndarray, near: _Near, memo: dict[tuple, int]) -> int:
    """The line of a part of the model just behind this point of a panel's back (within
    ``BEHIND``), or 0: what the panel would lie over there."""
    key = tuple(np.round(w, 1))
    if key not in memo:
        pts = np.array([w - k * d for k in BEHIND])
        ok = np.all(near.lo <= pts.max(0), axis=1) & np.all(near.hi >= pts.min(0), axis=1)
        memo[key] = next(
            (
                near.parts[i].line
                for i in np.nonzero(ok)[0]
                if near.parts[i].line > 0
                and near.parts[i].part.inside(near.parts[i].to_local(pts)).any()
            ),
            0,
        )
    return memo[key]


def _panel(
    studs: list[Stud], d: np.ndarray, colour: int, near: _Near, lib: Library, next_line: int
) -> tuple[list[New], list[tuple[Stud, str]]]:
    behind: dict[tuple, int] = {}
    cands = []
    seen: set[tuple] = set()
    for order, k in enumerate(PLATES):
        found = lib.resolve(k + ".dat")
        if found is None or found[0] != "part":
            continue
        key = found[1]
        part = lib.part(key)
        socks = sockets(part)
        grid = [(j, s.pos) for j, s in enumerate(socks, 1) if s.kind == "grid"]
        for turn in range(4):
            m = _clean(_rot_between(UP, d) @ np.linalg.matrix_power(QUARTER, turn))
            for s in studs:
                for j, g in grid:
                    pos = s.pos - m @ g
                    fp = _footprint(part, pos, m, d)
                    tag = (key, *np.round(fp, 1))
                    if tag in seen:
                        continue
                    seen.add(tag)
                    world = [pos + m @ q for _, q in grid]
                    caught = [
                        i
                        for i, t in enumerate(studs)
                        if any(float(np.linalg.norm(w - t.pos)) < 1.0 for w in world)
                    ]
                    on = {tuple(np.round(studs[i].pos, 1)) for i in caught}
                    if not all(
                        tuple(np.round(w, 1)) in on or _core(w, d, near, behind) for w in world
                    ):
                        continue  # a cell with no core within a plate behind it
                    area = (fp[1] - fp[0]) * (fp[3] - fp[2])
                    cands.append(
                        (key, part, pos, m, fp, caught, area, order, (s.line, s.number, j, turn))
                    )
    remaining = set(range(len(studs)))
    chosen: list[New] = []
    taken_fp: list[np.ndarray] = []
    rejected: dict[int, str] = {}
    why: dict[int, tuple[float, str]] = {}
    while remaining:
        ranked = sorted(
            range(len(cands)),
            key=lambda i: (-len(remaining & set(cands[i][5])), -cands[i][6], cands[i][7]),
        )
        best = None
        for i in ranked:
            key, part, pos, m, fp, caught, area, order, via = cands[i]
            if not remaining & set(caught):
                break
            if i in rejected or not all(_apart(fp, t) for t in taken_fp):
                continue
            cand = _placed(key, part, colour, pos, m, next_line + len(chosen))
            no, held = fits(cand, near)
            if no:
                rejected[i] = no
                for c in caught:
                    if c not in why or area < why[c][0]:
                        why[c] = (area, no)
                continue
            best = (cand, caught, held, via, fp)
            break
        if best is None:
            break
        cand, caught, held, via, fp = best
        near.add(cand)
        taken_fp.append(fp)
        remaining -= set(caught)
        chosen.append(
            New(
                cand.key,
                cand.part.description,
                cand.pos,
                cand.m,
                ldraw_line(colour, cand.pos, cand.m, cand.key),
                [studs[c] for c in caught],
                held,
                via,
            )
        )
    left = [(studs[i], why.get(i, (0, "no plate fits there"))[1]) for i in sorted(remaining)]
    return chosen, left


# ---- the two tools -------------------------------------------------------------------------


def _colour(colour: int, lib: Library) -> None:
    if colour in (16, 24) or colour not in lib.colours():
        raise CoverError(f"colour {colour} is not a colour of the library (never 16 or 24).")


def _verify(
    text: str, new: list[New]
) -> tuple[str, list[int], Report, list[tuple[New, str]], list[int]]:
    """Append the new lines, check, and drop new parts with a problem (and what stood on them),
    at most ``ROUNDS`` times. Returns the model, the new lines' numbers, the last report, what
    was dropped and the indexes of the new parts kept."""
    base = text.splitlines()
    first = len(base) + 1
    keep = list(range(len(new)))
    dropped: list[tuple[New, str]] = []
    for _ in range(ROUNDS):
        full = "\n".join([*base, *(new[i].line for i in keep)]) + "\n"
        report = check(full, movement=False)
        numbers = {first + k: i for k, i in enumerate(keep)}
        bad: dict[int, str] = {}
        for issue in report.problems:
            for n in issue.lines:
                if n in numbers and numbers[n] not in bad:
                    bad[numbers[n]] = issue.text[:240]
        for i in keep:  # a tile on a dropped plate goes with it
            if new[i].on in bad and i not in bad:
                bad[i] = "the plate it stood on was dropped"
        if not bad:
            return full, [first + k for k in range(len(keep))], report, dropped, keep
        dropped += [(new[i], bad[i]) for i in keep if i in bad]
        keep = [i for i in keep if i not in bad]
    full = "\n".join([*base, *(new[i].line for i in keep)]) + "\n"
    return full, [first + k for k in range(len(keep))], check(full, movement=False), dropped, keep


def cap(
    text: str,
    colour: int,
    lines: list[int] | None = None,
    box: tuple[np.ndarray, np.ndarray] | None = None,
    use: str = "tiles",
    keep: tuple[tuple[int, int], ...] | list[tuple[int, int]] = (),
    lib: Library | None = None,
    edges: str = "flat",
) -> Result:
    lib = lib or library()
    _colour(colour, lib)
    if use not in ("tiles", "plates"):
        raise CoverError('"with" is "tiles" or "plates".')
    if edges not in ("flat", "curved"):
        raise CoverError('edges is "flat" or "curved".')
    report = check(text, movement=False)
    named = _select(report, lines, box)
    keep_set = {(int(a), int(b)) for a, b in keep}
    res = Result(text, [], [], report)
    group = []
    for s, free in named:
        if not free:
            res.taken += 1
        elif (s.line, s.number) in keep_set:
            res.kept.append(s)
        elif float(s.way @ UP) > 0.999:
            group.append(s)
        else:
            res.other_way += 1
    if not group:
        return res
    near = _Near(report.placed)
    first = len(text.splitlines()) + 1
    level = {
        (round(float(s.pos @ UP), 1), *np.round(s.pos, 0))
        for s, _ in studs_of(report)
        if float(s.way @ UP) > 0.999
    }
    new, left, heights = _cover(
        group,
        UP,
        TILES if use == "tiles" else PLATES,
        colour,
        near,
        lib,
        first,
        curved=edges == "curved",
        level=level,
    )
    return _finish(text, res, new, left, heights=heights)


def skin(
    text: str,
    colour: int,
    lines: list[int] | None = None,
    box: tuple[np.ndarray, np.ndarray] | None = None,
    facing: str | None = None,
    finish: str = "tiles",
    lib: Library | None = None,
) -> Result:
    lib = lib or library()
    _colour(colour, lib)
    if finish not in ("tiles", "plates"):
        raise CoverError('finish is "tiles" or "plates".')
    if facing is not None and facing not in ("+x", "-x", "+z", "-z", "down"):
        raise CoverError('facing is "+x", "-x", "+z", "-z" or "down" (for studs on top, use cap).')
    report = check(text, movement=False)
    named = _select(report, lines, box)
    res = Result(text, [], [], report)
    by_way: dict[tuple[str, float], list[Stud]] = {}
    for s, free in named:
        if not free:
            res.taken += 1
            continue
        name = _axis_name(s.way)
        if name == "up" or (facing is not None and name != facing):
            res.other_way += 1
            continue
        if name is None:
            res.left.append((s, "it does not point along x, y or z"))
            continue
        by_way.setdefault((name, round(float(s.pos @ AXES[name]), 1)), []).append(s)
    if not by_way:
        return res
    near = _Near(report.placed)
    first = len(text.splitlines()) + 1
    new: list[New] = []
    left: list[tuple[Stud, str]] = []
    panels: list[Panel] = []
    # the panel with the fewest studs first (an end): the larger one (a flank) may then reach
    # over its edges and close the corner
    for (name, _), studs in sorted(by_way.items(), key=lambda kv: (len(kv[1]), kv[0])):
        d = AXES[name]
        plates, why = _panel(studs, d, colour, near, lib, first + len(new))
        left += why
        if not plates:
            continue
        p0 = len(new)
        new += plates
        tiles: list[New] = []
        if finish == "tiles":
            outward = []
            owner: dict[int, int] = {}
            for i, pl in enumerate(plates):
                part = lib.part(pl.key)
                for k, c in enumerate(numbered_studs(part), 1):
                    s = Stud(first + p0 + i, k, pl.m @ c.pos + pl.pos, pl.m @ c.axis)
                    owner[id(s)] = p0 + i
                    outward.append(s)
            tiles, tleft, _ = _cover(outward, d, TILES, colour, near, lib, first + len(new))
            for t in tiles:
                t.on = owner[id(t.studs[0])]
            left += tleft
            new += tiles
        pn = _panel_of(name, d, plates, tiles, lib)
        _face(pn, d, report.placed, lib)
        panels.append(pn)
    if facing is None:
        made = {pn.facing for pn in panels} | {name for name, _ in by_way}
        res.no_studs = [f for f in ("-z", "+z", "-x", "+x") if f not in made]
    return _finish(text, res, new, left, panels=panels)


FACE_STEP = 4.0  # LDU between the points a face is sampled at


def _face(pn: Panel, d: np.ndarray, placed: list[Placed], lib: Library) -> None:
    """What the panel lies over (lines of the model just behind it) and where the core of
    that face still shows beside it: the points of the face, sampled every ``FACE_STEP``,
    with a part of the model within ``BEHIND`` of the panel's back and no panel plate in
    front."""
    u, v = _plane(d)
    k = int(np.argmax(np.abs(d)))
    back = pn.back * float(d[k])  # along d
    boxes = [(p, *_world_bbox(p, 0.0)) for p in placed]
    face = [
        (p, lo, hi)
        for p, lo, hi in boxes
        if back - 8 <= _along(lo, hi, d)[1] <= back + 0.5  # its front within a plate behind
    ]
    if not face:
        return
    us = [float(b) for _, lo, hi in face for b in (lo @ np.abs(u), hi @ np.abs(u))]
    vs = [float(b) for _, lo, hi in face for b in (lo @ np.abs(v), hi @ np.abs(v))]
    gu = np.arange(min(us) + FACE_STEP / 2, max(us), FACE_STEP)
    gv = np.arange(min(vs) + FACE_STEP / 2, max(vs), FACE_STEP)
    if not len(gu) or not len(gv):
        return
    a, b = np.meshgrid(gu, gv, indexing="ij")
    a, b = a.ravel(), b.ravel()
    w = np.outer(a, np.abs(u)) + np.outer(b, np.abs(v)) + back * d
    core = np.zeros(len(w), dtype=int)
    for p, lo, hi in face:
        for depth in BEHIND:
            q = w - depth * d
            sel = np.nonzero((core == 0) & np.all((q >= lo - 0.5) & (q <= hi + 0.5), axis=1))[0]
            if len(sel):
                hit = p.part.inside(p.to_local(q[sel]))
                core[sel[hit]] = p.line
    fps = [_footprint(lib.part(x.key), x.pos, x.m, d) for x in pn.plates]
    # the footprints are in the signed plane axes; the samples in their absolute values
    su, sv = float(np.sign(u.sum())), float(np.sign(v.sum()))
    covered = np.zeros(len(w), dtype=bool)
    for fp in fps:
        ulo, uhi = sorted((fp[0] * su, fp[1] * su))
        vlo, vhi = sorted((fp[2] * sv, fp[3] * sv))
        covered |= (a >= ulo - 0.5) & (a <= uhi + 0.5) & (b >= vlo - 0.5) & (b <= vhi + 0.5)
    pn.over = sorted({int(x) for x in core[covered & (core > 0)]})
    bare = (core > 0) & ~covered
    pn.bare = float(bare.sum()) * FACE_STEP * FACE_STEP
    if bare.any():
        h = FACE_STEP / 2
        pn.bare_box = (
            float(a[bare].min() - h),
            float(a[bare].max() + h),
            float(b[bare].min() - h),
            float(b[bare].max() + h),
        )


def _along(lo: np.ndarray, hi: np.ndarray, d: np.ndarray) -> tuple[float, float]:
    """The span of a box along d (lowest, highest)."""
    x, y = float(lo @ d), float(hi @ d)
    return min(x, y), max(x, y)


def _panel_of(name: str, d: np.ndarray, plates: list[New], tiles: list[New], lib: Library) -> Panel:
    fps = np.array([_footprint(lib.part(p.key), p.pos, p.m, d) for p in plates])
    depth = []
    for p in plates + tiles:
        part = lib.part(p.key)
        lo, hi = part.bbox_min, part.bbox_max
        c = np.array(
            [[a, b, e] for a in (lo[0], hi[0]) for b in (lo[1], hi[1]) for e in (lo[2], hi[2])]
        )
        depth.append(((c @ p.m.T + p.pos) @ d).max())
    back = float(min((s.pos @ d) for p in plates for s in p.studs))
    k = int(np.argmax(np.abs(d)))
    sign = float(d[k])
    return Panel(
        name,
        back * sign,
        float(max(depth)) * sign,
        float(fps[:, 1].max() - fps[:, 0].min()),
        float(fps[:, 3].max() - fps[:, 2].min()),
        sum(p.held for p in plates),
        plates,
        tiles,
        [p for p in plates if p.held == 1],
    )


def _finish(
    text: str,
    res: Result,
    new: list[New],
    left: list[tuple[Stud, str]],
    heights: list[Height] | None = None,
    panels: list[Panel] | None = None,
) -> Result:
    res.left += left
    if not new:
        res.heights, res.panels = heights or [], panels or []
        return res
    full, numbers, report, dropped, keep = _verify(text, new)
    kept_ids = {id(new[i]) for i in keep}
    res.text, res.numbers, res.report, res.dropped = full, numbers, report, dropped
    res.lines = [new[i].line for i in keep]
    res.covered = sum(len(new[i].studs) for i in keep)
    for h in heights or []:
        h.parts = [p for p in h.parts if id(p) in kept_ids]
        h.studs = sum(len(p.studs) for p in h.parts)
    res.heights = [h for h in heights or [] if h.parts]
    for pn in panels or []:
        pn.plates = [p for p in pn.plates if id(p) in kept_ids]
        pn.tiles = [p for p in pn.tiles if id(p) in kept_ids]
        pn.turnable = [p for p in pn.turnable if id(p) in kept_ids]
        pn.held = sum(p.held for p in pn.plates)
    res.panels = [p for p in panels or [] if p.plates]
    return res


# ---- a core with side studs: fill's "sides" ----------------------------------------------

BRACKETS = {2: "99781", 1: "36841"}  # 1 x 2 and 1 x 1 brackets whose flange hangs down
COURSE = 5  # plates between bracket layers: two rows of a panel (40 LDU)
SIDES = ("-z", "+z", "-x", "+x")


@dataclass
class Core:
    lines: list[str] = field(default_factory=list)
    free_studs: list[tuple[float, float, float]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    parts: int = 0
    sides: dict[str, list[int]] = field(default_factory=dict)  # face -> indexes into lines
    rows: dict[str, list[float]] = field(default_factory=dict)  # face -> y of its side studs
    layers: list[int] = field(default_factory=list)  # plates (from 1 at the bottom) with brackets


def core(
    at: tuple[float, float, float],
    size: tuple[int, int, int],
    colour: int,
    sides: list[str] | str,
    lib: Library | None = None,
) -> Core:
    """A box filled as ``edit.fill`` fills it, built as a core whose named outer faces carry
    side studs facing out (see the contract): a layer of brackets along those faces at the top
    and every ``COURSE`` plates below it, while at least 3 plates up (a bracket's flange
    hangs 20 LDU), plates inside that layer, and ``edit.fill`` boxes between."""
    from bricksnap.lab.edit import EditError, fill

    lib = lib or library()
    x0, y0, z0 = (float(v) for v in at)
    w, d, h = (int(v) for v in size)
    want = list(SIDES) if sides == "all" else list(sides)
    if not want or any(s not in SIDES for s in want):
        raise EditError('sides is "all" or a list of "-z", "+z", "-x", "+x".')
    if h < 3:
        raise EditError("a core with side studs needs at least 3 plates of height.")
    if ("-z" in want and "+z" in want and d < 2) or ("-x" in want and "+x" in want and w < 2):
        raise EditError("side studs on two opposite faces need the box 2 studs across.")
    layers = [k for k in range(h, 2, -COURSE)]
    out = Core(layers=sorted(layers))

    def add(f: Any) -> None:
        if out.lines and out.lines[-1] != "0 STEP":
            out.lines.append("0 STEP")
        out.lines.extend(ln for ln in f.lines if ln != "0 STEP")
        out.parts += f.parts
        out.notes += f.notes

    # which cells of a bracket layer carry a bracket, by face (corners go to the z faces)
    cells: dict[str, list[tuple[int, int]]] = {}
    for face in want:
        if face in ("-z", "+z"):
            j = 0 if face == "-z" else d - 1
            cells[face] = [(i, j) for i in range(w)]
    for face in want:
        if face in ("-x", "+x"):
            i = 0 if face == "-x" else w - 1
            zs = [
                j
                for j in range(d)
                if not ((j == 0 and "-z" in want) or (j == d - 1 and "+z" in want))
            ]
            cells[face] = [(i, j) for j in zs]
    inner_i = [
        i for i in range(w) if not (i == 0 and "-x" in want) and not (i == w - 1 and "+x" in want)
    ]
    inner_j = [
        j for j in range(d) if not (j == 0 and "-z" in want) and not (j == d - 1 and "+z" in want)
    ]
    bottom = 1
    for k in sorted(layers):
        if k > bottom:  # the plain box below this bracket layer
            add(fill((x0, y0 - 8 * (bottom - 1), z0), (w, d, k - bottom), colour))
        y = y0 - 8 * (k - 1)  # the layer stands on studs at this height
        for face, cs in cells.items():
            for line in _bracket_row(face, cs, x0, y, z0, colour, lib):
                out.sides.setdefault(face, []).append(len(out.lines))
                out.lines.append(line)
                out.parts += 1
            out.rows.setdefault(face, []).append(y + 2)  # 10 below the layer's top (y - 8)
        if inner_i and inner_j:
            add(
                fill(
                    (x0 + 20 * inner_i[0], y, z0 + 20 * inner_j[0]),
                    (len(inner_i), len(inner_j), 1),
                    colour,
                )
            )
        bottom = k + 1
    if h >= bottom:
        add(fill((x0, y0 - 8 * (bottom - 1), z0), (w, d, h - bottom + 1), colour))
    out.lines.append("0 STEP")
    for face in out.rows:
        out.rows[face] = sorted(set(out.rows[face]))
    _top_studs(out, h, x0, y0, z0, lib)
    return out


def _bracket_row(
    face: str,
    cs: list[tuple[int, int]],
    x0: float,
    y: float,
    z0: float,
    colour: int,
    lib: Library,
) -> list[str]:
    """The bracket lines along one face's cells (1 x 2 brackets, a 1 x 1 for an odd one),
    each turned so its side studs point out of that face."""
    out = AXES[face]
    lines = []
    k = 0
    while k < len(cs):
        n = 2 if k + 1 < len(cs) else 1
        group = cs[k : k + n]
        key = BRACKETS[n] + ".dat"
        part = lib.part(key)
        side = next(s.axis for s in numbered_studs(part) if abs(s.axis[1]) < 0.5)
        socks = [s.pos for s in sockets(part) if s.kind == "grid"]
        studs = [np.array([x0 + 10 + 20 * i, y, z0 + 10 + 20 * j]) for i, j in group]
        for turn in range(4):
            m = _clean(np.linalg.matrix_power(QUARTER, turn))
            if float((m @ side) @ out) < 0.99:
                continue
            pos = studs[0] - m @ socks[0]
            got = sorted(tuple(np.round(pos + m @ s, 1)) for s in socks)
            if got == sorted(tuple(np.round(s, 1)) for s in studs):
                lines.append(ldraw_line(colour, pos, m, key))
                break
            pos = studs[-1] - m @ socks[0]
            got = sorted(tuple(np.round(pos + m @ s, 1)) for s in socks)
            if got == sorted(tuple(np.round(s, 1)) for s in studs):
                lines.append(ldraw_line(colour, pos, m, key))
                break
        else:
            raise AssertionError(f"no turn of {key} faces {face}")
        k += n
    return lines


def _top_studs(out: Core, h: int, x0: float, y0: float, z0: float, lib: Library) -> None:
    top = y0 - 8 * h
    for ln in out.lines:
        tok = ln.split()
        if len(tok) < 15 or tok[0] != "1":
            continue
        pos = np.array([float(v) for v in tok[2:5]])
        m = np.array([float(v) for v in tok[5:14]]).reshape(3, 3)
        for s in lib.part(tok[14]).top_studs():
            wpos = m @ s.pos + pos
            if abs(float(wpos[1]) - top) < 0.5 and float((m @ s.axis)[1]) < -0.99:
                x, yy, z = (round(float(v), 1) for v in wpos)
                out.free_studs.append((x, yy, z))
