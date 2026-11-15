# Working on BrickSnap

This file is for the AI coding agent (Claude Code, Codex, Cursor, or any other). Several people work on this
project, each through their own agent, at different times. None of them read the code or manage git themselves.
You are how they stay in sync, so follow this file exactly. Your user may not know these rules exist; apply
them quietly and explain in plain language only when something needs their attention.

## What we are building

BrickSnap turns any object or 3D model into a LEGO-compatible brick set that looks designed and works.

- `docs/VISION.md`: what and why. Short. Read it once per session.
- `docs/ROADMAP.md`: the order of work and the current stage. Read it before picking work.
- `docs/ARCHITECTURE.md`: how it is built. Read it before changing code.

The lead developer is Alec (GitHub `Alec-42`). His agent owns the roadmap and the architecture.

## Every session

**Before any work**

1. If there are uncommitted changes left from an earlier session, tell the user and finish or commit them first.
2. `git checkout main && git pull --rebase`.
3. Read `docs/VISION.md`, `docs/ROADMAP.md`, every file in `docs/decisions/` and `docs/tasks/`, and look at
   the commits the pull brought in.
4. Give the user a short catch-up (a few lines): what teammates changed, which proposals are waiting for
   their opinion, and what is in progress and by whom. Skip it if nothing is new.

**Before you change code**

- Check `docs/tasks/`. If someone else owns a task covering what your user asked for, do not do it. Tell the
  user who has it and offer something else. Prefer tasks from the current stage in `docs/ROADMAP.md`.
- For anything larger than a quick single-spot fix, claim it first: create or update the task file with
  `status: in-progress` and your user as owner, then commit and push just that file. The push is what makes
  the claim visible to everyone else.
- Check the request against `docs/decisions/` and `docs/VISION.md`. If it conflicts with an accepted
  decision, say so and follow "Decisions" below instead of quietly building it.

**While working**

- Change only what the task needs. Stay inside the files your task or lane covers (lanes are listed in
  `docs/ROADMAP.md`). Do not reformat, rename, reorder, or tidy code you are not changing.
- Match the style of the code around you.
- Commit small, working steps. Say what changed and why in plain English.

**Before you stop**

1. Run the checks in "Verifying a change".
2. In the same commit as the work: delete the task file if the task is finished, or update its Notes with
   what is done and what is left. Add a decision file if you made a choice a teammate might otherwise undo.
3. `git pull --rebase`, re-run the checks if the pull brought anything in, then `git push`.
4. Leave nothing unpushed. Unfinished work that does not break anything goes on `main`. Unfinished work that
   does break something goes on a branch named `wip/<owner>-<task>`, with the branch name written in the
   task file.

## Rules that are never broken

- `main` always works. Never push something you have not verified.
- Never force-push, rewrite pushed history, or throw away a teammate's commits or changes.
- Merge conflict: keep the intent of both sides. If you cannot tell what the other side intended, stop and
  ask your user rather than guess. Their side is a teammate's decision, not noise.
- Never commit secrets, API keys, or personal files. Look at `git status` before you stage.
- Only the lead's agent changes this file, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, and
  `bricksnap/types.py`. Anyone else proposes the change (see "Decisions").

## Tasks: `docs/tasks/<short-slug>.md`

One file per task, so two people never edit the same file. The folder holds only work that is not finished;
a done task is deleted, and git history keeps the record. Tasks have names, not numbers: two people making
"task 12" at the same moment is exactly the collision this avoids. Order comes from the `stage:` line and
the roadmap.

```markdown
# Short title
- status: open | in-progress
- owner: nobody | <git user.name> (since YYYY-MM-DD)
- stage: 1 | 2 | 3 | 4 | later

What is wanted and why, in a few sentences. How we will know it is done.

## Notes
Progress and findings, for whoever picks this up next.
```

When your user has an idea they are not doing now, add it as an `open` task so it is not lost. A claim more
than 7 days old with no related commits is probably abandoned: tell your user, and take it over only if they
say so.

## Decisions: `docs/decisions/YYYY-MM-DD-<short-slug>.md`

One file per decision. Keep them short; they are read at the start of every session. The date in the file
name only keeps them in order.

```markdown
# The decision, as one sentence
- status: proposed | accepted | superseded by <file>
- by: <git user.name>, YYYY-MM-DD

Why, in one to three sentences. What was rejected, if that will save someone re-arguing it.

## Responses
- <git user.name>, YYYY-MM-DD: agree | object, with a reason
```

- **Ordinary choices** (how a feature behaves, a wording, a default): decide with your user, record it as
  `accepted` if a teammate might otherwise undo or re-debate it, and carry on.
- **Choices that affect everyone** need a proposal first: reversing an accepted decision; adding a
  dependency, server, account, or API key; moving files or changing the shared types; removing or heavily
  changing a feature someone else built; changing the roadmap, architecture, or this file. Write the
  decision as `proposed`, push it, and do not build it yet.
- **When you see a proposal** your user has not answered, ask them and add their line under Responses.
- A proposal becomes `accepted` when the lead agrees under Responses. If the lead has not answered after 3
  days and nobody has objected, it is accepted. The lead's agent may record the lead's own decisions as
  `accepted` directly.
- **Anyone may object** to any decision, including the lead's, by adding a line under Responses. The lead
  must answer it in writing.
- Never edit the substance of an accepted decision. Write a new one and mark the old one superseded.

## Verifying a change

1. `node tools/check.mjs` must pass. It checks that the prototype's script still parses and that every
   local file the page refers to exists.
2. If the change affects what a user sees or downloads, exercise it. Use browser tools if you have them;
   otherwise ask your user to try it and tell them exactly what they should see.

This section changes when the Python engine lands (stage 1): the checks become `uv run pytest`,
`uv run ruff check`, and `uv run ty check`.

## State of the code

The project is moving from a prototype to the engine described in `docs/ARCHITECTURE.md`.

- **The prototype** is `index.html`: one page that fills a shape with custom 3D-printed bricks.
  `sample-photos/`, `sample-models/`, and `tools/*.ps1` belong to it. It is being moved to `legacy/` and
  is not developed further. Do not fix or extend it; its known bugs are not being fixed.
- **The engine** (`bricksnap/`, a Python package) is being laid down by the lead's agent as the task
  `stage-1-foundation`. Until that task is finished, do not create files under `bricksnap/`, `viewer/`, or
  `tests/`. Tasks that can be done meanwhile say so.

Things that must stay true are listed at the end of `docs/ARCHITECTURE.md`. The three that matter most:
the AI never places parts directly; every part and colour comes from the parts table; nothing leaves the
user's computer except through the AI design step.
