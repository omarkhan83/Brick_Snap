# An experimental second kind of model: built by the AI from parts, and checked
- status: accepted
- by: Alec-42, 2026-11-19

Alec asked to see what the AI can do when it builds with every kind of part, and to be able to try it.
So the web app and the command line (`bricksnap make`) can now make a "free build": the AI builds the
model part by part from the whole LDraw library, placing by connection, and a checker (not the solver)
says whether every part is held, nothing overlaps and it stands. It is marked experimental everywhere,
because the checker cannot yet prove clips, bars, pins and axles, does not judge how strong a joint is,
and does not know which colours a part is made in. It needs LeoCAD on the computer, for pictures and for
its copy of the parts library. Ordinary models are untouched: there the AI still never places a part.

Whether this becomes the main line of work is a separate, open proposal
(`2026-11-19-the-ai-builds-with-real-parts-and-the-solver-becomes-a-tool.md`).

## Responses
