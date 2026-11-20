# Design around what moves: the mechanics first, the form on top
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

Alec's idea, 19 November: for a model that should move, lay out the mechanics first (on a car: the axles
and the frame, where the doors and the hood hinge) and build the form around that. The mechanics are a
narrow problem that can be made reliable; the form is the art and fits on top.

It extends the project's founding split rather than replacing it: the software guarantees that the model
holds together and that what should move does move; the AI decides what it looks like. It is tried first
in the experimental free builds (`bricksnap/lab/`), where the AI already builds from real parts. It pulls
"functional sub-assemblies" forward from the roadmap's later list as an experiment; the roadmap's order
is unchanged until the experiment shows it works.

Done when:

1. There is a small set of proven moving modules (wheels that turn in two sizes, a hinge for a door, a
   hinge for a hood or a lid, a turntable), each with its parts, how it attaches, what moves, about which
   line and how far.
2. The checker says in plain words whether each moving thing can really move: nothing ties it shut,
   nothing is in its way over its whole swing, and a model on wheels rests on its wheels only.
3. The AI builder has a tool to put a module in by connection, sees the movement verdict in every check,
   can look at the model with something opened, and is told the method: mechanics first, then the body,
   then the skin and details.
4. A car built this way rolls and opens its doors and hood, and is pictured next to the car of 19
   November, which only rolls. The same for one model that is not a vehicle (a head that turns, a lid
   that opens).

## Notes
- Where this stands against what is known (`docs/research/2026-11-19-ai-as-the-builder/README.md`): the
  AI recalls real parts and has design intent; what it gets wrong is exact position, and the checker
  cannot confirm clips, bars, pins or axles, which are exactly the joints of a mechanism. A module that
  is proven once and then reused as a unit avoids having to prove such a joint in general.
- Three levels of difficulty, in order: wheels that roll (the AI did this unaided on 19 November); panels
  that swing open (needs the check that the swing is clear); steering, suspension and gears (tolerances
  and strength matter, and nothing here can check those yet). This task covers the first two.
- Most subjects have nothing that moves. For those the same idea is "fixed points first" (proportions,
  a pose), which the design-in-passes outline pass already tried, with modest gain. Movement can also be
  offered for any subject as a feature: a head that turns, wings that flap.
- The real AI test runs (point 4) spend Alec's Claude subscription: ask him first and report the count.
- The other way in, not part of this task: a converted model of a car getting wheels that turn from the
  solver (`docs/tasks/more-kinds-of-parts.md`, item 6).
