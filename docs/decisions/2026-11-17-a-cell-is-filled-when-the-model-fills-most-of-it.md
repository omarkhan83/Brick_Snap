# A grid cell is filled when the model fills most of it, not whenever the model touches it
- status: accepted
- by: Alec-42, 2026-11-17

Filling every cell the surface touches never loses a thin feature, but it makes everything fat: legs
merge, necks double in width, and the outline matched the model only about 81%. Filling by coverage gives
87%, with a fifth fewer parts. Thin features are kept one cell thick, and the cells the model only partly
covers are remembered so the make-buildable pass can fill one where a model would otherwise come apart or
hang by a thread. The price is more small weak spots (232 against 148 at 16 studs), because thin things
are thin; no section of 40 cells or more hangs on one part at that size. Rejected: staying with the fat
fill, and offering both as a setting (two conversions to keep correct, and the fat one is what the free
tools already do).

## Responses
