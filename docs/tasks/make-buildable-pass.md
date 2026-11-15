# Make-buildable pass: change the shape as little as possible so it can actually be built
- status: open
- owner: nobody
- stage: 2

Parts only hold through studs, vertically. Wide overhangs, sheets one plate thin, and the ceilings of hollow
models can have no connected layout at all. `bricksnap/buildable.py` adjusts the Design before layout:
step hollow tops inwards, thicken thin sheets, add hidden support columns. It must report what it changed.
See "Make buildable" in `docs/ARCHITECTURE.md`.

Done when a hollow box, a mushroom shape (wide cap on a thin stem), and a table shape all build as one
connected piece, and the report lists the cells that were added.

## Notes
Starts after `stage-1-foundation`.
