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
- 19 November, points 1 to 3 built on `wip/Alec-42-moving` (not yet merged; no AI session run):
  - Joints are comment lines, `0 !BRICKSNAP JOINT <name> SWING|SPIN|WHEEL [min max] AT x y z
    AXIS dx dy dz FIXED lines MOVING lines [MODULE m]`, appended after the parts they name, so
    line numbers keep their meaning and Studio and LeoCAD open the file unchanged
    (`bricksnap/lab/joints.py`).
  - Eight proven modules (`bricksnap/lab/modules.py`): wheels-small (4600 + 4624 + 3641),
    wheels-large (4600 + 6014b + 6015), wheel-large-single (4488 + 6014b + 6015),
    door-hinge-left and door-hinge-right (3831 + 3830), lid-hinge (3937 + 3938), turntable-small
    (3680 + 3679), turntable-large (3403 + 3404). Every number was read from the library
    (primitives, triangles, and the library's own assembled shortcuts such as 3937c01).
  - The movement check (`bricksnap/lab/movement.py`) is part of every check: tied shut, in the
    way (with how far a swing opens), wheels that rub, a model on wheels not resting on them.
    Swings are swept in 5 degree steps with the rough bodies (only new shared volume counts);
    wheels and spins use a solid of revolution from the real triangles, because the rough
    bodies fill a mudguard's curve.
  - Tools: modules, place_module, joint, and look with "open"; a prompt section "When the
    subject moves". The free-build page lists what moves; each run keeps pictures/opened.png
    (the web app does not serve it yet: `webapp._FREE_PICTURE` and its info would need
    "opened" added).
  - Found on the way: a hinge brick's top half standing on studs is tied by them (the door
    must stand on tiles or overhang); a door as long as its opening jams at its far end (its
    inner corner swings past the jamb): leave a stud's gap. Last night's three AI-built cars,
    with their wheels declared, roll and rest on their wheels.
  - Left: point 4 (a real car and a non-vehicle built this way, with Alec's permission);
    recognising undeclared wheels automatically (feasible for wheel-pin plates, see the
    report to the lead); steering, suspension and gears are not attempted.
- 19 November, after an independent review ("not ready": studs invisible, two hinges always
  tied, shallow interference missed, declared joints passing anything, the ground ignored,
  the lid hinge facing two ways): the movement check now works on the parts' real shapes
  with studs (`bricksnap/lab/solid.py`, voxels from the triangles), turns swings in steps no
  point moves more than 0.5 LDU across and stops at the ground, sees every interference
  deeper than 1 LDU, groups hinges on one line holding one panel, accepts a declared joint
  only about its own pin/axle/clip/hinge line, treats what stands on the ground as staying,
  and knows road wheels (level axle), wheels on their side and spares. Tests compare every
  joint-free report word for word with main's (`tests/moving_main_reports.json`; the one
  deliberate change, a turntable's two halves as a "not checked" joint, is pinned) and
  prove each module's seat against the library's shortcut files and connector axes.
  Still open: a joint whose turning line no primitive marks (bars by name, finger hinges
  without primitives) can only come from a module; the turntable base's fourth corner
  socket is missed by the rough body's column grid (see the report of 19 November).
- 19 November, after the second review ("merge after two named fixes"): a declared joint is
  accepted only on a Technic pin or a wheel pin, about the axis the library records (clips,
  bars and handles, finger hinges, ball joints and axles are refused: "the checker cannot
  yet confirm how a clip turns: use a module instead"); touching the ground no longer puts
  a part on the side that stays (an articulated lorry swings its trailer, a gate with a foot
  opens; the ground stops a movement only by being in its way), and the case that rule
  covered, a second hinge on another line whose base stands on the ground, is caught by its
  own test; spins stop at the ground too; a vehicle on one axle may stand on a stand (a
  warning, not a problem); a turntable's joint may be written as a SWING to limit it;
  solid.py states its guarantee per cell size and rebuilds damaged cache entries.
  Left for later (logged by the coordinator as a follow-up): reading clip and finger-hinge
  lines from their round bores, and a clip-and-bar hinge as a proven module; a ball joint;
  a fixed bar through a turntable's centre wrongly "cannot turn"; the first check with a
  large baseplate taking 6 to 12 s and up to 1.3 GB (surface points not cached on disk);
  4595's filled cavity; the turntable base's centre ring still listed as a socket; a second
  hinge of another kind on one panel; point 4 of this task (real AI builds, with Alec's
  permission).
