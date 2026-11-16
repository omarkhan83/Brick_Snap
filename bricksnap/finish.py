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
   - Directly below every cell of its bottom layer there is a filled cell.
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
   part before two one-wide parts; when a cell could slope in more than one direction, the
   direction in which the surface drops furthest. Break ties the same way every time.
   A cheese slope stands on a plate: a brick whose top is to carry one is swapped for a
   plate with the cheese slope on it.

4. Whatever a swap displaces is covered again. A swap takes whole existing parts out and
   puts back parts covering exactly the same cells: the tiles or slopes wanted, and bricks
   or plates (existing pairs only) for the cells left over.

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
- One summary sentence: how many tiles, slopes and detail parts were placed, and how many
  smooth or sloped cells were left as they were. Then one sentence per skipped detail. All
  in plain words with coordinates ("x=…, y=…, z=…"), because the AI designer and people
  read them. No note at all when there was nothing to do.

Other
- A Design with no smooth or sloped cells and no details gives back a Build equal to the
  input (same parts, same order, same steps).
- Deterministic. Speed: a 3,000-part build in under 5 seconds.
- This module may use ``bricksnap.connect`` and ``bricksnap.catalog``. It does not call the
  layout solver or the checks.
"""

from __future__ import annotations

from bricksnap.catalog import Catalog
from bricksnap.types import Build, Design

TILE_KIND = "tile"
SLOPE_PARTS = ("3039", "3040b", "85984", "54200")
"""Slope parts the pass must know how to place, biggest first."""


def finish(build: Build, design: Design, catalog: Catalog) -> Build:
    raise NotImplementedError
