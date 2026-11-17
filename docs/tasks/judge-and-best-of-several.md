# A judge that picks the best of several designs
- status: in-progress
- owner: Alec-42 (since 2026-11-16)
- stage: 3

Two runs of the designer on the same model give different results, and some are clearly better. Run the
designer several times on copies of a project, then have a separate clean-context judge (a second model
that sees only the seed picture and the candidates' pictures, not which is which or how they were made)
rank them, and keep the winner. The scorecard's numbers are given to the judge as facts, not as the
verdict.

Done when `uv run bricksnap design PROJECT --best-of 3` keeps the candidate the judge ranks first, the
judge's reasons are saved in the project, and on the cat and the duck a person agrees with its choice.

## Notes
Lives in `bricksnap/designer/`. The judge runs through the same clean-room runner with its own prompt and
no edit tools. Each run uses the user's Claude Code subscription; ask before running it, and say how many
runs a command will start.
The contract is the opening comment of `bricksnap/designer/judge.py`.

2026-11-16, Alec-42's agent: built, reviewed, and on `main`. One real run on the duck at 16 studs
(three designs and one judging, about four minutes): the judge ranked the design with the smooth head and
the thin sloped bill first, the same order the agent that wrote it had chosen from the pictures before
reading the verdict, and its reasons matched the pictures; measurement alone would have picked the
sturdiest design, whose bill is a chunky block. A second judging of the same three gave the same order.
Left before this task is closed: one run on the cat, and a person's opinion on both
(`docs/stages/stage-3/judge-sheet-duck.png` is the sheet the judge saw).
