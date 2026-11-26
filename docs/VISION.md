# Vision

**Turn any object or 3D model into a brick set that looks designed and works.**

Since 25 November the main way is the AI building the set itself from real parts, from words, pictures
or a 3D model as reference, with every model checked; the solver pipeline below is the older way and a
tool. The principles that follow were written for that older way; where they say otherwise, the decision
`docs/decisions/2026-11-19-the-ai-builds-with-real-parts-and-the-solver-becomes-a-tool.md` wins.

*Looks designed* means a person seeing the finished model thinks someone built it on purpose: the right
parts in the right places (slopes, tiles, round parts, a few well-chosen details), a deliberate set of
colours, and the features that make the thing recognisable given room to read. Not a pixelated blob.

*Works* means it holds together when built from real parts, stands up, and, eventually, moves where the
original moves (a car's wheels roll).

## Why this is worth building

Turning a 3D model into stacked bricks already exists and is free. BrickLink Studio has "Import 3D model as
a sculpture"; the Bricker add-on for Blender and the Brick My World phone app do the same. They all produce
a staircase of basic bricks. AI agents that build small models from a text prompt also exist (BrickWright,
BrickGPT).

What nobody has shown is taking an arbitrary model and producing a *designed* set: slopes, tiles, round and
detail parts chosen and placed automatically, with a guarantee that the result holds together. That is the
gap this project goes after.

**The bar:** on the same model, our result must be visibly better than Studio's free import.

## Principles

1. **A 3D model is always the starting point.** We call it the seed. Photos, phone scans, AI image-to-3D,
   CAD, a model from the web, and the prototype's three-photo mode are all just ways to get a seed. The
   core never depends on how the seed was made.
2. **The algorithm guarantees it holds together; the AI decides what it should look like.** A solver turns
   a shape into interlocked real bricks. The AI is the art director: how big, what to emphasise or
   exaggerate, which colours, where slopes, tiles, and details go. It does not place thousands of bricks
   one at a time, because that is where AI models fail and algorithms do not.
3. **Small is where design matters.** At 12 to 16 studs across, a voxelised cat is a blob and a designed
   one reads as a cat. Small sets are also cheap enough to actually buy and build. We prove the idea small
   before going big.
4. **Refinement in passes, always buildable.** Seed, then brief, then rough build, then design passes, then
   the finished set. Every edit is checked and either kept or rejected, so there is a valid set at every
   moment. A person can stop after any pass, or steer in plain words ("bigger ears, add a red collar").
5. **Real parts.** Real part numbers, only colours that exist for that part, and standard LDraw files that
   open in BrickLink Studio for rendering, instructions, and ordering. 3D-printing your own bricks is an
   optional extra, not the main road.
6. **Measured, not guessed.** A fixed set of test models and a scorecard, compared against Studio's import
   of the same model. A change is an improvement when the scorecard and the pictures say so.
7. **Private by default.** Everything runs on the user's computer, including the web app's server. Nothing
   is sent anywhere unless the user starts the AI design step, which sends pictures and a description of
   the model to the AI provider. A hosted copy of the web app, if we run one, receives the models people
   upload to it and says so.
8. **Usable by people who do not program.** The engine working well comes first. On top of it sits a
   command line for now and a web app after, both thin: neither holds any logic of its own.

## The passes

| Pass | Who does it | What comes out |
|---|---|---|
| Seed | The user | A 3D model, a size in studs, and which way is up |
| Brief | AI, with the user | What this is, what matters most, colours, style |
| Rough build | Algorithm | A valid build of plain bricks and plates |
| Design passes | AI and algorithm | Shape tweaks, colours, slopes, tiles, detail parts |
| Finished set | Algorithm | LDraw file with steps, parts list, shopping list, pictures |

## Ladder of ambition

| Level | Means | Examples | Stage |
|---|---|---|---|
| 1 Sculpture | Valid, interlocked bricks and plates | pawn, bottle | 1 |
| 2 Designed | Slopes, tiles, detail parts, chosen colours, emphasised features, chat edits | cat, hat, marker pen, logo | 2 and 3 |
| 3 Engineered | Big models, an internal frame, strength worked out from forces, cost limits | CAD-designed holder, large spaceship | Later |
| 4 Functional | Rolling wheels and hinges, from ready-made sub-assemblies | car | Later |
| 5 Expert | Sideways building, mechanisms, stickers and printed parts | a kit-quality film spaceship | Long term |

Each level builds on the one below. `docs/ROADMAP.md` says which stage is current.

## What this project is not

- **Not a scanner.** Getting the seed (photogrammetry, scanning apps, image-to-3D) is someone else's tool
  for now. Seed makers can be added later without touching the core.
- **Not an AI that places every brick.** See principle 2.
- **Not a shop.** We export a parts list and a BrickLink wanted list. Buying happens on BrickLink or LEGO's
  own site.

## Words and legal

- LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this project.
  Following LEGO's Fair Play policy: write "LEGO® bricks" or "LEGO-compatible", never "LEGOs"; never use
  the LEGO logo; the product is called BrickSnap, with no LEGO in its name or web address. User-facing
  pages carry the disclaimer above.
- Part numbers and shapes come from the LDraw parts library (CC BY 4.0, a few files CC BY 2.0) and must be credited.
- A model of something copyrighted (a film spaceship, a branded car) is the user's own responsibility. We
  do not ship such models as samples.

## Where the claims above come from

- Studio's sculpture import: https://studiohelp.bricklink.com/hc/en-us/articles/6508264220183
- BrickWright and BrickLayer (agents building small models, MIT licence): https://avalovelace1.github.io/brickwright/
- AI needs a validator, raw coordinates fail ("Build, Test, Success"): https://neurips.cc/virtual/2026/166935
- BrickGPT (20x20x20 grid, eight brick types): https://github.com/AvaLovelace1/BrickGPT
- LDraw licence: https://www.ldraw.org/legal-info
- LEGO Fair Play: https://www.lego.com/en-us/legal/notices-and-policies/fair-play/
