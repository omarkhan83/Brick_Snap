# Stage 1 foundation: the Python engine, from a model to a valid real-brick file
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 1

Lay down everything in stage 1 of `docs/ROADMAP.md` in one stretch, so the restructure does not collide with
anyone. Until this task is deleted, nobody else creates files under `bricksnap/`, `viewer/`, or `tests/`.

- Tooling: `uv` project, tests, lint, type check, headless Chromium for viewer tests.
- Prototype moved to `legacy/` (still opens by double-click); `sample-models/` becomes `samples/models/`.
- `bricksnap/types.py` and the project folder format.
- Mesh to plate-resolution Design; parts and colours table; layout solver; checks; LDraw writer; pictures
  without a GPU; edit operations (`add`, `remove`, `paint`); command line.
- The designer skeleton: prompt, four tools, clean-room runner, parity check.
- The viewer page.

Done when (from the roadmap): pawn, box, cylinder, and sphere build with zero loose bricks, solid and
hollow, at three sizes; a flat (zero-height) model is rejected with a message instead of hanging; the AI
makes one visible, valid change to a model through the clean-room runner.

## Notes
The loose-brick cases and the flat-model hang were found in the 2026-11-15 review of the prototype: its
scan-order merge left 840 of 920 bricks unattached on a solid 20x20x20 box, and a zero-height model sent
its voxeliser into an endless loop. The new solver and loader must pass tests for exactly these.
