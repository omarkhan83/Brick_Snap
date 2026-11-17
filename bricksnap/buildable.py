"""Design to Design: change the shape as little as possible so it can be built in one piece.

Parts hold each other only through studs, vertically. So some Designs have no layout in
which everything is attached: a feature in its own colour that touches the body only at its
side (a nose on a face), a sheet one plate thin, a part that hangs in the air. This pass
finds what the layout solver could not attach and repairs the Design in the least visible
way it can, and says what it did.

CONTRACT (tests go in tests/test_buildable.py)

``make_buildable(design, catalog, seed=0, max_solves=12, max_sturdy_solves=8) -> BuildableResult``

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
again. Stop as soon as there is one piece, or after ``max_solves`` solves. Then cure the
worst weak spots (below), with solves of its own.

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
2. Fill partly covered cells (stage 3). ``Design.skin`` lists the empty cells the model
   passes through but covers less than half of, each with its own colour. Those next to
   the loose piece are filled, in their own colour (not the piece's): the model is there,
   so the outline moves by less than half a cell. First those directly above or below the
   piece alone, then all those touching it, then also those touching them. It is what
   holds a whisker that touches the head only through an eye. Edits do not change the
   skin, so once the Design has been edited (its log is not empty), a cell's own colour is
   trusted only while a filled cell around it still has it; otherwise the model has been
   repainted there, and the cell takes the colour of the filled cells beside it.
3. Thicken. A loose piece that is a thin sheet (or the thin edge of one) gets cells added
   directly beneath it in its own colour, one plate at first, so that parts in two levels
   can overlap. Beneath, so the top surface stays as designed. A sheet lying on the ground
   one plate thin has nothing beneath it, so it is thickened from above instead (stage 3).
   Every cell added goes directly under (or on) a cell of the sheet as it was in the input
   Design, never under a cell another repair added.
4. Clamp (stage 3). A piece that touches the rest of the model only at its sides (nothing
   directly above or below it) gets ONE cell of the body's colour directly under one of
   its cells that touch the body, or on top of it when there is no room under, beside a
   cell of the body in that colour: a part of the body can then reach across under (or
   over) the piece and hold it.
5. Support. A loose piece that hangs in the air gets a column of cells from its underside
   straight down to the first filled cell or the ground, in its own colour, placed where it
   is hidden (inside a hollow) when that is possible and otherwise under the middle of the
   piece.
A piece that stands on the ground by itself and touches nothing (a second, separate object)
is not bridged; it is reported.

STAGE 3 ADDITION TO THE CONTRACT: the pass also cures the worst weak spots
One piece is not enough. With the thinner fill, a model can be one piece and still hang
together by a thread: in the sample pineapple at 16 studs, 124 of 240 parts hang on a single
stud, because the fill left one cell between the body and the crown where the model is
three studs wide; the spaceship's engine pods and the hat's brim touch the rest only side by
side. The layout solver cannot cure these, because it may not add cells. This pass can.

- After the model is one piece (or as close as the pass can get), look at the build's lone
  links (``bricksnap.connect.lone_links``: a part, or a single-stud joint, that is a
  group's only connection, and the cells that hang on it). A lone link is *heavy* when the
  cells hanging on it are at least 40, or at least a tenth of the model's filled cells,
  whichever is smaller, and at least 12.
- For each heavy lone link, heaviest first (those where the Design itself is cut before
  those the layout could have avoided), try to give its group a second connection, in this
  order, keeping a change only if the build has no more heavy weak spots than before (a
  stack of links in one thin place is one weak spot) and either the heaviest load in the
  whole build goes down by at least 12 cells, or it does not go up, there are fewer heavy
  weak spots and nothing heavy hangs at the cured place any more; and only if the model
  has no more pieces than before (one, when it was one piece) and nothing that was
  attached comes loose. Partly covered cells of a kept change that a fresh solve can do
  without are taken away again:
  1. fill partly covered cells (skin) around the link: the cells beside the part or joint
     and beside the group's cells next to it, in their own colour, smallest set first;
  2. recolour hidden cells there, as for loose pieces, so one part can span the seam where
     two colours meet;
  3. where the group touches the rest only side by side, add ONE cell (a clamp, as for loose
     pieces) so a part of the body reaches across.
  It never thickens or adds support columns for a weak spot: those change the look too much
  for something that already holds.
- Bounded: this phase may use at most ``max_sturdy_solves`` solves (default 8) beyond those
  the pass already used, taking away included, and stops early when no heavy lone link is
  left; 0 leaves it out. It starts no solve that would end the pass more than 8 seconds
  after it began, so a 16-stud model still finishes in under 10 seconds (unless repairing
  what was loose took that long by itself). This is the one place where the clock matters:
  on a machine slow enough for it to bind, fewer weak spots are cured.
- The guarantees of the pass hold unchanged: nothing emptied, no visible cell recoloured,
  every filled or added cell reported in the masks and in a note. The notes for this phase
  say what was hanging and on what, what was done, and how it hangs in the build the pass
  returns (not in the build right after that one change), for example: "Filled 3 partly
  covered cells at x=4 to 6, y=5, z=16 to 19 so that the top of the model (116 parts, 331
  cells) no longer hangs on a single stud at x=6, y=4, z=17 to 18 alone."
- A model with no heavy lone link comes back exactly as before this addition.
- What is left is said plainly: a heavy lone link the phase could not cure gets a note
  with its place, how much hangs on it, and why nothing helped (no partly covered cell
  beside it, for instance: the model really is that thin there), or that the pass ran out
  of attempts before it could try what it could have tried there. These notes come after
  what is still loose and before the other repairs; a model with nothing loose that has
  only such notes is otherwise returned unchanged.

Tests must include: a body and a crown joined through one cell where skin cells surround
it (cured by filling skin, and the heaviest load drops); two blocks of different colours
touching side by side with hidden cells at the seam (cured by recolouring); a pod beside a
hull touching only side by side with no skin (cured by one clamp cell); a neck that really
is one cell wide with no skin beside it (not cured, and the note says so); a model with no
heavy lone link (unchanged, same fingerprint); the sample pineapple, spaceship and hat at
16 studs (heaviest load lower than without this phase, still one piece, all guarantees
hold); every sample at 12, 16 and 24 studs still builds with no loose parts. After review:
only cells beside the link, each needed (the crown with partly covered cells far from its
neck); a bound that binds (four heads, budgets 1, 2 and 8) and a clock that binds (solves
that take 3 seconds each); a weak spot never reached that could not have been helped
anyway, told apart from one the solves ran out for; the cat at 24 studs no weaker after
finishing than without the phase; few cells at 12 and 16 studs; notes true of the build
returned.

What must be true of the result
- No filled cell is ever emptied, and the colour of a visible cell is never changed. The
  look changes only through added cells, and every added cell is reported. A cell added
  by thickening, a clamp, a support column or cells beside grows from a cell of the input
  Design, not from one another repair added (that one may be taken away again).
- ``result.design`` keeps the input's finish, details, regions, log and seed_offset; added
  cells get FINISH_STUDS. Nothing is appended to the log (these are not a person's edits).
- ``pieces_after <= pieces_before``. If the first solve is already one piece with no heavy
  lone link (or the Design is empty), nothing is changed: both masks are all False,
  ``notes`` is empty, and ``result.design.fingerprint() == design.fingerprint()``.
- When it cannot reach one piece, it returns the best Design it found (fewest pieces, then
  fewest changed cells) and a note saying what is still loose, where, and why nothing
  helped.
- Notes are for the AI designer and for people: plain words, counts and coordinates, for
  example "Recoloured 6 hidden cells behind the Dark Pink part at x=6 to 7, y=3, z=12 to 14
  so that it is held from inside." or "Added 16 cells under the sheet at x=2 to 9, y=0 to
  1, z=11: it was one plate thin and nothing held its outer edge." Each repair has its own
  kind of note: "Filled 2 partly covered cells at ... Light Bluish Grey next to the ...
  part ..., so that it is held: the model passes through those cells, so the outline moves
  by less than half a cell.", "Added 1 White cell at ... under the Black part at ... so that
  a White part of the body reaches across under it and holds it: it touched the body only
  at its side.", and "Added 40 Black cells on top of the sheet at ...: it was one plate
  thin and lay on the ground, where nothing can go beneath it, ...".
- Deterministic for a given ``seed``. A 16-stud model in under 10 seconds.

Tests must include: a nose in its own colour on the front of a head; two colours meeting on
one vertical plane through a thick block; a wide cap one plate thin on a narrow stem; a
table whose top is one plate thin; a bar floating above the model; two separate objects
(reported, not bridged); and a model that needs nothing (returned unchanged, partly covered
cells and all). Stage 3 adds: a whisker held only by an eye, joined through a partly
covered cell in that cell's own colour; the same whisker with no partly covered cells,
joined by a clamp (and on top when there is no room under); and a sheet on the ground
thickened from above. After review: a partly covered cell in the colour painted around it
after an edit; one two steps from the piece; one directly under the piece used alone when
the one beside it would get in the way; no clamp for a piece with the model above or below
it; and a thickening that rests only on the sheet's own cells.

Implementation notes
--------------------
Each loose piece of a solve becomes a *spot*, followed from solve to solve by the cells it
covered. A spot climbs a ladder of repairs, one rung per solve while it stays loose, and each
rung replaces the one before (its cells go back to the input): recolour hidden cells 1, 2,
then 3 studs deep (spreading side to side through hidden cells only, in the piece's own
levels, each cell taking the colour of the piece cell it was reached from); fill the
partly covered cells touching the piece, then also those touching them (through faces,
up and down included, each in its own colour; on the first of these rungs, those directly
above or below the piece alone are offered first, unless the floor joins the piece
already and so cannot tell whether they help); thicken (a plate under the piece's
one-plate-thin cells, then also under thin cells of the sheet within 2 studs, then under
the whole sheet; on top for a sheet on the ground); a clamp; a support column; and cells
beside it (below). All loose pieces are repaired at once, so one solve serves them all.

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
  place where the layout fell short), only the invisible recolour, the partly covered cells
  and the plate beneath (or on top of) a thin sheet are offered, never a clamp, a column or
  cells beside it.

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
  (z = 0, nothing above) is thickened from above, by the same rule: nothing goes below
  z = 0. Only when nothing can go above either (the top of the grid, or detail parts
  there) is it reported.
- Partly covered cells: only cells still empty in the Design, never a cell a detail part
  stands in. The rung fills every such cell next to the piece (after those directly above
  or below it, alone); once the best Design is found, those that hold nothing go (taking
  each out of the build splits no piece), and then each of the rest alone, each judged by
  a solve as below.
- Clamp: the cell goes where it touches the most filled cells (tucked in), under before on
  top, and its colour is that of the body cells beside it in its level (the most common;
  the lower code on a tie). The body cell beside it must be one of the Design's own, not
  one added by another repair: clamps on clamps make a chain that no part can span.
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
  piece; and then each filled partly covered cell alone (those touching the piece least
  first, those directly above or below it last), then every other spot's added cells, one
  spot at a time, biggest first, since a fresh layout may not need what the build leaned
  on. On the test mushroom the added plate goes from 76 cells to 32, on the table from 58
  to 27. On the sample models at 12, 16 and 24 studs, 26 partly covered cells are filled
  in all, 8 of which a fresh solve could still do without (with one guess at what to
  trim: 29, of which 13). The pruning shares the pass's limits on solves and slow solves;
  a try that is worse no longer ends it by itself.
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

The worst weak spots (``_sturdy``) come after the loose pieces and their pruning, on the
best Design found (or straight on the input when its first solve is one piece). The link's
*place* is the part's cells, or for a single-stud joint the two cells of that stud; the
group is the cells of the parts that hang on it, the rest all other cells but the link's
part. Before any solve, a change must be able to help, judged on the floor as for loose
pieces: when the floor itself has no way between group and rest without the link
(``floor_labels`` with the part's cells emptied, or that one stud's join cut), the change
must make one; otherwise it must at least touch both group and rest. Links of the first
kind go first (heaviest first among them): in a thin place several links stack up (the
pineapple's single cell is three joints and a part, one on the other), and only curing the
one the Design itself cuts can help; once it is given up, the links stacked on it (whose
group holds its group) are given up with it.
- The changes for a link, each the first that could help being solved: partly covered
  cells, the fewest first, of four sets: those touching both group and rest within two
  cells of the place; those touching the place; those touching the place or the group's
  and the rest's cells beside it; and also those touching them (``_skin``, so their colour
  is the model's own, or the colour painted around them after an edit). Then hidden cells
  of the rest within two cells of the place, given the group's colour 1 and then 2 studs
  deep (``_recolour``), and then one clamp cell (``_clamp``, given the group as the piece
  and the rest without the link's place as what it may touch only at its sides). The
  first change that the solve shows to be better is kept, and the links are found again
  on its build; a link none of whose changes is better is given up.
- Better (``_better``): no more heavy weak spots, where a weak spot is a stack of links
  in one thin place (``_stacks``: each carrying nearly all of what the heaviest of them
  carries, as in the notes), and then either the heaviest load (cells, over every lone link
  of the build) goes down by at least ``HEAVY_MIN`` cells, or there are fewer heavy weak
  spots, the heaviest load does not go up, and nothing heavy within two cells of the cured
  link carries most of what hung on it (``_now_at``). "Goes down" alone let the bottle at
  12 studs grow its neck one layer per solve (96 cells hanging, then 92, 88 and so on: 144
  cells added to a model of 148 for a load of 56). Counting every lone link let a change
  that turns a stack of two links into one count as a cure (the cat's front legs at 24
  studs, which then held worse after finishing than with no change at all); requiring only
  that the cured link carry 12 cells less let a leg's weak spot move three cells down for
  24 cells (74 to 54), which finishing alone would have held at 36; and a lower heaviest
  load bought with one more weak spot let one clamp cell on the pineapple at 24 studs hang
  41 cells more on the part it was meant to relieve.
- Taking away (partly covered cells only; a clamp is one cell and a recolour cannot be
  seen). First, without a solve (``_ranked``), the cells the new build leans on: taken out
  of it one at a time, farthest from the link first, each stays out when the build without
  it (``_estimate``: each part keeps its other cells and holds through those, and a part
  that falls into two is two) has no more pieces, no heavier load and no more heavy weak
  spots; those that cannot stay out are the ones it leans on. That alone is a poor judge
  of what a fresh layout needs (on the spaceship at 16 studs, the 2 of 16 cells it leans
  on leave a fresh layout hanging 102 cells), so then up to ``PRUNE_TRIES`` solves search,
  by halves, for the shortest list of cells (those it leans on first, then the others
  nearest the link first) with which a fresh solve does as well: no more pieces or heavy
  weak spots, and no heavier load unless that load is not heavy at all. These solves count
  towards ``max_sturdy_solves``. A change the new build leans on none of is sturdier by
  the tiling the cells brought about (on the cat at 24 studs, 3 cells beside a hind leg):
  it is kept, and its cells are taken away last, with the solves the phase has left once
  no link is left to try, the search starting from the one cell nearest the link (so that
  taking away never costs a cure: on the hat at 12 studs, searching straight away left two
  weak spots uncured for 3 cells fewer). Not keeping such changes at all cost the
  pineapple at 16 studs a clamp cell that takes its heaviest load from 50 cells to 28.
- Cells changed by the loose repairs, and cells under detail parts, are never changed
  again. The phase stops when its solves are spent, after ``SLOW_PATIENCE`` solves that
  could not reach the floor of their Design, when no link is left to try, or when the
  next solve, if it took as long as the longest one of the phase so far, would end later
  than ``STURDY_SECONDS`` after the pass began. A model where nothing could be tried (the
  neck in the tests) costs no solve at all.
- Notes: one per change kept, saying what hung on what and how it hangs in the build that
  is returned (``_cure_words``: the lightest heavy link there that carries most of the
  cured group, named as it is now, or none); then one per weak spot left, heaviest first
  (a stack of links in one place is one note, at the heaviest), at most ``LEFT_NOTES`` of
  them and a count of the rest. When the phase ran out of solves or time, a weak spot it
  never reached is looked at without a solve, in the order the phase would have taken its
  links, to say whether anything could have been tried there ("ran out of attempts") or
  not ("the model really is that thin there").
- Measured on the sample models at 12, 16 and 24 studs (heavy links of this pass's build,
  without the phase, then with it): 57 to 19 (before the review: 23), none left at 16
  studs; 106 cells added in all (before: 218), none recoloured; at 16 studs pineapple 4,
  spaceship 4, hat 6; at 12 studs hat 15 (before: 53), pawn 6 (before: 44). After
  finishing, heavy links go from 50 to 16 (before: 24), and no sample is weaker after
  finishing than without the phase (the cat at 24 studs had ended with 2 where finishing
  alone left none). Left: the bottle at 12 studs (its neck is two cells wide), the cat's
  legs at 24 (4, none after finishing), the hat at 24 (its solves ran out:
  11 left), and the pineapple at 24 (3), whose crown is a hollow wall one cell thick with
  no partly covered cell near it. Most cells are still at 24 studs: the bottle 22, the
  spaceship 25 and the hat 16, where the search ran out of solves before it found fewer.
  The phase made 61 solves in all over the 33 runs; the slowest pass is the hat at 12
  studs, 4 seconds. Every sample still builds with no loose parts.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import networkx as nx
import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from bricksnap.catalog import Catalog
from bricksnap.connect import connection_graph, lone_links, occupancy
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
SKIN_REACH = (1, 2)  # steps from the loose piece through partly covered cells
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


def floor_labels(colors: np.ndarray, cut: np.ndarray | None = None) -> np.ndarray:
    """int [x, y, z]: which piece each cell is in when every two vertically adjacent cells
    and every two side-by-side cells of one colour are joined; -1 where empty. ``cut`` (bool
    [x, y, z]) leaves out the join between a cell and the one directly above it.

    No layout can join cells this does not join (see the layout solver's notes), so a loose
    piece in a different label from the main piece cannot be attached without a change.
    """
    filled = colors != EMPTY
    idx = np.full(colors.shape, -1, dtype=np.int64)
    n = int(filled.sum())
    idx[filled] = np.arange(n)
    rows, cols = [], []
    m = filled[:, :, :-1] & filled[:, :, 1:]
    if cut is not None:
        m &= ~cut[:, :, :-1]
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
    kind: str = ""  # "recolour" | "skin" | "thicken" | "clamp" | "support" | "extend"
    tried: list[str] = field(default_factory=list)  # kinds that were applied at some point
    piece: np.ndarray | None = None  # the loose cells when the repair in place was chosen
    # support: hidden, upwards, touched; thicken and clamp: (False, upwards, False)
    column: tuple[bool, bool, bool] = (False, False, False)
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
    *(("skin", r) for r in SKIN_REACH),
    *(("thicken", r) for r in THICKEN_REACH),
    ("clamp", 1),
    ("support", 0),
    ("extend", 1),
)
_SIX = ndimage.generate_binary_structure(3, 1)


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


def _skin(colors, skin, piece, claimed, reach, edited) -> dict[Cell, int]:
    """Partly covered cells (``Design.skin``) next to the piece, up to ``reach`` steps away
    through such cells (6-connected), each in the colour of the model there (see
    ``_skin_colour``). With ``reach`` 0, only those directly above or below the piece."""
    free = (skin != EMPTY) & (colors == EMPTY) & ~claimed
    reached = piece.copy()
    found = np.zeros(piece.shape, dtype=bool)
    now = colors.copy()
    out: dict[Cell, int] = {}
    for _ in range(max(reach, 1)):
        if reach == 0:
            near = np.zeros(piece.shape, dtype=bool)
            near[:, :, 1:] |= piece[:, :, :-1]
            near[:, :, :-1] |= piece[:, :, 1:]
            near &= free
        else:
            near = ndimage.binary_dilation(reached, _SIX) & free & ~found
        if not near.any():
            break
        step = {
            (int(x), int(y), int(z)): _skin_colour(
                now, piece, (int(x), int(y), int(z)), skin, edited
            )
            for x, y, z in np.argwhere(near)
        }
        for c, colour in step.items():
            now[c] = colour
        out.update(step)
        found |= near
        reached |= near
    return out


def _skin_colour(
    colors: np.ndarray, piece: np.ndarray, cell: Cell, skin: np.ndarray, edited: bool
) -> int:
    """The colour a partly covered cell is filled in: the one the conversion gave it
    (``skin``), unless the Design has been ``edited`` since and no filled cell around it
    (of the 26 that share a face, an edge or a corner with it) still has that colour. Edits
    do not change the skin, so such a colour may be one the model no longer has there; the
    cell then takes the most common colour of the filled cells beside it (through a face)
    that are not the loose piece, or of the piece when only the piece is beside it (the
    lower code on a tie)."""
    x, y, z = cell
    own = int(skin[cell])
    if not edited:
        return own
    around = colors[max(x - 1, 0) : x + 2, max(y - 1, 0) : y + 2, max(z - 1, 0) : z + 2]
    if (around == own).any():
        return own
    beside, of_piece = [], []
    for dx, dy, dz in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
        a, b, k = x + dx, y + dy, z + dz
        if not (0 <= a < colors.shape[0] and 0 <= b < colors.shape[1] and 0 <= k < colors.shape[2]):
            continue
        if colors[a, b, k] != EMPTY:
            (of_piece if piece[a, b, k] else beside).append(int(colors[a, b, k]))
    pick = beside or of_piece
    return min(set(pick), key=lambda c: (-pick.count(c), c)) if pick else own


def _on_the_ground(colors: np.ndarray) -> np.ndarray:
    """Cells of a sheet one plate thin lying on the ground: z = 0, nothing directly above."""
    filled = colors != EMPTY
    out = np.zeros(filled.shape, dtype=bool)
    out[:, :, 0] = filled[:, :, 0]
    if filled.shape[2] > 1:
        out[:, :, 0] &= ~filled[:, :, 1]
    return out


def _thicken(colors, piece, claimed, reach, base) -> tuple[dict[Cell, int], bool]:
    """Cells directly beneath the piece's one-plate-thin cells, and whether they go above
    instead: a sheet lying on the ground has nothing beneath it, so it is thickened from
    above (its top changes, but nothing else could hold it).

    Only cells of the input Design (``base``) count as the sheet, and as what makes it thin
    or not: cells other repairs added may yet be taken away again, and a cell added on (or
    under) one of them would then be left with nothing of the sheet above or below it."""
    piece = piece & base
    for thin, step in ((_thin(colors) & base, -1), (_on_the_ground(colors) & base, 1)):
        start = piece & thin
        # a sheet, or the thin edge of one; a body with a few thin cells somewhere is not
        if not start.any() or THIN_SHARE * piece.sum() > start.sum():
            continue
        if step > 0 and colors.shape[2] < 2:
            continue
        if reach:
            more, _ = _grow_in_layers(start, colors, thin, reach)
            start = start | more
        out: dict[Cell, int] = {}
        for x, y, z in np.argwhere(start):
            cell = (int(x), int(y), int(z) + step)
            if not claimed[cell]:
                out[cell] = int(colors[x, y, z])
        return out, step > 0
    return {}, False


def _clamp(colors, piece, target, claimed, original, other=None) -> tuple[dict[Cell, int], bool]:
    """ONE cell of the body's colour directly under (or else on top of) a cell of the piece
    that touches the body at its side, beside a cell of the body in that colour, so that a
    part of the body can reach across under (or over) the piece and hold it. Only for a
    piece that touches the rest of the model at its sides alone. Returns the cell and
    whether it is on top. The body cell beside it must be one of the Design's own
    (``original``), not one another repair added: one cell holds only next to the body. So
    must the piece's cell it goes under or on top of, since cells other repairs added may
    yet be taken away again. ``other`` is the rest of the model the piece must touch at
    its sides alone (by default every filled cell outside the piece)."""
    filled = colors != EMPTY
    if other is None:
        other = filled & ~piece
    if (piece[:, :, 1:] & other[:, :, :-1]).any() or (piece[:, :, :-1] & other[:, :, 1:]).any():
        return {}, False
    held = target & filled & ~piece & (original == colors)
    roots = np.zeros(piece.shape, dtype=bool)
    for dx, dy in _STEPS4:
        roots |= piece & (original != EMPTY) & _layer_shift(other, -dx, -dy, False)
    nz_ = colors.shape[2]
    best = None
    for x, y, z in (tuple(int(v) for v in c) for c in np.argwhere(roots)):
        for step in (-1, 1):
            k = z + step
            if not 0 <= k < nz_ or filled[x, y, k] or claimed[x, y, k]:
                continue
            beside = []
            for dx, dy in _STEPS4:
                a, b = x + dx, y + dy
                if 0 <= a < colors.shape[0] and 0 <= b < colors.shape[1] and held[a, b, k]:
                    beside.append(int(colors[a, b, k]))
            if not beside:
                continue
            colour = min(set(beside), key=lambda c: (-beside.count(c), c))
            around = int(
                ndimage.binary_dilation(_mask(colors.shape, [(x, y, k)]), _SIX)[filled].sum()
            )
            key = (-around, step > 0, x, y, k)
            if best is None or key < best[0]:
                best = (key, (x, y, k), colour, step > 0)
    if best is None:
        return {}, False
    _, cell, colour, up = best
    return {cell: colour}, up


def _support(
    colors, piece, claimed, enclosed, base
) -> tuple[dict[Cell, int], tuple[bool, bool, bool]]:
    """A column under the piece down to the first filled cell, and (whether it is hidden,
    whether it goes up, whether the piece touches the model). The column starts from a cell
    of the input Design (``base``), not from one another repair added.

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
    piece = piece & base
    if not piece.any():
        return {}, none
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


def _extend(colors, piece, claimed, base) -> dict[Cell, int]:
    """Cells in the piece's colour beside it, in empty cells resting on (or under) the model,
    so a part can reach from the piece over the model's studs. Both the piece's cell they
    grow from and the model's cell they rest on are cells of the input Design (``base``)."""
    filled = colors != EMPTY
    body = filled & ~piece & base
    held = np.zeros(filled.shape, dtype=bool)
    held[:, :, 1:] |= body[:, :, :-1]
    held[:, :, :-1] |= body[:, :, 1:]
    cells, col = _grow_in_layers(piece & base, colors, ~filled & ~claimed & held, 1)
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
_SHOWN_IF_JOINED = ("recolour", "skin", "thicken")  # rungs worth trying when the floor joins
STURDY_SOLVES = 8  # default for ``max_sturdy_solves``
HEAVY_CELLS = 40  # a lone link is heavy with at least this many cells hanging on it,
HEAVY_SHARE = 1 / 10  # or this share of the model's filled cells, whichever is smaller,
HEAVY_MIN = 12  # and never fewer than this
LEFT_NOTES = 5  # weak spots left that get a note of their own; the rest are counted
PRUNE_TRIES = 4  # solves to find what of a kept change a fresh layout does without
STURDY_SECONDS = 8.0  # the weak-spot phase starts no solve that would end the pass later


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
    skin: np.ndarray,
    edited: bool,
) -> tuple[int, str, dict[Cell, int], tuple[bool, bool, bool]] | str | None:
    """The cheapest repair beyond the spot's current one that could join the piece to an
    anchor at all (judged on the floor of the Design); CARRIED when cells another spot
    added this round hold it already (see ``_joins``); or None.

    ``running`` holds the changes chosen so far, ``start`` is the Design just solved. When
    the floor joined the piece already in ``start`` (a sheet of one colour, or a place
    where the layout fell short), the floor cannot tell whether a change helps, so only the
    invisible recolour and the plate beneath a thin sheet are offered, never a column or
    cells beside it. ``skin`` is the Design's partly covered cells, ``edited`` whether the
    Design has been edited since the conversion (its log is not empty)."""
    claimed = _mask(running.shape, (c for o in spots if o is not s for c in o.change))
    piece, target, without, already, carried = _joins(s, piece, running, start, original, target)
    if not piece.any():
        return None
    if carried and not s.carry_failed:
        return CARRIED
    base = original != EMPTY
    for level in range(s.level + 1, len(_LADDER)):
        kind, amount = _LADDER[level]
        if already and kind not in _SHOWN_IF_JOINED:
            continue
        info = (False, False, False)
        options: list[dict[Cell, int]] = []  # smaller first: the first that could work is used
        if kind == "recolour":
            change = _recolour(without, piece, hidden, claimed, amount)
        elif kind == "skin":
            # those directly above or below the piece alone first: the fewer cells, the less
            # they can get in the layout's way, and only one of them is usually needed (not
            # when the floor joins the piece already: it cannot tell then whether they help)
            change = _skin(without, skin, piece, claimed | blocked, amount, edited)
            if amount == 1 and not already:
                options.append(_skin(without, skin, piece, claimed | blocked, 0, edited))
        elif kind == "thicken":
            change, up = _thicken(without, piece, claimed | blocked, amount, base)
            info = (False, up, False)
        elif kind == "clamp":
            change, up = _clamp(without, piece, target, claimed | blocked, original)
            info = (False, up, True)
        elif kind == "support":
            change, info = _support(without, piece, claimed | blocked, enclosed, base)
        else:
            change = _extend(without, piece, claimed | blocked, base)
        for option in (*options, change):
            if not option or option == s.change:  # the same Design again tells nothing new
                continue
            trial = without.copy()
            for c, colour in option.items():
                trial[c] = colour
            if _floor_joins(trial, piece, target):
                return level, kind, option, info
    return None


def make_buildable(
    design: Design,
    catalog: Catalog,
    seed: int = 0,
    max_solves: int = 12,
    max_sturdy_solves: int = STURDY_SOLVES,
) -> BuildableResult:
    from bricksnap.layout import solve

    started = time.perf_counter()
    nothing = np.zeros(design.shape, dtype=bool)
    build = solve(design, catalog, seed=seed)
    solves = 1
    pc = _pieces(build, catalog)
    pieces_before = pc.count
    if pc.count <= 1:
        st = _sturdy(design, design, build, pc, catalog, seed, max_sturdy_solves, started)
        work, build, pc = st.work, st.build, st.pc
        limit = heavy_limit(int(design.filled.sum()))
        notes = _sturdy_notes(catalog, work.colors, st, limit)
        if work is design:
            return BuildableResult(
                design.copy(), build, nothing, nothing.copy(), notes, pc.count, pc.count
            )
        recoloured = design.filled & (work.colors != design.colors)
        added = work.filled & ~design.filled
        return BuildableResult(work, build, recoloured, added, notes, pieces_before, pc.count)

    original = design.colors
    hidden = design.filled & ~visible_cells(design.filled)
    blocked = _detail_cells(design, catalog)
    assert design.skin is not None
    skin = design.skin
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
                    s, piece, running, start, original, spots, target, hidden, enclosed, blocked,
                    skin, bool(design.log),
                )  # fmt: skip
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

    _, _, work, build, pc, kept = best
    st = _sturdy(design, work, build, pc, catalog, seed, max_sturdy_solves, started)
    work, build, pc = st.work, st.build, st.pc
    limit = heavy_limit(int(design.filled.sum()))
    sturdy = _sturdy_notes(catalog, work.colors, st, limit)
    recoloured = design.filled & (work.colors != original)
    added = work.filled & ~design.filled
    notes = _notes(catalog, work, pc, spots, kept, ran_out, original, hidden, sturdy)
    result_design = work.copy() if work is design else work
    return BuildableResult(result_design, build, recoloured, added, notes, pieces_before, pc.count)


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
    - Partly covered cells filled for a joined piece go one by one, the same way: those
      whose taking out of the build splits no piece.
    All of that is tried at once; if that is worse, the recolouring alone, the partly
    covered cells alone, and then each of those spots alone. Then each filled partly
    covered cell is tried without, alone (those touching the piece least first: two steps
    away, then beside it, then directly above or below it), and then every other spot's
    added cells, one spot at a time, biggest first: the build may lean on cells that a
    fresh layout does not need (a part beside the piece can reach it as well), which only
    a solve can show. A Design already tried is not solved again. The pass's limits on
    solves and on slow solves hold throughout."""
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
    adding = [i for i, s in enumerate(kept) if s.kind in _ADDING]
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
    # partly covered cells filled for a joined piece go one by one when taking them out of
    # the build splits no piece (the repair fills every such cell next to the piece, and the
    # layout usually needs only some of them)
    for i, s in enumerate(kept):
        if s.kind != "skin" or i in sure:
            continue
        for c in sorted(s.change):
            trial = gone | _mask(design.shape, [c])
            rest = _held(occ, trial)
            if nx.number_connected_components(rest) <= len({piece_of[n] for n in rest}):
                gone = trial

    # each partly covered cell alone, last: those touching the piece least go first (two
    # steps away, then beside it, then directly above or below it, which hold best)
    singles: list[tuple[tuple[bool, bool, Cell], Cell]] = []
    for s in kept:
        if s.kind != "skin":
            continue
        piece = (s.piece if s.piece is not None else s.mask) & work.filled
        near = ndimage.binary_dilation(piece, _SIX)
        over = np.zeros(piece.shape, dtype=bool)
        over[:, :, 1:] |= piece[:, :, :-1]
        over[:, :, :-1] |= piece[:, :, 1:]
        singles += [((bool(over[c]), bool(near[c]), c), c) for c in s.change]
    skin_gone = frozenset(c for _, c in singles if gone[c])
    nobody: frozenset[int] = frozenset()
    no_cells: frozenset[Cell] = frozenset()

    def version(
        spots: list[_Spot], drop: frozenset[int], recolour: bool, skin_out: frozenset[Cell]
    ) -> list[_Spot]:
        out = [s.snapshot() for s in spots]
        for i, s in enumerate(out):
            if i in drop:
                s.change, s.kind = {}, ""
                continue
            if recolour and s.kind == "recolour":
                s.change = {c: v for c, v in s.change.items() if used[c]}
            elif s.kind == "skin":
                s.change = {c: v for c, v in s.change.items() if c not in skin_out}
            else:
                continue
            if not s.change:
                s.kind = ""
        return out

    def key(spots: list[_Spot]) -> tuple:
        return tuple(sorted((c, v) for s in spots for c, v in s.change.items()))

    first = (frozenset(sure), True, skin_gone)
    fallback = [
        (nobody, True, no_cells),  # the recolouring alone
        (nobody, False, skin_gone),  # the partly covered cells alone
        *((frozenset({i}), False, no_cells) for i in sure),
    ]
    queue = [first]
    rest_steps = [
        *((nobody, False, frozenset({c})) for _, c in sorted(singles)),
        *((frozenset({i}), False, no_cells) for i in others),
    ]
    current = kept
    seen = {key(kept)}  # the same Design again would tell nothing new
    while queue or rest_steps:
        step = queue.pop(0) if queue else rest_steps.pop(0)
        if solves >= max_solves or slow >= SLOW_SOLVES:
            break
        spots = version(current, *step)
        if key(spots) in seen:
            if step is first:
                queue = fallback
            continue
        seen.add(key(spots))
        trial = _apply(design, spots)
        tb = solve(trial, catalog, seed=seed)
        solves += 1
        tp = _pieces(tb, catalog)
        struggled = tp.count > _floor_count(trial.colors)
        slow += struggled
        if tp.count <= best[0]:
            best = (tp.count, _changed(spots), trial, tb, tp, spots)
            current = spots
        elif step is first:
            queue = fallback
    return best, solves, slow


def _contacts(occ: np.ndarray, removed: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(lower, upper, studs): the pairs of parts of a build where a cell of one lies directly
    on a cell of the other and neither cell is removed, with how many such cells (studs)."""
    lo, hi = occ[:, :, :-1], occ[:, :, 1:]
    keep = (lo >= 0) & (hi >= 0) & (lo != hi) & ~removed[:, :, :-1] & ~removed[:, :, 1:]
    if not keep.any():
        none = np.zeros(0, dtype=np.int64)
        return none, none, none
    pairs, studs = np.unique(np.stack([lo[keep], hi[keep]]), axis=1, return_counts=True)
    return pairs[0], pairs[1], studs


def _held(occ: np.ndarray, removed: np.ndarray) -> nx.Graph:
    """The parts of a build that keep a cell outside ``removed``, joined where a cell of one
    lies directly on a cell of another and neither cell is removed. (Bricks and plates have
    studs over their whole top, so this is the build's connection graph when nothing is
    removed.)"""
    lo, hi, _ = _contacts(occ, removed)
    g = nx.Graph()
    g.add_nodes_from(int(v) for v in np.unique(occ[(occ >= 0) & ~removed]))
    g.add_edges_from((int(a), int(b)) for a, b in zip(lo, hi, strict=True))
    return g


_ADDING = ("skin", "thicken", "clamp", "support", "extend")  # repairs that add cells

_TRIED_WORDS = {
    "recolour": "recolouring hidden cells next to it",
    "skin": "filling the partly covered cells next to it",
    "thicken": "adding a plate beneath it (or on top, on the ground)",
    "clamp": "adding a cell of the body's colour under or over it",
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
            "it, nor here on top of it, and parts side by side in one layer do not hold each "
            "other. To join it, make it two plates thick, or build something on it that "
            "reaches across from the rest of the model."
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
    sturdy: list[str],
) -> list[str]:
    """What is still loose, then the separate objects, then the notes of the weak-spot phase
    (``sturdy``), then what was added, then what was recoloured.

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
    on_top: dict[Cell, int] = {}
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
            (on_top if s.column[1] else sheet).update(s.change)
        elif s.kind == "skin":
            colours = sorted({_colour_name(catalog, v) for v in values})
            in_colour = (
                f"each in its own colour ({', '.join(colours[:-1])} and {colours[-1]})"
                if len(colours) > 1
                else colours[0]
            )
            text = (
                f"Filled {_count(n, 'partly covered cell', 'partly covered cells')} at {where} "
                f"{in_colour} next to {what}, so that it is held: the model passes through "
                f"{'that cell' if n == 1 else 'those cells'}, so the outline moves by less "
                "than half a cell."
            )
            added_notes.append((n, text))
        elif s.kind == "clamp":
            side = "on top of" if s.column[1] else "under"
            across = "over" if s.column[1] else "under"
            text = (
                f"Added {_count(n, colour + ' cell', colour + ' cells')} at {where} {side} "
                f"{what} so that a {colour} part of the body reaches across {across} it and "
                "holds it: it touched the body only at its side."
            )
            added_notes.append((n, text))
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
    by_colour: dict[int, list[Cell]] = {}
    for c, colour in sorted(on_top.items()):
        by_colour.setdefault(colour, []).append(c)
    for code, cells in sorted(by_colour.items()):
        colour = _colour_name(catalog, code)
        n = len(cells)
        text = (
            f"Added {_count(n, colour + ' cell', colour + ' cells')} on top of the sheet at "
            f"{_where(cells)}: it was one plate thin and lay on the ground, where nothing can "
            "go beneath it, so nothing held that part of it."
        )
        added_notes.append((n, text))
    added_notes.sort(key=lambda t: -t[0])
    recolour_notes.sort(key=lambda t: -t[0])
    return loose_notes + sturdy + [t for _, t in added_notes] + [t for _, t in recolour_notes]


# ---- the worst weak spots ------------------------------------------------------------------

_STURDY_WORDS = {
    "skin": "filling the partly covered cells beside it",
    "recolour": "giving the hidden cells at the seam its colour",
    "clamp": "adding a cell of the body's colour under or over it",
}


def heavy_limit(filled_cells: int) -> float:
    """Cells that must hang on a lone link for it to be *heavy*."""
    return max(HEAVY_MIN, min(HEAVY_CELLS, HEAVY_SHARE * filled_cells))


def _holds(cells: int, group: np.ndarray, other_cells: int, other_group: np.ndarray) -> bool:
    """Whether what hangs on another link (``other_group``) hangs on this one as well and is
    nearly all of what does: the two are one weak spot, a stack of links in a thin place."""
    inside = (other_group & group).sum()
    return bool(inside >= 0.9 * other_group.sum() and other_cells >= 0.8 * cells)


def _stacks(loads: list[tuple[int, np.ndarray]]) -> list[list[int]]:
    """Heavy links, given as (cells, group), gathered into weak spots: indices into
    ``loads``, heaviest first. A stack of links in one thin place (a neck, a column), each
    carrying nearly all of what the heaviest of them carries, is one weak spot."""
    out: list[list[int]] = []
    for i in sorted(range(len(loads)), key=lambda k: -loads[k][0]):
        stack = next((s for s in out if _holds(*loads[s[0]], *loads[i])), None)
        if stack is None:
            out.append([i])
        else:
            stack.append(i)
    return out


@dataclass
class _Link:
    """A heavy lone link of a build, in cells of the Design."""

    cells: int  # cells that hang on it
    load: int  # parts that hang on it
    group: np.ndarray  # cells of the parts that hang on it
    rest: np.ndarray  # cells of every other part, the link's own part left out
    at: np.ndarray  # the link: the part's cells, or the two cells of the single stud
    cut: np.ndarray | None  # for a stud: the join to leave out (see ``floor_labels``)
    lifted: bool  # the group stands on the ground itself, and comes away when lifted
    apart: bool = False  # the floor of the Design has no other way between group and rest
    tried: list[str] = field(default_factory=list)  # kinds of repair a solve judged
    found: list[str] = field(default_factory=list)  # kinds of repair that could be tried

    def same_place(self, other: _Link) -> bool:
        """The same weak spot, after a fresh layout may have moved it a little."""
        if not (self.at & ndimage.binary_dilation(other.at, _CUBE)).any():
            return False
        both = (self.group & other.group).sum()
        return bool(both * 2 >= (self.group | other.group).sum())

    def holds(self, other: _Link) -> bool:
        """``other`` hangs on this link as well and is nearly all of what does (``_holds``)."""
        return _holds(self.cells, self.group, other.cells, other.group)

    def near(self, other: _Link) -> bool:
        """Whether the other link is within two cells of this one."""
        return bool((other.at & ndimage.binary_dilation(self.at, _CUBE, iterations=2)).any())

    def take(self, other: _Link) -> None:
        """Add what was tried and found at the other link (the same weak spot) to this one."""
        self.apart = self.apart or other.apart
        self.tried = list(dict.fromkeys(self.tried + other.tried))
        self.found = list(dict.fromkeys(self.found + other.found))


_CUBE = np.ones((3, 3, 3), dtype=bool)


def _links(
    build: Build, catalog: Catalog, colors: np.ndarray | None, limit: float
) -> tuple[list[_Link], int]:
    """The heavy lone links of a build, each in cells, and the heaviest load (cells) of any
    lone link. Given the Design's ``colors``, also whether the floor of the Design itself has
    another way between each group and the rest (``apart`` when it has not)."""
    occ = occupancy(build, catalog)[0]
    filled = occ >= 0
    out: list[_Link] = []
    found = lone_links(build, catalog)
    for ln in found:
        if ln.cells < limit:
            continue
        group = np.isin(occ, ln.members)
        cut = None
        if ln.joint is not None:
            lo, hi = ln.joint
            cut = np.zeros(occ.shape, dtype=bool)
            cut[:, :, :-1] = (occ[:, :, :-1] == lo) & (occ[:, :, 1:] == hi)
            at = cut.copy()
            at[:, :, 1:] |= cut[:, :, :-1]
            rest = filled & ~group
        else:
            at = occ == ln.part
            rest = filled & ~group & ~at
        lk = _Link(ln.cells, ln.load, group, rest, at, cut, ln.lifted)
        if colors is not None:
            lk.apart = not _link_joined(colors, lk, {})
        out.append(lk)
    return out, max((ln.cells for ln in found), default=0)


def _link_joined(colors: np.ndarray, lk: _Link, change: dict[Cell, int]) -> bool:
    """Whether the floor of ``colors`` with ``change`` joins the group to the rest without
    the link."""
    trial = colors.copy()
    for c, colour in change.items():
        trial[c] = colour
    if lk.cut is None:
        trial[lk.at] = EMPTY
    lab = floor_labels(trial, lk.cut)
    a = np.unique(lab[lk.group & (lab >= 0)])
    b = np.unique(lab[lk.rest & (lab >= 0)])
    return bool(np.intersect1d(a, b).size)


def _judge(build: Build, catalog: Catalog, limit: float) -> tuple[tuple[int, int], list[_Link]]:
    """(heaviest load in cells, number of heavy weak spots), lower is sturdier, and the heavy
    links. A stack of links in one thin place counts as one weak spot (``_stacks``): a
    change that leaves two links there instead of three has not made it any sturdier."""
    links, heaviest = _links(build, catalog, None, limit)
    return (heaviest, len(_stacks([(k.cells, k.group) for k in links]))), links


def _now_at(links: list[_Link], lk: _Link) -> _Link | None:
    """The heaviest of ``links`` at the place of ``lk`` (within two cells) that carries most
    of what hung on ``lk``: what hangs there now, or None when nothing heavy does."""
    half = lk.group.sum() / 2
    there = [k for k in links if lk.near(k) and (k.group & lk.group).sum() > half]
    return max(there, key=lambda k: k.cells, default=None)


def _better(new: tuple[int, int], old: tuple[int, int], gone: bool) -> bool:
    """Whether a build is sturdier than another by enough to pay for a change: there are no
    more heavy weak spots, and either the heaviest load goes down by at least ``HEAVY_MIN``
    cells, or there are fewer heavy weak spots, the heaviest load does not go up, and the
    weak spot being cured is ``gone`` (nothing heavy near its place carries most of what
    hung on it). A step of a few cells is a thin neck grown one layer at a time: each step
    fattens the model and the next layer hangs as before. A weak spot that only moves a
    little down a leg is no cure: the finishing pass may well have held it where it was.
    And a lighter heaviest load bought with one more place that hangs by a thread is not
    sturdier."""
    if new[1] > old[1]:
        return False
    return new[0] <= old[0] - HEAVY_MIN or (new[0] <= old[0] and new[1] < old[1] and gone)


def _estimate(
    build: Build, catalog: Catalog, occ: np.ndarray, removed: np.ndarray, limit: float
) -> tuple[int, int, int]:
    """(pieces, heaviest load, heavy weak spots) of the build with the ``removed`` cells
    taken out, without a solve: a part that covers some of them keeps the rest of its cells
    and holds only through those (as in ``_held``), and where what it keeps falls into
    pieces (a cell taken out of the middle of a 1 x 3 plate), each piece is a part of its
    own, since no part could span the gap."""
    from bricksnap.connect import lone_links_of_graph

    keep = (occ >= 0) & ~removed
    node = np.where(keep, occ, -1).astype(np.int64)
    top = len(build.parts)
    for i in np.unique(occ[removed & (occ >= 0)]).tolist():
        box = node[catalog.cells(build.parts[i])]  # a view: relabelled in place
        lab, k = ndimage.label(box == i, structure=_SIX)
        for j in range(2, k + 1):
            box[lab == j] = top
            top += 1
    ids = np.unique(node[keep])
    n = len(ids)
    if not n:
        return 0, 0, 0
    index = np.full(top, -1, dtype=np.int64)
    index[ids] = np.arange(n)
    lo, hi, studs = _contacts(node, removed)
    edges = [(int(a), int(b), int(s)) for a, b, s in zip(index[lo], index[hi], studs, strict=True)]
    part = index[node[keep]]
    volume = np.bincount(part, minlength=n).astype(float)
    z = np.full(n, occ.shape[2], dtype=np.int64)
    np.minimum.at(z, part, np.nonzero(keep)[2])
    found, _ = lone_links_of_graph(n, edges, z.tolist(), volume.tolist(), [True] * n)
    graph = coo_matrix(
        (np.ones(len(edges)), ([e[0] for e in edges], [e[1] for e in edges])), shape=(n, n)
    )
    pieces = int(connected_components(graph, directed=False)[0])
    heavy = [(ln.cells, np.isin(node, ids[list(ln.members)])) for ln in found if ln.cells >= limit]
    return pieces, max((ln.cells for ln in found), default=0), len(_stacks(heavy))


def _ranked(
    change: dict[Cell, int], lk: _Link, build: Build, catalog: Catalog, limit: float
) -> tuple[list[Cell], int]:
    """The cells of a change, those the build leans on first, and how many it leans on.
    Without a solve (``_estimate``): the cells are taken out of the build one at a time,
    those farthest from the link first, each staying out when the build without it has no
    more pieces, no heavier load and no more heavy weak spots; those that cannot stay out
    are the ones it leans on. Within each kind, nearest the link first."""
    occ = occupancy(build, catalog)[0]
    removed = np.zeros(occ.shape, dtype=bool)
    base = _estimate(build, catalog, occ, removed, limit)
    far = ndimage.distance_transform_edt(~lk.at)
    for c in sorted(change, key=lambda c: (-far[c], c)):
        removed[c] = True
        worse = zip(_estimate(build, catalog, occ, removed, limit), base, strict=True)
        if any(a > b for a, b in worse):
            removed[c] = False
    order = sorted(change, key=lambda c: (bool(removed[c]), far[c], c))
    return order, sum(not removed[c] for c in change)


def _sturdy_options(lk: _Link, colors, skin, claimed, hidden, original, edited):
    """The changes that could give the link's group a second connection, smallest first:
    partly covered cells touching the link, then those touching the group's and the rest's
    cells beside it, then also those touching them; hidden cells of the rest beside the
    group near the link given the group's colour, 1 then 2 studs deep; ONE clamp cell where
    the group touches the rest only at its side. Yields (kind, change, on top)."""
    beside = ndimage.binary_dilation(lk.at, _CUBE) & (lk.group | lk.rest) | lk.at
    near = ndimage.binary_dilation(lk.at, _CUBE, iterations=2)
    both = ndimage.binary_dilation(lk.group, _SIX) & ndimage.binary_dilation(lk.rest, _SIX)
    sets = [
        {
            c: v
            for c, v in _skin(colors, skin, beside, claimed, 1, edited).items()
            if near[c] and both[c]
        },
        _skin(colors, skin, lk.at, claimed, 1, edited),
        _skin(colors, skin, beside, claimed, 1, edited),
        _skin(colors, skin, beside, claimed, 2, edited),
    ]
    for change in sorted(sets, key=len):  # the fewest cells first
        yield "skin", change, False
    there = ndimage.binary_dilation(lk.at, _CUBE, iterations=2) & lk.group
    for depth in RECOLOUR_DEPTHS[:2]:
        yield "recolour", _recolour(colors, there, hidden & lk.rest, claimed, depth), False
    change, up = _clamp(colors, lk.group, lk.rest, claimed, original, lk.rest & ~lk.at)
    yield "clamp", change, up


def _could_help(colors: np.ndarray, lk: _Link, change: dict[Cell, int]) -> bool:
    """Whether a change could give the group a second connection at all. When the floor has
    no other way between group and rest, the change must make one (no layout can beat the
    floor); otherwise it must at least touch both."""
    if lk.apart:
        return _link_joined(colors, lk, change)
    near = ndimage.binary_dilation(_mask(colors.shape, change), _SIX)
    return bool((near & lk.group).any() and (near & lk.rest).any())


@dataclass
class _Cure:
    kind: str
    change: dict[Cell, int]
    up: bool
    link: _Link  # as it was before the change


@dataclass
class _Sturdy:
    """What the weak-spot phase did: the Design, its build and pieces, the cures kept, the
    heavy links of the build, the weak spots left (one per stack, heaviest first), whether
    it ran out of solves or time, and the solves it made."""

    work: Design
    build: Build
    pc: _Pieces
    cures: list[_Cure] = field(default_factory=list)
    links: list[_Link] = field(default_factory=list)
    left: list[_Link] = field(default_factory=list)
    ran_out: bool = False
    solves: int = 0


def _sturdy(
    design: Design,
    work: Design,
    build: Build,
    pc: _Pieces,
    catalog: Catalog,
    seed: int,
    budget: int,
    started: float,
) -> _Sturdy:
    """Cure the heaviest lone links of ``build`` (the best Design the pass found, ``work``)
    by small changes to the Design, each judged by a solve and kept only if the build is
    sturdier by enough (``_better``) and has no more pieces; then what a kept change of
    partly covered cells does not need goes, when a fresh solve agrees. A link is heavy by
    the input Design's filled cells (``heavy_limit``). ``started`` is when the pass began
    (``time.perf_counter``): no solve is started that would end after ``STURDY_SECONDS``."""
    from bricksnap.layout import solve

    out = _Sturdy(work, build, pc)
    if budget <= 0 or pc.count == 0:
        return out
    limit = heavy_limit(int(design.filled.sum()))
    links, heaviest = _links(build, catalog, work.colors, limit)
    if not links:
        return out
    hidden = design.filled & ~visible_cells(design.filled)
    blocked = _detail_cells(design, catalog)
    assert design.skin is not None
    skin, edited, original = design.skin, bool(design.log), design.colors
    score = (heaviest, len(_stacks([(k.cells, k.group) for k in links])))
    given_up: list[_Link] = []
    slow = 0
    longest = 0.0  # the longest solve of the phase so far: does another one fit in time?

    def attempt(trial: Design) -> tuple[Build, _Pieces, tuple[int, int], list[_Link]] | None:
        nonlocal slow, longest
        late = time.perf_counter() - started + longest >= STURDY_SECONDS
        if out.solves >= budget or slow >= SLOW_PATIENCE or late:
            return None
        t = time.perf_counter()
        tb = solve(trial, catalog, seed=seed)
        longest = max(longest, time.perf_counter() - t)
        out.solves += 1
        tp = _pieces(tb, catalog)
        slow += tp.count > _floor_count(trial.colors)
        return tb, tp, *_judge(tb, catalog, limit)

    def shrink(change, order, need, make, full, pieces):
        """The shortest first part of ``order`` (at least ``need`` cells, found by halves
        in up to ``PRUNE_TRIES`` solves) with which a fresh solve does as well as with the
        whole ``change`` (score ``full``): no more pieces than ``pieces`` or heavy weak
        spots, and no heavier load unless that load is not heavy at all. Returns (the
        smaller change, its Design, what ``attempt`` gave), or None."""
        found = None
        low, high, k = need, len(change), need
        for _ in range(PRUNE_TRIES):
            if k >= high:
                break
            fewer = {c: change[c] for c in order[:k]}
            smaller = make(fewer)
            got = attempt(smaller)
            if got is None:
                break
            _, gp, (heaviest, spots), _ = got
            if (
                gp.count <= pieces.count
                and spots <= full[1]
                and (heaviest <= full[0] or heaviest < limit)
            ):
                high, found = k, (fewer, smaller, got)
            else:
                low = k + 1
            k = (low + high) // 2
        return found

    later: list[_Cure] = []  # kept changes the build leans on none of, taken away last
    while True:
        open_ = [
            lk
            for lk in links
            if not any(g.same_place(lk) for g in given_up)
            and not any(g.apart and lk.holds(g) for g in given_up)
        ]
        if not open_:
            break
        # those the floor itself cuts first: a stack of links in a thin place is cured there
        lk = min(open_, key=lambda k: (not k.apart, -k.cells))
        claimed = (work.colors != original) | blocked
        seen: list[dict[Cell, int]] = []
        kept = None
        for kind, change, up in _sturdy_options(
            lk, work.colors, skin, claimed, hidden, original, edited
        ):
            if not change or change in seen or not _could_help(work.colors, lk, change):
                continue
            seen.append(change)
            if kind not in lk.found:
                lk.found.append(kind)
            trial = _apply(work, [_Spot(mask=lk.at, change=change)])
            got = attempt(trial)
            if got is None:
                out.ran_out = True
                break
            if kind not in lk.tried:
                lk.tried.append(kind)
            tb, tp, ts, tl = got
            if tp.count > pc.count or not _better(ts, score, _now_at(tl, lk) is None):
                continue
            order, need = list(change), len(change)
            if kind == "skin":
                order, need = _ranked(change, lk, tb, catalog, limit)
            kept = (kind, change, up, trial, tb, tp, ts, order, need)
            break
        if out.ran_out:
            given_up.append(lk)
            break
        if kept is None:
            given_up.append(lk)
            continue
        kind, change, up, trial, tb, tp, ts, order, need = kept
        cure = _Cure(kind, change, up, lk)
        if need:
            # what the build does not lean on goes, when a fresh layout agrees
            def make(fewer: dict[Cell, int], base: Design = work, at: np.ndarray = lk.at):
                return _apply(base, [_Spot(mask=at, change=fewer)])

            found = shrink(change, order, need, make, ts, pc)
            if found:
                cure.change, trial, (tb, tp, ts, _) = found
        else:  # it leans on none of them: sturdier by the tiling they brought about
            later.append(cure)
        work, build, pc, score = trial, tb, tp, ts
        links, _ = _links(build, catalog, work.colors, limit)
        out.cures.append(cure)
    # changes the build leans on none of, with the solves left: from the nearest cell up
    for cure in later:
        far = ndimage.distance_transform_edt(~cure.link.at)
        order = sorted(cure.change, key=lambda c: (far[c], c))
        base = work

        def without(fewer: dict[Cell, int], cure: _Cure = cure, base: Design = base) -> Design:
            smaller = base.copy()
            assert smaller.finish is not None and design.finish is not None
            for c in cure.change:
                if c not in fewer:
                    smaller.colors[c], smaller.finish[c] = design.colors[c], design.finish[c]
            return smaller

        found = shrink(cure.change, order, 1, without, score, pc)
        if found:
            cure.change, work, (build, pc, score, _) = found
            links, _ = _links(build, catalog, work.colors, limit)
    out.work, out.build, out.pc, out.links = work, build, pc, links
    for k in links:  # what was tried there, for the notes
        for g in given_up:
            if g.same_place(k) or (g.apart and k.holds(g)):
                k.take(g)
    stacks = [[links[i] for i in s] for s in _stacks([(k.cells, k.group) for k in links])]
    claimed = (work.colors != original) | blocked
    for stack in stacks:
        rep = stack[0]
        for k in stack[1:]:
            rep.take(k)
        if out.ran_out and not rep.tried and not rep.found and len(out.left) < LEFT_NOTES:
            # never reached: say whether anything could have been tried here at all, taking
            # the links of the stack in the order the phase would have (once one the floor
            # cuts has nothing, those stacked on it are given up with it)
            for k in sorted(stack, key=lambda k: (not k.apart, -k.cells)):
                for kind, change, _ in _sturdy_options(
                    k, work.colors, skin, claimed, hidden, original, edited
                ):
                    if change and kind not in rep.found and _could_help(work.colors, k, change):
                        rep.found.append(kind)
                rep.apart = rep.apart or k.apart
                if rep.found or k.apart:
                    break
        out.left.append(rep)
    return out


def _link_words(catalog: Catalog, colors: np.ndarray, lk: _Link) -> str:
    """'a single stud at x=6, y=4, z=17 to 18' or 'one part, the Green part at ...'."""
    if lk.cut is not None:
        return f"a single stud at {_where(np.argwhere(lk.at))}"
    return f"one part, {_describe(catalog, colors, lk.at)}"


def _cure_words(catalog: Catalog, colors: np.ndarray, lk: _Link, links: list[_Link]) -> str:
    """How the group a change was made for hangs in the build the pass returns: on nothing
    heavy any more, or on the heavy link (as it is now) that carries most of it."""
    s_ = "" if " parts at " in _describe(catalog, colors, lk.group) else "s"
    old = _link_words(catalog, colors, lk)
    half = lk.group.sum() / 2
    holding = [k for k in links if (k.group & lk.group).sum() > half]
    now = min(holding, key=lambda k: k.cells, default=None)
    if now is None:
        return f"no longer hang{s_} on {old} alone"
    words = _link_words(catalog, colors, now)
    if not lk.near(now):
        return (
            f"no longer hang{s_} on {old} alone, but still hang{s_} on {words}, with "
            f"{now.cells} cells hanging there in all"
        )
    if now.cells < lk.cells:
        return (
            f"now hang{s_} on {words}, with {now.cells} cells hanging there instead of {lk.cells}"
        )
    return f"still hang{s_} on {words}, with {now.cells} cells hanging there"


def _sturdy_notes(catalog: Catalog, colors: np.ndarray, st: _Sturdy, limit: float) -> list[str]:
    """What the phase did, said of the build the pass returns, then the heavy weak spots
    left, heaviest first."""
    out: list[str] = []
    for cure in st.cures:
        lk = cure.link
        what = _describe(catalog, colors, lk.group)
        parts = f"{_count(lk.load, 'part', 'parts')}, {lk.cells} cells"
        why = _cure_words(catalog, colors, lk, st.links)
        s_ = "" if " parts at " in what else "s"
        n = len(cure.change)
        where = _where(list(cure.change))
        values = list(cure.change.values())
        if cure.kind == "skin":
            colours = sorted({_colour_name(catalog, v) for v in values})
            in_colour = (
                f"each in its own colour ({', '.join(colours[:-1])} and {colours[-1]})"
                if len(colours) > 1
                else colours[0]
            )
            out.append(
                f"Filled {_count(n, 'partly covered cell', 'partly covered cells')} at {where} "
                f"{in_colour} so that {what} ({parts}) {why}: the model passes through "
                f"{'that cell' if n == 1 else 'those cells'}, so the outline moves by less "
                "than half a cell."
            )
            continue
        colour = _colour_name(catalog, max(set(values), key=values.count))
        if cure.kind == "recolour":
            out.append(
                f"Recoloured {_count(n, 'hidden cell', 'hidden cells')} at {where} {colour} "
                f"so that one part can reach across the seam where {what} ({parts}) "
                f"meet{s_} the rest of the model, and {'they' if not s_ else 'it'} {why}."
            )
        else:
            side, across = ("on top of", "over") if cure.up else ("under", "under")
            out.append(
                f"Added {_count(n, colour + ' cell', colour + ' cells')} at {where} {side} "
                f"{what} ({parts}) so that a {colour} part of the body reaches across {across} "
                f"it: {'they' if not s_ else 'it'} touched the body only at "
                f"{'their' if not s_ else 'its'} side, and {'they' if not s_ else 'it'} {why}."
            )
    for lk in st.left[:LEFT_NOTES]:
        what = _describe(catalog, colors, lk.group)
        hang = f"{_count(lk.load, 'part', 'parts')}, {lk.cells} cells"
        lifted = (
            " (standing on the ground, but coming away when the model is lifted)"
            if lk.lifted
            else ""
        )
        if lk.tried:
            words = [_STURDY_WORDS[k] for k in _STURDY_WORDS if k in lk.tried]
            joined = f"{', '.join(words[:-1])} and {words[-1]}" if len(words) > 1 else words[0]
            verb = "were" if len(words) > 1 else "was"
            why = (
                f"{joined[0].upper()}{joined[1:]} {verb} tried, but the layout still hangs "
                "it there."
            )
        elif lk.found:  # something could be tried, but the solves (or the time) ran out
            why = "The pass ran out of attempts before it could try anything here."
        else:
            why = (
                "Nothing could give it a second hold: no partly covered cell beside it would "
                "join it to the rest, no hidden cell at a seam there could take its colour, "
                "and there is no place for one cell under or over it beside the rest of the "
                "model."
            )
            if lk.apart:
                why += " The model really is that thin there: to make it sturdier, make it wider."
        s_ = "" if " parts at " in what else "s"
        out.append(
            f"Still hanging by a thread: {what} ({hang}) hang{s_} on "
            f"{_link_words(catalog, colors, lk)} alone{lifted}. {why}"
        )
    if len(st.left) > LEFT_NOTES:
        more = len(st.left) - LEFT_NOTES
        out.append(
            f"{_count(more, 'more weak spot', 'more weak spots')} like these, each carrying "
            f"at least {int(np.ceil(limit))} cells, {'is' if more == 1 else 'are'} left as "
            "they are."
        )
    return out
