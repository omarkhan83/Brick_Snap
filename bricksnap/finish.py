"""Build to Build: swap plain parts for better-looking ones and put the detail parts on.

This pass is where a model stops looking like a staircase of bricks: tiles make smooth tops,
slopes take the corners off steps, and small detail parts stand on free studs.

CONTRACT (tests go in tests/test_finish.py)

``finish(build, design, catalog) -> Build``

``build`` is what ``bricksnap.layout.solve`` made from ``design``: bricks and plates only,
covering exactly the Design's filled cells. The input Build is not changed. The result
covers exactly the same cells, possibly with different parts, plus the Design's detail parts
standing in cells that were empty. ``result.shape`` and ``result.design_id`` are copied from
the input, ``result.report`` is None (the caller runs the checks), and ``result.notes`` is the
input's notes followed by this pass's own (see "Notes" below).

Words used below
- A cell is *open* when it is filled, the cell above it is empty (or it is in the top layer
  of the grid), and no detail part stands on it.
- A part's *stud cells* are the cells returned by ``Catalog.stud_cells``. A tile has none. A
  45-degree slope has them only on its high side.
- A slope part's *slanted cells* are the columns of its footprint that carry no stud. Its
  *downhill direction* is ``Catalog.low_side(placement)``, a grid direction (dx, dy).

1. Detail parts. For each entry of ``design.details``, in order, add a Placement when all of
   the following hold; otherwise skip it and add a note naming the part, its position and
   the reason.
   - The (part, colour) pair exists in the catalogue (``Catalog.exists``).
   - Every cell it covers (``Catalog.cells``) is inside the grid, empty in the Design, and
     not taken by an earlier detail.
   - Directly below every cell of its bottom layer there is a filled cell, and the part
     covering that cell has a stud there.
   - The detail part can grip studs from above (``Part.antistuds_bottom``).
   - No filled cell of the Design sits directly on top of the detail (the part above would
     have to be built before the detail it rests on).
   The cells below a placed detail must still carry studs when this pass is done, so the
   detail really holds: steps 2 and 3 never put a tile or a slanted face under a detail.

2. Tiles. Every open cell whose ``design.finish`` is FINISH_SMOOTH should end up as part of
   a part of kind "tile" (never the grille tile 2412b; that is a detail part).
   - Where the open cells belong to a plate, the plate is swapped for tiles over its smooth
     open cells and plates over the rest.
   - Where they belong to a brick, the brick is swapped for two levels of plates with a
     level of tiles (and plates over cells that are not smooth and open) on top.
   - Use the largest tiles that fit; tiles exist in fewer sizes than plates.

3. Slopes. Every open cell whose finish is FINISH_SLOPED should end up as a slanted cell of
   a slope part, where one fits. A slope Placement P fits when:
   - every cell P covers is filled with P's colour, and the (part, colour) pair exists;
   - in each slanted column, P's top cell is open and its finish is FINISH_SLOPED;
   - downhill is clear: for each footprint cell on P's low edge, the neighbouring cell in
     the downhill direction is empty (or outside the grid) at every level of P above its
     bottom level. The bottom level may be filled: the slope's lip rests against it.
   Parts to use: 3040b and 3039 (45 degrees, three plates tall, one row of studs on the
   high side), 54200 and 85984 (cheese slopes, two plates tall, no studs). 4286 and 11477
   may be used where they fit; 3665b (inverted) is not used by this pass.
   Preferences: a slope three plates tall before a cheese slope where both fit; a two-wide
   part before two one-wide parts. When a cell could slope in more than one direction:
   first the direction with the bigger drop at the low edge, counted only up to the slope's
   own height (a staircase must slope down its steps, not off its sides, although the
   sides drop all the way to the ground); then a direction in which the surface rises
   behind the slope; then the bigger full drop. Break ties the same way every time.
   A slope is never placed with its stud on an open cell marked smooth: the tile wanted
   there would be lost.
   A cheese slope stands on a plate: a brick whose top is to carry one is swapped for a
   plate with the cheese slope on it.

4. Whatever a swap displaces is covered again. A swap takes whole existing parts out and
   puts back parts covering exactly the same cells: the tiles or slopes wanted, and bricks
   or plates (existing pairs only) for the cells left over. Parts of the input that already
   collide, stick out of the grid, are unknown, or are not bricks or plates are left alone.

5. Nothing is ever made worse. Compared with the input:
   - the same cells are covered (apart from detail cells), each by exactly one part, in the
     same colour;
   - ``connect.occupancy`` reports no collision, nothing out of bounds and no unknown pair
     that the input did not already have;
   - the number of connected pieces (``connect.connection_graph``) has not gone up, and no
     part that was in the main piece has left it. A swap that would break this is not made
     (or is undone). When the wanted part does not exist in the cell's colour, the cell is
     left as it is; never substitute another colour.

6. Steps. A new part takes the step of the part it replaces (the latest, if it replaces
   cells of several). Detail parts come after everything else, in new steps of up to eight,
   ordered by z, then y, then x. No part has an earlier step than a part it stands on, and
   the steps used are 1..n with none missing.

Notes
- First, one sentence saying how many tiles, slopes and detail parts were placed. If every
  open smooth cell got a tile and every open sloped cell a slanted face, that is all.
- Otherwise, one sentence per reason a cell marked smooth kept its stud or a cell marked
  sloped got no slope, each saying how many cells and where (the box around them, "x=… to
  …, y=… to …, z=… to …", or the one cell; cells in several separate places get up to three
  boxes). The AI designer reads these after each rebuild and must be able to decide from
  the sentence alone whether to try something else, so each says what would change it:
  * a detail part stands on the cell, so it keeps its stud (as it should, not a failure);
  * the surface does not step down beside it (a flat top marked sloped): mark it "smooth"
    for a tile or "studs" to stop asking;
  * the step beside it is too small for the slope parts made in its colour, or the model
    is too thin there (fewer plates of one colour under it than any slope part is tall);
  * the part that would fit is not made in that colour (naming the colour and the part);
  * a tile or slope there would let go of parts held on only through this cell, so part
    of the model would come loose: making that part thicker or joining it more firmly
    could change that;
  * a tile or slope there would leave N parts hanging on a single part (the stage 3 rule
    below; N is the fewest the swaps refused for the cell would have left, each measured
    on its own; "up to N" when the cells of one sentence differ), with the same advice;
  * the same, but said of the tile or slope "with the others tried around it at the same
    time": on a large build the pass may not afford to measure every refused swap on its
    own, and then N is what the swaps refused with it left between them;
  * it is the high side of a slope placed next to it, which carries the slope's studs;
  * every slope that fits there overlaps a slope placed beside it, which was preferred;
  * anything else: no part fits there.
  The reason is the one the pass established for that cell, never a guess: a swap it tried
  and had to refuse comes first, then how far the closest slope part got through the tests
  of section 3. At most six such sentences, biggest first; past that the smallest groups
  are merged into "And N more cells in other places were left as they were."
- Then one sentence per skipped detail. All in plain words with coordinates ("x=…, y=…,
  z=…"), because the AI designer and people read them. No note at all when there was
  nothing to do.
- Only the notes depend on the reasons: the parts, steps and order are the same as if no
  reason were looked for.

Other
- A Design with no smooth or sloped cells and no details gives back a Build equal to the
  input (same parts, same order, same steps).
- Deterministic. Speed: a 3,000-part build in under 5 seconds.
- This module may use ``bricksnap.connect`` and ``bricksnap.catalog``. It does not call the
  layout solver or the checks.

STAGE 3 ADDITION TO THE CONTRACT: finishing never makes a build less sturdy
Section 5 only forbids loosening a part. That is not enough: in the sample pawn at 16
studs the solver's build has at most 6 parts hanging on any one part, and after finishing
48 parts hang on a single 2 x 2 plate, because swaps cut bricks that tied two sections
together into smaller parts.

- The measure is the solver's: a *lone link* is a part, or a joint engaging a single stud,
  that is a group's only connection to the rest of the model, and its *load* is what it
  carries (see ``bricksnap.connect``, which agrees with the weak spots that bricksnap.checks
  reports). The solver and this pass share that one definition:
  ``connect.lone_links(build, catalog)`` and ``connect.sturdiness(build, catalog)``;
  ``bricksnap.layout`` keeps its two names as aliases.
- Splitting a brick into plates, tiles and a slope must not count against a swap by
  itself. So both builds are *seen as the input's parts*: each part stands for the input
  parts whose cells it covers (a detail part, which covers none, for itself); when the part
  a lone link hangs on was cut from a single input part, its group leaves out the other
  pieces of that input part (a brick cut into plates and a tile hangs on its own bottom
  plate, and that is still the one brick); groups of the same input parts are one; a group
  holding fewer than 3 input parts is not a lone link; and its load in cells is the cells
  of the parts left in it (``LoneLink.cells`` before leaving any out). On the input this is
  simply its lone links.
- The rule, added to section 5: compared with the input (with the detail parts standing on
  it, since they stand there either way), both seen as the input's parts, the result's
  largest load in cells is no higher and it has no more lone links. A swap that would break
  the rule is not made, or is undone, exactly like a swap that would loosen something.
- Not promised: the weak spots the checks report count every lone link in finished parts,
  so their number and their largest load can go up after finishing, because a brick cut
  into plates and a tile is a lone link of its own wherever it carries two parts or stands
  on a single part. Counted that way, no tile could go on the cat's back at 12 studs, which
  tests/test_stage2.py asks for. (Decided by the lead, 2026-11-16: a brick cut into a
  plate and a tile is still one brick for this rule.)
- The notes gain a reason for cells left alone because of it: "a tile (or slope) there
  would leave N parts hanging on a single part" (N counted in the input's parts, as above),
  with the place, and the same advice as for parts that would come loose.
- Everything else about the pass is unchanged: on a build where no swap threatens
  sturdiness, the result is exactly what it was before this addition.
- Speed: a 3,000-part build still under 5 seconds.
- Measured on the scorecard at 16 studs: seen as the input's parts, no sample model is less
  sturdy after finishing than the solver's own build was. Counted as the checks count
  (every lone link, in finished parts), the worst weak spot of the duck and the pineapple
  carries two parts more, of the pawn and the teapot one more, and the pawn's covers 21
  cells where the solver's covered 16 (a 2 x 4 plate cut from a brick, carrying the rest of
  that brick, two plates of another and a slope); every model's weak spot total is below
  the saved scorecard's: 148 over the eleven models, against 219 there and 124 in the
  solver's own builds.

Implementation notes
--------------------
The pass keeps a working state: parts by id, an array saying which part covers each cell, an
array of where the studs are, and the connection graph as adjacency sets, built once with
``connect.connection_graph`` and then kept up to date by hand with the same rule.

Every change is one *swap*: a wanted part (a slope or a tile) goes in, every part that covers
any of its cells comes out, and what those parts leave is covered again (section 4). For a
brick there are two ways to cover the rest, tried in order: "bricks" (columns left whole stay
bricks, the rest becomes plates level by level) and "plates" (level by level, so the lowest
level is one plate of the brick's whole footprint, which keeps the brick's grip on everything
under it). 45-degree slopes try "bricks" first; cheese slopes and tiles use "plates", which is
the contract's "two levels of plates with tiles on top". Rectangles are the largest that
exist in the colour, taken greedily from the first free cell.

A swap (one wanted part, or several tiles going in together) is kept only if the model still
holds together. Quick test: the new parts and every part the removed ones touched are joined
to each other by the new parts' own connections. If not, they fall into a few groups, and a
search outwards from every group at once (one part per group in turn, merging groups whose
searches meet) decides: yes when one group is left, no as soon as one group's search runs out.
A refusal so costs about the size of the piece that would come loose, not the whole model.
Either way, every piece that existed stays one piece, so the number of pieces never goes up
and the main piece never loses a part. Otherwise the swap is undone exactly.

Slopes. Candidate placements are found for all slope parts at all rotations at once with
array tests (section 3, using ``Catalog.footprint``, ``stud_cells`` and ``low_side`` only),
then tried best first. The order is: three plates tall before cheese slopes; two-wide before
one-wide; then, for the direction, the drop beside the low edge *capped at the slope's own
height*, then whether the surface rises behind the slope (the cell behind its low edge, one
level above its top, is filled), then the full drop, then more slanted cells, then position.
The cap and the "rises behind" test are a refinement of "the direction in which the surface
drops furthest": without them a free-standing staircase or the edge of a model slopes off its
sides, because the side of any model drops all the way to the ground. A slope is never placed
with a stud on a cell that wants a tile. One class of slope at a time (by height and width) is
tried, and a candidate refused because it would loosen something is tried again (up to three
rounds) while others of its class are still going in, since a neighbour's swap can make it
safe; only then do lesser parts get those cells.

Tiles. First every part whose whole top is wanted smooth gets one tile of its own size, if one
exists (always safe: the tile sits on what the part sat on). The remaining smooth cells are
covered layer by layer with the largest tiles; a tile that is refused is retried. Where tiles
are still refused (typically on a slab two plates thick, where the largest tiles straddle the
top plates and no longer cross the joints between the plates underneath), each part under a
refused tile has its wanted top cells tiled on its own, as one swap: several greedy tilings
are tried (largest tiles first, longest along x first, longest along y first, each scanned
from all four corners), fewest tiles first, and the first the model holds with is kept.
Only what is refused after that is tried cell by cell with 1x1 tiles. A plate that stands
alone (its own piece) and has no tile of its size cannot become tiles at all: two tiles side
by side would be two pieces.

Details. Beyond the contract's conditions, a detail is also skipped (with a note) when the
part under it has no stud there, when the part has nothing underneath that grips studs
(11477), and when a filled cell of the Design sits directly on top of it: a part resting on a
detail would have to come before it, which section 6 forbids.

Steps. New parts take the latest step of the cells they replace; then, bottom up, a part's
step is raised to that of any part directly under it; steps are renumbered 1..n; details
follow in groups of eight. Parts are returned in step order.

Reasons. While the pass works it records, per cell, whether it was the slanted cell of any
slope candidate, whether the tile plan covered it, and whether a swap that wanted it was
refused because the model would come loose (``_State.refusal`` says why the last swap was
refused) or for another reason. At the end each cell left as it was is sorted, in this
order: a detail stands on it; it carries the studs of a slope placed beside it; a swap for
it was refused as loosening; one was refused by the stage 3 rule; a candidate was refused
for another reason ("no part fits"); a candidate existed but each overlapped a slope
already placed. A smooth cell no planned tile covered has no tile in its colour.
A sloped cell with no candidate at all goes through ``_no_slope_reasons``: a flat top if all
four neighbours at its level are filled; otherwise every slope part at every rotation and
position that would slant it is run through the candidate tests one at a time (own column
tall enough, footprint filled and changeable, other cells sloped, face clear at the top,
step deep enough), and the furthest any part gets is the reason, a part that passes them
all but is not made in the colour giving the colour reason. This runs only on the cells
left, after the build is decided, so it cannot change it.

Sturdiness. The pass first runs exactly as it did before the stage 3 rule and measures its
result once (``connect.lone_links`` on the result against the input with the details): if the
rule holds, that is the result, so a build no swap threatens comes out as before. Otherwise it
runs again, holding each *class* of swaps to the rule as it goes: each class of slopes (by
height and width, as above), then the tile plan, the per-part tilings and the 1x1 tiles.
Measuring after every swap would be too slow for 3,000 parts (each measure looks at the whole
build), so a class runs freely and is measured once at its end, from a snapshot of the state
taken at its start. When the class broke the rule:
- Rounds: the groups that break the rule (heavier than the input's heaviest, or, when there
  are too many, not one of the input's) are traced to the class's swaps whose new parts are
  the part or joint they hang on, or else cut through their group (new parts inside it and
  outside), or else lie in it, or else the swap nearest; those swaps are refused, and so is
  any other swap of the class wanting the same faces (a slope turned another way does the
  same harm), and the class runs again from the snapshot. After ``_STURDY_ROUNDS`` rounds,
  one round refuses all the swaps that could be to blame; if the rule still does not hold,
  every swap of the class is refused and the state goes back to the snapshot.
- Then, since the rounds refuse more than the rule needs, the class runs once more from where
  the rounds left it, with their refusals lifted: only the swaps they refused can be made
  now, and each is measured as it is made and undone if the build breaks the rule (a swap of
  a brick tries its other way of covering the rest first). The note for one still refused
  says how many parts it alone would have left hanging: the largest of the groups it made or
  changed, compared with the build just before it. This happens only when measuring every
  swap the rounds refused fits what is left of ``_MEASURE_BUDGET`` (parts measured, summed
  over the pass; twice their measuring must fit, since a swap may be tried more than once);
  a swap that cannot be measured when its turn comes stays refused. Where it does not fit
  (very large builds), the rounds' refusals stand and their notes say "with the others tried
  around it at the same time".
So the time is bounded: each class runs at most ``_STURDY_ROUNDS`` + 4 times and is measured
once per run, and the swap-by-swap measuring is capped by the budget (under a second). At 24
studs the pass keeps 762 slopes over the eleven sample models, against 769 with no limit on
measuring (only the duck, at 1,360 parts, cannot afford all its retries). Judging every swap
on its own from the start, as this pass once did where it could, kept fewer on the larger
builds: what one swap uses up of the rule, the next cannot use. On the 153 x 153 slab two
plates thick (about 3,000 parts, where almost every tile threatens the rule) the pass takes
about 3.5 seconds.
While it works the pass measures its own state (``_State.lone_links``): the same search,
``connect.lone_links_of_graph``, fed from the state's cells and studs with the parts numbered
in the order of the result, which gives exactly what ``connect.lone_links`` gives on the
result (the tests check this). It leaves out what parts the input already had problems with
hold (a part sticking out of the grid still holds the parts on its studs inside it), so when
the input has such parts the pass measures with ``connect.lone_links`` itself.
A refused swap's faces are marked with the parts it would have left hanging (the fewest, if
several were refused for a cell); a marked cell left as it was gets the sturdiness reason,
after the loosening one.

Safety net. At the end the result is checked against section 5 with ``bricksnap.connect``
itself, and, in the run that holds swaps to the stage 3 rule, against that rule with
``connect.lone_links``. If either ever failed (it never has in the tests, which make
``_fell_back`` fail), the input parts are returned with the details only, rather than a worse
build. Parts the input already had problems with (collisions, out of the grid, unknown, or not
a brick or plate) are never swapped.

STAGE 4 ADDITION TO THE CONTRACT: sideways parts
A detail with ``face`` other than "top" lies on a face of the model, pushed onto the side
stud of the brick that the solver pinned directly behind its column (see
``bricksnap.buildable.side_stud_pins`` and ``Placement``).
- Section 1 for such a detail: it is added as ``Placement(part, colour, x, y, z, 0,
  face=face)`` when the pair exists, the part may face sideways
  (``Catalog.can_face_sideways``) with rot 0, its column of three cells is inside the grid,
  empty in the Design and not taken by an earlier detail, and the part covering the cell
  directly behind the bottom of its column is upright, starts at the same z and has a side
  stud on that face (``Catalog.side_stud_faces``). The conditions about standing on studs,
  gripping studs, and the model coming down on top of it do not apply. Otherwise it is
  skipped with a note, as any detail ("... was not placed: the part behind it has no stud
  on that side to hold it.").
- The side-stud brick is never swapped or removed: it is not a brick or plate of the
  solver's kinds, so the pass leaves it alone like any part it cannot remake (section 4).
- A sideways detail stands on nothing, so the cell under its column keeps whatever finish it
  asks for; it holds nothing and is held by its brick alone. The sturdiness measure joins it
  to that brick, exactly as ``connect.connection_graph`` does.
- Steps: it comes with the other details, after everything else, so after its brick.
- A smooth or sloped mark on the top of the side-stud brick cannot be met (the brick is one
  part three plates tall; a tile on it would stand above the Design's cells): the note says
  so in its own words and suggests moving the detail one course down.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from itertools import groupby

import networkx as nx
import numpy as np

from bricksnap.catalog import Catalog
from bricksnap.connect import (
    MIN_LOAD,
    LoneLink,
    connection_graph,
    lone_links,
    lone_links_of_graph,
    occupancy,
    on_base_z,
)
from bricksnap.types import EMPTY, FACE_OUT, FINISH_SLOPED, FINISH_SMOOTH, Build, Design, Placement

TILE_KIND = "tile"
SLOPE_PARTS = ("3039", "3040b", "85984", "54200")
"""Slope parts the pass must know how to place, biggest first."""

EXTRA_SLOPE_PARTS = ("4286",)
"""Further slope parts used where they fit. 11477 is not used: nothing under it grips studs,
so it would hang loose; 3665b (inverted) is not used by this pass."""

NOT_TILES = ("2412b",)
"""Parts of kind "tile" that are detail parts, never used for smooth tops."""

DETAIL_STEP_SIZE = 8
ROTATIONS = (0, 90, 180, 270)
_PAD = 4  # padding around the grid in the slope tests; more than any slope footprint
_VARIANTS_TALL = ("bricks", "plates")
_VARIANTS_LOW = ("plates", "bricks")
_RETRY_ROUNDS = 3
_STURDY_ROUNDS = 8  # rounds of refusing the swaps to blame, per class, before a broad one
_MEASURE_BUDGET = 150_000  # parts measured, summed over the swaps judged one by one
_MEASURE_MARGIN = 2  # a class is judged swap by swap when twice its swaps' measuring fits


# ---- small helpers ------------------------------------------------------------------------


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else (plural or singular + 's')}"


def _colour_name(catalog: Catalog, code: int) -> str:
    c = catalog.colours.get(code)
    return c.name if c else f"colour {code}"


_SLOPE_NAMES = {
    "3039": "a 2 x 2 45-degree slope",
    "3040b": "a 1 x 2 45-degree slope",
    "85984": "a 1 x 2 cheese slope",
    "54200": "a 1 x 1 cheese slope",
    "4286": "a 1 x 3 shallow slope",
}


def _slope_label(catalog: Catalog, part_id: str) -> str:
    name = _SLOPE_NAMES.get(part_id)
    return f"{name} ({part_id})" if name else _part_label(catalog, part_id)


def _part_label(catalog: Catalog, part_id: str) -> str:
    part = catalog.parts.get(part_id)
    return f"{part_id} ({part.name})" if part else part_id


@dataclass(frozen=True)
class _SlopeShape:
    """A slope part at one rotation, in cell offsets from its minimum corner."""

    part: str
    rot: int
    w: int
    d: int
    h: int
    studs: tuple[tuple[int, int], ...]
    slanted: tuple[tuple[int, int], ...]
    edge: tuple[tuple[int, int], ...]  # footprint cells on the low edge
    low: tuple[int, int]
    order: int


@dataclass(frozen=True)
class _Candidate:
    key: tuple
    placement: Placement
    slanted: tuple[tuple[int, int, int], ...]  # the grid cells that become slanted


def _slope_shapes(catalog: Catalog) -> list[_SlopeShape]:
    shapes = []
    for order, pid in enumerate(SLOPE_PARTS + EXTRA_SLOPE_PARTS):
        part = catalog.parts.get(pid)
        if part is None or part.kind != "slope" or not part.antistuds_bottom:
            continue
        for rot in ROTATIONS:
            p = Placement(pid, 0, 0, 0, 0, rot)
            low = catalog.low_side(p)
            if low is None:
                continue
            w, d, h = catalog.footprint(p)
            studs = tuple(sorted(set(catalog.stud_cells(p))))
            cells = [(i, j) for i in range(w) for j in range(d)]
            slanted = tuple(c for c in cells if c not in studs)
            if not slanted:
                continue
            edge = tuple(
                c for c in cells if not (0 <= c[0] + low[0] < w and 0 <= c[1] + low[1] < d)
            )
            shapes.append(_SlopeShape(pid, rot, w, d, h, studs, slanted, edge, low, order))
    return shapes


class _Cover:
    """Covers a 2-D set of cells with the largest rectangles of one kind that exist in a colour."""

    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog
        self.sizes: dict[str, list[tuple[int, int, str, int]]] = {}
        for kind in ("brick", "plate", TILE_KIND):
            sizes = []
            for part in catalog.parts.values():
                if part.kind != kind or part.id in NOT_TILES:
                    continue
                sizes.append((part.sx, part.sz, part.id, 0))
                if part.sx != part.sz:
                    sizes.append((part.sz, part.sx, part.id, 90))
            sizes.sort(key=lambda s: (-s[0] * s[1], -s[0]))
            self.sizes[kind] = sizes
        self.cache: dict[tuple, list[tuple[str, int, int, int]] | None] = {}

    def __call__(
        self, mask: np.ndarray, kind: str, colour: int, partial: bool = False
    ) -> list[tuple[str, int, int, int]] | None:
        """Rectangles (part, dx, dy, rot) covering ``mask``; None if a cell cannot be covered.

        With ``partial`` a cell no part can cover is left out instead.
        """
        key = (mask.shape, mask.tobytes(), kind, colour, partial)
        if key in self.cache:
            return self.cache[key]
        greedy = self._greedy(mask, self._options(kind, colour), partial)
        out = None if greedy is None else [(pid, i, j, rot) for pid, i, j, rot, _, _ in greedy]
        self.cache[key] = out
        return out

    def _options(self, kind: str, colour: int) -> list[tuple[int, int, str, int]]:
        parts = self.catalog.parts
        return [s for s in self.sizes[kind] if colour in parts[s[2]].colours]

    @staticmethod
    def _greedy(
        mask: np.ndarray, options: list[tuple[int, int, str, int]], partial: bool
    ) -> list[tuple[str, int, int, int, int, int]] | None:
        """(part, dx, dy, rot, w, d) taking the first size that fits at each first free cell."""
        nw, nd = mask.shape
        free = mask.copy()
        out: list[tuple[str, int, int, int, int, int]] = []
        for i in range(nw):
            for j in range(nd):
                if not free[i, j]:
                    continue
                for w, d, pid, rot in options:
                    if i + w <= nw and j + d <= nd and free[i : i + w, j : j + d].all():
                        free[i : i + w, j : j + d] = False
                        out.append((pid, i, j, rot, w, d))
                        break
                else:
                    if not partial:
                        return None
                    free[i, j] = False
        return out

    def tilings(self, mask: np.ndarray, colour: int) -> list[list[tuple[str, int, int, int]]]:
        """Several ways to cover ``mask`` with tiles, fewest tiles first.

        Each is greedy, with the tile sizes in one of three orders (largest first, longest
        along x first, longest along y first) and the scan started from each corner, so the
        tiles can line up with the parts underneath in different ways. Cells no tile covers
        are left out.
        """
        base = self._options(TILE_KIND, colour)
        orders = (
            base,
            sorted(base, key=lambda s: (-s[0], -s[0] * s[1])),
            sorted(base, key=lambda s: (-s[1], -s[0] * s[1])),
        )
        nw, nd = mask.shape
        found: dict[frozenset, int] = {}
        out: list[list[tuple[str, int, int, int]]] = []
        for options in orders:
            for fx in (False, True):
                for fy in (False, True):
                    flipped = mask[:: -1 if fx else 1, :: -1 if fy else 1]
                    rects = self._greedy(flipped, options, partial=True) or []
                    tiling = [
                        (pid, nw - i - w if fx else i, nd - j - d if fy else j, rot)
                        for pid, i, j, rot, w, d in rects
                    ]
                    key = frozenset(tiling)
                    if tiling and key not in found:
                        found[key] = len(out)
                        out.append(tiling)
        return sorted(out, key=lambda t: (len(t), found[frozenset(t)]))


# ---- the working state --------------------------------------------------------------------


class _State:
    """The build being changed: parts by id, which part covers each cell, studs, the graph.

    ``stud[x, y, z]`` is True where the part covering (x, y, z) has its top layer at z and a
    stud at (x, y). ``adj`` is the connection graph exactly as ``connect.connection_graph``
    defines it, kept up to date as parts are swapped.
    """

    def __init__(self, build: Build, design: Design, catalog: Catalog) -> None:
        self.catalog = catalog
        self.shape = design.shape
        occ, collisions, out_of_bounds, unknown = occupancy(build, catalog)
        self.input_occ = occ
        self.input_parts = list(build.parts)
        self.input_problems = (len(collisions), len(out_of_bounds), len(unknown))
        self.occ = occ.copy()
        self.parts: dict[int, Placement] = dict(enumerate(build.parts))
        self.next_id = len(build.parts)
        self.swaps = 0
        self.refusal = ""  # why the last refused swap was refused: "loose" or something else
        self.banned: set[tuple[Placement, ...]] = set()  # swaps that made the build less sturdy
        self.done: list[tuple[Placement, ...]] = []  # the swaps made, in order
        self.made_by: dict[int, tuple[Placement, ...]] = {}  # new part -> the swap that made it
        self.originals: dict[int, tuple] = {}  # part id -> the input parts it stands for
        # (filled in by the sturdiness guard; forgotten when the id is given to a new part)
        self.watch: Callable[[tuple[Placement, ...]], bool] | None = None  # judges each swap
        self.last: tuple = ()  # what the last swap made needs to be undone
        frozen = set(out_of_bounds) | set(unknown) | {i for pair in collisions for i in pair}
        for i, p in enumerate(build.parts):
            part = catalog.parts.get(p.part)
            if part is None or part.kind not in ("brick", "plate"):
                frozen.add(i)
        self.frozen = frozen
        self.outside = set(out_of_bounds) | {
            i for i, p in enumerate(build.parts) if p.part not in catalog.parts
        }

        self.stud = np.zeros(self.shape, dtype=bool)
        self.stepg = np.zeros(self.shape, dtype=np.int64)
        for i, p in enumerate(build.parts):
            if i in self.outside:
                continue
            sl = catalog.cells(p)
            mine = self.occ[sl] == i
            self.stepg[sl][mine] = p.step
            top = p.z + catalog.parts[p.part].h - 1
            for x, y in catalog.stud_cells(p):
                if self.occ[x, y, top] == i:
                    self.stud[x, y, top] = True

        colour_of = np.array([p.color for p in build.parts] + [EMPTY], dtype=np.int64)
        frozen_of = np.array([i in frozen for i in range(len(build.parts))] + [True])
        self.usable = (
            design.filled & (occ >= 0) & (colour_of[occ] == design.colors) & ~frozen_of[occ]
        )

        graph = connection_graph(build, catalog, occ)
        self.adj: dict[int, set[int]] = {n: set(graph.adj[n]) for n in graph.nodes}
        comps = sorted(nx.connected_components(graph), key=lambda c: (-len(c), min(c)))
        self.input_pieces = len(comps)
        self.input_main = np.zeros(self.shape, dtype=bool)
        if comps:
            main_of = np.zeros(len(build.parts) + 1, dtype=bool)
            main_of[list(comps[0])] = True
            self.input_main = (occ >= 0) & main_of[occ]

    # ---- geometry of new parts ---------------------------------------------------------------

    def _edges(self, nid: int) -> set[int]:
        """Parts the part ``nid`` holds or is held by, as ``connect.connection_graph`` says."""
        cat = self.catalog
        q = self.parts[nid]
        part = cat.parts[q.part]
        w, d, h = cat.footprint(q)
        out: set[int] = set()
        if part.antistuds_bottom and q.z > 0:
            below = self.occ[q.x : q.x + w, q.y : q.y + d, q.z - 1]
            studs = self.stud[q.x : q.x + w, q.y : q.y + d, q.z - 1]
            out.update(int(j) for j in np.unique(below[studs & (below >= 0)]))
        top = q.z + h
        if top < self.shape[2]:
            for x, y in cat.stud_cells(q):
                j = int(self.occ[x, y, top])
                if j < 0 or j == nid:
                    continue
                above = self.parts[j]
                if above.z == top and cat.parts[above.part].antistuds_bottom:
                    out.add(j)
        out.discard(nid)
        return out

    def _joined(self, groups: list[set[int]]) -> bool:
        """True if all the groups of parts are in one piece of the connection graph.

        Searches outwards from every group at once, one part per group in turn. Groups whose
        searches meet are merged; the answer is yes when one group is left, and no as soon as
        a group's search runs out without meeting another (its piece is closed). So a refusal
        costs about as much as the smallest piece that would come loose, not the whole model.
        """
        if len(groups) <= 1:
            return True
        label: dict[int, int] = {}
        parent = list(range(len(groups)))
        queues = []
        for g, nodes in enumerate(groups):
            for n in nodes:
                label[n] = g
            queues.append(deque(sorted(nodes)))

        def find(a: int) -> int:
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a

        alive = len(groups)
        while True:
            for g in range(len(groups)):
                if parent[g] != g:
                    continue
                if not queues[g]:
                    return False
                n = queues[g].popleft()
                for m in self.adj[n]:
                    r = find(g)
                    h = label.get(m)
                    if h is None:
                        label[m] = r
                        queues[r].append(m)
                        continue
                    h = find(h)
                    if h == r:
                        continue
                    big, small = (r, h) if len(queues[r]) >= len(queues[h]) else (h, r)
                    parent[small] = big
                    queues[big].extend(queues[small])
                    queues[small] = deque()
                    alive -= 1
                    if alive == 1:
                        return True

    # ---- swaps ---------------------------------------------------------------------------------

    def _refill(
        self, removed: list[int], wanted: list[Placement], variant: str, cover: _Cover
    ) -> list[Placement] | None:
        """Bricks and plates covering what the wanted parts leave of the removed parts."""
        cat = self.catalog
        out: list[Placement] = []
        for i in removed:
            p = self.parts[i]
            w, d, h = cat.footprint(p)
            left = np.ones((w, d, h), dtype=bool)
            for q in wanted:
                qw, qd, qh = cat.footprint(q)
                x0, x1 = max(p.x, q.x), min(p.x + w, q.x + qw)
                y0, y1 = max(p.y, q.y), min(p.y + d, q.y + qd)
                z0, z1 = max(p.z, q.z), min(p.z + h, q.z + qh)
                if x0 < x1 and y0 < y1 and z0 < z1:
                    left[x0 - p.x : x1 - p.x, y0 - p.y : y1 - p.y, z0 - p.z : z1 - p.z] = False
            if not left.any():
                continue
            if variant == "bricks" and cat.parts[p.part].kind == "brick":
                full = left.all(axis=2)
                if full.any():
                    rects = cover(full, "brick", p.color)
                    if rects is None:
                        return None
                    out += [
                        Placement(pid, p.color, p.x + i, p.y + j, p.z, r) for pid, i, j, r in rects
                    ]
                    left[full] = False
            for k in range(h):
                if not left[:, :, k].any():
                    continue
                rects = cover(left[:, :, k], "plate", p.color)
                if rects is None:
                    return None
                out += [
                    Placement(pid, p.color, p.x + i, p.y + j, p.z + k, r) for pid, i, j, r in rects
                ]
        return out

    def swap(
        self, wanted: Placement | list[Placement], variants: tuple[str, ...], cover: _Cover
    ) -> bool:
        """Put ``wanted`` in, taking out the parts in its way and covering what they leave.

        ``wanted`` is one part or several that go in together. Made only if it keeps every
        piece of the model in one piece; otherwise nothing changes.
        """
        wanted = [wanted] if isinstance(wanted, Placement) else wanted
        key = tuple(wanted)
        if key in self.banned:
            self.refusal = "sturdy"
            return False
        self.refusal = "empty"
        regions = [self.occ[self.catalog.cells(q)] for q in wanted]
        if any((r < 0).any() for r in regions):
            return False
        removed = sorted({int(i) for r in regions for i in np.unique(r)})
        self.refusal = "frozen"
        if any(i in self.frozen for i in removed):
            return False
        self.refusal = "refill"
        loosens = weakens = False
        for variant in variants:
            refill = self._refill(removed, wanted, variant, cover)
            if refill is None:
                continue
            first = self.next_id
            if self._apply(removed, [*wanted, *refill]):
                if self.watch is not None and not self.watch(key):
                    self._take_back()  # it holds, but less sturdily than the rule allows
                    weakens = True
                    continue
                self.swaps += 1
                self.done.append(key)
                for nid in range(first, self.next_id):
                    self.made_by[nid] = key
                return True
            loosens = loosens or self.refusal == "loose"
        if loosens:
            self.refusal = "loose"
        elif weakens:
            self.refusal = "sturdy"
        return False

    def _apply(self, removed: list[int], new_parts: list[Placement]) -> bool:
        cat = self.catalog
        slices = [cat.cells(self.parts[i]) for i in removed]
        box = tuple(
            slice(min(s[a].start for s in slices), max(s[a].stop for s in slices)) for a in range(3)
        )
        occ_saved = self.occ[box].copy()
        stud_saved = self.stud[box].copy()
        step_saved = self.stepg[box].copy()
        steps = [int(self.stepg[cat.cells(q)].max()) for q in new_parts]
        for sl in slices:
            self.occ[sl] = -1
            self.stud[sl] = False
        new_ids: list[int] = []
        fits = True
        for q, step in zip(new_parts, steps, strict=True):
            nid = self.next_id
            self.next_id += 1
            self.originals.pop(nid, None)
            q = replace(q, step=step)
            self.parts[nid] = q
            new_ids.append(nid)
            sl = cat.cells(q)
            if (self.occ[sl] != -1).any():
                fits = False
            self.occ[sl] = nid
            self.stepg[sl] = step
            top = q.z + cat.parts[q.part].h - 1
            for x, y in cat.stud_cells(q):
                self.stud[x, y, top] = True
        if fits:  # the new parts must cover exactly the cells the old ones did
            fits = bool(np.array_equal(self.occ[box] >= 0, occ_saved >= 0))

        gone = set(removed)
        neighbours = set().union(*(self.adj[i] for i in removed)) - gone
        new_edges = {nid: self._edges(nid) for nid in new_ids} if fits else {}

        ok = False
        groups: list[set[int]] = []
        if fits:
            # quick test: are the new parts and every former neighbour joined right here?
            nodes = set(new_ids) | neighbours
            for es in new_edges.values():
                nodes |= es
            root = {n: n for n in nodes}

            def find(a: int) -> int:
                while root[a] != a:
                    root[a] = root[root[a]]
                    a = root[a]
                return a

            for nid, es in new_edges.items():
                for e in es:
                    root[find(nid)] = find(e)
            by_root: dict[int, set[int]] = {}
            for n in sorted(set(new_ids) | neighbours):
                by_root.setdefault(find(n), set()).add(n)
            groups = list(by_root.values())
            ok = len(groups) == 1

        old_adj = {i: self.adj.pop(i) for i in removed}
        if fits:
            for i, ns in old_adj.items():
                for n in ns:
                    if n not in gone:
                        self.adj[n].discard(i)
            for nid in new_ids:
                self.adj[nid] = set()
            for nid, es in new_edges.items():
                for e in es:
                    self.adj[nid].add(e)
                    self.adj[e].add(nid)
            if not ok:  # the whole model may still hold them together another way
                ok = self._joined(groups)

        saved = (new_ids, old_adj, box, occ_saved, stud_saved, step_saved)
        if ok:
            self.last = ({i: self.parts.pop(i) for i in removed}, saved)
            return True
        self.refusal = "loose" if fits else "fit"
        self._undo(fits, *saved)
        return False

    def _undo(
        self,
        linked: bool,
        new_ids: list[int],
        old_adj: dict[int, set[int]],
        box: tuple[slice, ...],
        occ_saved: np.ndarray,
        stud_saved: np.ndarray,
        step_saved: np.ndarray,
    ) -> None:
        """Take the new parts out and put the graph and arrays back as they were."""
        if linked:
            for nid in new_ids:
                for e in self.adj.pop(nid):
                    if e in self.adj:
                        self.adj[e].discard(nid)
            for i, ns in old_adj.items():
                for n in ns:
                    if n not in old_adj:
                        self.adj[n].add(i)
        self.adj.update(old_adj)
        for nid in new_ids:
            del self.parts[nid]
        self.occ[box] = occ_saved
        self.stud[box] = stud_saved
        self.stepg[box] = step_saved

    def _take_back(self) -> None:
        """Undo the swap ``_apply`` has just made, exactly."""
        removed, saved = self.last
        self._undo(True, *saved)
        self.parts.update(removed)

    def snapshot(self) -> tuple:
        """Everything a swap changes, to go back to with ``restore``."""
        return (
            dict(self.parts),
            self.occ.copy(),
            self.stud.copy(),
            self.stepg.copy(),
            {n: set(es) for n, es in self.adj.items()},
            self.next_id,
            self.swaps,
            len(self.done),
            dict(self.made_by),
        )

    def restore(self, snap: tuple) -> None:
        parts, occ, stud, stepg, adj, next_id, swaps, done, made_by = snap
        self.parts = dict(parts)
        self.occ[...] = occ
        self.stud[...] = stud
        self.stepg[...] = stepg
        self.adj = {n: set(es) for n, es in adj.items()}
        self.next_id = next_id
        self.swaps = swaps
        del self.done[done:]
        self.made_by = dict(made_by)

    # ---- result ----------------------------------------------------------------------------------

    def final_parts(self) -> list[Placement]:
        """The parts with steps made consistent: none before a part it stands on, 1..n used."""
        return [replace(self.parts[i], step=s) for i, s in self.final_order()]

    def final_order(self) -> list[tuple[int, int]]:
        """(part id, step) of every part, in the order ``final_parts`` returns them."""
        cat = self.catalog
        ids = sorted(self.parts, key=lambda i: (self.parts[i].z, i))
        step = {i: self.parts[i].step for i in ids}
        # every part directly under each part's footprint, all at once
        boxes = []
        for i in ids:
            p = self.parts[i]
            if i in self.outside or p.z == 0 or p.x < 0 or p.y < 0 or p.z > self.shape[2]:
                continue
            w, d, _ = cat.footprint(p)
            boxes.append((i, p.x, p.y, p.z - 1, w, d))
        below: dict[int, list[int]] = {}
        if boxes:
            b = np.array(boxes, dtype=np.int64)
            sizes = b[:, 4] * b[:, 5]
            local = np.arange(int(sizes.sum())) - np.repeat(np.cumsum(sizes) - sizes, sizes)
            deep = np.repeat(b[:, 5], sizes)
            cx = np.repeat(b[:, 1], sizes) + local // deep
            cy = np.repeat(b[:, 2], sizes) + local % deep
            owner = np.repeat(b[:, 0], sizes)
            inside = (cx < self.shape[0]) & (cy < self.shape[1])
            j = np.full(len(cx), -1, dtype=np.int64)
            j[inside] = self.occ[cx[inside], cy[inside], np.repeat(b[:, 3], sizes)[inside]]
            keep = (j >= 0) & (j != owner)
            for i, k in np.unique(np.stack([owner[keep], j[keep]], axis=1), axis=0).tolist():
                below.setdefault(i, []).append(k)
        for i in ids:
            for k in below.get(i, ()):
                if step[k] > step[i]:
                    step[i] = step[k]
        levels = {s: n + 1 for n, s in enumerate(sorted(set(step.values())))}
        order = sorted(ids, key=lambda i: (levels[step[i]], i))
        return [(i, levels[step[i]]) for i in order]

    def lone_links(self, ids: list[int], details: list[Placement]) -> list[LoneLink]:
        """``connect.lone_links`` of the parts ``ids`` (in that order) and then ``details``,
        worked out from the state's own cells and studs rather than built again.

        The search depends only on the graph and the numbering of its parts, so this is the
        shared measure; on a build whose parts collide the two may differ, and the final
        check, made with ``connect.lone_links`` itself, decides.
        """
        cat = self.catalog
        n_ids = len(ids)
        n = n_ids + len(details)
        size = self.next_id + 1  # index -1 (an empty cell) lands on the last entry
        pos = np.full(size, -1, dtype=np.int64)
        pos[ids] = np.arange(n_ids)
        zpart = np.full(size, -1, dtype=np.int64)
        grips = np.zeros(size, dtype=bool)
        z: list[int] = []
        volume: list[float] = []
        known: list[bool] = []
        for i in ids:
            p = self.parts[i]
            part = cat.parts.get(p.part)
            zpart[i] = p.z
            z.append(p.z)
            if part is None:
                known.append(False)
                volume.append(0.0)
                continue
            grips[i] = part.antistuds_bottom
            known.append(True)
            volume.append(float(part.sx * part.sz * part.h))
        lo, hi = self.occ[:, :, :-1], self.occ[:, :, 1:]
        xs, ys, zs = np.nonzero(self.stud[:, :, :-1] & (hi >= 0) & (hi != lo))
        a, b = lo[xs, ys, zs], hi[xs, ys, zs]
        keep = (zpart[b] == zs + 1) & grips[b]
        codes = [pos[a[keep]] * n + pos[b[keep]]]
        for k, q in enumerate(details):  # a detail stands on studs and holds nothing
            w, d, _ = cat.footprint(q)
            if q.face in FACE_OUT:  # held by the side stud of the brick behind it
                ox, oy = FACE_OUT[q.face]
                holder = np.asarray([self.occ[q.x - ox, q.y - oy, q.z]], dtype=np.int64)
                codes.append(pos[holder] * n + n_ids + k)
                z.append(on_base_z(q))
                known.append(True)
                volume.append(float(w * d * cat.parts[q.part].h))
                continue
            under = self.occ[q.x : q.x + w, q.y : q.y + d, q.z - 1]
            studs = self.stud[q.x : q.x + w, q.y : q.y + d, q.z - 1] & (under >= 0)
            codes.append(pos[under[studs]] * n + n_ids + k)
            z.append(q.z)
            known.append(True)
            volume.append(float(w * d * cat.parts[q.part].h))
        uniq, counts = np.unique(np.concatenate(codes), return_counts=True)
        edges = list(zip((uniq // n).tolist(), (uniq % n).tolist(), counts.tolist(), strict=True))
        return lone_links_of_graph(n, edges, z, volume, known)[0]


# ---- the passes -----------------------------------------------------------------------------


def _place_details(
    design: Design, catalog: Catalog, state: _State
) -> tuple[list[Placement], list[str]]:
    """Detail placements that may go on, in Design order, and one note per skipped one."""
    nx_, ny_, nz_ = design.shape
    filled = design.filled
    taken = np.zeros(design.shape, dtype=bool)
    placed: list[Placement] = []
    notes: list[str] = []
    for d in design.details:
        part = catalog.parts.get(d.part)
        reason = ""
        p = None
        if part is not None and d.face != "top":
            p, reason = _sideways_detail(design, catalog, state, taken, d)
        elif part is None:
            reason = "it is not a part in the parts table"
        elif d.rot % 360 not in ROTATIONS:
            reason = "it can only be turned by 0, 90, 180 or 270 degrees"
        elif not catalog.exists(d.part, d.color):
            reason = f"it is not made in {_colour_name(catalog, d.color)}"
        else:
            rot = int(d.rot) % 360
            p = Placement(d.part, int(d.color), int(d.x), int(d.y), int(d.z), rot)
            w, dd, h = catalog.footprint(p)
            sl = catalog.cells(p)
            if p.x < 0 or p.y < 0 or p.z < 0 or p.x + w > nx_ or p.y + dd > ny_ or p.z + h > nz_:
                reason = "it would stick out of the model's space"
            elif filled[sl].any():
                reason = "the space it needs is not empty"
            elif taken[sl].any():
                reason = "an earlier detail part already takes that space"
            elif p.z == 0 or not filled[p.x : p.x + w, p.y : p.y + dd, p.z - 1].all():
                reason = "there is nothing under it to stand on"
            elif not state.stud[p.x : p.x + w, p.y : p.y + dd, p.z - 1].all():
                reason = "the part under it has no studs there"
            elif p.z + h < nz_ and filled[p.x : p.x + w, p.y : p.y + dd, p.z + h].any():
                reason = "the model comes down right on top of it, so it would be buried"
            elif not part.antistuds_bottom:
                reason = "it has nothing underneath that grips studs, so it would fall off"
        if reason or p is None:
            face = f" on the {d.face} face" if d.face != "top" else ""
            notes.append(
                f"Detail part {_part_label(catalog, d.part)} in "
                f"{_colour_name(catalog, d.color)} at x={d.x}, y={d.y}, z={d.z}{face} was not "
                f"placed: {reason}."
            )
            continue
        taken[catalog.cells(p)] = True
        placed.append(p)
    return placed, notes


def _sideways_detail(
    design: Design, catalog: Catalog, state: _State, taken: np.ndarray, d
) -> tuple[Placement | None, str]:
    """The Placement of a detail lying on a face, or why it cannot go on."""
    nx_, ny_, nz_ = design.shape
    if d.face not in FACE_OUT:
        return None, f'"{d.face}" is not a face (top, front, right, back or left)'
    if not catalog.can_face_sideways(d.part):
        return None, "only a detail one stud wide and one plate thick can lie on a face"
    if d.rot % 360:
        return None, "a part lying on a face is not turned (its rot must be 0)"
    if not catalog.exists(d.part, d.color):
        return None, f"it is not made in {_colour_name(catalog, d.color)}"
    p = Placement(d.part, int(d.color), int(d.x), int(d.y), int(d.z), 0, face=d.face)
    sl = catalog.cells(p)
    ox, oy = FACE_OUT[d.face]
    bx, by = p.x - ox, p.y - oy
    if p.x < 0 or p.y < 0 or p.z < 0 or p.x >= nx_ or p.y >= ny_ or p.z + 3 > nz_:
        return None, "it would stick out of the model's space"
    if design.filled[sl].any():
        return None, "the space in front of the face it needs is not empty"
    if taken[sl].any():
        return None, "an earlier detail part already takes that space"
    holder = -1
    if 0 <= bx < nx_ and 0 <= by < ny_:
        holder = int(state.occ[bx, by, p.z])
    if holder < 0:
        return None, "there is nothing behind it to hold it"
    q = state.parts[holder]
    if q.part not in catalog.parts or q.z != p.z or d.face not in catalog.side_stud_faces(q):
        return None, (
            "the part behind it has no stud on that side to hold it (a brick with a stud on its "
            "side goes there only when the three cells behind are filled, in one colour the "
            "brick 87087 is made in, and z is a multiple of 3)"
        )
    return p, ""


def _slope_candidates(
    design: Design,
    catalog: Catalog,
    sloped: np.ndarray,
    smooth: np.ndarray,
    clear: np.ndarray,
    usable: np.ndarray,
) -> list[_Candidate]:
    """Every slope placement that fits (section 3 of the contract), best first."""
    xs, ys, zs = np.nonzero(sloped)
    if xs.size == 0:
        return []
    pad = _PAD
    colors = np.pad(design.colors.astype(np.int64), pad, constant_values=EMPTY)
    usable_p = np.pad(usable, pad, constant_values=False)
    filled_p = colors != EMPTY
    sloped_p = np.pad(sloped, pad, constant_values=False)
    smooth_p = np.pad(smooth, pad, constant_values=False)
    clear_xy = np.pad(clear, ((pad, pad), (pad, pad), (0, 0)), constant_values=True)
    # run[x, y, z]: clear cells from z straight down (to the ground beside the grid)
    run = np.zeros(clear_xy.shape, dtype=np.int64)
    prev = np.zeros(clear_xy.shape[:2], dtype=np.int64)
    for z in range(clear_xy.shape[2]):
        prev = np.where(clear_xy[:, :, z], prev + 1, 0)
        run[:, :, z] = prev
    run_p = np.pad(run, ((0, 0), (0, 0), (pad, pad)))
    clear_p = np.pad(clear_xy, ((0, 0), (0, 0), (pad, pad)), constant_values=True)

    out: list[_Candidate] = []
    for s in _slope_shapes(catalog):
        colours = np.fromiter(catalog.parts[s.part].colours, dtype=np.int64)
        origins = np.unique(
            np.concatenate(
                [np.stack([xs - i, ys - j, zs - (s.h - 1)], axis=1) for i, j in s.slanted]
            ),
            axis=0,
        )
        ox, oy, oz = origins[:, 0] + pad, origins[:, 1] + pad, origins[:, 2] + pad
        top = oz + s.h - 1
        i0, j0 = s.slanted[0]
        col = colors[ox + i0, oy + j0, top]
        good = np.isin(col, colours)
        for i in range(s.w):
            for j in range(s.d):
                for k in range(s.h):
                    good &= colors[ox + i, oy + j, oz + k] == col
                    good &= usable_p[ox + i, oy + j, oz + k]
        for i, j in s.slanted:
            good &= sloped_p[ox + i, oy + j, top]
        for i, j in s.studs:  # a stud where a tile is wanted would lose the tile
            good &= ~smooth_p[ox + i, oy + j, top]
        dx, dy = s.low
        drop = np.full(len(origins), 1 << 30, dtype=np.int64)
        rise = np.ones(len(origins), dtype=bool)
        for i, j in s.edge:
            for k in range(1, s.h):
                good &= clear_p[ox + i + dx, oy + j + dy, oz + k]
            drop = np.minimum(drop, run_p[ox + i + dx, oy + j + dy, top])
            rise &= filled_p[ox + i - dx, oy + j - dy, top + 1]
        for n in np.nonzero(good)[0]:
            x, y, z = (int(v) for v in origins[n])
            zt = z + s.h - 1
            dn = int(drop[n])
            key = (
                -s.h,
                -len(s.edge),
                -min(dn, s.h),
                -int(rise[n]),
                -dn,
                -len(s.slanted),
                zt,
                y,
                x,
                s.order,
                s.rot,
            )
            out.append(
                _Candidate(
                    key,
                    Placement(s.part, int(col[n]), x, y, z, s.rot),
                    tuple((x + i, y + j, zt) for i, j in s.slanted),
                )
            )
    out.sort(key=lambda c: c.key)
    return out


def _exact_tiles(state: _State, wanted: np.ndarray, cover: _Cover) -> list[Placement]:
    """One tile of the same size for each part whose whole top is wanted, where one exists.

    Such a swap never loosens anything: the tile (on two levels of plates, for a brick) sits
    on exactly what the part sat on, and nothing stood on the part.
    """
    catalog = state.catalog
    out: list[Placement] = []
    for i in sorted(state.parts):
        if i in state.frozen:
            continue
        p = state.parts[i]
        w, d, h = catalog.footprint(p)
        top = p.z + h - 1
        if not wanted[p.x : p.x + w, p.y : p.y + d, top].all():
            continue
        for tw, td, pid, rot in cover.sizes[TILE_KIND]:
            if (tw, td) == (w, d) and catalog.exists(pid, p.color):
                out.append(Placement(pid, p.color, p.x, p.y, top, rot))
                break
    return out


def _tile_plan(wanted: np.ndarray, colors: np.ndarray, cover: _Cover) -> list[Placement]:
    """The largest tiles covering the wanted cells, layer by layer and colour by colour."""
    out: list[Placement] = []
    for z in range(wanted.shape[2]):
        layer = wanted[:, :, z]
        if not layer.any():
            continue
        for colour in sorted(int(c) for c in np.unique(colors[:, :, z][layer])):
            mask = layer & (colors[:, :, z] == colour)
            xs, ys = np.nonzero(mask)
            x0, y0 = int(xs.min()), int(ys.min())
            sub = mask[x0 : int(xs.max()) + 1, y0 : int(ys.max()) + 1]
            for pid, i, j, rot in cover(sub, TILE_KIND, colour, partial=True) or []:
                out.append(Placement(pid, colour, x0 + i, y0 + j, z, rot))
    return out


def _replan_tiles(
    state: _State, failed: list[Placement], wanted: np.ndarray, cover: _Cover, place_tiles
) -> int:
    """For each part under a refused tile, tile its wanted top cells as one swap.

    The tiles stay inside the part's own footprint, so only that part comes out. Tilings are
    tried fewest tiles first (``_Cover.tilings``); the first the model holds with is kept.
    Returns how many tiles went in.
    """
    catalog = state.catalog
    ids: set[int] = set()
    for tile in failed:
        sl = catalog.cells(tile)
        below = state.occ[sl][wanted[sl]]
        ids.update(int(i) for i in below if i >= 0)
    placed = 0
    for pid in sorted(ids, key=lambda i: (state.parts[i].z, i) if i in state.parts else (0, i)):
        p = state.parts.get(pid)
        if p is None or pid in state.frozen:
            continue
        w, d, h = catalog.footprint(p)
        top = p.z + h - 1
        sl = (slice(p.x, p.x + w), slice(p.y, p.y + d), top)
        mask = wanted[sl] & (state.occ[sl] == pid)
        if not mask.any():
            continue
        for tiling in cover.tilings(mask, p.color):
            tiles = [Placement(t, p.color, p.x + i, p.y + j, top, r) for t, i, j, r in tiling]
            if place_tiles(tiles):
                placed += len(tiles)
                break
    return placed


def _with_retries(items: list, place, failed: list | None = None) -> int:
    """Try to place every item in order, then again those that failed while any went in.

    ``place`` returns True (placed), False (refused) or None (no longer wanted). Returns how
    many were placed; the ones still refused are added to ``failed``.
    """
    placed = 0
    pending = items
    for _ in range(_RETRY_ROUNDS):
        refused = []
        progress = False
        for item in pending:
            result = place(item)
            if result:
                placed += 1
                progress = True
            elif result is False:
                refused.append(item)
        pending = refused
        if not progress or not refused:
            break
    if failed is not None:
        failed += pending
    return placed


def _plain(p: Placement) -> Placement:
    return replace(p, step=0)


def _face_cells(catalog: Catalog, q: Placement) -> list[tuple[int, int, int]]:
    """The top cells of a wanted part that carry no stud: a tile's top, a slope's slant."""
    w, d, h = catalog.footprint(q)
    studs = set(catalog.stud_cells(q))
    top = q.z + h - 1
    return [
        (q.x + i, q.y + j, top)
        for i in range(w)
        for j in range(d)
        if (q.x + i, q.y + j) not in studs
    ]


class _Sturdy:
    """The rule that finishing never makes a build less sturdy, and who to blame when it does.

    Everything is seen as the input's parts (``_groups``). The input with the detail parts
    standing on it is measured once (``connect.lone_links``): its largest load in cells and
    its number of lone links. The working state is measured the same way, in the order the
    result will have. ``keeps`` judges one swap just made; ``check`` judges a whole class of
    swaps and says which of them to refuse.
    """

    def __init__(
        self,
        build: Build,
        details: list[Placement],
        catalog: Catalog,
        input_occ: np.ndarray,
        exact: bool,
    ) -> None:
        self.catalog = catalog
        self.details = details
        self.shape = build.shape
        self.input = list(build.parts)
        self.input_occ = input_occ  # which input part covers each cell
        self.exact = exact  # measure with connect.lone_links itself (an awkward input)
        self.originals: dict[Placement, tuple] = {}  # part -> the input parts it stands for
        self.most = self.count = -1  # the input's, measured when first needed
        self.known: set[frozenset] = set()  # the input's groups
        self.budget = _MEASURE_BUDGET  # parts that may still be measured swap by swap
        self.load = np.zeros(build.shape, dtype=np.int64)  # the fewest parts a swap wanting
        # the cell, measured on its own and refused, would have left hanging (0: none)
        self.together = np.zeros(build.shape, dtype=np.int64)  # the same for swaps refused
        # in rounds, from the weak spots their class left (0: none)
        self.in_class = np.zeros(build.shape, dtype=bool)  # faces refused in this class
        self.rounds = np.zeros(build.shape, dtype=np.int64)  # ``together`` as the rounds of
        # the class left it, while the swaps they refused are tried again one by one
        self.worst = 0  # the most parts a refused swap would have left hanging
        self.hanging = 0  # the most parts hanging on one part, as the last refusal found
        self.prev: set[frozenset] | None = None  # the groups before the swap being judged

    def _originals(self, p: Placement) -> tuple:
        """The input parts whose cells ``p`` covers (by index), or ``p`` itself when it
        covers none of them (a detail) or is not a brick or plate the pass could have made."""
        got = self.originals.get(p)
        if got is None:
            own = (("own", _plain(p)),)
            if p.part not in self.catalog.parts or min(p.x, p.y, p.z) < 0:
                got = own
            else:
                region = self.input_occ[self.catalog.cells(p)]
                got = tuple(int(v) for v in np.unique(region[region >= 0])) or own
            self.originals[p] = got
        return got

    def _groups(
        self, parts: list[Placement], originals: list[tuple], links: list[LoneLink]
    ) -> dict[frozenset, tuple[int, int, LoneLink]]:
        """The lone links seen as the input's parts: {input parts in the group: (how many,
        cells, the lone link)}.

        Each part stands for the input parts it covers cells of (``_originals``). A group
        leaves out the pieces of the part it hangs on, when that part was cut from a single
        input part (a brick cut into plates and a slope hangs on its own bottom plate: still
        the one brick); groups of the same input parts are one, the heaviest in cells kept;
        fewer than ``MIN_LOAD`` input parts is none. On the input this is simply its lone
        links.
        """
        cat = self.catalog
        volume = [
            (cat.parts[p.part].sx * cat.parts[p.part].sz * cat.parts[p.part].h)
            if p.part in cat.parts
            else 0
            for p in parts
        ]
        out: dict[frozenset, tuple[int, int, LoneLink]] = {}
        for ln in links:
            if ln.joint is None:
                on = ln.part
            else:
                a, b = ln.joint
                on = a if b in ln.members else b
            base = originals[on]  # its pieces are the parts cut from that one input part
            if len(base) != 1:
                base = ()  # a part covering cells of several input parts is new
            held: set = set()
            cells = 0
            for m in ln.members:
                mine = originals[m]
                if mine == base:
                    continue  # a piece of the part it hangs on
                held.update(mine)
                cells += volume[m]
            if len(held) < MIN_LOAD:
                continue
            key = frozenset(held)
            kept = out.get(key)
            if kept is None or cells > kept[1]:
                out[key] = (len(held), cells, ln)
        return out

    def _measure_input(self) -> None:
        if self.count >= 0:
            return
        base = self.input + self.details
        links = lone_links(Build(shape=self.shape, parts=base), self.catalog)
        groups = self._groups(base, [self._originals(p) for p in base], links)
        self.most = max((g[1] for g in groups.values()), default=0)
        self.count = len(groups)
        self.known = set(groups)

    def holds(self, parts: list[Placement]) -> bool:
        links = lone_links(Build(shape=self.shape, parts=parts), self.catalog)
        groups = self._groups(parts, [self._originals(p) for p in parts], links)
        return not self._offenders(groups)

    def _measure(self, state: _State) -> tuple[list[int], list[Placement], list[LoneLink]]:
        ids = [i for i, _ in state.final_order()]
        parts = [state.parts[i] for i in ids] + self.details
        if self.exact:
            return ids, parts, lone_links(Build(shape=self.shape, parts=parts), self.catalog)
        return ids, parts, state.lone_links(ids, self.details)

    def _state_groups(
        self, state: _State
    ) -> tuple[list[int], list[Placement], dict[frozenset, tuple[int, int, LoneLink]]]:
        ids, parts, links = self._measure(state)
        originals = []
        for i in ids:
            got = state.originals.get(i)
            if got is None:
                got = state.originals[i] = self._originals(state.parts[i])
            originals.append(got)
        originals += [self._originals(p) for p in self.details]
        return ids, parts, self._groups(parts, originals, links)

    def _offenders(
        self, groups: dict[frozenset, tuple[int, int, LoneLink]]
    ) -> dict[frozenset, tuple[int, int, LoneLink]]:
        """The groups that break the rule; none when it holds.

        A group breaks it when it covers more cells than the input's heaviest, or, when there
        are more groups than the input had, when it is not one of the input's (the same input
        parts hanging).
        """
        self._measure_input()
        too_many = len(groups) > self.count
        return {
            k: g
            for k, g in groups.items()
            if g[1] > self.most or (too_many and k not in self.known)
        }

    def affords(self, swaps: int, parts: int) -> bool:
        return swaps * parts * _MEASURE_MARGIN <= self.budget

    def start(self, state: _State) -> bool:
        """Get ready to judge swaps one by one from the state as it is (which keeps the
        rule); False when not even one could be measured."""
        n = len(state.parts) + len(self.details)
        if n > self.budget:
            return False
        self.budget -= n
        self.prev = set(self._state_groups(state)[2])
        return True

    def keeps(self, state: _State, key: tuple[Placement, ...]) -> bool:
        """Whether the swap ``key``, just made, keeps the rule (the state before it did).

        Used while the swaps refused in rounds are tried again. One that can no longer be
        measured (the budget ran out on the way) stays refused, as the rounds found."""
        n = len(state.parts) + len(self.details)
        if n > self.budget:
            faces = [c for q in key for c in _face_cells(self.catalog, q)]
            load = max((int(self.rounds[c]) for c in faces), default=0)
            self._mark(key, load or self.worst, "together")
            return False
        self.budget -= n
        groups = self._state_groups(state)[2]
        offenders = self._offenders(groups)
        if not offenders:
            self.prev = set(groups)
            return True
        # the groups this swap made or changed (the rest were there before it, which kept
        # the rule), however many parts they hold: one of them broke it
        made = [g[0] for k, g in groups.items() if self.prev is None or k not in self.prev]
        self.hanging = max(made or [g[0] for g in offenders.values()])
        self._mark(key, self.hanging, "measured")
        return False

    def check(
        self, state: _State, start: int, broad: bool
    ) -> list[tuple[tuple[Placement, ...], int]] | None:
        """None when the state keeps the rule; otherwise the swaps to refuse, each with the
        number of parts it left hanging. Only the swaps made since ``state.done[start]`` can
        be blamed: the ones before kept the rule.

        For each group that breaks the rule, the swaps refused are those that made the part
        or joint it hangs on; failing that, those that made parts both in its group and
        outside it (they cut through the group's ties); failing that, those that made parts
        in its group; failing that (a group can also come to hang alone when a swap beside it
        changes how the groups around it are counted), the swap made nearest to the part it
        hangs on. ``broad`` refuses all of the first three at once.
        """
        ids, parts, groups = self._state_groups(state)
        offenders = self._offenders(groups)
        if not offenders:
            return None
        recent = set(state.done[start:])
        made = [k if (k := state.made_by.get(i)) in recent else None for i in ids]
        made += [None] * len(self.details)
        new_of: dict[tuple[Placement, ...], list[int]] = {}
        for n, k in enumerate(made):
            if k is not None:
                new_of.setdefault(k, []).append(n)
        blamed: dict[tuple[Placement, ...], int] = {}
        for load, _, ln in offenders.values():
            hung_on = [ln.part] if ln.joint is None else list(ln.joint)
            makers = {k for n in hung_on if (k := made[n]) is not None}
            members = set(ln.members)
            inside = {k for n in ln.members if (k := made[n]) is not None}
            cutting = {k for k in inside if any(n not in members for n in new_of[k])}
            chosen = (makers | inside) if broad else (makers or cutting or inside)
            if not chosen and recent:
                chosen = {self._nearest(parts[ln.part], state.done[start:])}
            for k in chosen:
                blamed[k] = max(blamed.get(k, 0), load)
        self.hanging = max(g[0] for g in offenders.values())
        return list(blamed.items())

    def _nearest(self, p: Placement, swaps: list[tuple[Placement, ...]]) -> tuple[Placement, ...]:
        """The swap whose wanted parts come closest to ``p`` (the first, on a tie)."""
        w, d, h = self.catalog.footprint(p)

        def gap(q: Placement) -> int:
            qw, qd, qh = self.catalog.footprint(q)
            return (
                max(p.x - (q.x + qw), q.x - (p.x + w), 0)
                + max(p.y - (q.y + qd), q.y - (p.y + d), 0)
                + max(p.z - (q.z + qh), q.z - (p.z + h), 0)
            )

        return min(swaps, key=lambda k: min(gap(q) for q in k))

    def _mark(self, key: tuple[Placement, ...], load: int, how: str) -> None:
        """Remember, for the notes, the faces a refused swap wanted and how many parts it
        would have left hanging: ``how`` is "measured" (the swap on its own) or "together"
        (refused in rounds, from what its class left; the rest of this class then leaves
        those faces alone, since a slope turned another way would do the same harm)."""
        self.worst = max(self.worst, load)
        grid = self.load if how == "measured" else self.together
        for q in key:
            for c in _face_cells(self.catalog, q):
                grid[c] = load if grid[c] == 0 else min(int(grid[c]), load)
                if how == "together":
                    self.in_class[c] = True

    def refuse(self, state: _State, blamed: list[tuple[tuple[Placement, ...], int]]) -> None:
        """Refuse these swaps from now on."""
        for key, load in blamed:
            state.banned.add(key)
            self._mark(key, load, "together")


def _fell_back(why: str) -> None:
    """Called when the safety net is used, which is never expected (the tests make it fail)."""


def _detail_steps(details: list[Placement], first: int) -> list[Placement]:
    order = sorted(range(len(details)), key=lambda n: (details[n].z, details[n].y, details[n].x, n))
    return [replace(details[n], step=first + k // DETAIL_STEP_SIZE) for k, n in enumerate(order)]


def _verify(state: _State, parts: list[Placement], detail_mask: np.ndarray) -> bool:
    """Section 5 of the contract, checked with ``bricksnap.connect`` itself."""
    catalog = state.catalog
    result = Build(shape=state.shape, parts=parts)
    occ, collisions, out_of_bounds, unknown = occupancy(result, catalog)
    if any(
        a > b
        for a, b in zip(
            (len(collisions), len(out_of_bounds), len(unknown)), state.input_problems, strict=True
        )
    ):
        return False
    base = state.input_occ >= 0
    if not np.array_equal(occ >= 0, base | detail_mask):
        return False
    colour_in = np.array([p.color for p in state.input_parts] + [EMPTY], dtype=np.int64)
    colour_out = np.array([p.color for p in parts] + [EMPTY], dtype=np.int64)
    if not np.array_equal(colour_out[occ[base]], colour_in[state.input_occ[base]]):
        return False
    graph = connection_graph(result, catalog, occ)
    label = np.full(len(parts) + 1, -1, dtype=np.int64)
    pieces = 0
    for n, comp in enumerate(nx.connected_components(graph)):
        label[list(comp)] = n
        pieces += 1
    if pieces > state.input_pieces:
        return False
    main = np.unique(label[occ[state.input_main]])
    return len(main) <= 1 and (main.size == 0 or main[0] >= 0)


# ---- why cells were left as they were ---------------------------------------------------------

# Reasons, in the order sentences about equally many cells are given.
(
    _DETAIL,
    _STUD_ROW,
    _FLAT,
    _LOOSE,
    _STURDY,
    _TOGETHER,
    _CROWDED,
    _COLOUR,
    _SMALL,
    _THIN,
    _OTHER,
    _SIDE_BRICK,
) = range(12)
_MAX_REASON_NOTES = 6
_MAX_PLACES = 3


@dataclass
class _Tried:
    """What the pass tried for each cell (boolean grids of the Design's shape)."""

    candidate: np.ndarray  # the slanted cell of at least one slope placement that fits
    planned: np.ndarray  # covered by a tile of the tile plan
    loose: np.ndarray  # wanted by a swap refused because part of the model would come loose
    refused: np.ndarray  # wanted by a swap refused for another reason


@dataclass
class _Progress:
    """What the pass has done so far, beside the working state: cells taken, tiled and
    slanted, counts, refused tiles, and what was tried (saved and loaded with the state)."""

    claimed: np.ndarray
    slanted: np.ndarray
    tiled: np.ndarray
    tried: _Tried
    n_slopes: int = 0
    n_tiles: int = 0
    failed: list[Placement] = field(default_factory=list)

    def save(self) -> _Progress:
        t = self.tried
        return _Progress(
            self.claimed.copy(),
            self.slanted.copy(),
            self.tiled.copy(),
            _Tried(t.candidate.copy(), t.planned.copy(), t.loose.copy(), t.refused.copy()),
            self.n_slopes,
            self.n_tiles,
            list(self.failed),
        )

    def load(self, saved: _Progress) -> None:
        """Go back to ``saved``, in place (the pass holds on to these arrays)."""
        for name in ("claimed", "slanted", "tiled"):
            getattr(self, name)[...] = getattr(saved, name)
        for name in ("candidate", "planned", "loose", "refused"):
            getattr(self.tried, name)[...] = getattr(saved.tried, name)
        self.n_slopes, self.n_tiles = saved.n_slopes, saved.n_tiles
        self.failed[:] = saved.failed


def _cell(c: np.ndarray) -> tuple[int, int, int]:
    return int(c[0]), int(c[1]), int(c[2])


def _no_slope_reasons(
    design: Design,
    catalog: Catalog,
    cells: np.ndarray,
    sloped: np.ndarray,
    smooth: np.ndarray,
    clear: np.ndarray,
    usable: np.ndarray,
) -> list[tuple]:
    """Why no slope placement fits these sloped cells: one reason key per cell.

    Every slope part at every rotation and position that would have the cell as a slanted
    cell is put through the tests of section 3 in turn: the cell's own column is tall enough
    in its colour, the whole footprint is filled in that colour and can be changed, the other
    slanted cells are sloped and no stud lands on a smooth cell, the face does not run into
    the model at the top, the step beside it is deep enough, and the part is made in the
    colour. The furthest any part gets is the reason, so a part that fits everywhere but is
    not made in the colour gives "not made in that colour".
    """
    pad = _PAD
    colors = np.pad(design.colors.astype(np.int64), pad, constant_values=EMPTY)
    usable_p = np.pad(usable, pad, constant_values=False)
    sloped_p = np.pad(sloped, pad, constant_values=False)
    smooth_p = np.pad(smooth, pad, constant_values=False)
    clear_p = np.pad(clear, pad, constant_values=True)
    filled_p = colors != EMPTY
    cx, cy, cz = (cells[:, a] + pad for a in range(3))
    colour = colors[cx, cy, cz]
    n = len(cells)
    flat = np.ones(n, dtype=bool)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        flat &= filled_p[cx + dx, cy + dy, cz]
    best_made = np.full(n, -1, dtype=np.int64)  # furthest stage of a part made in the colour
    fits_unmade = np.full(n, -1, dtype=np.int64)  # first part that fits but is not made in it
    best_any = np.full(n, -1, dtype=np.int64)  # furthest stage of any part, in any colour
    thinnest = np.full(n, 1 << 30, dtype=np.int64)  # lowest part made in the colour
    shapes = _slope_shapes(catalog)
    lowest = min((s.h for s in shapes), default=0)
    for si, s in enumerate(shapes):
        made = np.isin(colour, np.fromiter(catalog.parts[s.part].colours, dtype=np.int64))
        thinnest = np.where(made, np.minimum(thinnest, s.h), thinnest)
        dx, dy = s.low
        for i, j in s.slanted:
            ox, oy, oz = cx - i, cy - j, cz - (s.h - 1)
            ok = np.ones(n, dtype=bool)
            for k in range(s.h):  # the cell's own column, in its colour
                ok &= colors[cx, cy, oz + k] == colour
            stage = ok.astype(np.int64)
            for a in range(s.w):  # the whole footprint, in the colour and free to change
                for b in range(s.d):
                    for k in range(s.h):
                        ok &= (colors[ox + a, oy + b, oz + k] == colour) & usable_p[
                            ox + a, oy + b, oz + k
                        ]
            stage += ok
            for a, b in s.slanted:
                ok &= sloped_p[ox + a, oy + b, cz]
            for a, b in s.studs:
                ok &= ~smooth_p[ox + a, oy + b, cz]
            stage += ok
            for a, b in s.edge:  # the face does not run into the model at the top
                ok &= clear_p[ox + a + dx, oy + b + dy, cz]
            stage += ok
            for a, b in s.edge:  # the step is deep enough
                for k in range(1, s.h):
                    ok &= clear_p[ox + a + dx, oy + b + dy, oz + k]
            stage += ok
            best_made = np.where(made, np.maximum(best_made, stage), best_made)
            best_any = np.maximum(best_any, stage)
            fits_unmade[~made & ok & (fits_unmade < 0)] = si
    out: list[tuple] = []
    for c in range(n):
        col = int(colour[c])
        unmade = shapes[int(fits_unmade[c])].part if fits_unmade[c] >= 0 else ""
        best = int(best_made[c])
        if flat[c]:
            out.append((_FLAT,))
        elif unmade and best < 4:
            out.append((_COLOUR, col, unmade))
        elif best == 4:
            out.append((_SMALL, col, unmade))
        elif best < 0:  # no slope part in this colour, and none would fit in another
            out.append((_THIN, lowest) if best_any[c] == 0 else (_COLOUR, col, ""))
        elif best == 0:
            out.append((_THIN, int(thinnest[c])))
        else:
            out.append((_OTHER,))
    return out


def _why_left(
    design: Design,
    catalog: Catalog,
    state: _State,
    left_smooth: np.ndarray,
    left_sloped: np.ndarray,
    claimed: np.ndarray,
    tried: _Tried,
    guard: _Sturdy,
    smooth: np.ndarray,
    sloped: np.ndarray,
    clear: np.ndarray,
    reasons: dict[tuple, list[tuple[int, int, int]]],
) -> None:
    """Add every smooth cell that kept its stud and every sloped cell that got no slope to
    ``reasons``, under the reason found for it."""

    def add(name: str, mask: np.ndarray, key: tuple) -> None:
        for c in np.argwhere(mask):
            reasons.setdefault((name, *key), []).append(_cell(c))

    measured = guard.load > 0
    together = (guard.together > 0) & ~measured
    sturdy = measured | together

    def add_sturdy(name: str, mask: np.ndarray) -> None:
        """The cells a swap was refused for by the sturdiness rule: measured on its own,
        then refused in rounds; with the most parts left hanging, and whether all agree."""
        for reason, grid, where in (
            (_STURDY, guard.load, measured),
            (_TOGETHER, guard.together, together),
        ):
            cells = mask & where
            if cells.any():
                hi, lo = int(grid[cells].max()), int(grid[cells].min())
                add(name, cells, (reason, hi, hi == lo))

    # the top of a brick with a stud on its side, which holds a detail on a face: one part
    side_ids = [
        i
        for i, p in state.parts.items()
        if catalog.parts.get(p.part) and catalog.parts[p.part].kind == "side_stud"
    ]
    side = np.isin(state.occ, side_ids) if side_ids else np.zeros(state.shape, dtype=bool)
    add("smooth", left_smooth & side, (_SIDE_BRICK,))
    add("sloped", left_sloped & side, (_SIDE_BRICK,))
    left_smooth = left_smooth & ~side
    left_sloped = left_sloped & ~side

    # smooth: a refused tile beats "no tile is made in that colour" beats "no tile fits"
    usable = state.usable
    add("smooth", left_smooth & ~usable, (_OTHER,))
    add("smooth", left_smooth & usable & tried.loose, (_LOOSE,))
    add_sturdy("smooth", left_smooth & usable & ~tried.loose)
    rest = left_smooth & usable & ~tried.loose & ~sturdy
    add("smooth", rest & tried.refused, (_OTHER,))
    add("smooth", rest & ~tried.refused & tried.planned, (_OTHER,))
    for c in np.argwhere(rest & ~tried.refused & ~tried.planned):
        x, y, z = (int(v) for v in c)
        key = ("smooth", _COLOUR, int(design.colors[x, y, z]))
        reasons.setdefault(key, []).append((x, y, z))

    # sloped: the high side of a slope; a refused slope; a slope that fitted but lost out to
    # a neighbour; otherwise the furthest any slope part got in the tests of section 3
    add("sloped", left_sloped & claimed, (_STUD_ROW,))
    open_ = left_sloped & ~claimed
    add("sloped", open_ & tried.loose, (_LOOSE,))
    add_sturdy("sloped", open_ & ~tried.loose)
    open_ &= ~sturdy
    fitted = open_ & ~tried.loose & tried.candidate
    add("sloped", fitted & tried.refused, (_OTHER,))
    add("sloped", fitted & ~tried.refused, (_CROWDED,))
    cells = np.argwhere(open_ & ~tried.loose & ~tried.candidate)
    if len(cells):
        keys = _no_slope_reasons(design, catalog, cells, sloped, smooth, clear, state.usable)
        for c, key in zip(cells, keys, strict=True):
            reasons.setdefault(("sloped", *key), []).append(_cell(c))


def _places(cells: list[tuple[int, int, int]]) -> list[list[tuple[int, int, int]]]:
    """The cells in groups that touch (also along edges and corners), biggest first."""
    left = set(cells)
    groups = []
    for start in sorted(cells):
        if start not in left:
            continue
        left.discard(start)
        group = [start]
        queue = deque([start])
        while queue:
            x, y, z = queue.popleft()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        c = (x + dx, y + dy, z + dz)
                        if c in left:
                            left.discard(c)
                            group.append(c)
                            queue.append(c)
        groups.append(group)
    return sorted(groups, key=lambda g: (-len(g), min(g)))


def _box(cells: list[tuple[int, int, int]]) -> str:
    """ "x=1 to 3, y=0, z=5 to 6": the box around the cells, one number where it is one cell."""
    parts = []
    for axis, name in enumerate("xyz"):
        lo = min(c[axis] for c in cells)
        hi = max(c[axis] for c in cells)
        parts.append(f"{name}={lo}" if lo == hi else f"{name}={lo} to {hi}")
    return ", ".join(parts)


def _where(cells: list[tuple[int, int, int]]) -> str:
    groups = _places(cells)
    if len(groups) == 1:
        return "at " + _box(cells)
    shown = "; ".join(_box(g) for g in groups[:_MAX_PLACES])
    more = len(groups) - _MAX_PLACES
    if more > 0:
        shown += f"; and {_count(more, 'more place')}"
    return f"in {len(groups)} places ({shown})"


def _reason_sentence(key: tuple, cells: list[tuple[int, int, int]], catalog: Catalog) -> str:
    name, reason, *extra = key
    n = len(cells)
    one = n == 1
    subject = f"{_count(n, 'cell')} marked {name} {_where(cells)}"
    them, these = ("it", "this cell") if one else ("them", "these cells")
    kept = "kept its stud" if one else "kept their studs"
    keep = "keeps its stud" if one else "keep their studs"
    left = kept if name == "smooth" else "got no slope"
    part = "a tile" if name == "smooth" else "a slope"
    if reason == _DETAIL:
        return (
            f"{subject} {keep} because a detail part stands on {them}; that is as it should "
            "be, nothing to change."
        )
    if reason == _SIDE_BRICK:
        return (
            f"{subject} {keep} because {'it is' if one else 'they are'} the top of a brick "
            "with a stud on its side (87087) that holds a detail on a face: that brick is one "
            f"part three plates tall, so no {part[2:]} can take its top. To have {them} "
            "smooth, move the detail one brick course down."
        )
    if reason == _STUD_ROW:
        return (
            f"{subject} {keep} because {'it is' if one else 'they are'} the high side of a "
            f"slope placed next to {them}, which carries its row of studs there; that is how "
            "a 45-degree slope is made, nothing to change."
        )
    if reason == _CROWDED:
        return (
            f"{subject} {left} because every slope that fits there would overlap a slope "
            f"already placed beside {them}, which was preferred; nothing to change."
        )
    if reason == _FLAT:
        return (
            f"{subject} {left} because the surface does not step down beside {them}: on a "
            f'flat top there is nothing to slope. Mark {them} "smooth" for tiles, or "studs" '
            "to stop asking."
        )
    if reason == _LOOSE:
        return (
            f"{subject} {left} because {part} there would let go of parts that are held on "
            f"only through {these}, so part of the model would come loose. Making that part "
            "of the model thicker, or joining it more firmly to the rest, could change that; "
            "otherwise leave studs there."
        )
    if reason in (_STURDY, _TOGETHER):
        hanging = _count(extra[0], "part") if extra[1] else f"up to {extra[0]} parts"
        where = "there"
        if reason == _TOGETHER:
            where = f"there, with the others tried around {them} at the same time,"
        return (
            f"{subject} {left} because {part} {where} would leave {hanging} hanging on a "
            "single part, so that part of the model would come off too easily. Making that "
            "part of the model thicker, or joining it more firmly to the rest, could change "
            "that; otherwise leave studs there."
        )
    if reason == _COLOUR:
        colour = _colour_name(catalog, extra[0])
        if name == "smooth":
            what = f"no tile that fits there is made in {colour}"
        elif extra[1]:
            label = _slope_label(catalog, extra[1])
            what = f"the slope that would fit there, {label}, is not made in {colour}"
        else:
            return f"{subject} {left} because no slope part is made in {colour}."
        return f"{subject} {left} because {what}: a different colour there would allow one."
    if reason == _SMALL:
        colour = _colour_name(catalog, extra[0])
        also = ""
        if extra[1]:
            also = (
                f"; {_slope_label(catalog, extra[1])} would fit that step, but it is not made in "
                f"{colour}"
            )
        return (
            f"{subject} {left} because the step down beside {them} is too small for the slope "
            f"parts made in {colour}{also}. Make the step deeper, use another colour, or mark "
            f'{them} "smooth".'
        )
    if reason == _THIN:
        have = "is only 1" if extra[0] == 2 else "are fewer"
        return (
            f"{subject} {left} because the model is too thin there: a slope part is at least "
            f"{extra[0]} plates tall and needs that many plates of one colour stacked there "
            f"(counting the marked cell), but there {have}. "
            f'Make it thicker there, or mark {them} "smooth".'
        )
    what = "no tile fits there" if name == "smooth" else "no slope part fits there"
    return f"{subject} {left}: {what}."


def _reason_notes(reasons: dict[tuple, list[tuple[int, int, int]]], catalog: Catalog) -> list[str]:
    """One sentence per reason, biggest first; past six, the smallest are merged into one."""
    order = sorted(reasons, key=lambda k: (-len(reasons[k]), k[1], k))
    shown = order
    rest = 0
    if len(order) > _MAX_REASON_NOTES:
        shown = order[: _MAX_REASON_NOTES - 1]
        rest = sum(len(reasons[k]) for k in order[_MAX_REASON_NOTES - 1 :])
    notes = [_reason_sentence(k, reasons[k], catalog) for k in shown]
    if rest:
        notes.append(
            f"And {_count(rest, 'more cell')} in other places "
            f"{'was' if rest == 1 else 'were'} left as {'it was' if rest == 1 else 'they were'}."
        )
    return notes


def finish(build: Build, design: Design, catalog: Catalog) -> Build:
    if tuple(build.shape) != design.shape:
        raise ValueError(
            f"The build's grid ({build.shape}) is not the same size as the design's "
            f"({design.shape})."
        )
    assert design.finish is not None
    above_empty = np.ones(design.shape, dtype=bool)
    above_empty[:, :, :-1] = ~design.filled[:, :, 1:]
    marked = (design.finish == FINISH_SMOOTH) | (design.finish == FINISH_SLOPED)
    if not design.details and not (design.filled & above_empty & marked).any():
        return Build(
            shape=build.shape,
            parts=list(build.parts),
            report=None,
            design_id=build.design_id,
            notes=list(build.notes),
        )
    # first exactly as without the sturdiness rule; only if that breaks the rule, again with it
    plain = _finish(build, design, catalog, sturdy=False)
    if plain is not None:
        return plain
    result = _finish(build, design, catalog, sturdy=True)
    assert result is not None
    return result


def _finish(build: Build, design: Design, catalog: Catalog, sturdy: bool) -> Build | None:
    """The pass. With ``sturdy`` each class of swaps is held to the sturdiness rule as it
    goes; without, nothing is (as before the rule), and None is returned if the result
    breaks it."""
    assert design.finish is not None
    state = _State(build, design, catalog)
    details, detail_notes = _place_details(design, catalog, state)

    filled = design.filled
    detail_mask = np.zeros(design.shape, dtype=bool)
    under = np.zeros(design.shape, dtype=bool)
    for p in details:
        detail_mask[catalog.cells(p)] = True
        if p.face != "top":  # it stands on nothing
            continue
        w, d, _ = catalog.footprint(p)
        under[p.x : p.x + w, p.y : p.y + d, p.z - 1] = True
    above_empty = np.ones(design.shape, dtype=bool)
    above_empty[:, :, :-1] = ~filled[:, :, 1:]
    open_cells = filled & above_empty & ~under
    smooth = open_cells & (design.finish == FINISH_SMOOTH)
    sloped = open_cells & (design.finish == FINISH_SLOPED)

    cover = _Cover(catalog)
    # what was tried for each cell, so the notes can say why a cell was left as it was
    prog = _Progress(
        claimed=np.zeros(design.shape, dtype=bool),
        slanted=np.zeros(design.shape, dtype=bool),
        tiled=np.zeros(design.shape, dtype=bool),
        tried=_Tried(
            candidate=np.zeros(design.shape, dtype=bool),
            planned=np.zeros(design.shape, dtype=bool),
            loose=np.zeros(design.shape, dtype=bool),
            refused=np.zeros(design.shape, dtype=bool),
        ),
    )
    claimed, tried = prog.claimed, prog.tried
    awkward = any(state.input_problems)  # the quick measure may miss what such parts hold
    guard = _Sturdy(build, details, catalog, state.input_occ, exact=awkward)

    def guarded(work: Callable[[], None]) -> None:
        """Run one class of swaps. If it leaves the build less sturdy than the input, refuse
        the swaps to blame and run the class again from where it started; after
        ``_STURDY_ROUNDS`` such rounds, one round refusing every swap that could be to blame;
        after that, every swap of the class is refused. The rounds refuse more than the rule
        needs, so then the swaps they refused are tried again one by one, each measured as it
        is made, when the budget allows measuring them all."""
        if not sturdy:
            work()
            return
        snap, saved, start = state.snapshot(), prog.save(), len(state.done)
        guard.in_class[...] = False
        before = guard.together.copy()
        work()
        if len(state.done) == start:
            return
        blamed = guard.check(state, start, broad=False)
        if blamed is None:
            return
        refused: set[tuple[Placement, ...]] = set()
        for attempt in range(_STURDY_ROUNDS + 2):
            if not blamed or attempt == _STURDY_ROUNDS + 1:
                # nothing left to blame: refuse the whole class
                blamed = [(k, guard.hanging) for k in state.done[start:]]
                guard.refuse(state, blamed)
                refused.update(k for k, _ in blamed)
                state.restore(snap)
                prog.load(saved)
                break
            guard.refuse(state, blamed)
            refused.update(k for k, _ in blamed)
            state.restore(snap)
            prog.load(saved)
            work()
            if len(state.done) == start:
                break
            blamed = guard.check(state, start, broad=attempt + 1 >= _STURDY_ROUNDS)
            if blamed is None:
                break
        if not guard.affords(len(refused), len(state.parts)) or not guard.start(state):
            return  # the refusals stand, noted as made in rounds
        state.banned -= refused
        guard.rounds[...] = guard.together
        guard.together[...] = before
        guard.in_class[...] = False
        prog.failed[:] = saved.failed
        state.watch = lambda key: guard.keeps(state, key)
        try:
            work()
        finally:
            state.watch = None

    def mark_refused(cells: Iterable[tuple]) -> None:
        if state.refusal == "sturdy":
            return  # the guard has marked the cells already
        refused = tried.loose if state.refusal == "loose" else tried.refused
        for c in cells:
            refused[c] = True

    clear = ~filled & ~detail_mask
    candidates = _slope_candidates(design, catalog, sloped, smooth, clear, state.usable)
    for cand in candidates:
        for c in cand.slanted:
            tried.candidate[c] = True

    # one class at a time (tall before cheese, two-wide before one-wide), so a better part
    # that only fits once its neighbours have changed is retried before a lesser one takes over
    def place_slope(cand: _Candidate) -> bool | None:
        sl = catalog.cells(cand.placement)
        if claimed[sl].any():
            return None
        variants = _VARIANTS_TALL if -cand.key[0] >= 3 else _VARIANTS_LOW
        if any(guard.in_class[c] for c in cand.slanted):
            return False
        if not state.swap(cand.placement, variants, cover):
            mark_refused(cand.slanted)
            return False
        claimed[sl] = True
        for c in cand.slanted:
            prog.slanted[c] = True
        return True

    def slope_class(group: list[_Candidate]) -> Callable[[], None]:
        def work() -> None:
            prog.n_slopes += _with_retries(group, place_slope)

        return work

    for _, group in groupby(candidates, key=lambda c: c.key[:2]):
        guarded(slope_class(list(group)))

    def place_tiles(tiles: list[Placement]) -> bool | None:
        slices = [catalog.cells(t) for t in tiles]
        if any(claimed[sl].any() for sl in slices):
            return None
        if any(guard.in_class[sl].any() for sl in slices):
            return False
        if not state.swap(tiles, ("plates",), cover):
            mark_refused(slices)
            return False
        for sl in slices:
            claimed[sl] = True
            prog.tiled[sl] = True
        return True

    def place_tile(tile: Placement) -> bool | None:
        return place_tiles([tile])

    wanted_tiles = smooth & state.usable & ~claimed
    exact = _exact_tiles(state, wanted_tiles, cover)
    rest = wanted_tiles.copy()
    for tile in exact:
        rest[catalog.cells(tile)] = False
    plan = exact + _tile_plan(rest, design.colors, cover)
    for tile in plan:
        tried.planned[catalog.cells(tile)] = True

    def plan_tiles() -> None:
        prog.n_tiles += _with_retries(plan, place_tile, prog.failed)

    # a tile refused whole straddled parts in a way that loosens something: cover what each
    # part underneath still wants on its own, in several tilings, keeping the first that holds
    def replan_tiles() -> None:
        prog.n_tiles += _replan_tiles(
            state, prog.failed, wanted_tiles & ~claimed, cover, place_tiles
        )

    # what is still refused: try its cells one by one, some may still take a tile
    def single_tiles() -> None:
        singles = []
        for tile in prog.failed:
            w, d, _ = catalog.footprint(tile)
            one = cover(np.ones((1, 1), dtype=bool), TILE_KIND, tile.color)
            if w * d > 1 and one:
                singles += [
                    Placement(one[0][0], tile.color, tile.x + i, tile.y + j, tile.z)
                    for i in range(w)
                    for j in range(d)
                ]
        prog.n_tiles += _with_retries(singles, place_tile)

    for work in (plan_tiles, replan_tiles, single_tiles):
        guarded(work)

    slanted, tiled = prog.slanted, prog.tiled
    n_slopes, n_tiles = prog.n_slopes, prog.n_tiles
    fell_back: tuple | None = None
    if state.swaps == 0 and not details:
        parts = list(build.parts)
    else:
        parts = state.final_parts()
        last = max((p.step for p in parts), default=0)
        parts += _detail_steps(details, last + 1)
        if not _verify(state, parts, detail_mask):
            # never expected; keep the input as it was rather than hand back a worse build
            fell_back = (_OTHER,)
            _fell_back("section 5")
        elif not guard.holds(parts):
            if not sturdy:
                return None
            # never expected: each class was measured as it went
            worst = max(guard.worst, guard.hanging)
            fell_back = (_TOGETHER, worst, worst == guard.worst)
            _fell_back("sturdiness")
        if fell_back is not None:
            n_slopes = n_tiles = 0
            slanted[:] = False
            tiled[:] = False
            parts = list(build.parts)
            last = max((p.step for p in parts), default=0)
            with_details = parts + _detail_steps(details, last + 1)
            if details and _verify(state, with_details, detail_mask):
                parts = with_details
            else:
                details = []

    notes = list(build.notes)
    if smooth.any() or sloped.any() or design.details:
        notes.append(
            f"Finishing placed {_count(n_tiles, 'tile')}, {_count(n_slopes, 'slope')} and "
            f"{_count(len(details), 'detail part')}."
        )
        reasons: dict[tuple, list[tuple[int, int, int]]] = {}
        marked = (design.finish == FINISH_SMOOTH) | (design.finish == FINISH_SLOPED)
        for c in np.argwhere(filled & above_empty & under & marked):
            x, y, z = (int(v) for v in c)
            name = "smooth" if design.finish[x, y, z] == FINISH_SMOOTH else "sloped"
            reasons.setdefault((name, _DETAIL), []).append((x, y, z))
        if fell_back is not None:
            for name, left in (("smooth", smooth & ~tiled), ("sloped", sloped & ~slanted)):
                for c in np.argwhere(left):
                    reasons.setdefault((name, *fell_back), []).append(_cell(c))
        else:
            _why_left(
                design,
                catalog,
                state,
                smooth & ~tiled,
                sloped & ~slanted,
                claimed,
                tried,
                guard,
                smooth,
                sloped,
                clear,
                reasons,
            )
        notes += _reason_notes(reasons, catalog)
        notes += detail_notes
    return Build(
        shape=build.shape, parts=parts, report=None, design_id=build.design_id, notes=notes
    )
