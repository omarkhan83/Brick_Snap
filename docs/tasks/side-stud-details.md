# Details on the side of a model: eyes, lights, badges
- status: open
- owner: nobody
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
