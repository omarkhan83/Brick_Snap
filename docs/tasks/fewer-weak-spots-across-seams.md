# The solver should tie big sections together with more than one part
- status: open
- owner: nobody
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
