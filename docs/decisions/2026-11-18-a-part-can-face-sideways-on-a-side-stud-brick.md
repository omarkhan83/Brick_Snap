# A small part can face sideways, held by a brick with a stud on its side
- status: accepted
- by: Alec-42, 2026-11-18

Eyes on the front of a head are painted cells today, because every part stands upright. `Placement` and
`Detail` (in `bricksnap/types.py`) gain one field, `face`: "top" as now, or "front", "right", "back",
"left", the picture view in which the part's top is seen straight on. A sideways part is a one-stud detail
(a round tile, a 1 x 1 tile, a round plate) pushed onto the side stud of a 1 x 1 brick directly behind it
(part 87087), which the solver places at exactly that spot. It keeps clear the one column of three cells in
front of that brick. A design or build with no sideways part is saved, and fingerprinted, exactly as before.

Rejected: listing brick and tile as one made-up part (the parts list and the LDraw file would name a part
nobody can buy); a free rotation for every part (nothing else needs it, and the checks reason on a grid);
brackets and headlight bricks, which put the stud at other heights and can come later.

## Responses
