# The two-minute walkthrough

What to show someone who has never seen BrickSnap, in about two minutes, from a fresh copy of this folder.
It uses the saved example models, so nothing in it waits for an AI run except step 5, which is optional.

## Before you start (once)

- `uv sync`, as in the README.
- For step 5 only: Claude Code installed and signed in on this computer.

## Start

`uv run bricksnap serve --examples`, or tell your agent "open BrickSnap with the examples". The browser
opens on "Your brick models" with three cards: a cat, a duck, and a car.

## What to show and say

| | Do | Say |
|---|---|---|
| 1 | Point at the three cards. | "Each of these started as an ordinary 3D model. Each is now a set of real LEGO® parts that holds together: the green label is the software's own check." |
| 2 | Open the cat. Drag to turn both views. | "Left is what a plain converter makes: a stack of bricks. Right is what BrickSnap made of the same model at the same size: cleaner shapes, smooth tiles on top, and a red collar that was added by typing 'add a red collar'." |
| 3 | Point at the designer's brief on the right. | "An AI wrote this plan before it changed anything: what makes a cat recognisable at this size. It decides what the model should look like. It never places a brick; the solver does, and guarantees the result holds." |
| 4 | Pull the step slider back and forward. | "These are the building steps. The same steps are in the instruction booklet." Click "Building instructions" under Download to show it. |
| 5 | Optional, takes a few minutes: type a change, for example "make the tip of the tail white", press "Ask the designer", read the panel, tick the box, start. | "This is the only thing that leaves this computer, and it asks first." Carry on with step 6 while it works; come back to see the change. |
| 6 | Back to "All your models". Choose `samples/models/pineapple.glb`, leave the size at 16 studs, press "Turn it into bricks". | "A new model takes a few seconds." Open it when it says it is ready. |
| 7 | On any model, click "The brick model" and "The BrickLink wanted list" under Download. | "This file opens in BrickLink Studio, the free program LEGO® builders use. This one is a shopping list: upload it on BrickLink and you can order every part." |

## If something goes wrong

- **The page says it cannot reach BrickSnap:** the window where it was started was closed. Start it again;
  the models are still there.
- **Step 5 fails or takes too long:** skip it. All three examples already show a typed change: the cat's
  red collar, the duck's blue bow tie, and the car's white racing stripe (`docs/stages/stage-3.md`).
- **The port is taken:** `uv run bricksnap serve --examples --port 0` picks a free one and prints the address.

## Not in the walkthrough yet

- The same cat from BrickLink Studio's own converter, pictured next to ours
  (`docs/tasks/compare-with-studio-import.md`).
- A model built from real parts on the table.
