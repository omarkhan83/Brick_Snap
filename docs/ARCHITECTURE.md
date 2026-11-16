# Architecture

How BrickSnap is built. Read `docs/VISION.md` first for why. This document describes the target design;
`docs/ROADMAP.md` says how much of it exists yet, so files named here may be planned rather than present.
If the code and this document disagree, that is a bug: the lead's agent fixes whichever is wrong; anyone
else records it as a task.

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
| **Design** | A grid of coloured cells plus notes about finish and details: *what it should look like* | The AI designer and chat edits, through edit operations |
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
  build.json         the parts, their steps, the check report, and notes on what the software changed
  build.rough.json   the plain conversion's build, kept for before-and-after pictures
  build.ldr          the LDraw file
  parts.csv          the parts list (written by `bricksnap export`)
  wanted_list.xml    the same list in BrickLink's upload format
  renders/           pictures
  designer/          transcripts of AI design runs
```

`projects/` is ignored by git (see `.gitignore`). Example projects worth keeping go in `samples/projects/`.

## The Design

- `colors`: integer array `[x, y, z]`. -1 means empty; any other value is an LDraw colour code.
- `finish`: small-integer array, same shape. What the exposed top of a cell should be: 0 studs (default),
  1 smooth (tiles), 2 sloped. The conversion marks cells sloped where the seed's own surface is slanted;
  the designer marks more, or unmarks them. A mark only matters on a cell with nothing above it.
- `details`: a list of small parts standing on free studs (part, colour, cell, rotation), such as round
  tiles for eyes. A detail occupies cells that are empty in `colors`, directly above filled ones.
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

Coordinates are grid cells (x and y in studs, z in plates), and `min` and `max` are inclusive. The
operations so far:

| Operation | What it does |
|---|---|
| `add`, `remove`, `paint` | Fill, empty, or recolour the cells inside a `box` or an `ellipsoid` |
| `set_finish` | Mark the tops of cells `studs`, `smooth`, or `sloped` |
| `place_detail`, `remove_detail` | Stand a small part on free studs, or take it away |
| `"mirror": true` on any of them | Also apply it to the mirror image across the model's left-right middle |

Details never dangle: filling the cell a detail stands in, or emptying the cell beneath it, removes the
detail and says so. Later stages add more shapes (cone, capsule, half-space), selections (by colour,
surface only, connected region, combined with and, or, not), `grow`, `shrink`, `move`, and `name_region`.

Why declarative: there is no model-written code to sandbox, every edit can be validated before it is
applied, and the same tool works unchanged when the AI later runs on the API.

## Deterministic steps

**Voxelise (seed to Design).** Scale the mesh so its longest side is the requested number of studs, stand
it on the ground, and centre it on the stud grid so that a symmetric model comes out symmetric. Mark every
cell the surface passes through, then fill everything the outside cannot reach (this tolerates scans with
small holes). Take colours from the mesh where it has them and snap each to the catalogue colour that looks
closest (the CIEDE2000 colour difference, not distance in RGB); otherwise use one default colour. Mark a
cell's finish as sloped where the seed's upward-facing surface in it is slanted between 20 and 70 degrees.
Optionally hollow the inside, keeping a shell. A model with zero size on any axis is rejected with a clear
message.

**Make buildable (Design to Design).** Parts only hold each other through studs, vertically, and each part
has one colour. So some Designs have no layout in which everything is attached: a feature in its own
colour stuck on the side of the body, a sheet one plate thin, something hanging in the air. This pass uses
the layout solver as its judge: solve, look at what is loose, repair the Design near it, solve again. Its
repairs, cheapest first:

1. Recolour cells nobody can see (every neighbour filled, or facing only an enclosed hollow), so that the
   loose feature's parts can reach into the body and be held from above and below. This changes nothing
   visible, and it is what makes a nose stay on a face.
2. Thicken a thin sheet from beneath, so parts in two levels can overlap.
3. Add a support column under something that hangs, hidden inside a hollow when possible.

It never empties a cell and never changes the colour of a visible one. It works on a copy inside every
rebuild: the saved Design stays exactly what the designer or the person made, and what the pass did is
written in the Build's notes.

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

**Finish (Build to Build).** Swaps plain parts for better-looking ones covering exactly the same cells:
tiles where the finish is smooth; 45-degree slopes where a sloped cell steps down by a brick; cheese slopes
where it steps down by two plates. A slope takes the corner off a step and never adds material. Then the
Design's detail parts are stood on their studs. A swap that would loosen any part of the model is not made,
and a part that does not exist in the cell's colour is never substituted. What could not be done is
written in the Build's notes.

**Checks (Build to report).** No two parts share a cell. Every part is connected to every other, through
studs, in one piece that reaches the ground. The centre of mass sits over the footprint. Weak spots (a
section hanging on one stud, a long unsupported span) are listed in plain words with their coordinates, so
the AI or a person can act on them. Working out forces is a later stage.

**Outputs.** `build.ldr` with steps (opens in BrickLink Studio, LeoCAD, LDView); a parts list; a BrickLink
wanted-list file; pictures.

**The rough build.** The untouched base Design laid out with no passes at all is kept as
`build.rough.json`. It is the "before" in every before-and-after picture and in the scorecard.

**The scorecard.** `bricksnap bench` builds every model in `samples/models/` and prints one row each:
valid or not, loose parts, part count, how much of the upward surface is tiles, slopes, or details rather
than plain studs, and how closely the build's outline matches the seed's from three sides. A change is an
improvement when these numbers and the pictures say so.

## The AI designer

The designer is a language model with five tools and nothing else:

| Tool | Gives or does |
|---|---|
| `describe` | Text: grid size, the brief, the check report, what the software changed by itself, colours and finish marks in use, details placed, and the colours and detail parts available |
| `render` | One picture: straight-on views of the seed and of the current build, drawn at the same scale with stud and plate numbers along the edges |
| `brief` | Records the designer's decisions before it edits: what the object is, what makes it recognisable, what to exaggerate or drop, the palette, the finish. Saved in `project.json` and shown to the person |
| `apply_ops` | Applies a list of edit operations to the Design; returns which were applied or rejected and why. Refuses until a brief exists |
| `rebuild` | Runs make-buildable, layout, finish, and checks; returns the notes and the report |

It works in this order: look, write the brief, edit, rebuild, look again, for a bounded number of rounds.
The same tools serve a person's chat edits.

Prompt and tool definitions live in `bricksnap/designer/` as plain files, defined once.

### Running it clean

The designer must behave as it would through a bare API call: only our prompt, only our tools. For now it
runs through headless Claude Code on the lead's subscription, started from an empty temporary folder by
`bricksnap/designer/runner.py`:

```
claude -p --system-prompt-file <prompt.md>   # replaces Claude Code's whole default prompt
       --tools ""                            # no built-in tools
       --mcp-config <ours.json> --strict-mcp-config   # only our tool server
       --setting-sources "" --disable-slash-commands --no-session-persistence
       --allowedTools mcp__bricksnap --permission-mode dontAsk
       --model <id> --effort <level> --max-turns <n> --output-format stream-json --verbose
```

The runner also removes `ANTHROPIC_API_KEY` and every inherited `CLAUDE*` variable from the child's
environment (so the API key is never spent and nothing leaks in from another Claude Code session), and
sets the variables that switch off auto memory, CLAUDE.md loading, built-in agents, bundled skills, and
non-essential network traffic. `--bare` cannot be used: it turns off subscription login.

What was measured (Claude Code 2.1.325): with these settings the model receives our system prompt, exactly
our tools, no built-in tools, no skills, no agents, and no project or memory files. Four things remain
that no documented setting removes:

- one identity line before our prompt ("You are a Claude agent, built on Anthropic's Claude Agent SDK.");
- one sentence after it asking for independent tool calls to be made together;
- an environment note (working folder, operating system, model name, today's date);
- a reminder holding the account's email address.

Claude Code also lists three built-in plugins in its start-up report; they add no tools and no text the
model sees. None of this concerns the design task, the model has no tool that could act on it, and the
prompt tells it to ignore it. All of it disappears when the same prompt and tools run on the API.

`bricksnap/designer/parity.py` repeats the measurement (`uv run python -m bricksnap.designer.parity`), so we
notice if a Claude Code update changes it. The runner itself stops a run at once if Claude Code reports
that an API key is in use, if our tool server did not start, or if a different model answered than the
one asked for.

Starting the designer is the only thing in BrickSnap that sends data off the computer.

## Parts and colours

`bricksnap/catalog/parts.json` and `colours.json` are a small, checked table: 50 parts and 40
colours, each with its LDraw file, BrickLink ID, footprint, height in plates, where its studs are, and
which colours it really exists in. The solver only uses part and colour pairs from this table. The table
is derived from the LDraw library (CC BY 4.0, a few files CC BY 2.0) and Rebrickable's data; `catalog/SOURCES.md` says how.

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
  bench.py        the scorecard over the test models
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
- `uv run bricksnap <command>`: `new`, `build`, `check`, `render`, `export`, `ops`, `design`, `view`, `bench`.
- The viewer is plain JavaScript modules with three.js copied into `viewer/vendor/`; `bricksnap view`
  serves it with Python's built-in web server. It is tested with headless Chromium through Playwright.

## The prototype

The original app (`legacy/index.html`) still opens by double-click and is not developed further. Its
three-photo mode is the first candidate for a seed maker. Its 3D-printable brick generator is the starting
point for the optional printable output.

## Things that must stay true

- The AI never writes to the Build. Only the solver and finishing pass do.
- The make-buildable pass never empties a cell and never recolours a visible one, and the saved Design is
  only ever changed by edit operations.
- Every part and colour pair in a Build comes from the parts table.
- A Build that fails its checks is never presented as finished; the failure is reported in words.
- Nothing leaves the computer except through the AI design step.
- Text from a file name, file contents, or the AI goes into a web page with `textContent`, never
  `innerHTML`.

## Glossary

| Word | Meaning |
|---|---|
| Stud | The round bump on top of a part. Also the unit of width and depth: one stud is 8 mm |
| Plate | The thin flat part, 3.2 mm tall. Also the unit of height: a brick is three plates tall |
| Brick | The standard tall part: three plates (9.6 mm) |
| Tile | A plate with a smooth top and no studs |
| Slope | A part with a slanted face. A "cheese slope" is the tiny 1x1 wedge, two plates tall |
| Detail part | A small part used for looks: round tile, cone, grille, and so on |
| Seed | The 3D model a project starts from |
| Design | The grid of coloured cells and notes: what the model should look like |
| Build | The list of real parts and positions: how the model is made |
| Layout solver | The code that turns a Design into a Build |
| Loose part | A part that is not connected to the main model through studs |
| LDraw | The standard open file format for LEGO models (`.ldr`), and the community parts library behind it |
| LDU | LDraw's length unit. One stud is 20 LDU; one plate is 8 LDU tall |
| BrickLink Studio | Free design software from BrickLink that opens LDraw files, renders them, and orders parts |
| Wanted list | BrickLink's shopping list, which can be uploaded as a file |
| AI designer | The language model that edits the Design through five tools |
| Brief | The designer's written decisions about a model, made before it edits |
| Finish | What the top of a cell should be: studs, smooth (a tile), or sloped |
| Hidden cell | A filled cell nobody can see once the model is built; its colour is free |
| Rough build | The plain conversion of the seed, before any design work or finishing |
| Scorecard | The table `bricksnap bench` prints: one row of measurements per test model |
| Clean-room runner | The code that starts the AI designer with only our prompt and tools (see "Running it clean") |
| Parity check | The test that shows the AI designer really received only our prompt and tools |
| Headless Chromium | A web browser with no window, driven by a test script to check the viewer page |
