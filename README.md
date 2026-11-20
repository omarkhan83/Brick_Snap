# BrickSnap

Turn any object or 3D model into a brick set of real LEGO® parts that looks designed and works.

You give it a 3D model. A solver builds it from real, interlocking bricks and plates, then swaps in tiles
and slopes where the surface should be smooth or slanted. An AI acts as art director: it decides what makes
the object recognisable at brick scale, reshapes and recolours the design, and places small detail parts,
while the solver guarantees the result still holds together. Out comes a standard LDraw file you can open in
BrickLink Studio, with building steps, plus a parts list and a BrickLink wanted list.

- [`docs/VISION.md`](docs/VISION.md): what we are building and why
- [`docs/ROADMAP.md`](docs/ROADMAP.md): the order of work and where we are
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md): how it is built
- [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md): a two-minute tour to give someone

LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.

## Run it

You need [uv](https://docs.astral.sh/uv/). Then, in this folder:

```
uv sync                 # once: installs everything
uv run bricksnap serve  # opens BrickSnap in your web browser
```

In the browser: choose a 3D model file and a size, and press "Turn it into bricks". You get the plain
conversion beside the finished build in 3D, the building steps, and downloads (the brick model for
BrickLink Studio, the parts list, a BrickLink wanted list, an instruction booklet). From there you can start
the AI designer and then ask it for changes in your own words. Every change is kept as a version: choose
any two to see side by side, go back to one you liked better, and use "Look inside" to cut the model open.

There is also an experimental second way: "Describe it and let the AI build it". You type what you want
("a small red fire truck"), and the AI builds it part by part from the whole parts library, with a checker
confirming that every part is held. It needs [LeoCAD](https://www.leocad.org/) on the computer. Everything runs on your own computer; only
the AI designer sends anything off it, and the page says what and asks first. It needs
[Claude Code](https://claude.com/claude-code) installed and signed in. Sample models to try are in
`samples/models/`.

The same from the command line:

```
uv run bricksnap new samples/models/pawn.stl --studs 16    # model in, bricks out
uv run bricksnap view pawn                                 # look at it in 3D in your browser
```

`new` makes a folder under `projects/` holding the build (`build.ldr` opens in BrickLink Studio), a picture
comparing the model with the build (`renders/compare.png`), and the check report. If the file is not one
object but several separate pieces laid out side by side (a kit set out for 3D printing), `new` builds
nothing yet: it lists the pieces with their sizes, writes a numbered picture of them, and asks you to choose
with `--piece largest`, `--piece N` or `--piece all`. The web app asks the same question on the page. Other
commands:

| Command | What it does |
|---|---|
| `bricksnap build PROJECT` | Rebuild from the current design and check it |
| `bricksnap check PROJECT` | Check the saved build again and list every weak spot |
| `bricksnap ops PROJECT edits.json --build` | Apply edit operations by hand |
| `bricksnap design PROJECT` | Let the AI designer improve it. The only command that sends anything off your computer |
| `bricksnap design PROJECT "add a red collar"` | Ask the designer for one change to a model it has already designed |
| `bricksnap design PROJECT --studio` | Have the AI design it in passes, from the model itself: plan, outline, refine, surface, a critic, fixes. Up to six AI runs, each kept as a version |
| `bricksnap design PROJECT --best-of 3` | Design it three times and let a second AI, which cannot tell which is which, keep the best |
| `bricksnap render PROJECT` | Write the comparison picture. With `--rough`: your model, the plain conversion, and the finished build |
| `bricksnap view PROJECT` | Open the 3D viewer |
| `bricksnap make "a sitting cat"` | Experimental: the AI builds a model from the whole parts library, part by part, and a checker says whether it holds. `--reference PROJECT` shows it one of your models; `--change PROJECT "..."` asks for a change |
| `bricksnap versions PROJECT` | List the versions kept of a model; with `--restore N`, bring one back |
| `bricksnap serve` | Open the web app: everything above from a page in your browser |
| `bricksnap export PROJECT` | Write the LDraw file, a parts list (`parts.csv`), and a BrickLink wanted list (`wanted_list.xml`) |
| `bricksnap instructions PROJECT` | Write an instruction booklet (`instructions.pdf` and `.html`): the parts, then one page per building step |
| `bricksnap bench` | Build every test model and print the scorecard: how we tell whether a change helped |

## Working on it as a team

Everyone works through an AI coding agent (Claude Code, Codex, Cursor, and so on). Open this folder in your agent and say what you want in plain words. The agent follows [`AGENTS.md`](AGENTS.md), which keeps everybody's work in sync:

- At the start of a session it pulls the latest version and tells you what your teammates changed.
- **Tasks** live in [`docs/tasks/`](docs/tasks): what is open and who is on what. Ask "what's open?" or "add this to the list".
- **Decisions** live in [`docs/decisions/`](docs/decisions). Big changes are written up as a proposal first, and your agent will ask for your opinion on your teammates' proposals.
- When it finishes, it runs the tests and pushes, so nothing sits on only one person's computer.

One-time setup: you need to be a collaborator on the GitHub repository, with git signed in on your computer, and `uv` installed.

## Layout

| Path | What it is |
|---|---|
| `bricksnap/` | The engine: model to grid, layout solver, finishing, checks, exports, pictures, the scorecard, the AI designer's tools |
| `viewer/` | The 3D viewer page |
| `tests/` | Tests. `uv run pytest` runs them |
| `samples/` | Test models (each with its licence), example projects, and the saved scorecard |
| `docs/` | Vision, roadmap, architecture, open tasks, recorded decisions |
| `AGENTS.md`, `CLAUDE.md` | Rules for the AI agents |
| `tools/catalog/` | Scripts that rebuild the parts table from the LDraw library |
| `legacy/` | The original prototype (below) |

## The prototype

`legacy/index.html` is where the project started: a single web page that turns three photos (or a 3D model)
into a kit of custom 3D-printable bricks. Open it by double-clicking; nothing to install. It is kept working
but is no longer developed. Its three-photo mode is a candidate for a future way of making a model to start
from, and its printable-brick generator for an optional printable output.

If a browser blocks something when it is opened as a file, on Windows run
`powershell -ExecutionPolicy Bypass -File legacy\tools\serve.ps1` and go to http://localhost:8765/.

## Credits

Part numbers, shapes, and colours come from the [LDraw](https://www.ldraw.org/) parts library (CC BY 4.0, a
few files CC BY 2.0) and from [Rebrickable](https://rebrickable.com/)'s data; see
[`bricksnap/catalog/SOURCES.md`](bricksnap/catalog/SOURCES.md). Test models are CC0; see
[`samples/models/README.md`](samples/models/README.md).

### Prototype image credits

The prototype's sample photos (in `legacy/sample-photos/`) are from Wikimedia Commons under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Rulers were added on top of them.

- `real-ds4-top-with-ruler.png` and `ds4-original/`: "Sony DualShock 4 wireless controller for PlayStation 4 (black)" by ITEagle Europe - Sebastiaan Broekhoven
- `bottle-black-*` and `bottle-original/steel-bottle.jpg`: "Stainless Steel Water Bottle" by Gannu03
- `bottle-red-*` and `bottle-original/red-grey-bottle.jpg`: "Red and Grey Water Bottle" by Zohasheikh

All other sample images and models were generated by the scripts in `legacy/tools/`.
