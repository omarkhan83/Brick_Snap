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
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from bricksnap.catalog import Catalog
from bricksnap.types import Build, Design


@dataclass
class BuildableResult:
    design: Design
    build: Build
    recoloured: np.ndarray
    added: np.ndarray
    notes: list[str] = field(default_factory=list)
    pieces_before: int = 0
    pieces_after: int = 0


def make_buildable(
    design: Design, catalog: Catalog, seed: int = 0, max_solves: int = 12
) -> BuildableResult:
    raise NotImplementedError
