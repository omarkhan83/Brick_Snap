# The AI leads: design the model in passes, from the model itself
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

See `docs/decisions/2026-11-19-the-ai-can-lead-and-design-the-model-in-passes.md`. Build the second way of
designing: a run of several AI passes (lay out the main shapes; refine and colour; surface and details; a
critic who has not seen the work; fixes), each with its own instructions and each kept as a version. Give
the passes what they need to do it well: more shapes to build with, a way to copy part of the conversion,
numbers that say where the design differs from the model, and cut-through views so they can see and build
interiors (a car's cabin, a room).

Done when the same three showcase models have been designed both ways with every pass kept as a version,
a blind judge has compared the results, and the web app offers both ways with an honest note of how many
AI runs each takes.

## Notes
2026-11-19, Alec-42's agent: started. Alec asked for this after trying the web app, and for interiors
and more kinds of parts (`docs/tasks/more-kinds-of-parts.md`). Real AI runs are needed to judge it; they
use Alec's Claude subscription, so keep count and report it.

2026-11-19, Alec-42's agent: built and on `main`. `bricksnap design PROJECT --studio` and, in the web app,
"Design it in passes" in the designer's confirmation panel. The first real runs (Fable 5.2 on the cat, the
duck and the car) got every pass through; a whole run took 8 to 14 minutes, and Claude Code reported
about 5 dollars at list prices per model. The AI service answered "overloaded" once for each model at the
start, so a pass is now tried again after a wait. Left: finish those three runs, have the blind judge
compare each with the one-designer result on the same model, and write down what the pictures show.

