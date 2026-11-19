# The AI designer uses Claude Fable 5.2 unless told otherwise
- status: accepted
- by: Alec-42, 2026-11-19

Alec asked to try Fable 5.2. On the same three models, in one five-minute run each, it gave clearly better
designs than the Opus 5.5 runs of a few days earlier: a car with a slanted glass windscreen and round wheel
hubs, a duck with round eyes on the sides of its head. So it is now the model the designer, the studio and
the judge use when none is named (`DEFAULT_MODEL` in `bricksnap/designer/runner.py`). It uses more of a
Claude subscription per run than Opus does; `--model claude-opus-5-5` on the command line chooses the
cheaper one. The comparison is in `docs/research/2026-11-19-ai-as-the-builder/README.md`.

## Responses
