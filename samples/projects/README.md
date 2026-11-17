# Example projects

Project folders worth keeping, exactly as `bricksnap new` writes them. Unlike `projects/` at the top of the
repository, this folder is kept in git.

| Folder | What it is |
|---|---|
| `pawn/` | `samples/models/pawn.stl` at 16 studs: the plain conversion as stage 1 made it, bricks and plates only |
| `cat-designed/` | `samples/models/cat.glb` at 16 studs after one run of the AI designer: tiles, a brief in `project.json`, a parts list, a BrickLink wanted list, and the instruction booklet (`instructions.pdf`). `renders/compare-rough.png` shows the model, the plain conversion, and the designed build |

To look at one: `uv run bricksnap view samples/projects/pawn`, or open its `build.ldr` in BrickLink Studio,
LeoCAD, or LDView. `renders/compare.png` shows the model on the top row and the brick version below it.

Screenshots and notes from opening these files in other programs (see the task
`docs/tasks/check-ldraw-file-in-studio.md`) go in the same folder as the file that was opened.
