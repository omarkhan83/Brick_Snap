# Curved models use too many small plates
- status: in-progress
- owner: Alec-42 (since 2026-11-19)
- stage: 4

The grid is one plate tall per cell, so a rounded surface becomes rings of 1 x 1 and 1 x 2 plates: the
duck is about 550 parts at 16 studs before finishing and 700 after, and more than half of a sphere's parts
are that small. That is expensive to buy and slow to build. Try: rounding a column's height to whole
bricks wherever the difference from the seed is under about a plate and a slope will cover the step
anyway; and letting the finishing pass merge the plates it leaves behind.

Done when the duck at 16 studs is under 450 parts with its outline match in `bricksnap bench` no worse
than two points below today's, and every model still builds with no loose parts.

## Notes
Measure with `uv run bricksnap bench` before and after. The outline match and the part count are both in
the table.

2026-11-17, Alec-42's agent: filling cells by coverage (now on `main`) took the duck at 16 studs from
622 parts to 503 and the eleven samples from 3,615 to 2,809. The target here is the duck under 450. The
two ideas above are still untried.

2026-11-19, Alec-42's agent: started. The scorecard shows where the parts come from: the duck is 398
parts as a plain conversion and 503 finished, so the finishing pass adds about a quarter (it cuts parts
up to fit slopes and leaves the remnants as small plates). The knight (281 to 350), the pawn (190 to 236)
and the teapot (209 to 262) show the same. Work is on the branch `wip/Alec-42-fewer-parts`.

