# Fill a cell when the model fills most of it, not whenever it touches it
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 3

The conversion fills every grid cell the model's surface passes through. Nothing thin is ever lost, but
everything comes out fat: the sample cat's legs are 1.6 studs wide and come out 3 studs wide, merged into
one block; a bottle's neck doubles in width. Filling a cell only when the model covers at least half of it
(with rules that keep whiskers, fins, and brims one cell thick and attached) was built and reviewed. On
the scorecard it raised the average outline match from about 81% to 87% and cut the parts by a fifth.

It is not on `main` because it makes thin features too fragile to build: the cat's whiskers come loose at
16 and 24 studs (they touch the head only through the visible eye cells), a thin-walled hat falls apart at
12 studs, and weak spots rise from 237 to about 390. The work is on the branch `wip/Alec-42-coverage-fill`.

Done when it is on `main` with every sample model building at 12, 16, and 24 studs with no loose parts,
the scorecard's outline match at 86% or better on average, and no model with more weak spots than in
`samples/scorecard.json` today.

## Notes
What is left, in the order to try it:

1. **Give the make-buildable pass the cells the model only partly covers.** The conversion knows them (the
   old fill minus the new one) with their colours. Filling one of those next to a loose piece changes the
   outline by less than half a cell and is what fixes the cat's whiskers. It should come after recolouring
   hidden cells and before thickening. This needs a new array in `Design`, which is a change to
   `bricksnap/types.py`.
2. **Two more repairs in the make-buildable pass:** thicken a sheet from above when it lies on the ground
   (the hat's brim), and clamp a feature that touches the body only at its side by adding one cell of the
   body's colour over its root, so a body part reaches across it.
3. **Keep box corners.** A box in a general position loses its corner cells (0.6 x 0.6 of a cell is under
   half), so boxes come out with chopped corners and the bottle looks like a plus sign from above. Judge
   each axis separately instead: a cell is filled when, along each axis, the lines through it that hit the
   model are at least half inside it on average.
4. Thin walls that step diagonally from layer to layer connect only at their edges and cannot be built.
   The fill has to keep a stud of overlap between layers, or item 1 has to restore it.

The reviewer's and the author's full findings are in the commit messages on the branch.
