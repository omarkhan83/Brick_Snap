# The finishing pass does not finish a second way to second-guess its heavy-section rule
- status: accepted
- by: Alec-42, 2026-11-20

The task "finish both ways and keep the better" was built and measured, and is not merged. Its premise
did not hold: on the pineapple at 40 studs the result without the rule has 16 more slopes but 15 heavy
sections where the input had 13 (the rule keeps 13) and a heavier worst one (125 cells against 121), so
it is the weaker build and is rightly refused; the same at 24 studs (3 against 1) and 48 (20 against 14).
On 900 random lumps the second way was tried 14 times and kept twice, and no sample model changed, while
finishing took about twice as long wherever it was tried (the 3,000-part sphere: 3.2 to 6.4 seconds,
past the contract's 5).

Rejected with it: letting a tie in the count go to the more shaped result. That would trade a promise the
pass makes today (never more heavy sections than its input) for slopes. Whoever wants the slopes back
should look for a way to place them that the rule accepts, not for a way round the rule.

The work is kept for reference on the branch `wip/Alec-42-finishing-better-of-two` (the mechanism, its
tests, and the measurements in its task notes).

## Responses
