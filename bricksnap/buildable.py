"""Design to Design: change the shape as little as possible so it can be built in one piece.

Parts hold each other only through studs, vertically. So some Designs have no layout in
which everything is attached: a feature in its own colour that touches the body only at its
side (a nose on a face), a sheet one plate thin, a part that hangs in the air. This pass
finds what the layout solver could not attach and repairs the Design in the least visible
way it can, and says what it did.

CONTRACT (tests go in tests/test_buildable.py)

``make_buildable(design, catalog, seed=0, max_solves=12) -> BuildableResult``

    @dataclass
    class BuildableResult:
        design: Design          # a changed copy; the input Design is never modified
        build: Build            # layout.solve(result.design, catalog, seed): no need to solve again
        recoloured: np.ndarray  # bool [x, y, z]: hidden cells whose colour was changed
        added: np.ndarray       # bool [x, y, z]: cells that were empty and are now filled
        notes: list[str]        # plain sentences with coordinates, most important first
        pieces_before: int      # connected pieces of the first solve
        pieces_after: int       # connected pieces of result.build

The solver is the judge: solve, look at which parts are not in the main piece
(``bricksnap.connect.connection_graph``; the main piece is the one with the most cells among
those touching the ground, as in ``bricksnap.checks``), repair the Design near them, solve
again. Stop as soon as there is one piece, or after ``max_solves`` solves.

Words used below
- *Outside air*: empty cells that can be reached, moving between neighbouring empty cells
  (6-connected), from beyond the four sides or the top of the grid. The space below z = 0 is
  the table, not air.
- A filled cell is *visible* when one of its six neighbours is outside air (a neighbour
  beyond the sides or the top of the grid counts as outside air). Every other filled cell
  is *hidden*: nobody can see it once the model is built, so its colour does not matter.
  Cells facing only an enclosed hollow are hidden.

Repairs, in this order of preference (the cheapest that works is used for each loose piece)
1. Recolour hidden cells. Give hidden cells next to the loose piece the piece's colour, so
   its parts can reach into the body and be held from above and below. This is invisible.
   It is what fixes a feature in its own colour stuck on a surface, and two colours that
   meet on a vertical plane.
2. Thicken. A loose piece that is a thin sheet (or the thin edge of one) gets cells added
   directly beneath it in its own colour, one plate at first, so that parts in two levels
   can overlap. Beneath, so the top surface stays as designed.
3. Support. A loose piece that hangs in the air gets a column of cells from its underside
   straight down to the first filled cell or the ground, in its own colour, placed where it
   is hidden (inside a hollow) when that is possible and otherwise under the middle of the
   piece.
A piece that stands on the ground by itself and touches nothing (a second, separate object)
is not bridged; it is reported.

What must be true of the result
- No filled cell is ever emptied, and the colour of a visible cell is never changed. The
  look changes only through added cells, and every added cell is reported.
- ``result.design`` keeps the input's finish, details, regions, log and seed_offset; added
  cells get FINISH_STUDS. Nothing is appended to the log (these are not a person's edits).
- ``pieces_after <= pieces_before``. If the first solve is already one piece (or the Design
  is empty), nothing is changed: both masks are all False, ``notes`` is empty, and
  ``result.design.fingerprint() == design.fingerprint()``.
- When it cannot reach one piece, it returns the best Design it found (fewest pieces, then
  fewest changed cells) and a note saying what is still loose, where, and why nothing
  helped.
- Notes are for the AI designer and for people: plain words, counts and coordinates, for
  example "Recoloured 6 hidden cells behind the Dark Pink part at x=6 to 7, y=3, z=12 to 14
  so that it is held from inside." or "Added 16 cells under the sheet at x=2 to 9, y=0 to
  1, z=11: it was one plate thin and nothing held its outer edge."
- Deterministic for a given ``seed``. A 16-stud model in under 10 seconds.

Tests must include: a nose in its own colour on the front of a head; two colours meeting on
one vertical plane through a thick block; a wide cap one plate thin on a narrow stem; a
table whose top is one plate thin; a bar floating above the model; two separate objects
(reported, not bridged); and a model that needs nothing (returned unchanged).

Implementation notes
--------------------
Each loose piece of a solve becomes a *spot*, followed from solve to solve by the cells it
covered. A spot climbs a ladder of repairs, one rung per solve while it stays loose, and each
rung replaces the one before (its cells go back to the input): recolour hidden cells 1, 2,
then 3 studs deep (spreading side to side through hidden cells only, in the piece's own
levels, each cell taking the colour of the piece cell it was reached from); thicken (a plate
under the piece's one-plate-thin cells, then also under thin cells of the sheet within 2
studs, then under the whole sheet); a support column; and cells beside it (below). All loose
pieces are repaired at once, so one solve serves them all.

Loose is judged per object. An *object* is a group of filled cells that touch each other
(6-connected); each object that stands on the ground has an *anchor*, its piece with the
most cells among those touching the ground. The main piece is the biggest anchor, the
other anchors are separate objects (reported once each, never bridged), and every other
piece is loose and is repaired towards any anchor. So a nose on a second object is joined
to that object, and a second object that is a mushroom gets its cap thickened.

A rung is only used if it could work at all: the change must join the piece to an anchor
on the *floor* of the Design (vertically adjacent cells joined, side-by-side cells of one
colour joined; ``floor_labels``), which no layout can beat. Hopeless rungs cost no solve.
Pieces are looked at twice per round, so a nose whose only way in is through a loose muzzle
can use the muzzle's repair chosen in the same round. The floor test says nothing when the
piece is joined without the change, so:
- if cells another spot added in the same round stand directly on or under the piece, and
  it is through them that the floor joins it, the spot waits a round (*carried*); a change
  that adds cells and was chosen earlier in the round is taken back the same way once a
  later one holds its piece. Only a vertical contact counts: cells one above the other are
  always held together, while side-by-side cells of one colour (which the floor also
  joins) may never be, as in a sheet one plate thin. If the piece comes loose again anyway,
  it no longer waits.
- if the floor joined it already in the Design just solved (a sheet of one colour, or a
  place where the layout fell short), only the invisible recolour and the plate beneath a
  thin sheet are offered, never a column or cells beside it.

Time. A solve the layout can bring down to the floor of its Design is quick (well under a
second at 16 studs); one it cannot (*slow*) costs seconds, because the layout spends its
whole repair budget. So:
- at most ``SLOW_SOLVES`` slow solves are made in all, pruning included;
- ``SLOW_PATIENCE`` slow solves in a row that are no better than the best end the pass;
- after a slow solve that was no better, a spot that is still loose moves on to the next
  kind of repair instead of the same kind a little bigger (recolour 2 studs deep after 1);
- a rung whose change is the same as the one in place is skipped (recolouring 2 studs deep
  often reaches no more cells than 1 stud deep), since the same Design tells nothing new.
On 541 random test designs this ends with fewer loose pieces in all than climbing every
rung did (874 against 880, thanks to the per-object judging above), with at most three slow
solves each; 8 designs that needed four to six slow solves (up to 11 seconds) now keep one
more loose piece. The hollow box of two colours in the tests, which took 9 solves
and 15 seconds, now takes 3 solves and under 4 seconds.

Choices beyond the contract's words:
- Thicken applies only to cells one plate thin (nothing directly above or below), and only
  when at least a third of the loose piece is such cells; a thick body with a few thin cells
  is not a sheet, and trying would cost solves for nothing. A sheet lying on the ground
  cannot be thickened (nothing goes below z = 0, and the top must stay as designed); it is
  reported.
- A support column normally goes down; when nothing below can be reached it may go up to
  the model above, and its note then says "above". A piece that touches the model somewhere
  (a nose on a face) is not hanging in the air, so it gets a column only where the column is
  hidden or at most ``SHORT_COLUMN`` cells tall: a tall post in front of a face is no repair.
- A fourth repair, *cells beside*, comes last: cells in the piece's colour in empty cells
  next to it, in its own level, resting on (or under) the rest of the model, so a part can
  reach from it over the model's studs. It fixes a feature on the top edge of another (a
  nose in front of the top row of a muzzle), where the cell behind can be seen and so
  cannot be recoloured. Its added cells are reported like any other.
- After the best Design is found, what it does not need is taken away, each smaller
  version judged by a solve and kept when it has no more pieces (``_prune``): recoloured
  cells that no part used to join them to cells of the same colour get their colour back
  (on two colours meeting on a plane, 16 down to 6); cells added for a piece that is still
  loose go; cells added for a joined piece go when taking them out of the build splits no
  piece; and then every other spot's added cells are tried without, one spot at a time,
  biggest first, since a fresh layout may not need what the build leaned on. On the test
  mushroom the added plate goes from 76 cells to 32, on the table from 58 to 27. A try
  that is worse and slow ends the pruning.
- No cell covered by a detail part is ever filled.
- Loose pieces that touch each other get one note (the layout splits a long loose feature
  into several parts, each a piece of its own). A group that cannot be repaired gets a note
  saying why in words a person or the AI designer can act on: it lies on the ground one
  plate thin, it touches only visible cells of another colour (paint one in its colour), it
  meets the model in its own colour at a place no part can use, or it touches nothing at
  all; "give it something to stand on" is never said of a piece on the ground. A Design is
  kept only if it has fewer pieces than every one before it, or as many with fewer changed
  cells, so a repair that helped nothing is not returned.
- The pass stops when a round has nothing new to try, so a model with a piece that cannot
  be joined usually costs one or two solves, not ``max_solves``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from bricksnap.catalog import Catalog
from bricksnap.connect import connection_graph, occupancy
from bricksnap.types import EMPTY, FINISH_STUDS, Build, Design, Placement


@dataclass
class BuildableResult:
    design: Design
    build: Build
    recoloured: np.ndarray
    added: np.ndarray
    notes: list[str] = field(default_factory=list)
    pieces_before: int = 0
    pieces_after: int = 0


Cell = tuple[int, int, int]

_SIDES = (
    (np.s_[:-1, :, :], np.s_[1:, :, :]),
    (np.s_[:, :-1, :], np.s_[:, 1:, :]),
)
_STEPS4 = ((1, 0), (-1, 0), (0, 1), (0, -1))

RECOLOUR_DEPTHS = (1, 2, 3)  # studs into the body, tried in this order
THICKEN_REACH = (0, 2, 99)  # how far beyond the loose piece the added plate reaches
THIN_SHARE = 1 / 3  # thicken a loose piece only if at least this share of it is one plate thin
SHORT_COLUMN = 3  # a piece that touches the model gets a support in view only this tall


# ---- geometry of the Design ----------------------------------------------------------------


def outside_air(filled: np.ndarray) -> np.ndarray:
    """bool [x, y, z]: empty cells reachable from beyond the four sides or the top."""
    nx_, ny_, nz_ = filled.shape
    empty = np.ones((nx_ + 2, ny_ + 2, nz_ + 1), dtype=bool)
    empty[1:-1, 1:-1, :-1] = ~filled
    labels, _ = ndimage.label(empty)
    border = np.zeros(empty.shape, dtype=bool)
    border[[0, -1], :, :] = True
    border[:, [0, -1], :] = True
    border[:, :, -1] = True
    outside = np.isin(labels, np.unique(labels[border & empty]))
    return outside[1:-1, 1:-1, :-1] & ~filled


def visible_cells(filled: np.ndarray) -> np.ndarray:
    """bool [x, y, z]: filled cells with outside air as one of their six neighbours."""
    air = np.zeros((filled.shape[0] + 2, filled.shape[1] + 2, filled.shape[2] + 2), dtype=bool)
    air[1:-1, 1:-1, 1:-1] = outside_air(filled)
    air[[0, -1], :, :] = True
    air[:, [0, -1], :] = True
    air[:, :, -1] = True  # beyond the top; below z = 0 (index 0) is the table
    near = (
        air[:-2, 1:-1, 1:-1]
        | air[2:, 1:-1, 1:-1]
        | air[1:-1, :-2, 1:-1]
        | air[1:-1, 2:, 1:-1]
        | air[1:-1, 1:-1, :-2]
        | air[1:-1, 1:-1, 2:]
    )
    return filled & near


def floor_labels(colors: np.ndarray) -> np.ndarray:
    """int [x, y, z]: which piece each cell is in when every two vertically adjacent cells
    and every two side-by-side cells of one colour are joined; -1 where empty.

    No layout can join cells this does not join (see the layout solver's notes), so a loose
    piece in a different label from the main piece cannot be attached without a change.
    """
    filled = colors != EMPTY
    idx = np.full(colors.shape, -1, dtype=np.int64)
    n = int(filled.sum())
    idx[filled] = np.arange(n)
    rows, cols = [], []
    m = filled[:, :, :-1] & filled[:, :, 1:]
    rows.append(idx[:, :, :-1][m])
    cols.append(idx[:, :, 1:][m])
    for lo, hi in _SIDES:
        m = filled[lo] & filled[hi] & (colors[lo] == colors[hi])
        rows.append(idx[lo][m])
        cols.append(idx[hi][m])
    r, q = np.concatenate(rows), np.concatenate(cols)
    g = coo_matrix((np.ones(len(r)), (r, q)), shape=(n, n))
    _, lab = connected_components(g, directed=False)
    out = np.full(colors.shape, -1, dtype=np.int64)
    out[filled] = lab
    return out


# ---- pieces of a Build ---------------------------------------------------------------------


@dataclass
class _Pieces:
    count: int
    label: np.ndarray  # int [x, y, z]: piece of the part covering each cell, -1 where empty
    main: int  # label of the main piece
    loose: list[int]  # labels of the pieces that are not anchors, biggest first
    parts: list[int]  # parts in each piece, by label
    anchors: list[int] = field(default_factory=list)  # main first, then one per separate object

    def anchored(self) -> np.ndarray:
        """bool [x, y, z]: cells of the anchor pieces (the main piece and separate objects)."""
        return np.isin(self.label, self.anchors)


def _pieces(build: Build, catalog: Catalog) -> _Pieces:
    """The pieces of a build. Each object (a group of filled cells touching each other,
    6-connected) that stands on the ground has an *anchor*: its piece with the most cells
    among those touching the ground. The main piece is the biggest anchor; the others are
    separate objects. Every other piece is loose, and is repaired towards an anchor."""
    occ = occupancy(build, catalog)[0]
    graph = connection_graph(build, catalog, occ)
    comps = [sorted(c) for c in nx.connected_components(graph)]
    of_part = np.full(len(build.parts) + 1, -1, dtype=np.int64)
    ranks = []
    for k, comp in enumerate(comps):
        of_part[comp] = k
        cells = sum(int(np.prod(catalog.footprint(build.parts[i]))) for i in comp)
        grounded = any(build.parts[i].z == 0 for i in comp)
        ranks.append((grounded, cells, -comp[0]))
    label = np.where(occ >= 0, of_part[occ], -1)
    if not comps:
        return _Pieces(0, label, -1, [], [], [])
    covered = label >= 0
    objects, _ = ndimage.label(covered)
    pairs = np.unique(np.stack([label[covered], objects[covered]]), axis=1)
    object_of = dict(zip(pairs[0].tolist(), pairs[1].tolist(), strict=True))
    main = max(range(len(comps)), key=lambda k: ranks[k])
    others: dict[int, int] = {}
    for k in range(len(comps)):
        o = object_of.get(k, -1)
        if not ranks[k][0] or o == object_of.get(main, -1):
            continue
        if o not in others or ranks[k] > ranks[others[o]]:
            others[o] = k
    anchors = [main, *sorted(others.values(), key=lambda k: ranks[k], reverse=True)]
    loose = sorted((k for k in range(len(comps)) if k not in anchors), key=lambda k: ranks[k][1:])
    return _Pieces(len(comps), label, main, loose[::-1], [len(c) for c in comps], anchors)


def _floor_count(colors: np.ndarray) -> int:
    """Pieces of the floor of a Design: fewer than this no layout can reach."""
    lab = floor_labels(colors)
    return int(lab.max()) + 1 if lab.size and lab.max() >= 0 else 0


# ---- repairs -------------------------------------------------------------------------------


@dataclass
class _Spot:
    """One place that came loose, followed from solve to solve."""

    mask: np.ndarray  # cells that were loose here, in any solve
    level: int = -1  # index into _LADDER of the repair in place, -1 for none yet
    change: dict[Cell, int] = field(default_factory=dict)  # cell -> colour given to it
    kind: str = ""  # "recolour" | "thicken" | "support" | "extend" while ``change`` is in place
    tried: list[str] = field(default_factory=list)  # kinds that were applied at some point
    piece: np.ndarray | None = None  # the loose cells when the repair in place was chosen
    column: tuple[bool, bool, bool] = (False, False, False)  # support: hidden, upwards, touched
    carried: bool = False  # left alone last round because another spot's change joined it
    carry_failed: bool = False  # it was carried and still came loose: do not wait again

    def snapshot(self) -> _Spot:
        return _Spot(
            mask=self.mask.copy(),
            level=self.level,
            change=dict(self.change),
            kind=self.kind,
            tried=list(self.tried),
            piece=None if self.piece is None else self.piece.copy(),
            column=self.column,
            carried=self.carried,
            carry_failed=self.carry_failed,
        )


_LADDER: tuple[tuple[str, int], ...] = (
    *(("recolour", d) for d in RECOLOUR_DEPTHS),
    *(("thicken", r) for r in THICKEN_REACH),
    ("support", 0),
    ("extend", 1),
)


def _layer_shift(a: np.ndarray, dx: int, dy: int, fill) -> np.ndarray:
    """``a`` moved by (dx, dy) within each layer: out[x, y] = a[x - dx, y - dy]."""
    out = np.full(a.shape, fill, dtype=a.dtype)
    nx_, ny_ = a.shape[0], a.shape[1]
    xs = slice(max(dx, 0), nx_ + min(dx, 0))
    ys = slice(max(dy, 0), ny_ + min(dy, 0))
    xd = slice(max(-dx, 0), nx_ + min(-dx, 0))
    yd = slice(max(-dy, 0), ny_ + min(-dy, 0))
    out[xs, ys] = a[xd, yd]
    return out


def _grow_in_layers(
    seeds: np.ndarray, colour: np.ndarray, allowed: np.ndarray, steps: int
) -> tuple[np.ndarray, np.ndarray]:
    """Spread from ``seeds`` through ``allowed`` cells, side to side only, ``steps`` times.

    Returns the cells reached (seeds excluded) and, for each, the colour of the seed it was
    reached from (``colour`` is read at the seeds).
    """
    reached = seeds.copy()
    col = np.where(seeds, colour, EMPTY).astype(np.int16)
    for _ in range(steps):
        new_col = np.full(col.shape, EMPTY, dtype=np.int16)
        for dx, dy in _STEPS4:
            moved = _layer_shift(col, dx, dy, EMPTY)
            take = (new_col == EMPTY) & (moved != EMPTY)
            new_col[take] = moved[take]
        new = (new_col != EMPTY) & allowed & ~reached
        if not new.any():
            break
        reached |= new
        col[new] = new_col[new]
    return reached & ~seeds, col


def _recolour(colors, piece, hidden, claimed, depth) -> dict[Cell, int]:
    allowed = hidden & ~piece & ~claimed
    cells, col = _grow_in_layers(piece, colors, allowed, depth)
    cells &= col != colors
    return {(int(x), int(y), int(z)): int(col[x, y, z]) for x, y, z in np.argwhere(cells)}


def _thin(colors: np.ndarray) -> np.ndarray:
    """Cells of a sheet one plate thin: filled, above z = 0, nothing directly above or below."""
    filled = colors != EMPTY
    above = np.zeros(filled.shape, dtype=bool)
    above[:, :, :-1] = filled[:, :, 1:]
    out = np.zeros(filled.shape, dtype=bool)
    out[:, :, 1:] = filled[:, :, 1:] & ~filled[:, :, :-1]
    return out & ~above


def _thicken(colors, piece, claimed, reach) -> dict[Cell, int]:
    thin = _thin(colors)
    start = piece & thin
    # a sheet, or the thin edge of one; a body with a few thin cells somewhere is not
    if not start.any() or THIN_SHARE * piece.sum() > start.sum():
        return {}
    if reach:
        more, _ = _grow_in_layers(start, colors, thin, reach)
        start = start | more
    out: dict[Cell, int] = {}
    for x, y, z in np.argwhere(start):
        cell = (int(x), int(y), int(z) - 1)
        if not claimed[cell]:
            out[cell] = int(colors[x, y, z])
    return out


def _support(colors, piece, claimed, enclosed) -> tuple[dict[Cell, int], tuple[bool, bool, bool]]:
    """A column under the piece down to the first filled cell, and (whether it is hidden,
    whether it goes up, whether the piece touches the model).

    A piece that touches the model somewhere (a nose on a face) is not hanging in the air:
    it gets a column only where the column is hidden or short, never a tall post in view.
    When no column below reaches anything, a column up to the model above is the fallback
    (a part hanging under the model is held by its studs just the same).
    """
    none = (False, False, False)
    if piece[:, :, 0].any():
        return {}, none
    filled = colors != EMPTY
    nz_ = colors.shape[2]
    touches = bool((filled & ndimage.binary_dilation(piece) & ~piece).any())
    xs, ys, _ = np.nonzero(piece)
    cx, cy = xs.mean(), ys.mean()
    best = None
    for x, y in sorted({(int(a), int(b)) for a, b in zip(xs, ys, strict=True)}):
        for z0 in (int(v) for v in np.nonzero(piece[x, y])[0]):
            for step in (-1, 1):
                z = z0 + step
                if not 0 <= z < nz_ or filled[x, y, z]:
                    continue
                while 0 <= z < nz_ and not filled[x, y, z] and not claimed[x, y, z]:
                    z += step
                if z >= nz_ or (z >= 0 and claimed[x, y, z]):
                    continue  # nothing above to hang from, or another repair is in the way
                cells = [(x, y, k) for k in range(min(z, z0) + 1, max(z, z0))]
                hidden = all(enclosed[c] for c in cells)
                if touches and not hidden and len(cells) > SHORT_COLUMN:
                    continue
                d2 = (x - cx) ** 2 + (y - cy) ** 2
                key = (z < 0, step > 0, not hidden, d2, len(cells), x, y, -z0)
                if best is None or key < best[0]:
                    best = (key, cells, int(colors[x, y, z0]), (hidden, step > 0, touches))
    if best is None:
        return {}, none
    _, cells, colour, info = best
    return {c: colour for c in cells}, info


def _extend(colors, piece, claimed) -> dict[Cell, int]:
    """Cells in the piece's colour beside it, in empty cells resting on (or under) the model,
    so a part can reach from the piece over the model's studs."""
    filled = colors != EMPTY
    body = filled & ~piece
    held = np.zeros(filled.shape, dtype=bool)
    held[:, :, 1:] |= body[:, :, :-1]
    held[:, :, :-1] |= body[:, :, 1:]
    cells, col = _grow_in_layers(piece, colors, ~filled & ~claimed & held, 1)
    return {(int(x), int(y), int(z)): int(col[x, y, z]) for x, y, z in np.argwhere(cells)}


def _detail_cells(design: Design, catalog: Catalog) -> np.ndarray:
    """Cells the Design's detail parts stand in: nothing may be added there."""
    out = np.zeros(design.shape, dtype=bool)
    for d in design.details:
        if d.part in catalog.parts:
            p = Placement(part=d.part, color=d.color, x=d.x, y=d.y, z=d.z, rot=d.rot)
            xs, ys, zs = catalog.cells(p)
            out[
                max(xs.start, 0) : xs.stop, max(ys.start, 0) : ys.stop, max(zs.start, 0) : zs.stop
            ] = True
    return out


def _floor_joins(colors: np.ndarray, piece: np.ndarray, target: np.ndarray) -> bool:
    """Whether the piece and the target are one piece on the floor of ``colors``."""
    lab = floor_labels(colors)
    a = np.unique(lab[piece & (lab >= 0)])
    b = np.unique(lab[target & (lab >= 0)])
    return bool(np.intersect1d(a, b).size)


# ---- words ---------------------------------------------------------------------------------


def _span(lo: int, hi: int) -> str:
    return str(lo) if lo == hi else f"{lo} to {hi}"


def _where(cells) -> str:
    a = np.asarray(cells).reshape(-1, 3)
    lo, hi = a.min(axis=0), a.max(axis=0)
    return ", ".join(f"{n}={_span(int(lo[i]), int(hi[i]))}" for i, n in enumerate("xyz"))


def _count(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _colour_name(catalog: Catalog, code: int) -> str:
    c = catalog.colours.get(int(code))
    return c.name if c else f"colour {int(code)}"


def _colours_by_use(colors: np.ndarray, mask: np.ndarray) -> list[int]:
    vals, counts = np.unique(colors[mask & (colors != EMPTY)], return_counts=True)
    order = sorted(range(len(vals)), key=lambda i: (-counts[i], int(vals[i])))
    return [int(vals[i]) for i in order]


def _describe(catalog: Catalog, colors: np.ndarray, mask: np.ndarray) -> str:
    """'the Dark Pink part at x=3 to 4, y=0, z=6 to 8'."""
    names = [_colour_name(catalog, c) for c in _colours_by_use(colors, mask)]
    if len(names) <= 1:
        what = f"the {names[0] if names else 'added'} part"
    elif len(names) == 2:
        what = f"the {names[0]} and {names[1]} parts"
    else:
        what = f"the {names[0]}, {names[1]} and other parts"
    return f"{what} at {_where(np.argwhere(mask))}"


# ---- the pass ------------------------------------------------------------------------------

SLOW_SOLVES = 3  # solves the layout could not bring down to the floor; each costs seconds
SLOW_PATIENCE = 2  # such solves in a row, no better than the best, that end the pass
CARRIED = "carried"  # another spot's change chosen this round joins the piece already
_SHOWN_IF_JOINED = ("recolour", "thicken")  # rungs worth trying when the floor joins already


def _apply(base: Design, spots: list[_Spot]) -> Design:
    out = base.copy()
    assert out.finish is not None
    for s in spots:
        for (x, y, z), colour in s.change.items():
            if out.colors[x, y, z] == EMPTY:
                out.finish[x, y, z] = FINISH_STUDS
            out.colors[x, y, z] = colour
    return out


def _changed(spots: list[_Spot]) -> int:
    return sum(len(s.change) for s in spots)


def _mask(shape: tuple[int, ...], cells) -> np.ndarray:
    out = np.zeros(shape, dtype=bool)
    for c in cells:
        out[c] = True
    return out


def _joins(
    s: _Spot,
    piece: np.ndarray,
    running: np.ndarray,
    start: np.ndarray,
    original: np.ndarray,
    target: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, bool, bool]:
    """The spot's piece and target with its own change taken away, the Design that leaves
    (``without``), whether the floor joined piece and target already in the Design that was
    just solved (``already``), and whether it is *carried*: cells another spot added this
    round stand directly on or under the piece, and it is through them that the floor joins
    it (without them it would not be joined).

    Only a vertical contact counts as carrying: two cells one above the other are always
    held together by whatever parts cover them, while side-by-side cells of one colour,
    which the floor also joins, may never be (a sheet one plate thin)."""
    own = _mask(running.shape, s.change)
    without = running.copy()
    before = (original if s.carry_failed else start).copy()
    for c in s.change:
        without[c] = original[c]
        before[c] = original[c]
    piece = piece & (without != EMPTY)
    target = target & ~own & (without != EMPTY)
    filled = before != EMPTY
    already = _floor_joins(before, piece & filled, target & filled)
    new = (without != EMPTY) & (start == EMPTY)  # cells others added this round
    touching = np.zeros(new.shape, dtype=bool)
    touching[:, :, 1:] |= new[:, :, 1:] & piece[:, :, :-1]  # on top of the piece
    touching[:, :, :-1] |= new[:, :, :-1] & piece[:, :, 1:]  # under it
    carried = False
    if touching.any() and not already and _floor_joins(without, piece, target):
        cut = without.copy()
        cut[touching] = EMPTY
        carried = not _floor_joins(cut, piece, target & ~touching)
    return piece, target, without, already, carried


def _choose(
    s: _Spot,
    piece: np.ndarray,
    running: np.ndarray,
    start: np.ndarray,
    original: np.ndarray,
    spots: list[_Spot],
    target: np.ndarray,
    hidden: np.ndarray,
    enclosed: np.ndarray,
    blocked: np.ndarray,
) -> tuple[int, str, dict[Cell, int], tuple[bool, bool, bool]] | str | None:
    """The cheapest repair beyond the spot's current one that could join the piece to an
    anchor at all (judged on the floor of the Design); CARRIED when cells another spot
    added this round hold it already (see ``_joins``); or None.

    ``running`` holds the changes chosen so far, ``start`` is the Design just solved. When
    the floor joined the piece already in ``start`` (a sheet of one colour, or a place
    where the layout fell short), the floor cannot tell whether a change helps, so only the
    invisible recolour and the plate beneath a thin sheet are offered, never a column or
    cells beside it."""
    claimed = _mask(running.shape, (c for o in spots if o is not s for c in o.change))
    piece, target, without, already, carried = _joins(s, piece, running, start, original, target)
    if not piece.any():
        return None
    if carried and not s.carry_failed:
        return CARRIED
    for level in range(s.level + 1, len(_LADDER)):
        kind, amount = _LADDER[level]
        if already and kind not in _SHOWN_IF_JOINED:
            continue
        info = (False, False, False)
        if kind == "recolour":
            change = _recolour(without, piece, hidden, claimed, amount)
        elif kind == "thicken":
            change = _thicken(without, piece, claimed | blocked, amount)
        elif kind == "support":
            change, info = _support(without, piece, claimed | blocked, enclosed)
        else:
            change = _extend(without, piece, claimed | blocked)
        if not change or change == s.change:  # the same Design again would tell nothing new
            continue
        trial = without.copy()
        for c, colour in change.items():
            trial[c] = colour
        if _floor_joins(trial, piece, target):
            return level, kind, change, info
    return None


def make_buildable(
    design: Design, catalog: Catalog, seed: int = 0, max_solves: int = 12
) -> BuildableResult:
    from bricksnap.layout import solve

    nothing = np.zeros(design.shape, dtype=bool)
    build = solve(design, catalog, seed=seed)
    solves = 1
    pc = _pieces(build, catalog)
    pieces_before = pc.count
    if pc.count <= 1:
        return BuildableResult(
            design.copy(), build, nothing, nothing.copy(), [], pc.count, pc.count
        )

    original = design.colors
    hidden = design.filled & ~visible_cells(design.filled)
    blocked = _detail_cells(design, catalog)
    spots: list[_Spot] = []
    work = design
    best = (pc.count, 0, work, build, pc, [s.snapshot() for s in spots])
    slow = int(pc.count > _floor_count(work.colors))
    stale = 0  # slow solves in a row that were no better than the best
    ran_out = False

    while pc.count > 1:
        if solves >= max_solves or slow >= SLOW_SOLVES:
            ran_out = True
            break
        target = pc.anchored()
        start = work.colors
        enclosed = (start == EMPTY) & ~outside_air(work.filled)
        # the loose pieces, gathered by the spot they belong to
        groups: dict[int, np.ndarray] = {}
        for lab in pc.loose:
            piece = pc.label == lab
            k = next((i for i, s in enumerate(spots) if (s.mask & piece).any()), None)
            if k is None:
                spots.append(_Spot(mask=piece.copy()))
                k = len(spots) - 1
            spots[k].mask |= piece
            groups[k] = groups[k] | piece if k in groups else piece
        for k, s in enumerate(spots):
            s.carry_failed |= s.carried and k in groups
            s.carried = False
            if stale and k in groups and s.kind:
                # its repair made things no better and the layout struggled: rather than the
                # same kind of repair a little bigger (each try costs seconds), the next kind
                s.level = max(i for i, (kind, _) in enumerate(_LADDER) if kind == s.kind)
        prior = [s.snapshot() for s in spots]
        running = start.copy()
        chosen: list[int] = []
        done: set[int] = set()
        # a piece may only become joinable once another one has its repair, so look twice
        for second_look in (False, True):
            for k, piece in groups.items():
                if k in done:
                    continue
                s = spots[k]
                choice = _choose(
                    s, piece, running, start, original, spots, target, hidden, enclosed, blocked
                )
                if not isinstance(choice, tuple) and not second_look:
                    continue
                done.add(k)
                for c in s.change:
                    running[c] = original[c]
                if not isinstance(choice, tuple):
                    if choice == CARRIED:
                        s.carried = True
                    elif s.tried:  # nothing left to try here
                        s.level = len(_LADDER)
                    s.change, s.kind = {}, ""
                    continue
                s.level, s.kind, s.change, s.column = choice
                s.piece = piece & (running != EMPTY)
                for c, colour in s.change.items():
                    running[c] = colour
                if s.kind not in s.tried:
                    s.tried.append(s.kind)
                chosen.append(k)
        # cells added early in the round may hold nothing once a later change is in place
        for k in chosen:
            s = spots[k]
            if s.kind in ("", "recolour") or s.carry_failed:
                continue
            _, _, without, _, carried = _joins(s, groups[k], running, start, original, target)
            if carried:
                running = without
                old = prior[k]
                s.change, s.kind, s.level, s.tried = {}, "", old.level, old.tried
                s.piece, s.column, s.carried = old.piece, old.column, True
        changed = any(
            s.change != (prior[k].change if k < len(prior) else {}) for k, s in enumerate(spots)
        )
        if not changed:
            break
        work = _apply(design, spots)
        build = solve(work, catalog, seed=seed)
        solves += 1
        pc = _pieces(build, catalog)
        struggled = pc.count > _floor_count(work.colors)
        slow += struggled
        improved = pc.count < best[0]
        key = (pc.count, _changed(spots))
        if key < best[:2]:
            best = (*key, work, build, pc, [s.snapshot() for s in spots])
        stale = stale + 1 if struggled and not improved else 0
        if stale >= SLOW_PATIENCE:
            break  # the layout cannot get further, and every try like this costs seconds

    if best[1]:
        best, solves, slow = _prune(design, best, catalog, seed, solves, slow, max_solves)

    n_best, _, work, build, pc, kept = best
    recoloured = design.filled & (work.colors != original)
    added = work.filled & ~design.filled
    notes = _notes(catalog, work, pc, spots, kept, ran_out, original, hidden)
    result_design = work.copy() if work is design else work
    return BuildableResult(result_design, build, recoloured, added, notes, pieces_before, n_best)


def _prune(
    design: Design,
    best: tuple,
    catalog: Catalog,
    seed: int,
    solves: int,
    slow: int,
    max_solves: int,
) -> tuple[tuple, int, int]:
    """Take away what the best repairs do not need, judged by the solver: each smaller
    version is solved and kept when it has no more pieces. Returns the new best and the
    solve counts.

    - Recoloured cells that no part used to join them to cells of the same colour get their
      colour back: the first repair recolours every hidden cell beside the loose piece, and
      the solver usually needs only some of them.
    - Cells added for a piece that is still loose go, and so do cells added for a joined
      piece that hold nothing: with them taken out of the build (a part that reaches beyond
      them shrinks to the cells it keeps, and holds only through those), no piece splits.
      Spots are judged one after another, biggest first, since two repairs may each hold
      the same piece and only one of them can go.
    All of that is tried at once; if that is worse, the recolouring alone and then each of
    those spots alone. Then every other spot's added cells are tried without, one spot at a
    time, biggest first: the build may lean on cells that a fresh layout does not need (a
    part beside the piece can reach it as well), which only a solve can show. A try that is
    worse and was slow ends it, and the pass's limits on solves hold throughout."""
    from bricksnap.layout import solve

    _, _, work, build, pc, kept = best
    recoloured = design.filled & (work.colors != design.colors)
    used = np.zeros(design.shape, dtype=bool)
    for p in build.parts:
        if p.part not in catalog.parts:
            continue
        cells = catalog.cells(p)
        here = recoloured[cells]
        if here.any() and not here.all():
            used[cells] |= here
    occ = occupancy(build, catalog)[0]
    whole_build = _held(occ, np.zeros(design.shape, dtype=bool))
    piece_of = {n: k for k, comp in enumerate(nx.connected_components(whole_build)) for n in comp}
    anchored = pc.anchored()
    sure: list[int] = []
    others: list[int] = []
    gone = np.zeros(design.shape, dtype=bool)  # added cells taken out so far
    adding = [i for i, s in enumerate(kept) if s.kind in ("thicken", "support", "extend")]
    # biggest first; columns out of sight last, since nobody sees them
    adding.sort(
        key=lambda i: (kept[i].kind == "support" and kept[i].column[0], -len(kept[i].change), i)
    )
    for i in adding:
        s = kept[i]
        piece = (s.piece if s.piece is not None else s.mask) & work.filled
        if not anchored[piece].any():
            sure.append(i)
            continue
        trial = gone | _mask(design.shape, s.change)
        rest = _held(occ, trial)
        if nx.number_connected_components(rest) <= len({piece_of[n] for n in rest}):
            sure.append(i)
            gone = trial
        else:
            others.append(i)

    def version(spots: list[_Spot], drop: set[int], trim: bool) -> list[_Spot]:
        out = [s.snapshot() for s in spots]
        for i, s in enumerate(out):
            if i in drop:
                s.change, s.kind = {}, ""
            elif trim and s.kind == "recolour":
                s.change = {c: v for c, v in s.change.items() if used[c]}
                if not s.change:
                    s.kind = ""
        return out

    first = (set(sure), True)
    fallback = [(set(), True), *(({i}, False) for i in sure)]
    queue = [first]
    rest_steps = [({i}, False) for i in others]
    current = kept
    while queue or rest_steps:
        step = queue.pop(0) if queue else rest_steps.pop(0)
        if solves >= max_solves or slow >= SLOW_SOLVES:
            break
        spots = version(current, *step)
        if _changed(spots) == _changed(current):
            if step is first:
                queue = fallback
            continue
        trial = _apply(design, spots)
        tb = solve(trial, catalog, seed=seed)
        solves += 1
        tp = _pieces(tb, catalog)
        struggled = tp.count > _floor_count(trial.colors)
        slow += struggled
        if tp.count <= best[0]:
            best = (tp.count, _changed(spots), trial, tb, tp, spots)
            current = spots
        elif struggled:
            break
        elif step is first:
            queue = fallback
    return best, solves, slow


def _held(occ: np.ndarray, removed: np.ndarray) -> nx.Graph:
    """The parts of a build that keep a cell outside ``removed``, joined where a cell of one
    lies directly on a cell of another and neither cell is removed. (Bricks and plates have
    studs over their whole top, so this is the build's connection graph when nothing is
    removed.)"""
    lo, hi = occ[:, :, :-1], occ[:, :, 1:]
    keep = (lo >= 0) & (hi >= 0) & (lo != hi) & ~removed[:, :, :-1] & ~removed[:, :, 1:]
    g = nx.Graph()
    g.add_nodes_from(int(v) for v in np.unique(occ[(occ >= 0) & ~removed]))
    g.add_edges_from((int(a), int(b)) for a, b in zip(lo[keep], hi[keep], strict=True))
    return g


_TRIED_WORDS = {
    "recolour": "recolouring hidden cells next to it",
    "thicken": "adding a plate beneath it",
    "support": "a support column beneath it",
    "extend": "adding cells beside it on top of the model",
}


def _why_nothing(colors: np.ndarray, group: np.ndarray, hidden: np.ndarray) -> str:
    """Why no repair could even be tried for a group of loose pieces that touch each other,
    with what a person could do. Every filled cell beside the group belongs to an anchor
    (the main piece or a separate object), since the group holds every loose piece it
    touches."""
    filled = colors != EMPTY
    other = filled & ~group
    side = np.zeros(filled.shape, dtype=bool)
    for dx, dy in _STEPS4:
        side |= _layer_shift(group, dx, dy, False)
    side &= other
    vertical = np.zeros(filled.shape, dtype=bool)
    vertical[:, :, 1:] |= group[:, :, :-1]
    vertical[:, :, :-1] |= group[:, :, 1:]
    vertical &= other
    grounded = bool(group[:, :, 0].any())
    or_stand = "" if grounded else ", or give it something to stand on"
    if not side.any() and not vertical.any():
        return (
            "It touches nothing, and no column straight down or up from it would reach the model."
        )
    if grounded and not vertical.any() and not group[:, :, 1:].any():
        return (
            "It is one plate thin and lies on the ground, where nothing can be added beneath "
            "it, and parts side by side in one layer do not hold each other. To join it, make "
            "it two plates thick, or build something on it that reaches across from the rest "
            "of the model."
        )
    same = np.zeros(filled.shape, dtype=bool)  # its cells beside a cell of the same colour
    for dx, dy in _STEPS4:
        beside = _layer_shift(colors, -dx, -dy, EMPTY)
        same |= group & (beside == colors) & _layer_shift(side, -dx, -dy, False)
    if same.any():
        return (
            "It meets the rest of the model in its own colour only at "
            f"{_where(np.argwhere(same))}, and no part can cover both sides there and still "
            f"hold on to the rest. To join it, make that contact wider{or_stand}."
        )
    if side.any() and not vertical.any() and not (side & hidden).any():
        return (
            "It touches the rest of the model only at its side, and every cell it touches "
            "there can be seen, so none of them could take its colour without changing the "
            f"look. To join it, paint a cell it touches in its colour{or_stand}."
        )
    contact = side | vertical
    bits = [
        "giving the hidden cells beside it its colour would not join it to the model"
        if (contact & hidden).any()
        else "no hidden cell beside it could take its colour",
        "no plate could be added beneath it"
        if (group & _thin(colors)).sum() >= THIN_SHARE * group.sum()
        else "it is not a thin sheet",
        "it stands on the ground" if grounded else "no column beneath it would reach the model",
    ]
    return f"Nothing could be changed to hold it: {bits[0]}, {bits[1]}, and {bits[2]}."


def _notes(
    catalog: Catalog,
    work: Design,
    pc: _Pieces,
    spots: list[_Spot],
    kept: list[_Spot],
    out_of_solves: bool,
    original: np.ndarray,
    hidden: np.ndarray,
) -> list[str]:
    """What is still loose, then the separate objects, then what was added, then what was
    recoloured.

    Loose pieces that touch each other are one note. ``spots`` say what was tried; ``kept``
    are the same spots as they were in the Design that is returned, with its changes.
    """
    colors = work.colors
    groups, n_groups = ndimage.label(np.isin(pc.label, pc.loose))
    found = []
    for g in range(1, n_groups + 1):
        group = groups == g
        labs = [int(v) for v in np.unique(pc.label[group])]
        first = tuple(int(v) for v in np.argwhere(group)[0])
        found.append((-int(group.sum()), first, group, labs))
    found.sort(key=lambda t: t[:2])
    loose_notes: list[str] = []
    for _, _, group, labs in found:
        what = _describe(catalog, original, group)
        parts = _count(sum(pc.parts[k] for k in labs), "part", "parts")
        if len(labs) > 1:
            parts += f" in {len(labs)} pieces that touch but do not hold each other"
        near = [s for s in spots if (s.mask & group).any()]
        tried = [_TRIED_WORDS[k] for k in _TRIED_WORDS if any(k in s.tried for s in near)]
        if tried:
            joined = f"{', '.join(tried[:-1])} and {tried[-1]}" if len(tried) > 1 else tried[0]
            why = f"{joined} were tried" if len(tried) > 1 else f"{joined} was tried"
            why = f"{why[0].upper()}{why[1:]}, but the layout still could not hold it."
        elif out_of_solves:
            why = "The pass ran out of attempts before it could try anything here."
        else:
            why = _why_nothing(colors, group, hidden)
        loose_notes.append(f"Still loose: {what} ({parts}). {why}")
    for lab in pc.anchors[1:]:
        what = _describe(catalog, original, pc.label == lab)
        parts = _count(pc.parts[lab], "part", "parts")
        verb = "stand" if " parts at " in what else "stands"
        loose_notes.append(
            f"{what[0].upper()}{what[1:]} ({parts}) {verb} on the ground apart from the rest "
            "of the model and touches nothing of it, so it was left as a separate object."
        )

    added_notes: list[tuple[int, str]] = []
    recolour_notes: list[tuple[int, str]] = []
    sheet: dict[Cell, int] = {}
    for s in kept:
        if not s.change:
            continue
        n = len(s.change)
        values = list(s.change.values())
        colour = _colour_name(catalog, max(set(values), key=values.count))
        piece = s.piece if s.piece is not None else s.mask
        what = _describe(catalog, original, piece)
        where = _where(list(s.change))
        if s.kind == "recolour":
            text = (
                f"Recoloured {_count(n, 'hidden cell', 'hidden cells')} at {where} {colour} "
                f"so that {what} beside {'it' if n == 1 else 'them'} "
                f"{'are' if ' parts at ' in what else 'is'} held from inside."
            )
            recolour_notes.append((n, text))
        elif s.kind == "thicken":
            sheet.update(s.change)
        elif s.kind == "extend":
            text = (
                f"Added {_count(n, colour + ' cell', colour + ' cells')} at {where} beside "
                f"{what}: it touched the model only at its side, and now reaches over the "
                "model's studs."
            )
            added_notes.append((n, text))
        else:
            hidden_column, up, touched = s.column
            place = "hidden inside the model" if hidden_column else "where it can be seen"
            column = f"Added a column of {_count(n, colour + ' cell', colour + ' cells')}"
            if up:
                why = (
                    "it touched the model only at its side"
                    if touched
                    else "it hung in the air with nothing beneath it to stand on"
                )
                text = (
                    f"{column} at {where} ({place}) above {what}, up to the model so that it "
                    f"hangs from it: {why}."
                )
            else:
                why = (
                    "it touched the model only at its side and had nothing beneath it"
                    if touched
                    else "it hung in the air with nothing beneath it"
                )
                text = f"{column} at {where} ({place}) under {what}: {why}."
            added_notes.append((n, text))
    # one note per level and colour of added plate, however many loose pieces needed it
    by_level: dict[tuple[int, int], list[Cell]] = {}
    for c, colour in sorted(sheet.items()):
        by_level.setdefault((c[2], colour), []).append(c)
    for (_, code), cells in sorted(by_level.items()):
        colour = _colour_name(catalog, code)
        n = len(cells)
        text = (
            f"Added {_count(n, colour + ' cell', colour + ' cells')} under the sheet at "
            f"{_where(cells)}: it was one plate thin and nothing held that part of it."
        )
        added_notes.append((n, text))
    added_notes.sort(key=lambda t: -t[0])
    recolour_notes.sort(key=lambda t: -t[0])
    return loose_notes + [t for _, t in added_notes] + [t for _, t in recolour_notes]
