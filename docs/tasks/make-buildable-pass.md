# Make-buildable pass: change the shape as little as possible so it can actually be built
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 2

Parts only hold through studs, vertically. Wide overhangs, sheets one plate thin, and the ceilings of hollow
models can have no connected layout at all. `bricksnap/buildable.py` adjusts the Design before layout:
step hollow tops inwards, thicken thin sheets, add hidden support columns. It must report what it changed.
See "Make buildable" in `docs/ARCHITECTURE.md`.

Done when a hollow box, a mushroom shape (wide cap on a thin stem), and a table shape all build as one
connected piece, and the report lists the cells that were added.

## Notes
The contract is the opening comment of `bricksnap/buildable.py`. Its cheapest repair is recolouring cells
nobody can see, so that a feature in its own colour is held from inside the model.
