# The free-build checker still takes some joints on trust that it could test
- status: open
- owner: nobody
- stage: 4

On 20 November the checker stopped calling official techniques wrong (215 false problems on six
official sets fell to 18; see `docs/research/2026-11-19-how-real-sets-are-built/experiments.md`,
"After the fixes"). The independent review of that change found places where the checker is still
too easy, most of them older than the change. They were left out of it on purpose so that the fix
stayed small. A builder who is told "no problems" for one of these has a model that cannot be built
as drawn, so they matter more the more the AI builder uses clips, bars and wheels.

Done when each item below is either fixed with a test at its limit, or written into the checker's
CONTRACT as a stated limit; and the six official sets still give no more false problems than today.

## Notes
In rough order of how likely a builder is to meet them:

1. **A pair with a named joint skips the real-shape test** (`validate.py`, the `elif joint:` branch
   comes before the test on real shapes). So:
   - a clip plate (4085c) sitting 12 LDU above a handle (2540) and gripping nothing is "joined": the
     handle's length is taken along the primitive's own axis, not the bar's direction;
   - two "Bar Tube with Handle" (23443) placed 2 LDU apart pass although their real shapes share a
     piece 3 LDU thick; a bar tube moved 4 or 8 LDU off its bar is still a joint;
   - a wheel moved one stud off its pin sits through its own tyre and passes; a wheel-and-tyre part
     placed twice 10 LDU apart passes.
   The fix is probably to run the real-shape test on these pairs too, allowing only what the joint
   itself needs to share.
2. **Wheel pins are judged by nearness.** A part with a wheel pin moved a whole stud is missed about
   a third of the time (68 caught of 102 in the reviewer's run; 38 of 102 when moved 4 LDU).
3. **A part moved 1 LDU into its neighbour is not caught** (82 of the reviewer's 3,339 changes, the
   largest single loss of the fix). On 0.5 LDU cells a 1 LDU overlap looks the same as two faces
   touching. Two bricks overlapping sideways by 1.1 or 1.2 LDU also pass. Finer cells only for pairs
   the filled bodies flag would close it.
4. **A bar sunk 2 to 6 LDU into a solid top** is reported, but as "Loose ... There is no part under
   it", not as an overlap; from 12 LDU it is an overlap. The words should say the bar is inside the
   part.
5. **Parts the overlap test cannot see:** 106 of 5,640 indexed parts are nowhere 1.5 LDU thick (ribbed
   hoses, capes, sails, plastic sheets), so they can never raise an overlap. They are still reported
   loose.
6. **A solid that is wrong:** the wall of friction pin 11214 is not filled in its middle section, so
   the pin can read as "a bar in a pin hole".
7. **Studs in pin holes:** a stud 2 LDU short of the hole's face is joined.
8. **Bars judged on a short span:** a short bar's lean can only be measured over the length that is a
   bar, so a short bar off its axis may pass.
9. **What is still falsely reported on the six sets (18):** irregular sockets (5), a T-piece the
   library records no joint for (with the steering wheel on it), five shields, two plant groups
   resting on a handle, and a round plate on a bracket with what stands on it. On the wider 18
   models (226): an axle pin in a domed cylinder whose library shapes share 3 LDU (40433), and a
   rotor under a curved slope and a jumper under a plane's nose that sit half a stud off the grid
   (75892, 60067).
10. **A pin in a pin hole is found only at the pin connector's own point.** In 10349 two long axle
    pins (11214) sit in Technic bricks and that joint is not listed at all; they are held through
    their axle ends.
11. **A bar drawn as a tube** counts as a bar when 6 of 8 points round the axis are solid. No test
    can tell 6 from 1, because the centring rule refuses the same cases first.
12. **Movement:** a declared wheel on an axle is refused ("the checker cannot yet confirm how an axle
    turns: use a module instead"), as are clips, bars, finger hinges and balls. A clip on a bar as a
    proven module is the first one worth adding (see `movement-first-models.md`).

The reviewer's cases and pictures are on the lead's machine under
`~/.cache/bricksnap/research/review-work/` (not in the repository: they include files of official
sets from the community's LDraw collection).

## Done on 20 November 2026: items 1, 2 and 4 (on main)
- **Item 1: done.** A named joint is now measured on the real shapes like any overlap, leaving
  out only the joint's room (`JOINT_ROOM` in `validate.py`: round each hole, clip, hinge or
  ball socket, never round the pin or axle that goes in; round a handle's bar; a tyre's own
  round box). Joints known only by name may share less than 1.5 LDU deep and 1,000 LDU^3. A
  handle's bar is now where its two attachments meet, and a clip must be within 7.5 LDU of it
  (`CLIP_REACH`, calibrated on official sets: up to 7.3). The review's cases: clip 12 LDU above
  a handle, loose (was no problem); two 23443 2 LDU apart, overlap (was joined); a bar tube in
  10349 moved 4 or 8 LDU, overlap (was joined); our-car's wheel (line 97) moved z+20, overlap
  with its tyre and loose (was no problem); 66727c01 twice 10 LDU apart, overlap (was joined).
  Stated limits, in the CONTRACT: the clip's room takes in most of a 1 x 1 clip plate, and the
  clip, bar-handle, wheel-hole and tyre rooms and the 1,000 LDU^3 allowance are upper bounds no
  test pins down.
- **Item 2: done.** A wheel pin joins a wheel only on the line of the wheel's hole (or its round
  box), and in as far as the shorter of pin and hole (half the wheel's width when it has no hole
  primitive) less 1 LDU. A tyre sits on a wheel only on its line; two wheels-with-tyres are not
  a tyre on a wheel. Left: a tyre need only be round the pin's line, so a wheel slid off its pin
  still hangs on its tyre (requiring more changes every free build's and pinned report's joint
  lines). Reviewer's targeted run (900): wheel pin moved 4 caught 38 -> 84 of 102, moved 8
  56 -> 88, moved 20 68 -> 90; hinge moved 4 32 -> 36 of 42; Technic pin moved 4 27 -> 41 of 45;
  bar in a clip moved 4 56 -> 80 of 99. Nothing lost in any class.
- **Item 4: done (words only).** A loose group of up to 3 parts whose real shape is inside
  another says "It is sunk N LDU into line M: it is inside that part, not on it. Fix: move line
  K by (...)". Sunk 0 or 1 LDU keeps "rests on"; 12 LDU is an overlap as before.
- `exp_measures.py` now joins a proven module's parts. The sports car built the designers' way:
  not joined to the ground 80 -> 0; hanging holders 0 -> 27, largest section 18 parts (21%), 2
  sections of 5 or more.
- Unchanged: the six sets 18, the 18 models 226, every free build's report, every pinned report
  except two AI cars whose wheels or bushes are turned across their pins (now told so). The
  study's 2,352 mutations: 2,043 -> 2,085 caught (strict 2,063 -> 2,104); the reviewer's 3,339:
  2,132 -> 2,186 (strict 2,187 -> 2,240); none lost in any class.
- Items 3, 5 to 12: left as they were.

## What the independent review of that work changed (20 November)
The review ran the library's own assembled parts (its 4,612 shortcuts of 2 to 6 parts) and
found what the six sets and free builds had not. Fixed:
- Official wheels with tyres refused (22969ac01/02, 56908c01-03, 30027ac01, 32248, 42716c01,
  51377c01/02): a wheel's line now comes from a hole at least 4 LDU long, else its box, else
  its real shape as a body of revolution (364 of the library's 382 wheels and tyres); with no
  line it is judged by nearness as before. A tyre covers all but 6 LDU of the narrower width;
  a wheel may sit 2 LDU short on its pin (the library's 30187c01 sits 1.5 short).
- `solid.py` built an untransposed empty grid for parts with no triangle facing one axis
  (343, 932, 993): 11 assemblies raised. Fixed at the root, with a test.
- The sunk search: one small loose part at a time, against at most 2 held neighbours, for the
  first 8 such parts, at most 6 real-shape measurements each, no further than 8 LDU; only
  where the older words gave no move, and never with a pin, axle or hole between them. Sunk
  words in the assemblies 281 -> 9 (in 8, e.g. 10677 bat-wing hands, 561c01 battery box
  parts); in the 18 sets 0 (the axle pin in 75892's gear is gone).
- Turntable Type 2 (50163), giant torso arms (37777c01), T-Rex (76409c01): a turntable's room
  is each half's round box; outside any room a joint may share less than 1.5 LDU deep and
  1,000 LDU^3 (the arms share 1 LDU and about 250).
- `tests/test_lab_assemblies.py`: 239 assemblies that name a joint, as a standing guard.
- `exp_measures.py` joins a module's parts to its anchor (sports car: holders 27 -> 23).

## Left, with the reviewer's cases (in `~/.cache/bricksnap/research/review-work/cases/`)
- The tyre gap: a wheel slid off its pin still hangs on its tyre (the tyre need only be round
  the pin's line).
- The small clip plate: the clip room (11.5 LDU) takes in most of a 1 x 1 clip plate.
- `CLIP_REACH` per clip primitive, and a reach for plain bars: a Bar 3L standing 12 LDU beside
  a clip is "joined" (cases H and clipreach).
- A gap rule for joints known only by name: a hinge top lifted 8 LDU, a bar tube 30 degrees off
  its bar, a ball socket 8 LDU off its ball still pass (cases J*).
- Finger hinges: a meshed pair is not seen as a joint, and two plates facing each other pass.
- Rooms and tolerances no test pins down: the axle-hole, hinge, ball-socket, clip, bar-handle,
  wheel-hole, tyre and turntable rooms (the turntable's takes in all of both halves); the
  pin-hole room at 20; the 2 LDU past a room's ends; `_round_axis` 0.6; the bar's ends in
  `_clip_at_bar`; `BODY_ROUND`, `BODY_SIDES`, `BODY_OUT` and `HOLE_SHORT`; and three of the sunk
  rules (not into a loose part, never with a pin, never over a move onto studs), which no
  test of ours yet fails without. Pinned now: the pin-hole room at 8, the
  allowance outside a room (1.5 LDU, 1,000 LDU^3), the half-width hub, `WHEEL_PLAY`,
  `TYRE_PLAY`.
- 18 wheels and tyres with no line at all (knobbly tyres such as 32298, 45982, 69909; spoked
  wheels 100942, 59521, 64711) are judged by nearness.
- The 9 sunk words left in the library's assemblies are for parts rightly inside another that
  the library records no joint for.
- Measured after round 2: six sets 18, 18 models 226; the 15 free builds and all 68 of their
  .ldr files (models and saved attempts) unchanged; the 4,612 assemblies: none raises, none
  gains a problem, none loses a listed joint. Mutations, nothing lost in any class: study
  2,043 -> 2,079 (strict 2,063 -> 2,098), reviewer's 3,339 2,132 -> 2,168 (2,187 -> 2,222),
  targeted 900 573 -> 768. Timings (best of 3, s, base -> branch): Car Base 30278c01 0.005 ->
  0.006, triceratops 30461c01 0.049 -> 0.052 (best of 15), 22969ac01 0.009 -> 0.009,
  from-pictures fable-duck 1.31 -> 1.33, 31072 0.49 -> 0.53, 40379 0.62 -> 0.62, 40441 1.23 -> 1.23.

## Next (claimed 20 November): joints the checker now tests for fit should not read as "cannot confirm"
A plane Alec built on 20 November (206 parts, guide on) stands on three wheels the builder put on
wheel pins itself, and its summary reads "every part is held (203 of them only by joints the checker
cannot confirm)". Since the work above, a wheel on its pin, a tyre on its wheel, an axle in its hole
and a bar in its hollow are each tested for position against the real shapes, as a stud in its socket
is; only grip is untested, and grip is untested for studs too. So the report should tell two things
apart: joints tested for fit (they hold a part the way a stud does) and joints known only by name
(clips by reach, hinge halves, ball joints, the 18 wheels with no line), and count only the second
kind in "held only by joints the checker cannot confirm". The words the builder and the page show
about this ("parts joined by clips, bars, pins and axles are counted as joined without proof") change
with it.

Done on branch `wip/Alec-42-joints-tested-for-fit` (not yet on main):
- Joints tested for fit (severity "fit", listed under HOW IT HOLDS TOGETHER, counted as
  confirmed): a wheel on a wheel pin (in a hole of at least 4 LDU, or on a round box's axis
  with half the width as hub), a tyre on a wheel (both round boxes), an axle drawn as one in a
  hole, a Technic pin in a pin hole (new: on the hole's line, in all but 2 LDU of the shorter
  of pin and hole; a full pin's undrawn half from its box), a bar in a hollow, a stud in a pin
  hole. Everything else is known by name only and stays in NOT CHECKED, reworded. A wheel off
  its pin does not count through its tyre (the tyre's contact with the pin is name only).
- The plane now reads "every part is held, nothing overlaps, and it stands; all 4 joints move
  freely. (1 warning, 3 joints not checked)": its Technic pins qualify; the 3 left are its
  tyres touching their wheel pins.
- Problems unchanged everywhere (six sets 18, 18 models 226, every free build and attempt).
  The builder's instructions, the check tool, the command line and the pages say the same
  claim; the guide-off prompt and tools pins are updated.

Left:
- `HOLE_SHORT` (4 LDU) and the stud's "2 LDU of the hole's reach" are not pinned by a test that
  fails when they loosen (a stud 2.5 LDU out no longer reaches the brick at all, so the stud's
  own reach is what binds); the body-of-revolution constants no longer affect what is tested
  for fit.
- A wheel or tyre whose line comes only from its real shape (32247, 30027a) is accepted but
  known by name only; a full pin through two parts is tested in one of them by its drawn half
  and in the other by its box.
- A proven module's own line ("the joints inside it ... counted as joined") still sits in the
  NOT CHECKED section under the new heading, as before.

## Thin members on clips and bars (branch `wip/Alec-42-thin-members`, 20 November)
Done:
- The 11090 bug: a part's own clip no longer hides the name that makes it a bar tube, a bar
  or a handle; a bar tube's bore (none drawn in the library) is found in its real shape
  (11090 and 23443: 10 LDU deep to a stop), so a bar in it is a bar in a hollow, tested for
  fit; a bar pushed past the stop is an overlap. The Cessna's attempt 3 goes from 2 problems
  (both struts "Loose") to none. Same trap, now handled: 3628 and 4735 (bars with clips of
  their own), 48729 (a bar with a clip, no primitives). 72869 (Bar Tube with Clip Angled 90)
  is still not found: its bore is not on its box's middle line.
- A clip on a bar or handle is tested for fit (`_clip_fit`): the bar through the grip (per
  clip primitive, `CLIP_GRIP`), leaning at most 5 degrees, bar-thick with the clip round it
  2 LDU either side of the grip's middle, not at the bar's end; any angle about the bar.
  A plain bar must be within `CLIP_REACH` of a clip, as a handle is. In the 18 official
  models 69 clip joints and 8 bar-tube joints are fitted; 8 stay known by name only.
- Tests: `tests/test_lab_thin.py` builds a bar strut on 23443, one on 11090, a blade strut,
  a rail, a leg in a clip tile, an aerial, and a clip on a handle at 0, 30, 45, 90 degrees.
Left:
- The 8 official clip joints still known by name only: a 15712 whose bar sits at its end
  (21026); clip6 or clip3 clips on handles or bars whose line cannot be found (40379, 75892:
  25893, 3957b, 27257); a mechanical arm's clip with no primitive that is not round its
  handle (75892: 98313); 11090 on 25893's handle (76897).
- Clip primitives not measured (known by name only): clip2 (4085c, the thick U-clip), clip9,
  clip10, clip14.
- The limits no test pinned are settled: the per-primitive reach in `CLIP_GRIP` and
  `CLIP_TOL` are removed (the grip ring decided every case; the official sets, the 18 models,
  the free builds and the mutation runs are the same without them); `BAR_BOX` is pinned by a
  clip on 6190's bar, the bar tube's wall by 11090's clip end, its depth by 20612's middle.
- A builder tool that puts a clip on a handle at a given angle (the tests' `frame` and
  `handle_middle` do it in a few lines).
- Hinge halves, finger hinges, ball joints and turntables stay known by name only.
