# Thin models still have too many weak spots, mostly at larger sizes
- status: open
- owner: nobody
- stage: 4

Since the conversion fills cells by coverage, shapes are truer and thinner. At 16 studs no large section
hangs on one part any more, but small weak spots are more numerous than with the old fat conversion (232
against 148 over the eleven samples), and at 24 studs some large ones remain: the hat (11 sections of 40
cells or more hanging on one part, the worst 67 cells) and the pineapple's crown (89 cells), which is a
hollow wall one cell thick. At 12 studs the bottle's neck (96 cells) stands on a 2 x 2 column.

Done when, at 12, 16, and 24 studs, no sample model has a section of 40 cells or more hanging on a single
part or stud unless the model really is that thin there (and the notes say so), and the weak-spot total at
16 studs in `uv run bricksnap bench` is back under 180.

## Notes
What is known, from the work on `docs/decisions/2026-11-17-a-cell-is-filled-when-the-model-fills-most-of-it.md`:

- Most remaining weak spots are strips one stud deep, or parts of the model that touch the rest only side
  by side. A layout with parts spanning the seam would tie them; the solver's sturdiness step
  (`bricksnap/layout.py`) and the make-buildable pass's weak-spot phase (`bricksnap/buildable.py`) are
  the two places to work.
- The make-buildable pass stops after 8 extra solves; on the hat at 24 studs it runs out before it has
  tried every weak spot, and says so in its notes.
- Of the cells that pass fills, about half could be taken away again without loss; finding which costs a
  solve each.
- A box always comes out a box, but a hexagon does not: the sample bottle is plus-shaped from above.
- Thin coloured bands come out as dashes (the hat's red ribbon), because a band thinner than a cell
  loses the colour vote in most cells it crosses.
- The finishing pass measures at most 150,000 parts while deciding which swaps to keep; on the duck at 24
  studs that is 4% short, and it gives up 36 slopes it could have kept. Raising the limit to 200,000 cures
  it at about half a second's cost.
