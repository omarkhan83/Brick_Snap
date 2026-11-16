# Roadmap

The order of work. There are no dates here on purpose: what matters is the sequence. Only the lead
(Alec-42, through his agent) edits this file. Everyone else proposes changes through `docs/decisions/`.

**Current stage: 2**

Pick tasks from the current stage first. A task's `stage:` line says where it belongs.

## Stages

| Stage | Goal | Done when |
|---|---|---|
| 1 | **Model in, valid real-brick file out, and the AI loop alive** | Pawn, box, cylinder, and sphere build with zero loose bricks, solid and hollow, at three sizes. A flat (zero-height) model is rejected with a message. The AI makes one visible, valid change to a model through the clean-room runner |
| 2 | **Looks designed** | A cat 12 to 16 studs long: rough build and designed build side by side, clearly different, both valid |
| 3 | **Steerable and showable** | Three showcase models run from seed to finished set, including a typed edit |
| 4 | **Presentable** | The two-minute walkthrough works from a clean checkout |
| Later | Everything under "After stage 4" | |

### Stage 1: model in, valid real-brick file out, and the AI loop alive

Engine skeleton and tests. Prototype moved to `legacy/`. Mesh to plate-resolution grid. Parts and colours
table. Layout solver with real interlock. Checks. LDraw export. Pictures without a GPU. A bare AI loop
(three edit types, one render) through the clean-room runner, with the parity check. A viewer page.

**Done.** What was shown, with pictures: `docs/stages/stage-1.md`.

### Stage 2: looks designed

Finishing pass (tiles, 45-degree slopes, cheese slopes). Detail parts on free studs. Make-buildable pass.
The design brief. Six test models and the scorecard. Parts list and BrickLink wanted-list export. Only
part and colour pairs that exist.

### Stage 3: steerable and showable

- Chat edits: a person types a change and the designer makes it.
- Side-stud details (eyes, lights) using a brick with a stud on its side.
- Viewer shows rough and designed builds side by side, and steps through the instructions.
- A separate clean-context judge compares candidate designs blind; keep the best of several.
- Choose the showcase models. If a physical model is wanted, order its parts as soon as its design is
  good enough, because parts take time to arrive.

### Stage 4: presentable

- The same models through BrickLink Studio's sculpture import, pictured next to ours.
- Saved example projects in `samples/projects/` so nothing depends on a live run.
- A walkthrough script. Polish: error messages, README, licence and credits, Fair Play wording.

The two-minute walkthrough: the same cat from Studio's import and from BrickSnap, side by side; the AI's
brief and its rounds; one live edit ("add a red collar"); then the wanted list and, ideally, the physical
model.

### After stage 4, in order

1. The AI designer inside the app, on the API, with the same prompt and tools.
2. Strength worked out from forces; internal frames for big models.
3. More part types: curved slopes, wedges, more sideways building.
4. Functional sub-assemblies: wheels on axles, hinges, turntables.
5. Detail sub-assemblies built by an agent with the BrickLayer toolkit and attached to the sculpture.
6. Seed makers: guides for scanning apps, image-to-3D, a logo image to a relief, the prototype's photo mode.
7. Stickers and printed parts. Price estimates. A printable kit of the basic parts.

### Alongside any stage

`licence-and-photo-credits` (a licence for the project, credits for photos and part data) does not depend
on the engine and can be done at any time.

## If something has to be dropped

Drop in this order: a real web app (the command line plus the viewer page is enough); our own instruction
booklet (Studio makes one from our file); the judge and best-of-several; colour taken from textures (the
AI paints instead); printable STL output.

## Lanes

Lanes are groups of files. People can work side by side by staying in different lanes:

| Lane | Files | Kind of work |
|---|---|---|
| Engine | `bricksnap/layout.py`, `buildable.py`, `finish.py`, `checks.py` | Solver, finishing, checks |
| Parts and export | `bricksnap/catalog/`, `ldraw.py`, `export.py` | Parts table, file formats, checking files open in Studio |
| Designer | `bricksnap/designer/`, `design.py` | Prompt, tools, test runs, judging |
| Viewer | `viewer/` | The web page |
| No code | `samples/`, Notes in `docs/tasks/` | Collecting licensed test models, rating results, the walkthrough script, ordering parts |

## How we know a stage is done

`uv run pytest` passes, the stage's "done when" is shown with pictures or output in the commit that closes
it, and the lead's agent updates "Current stage" above.
