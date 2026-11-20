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
