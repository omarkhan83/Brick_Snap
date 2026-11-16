# A judge that picks the best of several designs
- status: open
- owner: nobody
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
