# What the sturdier builds still cost: time on thin models, and the pineapple at 96 studs
- status: open
- owner: nobody
- stage: 4

Left from the weak-spots work of 19 November, which made builds much sturdier (the contracts at the top
of `bricksnap/layout.py`, `bricksnap/buildable.py` and `bricksnap/finish.py` state the rules). Three
things it did not solve. Done when the first two cost no more than about half of what they do today on
the models named, with the scorecard no worse, and the third is either fixed or shown to be out of reach.

## Notes
- The solver's sturdiness step costs up to about four times the solve without it on thin, spiky shapes
  (2.5 times on the samples). What remains of that cost is the whole-build count of weak spots in
  `bricksnap/connect.py`.
- Thin models at 48 to 96 studs take about twice as long to build as before (the hat at 48: 8 to 18
  seconds) for much sturdier builds. The make-buildable pass is bounded by work (`STURDY_WORK`), with a
  60-second clock only as a safety net; the pineapple at 48 and 64 studs comes within reach of that net
  on a machine about 1.7 times slower than the one it was measured on, and would then say so in a note.
- The pineapple at 96 studs is as weak as it was (its crown hangs on one part): its repairs alone use the
  whole budget.
- 20 November: the idea of finishing a second way without the heavy-section rule and keeping the better
  result was tried and turned down; see the decision of that date. The pineapple at 40 studs does lose
  16 slopes to the rule (shaped share 22% to 17.5%), and gets a sturdier build for it.
- 20 November (found by the seating work, branch `wip/Alec-42-seating`): the finishing pass's own
  sturdiness measure and the independent check in `tests/test_finish.py` (`hanging_on_one_part`)
  disagree on one input. To reproduce: make the pawn at 16 studs in seating (1, 1)
  (`pipeline.create_project(samples/models/pawn.stl, studs=16)` on that branch with
  `pipeline.SEAT_PARTS` set very large, or `load_seed(..., seat=(1, 1))`, voxelize, `make_buildable`),
  then `finish(build, design, catalog)`. The pass's measure (`sturdiness_in_cells`) says lone links go
  from (5 cells, 1) to (0, 0); the independent check finds one plate (a 2 x 4 plate 3020 at x=7, y=11,
  z=3, and three more like it near the head) cutting off 8 cells, a slope 3040b and a cheese slope
  54200 that stand for three input parts, where the input's heaviest weak spot was 5 cells. So
  `test_the_pawn_is_no_less_sturdy_after_finishing` would fail on that build. By the finishing
  CONTRACT's own words the check looks right: "a group holding fewer than 3 input parts is not a lone
  link" counts input parts, but the pass starts from `connect.lone_links`, which already leaves out
  groups of fewer than `MIN_LOAD` (3) *finished* parts, so a group of two finishing parts that stands
  for three input parts is never seen. Not fixed; the seating no longer moves the pawn at 16 studs, so
  no test meets it today.
