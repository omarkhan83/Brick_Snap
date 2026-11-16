# The solver should tie big sections together with more than one part
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 3

A build can pass every check and still be fragile. In an AI-designed cat, the whole head (92 parts) is
joined to the body through a single 2 x 6 brick, because head and body meet on one vertical plane and the
solver crosses that plane only once. The check report lists such places as weak spots; the scorecard
counts them. The solver should cross a seam between two large regions of the same colour in every second
layer at least, the way a bricklayer staggers joints.

Done when the weak-spot count in `bricksnap bench` falls on the cat, the car, and the knight without any
model gaining loose parts, and no weak spot in those three models has more than 20 parts hanging on one
part. Lives in `bricksnap/layout.py`.

## Notes
The solver already alternates its preferred direction from layer to layer and rewards sitting on several
parts below. What it lacks is any notion of a long seam between regions. `tests/test_layout.py` has an
independent lower bound for piece counts that must keep passing.

2026-11-16, Alec-42's agent: written, now being reviewed. The solver has a sturdiness step after the
model is one piece. Measured at 16 studs before review: in the cat the worst weak spot goes from 107 parts
on one brick to 8; weak spots over the eleven models go from 237 to 214; parts up 1.4%; nothing loose.
Open problem: the finishing pass undoes some of it (the pawn's worst weak spot goes from 11 to 48 parts
after finishing), because a swap is refused only if it loosens something, not if it leaves a section
hanging on one part. The finishing pass needs the same measure the solver now uses.

2026-11-16, later: the solver part is reviewed, fixed, and on `main`. Against the saved scorecard at 16
studs: weak spots 237 to 219, parts 3,570 to 3,621 (+1.4%), nothing loose. Worst weak spot per model
(parts hanging on one part), before to after: cat 107 to 8, knight 12 to 8, spaceship 10 to 6, star 19 to
8, teapot 17 to 12, car 11 to 10; duck 7 to 12 and pawn 11 to 48 got worse.

What is left, and it is the next thing to do: the pawn and the duck get worse in the finishing pass, not
in the solver (the solver's own pawn has a worst weak spot of 6). `bricksnap/finish.py` refuses a swap
only when it loosens something. It should also refuse one that makes the build less sturdy, using
`bricksnap.layout.sturdiness(build, catalog)`. The saved scorecard has not been updated: do that in the
same commit as the finishing fix, once the pawn is no worse than before.

Also open: in 12 of 4,860 head-against-body shapes two neighbouring courses still have no part across the
shared face (the contract says every second layer); none of the twelve has a weak spot.
