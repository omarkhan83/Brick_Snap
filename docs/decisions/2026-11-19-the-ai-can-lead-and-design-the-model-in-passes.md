# The AI can lead: it designs the model in passes, and the conversion becomes its reference
- status: accepted
- by: Alec-42, 2026-11-19

Alec tried the web app and found the results not good enough: the conversion copies the shape cell by cell
and the designer only touches it up afterwards. So there is now a second way to design, beside the first.
The AI studies the model and builds the design itself, in passes with one job each: lay out the main
shapes, refine and colour them, choose surface and details, and then a critic who has not seen the work
compares it with the model and says what to fix. The conversion is what the passes measure against, not
what they start from. Each pass is kept as a version, so a person can put any two side by side and go
back. Nothing else changes: the AI still edits only the design, the solver still places every part, and
every result is still checked.

Rejected: letting the AI place parts itself (measured elsewhere to fail without a validator, and it would
give up the guarantee that the model holds together); replacing the first way (it is quicker and cheaper,
and the two can now be compared on the same model).

## Responses
