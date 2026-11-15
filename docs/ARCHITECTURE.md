# Architecture

How BrickSnap is built. Read `docs/VISION.md` first for why. This document describes the target design;
`docs/ROADMAP.md` says how much of it exists yet. If the code and this document disagree, fix whichever is
wrong in the same commit.

## The idea in one picture

```
seed mesh --voxelise--> DESIGN --make buildable--> --layout--> BUILD --finish--> outputs
                          ^                                      |
                          |  apply_ops                           |  describe, render, checks
                          +------- AI designer / chat edits <----+
```

There are three representations. Deterministic code moves between them. The AI only ever edits the middle
one.

| | What it is | Who changes it |
|---|---|---|
| **Seed** | The 3D model, with a chosen size in studs and an up direction | The user |
| **Design** | A grid of coloured cells plus notes about finish and details: *what it should look like* | The AI designer, chat edits, the make-buildable pass |
| **Build** | Real parts at real positions, in steps: *how it is made* | Only the layout solver and finishing pass |

Why the split: AI models are good at "the ears should be bigger and orange" and bad at placing hundreds of
parts by coordinate without collisions. So the AI states intent on a grid, and code that cannot make a
placement mistake turns intent into parts.

## Units and coordinates

- One grid cell is one stud wide, one stud deep, and one **plate** tall: 8 x 8 x 3.2 mm. A brick is three
  cells tall.
- Grid axes: **x** runs left to right, **y** runs front to back (the front of the object is at y = 0),
  **z** runs up from the ground (z = 0 is the bottom layer). x and y count studs; z counts plates.
- Arrays are indexed `[x, y, z]`.
- Mesh files: STL and 3MF are treated as Z-up (x, y, z map straight across). OBJ, GLB, and glTF are treated
  as Y-up with the front facing +Z, so grid x = X, y = -Z, z = Y. The user can override the up axis.
- LDraw output: 1 stud = 20 LDU, 1 plate = 8 LDU, and LDraw's Y axis points down. A grid point (x, y, z)
  maps to LDraw (20x, -8z, 20y), which is a pure rotation, not a mirror. A standard part's LDraw origin is
  the centre of its top face, so a part covering cells x0..x0+w-1, y0..y0+d-1, z0..z0+h-1 is written at
  LDraw (20(x0 + w/2), -8(z0 + h), 20(y0 + d/2)).

## Project folder

Everything about one model lives in one folder, so the command line, the AI's tools, the viewer, and a
person can all look at the same files.

```
projects/<name>/
  project.json       name, seed file, size in studs, up axis, hollow or solid, the brief
  seed.<ext>         a copy of the input model
  design.base.npz    the Design exactly as voxelised from the seed (never edited)
  design.npz         the current Design arrays
  design.json        named regions, detail parts, and the edit log
  build.json         the parts, their steps, and the check report
  build.ldr          the LDraw file
  renders/           pictures
  designer/          transcripts of AI design runs
```

`projects/` is ignored by git. Example projects worth keeping go in `samples/projects/`.

## The Design

- `colors`: integer array `[x, y, z]`. -1 means empty; any other value is an LDraw colour code.
- `finish`: small-integer array, same shape. What the exposed top of a cell should be: 0 studs (default),
  1 smooth (tiles), 2 sloped.
- `details`: a list of small parts sitting on free studs (part, colour, cell, rotation), such as round
  tiles for eyes.
- `regions`: names for areas of the grid ("ear_left"), stored as the shape that defined them.
- `log`: every edit operation applied since the base Design, in order. Replaying the log on
  `design.base.npz` reproduces the current Design. That gives undo, before/after, and a record of what the
  AI did.

### Edit operations

Edits are declarative, not code. One operation is a small JSON object:

```json
{"op": "paint", "shape": {"type": "box", "min": [2, 0, 9], "max": [5, 1, 11]}, "color": 4}
{"op": "add", "shape": {"type": "ellipsoid", "center": [8, 3, 20], "radius": [2, 1, 3]}, "color": 25}
{"op": "remove", "shape": {"type": "box", "min": [0, 0, 0], "max": [1, 7, 2]}}
```

Coordinates are grid cells (x and y in studs, z in plates), and `min` and `max` are inclusive. Stage 1 has
`add`, `remove`, and `paint` with `box` and `ellipsoid`. Later stages add more shapes (cone, capsule,
half-space), a `symmetric` flag, selections (by colour, surface only, connected region, combined with and,
or, not), `grow`, `shrink`, `mirror`, `move`, `set_finish`, `name_region`, and `place_detail`.

Why declarative: there is no model-written code to sandbox, every edit can be validated before it is
applied, and the same tool works unchanged when the AI later runs on the API.

## Deterministic steps

**Voxelise (seed to Design).** Scale the mesh so its longest side is the requested number of studs. Mark
every cell the surface passes through, then fill everything the outside cannot reach (this tolerates
scans with small holes). Take colours from the mesh where it has them and snap each to the nearest colour
in the parts table; otherwise use one default colour. Optionally hollow the inside, keeping a shell. A
model with zero size on any axis is rejected with a clear message.

**Make buildable (Design to Design).** Parts only hold each other through studs, vertically. Cells side by
side in one layer do not hold each other. So some shapes cannot be built as given: wide overhangs, thin
horizontal sheets, the ceiling of a hollow. This pass changes the Design as little as it can to fix that:
steps the tops of hollow spaces inwards, thickens sheets that are one plate thin, and adds hidden support
columns inside. It reports what it changed. It runs after voxelising and after every edit.

**Layout (Design to Build).** The solver chooses parts.
1. Split the height into courses of three plates. Where a cell is filled through a whole course it becomes
   a brick cell; where it is partly filled, its filled plates become plate cells.
2. Tile each layer with parts from the table (1x1 up to 2x8, both directions, one colour per part). Always
   place the most constrained free cell first. Score each candidate part: larger is better, covering
   several different parts in the layer below is much better, an edge directly above an edge below is
   worse, and the preferred direction alternates from layer to layer.
3. Build the connection graph (two parts connect when one sits on the other's studs). While there is more
   than one connected piece, tear up a small window where two pieces touch and re-tile it, rewarding parts
   that join them. If that fails, report it as a weak spot instead of pretending.

**Finish (Build to Build).** Only swaps parts that have nothing on top of them, so it cannot break a
connection: tiles where the finish is smooth, 45-degree slopes where the surface steps down by a brick,
cheese slopes where it steps down by a plate. Detail parts are added on free studs. Each swap is undone if
a check fails.

**Checks (Build to report).** No two parts share a cell. Every part is connected to every other, through
studs, in one piece that reaches the ground. The centre of mass sits over the footprint. Weak spots (a
section hanging on one stud, a long unsupported span) are listed in plain words with their coordinates, so
the AI or a person can act on them. Working out forces is a later stage.

**Outputs.** `build.ldr` with steps (opens in BrickLink Studio, LeoCAD, LDView); a parts list; a BrickLink
wanted-list file; pictures.

## The AI designer

The designer is a language model with four tools and nothing else:

| Tool | Gives or does |
|---|---|
| `describe` | Text: grid size, colours used, part counts, named regions with their bounds, the check report |
| `render` | Pictures: straight-on views (front, right, back, left, top) of the seed and of the current build, drawn at the same scale with stud and layer numbers along the edges |
| `apply_ops` | Applies a list of edit operations to the Design; returns which were applied or rejected and why |
| `rebuild` | Runs make-buildable, layout, finish, and checks; returns the report |

It works in this order: look, write a brief (what this is, what must be recognisable, colours, what to
exaggerate at this size), edit, rebuild, look again, for a bounded number of rounds. The same tools serve
a person's chat edits.

Prompt and tool definitions live in `bricksnap/designer/` as plain files, defined once.

### Running it clean

The designer must behave as it would through a bare API call: only our prompt, only our tools. For now it
runs through headless Claude Code, started from an empty temporary folder:

```
claude -p --system-prompt-file <prompt.md>   # replaces Claude Code's whole default prompt
       --tools ""                            # no built-in tools
       --mcp-config <ours.json> --strict-mcp-config   # only our tool server
       --setting-sources "" --disable-slash-commands --no-session-persistence
       --allowedTools mcp__bricksnap --permission-mode dontAsk
       --model <id> --effort <level> --output-format stream-json
```

`--bare` cannot be used: it turns off subscription login. `bricksnap/designer/parity.py` checks what the
model actually receives (tool list, any text Claude Code adds) and writes it down; anything that cannot be
removed is recorded in a decision. Later the same prompt and tools run on the API with no changes.

Starting the designer is the only thing in BrickSnap that sends data off the computer.

## Parts and colours

`bricksnap/catalog/parts.json` and `colours.json` are a small, hand-checked table: about 40 parts and 30
colours, each with its LDraw file, BrickLink ID, footprint, height in plates, where its studs are, and
which colours it really exists in. The solver only uses part and colour pairs from this table. The table
is derived from the LDraw library (CC BY 2.0) and Rebrickable's data; `catalog/SOURCES.md` says how.

Nothing at run time needs the full LDraw library, a GPU, or a paid licence.

## Code layout

```
bricksnap/
  types.py        Design, Build, Placement, Report: shared data shapes, no logic
  catalog/        parts.json, colours.json, loader, nearest-colour lookup
  seed.py         load a mesh, orient it, scale it
  voxelize.py     mesh to Design
  design.py       apply_ops, the edit log, replay
  buildable.py    make-buildable pass
  layout.py       Design to Build
  finish.py       finishing pass
  checks.py       Build to report
  ldraw.py        Build to LDraw text
  export.py       parts list and BrickLink wanted list
  render.py       pictures of a mesh, a Design, or a Build (plain numpy, no GPU)
  project.py      read and write a project folder
  cli.py          the `bricksnap` command
  designer/       prompt.md, tools.py, mcp_server.py, runner.py, parity.py
viewer/           a build-free web page that shows a project folder in 3D
tests/            unit tests and acceptance tests
samples/          test models (with their licences) and example projects
legacy/           the original single-page prototype, kept working
```

Rules that keep parallel work from colliding:
- Modules talk to each other only through the types in `types.py`. Changing `types.py` affects everyone,
  so it needs a proposal.
- Each module has its own test file. A module's tests do not need another module's internals.

## Tools

- Python 3.12 or newer, managed by `uv`. `uv sync` installs everything.
- `uv run pytest` runs the tests, `uv run ruff check` and `uv run ruff format` lint and format,
  `uv run ty check` checks types.
- `uv run bricksnap <command>`: `new`, `build`, `check`, `render`, `export`, `design`, `view`.
- The viewer is plain JavaScript modules with three.js copied into `viewer/vendor/`; `bricksnap view`
  serves it with Python's built-in web server. It is tested with headless Chromium through Playwright.

## The prototype

The original app (`legacy/index.html`) still opens by double-click and is not developed further. Its
three-photo mode is the first candidate for a seed maker. Its 3D-printable brick generator is the starting
point for the optional printable output.

## Things that must stay true

- The AI never writes to the Build. Only the solver and finishing pass do.
- Every part and colour pair in a Build comes from the parts table.
- A Build that fails its checks is never presented as finished; the failure is reported in words.
- Nothing leaves the computer except through the AI design step.
- Text from a file name, file contents, or the AI goes into a web page with `textContent`, never
  `innerHTML`.
