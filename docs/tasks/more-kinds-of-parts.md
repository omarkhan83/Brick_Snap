# More kinds of parts: undersides, curves, round columns, tapers
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

Alec, after trying the web app: "use different blocks rather than the simple ones". The finishing pass
knows tiles, three straight slopes, the cheese slope and one curved slope, and only on top surfaces.
Models would look far less like stacked boxes with, roughly in order of what it buys for the work:

1. **Inverted slopes** under overhangs (a chin, a belly, a bumper, a hull), the mirror image of what the
   pass already does on top. The 2 x 1 inverted slope is in the parts table but never placed; write its
   file as `3665.dat`, the name Studio knows (see the Studio task).
2. **More curved slopes** (2 x 2, 3 x 1, 4 x 1) as a fourth finish, "rounded", for car roofs and animals'
   backs.
3. **Round bricks and plates** (1 x 1 and 2 x 2) where a column is round in the model: legs, necks,
   bottles, towers.
4. **Wedge plates** where the outline tapers seen from above: wings, noses, tails.
5. **Arches** over openings.
6. **Wheels that turn**: a plate with wheel holders, wheels and tyres. This is the first part that reaches
   outside its own cells and below the model, so it needs the solver to keep space clear, as the
   side-stud brick did for details on a face.

Done when at least the first two are placed automatically, the scorecard shows the shaped share rising on
the rounded models with no model weaker, and LeoCAD and Studio draw the results correctly.

## Notes
Each new part needs: its row in the parts table (`bricksnap/catalog/SOURCES.md` says how the table is
made), which way it faces for each turn, where it can go, and what it does to the parts around it. The
finishing pass's contract (the opening comment of `bricksnap/finish.py`) says exactly what a swap may do.

2026-11-19, Alec-42's agent: started with item 1, inverted slopes under overhangs, on the branch
`wip/Alec-42-undersides`. The pictures and the 3D viewer can already draw an inverted slope; what is
missing is the finishing pass placing one and the conversion marking where the model's underside slants.

2026-11-19, Alec-42's agent: item 1 is done. The finishing pass places inverted slopes (2 x 1, 2 x 2 and
the shallow 3 x 1) under overhangs, and the conversion marks where the model's underside slants. On the
eleven samples at 16 studs: 49 inverted slopes on six models (16 on the star, 15 on the duck, 7 on the
teapot), the same 2,416 parts in all, weak spots down from 186 to 180, and the outline match within half
a point. LeoCAD draws them pointing down and outwards on all four sides. Two limits keep it honest: a
swap may add at most one part, and no weak spot may get heavier. Items 2 to 6 are open. Before item 2,
decide how the designer asks for a rounded surface: a fourth finish, or automatically where the model is
curved.

