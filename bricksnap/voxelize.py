"""Seed to Design: decide which grid cells are filled, and what colour each is.

CONTRACT (tests are in tests/test_voxelize.py)

``voxelize(seed, catalog, hollow=False, shell_studs=2, margin_studs=2,
default_colour=DEFAULT_COLOUR) -> Design``

Grid
- A cell is CELL_MM = (8, 8, 3.2) mm. The body of the model needs
  ``ceil(extent / cell)`` cells per axis (at least 1; subtract a tiny epsilon before ceil so
  an exact multiple does not gain a cell).
- The grid is padded so later edits have room to grow the shape: ``margin_studs`` cells on
  each side in x and y, and ``3 * margin_studs`` cells above in z. Nothing is added below:
  the model stands on z = 0. ``Design.seed_offset`` is ``(margin_studs, margin_studs, 0)``.

Which cells are filled (port of the prototype, legacy/index.html lines 349-364)
1. Mark every cell the surface passes through, by sampling each triangle with points spaced
   under half a cell apart along every axis (cells are not cubes: scale accordingly).
2. Flood-fill the empty space inward from the outside of the grid (6-connected). Every cell
   the flood cannot reach is inside the model and is filled too.
   This tolerates scans with small holes, and guarantees a feature thinner than one cell
   still gets its cells rather than vanishing.

Colour
- If ``seed.face_colors`` is None every filled cell gets ``default_colour``.
- Otherwise snap each surface sample's RGB with ``catalog.nearest_colour`` (solid colours
  only) and give each surface cell the most common snapped colour among its samples. Cells
  with no sample (the inside) get the most common colour of the whole surface.

Hollow
- With ``hollow=True`` empty the deep inside and keep a shell. A filled cell is kept when
  some "outside" cell lies within ``shell_studs`` cells of it in x and in y and within
  ``3 * shell_studs`` cells in z (a box neighbourhood). Everything beyond the grid counts as
  outside, including below the ground, so a hollow model keeps a floor.
- Only space enclosed by the model is emptied; the outside shape must not change.

Other
- ``finish`` is all zeros; ``details``, ``regions`` and ``log`` start empty.
- Deterministic: the same inputs give an identical Design.
- Speed: a 200,000-triangle mesh at 48 studs in well under 10 seconds (use numpy and
  scipy.ndimage; no Python loop over cells or samples).

STAGE 2 ADDITION TO THE CONTRACT: where the seed's surface is slanted

``voxelize(..., slope_hints=True)``. Replaces "``finish`` is all zeros" above.
- For each filled cell with an empty cell above it (or in the top layer), take the mean of
  the normals of the seed's upward-facing surface inside that cell, weighted by area, in
  real space (millimetres, so the cell's 8 x 8 x 3.2 mm shape is taken into account) and
  normalised. If its upward part n_z is between cos(70 degrees) and cos(20 degrees) (about
  0.34 to 0.94), the cell's ``finish`` is FINISH_SLOPED. Every other cell is FINISH_STUDS.
- Walls and undersides are left out of the mean: otherwise the wall below the edge of a
  flat top would tilt it. A wall only has a say when it faces downhill and is larger than
  the cell's upward surface (a tiny chamfer on a big wall is not a slope).
- So a box gets no sloped cells; a sphere gets a band of them around its upper half but not
  on its very top; a pitched roof gets them all along both faces, including one modelled as
  a thin sheet.
- Normals follow the triangles' winding (outward). A cell with no upward-facing surface in
  it is FINISH_STUDS.
- With ``slope_hints=False`` the finish is all FINISH_STUDS.
- Hollowing does not change the finish of the cells that remain.

STAGE 2 ADDITION TO THE CONTRACT: the seed keeps its place on the grid
- ``load_seed`` leaves the model standing on z = 0 and centred, in x and y, in the smallest
  whole number of studs that holds it, so its minimum corner is (sx, sy, 0) with sx and sy
  under half a stud. voxelize keeps that offset: a seed point p (mm) lies in body cell
  floor(p / CELL_MM), and the body still needs ceil(extent / cell) cells per axis, counted
  from 0 (the offset never adds a cell: half the slack is on each side).
- On any axis where the seed does not start within the first cell (its minimum is below 0,
  or one cell or more above it; in z, anything but 0), it is first moved along that axis to
  start at 0, as before. The same happens when keeping the offset would need one more cell
  than the extent alone (a hand-made seed with more offset than slack). Seeds made by hand
  in tests usually start at 0 and are unaffected.
- A model that is mirror-symmetric left to right therefore gives a Design whose filled
  cells, colours and finish are mirror-symmetric too (cell x against nx - 1 - x), up to the
  tie-breaking of colour votes.

STAGE 2 CHANGE TO THE CONTRACT: a cell is filled when the model fills most of it
Replaces steps 1 and 2 of "Which cells are filled" above. Stage 1 filled every cell the
surface passed through. That never lost a thin feature, but it made everything fat: a leg
1.6 studs wide that straddles a stud line came out 3 studs wide, two such legs with a clear
gap between them merged into one block, and a bottle neck doubled in width. Now:

- Coverage. Each cell has a coverage: the share of its volume that lies inside the model,
  from 0 to 1, right to within about 0.1. "Inside" is as before: what the outside cannot
  reach, so scans with small holes still work.
- Rule 1 (changed in stage 3). A cell is filled when, along each of the three axes, the
  lines through it that meet the model lie at least half inside the model on average. Each
  axis is judged on its own: a box's edge cell, 0.6 x 0.6 of it covered, is more than half
  inside along every line that meets it, so it is filled although it holds only 0.36 of
  its volume, and a box stays a box wherever it sits. (Judged by volume, boxes in a general
  position lost their corners and edges.) A cell at least half covered is always filled;
  a cell cut diagonally through its middle (a slanted face) is filled or not as by volume.
- Rule 2, so that nothing vanishes. A cell rule 1 leaves empty that the surface passes
  through hands its material to the cell behind it: the neighbour across the face that the
  surface in the cell faces away from. If that neighbour is filled by rule 1, this cell is
  left empty (it was only the skin of something that is there anyway). Otherwise the
  material has no better home (the model is thinner than a cell here: a whisker, a fin, a
  brim) and one cell keeps it: this one, or that neighbour if it holds more.
- Rule 3, so that nothing comes apart. Wherever stage 1's fill connected two parts of the
  model through cell faces, the new fill connects them through cell faces too. Where rules
  1 and 2 leave a gap (a thin rod running diagonally), the gap is closed with the cells of
  stage 1's fill that hold the most.
- Rule 4 (stage 3), so that walls are as thick as nobody can see. Once rules 1 to 3 (and
  standing, below) have decided the fill, every cell the model passes through but covers
  less than half of (the skin, see "STAGE 3 ADDITION" below) that is not outside air is
  filled too, in its own colour. Outside air is as bricksnap/buildable.py has it: the
  empty cells reachable through faces from beyond the four sides or the top of the grid;
  below z = 0 is the table, not air. So the inside of a thin wall that faces only a hollow
  the outside cannot reach (the inside of a hat or of an upside-down bowl, which the table
  closes off) is filled, and its skin on the outside is not. The cells are decided all at
  once, against the fill before this rule with the skin counted as empty, so filling one
  never hides another and a symmetric model stays symmetric. Nothing anyone can see
  changes: no outside air is filled, so every cell that had an outside-air neighbour still
  has it and no other cell gains one, and the outline from every side and from above is
  what rules 1 to 3 made it. The colours and slope hints of the cells already filled stay.
  (A hollow sealed all round is never skin: the outside cannot reach it, so it is inside
  and filled already. The inside of a bottle is reached through its mouth: outside air.)
- Never fill a cell that stage 1 would have left empty.

What must be true, and is tested
- A box placed anywhere on the grid that covers at least half of some row of cells on each
  axis fills exactly a box of cells: on each axis, the rows it covers at least half of (so
  floor(w) or ceil(w) cells for a box w studs wide, depending on where it sits; never wider
  than ceil(w), and w on average over where it sits). The same in y and, in plates, in z.
  Two boxes with a gap of one cell or more between them stay apart. (A box covering a row
  within a hair of half may go either way there.) A box that covers no row half on some
  axis (thinner than a cell there and straddling a row boundary, so under one cell of
  either row) is kept by rule 2 instead, as a thin sheet or rod is (below), but not always
  as a box: rule 2 judges a cell by where its material lies, not axis by axis, and such a
  slab can lose a corner or edge cell (about a third of slabs 0.5 to 1 cell thick that
  straddle a boundary did).
- A sphere 8 studs or more across has a filled volume within 5% of its true volume (stage 1
  was far above). A cylinder does not always: each layer of an upright cylinder is the
  cells rule 1 fills, which at 9 studs is 8.5% more than the circle's area, and within 9%
  at every size from 8 to 16 studs in quarter steps.
- A rod 0.3 studs thick, along any axis, at any position (inside a row of cells, on the
  boundary between two rows, on the edge where four meet) is still there from end to end,
  connected through faces, and at most two cells thick (one inside a row; two where it sits
  exactly on a boundary, so the result stays symmetric, and in about 2% of random positions
  elsewhere, where the rays across the rod miss it and two cells measure alike). The same
  for a sheet 0.2 studs thick, level or upright: no holes, one cell thick. A rod or sheet
  running diagonally stays connected through faces.
- A thin feature stays joined, through cell faces, to the body it grows from.
- The number of face-connected pieces is the same as in stage 1's fill, for every sample
  model in samples/models at 12, 16 and 24 studs.
- A mirror-symmetric model still gives a mirror-symmetric Design, skin included (tested on
  the sample models from 4 to 24 studs). A model symmetric only to within a tenth of a
  millimetre (the sample duck) gives mirror-symmetric filled cells, though its skin may
  differ where the model reaches a hair into a cell on one side only. A file that is not
  watertight can break this where a ray crosses a crack on one side only (the sample pawn
  at 96 studs).
- Colour and slope hints: a filled cell takes them from the surface inside it and, when the
  surface that bounds it lies in a neighbouring cell that was left empty (always the case
  for a cell filled without the surface passing through it), from that surface: the cell
  directly above for the slope hint, the nearest such neighbour for the colour. A top cell
  must not lose its hint or its colour because its skin cell was dropped.
- Hollowing, padding, determinism and the speed limits are as before.

STAGE 3 ADDITION TO THE CONTRACT: the skin
- ``Design.skin`` holds, in each cell of stage 1's fill that the new fill leaves empty (the
  cells the model passes through but covers less than half of), the colour stage 1 gave
  that cell: the vote of its own surface. It is EMPTY everywhere else, including every
  filled cell and the padding. Hollowing does not change it. The make-buildable pass uses
  it (see bricksnap/buildable.py); a mirror-symmetric model gives a mirror-symmetric skin.

Implementation notes
--------------------
- Everything is done in cell units (millimetres divided by CELL_MM), where a cell is a unit
  cube, so the anisotropic 8 x 8 x 3.2 mm cell needs no special cases after that.
- The seed keeps its offset on each axis where it starts within the first cell (``load_seed``
  centres it in whole studs, so it starts under half a stud in), and a point p strictly
  inside a cell is in body cell floor(p / CELL_MM). In z, and on any axis where it starts
  below 0 or a cell or more above it, it is first moved to start at 0, as before (so a
  seed starting at 0 gives exactly the Design it always did). A seed that starts within
  the first cell but would then reach past the ceil(extent / cell) cells the body has (a
  hand-made seed with more offset than slack) is moved to 0 on that axis too, rather than
  having its far end squashed into the last cell. The cell count, the boundary snap, the
  nudge into the solid and the clamp of anything beyond the body all work on these placed
  coordinates, whose cell boundaries are the grid's own, so none of them assumes a start
  at 0.
- Coordinates within 1e-4 of a cell (0.8 micrometres across, 0.3 up) of a cell boundary are
  snapped onto it. Binary STL, GLB and PLY store single precision, so a face meant to sit on
  a boundary comes back up to about 3e-5 of a cell off it; without the snap, the faces at
  right angles to it would reach into the next cell and fatten blocky models.
- Stage 1's fill is still worked out, as the bound of the new one and the judge of what
  belongs together (see "Coverage and the three rules" below). Its surface cells are found
  exactly rather than sampled. Point sampling at half-cell spacing (the prototype's
  method) misses about one surface cell in ten where a triangle only clips a cell's corner.
  Instead each triangle is clipped against the cell slabs, one axis after the other
  (Sutherland-Hodgman, vectorised; a piece has at most 9 corners), so every final piece is
  the part of one triangle inside one cell, with its exact area. The work is proportional
  to the cells a triangle passes through, not to its length, so the long slivers of CAD
  exports cost no more than evenly sized triangles. Triangles are processed in batches
  sized by an estimate of their piece count, to bound memory.
- A cell is marked when the surface passes through its inside; merely touching its boundary
  does not count, nor does reaching less than 1e-9 of a cell into it (so the side of a box
  whose base is 9.6 mm, which is 2.9999999999999996 plates in floating point, does not poke
  into the layer below). Pieces are clipped to the cell shrunk by that 1e-9.
- A face lying exactly on a cell boundary (every face of a box whose size is a whole number
  of cells) would then mark nothing, and rounding could put it a hair either side. So each
  triangle is first nudged 1e-6 of a cell (well over that 1e-9) against its normal, into
  the solid: a box's right face at exactly x = 10 cells goes in cell 9, its left face at
  x = 0 in cell 0, and a 10-cell box stays 10 cells wide wherever it sits. This uses the
  triangles' winding (the usual outward-facing convention); a face wound the wrong way
  lands one cell outside at worst, never leaves a gap. Anything that still ends up beyond
  the body is clamped into it. Zero-area triangles mark nothing.
- A "sample" for the colour vote is one (triangle, cell) piece, weighted by its area in
  square millimetres, so the vote follows visible surface area. Votes within one part in a
  million of the best count as a tie, and a tie goes to the lower LDraw code. "The most
  common colour of the whole surface" counts surface cells (ties again to the lower code).
- Each surface cell's own colour is its own vote (what stage 1 showed there). The colour
  moves with the material: a filled cell that emptied surface cells handed their material
  to (rule 2, also along a chain) takes the own colour of those cells, and of itself when
  it has surface of its own, that has the most area (each cell counts the area of its own
  colour; a lone giver needs no areas). So a top whose skin was emptied keeps its colour,
  and so does a painted or thin feature in another colour (an eye, a stripe) whose cells
  were only skin; mixing all of those cells' surface by area instead lost such features to
  the larger surface around them, and counting cells let one side skin tie with the whole
  top and win on the lower code. On top of that, a cell with nothing filled above it takes
  the colour of the emptied cell right above it, when that gave it its material: the
  colour seen from above stays. A filled cell no material came to takes its own surface,
  else the surface of its emptied face-neighbours by area, else the colour of the inside.
- Colours are snapped with ``Catalog.nearest_colours`` (closest as eyes judge it; the
  first catalogue colour wins an exact tie).
  ``default_colour`` must be a solid colour of the catalogue.
- The flood fill labels the empty space (6-connected) and keeps the pieces that touch any
  face of the grid; beyond every face of the grid, including below z = 0, is outside.
- The hollow rule is a box erosion, done as three 1-D minimum filters.

Coverage and the three rules (implementation notes)
- Coverage is measured per sub-cell: each surface cell of stage 1 is cut into s x s x s
  sub-cells, s = 3 (27 per cell), or 2 when the surface cells would have over 4 million
  sub-cells (about 148,000 surface cells; none of the sample models at 96 studs gets
  there). Cells stage 1 found inside have coverage 1, all others 0.
- Rays run along each axis through the middle of every sub-cell, and are cut by the
  triangles exactly (a scanline over each triangle's projection, across its shorter side,
  half-open so a ray on an edge two triangles share counts once; each edge is worked out
  from its lower end, so both triangles compute it alike). The rays meet the triangles as
  they are, not nudged: nudging each triangle along its own normal opens hair-thin gaps
  between neighbours, and a ray through one missed a crossing on one side of a symmetric
  model and not on the other. Instead each crossing is moved 1e-6 of a cell into the solid
  along the ray, so a face on a cell boundary still lies in the cell behind it. Along a
  ray, the surface cells come in runs bounded by cells stage 1 knows to be outside or
  inside. The winding (+1 crossing into a part, -1 out of one) starts at the lower bound's
  own (0 outside, the ray's own count but at least 1 inside, so overlapping parts are one
  solid); where it ends at the upper bound's own the run agrees and a point is inside where
  the winding is 1 or more. A run that does not agree crosses a hole, a lone sheet or a
  part open at one end: then what the outside can reach along the ray is outside (nothing
  is inside between two outside bounds; up to the first crossing from an outside bound into
  an inside one; all of it between two inside bounds; half where an outside and an inside
  bound have no crossing between them). Each sub-cell takes the inside share of its length
  along the ray.
- Of the three rays through a sub-cell, the agreeing ones are used (all three if none
  agrees), and of those the one that crosses the surface most squarely inside the sub-cell
  (for a flat surface that is exact; within 1e-3 of the squarest, the first axis, so noise
  does not choose); a sub-cell no used ray crosses takes their mean. A closed part wound
  inside out (corners joined where equal; each edge used twice, once each way; negative
  volume) counts as wound outward, so a hollow made by an inverted inner shell is solid, as
  stage 1 had it.
- Mirror images measure alike. Files store single precision, so the mirror image of a cell
  in a symmetric model measures up to about 1e-5 differently (its corners are up to 1e-3 mm
  off). Each surface cell whose mirror image (left to right, and front to back) has the
  model in the same sub-cells, with shares within 1e-3 of its own, takes the mean of the
  two; a cell's coverage is the sum of its sub-cells in sorted order, so the two come out
  exactly equal. Coverages within 1e-5 of each other count as equal throughout rule 2.
- Measured: the coverage summed over a sphere of 8 to 16 studs is within 0.1% of its
  volume; box faces come out exact. Rule 1 alone puts a sphere 1 to 4% over its volume
  (thresholding a curved surface), 4% at 8 studs, and an upright cylinder up to 8.5% over
  (at 9 studs: 69 cells per layer are at least half covered, against an area of 63.6).
- Rule 1 counts from 0.5 - 1e-5 (the nudge into the solid takes up to 1e-6 from each face),
  so a box covering exactly half of two cells fills both, symmetrically.
- Rule 1's lines are the rays already cast for the coverage: s x s of them along each axis
  through each surface cell. A ray's share inside the cell is the sum of its sub-cells'
  inside lengths; a ray whose run disagrees with the cells known outside and inside (a
  crack in a file that is not watertight) uses the shares chosen for its sub-cells instead
  (from the other axes' rays), since on the sample pawn such a ray found a crack on one
  side only. Of the rays along an axis, those whose share is above 1e-6 meet the model;
  the axis passes when their mean is at least 0.5 - 1e-5, and fails when none does. A ray
  whose share is under 0.05 counts in proportion to its share (one of 0.02 counts as 0.4
  of a ray): counted in full, a ray that only grazes the model dragged the mean down by up
  to 0.07 the moment it touched, so a change of a hundredth of a millimetre could decide a
  cell (the sample duck, symmetric to within 0.08 mm, came out lopsided at 16 studs). Rays
  of a box all hold the same share, so a box is judged exactly as before; a larger
  threshold would also raise the mean on curved surfaces (at 0.1, a sphere of 8 studs came
  out 5.3% over its volume). The means of mirror-image cells that agree to within 0.02 are
  made exactly equal (the sub-cells: to within 1e-3), so a model that is symmetric to
  within a tenth of a millimetre gives symmetric filled cells. A cell at least half
  covered is filled even if its rays say otherwise (with s = 3 they measure a line average
  only to within about 0.07), so no cell rule 1 filled before is lost.
- Rule 2: "the side the surface faces away from" is taken as the side the cell's material
  lies on: along each axis where the middle of the material (from the sub-cells) is at
  least 0.1 of a cell from the cell's middle, the neighbour on that side, when the material
  reaches it across their shared face (both sub-layers next to the face hold some, at the
  same place). Material in the middle of the cell stays (the model is thin here). Where
  the material meets that neighbour over half of the face or more it is a skin and is
  handed on; over less (the end of a rod or a fin) only when it reaches less than half way
  into the cell on average, so a thin feature ends where it covers half of its last cell,
  as a thick one does, or when the cell meets fuller neighbours on two axes or more (it is
  the corner or edge of something larger, as at the corner of a box, not the end of a
  rod: kept, it made a lone bump). Of the candidates, the one holding most is taken (the
  first axis among equals), and the material is handed on when it holds more. Handing on
  repeats along the chain (a skin of a skin ends in the rule-1 cell it lies on): material
  that reaches a rule-1 cell adds nothing; otherwise the cell where it stops is filled.
  Ties stay where they are, so a rod exactly on a boundary keeps both cells.
- Rule 2 for a cell where the rays found no material at all. Its surface's net area (each
  piece's area times its outward normal, from clipping the triangles to it) tells which:
  a sliver of skin (the model reaches only a hair into the cell, as at the corner of a box
  off the grid) has its surface facing one way, net area at least half its area, and
  hands its share to the fullest cell behind that surface (on each axis where the net area
  has at least a fifth of its length) that holds material, or that a sliver handed its
  share to before: a row of slivers along an edge empties into the body one step at a
  time. Slivers with nothing of the model behind them stay. Before, a sliver whose
  neighbours were slivers too stayed, and rule 3 then joined it on through more slivers:
  stray cells holding under 0.01% of a cell, wider than ceil(w). Any other such cell (a
  sheet with no thickness, a thin feature the rays all miss, whose surface faces both ways)
  hands its share to the fullest neighbour its surface runs on into when that holds more,
  and otherwise stays, so such features do not vanish.
- Rule 3: two face-neighbours of stage 1's fill belong together when a triangle crosses
  their shared face (found while finding stage 1's surface cells), or when the model in
  them comes within a cell of each other across it (fewer than s - 1 empty sub-layers
  between; an inside cell is full). So two boxes a cell or more apart do not belong
  together even where stage 1 joined them. Where one such group's filled cells fall into
  several face-connected pieces, the pieces are joined along the cheapest paths through
  the group's emptied cells, a cell costing 1.5 minus its coverage (scipy's Dijkstra from
  all pieces at once, then a minimum spanning tree over the pieces it found next to each
  other); a tiny cost that grows away from the middle in x and y breaks ties the same way
  on both sides. A spanning tree keeps only one of two equally cheap joins that are mirror
  images of each other, so where the fill so far, stage 1's fill and the coverage are all
  mirror-symmetric, every cell added is added with its mirror images too. A group left
  without a filled cell keeps its fullest one (and its mirror images).
- Standing (not in the contract's rules; it keeps "it stands" true): a cell of the bottom
  layer that stage 1 filled is filled too when the model reaches the ground inside it (its
  lowest sub-layer holds some of the model) and the cell above it is filled. Otherwise a
  model resting on round parts (a car's wheels, a ball) lost the cells it stands on, which
  hold less than half, and floated or tipped over. Applied before rule 3. After rule 3, if
  the centre of mass of the filled cells is not over the convex hull of the bottom layer's
  cells (the sample spaceship rests on a small part of itself and leans out; stage 1's
  wider bottom layer hid it), the bottom cells of stage 1's fill under filled cells are
  added, nearest the centre of mass first and mirror images together, as few as make it
  stand (found by halving); none if even all of them do not.
- Slope hints of an open-topped filled cell count the upward surface in the emptied surface
  cells stacked right above it (up to the first cell that is not an emptied surface cell)
  as its own, and leave out their walls, which belong to cells that are not there.
- Rule 4 runs last, after the colours and the slope hints: the empty cells are labelled
  (6-connected) once, the labels that touch the four sides or the top layer of the body
  are outside air (beyond those faces is the padding, which is air; the bottom is left
  out), and every skin cell with another label is filled with its skin colour and its skin
  entry cleared. A skin cell is empty, so it has an outside-air neighbour exactly when it
  is outside air itself. The new fill lies inside stage 1's, so its empty space reaches
  the outside wherever stage 1's did: what is hidden is in practice the space stage 1
  reached from below z = 0 alone, with the skin that lines it. That is why, of the sample
  models, only the hat gains cells (64 at 12 studs, 120 at 16), and not at 24 studs:
  there its crown steps diagonally from layer to layer, the steps meet only at edges, and
  the hollow under it reaches the outside through those gaps, which only skin cells
  close. A cell rule 4 fills is FINISH_STUDS; the cell under it keeps the slope hint it
  had as an open top (bricksnap/finish.py only shapes open cells, so a covered one's hint
  does nothing), so that no filled cell's hint changes.
- Hollowing comes after rule 4 and treats the cells it filled as wall like any other: the
  shell rule is measured from the empty cells that remain, the hollow under a hat among
  them, so a wall rule 4 thickened is kept in full next to that hollow, and the floor is
  kept as before (below the grid counts as outside for the shell rule). Only where rule 4
  filled a whole hollow can hollowing then empty cells near it that it kept before; such a
  cell is left with no skin entry, as hollowing never changes the skin.

Slope hints (implementation notes)
- Only the surface that faces up (n_z above cos 70 degrees, in millimetres) is averaged.
  Walls (n_z within cos 70 degrees of level) and undersides are left out of the mean.
  Averaging everything, as the contract's first sentence reads, would mark every top edge
  of a box: an edge cell holds 64 mm² of top and 25.6 mm² of side, whose mean has n_z =
  0.93, and a corner cell 0.87. Left out, the walls cannot drag a flat top into the band,
  and the gable ends and eaves of a roof are still sloped. Since everything averaged faces
  up, normals can no longer cancel out; a cell with no upward surface is FINISH_STUDS.
- So a thin slanted sheet whose top and underside share a cell is sloped: the underside is
  left out rather than cancelling the top. This is deliberate, because roofs are often
  modelled as thin sheets and would otherwise get no slopes, but it departs from the
  contract's "whose normals cancel out" sentence; the lead may decide otherwise.
- Walls still have one say: a cell is sloped only when its upward surface is at least as
  large (in mm²) as its walls seen from downhill. Each wall counts its area times how
  squarely it faces the way the upward surface runs down (the horizontal direction of
  their mean normal), and nothing if it faces across the slope or back uphill. So a wall
  that pokes a little way into a new column with a small chamfer or rounding on its top
  edge keeps its studs (that wall faces downhill), while the gable wall at the end of a
  roof, the sides of a narrow ramp and the back of a wedge, which face across the slope or
  away from it, never take a cell's slope away, however little of the slope the cell holds.
- There is no minimum area. A ramp often reaches only a sliver of the top cell of a column
  (the rest of its surface is in the cells below, which are covered); the sliver's own
  normal is the right one, so every column along a ramp is marked.
- What the grid does with this, on purpose or not: a cone's tip in the middle of a column
  is FINISH_STUDS (its sides cancel sideways), but a tip on the corner of four columns
  gives each of them one side, so all four are sloped. A rounded edge whose rounding falls
  alone in the outermost column is sloped there, while on the other side of the same
  model the rounding can share a cell with the flat top and keep its studs.
- A mesh wound inside out has its tops facing down, so they count as undersides: it gets
  no slope hints at all. (Its filled cells can also grow by up to one cell, see above.)
- The hints are worked out on the solid shape, before hollowing; a hollowed-out cell is
  FINISH_STUDS. The extra work is one more clip of the triangles that face up or sideways,
  completed only in open-topped cells (about a fifth more time on a 200,000-triangle mesh).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse import csgraph
from scipy.spatial import ConvexHull

from bricksnap.catalog import Catalog
from bricksnap.types import (
    CELL_MM,
    DEFAULT_COLOUR,
    EMPTY,
    FINISH_SLOPED,
    FINISH_STUDS,
    Design,
    Seed,
    SeedError,
)

_CEIL_EPS = 1e-6  # cells; an exact multiple of the cell size does not gain a cell
_SNAP = 1e-4  # cells; coordinates this close to a cell boundary are put on it
_NUDGE = 1e-6  # cells; how far each triangle is moved into the solid before testing
_TOUCH = 1e-9  # cells; reaching less than this into a cell counts as only touching it
_TIE = 1e-6  # relative; colour votes this close to the best count as a tie
_PIECES = 250_000  # (triangle, cell) pieces made per batch, to bound memory
_STEEP = float(np.cos(np.radians(70.0)))  # n_z at or below this: a wall or an underside
_FLAT = float(np.cos(np.radians(20.0)))  # n_z at or above this: a flat top
_SUB_LIMIT = 4_000_000  # sub-cells of surface cells at 3 per axis; beyond this, 2 per axis
_MATERIAL = 1e-6  # share of a sub-cell below which it holds none of the model
_GRAZE = 0.05  # a ray holding less than this share of a cell's length counts only in part
_LINE_NOISE = 0.02  # line averages of mirror-image cells this close are made equal
_EVEN = 1e-5  # coverages this close count as equal (files store single precision)
_NOISE = 1e-3  # sub-cell shares this close in mirror-image cells differ only by file noise
_SQUARE = 1e-3  # rays whose squareness to the surface differs by less meet it alike
_HALF = 1e-5  # coverage this close below 0.5 counts as half (the nudge takes up to 6e-6)
_SIDE = 0.1  # cells; material this far off a cell's middle lies on that side of it


def voxelize(
    seed: Seed,
    catalog: Catalog,
    *,
    hollow: bool = False,
    shell_studs: int = 2,
    margin_studs: int = 2,
    default_colour: int = DEFAULT_COLOUR,
    slope_hints: bool = True,
) -> Design:
    """Turn a Seed into a Design (see the module docstring for the rules)."""
    shell_studs = _whole(shell_studs, "shell_studs", minimum=1)
    margin_studs = _whole(margin_studs, "margin_studs", minimum=0)
    default_colour = _solid_colour(default_colour, catalog)
    vertices = np.asarray(seed.vertices, dtype=np.float64)
    faces = np.asarray(seed.faces, dtype=np.int64)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("Seed.vertices must be an (n, 3) array")
    if faces.size == 0:
        raise SeedError("The model has no triangles, so there is nothing to turn into bricks.")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError("Seed.faces must be an (m, 3) array")
    if faces.min() < 0 or faces.max() >= len(vertices):
        raise ValueError("Seed.faces refers to vertices that do not exist")
    if not np.isfinite(vertices[faces]).all():
        raise SeedError("The model is damaged: some of its points have no valid position.")
    face_colors = seed.face_colors
    if face_colors is not None:
        face_colors = np.asarray(face_colors)
        if face_colors.shape != (len(faces), 3):
            raise ValueError("Seed.face_colors must be an (m, 3) array, one RGB per face")

    tris, body = _place(vertices[faces])
    nx, ny, nz = body

    # colour of each face, as an index into `codes`
    if face_colors is None:
        codes = np.asarray([default_colour], dtype=np.int64)
        face_code = np.zeros(len(faces), dtype=np.int64)
    else:
        codes, face_code = _snap(face_colors, catalog)

    # 1. stage 1's fill: every cell the surface passes through, and what the outside cannot
    # reach; it bounds the new fill and says which parts belong together
    keep, nudged, estimate, axes = _prepare(tris)
    kept_code = face_code[keep]
    surface, pairs, crossed = _surface_pass(nudged, estimate, axes, body, kept_code, len(codes))
    stage1 = _fill_inside(surface)
    interior = stage1 & ~surface

    # 2. how much of each cell the model fills, and which cells keep its material
    s = _subdivision(int(surface.sum()))
    flip = _turned_out(tris[keep])
    sub, occupied, index, lines = _coverage(tris[keep], flip, body, surface, interior, s)
    _even_out(sub, occupied, index)
    _even_out_lines(lines, index)
    coverage = interior.astype(np.float64)
    # summed in sorted order, so that mirror-image cells come out exactly equal
    coverage[surface] = np.sort(sub.reshape(len(sub), -1), axis=1).sum(axis=1) / s**3
    empty_handed = surface & (coverage * s**3 <= _MATERIAL)  # cells the rays found nothing in
    net, area = _facing(nudged, flip, estimate, axes, body, index, empty_handed)
    # rule 1: on every axis, the lines through the cell that meet the model are at least
    # half inside it on average (so every cell at least half covered, and a box's corners)
    across = np.zeros(body, dtype=bool)
    across[surface] = (lines >= 0.5 - _HALF).all(axis=1)
    rule1 = interior | (surface & (across | (coverage >= 0.5 - _HALF)))
    filled, went = _choose(
        coverage, sub, occupied, net, area, index, surface, stage1, crossed, rule1
    )

    # 3. colours, from the surface in each filled cell and in the emptied cells around it
    dropped = surface & ~filled
    colours, skin = _colours(
        nudged, estimate, axes, body, kept_code, codes, pairs, filled, dropped, went,
        default_colour,
    )  # fmt: skip

    # 4. slope hints, on the solid shape, so hollowing cannot change them
    finish = np.full(body, FINISH_STUDS, dtype=np.uint8)
    if slope_hints:
        open_top = filled & ~np.concatenate([filled[:, :, 1:], np.zeros((nx, ny, 1), bool)], 2)
        # the emptied surface cells stacked right above an open top are its skin: for each,
        # the flat index of that top (-1 for every other cell)
        z = np.arange(nz)
        base = np.maximum.accumulate(np.where(dropped, -1, z), axis=2)  # last cell not dropped
        home = np.full(body, -1, dtype=np.int64)
        xs, ys, zs = np.nonzero(dropped & (base >= 0))
        top = base[xs, ys, zs]
        on_top = open_top[xs, ys, top]
        home[xs[on_top], ys[on_top], zs[on_top]] = np.ravel_multi_index(
            (xs[on_top], ys[on_top], top[on_top]), body
        )
        finish[_sloped(tris, body, open_top, home)] = FINISH_SLOPED

    # 5. rule 4: the skin nobody can see thickens the wall it lines (after the slope hints,
    # so the cells already filled keep theirs; a cell filled here is FINISH_STUDS)
    hidden = _hidden_skin(filled, skin != EMPTY)
    colours[hidden] = skin[hidden]
    skin[hidden] = EMPTY
    filled = filled | hidden

    if hollow:
        colours[filled & ~_keep_shell(filled, shell_studs)] = EMPTY
        finish[colours == EMPTY] = FINISH_STUDS

    m = margin_studs
    grid = np.full((nx + 2 * m, ny + 2 * m, nz + 3 * m), EMPTY, dtype=np.int16)
    grid[m : m + nx, m : m + ny, :nz] = colours
    finish_grid = np.full(grid.shape, FINISH_STUDS, dtype=np.uint8)
    finish_grid[m : m + nx, m : m + ny, :nz] = finish
    skin_grid = np.full(grid.shape, EMPTY, dtype=np.int16)
    skin_grid[m : m + nx, m : m + ny, :nz] = skin
    return Design(colors=grid, finish=finish_grid, seed_offset=(m, m, 0), skin=skin_grid)


# ---- helpers --------------------------------------------------------------------------------


def _whole(value: Any, name: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int | np.integer) or value < minimum:
        raise ValueError(f"{name} must be a whole number of at least {minimum}, not {value!r}")
    return int(value)


def _solid_colour(value: Any, catalog: Catalog) -> int:
    colour = None
    if isinstance(value, int | np.integer) and not isinstance(value, bool):
        colour = catalog.colours.get(int(value))
    if colour is None or colour.transparent:
        raise ValueError(
            f"default_colour must be the LDraw code of a solid colour in the parts table, "
            f"not {value!r}"
        )
    return int(colour.code)


def _place(tris_mm: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int]]:
    """Triangles (m, 3, 3) in mm to cell units on the body grid, and the body's size.

    On each axis where the seed starts within the first cell (0 <= minimum < 1 cell; never
    in z) it keeps that offset, so a point p is in body cell floor(p / CELL_MM). Elsewhere,
    or where the seed would then reach past the ceil(extent / cell) cells the body has, it
    is first moved along that axis to start at 0. Coordinates within _SNAP of a cell
    boundary are put on it."""
    cell = np.asarray(CELL_MM, dtype=np.float64)
    low = tris_mm.reshape(-1, 3).min(axis=0)
    keep = (low >= 0.0) & (low < cell)
    keep[2] = False  # the model stands on z = 0
    while True:
        tris = (tris_mm - np.where(keep, 0.0, low)) / cell
        nearest = np.round(tris)
        tris = np.where(np.abs(tris - nearest) < _SNAP, nearest, tris)
        flat = tris.reshape(-1, 3)
        start, end = flat.min(axis=0), flat.max(axis=0)
        size = np.maximum(1, np.ceil(end - start - _CEIL_EPS)).astype(np.int64)
        beyond = keep & (end > size + _CEIL_EPS)  # would need one more cell: move it to 0
        if not beyond.any():
            return tris, (int(size[0]), int(size[1]), int(size[2]))
        keep &= ~beyond


def _snap(face_colors: np.ndarray, catalog: Catalog) -> tuple[np.ndarray, np.ndarray]:
    """Snap every distinct face RGB to the catalogue: (sorted codes, code index per face).

    The snapping itself is ``Catalog.nearest_colours`` (solid colours only), so a colour
    lands on the same catalogue colour here as anywhere else in BrickSnap."""
    rgb = np.clip(np.round(face_colors.astype(np.float64)), 0, 255)
    distinct, which = np.unique(rgb, axis=0, return_inverse=True)
    snapped = catalog.nearest_colours(distinct, solid_only=True)
    codes, code_index = np.unique(snapped, return_inverse=True)
    return codes, code_index[which.ravel()]


def _vote(
    cell: np.ndarray, code: np.ndarray, weight: np.ndarray, n_codes: int
) -> tuple[np.ndarray, np.ndarray]:
    """The winning colour index of each cell: most area, near-ties to the lower index.

    ``code`` indexes the sorted LDraw codes, so the lower index is the lower code."""
    unique, inverse = np.unique(cell * n_codes + code, return_inverse=True)
    votes = np.bincount(inverse.ravel(), weights=weight, minlength=len(unique))
    vote_cell, vote_code = unique // n_codes, unique % n_codes  # by cell, then by code
    starts = np.flatnonzero(np.r_[True, vote_cell[1:] != vote_cell[:-1]])
    best = np.maximum.reduceat(votes, starts)
    best = np.repeat(best, np.diff(np.r_[starts, len(votes)]))
    contender = np.flatnonzero(votes >= best * (1.0 - _TIE))
    _, first = np.unique(vote_cell[contender], return_index=True)  # lowest code per cell
    winners = contender[first]
    return vote_cell[winners], vote_code[winners]


def _most_common(values: np.ndarray) -> int:
    found, counts = np.unique(values, return_counts=True)
    return int(found[np.argmax(counts)])  # np.unique sorts, so ties go to the lower code


def _flat_cells(body: tuple[int, int, int]) -> Callable[[np.ndarray], np.ndarray]:
    """A function from cells (q, 3) to flat body-cell indices, clamping anything beyond."""
    shape = np.asarray(body, dtype=np.int64)
    strides = np.array([body[1] * body[2], body[2], 1], dtype=np.int64)

    def flat(cell: np.ndarray) -> np.ndarray:
        return np.clip(cell, 0, shape - 1) @ strides

    return flat


def _surface_pass(
    nudged: np.ndarray,
    estimate: np.ndarray,
    axes: tuple[int, ...],
    body: tuple[int, int, int],
    code: np.ndarray,
    n_codes: int,
) -> tuple[np.ndarray, np.ndarray, list[np.ndarray]]:
    """Stage 1's surface cells: every cell a triangle passes through the inside of.

    ``nudged`` and ``estimate`` come from ``_prepare``; ``code`` is each triangle's colour
    index. Returns the cells (bool, shape ``body``), the distinct (cell, colour) pairs as
    flat cell * n_codes + code (empty with one colour), and for each axis the faces some
    triangle crosses: ``crossed[a][cell]`` is the face between the cell and the next one
    along axis a (a triangle with pieces in two face-neighbours crosses the face between).
    """
    n_cells = int(np.prod(body))
    flat = _flat_cells(body)
    shape = np.asarray(body, dtype=np.int64)
    surface = np.zeros(n_cells, dtype=bool)
    crossed = [np.zeros(n_cells, dtype=bool) for _ in range(3)]
    # a cell index in the order the clip cuts the axes, so each batch's pieces come out
    # sorted by (triangle, that index) and a neighbour is found by binary search
    order_stride = np.zeros(3, dtype=np.int64)
    order_stride[axes[2]] = 1
    order_stride[axes[1]] = body[axes[2]]
    order_stride[axes[0]] = body[axes[1]] * body[axes[2]]
    pairs_out = []
    for batch in _batches(np.arange(len(nudged)), estimate):
        _, _, owner, cell = _clip_to_cells(nudged[batch], axes)
        cell = np.clip(cell, 0, shape - 1)
        where = flat(cell)
        surface[where] = True
        if n_codes > 1:
            pairs_out.append(np.unique(where * n_codes + code[batch[owner]]))
        key = owner * n_cells + cell @ order_stride
        for axis in range(3):
            if body[axis] == 1:
                continue
            target = key + order_stride[axis]
            at = np.minimum(np.searchsorted(key, target), len(key) - 1)
            found = (key[at] == target) & (cell[:, axis] < body[axis] - 1)
            crossed[axis][where[found]] = True
    pairs = np.unique(np.concatenate(pairs_out)) if pairs_out else np.zeros(0, dtype=np.int64)
    return surface.reshape(body), pairs, [c.reshape(body) for c in crossed]


def _facing(
    nudged: np.ndarray,
    flip: np.ndarray,
    estimate: np.ndarray,
    axes: tuple[int, ...],
    body: tuple[int, int, int],
    index: np.ndarray,
    wanted: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """The surface inside each ``wanted`` cell: its net area as a vector (each piece's area
    times its outward unit normal, in cell units) and its total area, indexed like the
    surface cells (zero for cells not wanted)."""
    n = int(index.max()) + 1 if index.size else 0
    net = np.zeros((n, 3))
    area = np.zeros(n)
    if not wanted.any():
        return net, area
    flat = _flat_cells(body)
    wanted_flat = wanted.ravel()
    index_flat = index.ravel()
    for batch in _batches(np.arange(len(nudged)), estimate):
        poly, count, owner, cell = _clip_to_cells(
            nudged[batch], axes, select=lambda c: wanted_flat[flat(c)]
        )
        if len(owner) == 0:
            continue
        rel = poly[:, 1:] - poly[:, :1]
        fan = np.cross(rel[:, :-1], rel[:, 1:])
        real = (np.arange(1, poly.shape[1] - 1)[None, :] + 1) < count[:, None]
        vector = 0.5 * (fan * real[:, :, None]).sum(axis=1) * flip[batch[owner], None]
        where = index_flat[flat(cell)]
        for k in range(3):
            net[:, k] += np.bincount(where, vector[:, k], minlength=n)
        area += np.bincount(where, np.linalg.norm(vector, axis=1), minlength=n)
    return net, area


def _even_out(sub: np.ndarray, occupied: np.ndarray, index: np.ndarray) -> None:
    """Make the measurements of mirror-image cells (left to right, and front to back) equal
    where they differ only by the noise of a file's single precision, in place.

    Each surface cell whose mirror image is a surface cell too, with the model in the same
    sub-cells, and whose sub-cells' shares agree with the mirror image's to within _NOISE,
    takes the mean of the two, so the rules that follow treat both sides alike."""
    for axis in (0, 1):
        mirror = np.flip(index, axis)
        both = (index >= 0) & (mirror >= 0)
        mine, theirs = index[both], mirror[both]
        a, b = sub[mine], np.flip(sub[theirs], 1 + axis)
        same = (occupied[mine] == np.flip(occupied[theirs], 1 + axis)).all(axis=(1, 2, 3))
        close = same & (np.abs(a - b).max(axis=(1, 2, 3)) <= _NOISE)
        sub[mine[close]] = (a[close] + b[close]) / 2


def _even_out_lines(lines: np.ndarray, index: np.ndarray) -> None:
    """As ``_even_out``, for the line averages (n_surface, 3) of mirror-image cells: where
    the two differ by no more than _NOISE, both take their mean, so they are exactly equal.
    (Mirroring keeps each axis's lines lines of that axis, so the averages are compared
    axis by axis.)"""
    for axis in (0, 1):
        mirror = np.flip(index, axis)
        both = (index >= 0) & (mirror >= 0)
        mine, theirs = index[both], mirror[both]
        a, b = lines[mine], lines[theirs]
        close = np.abs(a - b) <= _LINE_NOISE
        lines[mine] = np.where(close, (a + b) / 2, a)


def _subdivision(n_surface: int) -> int:
    """Sub-cells per axis for the coverage: 3 (27 per cell), or 2 on very large models."""
    return 3 if n_surface * 27 <= _SUB_LIMIT else 2


def _turned_out(tris: np.ndarray) -> np.ndarray:
    """+1 for each triangle, -1 for those of a closed part wound inside out.

    Corners are joined where their coordinates are equal. A part is closed when each of its
    edges is used by exactly two of its triangles, once in each direction; a closed part
    whose volume comes out negative is wound inside out and is solid all the same."""
    m = len(tris)
    flip = np.ones(m, dtype=np.int64)
    if m == 0:
        return flip
    _, vertex = np.unique(tris.reshape(-1, 3), axis=0, return_inverse=True)
    vertex = vertex.reshape(m, 3)
    n_vertices = int(vertex.max()) + 1
    start, end = vertex.ravel(), vertex[:, [1, 2, 0]].ravel()
    key = np.minimum(start, end) * n_vertices + np.maximum(start, end)
    order = np.argsort(key, kind="stable")
    ks = key[order]
    first = np.flatnonzero(np.r_[True, ks[1:] != ks[:-1]])
    count = np.diff(np.r_[first, len(ks)])
    forward = np.add.reduceat((start < end)[order].astype(np.int64), first)
    good = np.repeat((count == 2) & (forward == 1), count)  # per half-edge, in `order`
    twice = first[count == 2]
    graph = sparse.coo_matrix(
        (np.ones(len(twice)), (order[twice] // 3, order[twice + 1] // 3)), shape=(m, m)
    )
    n_parts, part = csgraph.connected_components(graph, directed=False)
    open_part = np.zeros(n_parts, dtype=bool)
    open_part[part[order[~good] // 3]] = True
    volume = np.einsum("ij,ij->i", tris[:, 0], np.cross(tris[:, 1], tris[:, 2]))
    part_volume = np.bincount(part, volume, minlength=n_parts)
    inverted = ~open_part & (part_volume < 0)
    flip[inverted[part]] = -1
    return flip


def _coverage(
    exact: np.ndarray,
    flip: np.ndarray,
    body: tuple[int, int, int],
    surface: np.ndarray,
    interior: np.ndarray,
    s: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """How much of each sub-cell of each surface cell lies inside the model.

    Each surface cell is cut into s x s x s sub-cells. Rays run along each axis through the
    middle of every sub-cell; along each ray, what is inside is worked out from the
    surface crossings (see ``_axis_coverage``), and a sub-cell takes the share of its
    length that is inside. Of the three rays through a sub-cell, the one whose run of cells
    agrees with the cells known to be outside or inside is preferred, and among those the
    one crossing the surface most squarely inside the sub-cell (for a flat surface that is
    exact); a sub-cell no agreeing ray crosses takes their mean.

    Returns the share inside, (n_surface, s, s, s) indexed [cell, x, y, z]; which sub-cells
    hold any of the model (material or a ray crossing); the surface-cell index of each
    body cell (-1 elsewhere); and, for each surface cell and axis (n_surface, 3), how much
    of the cell's length the rays along that axis that meet the model in it lie inside it,
    on average (0 when none does)."""
    n = int(surface.sum())
    index = np.full(body, -1, dtype=np.int64)
    index[surface] = np.arange(n)
    estimate = np.zeros((3, n, s, s, s))
    weight = np.zeros((3, n, s, s, s))
    agree = np.zeros((3, n, s, s, s), dtype=bool)
    lines = np.zeros((n, 3))
    sub_tris = exact * s  # not nudged: triangles that share an edge must still share it
    normal = np.cross(sub_tris[:, 1] - sub_tris[:, 0], sub_tris[:, 2] - sub_tris[:, 0])
    length = np.linalg.norm(normal, axis=1)
    for axis in range(3):
        _axis_coverage(
            sub_tris, normal, length, flip, axis, body, surface, interior, index, s,
            estimate[axis], weight[axis], agree[axis],
        )  # fmt: skip
    use = agree | ~agree.any(axis=0)[None]
    score = np.where(use, weight, -1.0)
    # the first axis whose ray is within _SQUARE of the squarest, so that the choice does not
    # turn on noise where two rays meet the surface alike (mirror images stay alike)
    best = (score >= score.max(axis=0) - _SQUARE).argmax(axis=0)[None]
    mean = (estimate * use).sum(axis=0) / use.sum(axis=0)
    share = np.where(
        np.take_along_axis(score, best, 0)[0] > 0, np.take_along_axis(estimate, best, 0)[0], mean
    )
    occupied = (share > _MATERIAL) | (weight.max(axis=0) > 0)
    # for each axis, the share of the cell's length inside the model along each of its s x s
    # rays, averaged over the rays that meet the model in the cell (0 when none does); a ray
    # holding less than _GRAZE counts in proportion, so one that starts to graze the model
    # moves the average a little, not by a whole ray's worth
    for axis in range(3):
        # a ray whose run disagrees with the cells known outside and inside (a crack in the
        # surface, a lone sheet) is replaced by the shares chosen for its sub-cells above
        length = (
            np.where(
                agree[axis].all(axis=1 + axis),
                estimate[axis].sum(axis=1 + axis),
                share.sum(axis=1 + axis),
            )
            / s
        )  # (n, s, s)
        counts = np.where(length > _MATERIAL, np.minimum(length / _GRAZE, 1.0), 0.0)
        total = counts.sum(axis=(1, 2))
        lines[:, axis] = np.where(
            total > 0, (length * counts).sum(axis=(1, 2)) / np.where(total > 0, total, 1.0), 0.0
        )
    return share, occupied, index, lines


def _axis_coverage(
    sub_tris: np.ndarray,
    normal: np.ndarray,
    length: np.ndarray,
    flip: np.ndarray,
    axis: int,
    body: tuple[int, int, int],
    surface: np.ndarray,
    interior: np.ndarray,
    index: np.ndarray,
    s: int,
    estimate: np.ndarray,
    weight: np.ndarray,
    agree: np.ndarray,
) -> None:
    """Fill ``estimate``, ``weight`` and ``agree`` (each (n_surface, s, s, s)) for one axis.

    Rays run along ``axis`` through the middle of each sub-cell. Along a ray the surface
    cells come in runs, bounded by cells known to be outside (or the edge of the grid) or
    inside. Coming from the lower end, the winding (+1 for each crossing into a part, -1
    out of one) starts at the lower bound's own: 0 outside, at least 1 inside. Where it
    ends at the upper bound's own winding the run agrees, and a point is inside where the
    winding is 1 or more (so parts that overlap make one solid). Where it does not agree
    (a hole in the surface, a lone sheet, a part open at one end), what the outside can
    reach along the ray is outside: between two outside ends, all of it; from an outside
    end up to the first crossing towards an inside end; with an inside cell at both ends
    nothing; with no crossing between an outside and an inside end, half. ``weight`` is how
    squarely the steepest crossing inside a sub-cell meets the ray (0 with none)."""
    b, c = (d for d in range(3) if d != axis)
    nb, nc, na = body[b], body[c], body[axis]
    ub, uc, ua = nb * s, nc * s, na * s
    ray, pos, step, steep = _cast(
        sub_tris, normal, length, flip, axis, b, c, ub, uc, ua, _NUDGE * s
    )
    span = ua + 2.0
    key = ray * span + pos
    order = np.argsort(key, kind="stable")
    ray, pos, step, steep, key = ray[order], pos[order], step[order], steep[order], key[order]
    wind = np.r_[0, np.cumsum(step)]  # winding before crossing k is wind[k] (whole ray)

    # runs of surface cells along the axis, line by line
    lines = surface.transpose(b, c, axis)
    inside_t = interior.transpose(b, c, axis)
    pad = np.zeros((nb, nc, 1), dtype=bool)
    starts = lines & ~np.concatenate([pad, lines[:, :, :-1]], axis=2)
    ends = lines & ~np.concatenate([lines[:, :, 1:], pad], axis=2)
    lb, lc, r0 = np.nonzero(starts)
    r1 = np.nonzero(ends)[2]
    lo_in = np.zeros(len(r0), dtype=bool)
    hi_in = np.zeros(len(r0), dtype=bool)
    below, above = r0 > 0, r1 < na - 1
    lo_in[below] = inside_t[lb[below], lc[below], r0[below] - 1]
    hi_in[above] = inside_t[lb[above], lc[above], r1[above] + 1]

    # one row per (run, ray through it)
    s2 = s * s
    run = np.repeat(np.arange(len(r0)), s2)
    pb = np.tile(np.repeat(np.arange(s), s), len(r0))
    pc = np.tile(np.tile(np.arange(s), s), len(r0))
    ray_id = (lb[run] * s + pb) * uc + (lc[run] * s + pc)
    a0 = (r0[run] * s).astype(np.float64)
    a1 = ((r1[run] + 1) * s).astype(np.float64)
    k_ray = np.searchsorted(key, ray_id * span)
    k_end = np.searchsorted(key, ray_id * span + span - 1)
    k0 = np.searchsorted(key, ray_id * span + a0)
    k1 = np.searchsorted(key, ray_id * span + a1)
    w0 = wind[k0] - wind[k_ray]  # winding from the lower end, just before the run
    w1 = wind[k1] - wind[k_ray]  # and just after it
    total = wind[k_end] - wind[k_ray]
    lo = np.where(lo_in[run], np.maximum(1, w0), 0)
    hi = np.where(hi_in[run], np.maximum(1, w1 - total), 0)
    offset = lo - w0
    ok = (w1 + offset) == hi
    n_cross = k1 - k0
    padded = np.r_[pos, 0.0]  # so that rows without a crossing can index it
    first = np.where(n_cross > 0, padded[k0], a0)
    last = np.where(n_cross > 0, padded[np.maximum(k1 - 1, 0)], a1)

    # inside length from the run's start up to each crossing in an agreeing run
    rows = np.repeat(np.arange(len(run)), n_cross)
    cross = np.repeat(k0 - np.cumsum(n_cross) + n_cross, n_cross) + np.arange(len(rows))
    after = (wind[cross + 1] - wind[k_ray[rows]] + offset[rows]) >= 1
    is_first = cross == k0[rows]
    before = np.where(is_first, lo[rows] >= 1, np.r_[False, after[:-1]])
    gap = pos[cross] - np.where(is_first, a0[rows], np.r_[0.0, pos[cross][:-1]])
    piece = before * gap
    total_len = np.cumsum(piece)
    upto = np.zeros(len(pos) + 1)
    upto[cross] = total_len - np.repeat((total_len - piece)[is_first], n_cross[n_cross > 0])
    inside_after = np.zeros(len(pos) + 1, dtype=bool)
    inside_after[cross] = after

    # the inside length from the run's start at every sub-cell boundary along each row
    n_pos = (r1[run] - r0[run] + 1) * s + 1
    erow = np.repeat(np.arange(len(run)), n_pos)
    at = a0[erow] + (np.arange(len(erow)) - np.repeat(np.cumsum(n_pos) - n_pos, n_pos))
    last_cross = np.searchsorted(key, ray_id[erow] * span + at, side="right") - 1
    last_cross = np.minimum(last_cross, k1[erow] - 1)
    has = last_cross >= k0[erow]
    lc_safe = np.maximum(last_cross, 0)
    agreeing = np.where(
        has,
        upto[lc_safe] + inside_after[lc_safe] * (at - padded[lc_safe]),
        (lo[erow] >= 1) * (at - a0[erow]),
    )
    lo_out, hi_out = ~lo_in[run[erow]], ~hi_in[run[erow]]
    some = n_cross[erow] > 0
    f, g = first[erow], last[erow]
    from_start = at - a0[erow]
    fallback = np.where(
        lo_out & hi_out,
        0.0,
        np.where(
            lo_out,
            np.where(some, np.maximum(0.0, at - f), 0.5 * from_start),
            np.where(hi_out, np.where(some, np.minimum(at, g) - a0[erow], 0.5 * from_start),
                     from_start),
        ),
    )  # fmt: skip
    length_in = np.where(ok[erow], agreeing, fallback)

    # each sub-cell: the difference between its two boundaries
    seg = np.flatnonzero(np.r_[erow[1:] == erow[:-1], False])
    share = np.clip(length_in[seg + 1] - length_in[seg], 0.0, 1.0)
    srow = erow[seg]
    j = (at[seg] - a0[srow]).astype(np.int64)
    cell = np.zeros((len(seg), 3), dtype=np.int64)
    cell[:, axis] = r0[run[srow]] + j // s
    cell[:, b] = lb[run[srow]]
    cell[:, c] = lc[run[srow]]
    local = np.zeros((len(seg), 3), dtype=np.int64)
    local[:, axis] = j % s
    local[:, b] = pb[srow]
    local[:, c] = pc[srow]
    sub = _sub_index(index, cell, local, s)
    estimate.reshape(-1)[sub] = share
    agree.reshape(-1)[sub] = ok[srow]

    # how squarely the steepest crossing in each sub-cell meets the ray
    if len(rows):
        j = np.clip(np.floor(pos[cross] - a0[rows]).astype(np.int64), 0, None)
        j = np.minimum(j, (r1[run[rows]] - r0[run[rows]] + 1) * s - 1)
        cell = np.zeros((len(rows), 3), dtype=np.int64)
        cell[:, axis] = r0[run[rows]] + j // s
        cell[:, b] = lb[run[rows]]
        cell[:, c] = lc[run[rows]]
        local = np.zeros((len(rows), 3), dtype=np.int64)
        local[:, axis] = j % s
        local[:, b] = pb[rows]
        local[:, c] = pc[rows]
        np.maximum.at(weight.reshape(-1), _sub_index(index, cell, local, s), steep[cross])


def _choose(
    coverage: np.ndarray,
    sub: np.ndarray,
    occupied: np.ndarray,
    net: np.ndarray,
    area: np.ndarray,
    index: np.ndarray,
    surface: np.ndarray,
    stage1: np.ndarray,
    crossed: list[np.ndarray],
    rule1: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Rules 1 to 3: which cells are filled (bool, the body's shape), and for each surface
    cell rule 1 leaves empty, the flat index of the cell its material went to (-1
    elsewhere). ``rule1`` is the cells rule 1 fills."""
    interior = stage1 & ~surface
    low = surface & ~rule1
    kept, went = _keepers(coverage, sub, occupied, net, area, index, low, rule1, interior, crossed)
    filled = rule1 | kept
    # the model keeps standing where it stood: a bottom cell of stage 1's fill in whose lowest
    # sub-layer the model reaches the ground, under a filled cell, is filled
    resting = np.zeros(coverage.shape, dtype=bool)
    where = np.flatnonzero(surface[:, :, 0].ravel())
    if len(where) and coverage.shape[2] > 1:
        xy = np.stack(np.unravel_index(where, coverage.shape[:2]), axis=1)
        floor = occupied[index[xy[:, 0], xy[:, 1], 0]][:, :, :, 0].any(axis=(1, 2))
        up = filled[xy[:, 0], xy[:, 1], 1]
        resting[xy[floor & up, 0], xy[floor & up, 1], 0] = True
    filled |= resting
    filled = _join(filled, coverage, occupied, index, surface, stage1, crossed)
    return _stand(filled, stage1, coverage), went


def _stands(filled: np.ndarray) -> bool:
    """Whether the centre of mass of the filled cells (each weighing the same, at its middle)
    lies over the convex hull of the corners of the filled cells of the bottom layer."""
    total = filled.sum()
    centre = np.array(
        [filled.sum(axis=(1, 2)) @ (np.arange(filled.shape[0]) + 0.5),
         filled.sum(axis=(0, 2)) @ (np.arange(filled.shape[1]) + 0.5)]
    ) / total  # fmt: skip
    base = np.argwhere(filled[:, :, 0]).astype(np.float64)
    corners = np.unique(
        np.concatenate([base + d for d in ((0, 0), (1, 0), (0, 1), (1, 1))]), axis=0
    )
    hull = ConvexHull(corners)  # cell corners always span an area
    return bool((hull.equations[:, :2] @ centre + hull.equations[:, 2] <= 1e-9).all())


def _stand(filled: np.ndarray, stage1: np.ndarray, coverage: np.ndarray) -> np.ndarray:
    """Standing, part two: if the model's centre of mass is not over its footprint (a model
    that rests on a small part of itself and leans out, which stage 1's wider bottom layer
    hid), the cells of stage 1's bottom layer under filled cells are added, the ones nearest
    the centre of mass first (mirror images together), as few as make it stand. If even all
    of them do not, none are added."""
    if filled.shape[2] < 2 or not filled[:, :, 0].any() or _stands(filled):
        return filled
    spare = np.argwhere(stage1[:, :, 0] & ~filled[:, :, 0] & filled[:, :, 1])
    if len(spare) == 0:
        return filled
    total = filled.sum()
    centre = np.array(
        [filled.sum(axis=(1, 2)) @ (np.arange(filled.shape[0]) + 0.5),
         filled.sum(axis=(0, 2)) @ (np.arange(filled.shape[1]) + 0.5)]
    ) / total  # fmt: skip
    distance = np.round(np.linalg.norm(spare + 0.5 - centre, axis=1), 6)
    order = np.lexsort((-coverage[spare[:, 0], spare[:, 1], 0], distance))
    spare, distance = spare[order], distance[order]
    ends = np.r_[np.flatnonzero(distance[1:] != distance[:-1]) + 1, len(spare)]

    def with_first(k: int) -> np.ndarray:
        out = filled.copy()
        out[spare[: ends[k], 0], spare[: ends[k], 1], 0] = True
        return out

    if not _stands(with_first(len(ends) - 1)):
        return filled
    low, high = 0, len(ends) - 1  # the fewest groups that make it stand
    while low < high:
        middle = (low + high) // 2
        if _stands(with_first(middle)):
            high = middle
        else:
            low = middle + 1
    return with_first(low)


def _keepers(
    coverage: np.ndarray,
    sub: np.ndarray,
    occupied: np.ndarray,
    net: np.ndarray,
    area: np.ndarray,
    index: np.ndarray,
    low: np.ndarray,
    rule1: np.ndarray,
    interior: np.ndarray,
    crossed: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    """Rule 2: where the material of the ``low`` cells (surface, under half full) goes.

    The cell behind a low cell is the face-neighbour on the side its material lies (the
    side its surface faces away from): along each axis where the middle of the material is
    at least _SIDE of a cell from the middle of the cell, the neighbour on that side, if
    the material reaches into it across their shared face; of those, the one holding the
    most (a neighbour met over less than half the face only when the material reaches
    less than half way in, or when the cell is the corner of something larger). A low cell
    hands its material on when that neighbour holds more (by over _EVEN); this repeats
    until the material reaches a rule-1 cell (then it is there anyway: nothing is added)
    or a cell holding at least as much as the next one, which is filled. Material in the
    middle of the cell (the model is thin here) stays where it is. Cells the rays found
    nothing in are judged by the net area of their surface (``net``, ``area``: see the
    module notes). Returns the cells filled so, and for each low cell the flat index of
    the cell its material ended in (-1 for the others)."""
    body = coverage.shape
    s = sub.shape[1]
    keep = np.zeros(body, dtype=bool)
    lows = np.flatnonzero(low.ravel())
    if len(lows) == 0:
        return keep, np.full(body, -1, dtype=np.int64)
    cells = np.stack(np.unravel_index(lows, body), axis=1)
    share = sub[index.ravel()[lows]]
    mass = share.sum(axis=(1, 2, 3))
    middle = (np.arange(s) + 0.5) / s - 0.5
    spread = [share.sum(axis=(2, 3)), share.sum(axis=(1, 3)), share.sum(axis=(1, 2))]
    offset = np.stack([sp @ middle for sp in spread], axis=1) / np.maximum(mass, 1e-12)[:, None]
    flat_cov = coverage.ravel()
    best = np.full(len(lows), -1.0)
    target = lows.copy()
    strides = np.array([body[1] * body[2], body[2], 1])
    ones = np.ones((s, s))
    nothing = np.zeros(0, dtype=np.int64)
    cand_rows, cand_there, cand_axis = [nothing], [nothing], [nothing]
    cand_contact = [np.zeros(0)]
    for axis in range(3):
        side = np.where(offset[:, axis] > 0, 1, -1)
        nb = cells[:, axis] + side
        ok = (mass > _MATERIAL) & (np.abs(offset[:, axis]) >= _SIDE)
        ok &= (nb >= 0) & (nb < body[axis])
        rows = np.flatnonzero(ok)
        if len(rows) == 0:
            continue
        there = lows[rows] + side[rows] * strides[axis]
        up = side[rows] > 0
        mine = np.where(
            up[:, None, None], share[rows].take(s - 1, axis=1 + axis),
            share[rows].take(0, axis=1 + axis),
        )  # fmt: skip
        theirs = np.zeros_like(mine)
        their_index = index.ravel()[there]
        on_surface = their_index >= 0
        if on_surface.any():
            other = sub[their_index[on_surface]]
            theirs[on_surface] = np.where(
                up[on_surface, None, None], other.take(0, axis=1 + axis),
                other.take(s - 1, axis=1 + axis),
            )  # fmt: skip
        theirs[interior.ravel()[there]] = ones
        # the share of the face across which the material meets the neighbour's
        contact = np.minimum(mine, theirs).mean(axis=(1, 2))
        meets = contact > _MATERIAL
        cand_rows.append(rows[meets])
        cand_there.append(there[meets])
        cand_contact.append(contact[meets])
        cand_axis.append(np.full(int(meets.sum()), axis))
    # Over most of the face the material is a skin on the neighbour. Over less (the end of
    # a rod or a fin) it is handed on only when it reaches less than half way into the cell
    # on average, or when the cell is the corner or edge of something larger: neighbours on
    # two axes or more that it meets hold more than it does.
    rows, there, contact, cand_ax = (
        np.concatenate(x) for x in (cand_rows, cand_there, cand_contact, cand_axis)
    )
    fuller = flat_cov[there] > flat_cov[lows[rows]] + _EVEN
    axes_fuller = np.zeros((len(lows), 3), dtype=bool)
    axes_fuller[rows[fuller], cand_ax[fuller]] = True
    corner = axes_fuller.sum(axis=1) >= 2
    shallow = (contact >= 0.5 - _EVEN) | (mass[rows] / s**3 < 0.5 * contact) | corner[rows]
    for axis in range(3):  # in axis order, so that near-ties go the same way on both sides
        pick = shallow & (cand_ax == axis)
        better = pick & (flat_cov[there] > best[rows] + _EVEN)
        best[rows[better]] = flat_cov[there[better]]
        target[rows[better]] = there[better]
    hand_on = best > flat_cov[lows] + _EVEN
    following = np.arange(coverage.size)
    following[lows] = np.where(hand_on, target, lows)
    # A cell where the rays found no material. A sliver of skin (the model reaches only a
    # hair into it, as at the corner of a box: the surface in it faces one way, so its net
    # area is at least half its area) hands its share to the fullest cell behind that
    # surface that holds material, or that a sliver handed its share to before (so a row of
    # slivers along an edge empties into the body, one step at a time). Any other such cell
    # (a sheet with no thickness, a feature thinner than the rays are apart) hands it to the
    # fullest neighbour its surface runs on into when that holds more, and otherwise stays.
    none = np.flatnonzero(mass <= _MATERIAL)
    which = index.ravel()[lows[none]]
    facing, size = net[which], area[which]
    length = np.linalg.norm(facing, axis=1)
    one_sided = ~occupied[which].any(axis=(1, 2, 3)) & (size > 0) & (length >= 0.5 * size)
    others, slivers = none[~one_sided], none[one_sided]
    best_s = np.full(len(lows), -1.0)
    for axis in range(3):
        for side in (-1, 1):
            nb = cells[others, axis] + side
            ok = (nb >= 0) & (nb < body[axis])
            rows, there = others[ok], lows[others[ok]] + side * strides[axis]
            face = there if side < 0 else lows[rows]
            ok = crossed[axis].ravel()[face] & (flat_cov[there] > best_s[rows] + _EVEN)
            best_s[rows[ok]] = flat_cov[there[ok]]
            target[rows[ok]] = there[ok]
    hand = others[best_s[others] > _EVEN]
    following[lows[hand]] = target[hand]
    facing, length = facing[one_sided], length[one_sided]
    behind = np.where(np.abs(facing) >= 0.2 * length[:, None], -np.sign(facing), 0).astype(int)
    holds = flat_cov > _MATERIAL  # rule-1 cells, the inside, and low cells holding some
    waiting = np.arange(len(slivers))
    while len(waiting):
        rows_all = slivers[waiting]
        best_s[rows_all] = -1.0
        for axis in range(3):
            side = behind[waiting, axis]
            nb = cells[rows_all, axis] + side
            ok = np.flatnonzero((side != 0) & (nb >= 0) & (nb < body[axis]))
            there = lows[rows_all[ok]] + side[ok] * strides[axis]
            better = holds[there] & (flat_cov[there] > best_s[rows_all[ok]] + _EVEN)
            ok, there = ok[better], there[better]
            best_s[rows_all[ok]] = flat_cov[there]
            target[rows_all[ok]] = there
        found = best_s[rows_all] > -1.0
        if not found.any():
            break  # the rest have nothing of the model behind them: they stay
        following[lows[rows_all[found]]] = target[rows_all[found]]
        holds[lows[rows_all[found]]] = True
        waiting = waiting[~found]
    while True:  # follow the material to where it stops
        nxt = following[following]
        if np.array_equal(nxt, following):
            break
        following = nxt
    end = following[lows]
    keep.flat[end[~rule1.ravel()[end]]] = True
    went = np.full(body, -1, dtype=np.int64)
    went.flat[lows] = end
    return keep, went


def _join(
    filled: np.ndarray,
    coverage: np.ndarray,
    occupied: np.ndarray,
    index: np.ndarray,
    surface: np.ndarray,
    stage1: np.ndarray,
    crossed: list[np.ndarray],
) -> np.ndarray:
    """Rule 3: rejoin, through cells of stage 1's fill, what the model joins.

    Two face-neighbours of stage 1's fill belong together when a triangle crosses their
    shared face, or when the model in them comes within a cell of each other across it
    (fewer than s - 1 empty sub-layers between; a cell inside is full). Where the filled
    cells of one such group fall into several face-connected pieces, the pieces are joined
    by the cheapest paths through the group's emptied cells, a cell costing 1.5 minus its
    coverage (so short paths through fuller cells win). A group left with no filled cell
    keeps its fullest cell. Where the problem is mirror-symmetric, every cell added comes
    with its mirror images."""
    body = coverage.shape
    s = occupied.shape[1]
    n_cells = coverage.size
    strides = np.array([body[1] * body[2], body[2], 1])
    interior = stage1 & ~surface
    flat_index = index.ravel()
    together = []
    for axis in range(3):
        layers = occupied.any(axis=tuple(d for d in (1, 2, 3) if d != 1 + axis))
        have = layers.any(axis=1)
        top = np.where(have, s - 1 - np.argmax(layers[:, ::-1], axis=1), -1)
        bottom = np.where(have, np.argmax(layers, axis=1), s)
        high = np.full(n_cells, -1)
        low = np.full(n_cells, s)
        high[interior.ravel()] = s - 1
        low[interior.ravel()] = 0
        where = np.flatnonzero(surface.ravel())
        high[where] = top[flat_index[where]]
        low[where] = bottom[flat_index[where]]
        pair = np.zeros(body, dtype=bool)
        sl = [slice(None)] * 3
        sl[axis] = slice(0, body[axis] - 1)
        nxt = [slice(None)] * 3
        nxt[axis] = slice(1, None)
        high_g, low_g = high.reshape(body), low.reshape(body)
        near = (s - 1 - high_g[tuple(sl)]) + low_g[tuple(nxt)] < s - 1
        pair[tuple(sl)] = stage1[tuple(sl)] & stage1[tuple(nxt)] & (crossed[axis][tuple(sl)] | near)
        a = np.flatnonzero(pair.ravel())
        together.append((a, a + strides[axis]))
    perturb = (
        1e-6
        * (
            np.abs(2 * np.arange(body[0]) + 1 - body[0])[:, None, None] / body[0]
            + np.abs(2 * np.arange(body[1]) + 1 - body[1])[None, :, None] / body[1]
        )
        + 1e-7 * np.arange(body[2])[None, None, :] / body[2]
    )  # mirror-symmetric tie-breaker
    cost_cell = (1.5 - coverage + perturb).ravel()

    # where the model is mirror-symmetric, whatever is added on one side is added on the
    # other too (of two equally cheap joins, a mirror image of each other, both are made)
    mirrors = [
        axis
        for axis in (0, 1)
        if np.array_equal(filled, np.flip(filled, axis))
        and np.array_equal(stage1, np.flip(stage1, axis))
        and np.abs(coverage - np.flip(coverage, axis)).max() <= _EVEN
    ]

    def add_cells(cells: np.ndarray) -> None:
        new = np.zeros(n_cells, dtype=bool)
        new[cells] = True
        new = new.reshape(body)
        for axis in mirrors:
            new |= np.flip(new, axis)
        filled[new & stage1] = True

    for _ in range(3):
        labels, n_pieces = ndimage.label(filled, structure=ndimage.generate_binary_structure(3, 1))
        dropped = np.flatnonzero((stage1 & ~filled).ravel())
        node = np.full(n_cells, -1)
        node[filled.ravel()] = labels.ravel()[filled.ravel()] - 1
        node[dropped] = n_pieces + np.arange(len(dropped))
        n_nodes = n_pieces + len(dropped)
        u = np.concatenate([node[a] for a, _ in together])
        v = np.concatenate([node[b] for _, b in together])
        differ = u != v
        u, v = u[differ], v[differ]
        graph = sparse.coo_matrix((np.ones(len(u)), (u, v)), shape=(n_nodes, n_nodes))
        n_groups, group = csgraph.connected_components(graph, directed=False)
        pieces_in = np.bincount(group[:n_pieces], minlength=n_groups)
        lonely = np.flatnonzero(pieces_in == 0)
        if len(lonely):  # a group whose cells were all emptied keeps its fullest cell
            g = group[n_pieces:]
            order = np.lexsort((dropped, -coverage.ravel()[dropped], g))
            first = order[np.r_[True, g[order][1:] != g[order][:-1]]]
            add_cells(dropped[first[np.isin(g[first], lonely)]])
            continue
        if not (pieces_in > 1).any():
            return filled
        busy = (pieces_in > 1)[group]
        keep = busy[u]
        u, v = u[keep], v[keep]
        cost = np.full(n_nodes, 1e-9)
        cost[n_pieces:] = cost_cell[dropped]
        graph = sparse.csr_matrix(
            (np.r_[cost[v], cost[u]], (np.r_[u, v], np.r_[v, u])), shape=(n_nodes, n_nodes)
        )
        sources = np.flatnonzero(busy[:n_pieces])
        dist, pred, src = csgraph.dijkstra(
            graph, indices=sources, return_predecessors=True, min_only=True
        )
        meet = (src[u] >= 0) & (src[v] >= 0) & (src[u] != src[v])
        cu, cv = u[meet], v[meet]
        total = dist[cu] + dist[cv]
        pa, pb = np.minimum(src[cu], src[cv]), np.maximum(src[cu], src[cv])
        pair_key = pa * n_pieces + pb
        order = np.lexsort((total, pair_key))
        first = order[np.r_[True, pair_key[order][1:] != pair_key[order][:-1]]]
        tree = csgraph.minimum_spanning_tree(
            sparse.csr_matrix((total[first], (pa[first], pb[first])), shape=(n_pieces,) * 2)
        ).tocoo()
        chosen_key = tree.row.astype(np.int64) * n_pieces + tree.col
        chosen = first[np.isin(pair_key[first], chosen_key)]
        walk = np.r_[cu[chosen], cv[chosen]]
        add = []
        while len(walk):
            add.append(walk[walk >= n_pieces])
            walk = pred[walk]
            walk = walk[walk >= 0]
        add_cells(dropped[np.concatenate(add) - n_pieces])
    return filled


def _colours(
    nudged: np.ndarray,
    estimate: np.ndarray,
    axes: tuple[int, ...],
    body: tuple[int, int, int],
    code: np.ndarray,
    codes: np.ndarray,
    pairs: np.ndarray,
    filled: np.ndarray,
    dropped: np.ndarray,
    went: np.ndarray,
    default_colour: int,
) -> tuple[np.ndarray, np.ndarray]:
    """The colour of every body cell (EMPTY where not filled), and the skin: the own colour
    of every ``dropped`` cell (EMPTY elsewhere), the colour stage 1 showed there.

    Each surface cell has its own colour: the vote of the surface inside it, weighted by
    area in mm² (what stage 1 showed there). A filled cell that an emptied surface cell
    handed its material to (rule 2) shows that cell's own colour: the colour moves with the
    material, so an emptied skin's colour (a top, a painted eye) stays where it was seen;
    with several, or with surface of its own too, the colour with the most area (each cell
    counts the area of its own colour); a cell with nothing filled above it takes the colour
    of the emptied cell right above it, so a side skin cannot take the colour of a top.
    Any other filled cell takes the surface inside it, else the surface in its emptied
    face-neighbours (area-weighted together), else the most common colour of the whole
    surface (counting surface cells)."""
    n_codes = len(codes)
    n_cells = int(np.prod(body))
    out = np.full(n_cells, EMPTY, dtype=np.int64)
    flat_filled = filled.ravel()
    skin = np.full(n_cells, EMPTY, dtype=np.int64)
    if n_codes == 1:
        out[flat_filled] = codes[0]
        skin[dropped.ravel()] = codes[0]
        return out.reshape(body), skin.reshape(body)
    pair_cell, pair_code = pairs // n_codes, pairs % n_codes
    strides = np.array([body[1] * body[2], body[2], 1])

    # filled cells an emptied surface cell handed its material to show its colour instead
    flat_dropped = dropped.ravel()
    givers = np.flatnonzero(flat_dropped & (went.ravel() >= 0))
    givers = givers[flat_filled[went.ravel()[givers]]]
    receives = np.zeros(n_cells, dtype=bool)
    receives[went.ravel()[givers]] = True

    # every (filled cell, cell whose surface it takes, colour) for the others
    own = flat_filled[pair_cell] & ~receives[pair_cell]
    targets, sources, colour = [pair_cell[own]], [pair_cell[own]], [pair_code[own]]
    has_own = np.zeros(n_cells, dtype=bool)
    has_own[pair_cell[own]] = True
    emptied = flat_dropped[pair_cell]
    d_cell, d_code = pair_cell[emptied], pair_code[emptied]
    d_xyz = np.stack(np.unravel_index(d_cell, body), axis=1)
    for axis in range(3):
        for step in (-1, 1):
            ok = (d_xyz[:, axis] + step >= 0) & (d_xyz[:, axis] + step < body[axis])
            there = d_cell + step * strides[axis]
            ok[ok] &= flat_filled[there[ok]] & ~receives[there[ok]] & ~has_own[there[ok]]
            targets.append(there[ok])
            sources.append(d_cell[ok])
            colour.append(d_code[ok])
    target, source, tcode = (np.concatenate(x) for x in (targets, sources, colour))
    distinct = np.unique(target * n_codes + tcode) // n_codes
    contested = np.zeros(n_cells, dtype=bool)
    contested[distinct[1:][distinct[1:] == distinct[:-1]]] = True
    own_contested = np.zeros(n_cells, dtype=bool)
    own_contested[pair_cell[1:][pair_cell[1:] == pair_cell[:-1]]] = True

    # exact areas where colours compete
    need = own_contested.copy()
    need[source[contested[target]]] = True
    taken = went.ravel()[givers]
    has_surface = np.zeros(n_cells, dtype=bool)
    has_surface[pair_cell] = True
    # a cell given to with nothing filled above it votes with its own surface too (its top)
    open_above = np.ones(n_cells, dtype=bool)
    open_above[:-1] = ~flat_filled[1:]
    open_above[body[2] - 1 :: body[2]] = True
    selves = np.unique(taken[has_surface[taken] & open_above[taken]])
    voters, voted = np.r_[givers, selves], np.r_[taken, selves]
    shared = np.bincount(voted, minlength=n_cells)[voted] > 1  # several voters for one cell
    need[voters[shared]] = True
    area_key = np.zeros(0, dtype=np.int64)
    area_sum = np.zeros(0)
    if need.any():
        flat = _flat_cells(body)
        keys_out, areas_out = [], []
        for batch in _batches(np.arange(len(nudged)), estimate):
            poly, count, owner, cell = _clip_to_cells(
                nudged[batch], axes, select=lambda c: need[flat(c)]
            )
            keys_out.append(flat(cell) * n_codes + code[batch[owner]])
            areas_out.append(_polygon_area_mm(poly, count))
        area_key, inverse = np.unique(np.concatenate(keys_out), return_inverse=True)
        area_sum = np.bincount(inverse.ravel(), np.concatenate(areas_out), len(area_key))

    def area_of(cell: np.ndarray, which: np.ndarray) -> np.ndarray:
        if len(area_key) == 0:
            return np.zeros(len(cell))
        k = cell * n_codes + which
        at = np.minimum(np.searchsorted(area_key, k), len(area_key) - 1)
        return np.where(area_key[at] == k, area_sum[at], 0.0)

    # each surface cell's own colour, for the colour of the inside
    own_colour = np.full(n_cells, -1, dtype=np.int64)
    single = ~own_contested[pair_cell]
    own_colour[pair_cell[single]] = pair_code[single]
    many = ~single
    if many.any():
        win_cell, win_code = _vote(
            pair_cell[many], pair_code[many], area_of(pair_cell[many], pair_code[many]), n_codes
        )
        own_colour[win_cell] = win_code
    surface_cells = np.unique(pair_cell)
    if len(surface_cells):
        inside_colour = _most_common(codes[own_colour[surface_cells]])
    else:
        inside_colour = default_colour

    out[flat_filled] = inside_colour
    if len(givers):
        given = own_colour[voters]
        ok = given >= 0
        weight = np.where(shared, area_of(voters, np.maximum(given, 0)), 1.0)
        win_cell, win_code = _vote(voted[ok], given[ok], weight[ok], n_codes)
        out[win_cell] = codes[win_code]
        # a cell with nothing filled above it shows the colour of its emptied skin above
        given, ok = given[: len(givers)], ok[: len(givers)]
        above = ok & (givers == taken + 1) & (taken % body[2] < body[2] - 1)
        above &= ~flat_filled[np.minimum(taken + 1, n_cells - 1)]
        out[taken[above]] = codes[given[above]]
    plain = ~contested[target]
    out[target[plain]] = codes[tcode[plain]]
    fought = ~plain
    if fought.any() and len(target):
        win_cell, win_code = _vote(
            target[fought], tcode[fought], area_of(source[fought], tcode[fought]), n_codes
        )
        out[win_cell] = codes[win_code]
    skinned = np.flatnonzero(flat_dropped & (own_colour >= 0))
    skin[skinned] = codes[own_colour[skinned]]
    return out.reshape(body), skin.reshape(body)


def _sub_index(index: np.ndarray, cell: np.ndarray, local: np.ndarray, s: int) -> np.ndarray:
    """Flat index into an (n_surface, s, s, s) array of the sub-cell ``local`` of ``cell``."""
    which = index[cell[:, 0], cell[:, 1], cell[:, 2]]
    return ((which * s + local[:, 0]) * s + local[:, 1]) * s + local[:, 2]


def _cast(
    sub_tris: np.ndarray,
    normal: np.ndarray,
    length: np.ndarray,
    flip: np.ndarray,
    axis: int,
    b: int,
    c: int,
    ub: int,
    uc: int,
    ua: int,
    nudge: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Where rays along ``axis`` through sub-cell middles cross the triangles.

    Rays sit at (u + 1/2, v + 1/2) in sub-cell units on axes (b, c), u < ub and v < uc,
    and are numbered u * uc + v. Each triangle is scanned in rows across its shorter side
    (so a long sliver costs no more than its crossings), half-open across the rows and
    then along them, so a ray on an edge two triangles share counts for exactly one of
    them and a closed surface is crossed consistently. Returns, per crossing: the ray, the
    position along the axis (0..ua), the change of winding when moving up the axis (+1
    into a part, -1 out of it, by the winding and ``flip``), and how squarely the triangle
    meets the ray (|n_axis|)."""
    use = np.flatnonzero(normal[:, axis] != 0)
    tri = sub_tris[use]
    span_b = np.ptp(tri[:, :, b], axis=1)
    span_c = np.ptp(tri[:, :, c], axis=1)
    out: list[list[np.ndarray]] = [[], [], [], []]
    for across, along, n_across, n_along, which in (
        (c, b, uc, ub, np.flatnonzero(span_c <= span_b)),
        (b, c, ub, uc, np.flatnonzero(span_c > span_b)),
    ):
        rows, cols, owner = _scan(tri[which], across, along, n_across, n_along)
        t_idx = which[owner]
        n = normal[use[t_idx]]
        p0 = tri[t_idx, 0]
        u, v = (cols, rows) if across == c else (rows, cols)
        position = (
            p0[:, axis]
            - (n[:, b] * (u + 0.5 - p0[:, b]) + n[:, c] * (v + 0.5 - p0[:, c])) / n[:, axis]
        )
        # a crossing is moved _NUDGE of a cell into the solid along the ray, as the triangles
        # are for stage 1, so that a face on a cell boundary lies in the cell behind it
        position -= nudge * np.sign(n[:, axis])
        out[0].append(u * uc + v)
        out[1].append(np.clip(position, 0.0, float(ua)))
        out[2].append(-np.sign(n[:, axis]).astype(np.int64) * flip[use[t_idx]])
        out[3].append(np.abs(n[:, axis]) / length[use[t_idx]])
    ray, pos, step, steep = (np.concatenate(o) for o in out)
    return ray, pos, step, steep


def _scan(
    tri: np.ndarray, across: int, along: int, n_across: int, n_along: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The grid points (r + 1/2, k + 1/2) inside each triangle's projection, scanned in rows
    across axis ``across``: returns the row r, the point k along axis ``along`` and the
    triangle of each. A row runs from the projection's low edge (included) to its high
    edge (left out), and a row through a corner or along an edge is half-open too."""
    cc, bb = tri[:, :, across], tri[:, :, along]
    row_first = np.maximum(np.ceil(cc.min(axis=1) - 0.5), 0).astype(np.int64)
    row_last = np.minimum(np.ceil(cc.max(axis=1) - 0.5) - 1, n_across - 1).astype(np.int64)
    n_rows = np.maximum(row_last - row_first + 1, 0)
    # about the work and output of each triangle: its rows and the points in them
    area = 0.5 * np.abs(
        (bb[:, 1] - bb[:, 0]) * (cc[:, 2] - cc[:, 0])
        - (bb[:, 2] - bb[:, 0]) * (cc[:, 1] - cc[:, 0])
    )
    out: list[list[np.ndarray]] = [[], [], []]
    for part in _batches(np.arange(len(tri)), area + n_rows + 1.0):
        rep = np.repeat(part, n_rows[part])
        if len(rep) == 0:
            continue
        row = (
            row_first[rep]
            + np.arange(len(rep))
            - np.repeat(np.cumsum(n_rows[part]) - n_rows[part], n_rows[part])
        )
        y = row + 0.5
        low = np.full(len(rep), np.inf)
        high = np.full(len(rep), -np.inf)
        for i, k in ((0, 1), (1, 2), (2, 0)):
            ci, ck, bi, bk = cc[rep, i], cc[rep, k], bb[rep, i], bb[rep, k]
            # each edge from its lower end, so two triangles sharing it compute it alike
            swap = (ci > ck) | ((ci == ck) & (bi > bk))
            ci, ck = np.where(swap, ck, ci), np.where(swap, ci, ck)
            bi, bk = np.where(swap, bk, bi), np.where(swap, bi, bk)
            hit = (ci <= y) & (y < ck)
            t = np.divide(y - ci, ck - ci, out=np.zeros(len(rep)), where=hit)
            x = bi + t * (bk - bi)
            low = np.where(hit, np.minimum(low, x), low)
            high = np.where(hit, np.maximum(high, x), high)
        good = np.isfinite(low) & np.isfinite(high)
        first = np.where(good, np.maximum(np.ceil(low - 0.5), 0), 0).astype(np.int64)
        last = np.where(good, np.minimum(np.ceil(high - 0.5) - 1, n_along - 1), -1)
        n_pts = np.maximum(last.astype(np.int64) - first + 1, 0)
        rep2 = np.repeat(np.arange(len(rep)), n_pts)
        out[0].append(row[rep2])
        out[1].append(
            first[rep2] + np.arange(len(rep2)) - np.repeat(np.cumsum(n_pts) - n_pts, n_pts)
        )
        out[2].append(rep[rep2])
    if not out[0]:
        empty = np.zeros(0, dtype=np.int64)
        return empty, empty, empty
    rows, cols, owner = (np.concatenate(o) for o in out)
    return rows, cols, owner


def _prepare(tris: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, ...]]:
    """Get triangles (m, 3, 3), in cell units, ready for ``_clip_to_cells``.

    Returns the indices of the triangles with an area, those triangles nudged into the
    solid, a rough count of the pieces each will make, and the order to cut the axes in."""
    normal = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    length = np.linalg.norm(normal, axis=1)
    keep = np.flatnonzero(length > 0)  # zero-area triangles mark nothing
    unit = normal[keep] / length[keep, None]
    nudged = tris[keep] - _NUDGE * unit[:, None, :]  # into the solid, against the normal

    # a rough count of the pieces each triangle makes: its projected areas plus its spans
    span = nudged.max(axis=1) - nudged.min(axis=1)
    estimate = 0.5 * np.abs(normal[keep]).sum(axis=1) + span.sum(axis=1) + 1.0
    # cut along the axis with the most slabs last: that cut makes the most pieces, and the
    # last cut can be skipped when only the cells are wanted
    axes = tuple(int(i) for i in np.argsort(span.sum(axis=0), kind="stable"))
    return keep, nudged, estimate, axes


def _sloped(
    tris: np.ndarray, body: tuple[int, int, int], open_top: np.ndarray, home: np.ndarray
) -> np.ndarray:
    """Which ``open_top`` cells (bool, shape ``body``) hold a slanted upward surface.

    The upward surface in a skin cell (an emptied surface cell in the stack right above an
    open top; ``home`` gives that top's flat index, -1 elsewhere) counts as the top's own;
    its walls belong to the dropped cell and are left out.

    ``tris`` is (m, 3, 3) in cell units; normals are measured in millimetres. In each cell
    the upward surface (n_z above cos 70 degrees) is summed as area times unit normal, and
    each wall piece (n_z within cos 70 degrees of level) is kept. The cell is sloped when
    the upward surface's mean n_z is below cos 20 degrees and its area is no smaller than
    the walls' area seen from downhill (each wall's area times the positive part of its
    normal along the mean's horizontal direction). Undersides do not count. Returns a bool
    array of shape ``body``."""
    result = np.zeros(body, dtype=bool)
    if not open_top.any():
        return result
    mm = np.asarray(CELL_MM, dtype=np.float64)
    normal_mm = np.cross((tris[:, 1] - tris[:, 0]) * mm, (tris[:, 2] - tris[:, 0]) * mm)
    length = np.linalg.norm(normal_mm, axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        up = normal_mm[:, 2] / length
    counted = np.flatnonzero((length > 0) & (up >= -_STEEP))  # undersides never count
    if not (up[counted] > _STEEP).any():
        return result
    keep, nudged, estimate, axes = _prepare(tris[counted])
    unit = normal_mm[counted[keep]] / length[counted[keep], None]
    is_up = unit[:, 2] > _STEEP
    top_flat = open_top.ravel()
    home_flat = home.ravel()
    skin_flat = home_flat >= 0
    wanted = top_flat | skin_flat
    n_cells = int(np.prod(body))
    flat = _flat_cells(body)

    # per cell: upward area * (n_x, n_y, n_z), upward area; and every wall piece, kept
    total = np.zeros((4, n_cells))
    wall_cell, wall_area, wall_normal = [], [], []
    for batch in _batches(np.arange(len(keep)), estimate):
        poly, count, owner, cell = _clip_to_cells(
            nudged[batch], axes, select=lambda c: wanted[flat(c)]
        )
        if len(owner) == 0:
            continue
        where = flat(cell)
        in_skin = skin_flat[where]
        where = np.where(in_skin, home_flat[where], where)  # a skin's surface is its top's
        area = _polygon_area_mm(poly, count)
        tri = batch[owner]
        up = is_up[tri]
        up_area = np.where(up, area, 0.0)
        for k in range(3):
            total[k] += np.bincount(where, up_area * unit[tri, k], minlength=n_cells)
        total[3] += np.bincount(where, up_area, minlength=n_cells)
        wall = ~up & ~in_skin  # walls of dropped cells are not the top's
        wall_cell.append(where[wall])
        wall_area.append(area[wall])
        wall_normal.append(unit[tri[wall], :2])
    mean_length = np.linalg.norm(total[:3], axis=0)
    some = (total[3] > 0) & (mean_length > 0)
    slanted = some & (total[2] < _FLAT * mean_length)
    if wall_cell and slanted.any():
        # the walls seen from downhill: each wall's area times how squarely it faces the
        # way the upward surface runs down (walls facing across or uphill count nothing)
        downhill = np.zeros((n_cells, 2))
        across = np.linalg.norm(total[:2], axis=0)
        downhill[slanted] = (total[:2, slanted] / across[slanted]).T
        where = np.concatenate(wall_cell)
        facing = (np.concatenate(wall_normal) * downhill[where]).sum(axis=1)
        seen = np.concatenate(wall_area) * np.maximum(facing, 0.0)
        slanted &= total[3] >= np.bincount(where, seen, minlength=n_cells)
    return (slanted & top_flat).reshape(body)


def _batches(items: np.ndarray, estimate: np.ndarray) -> list[np.ndarray]:
    """Split ``items`` into runs whose estimated piece counts add up to about _PIECES."""
    bounds = np.searchsorted(np.cumsum(estimate), np.arange(_PIECES, estimate.sum(), _PIECES))
    return [b for b in np.split(items, np.unique(bounds)) if len(b)]


def _clip_to_cells(
    tris: np.ndarray,
    axes: tuple[int, ...] = (0, 1, 2),
    select: Callable[[np.ndarray], np.ndarray] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Cut triangles (p, 3, 3) into their parts inside each cell (shrunk by _TOUCH).

    Returns the pieces as padded polygons (q, w, 3) with w <= 9, their corner counts (q,),
    the triangle each came from (q,) and its cell (q, 3). The cells are always exact, but
    without ``select`` the pieces are not clipped along the last axis. With ``select``
    (cells (q, 3) -> bool mask), only the selected pieces are returned, fully clipped.
    """
    p = len(tris)
    poly = np.array(tris, dtype=np.float64)
    count = np.full(p, 3, dtype=np.int64)
    owner = np.arange(p)
    cell = np.zeros((p, 3), dtype=np.int64)
    for step_index, axis in enumerate(axes):
        used = np.arange(poly.shape[1])[None, :] < count[:, None]
        coord = poly[:, :, axis]
        low = np.where(used, coord, np.inf).min(axis=1)
        high = np.where(used, coord, -np.inf).max(axis=1)
        first = np.floor(low + _TOUCH).astype(np.int64)
        last = np.ceil(high - _TOUCH).astype(np.int64) - 1  # slabs whose inside it reaches
        n_slabs = np.maximum(last - first + 1, 0)
        rep = np.repeat(np.arange(len(poly)), n_slabs)
        k = first[rep] + np.arange(len(rep)) - np.repeat(np.cumsum(n_slabs) - n_slabs, n_slabs)
        owner, count, cell = owner[rep], count[rep], cell[rep]
        cell[:, axis] = k
        if step_index == len(axes) - 1:
            if select is None:
                return poly[rep], count, owner, cell
            chosen = np.flatnonzero(select(cell))
            rep, k, owner, count, cell = (
                rep[chosen],
                k[chosen],
                owner[chosen],
                count[chosen],
                cell[chosen],
            )
        poly, low, high = poly[rep], low[rep], high[rep]
        for bound, above, cut in (
            (k + _TOUCH, True, low < k + _TOUCH),
            (k + 1.0 - _TOUCH, False, high > k + 1.0 - _TOUCH),
        ):
            rows = np.flatnonzero(cut)
            if len(rows) == 0:
                continue
            clipped, new_count = _clip(poly[rows], count[rows], axis, bound[rows], above=above)
            if clipped.shape[1] > poly.shape[1]:
                poly = np.concatenate([poly, np.zeros((len(poly), 1, 3))], axis=1)
            poly[rows] = clipped
            count[rows] = new_count
        width = int(count.max()) if len(count) else 3
        poly = poly[:, : max(width, 3)]
    return poly, count, owner, cell


def _clip(
    poly: np.ndarray, count: np.ndarray, axis: int, bound: np.ndarray, *, above: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Keep the part of each convex polygon on one side of the plane coord[axis] = bound.

    Returns polygons one corner wider than the input (a cut adds at most one corner)."""
    q, width, _ = poly.shape
    slots = np.arange(width)
    used = slots[None, :] < count[:, None]
    following = np.where(slots[None, :] + 1 < count[:, None], slots[None, :] + 1, 0)
    a = poly
    b = poly[np.arange(q)[:, None], following]
    da = a[:, :, axis] - bound[:, None]
    db = b[:, :, axis] - bound[:, None]
    if not above:
        da, db = -da, -db
    a_in, b_in = da >= 0, db >= 0
    crossing = used & (a_in != b_in)
    t = np.divide(da, da - db, out=np.zeros_like(da), where=crossing)
    meet = a + t[:, :, None] * (b - a)
    meet[:, :, axis] = bound[:, None]
    out = np.stack([a, meet], axis=2).reshape(q, 2 * width, 3)
    ok = np.stack([used & a_in, crossing], axis=2).reshape(q, 2 * width)
    row, col = np.nonzero(ok)
    dest = (np.cumsum(ok, axis=1) - 1)[row, col]
    result = np.zeros((q, width + 1, 3))
    result[row, dest] = out[row, col]
    return result, ok.sum(axis=1)


def _polygon_area_mm(poly: np.ndarray, count: np.ndarray) -> np.ndarray:
    """Area in mm² of each flat convex polygon (padded corners beyond ``count`` ignored)."""
    mm = poly * np.asarray(CELL_MM)
    rel = mm[:, 1:] - mm[:, :1]
    fan = np.cross(rel[:, :-1], rel[:, 1:])  # triangle (0, i, i + 1) for i = 1 .. w - 2
    real = (np.arange(1, poly.shape[1] - 1)[None, :] + 1) < count[:, None]
    return 0.5 * np.linalg.norm((fan * real[:, :, None]).sum(axis=1), axis=1)


def _fill_inside(surface: np.ndarray) -> np.ndarray:
    """Surface plus every empty cell the outside cannot reach through faces (6-connected)."""
    empty = ~surface
    labels, _ = ndimage.label(empty, structure=ndimage.generate_binary_structure(3, 1))
    border = np.concatenate(
        [
            labels[0].ravel(),
            labels[-1].ravel(),
            labels[:, 0].ravel(),
            labels[:, -1].ravel(),
            labels[:, :, 0].ravel(),
            labels[:, :, -1].ravel(),
        ]
    )
    outside_labels = np.unique(border[border > 0])
    outside = np.isin(labels, outside_labels)
    return ~outside


def _hidden_skin(filled: np.ndarray, skin: np.ndarray) -> np.ndarray:
    """The skin cells (bool) that are not outside air, against ``filled`` as it stands.

    Outside air is the empty cells (skin included) that the space beyond the four sides or
    the top of the grid reaches through faces; below z = 0 is the table, not air. A skin
    cell is empty, so it has an outside-air neighbour exactly when it is outside air."""
    labels, _ = ndimage.label(~filled, structure=ndimage.generate_binary_structure(3, 1))
    border = np.concatenate(
        [
            labels[0].ravel(),
            labels[-1].ravel(),
            labels[:, 0].ravel(),
            labels[:, -1].ravel(),
            labels[:, :, -1].ravel(),
        ]
    )
    air = np.isin(labels, np.unique(border[border > 0]))
    return skin & ~air


def _keep_shell(filled: np.ndarray, shell_studs: int) -> np.ndarray:
    """Filled cells with an outside cell within the shell box (beyond the grid is outside)."""
    s = shell_studs
    deep = filled.astype(np.uint8)
    for axis, size in ((0, 2 * s + 1), (1, 2 * s + 1), (2, 6 * s + 1)):
        deep = ndimage.minimum_filter1d(deep, size=size, axis=axis, mode="constant", cval=0)
    return filled & (deep == 0)
