# Detail parts: let the designer place small parts on free studs
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 2

Add the `place_detail` edit operation and about 20 detail parts to the parts table (round tile, round plate,
cheese slope, dish, grille tile, cone, and similar). A detail may only go on a stud with nothing above it.
This is where most of the "someone designed this" feeling comes from: eyes, noses, buttons, lights.

Done when the designer can put two round-tile eyes on a model's top surface, the build passes its checks,
and the parts appear in the LDraw file and the viewer.

## Notes
The edit operations are specified in `bricksnap/design.py`; the parts are placed by `bricksnap/finish.py`.
Side-facing details (eyes on the side of a head) need a brick with a stud on its side and are stage 3.
