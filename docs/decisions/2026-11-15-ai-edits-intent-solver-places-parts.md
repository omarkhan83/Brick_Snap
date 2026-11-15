# The AI edits what the model should look like; only the solver places parts
- status: accepted
- by: Alec-42, 2026-11-15

The AI designer changes a grid of coloured cells with notes (the Design) through declarative edit
operations. Deterministic code turns that into parts (the Build) and checks it. The AI never writes parts
directly. Published results (BrickWright, "Build, Test, Success", BrickNet) show models placing parts by
coordinate fail most of the time, and succeed when a validator stands between them and the result.

Rejected: letting the AI write code against a building library (needs a sandbox on every teammate's
computer and later on the API), and letting it place every part (does not scale past about 100 parts).

## Responses
