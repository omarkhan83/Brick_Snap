# Curved models use too many small plates
- status: open
- owner: nobody
- stage: 3

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
