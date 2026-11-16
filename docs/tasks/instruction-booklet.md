# An instruction booklet made by BrickSnap itself
- status: in-progress
- owner: Alec-42 (since 2026-11-16)
- stage: 4

`uv run bricksnap instructions PROJECT` writes `instructions.html` and `instructions.pdf` into the project:
a cover, the parts needed, then one page per building step with the new parts in full colour and what was
built before drawn pale. The solver already assigns the steps and the renderer already draws any step, so
no other program is needed. BrickLink Studio can also make a booklet from our file (its instruction maker
reads our steps), which stays the route for people who want to design the pages by hand.

Done when the booklet for `samples/projects/cat-designed` can be followed, page by page, by a person who
has not seen the model, and a copy of it is in that sample folder.

## Notes
The contract is the opening comment of `bricksnap/instructions.py`. Following a booklet to the end with
real parts needs a person and the parts; until then, a person reading it page by page against the 3D
viewer's step slider is the check.

2026-11-16, Alec-42's agent: built, reviewed, and on `main`; `uv run bricksnap instructions PROJECT`
writes both files. `samples/projects/cat-designed/instructions.pdf` is the cat's booklet (37 pages, 33
steps; the web-page version is made by the same command). Left before this task is closed: a person
reading it page by page, and ideally building from it.
