# The bottle's neck comes out as a 2 x 2 column where the model is over 3 studs across
- status: open
- owner: nobody
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
