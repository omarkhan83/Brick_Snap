# Chat edits: a person types a change and the designer makes it
- status: in-progress
- owner: Alec-42 (since 2026-11-15)
- stage: 3

`uv run bricksnap design PROJECT "add a red collar"` should make that one change and nothing else: keep the
existing brief, leave the rest of the model alone, rebuild, and say what it did. Today the instruction is
passed through, but the designer's prompt is written for a first full pass and tends to redo the model.

Done when three typed edits in a row on the cat (a collar, bigger ears, a different tail) each change only
what was asked, each build is valid, and the edit log shows only the operations for that edit.

## Notes
Lives in `bricksnap/designer/` (the prompt and the runner) and `bricksnap/cli.py`. The tools already work
for this: `apply_ops` only needs a brief to exist, and the brief is kept from the first run. Starting the
designer uses the user's Claude Code subscription; ask before running it.
