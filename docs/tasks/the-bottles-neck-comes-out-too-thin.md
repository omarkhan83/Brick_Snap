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

20 November, two ways tried and turned down (both kept as branches for reference; an independent
reviewer ran about 1,460 made-up shapes through the first):

- **Fill a 2 x 2 column out to a plus in the make-buildable pass, where something heavy hangs on it**
  (branch `wip/Alec-42-bottle-neck`). It fixes the bottle (front outline 70.5% to 84.0%, heaviest section
  96 to 48 cells, no other sample changed), but the pass only knows that the model touches a cell, not
  how far it reaches in. So square legs 2.1 to 2.8 studs wide are filled out to 4 (a table on square legs:
  outline 84% to 67%), two round legs a stud apart fuse into one block (the outline measure does not
  see it), and of more than eight equal columns eight are widened and the rest are not. A decision about
  shape was being taken by a rule about sturdiness.
- **Fill each level's section so its outline matches the model best, in the conversion** (branch
  `wip/Alec-42-section-fill`; only adds cells, never closes a gap, same result wherever the section
  stands). Round posts and legs about 3 studs across on a cell corner gain 3 to 15 points and lose
  their heavy sections, and square legs are left alone. But over the 11 samples at four sizes the mean
  outline match moves by 0.1 to 0.4 points, a box no longer stays a box (ten contract tests fail), the
  bottle's body comes out 2 x 4 and is then filled to 4 x 4 downstream (top outline 72% to 57%), fewer
  tops are shaped (38% to 36% at 16 studs), and the conversion is up to five times slower at 96 studs.
  Applying it only to badly cut-down sections keeps the losses and loses the gains.

What both showed: the trouble is one alignment. A round section about 3 studs across comes out 2 x 2
when its axis falls on the corner where four cells meet, and 3 x 3 when it falls on the middle of a
cell; `load_seed` centres a model in a whole number of studs, which decides between the two by the
parity of its width. Next to try: let the conversion choose the seating (the model moved half a stud
in x, in y, or both) that the fill matches best.

Also learned, for whoever takes up sturdiness: the solver lays any column 2 cells wide one part per
level, so every part carries everything above it. The reviewer showed by hand that the bottle's
48-cell section at its mouth goes away only if the plate under the column is split in two and the
levels above are laid as crossed 1 x 2 parts (no lone link at all with every level crossed, for 15
more parts), and asked the fair question whether a full-width part with all its studs engaged should
count as a weak spot in the first place: crossed or stacked, each level is held by the same four studs.
