# The bottle's neck comes out as a 2 x 2 column where the model is over 3 studs across
- status: in-progress
- owner: Alec-42 (since 2026-11-20)
- stage: 4

At 12 studs the sample bottle's neck is 3.2 to 3.7 studs across in the model, but the conversion makes it
a 2 x 2 column with a ring of twelve partly covered cells around it at every level. A column of 2 x 2
bricks is one weak spot by definition (96 cells hang on one brick), and the bottle's outline match (70 to
74%) is the worst of all the samples at any size. The solver cannot fix this: there is nothing beside
the column to tie it to.

Done when the bottle at 12 studs has a neck at least three studs across where the model is, its outline
match rises, no other sample's outline match falls, and its 96-cell weak spot is gone.

## Notes
Found by the review of the weak-spots work, 19 November. The conversion fills a cell when the model
covers most of it (`docs/decisions/2026-11-17-a-cell-is-filled-when-the-model-fills-most-of-it.md`); a
round neck between 3 and 4 studs across leaves every cell of its outer ring under half covered. The same
task file's history notes that a hexagon does not come out a hexagon (the bottle is plus-shaped from
above). `tests/test_finish.py` excuses this one section by name; remove that when it is fixed.

2026-11-20 (Alec-42, with Claude): measured first, then fixed in the make-buildable pass, not
the conversion.
- Measured: the conversion's filled area against the model's true area, level by level, for every
  sample at 12, 16 and 24 studs. There is no general loss: the total volume is within a few per
  cent of the model's for most samples (more for thin sheets, which rule 2 keeps a cell thick).
  The loss is in small round cross-sections on the corner of four cells: the bottle at 12 studs
  (-7.6% of its volume; its neck 6.5 to 8.1 studs² filled as 4) and at 16 (-9.9%), and the cat's
  legs at 12. At 24 studs it is gone.
- The bottle's neck (levels 3 to 17 at 12 studs) is a hexagon 2.85 studs across its flats and
  3.3 across its corners, centred on the corner of four cells, so a symmetric fill can only be 2
  or 4 wide; by area (7 studs² against 4 or 12) 2 x 2 is the nearer. Filling it to match the area
  (2 x 4) does not help: the solver lays a 2 x 4 column with one part per level too (144 cells on
  one part) and the pass then fills it out to a full 4 x 4 (top outline 71.9% to 56.6%). Changing
  the conversion to fill a plus would break "filled when the model fills most of it", so it is not
  done there.
- Done: in the weak-spot phase of bricksnap/buildable.py ("A thin column" in its contract), a
  heavy link in a 2 x 2 column whose twelve surrounding cells are all partly covered (the model
  reaches the corners, so it is at least 2.83 cells across, where 4 wide outlines it at least as
  well as 2 wide) gets the eight side cells filled along that whole stretch at once, never the
  corners, kept or dropped whole. Only the bottle at 12 studs changes of all 33 sample runs:
  outline front 70.5% to 84.0%, right 73.7% to 73.8%, top 71.9% unchanged; 32 to 40 parts; the
  96-cell weak spot is gone. The scorecard at 16 studs: no change.
- Left: 48 cells (levels 18 to 29) still hang on one part: the bottle's mouth, which the model
  makes 0.7 to 2.5 studs across and the conversion already fills 2 x 2. `_thin_there` in
  tests/test_finish.py now excuses only that (at most 48 cells, z 17 and up). The cure for it
  would be in the solver: a 2 x 2 column laid as pairs of 1 x 2 plates crossing level to level
  has no lone link at all; today it lays 2 x 2 plates and bricks. Not done here.
- Not done: the plus shape seen from above at 16 studs (the hexagon does not come out a
  hexagon); the outline match from above is unchanged by this work.
