# The test suite takes about fourteen minutes; it should take a few
- status: in-progress
- owner: Alec-42 (since 2026-11-17)
- stage: 4

Every agent runs `uv run pytest` before it pushes. Since the coverage fill and the sturdiness work went
in, that takes about fourteen minutes, because several test files each put every sample model through the
whole pipeline at three sizes. Nobody will keep running a suite that slow.

Done when `uv run pytest` passes in under five minutes on the lead's machine with nothing important left
unchecked: the slow, thorough runs (every sample at 12, 16, and 24 studs) move behind a mark,
`uv run pytest -m thorough`, which the lead's agent runs before closing a stage and which `AGENTS.md` names.

## Notes
`uv run pytest --durations=40` lists the slowest tests.
