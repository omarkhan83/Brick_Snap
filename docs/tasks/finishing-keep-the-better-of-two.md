# Finishing: when the heavy-section rule refuses a step, finish both ways and keep the better
- status: open
- owner: nobody
- stage: 4

The finishing pass may not leave more sections of 40 cells or more hanging on one part than the build it
was given. On real models that rule helps (the pineapple at 24 studs: three such sections become one; at
48: 21 become 14; the teapot at 32: two become none), but it can also refuse a step that would have led
somewhere better. The pineapple at 40 studs keeps the same 16 heavy sections with the rule as without it
and loses 16 slopes (shaped share 22% to 17.5%). On 240 random lumps the rule leaves fewer heavy sections
than no rule in 37 to 45 builds, more in 14 to 15, and a heavier worst section in 18.

Done when the pass never ends worse than it would have without the rule: finish both ways when the rule
refuses something, and keep the rule's result unless the other one also has no more heavy sections than
its input and is better (fewer of them, then a lighter worst one). The cost is a second finishing pass,
only on builds where the rule refuses something. The scorecard must not get worse and the pineapple at 40
studs must get its slopes back.

## Notes
From the weak-spots work of 19 November (the contract at the top of `bricksnap/finish.py` states the rule
and how it counts). Also left from that work, smaller:

- The solver's sturdiness step costs up to about four times the solve without it on thin, spiky shapes
  (2.5 times on the samples). What remains of that cost is the whole-build count of weak spots in
  `bricksnap/connect.py`.
- Thin models at 48 to 96 studs now take about twice as long to build as before (the hat at 48: 8 to 18
  seconds) for much sturdier builds. The make-buildable pass is bounded by work (`STURDY_WORK`), with a
  60-second clock only as a safety net; the pineapple at 48 and 64 studs comes within reach of that net
  on a machine about 1.7 times slower than the one it was measured on, and would then say so in a note.
- The pineapple at 96 studs is as weak as it was (its crown hangs on one part): its repairs alone use the
  whole budget.
