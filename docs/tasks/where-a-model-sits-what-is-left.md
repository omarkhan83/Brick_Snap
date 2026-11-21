# Where a model sits on the grid: what the first version leaves undone
- status: open
- owner: nobody
- stage: 4

Since 20 November a small model (up to 16 studs) is tried sitting half a stud over on the grid in x, in
y and in both, and keeps the seating whose finished build is clearly closer to the model, no less sturdy
and joins no more of the model's separate sections (the decision of that date; the rule is in the
CONTRACT of `bricksnap/pipeline.py`). It began as the task "the bottle's neck comes out too thin", which
it settles: the bottle at 12 studs has a body 3 x 3 where the model is over 3 studs across, its outline
match rose from 70/74/72% to 83/89/82%, and its 96-cell weak column is gone.

Done when the items under "Left" below are each fixed, measured and turned down, or written into the
contract as a stated limit. The largest are the wait, the cliff at 16 studs, and judging on the Design
instead of on four finished builds.

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

2026-11-20, the seating (branch `wip/Alec-42-seating`; Alec-42 with Claude): **built**. A model up to
`pipeline.SEAT_STUDS` (16) studs on its longest side is built in each seating its sides allow (centred
as before; half a stud over in x, in y or both, where that side is not a whole number of studs and the
grid stays within the size asked for), and another seating is kept only when it has no loose parts,
is no less sturdy (after the review: by the shared measure, `connect.sturdiness`), joins no more of the
model's own sections than today's (after the review), loses no view's outline match by more than a
point, and gains at least a point on the mean, plus a point for every 10 per cent of extra parts it
needs; a seating that keeps apart what today joins is favoured, and a one-axis seating within a point
of its twin never decides. The project remembers it
(project.json "seat", "seat_note"); `load_project_seed` applies it; `Seed.seat` lets the conversion
grow the grid by the one cell a seated model needs. The bottle at 12 studs now sits half a stud over
in x and y: body 3 x 3, outline 83/89/82% against 70/74/72%, no section of 40 cells or more, so
`_thin_there` no longer excuses it. At 12 studs the knight, pawn and teapot also move; at 16 only the
bottle (mean outline 83.2% to 85.2% at 12); nothing moves at 24 in the measurements. The pawn at 16
would gain 2 to 4 points for 283 parts against 185 and a head of stacked plates: the parts condition
keeps it where it was. Choosing costs up to about 7 seconds at 16 studs, 14 at 24, 33 at 32.

Left:
- The bottle's neck at 12 studs is truer and more fragile: its mouth is a single column of 1 x 1
  cells ten levels tall (less comes off, more easily: six small weak spots, 1 before). And the solver
  still lays any 2-wide column one part per level (see above): seating avoids it for the bottle but
  does not cure it.
- From the independent review of the seating (its files are in the review's scratch folder): the
  conditions refuse some large gains for small reasons: 97 runs for one view down by more than a point
  (for example two columns going 70/69/82 to 99/98/80) and 31 for parts (for example a round 5 x 5
  column refused for a square 4 x 4). The outline measure favours a build one cell too big over one a
  cell too small.
- 16 studs is a cliff: of 65 models that moved at 16, 42 have a mean outline 3 points or more lower at
  17, and 20 would move at 17.
- The wait: `new` goes from about 2.5 s to 10 to 15 s on busy samples, and a model full of weak spots
  took 36 s where it took 0.6 (a trial seating can send the weak-spot phase through all its solves);
  every seating is built and the chosen one is built once more by `rebuild`.
- The reviewer's view: the judging belongs on the Design (the outline of the cells and the separate
  sections against the model: the same under a quarter turn, cheap at any size, no limit needed), with
  sturdiness only as a veto. And pieces of one file built as separate projects each choose their own
  seating, so parts meant to fit together can end half a stud apart.
- Choosing does not look at the shaped share: the bottle's shaped tops go from 44% to 20% at 16 studs
  (fewer steps need fewer slopes).
- The seated pawn at 16 studs showed a disagreement in finishing's sturdiness measure; it is written up
  in `docs/tasks/what-the-sturdier-builds-still-cost.md`.
