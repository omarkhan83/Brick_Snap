# The AI builds the model from real parts, and the solver becomes one of its tools
- status: accepted
- by: Alec-42, 2026-11-19

Proposed by Alec's agent after the experiments in `docs/research/2026-11-19-ai-as-the-builder/README.md`.
Given a parts search, a way to place a part by the stud it sits on, a checker and pictures, Fable 5.2 built
a sunflower, a cat and a car with turning wheels from the whole parts library; the checker passed all
three and BrickLink Studio opens them. Nothing our grid-and-solver pipeline makes looks like them, because
it knows about fifty basic parts and only stacks them. So the main line of work would become: the AI
builds, part by part and by connection, in passes; the software is its workshop (find parts, attach,
fill a volume using today's solver, mirror, check, look); every model is checked before it is shown.
Today's pipeline stays, as the fill tool and as the way to follow a round shape closely.

This would replace two accepted decisions: "the AI edits intent and the solver places parts" (the
guarantee that a model holds moves from the solver to the checker) and "a 3D model is always the starting
point" (the object becomes the reference when there is one; words alone are enough). It also needs the
whole LDraw parts library on the user's computer (147 MB, CC BY), which the engine has avoided so far.

Not rejected, but not chosen as the main line: the six-pass studio on the present grid. A blind judge
preferred it to one designer on two models of three, narrowly, at three times the time.

## Responses
- Alec-42, 2026-11-25: agree. "The final app should be a single prompt bar, you can type or upload images (the 3d model thing is actually not that important or required if AI is going to build it). The idea is that AI builds it high quality." Recorded by his agent; the app side is `2026-11-25-the-app-is-one-prompt-bar-and-the-ai-builds-from-parts.md`.
