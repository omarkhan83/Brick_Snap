# Box-shaped and Solid builds come out as separate towers that do not hold together
- status: open
- owner: nobody

The brick layout (`merge` in `build()`, `index.html` around lines 471-485) fills each layer in scan order, so
the first free cell can only start a brick at that cell and the "grip several bricks below" score rarely has
a real choice. Layers alternate between two fixed patterns, and on straight-sided shapes whole columns of
bricks stack exactly on top of each other without overlapping their neighbours. `join` and the pillars cannot
repair that.

Measured by running the app's own layout code on single-colour shapes (bricks not connected to the main model):

| Shape (studs) | Hollow | Solid |
|---|---|---|
| Box 6x4x4 | 4 of 12 | 4 of 12 |
| Box 12x12x4 | 40 of 56 | 40 of 56 |
| Box 16x10x10 | 0 of 144 | 120 of 160 |
| Box 20x20x20 | 4 of 473 | 840 of 920 |
| Cylinder 20x20x16 | 10 of 534 | 752 of 800 |
| Sphere 24x24x20 | 0 | 0 |

So Solid is broken for anything with straight sides, and Hollow is broken when the model is only a few layers
tall. The app does report it ("N bricks don't snap onto the rest"), but the kit is not usable.

Done when those shapes produce zero loose bricks in both fills. The likely fix is offsetting the brick grid
from layer to layer (as a real brick wall does) rather than only swapping brick orientation.

## Notes
Found in the 2026-11-15 code review. The layout code is pure and can be run in node by slicing it out of
`index.html`; a permanent test like that is worth adding as part of this task.
