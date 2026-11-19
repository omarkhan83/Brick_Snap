# Details on the side of a model: eyes, lights, badges
- status: in-progress
- owner: Alec-42 (since 2026-11-18)
- stage: 4

Detail parts can only stand on top of the model today, so eyes on the front of a head are painted cells.
A brick with a stud on its side (87087, or 4733 with studs on four sides, both already in the parts table)
lets a round tile or a small slope face sideways. Add a way for `place_detail` to name a side face, have
the finishing pass swap in the side-stud brick behind it, and teach the checks, the LDraw writer, the
pictures, and the viewer about parts that are turned on their side.

Done when the cat can have two round-tile eyes on the front of its head, the build passes its checks, and
the eyes show in the pictures, the viewer, and the LDraw file.

## Notes
This is the first part that is not upright, so `Placement` needs a way to say which way a part faces.
That is a change to `bricksnap/types.py`: propose it in `docs/decisions/` first. The parts table has no
field yet for which way a side stud points; `bricksnap/catalog/SOURCES.md` says how the table is made.

2026-11-18, Alec-42's agent: the decision is `docs/decisions/2026-11-18-a-part-can-face-sideways-on-a-side-stud-brick.md`.
Building starts once the web app and the quicker test suite are on `main`, because it touches the viewer
and many tests. The design, so that nothing has to be worked out twice:

- **Where the stud is.** The solver's bricks sit in courses: heights 0 to 2, 3 to 5, 6 to 8 and so on.
  The side-stud brick is one of those bricks, so a sideways detail can sit at every third height only. Its
  stud is 14 LDU above the brick's bottom (`studs_side` in the parts table: 10 LDU below the top), so a
  1 x 1 round tile ends level with the brick's top and 4 LDU above its bottom.
- **What it keeps clear.** The column of three cells in front of the brick (a tile is 8 LDU thick, less
  than half a cell, but it reaches into all three). `(x, y, z)` of the sideways part is that column's
  lowest cell, so z is a multiple of 3, and the brick behind it is one cell further in.
- **Which parts.** Only detail parts one stud wide and one plate thick for now (98138 round tile, 3070b
  tile, 6141 round plate): turning them about the stud changes nothing, so `rot` stays 0. Wider parts do
  not fit, because studs on stacked side-stud bricks are 24 LDU apart and studs on a part are 20.
- **`place_detail`** gains `"face"`. Rejected, saying what would work, when: z is not a multiple of 3 (name
  the two nearest that are); the column is not empty; the three cells behind it are not all filled (say
  which are missing; the make-buildable pass may fill a hidden one, but the visible surface must be
  there); the brick is not made in the colour of the cells behind (87087 comes in 34 of our colours);
  the part is not a one-stud, one-plate detail. With `"mirror": true`, front and back stay front and
  back, left and right swap.
- **Solver.** `solve(..., pinned=[Placement, ...])`: bricks to place exactly as given (kind `side_stud`,
  in a course, on filled cells of their colour). Everything else is tiled around them; for holding
  together they count as 1 x 1 bricks, which is what they are. With nothing pinned the result must be
  the same as today, part for part (`uv run bricksnap bench` says "No change").
- **Make buildable** makes the three cells behind a sideways detail one colour and passes the pin to
  every solve it runs. **Finishing** places the detail, never swaps the pinned brick for anything, and
  may still put a tile on top of it.
- **Checks and connections.** A sideways part is joined to the part behind it when that part has a side
  stud on that face (`Catalog` needs to say which faces, turned by `rot`); otherwise it is loose and the
  report says so in words. It takes up its column for collisions.
- **LDraw, pictures, viewer, booklet.** The part is turned so its top points out of the face. Check the
  LDraw file in LeoCAD and in Studio (both can be done without a person, see the Studio task).
- **Saved files.** `face` is written only when it is not "top", and left out of the fingerprint when it
  is "top", so every saved sample stays byte for byte the same and still counts as up to date.
- **The designer** is told in its prompt and tool descriptions that eyes, lights and badges can go on a
  face; that changes how models come out, so run the bench and look at a cat.
