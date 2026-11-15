# Working on BrickSnap

This file is for the AI coding agent (Claude Code, Codex, Cursor, or any other). Several people work on this
project, each through their own agent, at different times. None of them read the code or manage git themselves.
You are how they stay in sync, so follow this file exactly. Your user may not know these rules exist; apply
them quietly and explain in plain language only when something needs their attention.

## Every session

**Before any work**

1. If there are uncommitted changes left from an earlier session, tell the user and finish or commit them first.
2. `git checkout main && git pull --rebase`.
3. Read every file in `docs/decisions/` and `docs/tasks/`, and look at the commits the pull brought in.
4. Give the user a short catch-up (a few lines): what teammates changed, which proposals are waiting for
   their opinion, and what is in progress and by whom. Skip it if nothing is new.

**Before you change code**

- Check `docs/tasks/`. If someone else owns a task covering what your user asked for, do not do it. Tell the
  user who has it and offer something else.
- For anything larger than a quick single-spot fix, claim it first: create or update the task file with
  `status: in-progress` and your user as owner, then commit and push just that file. The push is what makes
  the claim visible to everyone else.
- Check the request against `docs/decisions/`. If it conflicts with an accepted decision, say so and follow
  "Decisions" below instead of quietly building it.

**While working**

- Change only what the task needs. Do not reformat, rename, reorder, or tidy code you are not changing:
  the lines in this codebase are long, and cosmetic edits turn into merge conflicts for everyone else.
- Match the style of the code around you.
- Commit small, working steps. Say what changed and why in plain English.

**Before you stop**

1. Run the checks in "Verifying a change".
2. In the same commit as the work: delete the task file if the task is finished, or update its Notes with
   what is done and what is left. Add a decision file if you made a choice a teammate might otherwise undo.
3. `git pull --rebase`, re-run the checks if the pull brought anything in, then `git push`.
4. Leave nothing unpushed. Unfinished work that does not break the app goes on `main`. Unfinished work that
   does break it goes on a branch named `wip/<owner>-<task>`, with the branch name written in the task file.

## Rules that are never broken

- `main` always works. Never push something you have not verified.
- Never force-push, rewrite pushed history, or throw away a teammate's commits or changes.
- Merge conflict: keep the intent of both sides. If you cannot tell what the other side intended, stop and
  ask your user rather than guess. Their side is a teammate's decision, not noise.
- Never commit secrets, API keys, or personal files. Look at `git status` before you stage.
- Changes to this file go through a proposal (see below).

## Tasks: `docs/tasks/<short-slug>.md`

One file per task, so two people never edit the same file. The folder holds only work that is not finished;
a done task is deleted, and git history keeps the record.

```markdown
# Short title
- status: open | in-progress
- owner: nobody | <git user.name> (since YYYY-MM-DD)

What is wanted and why, in a few sentences. How we will know it is done.

## Notes
Progress and findings, for whoever picks this up next.
```

When your user has an idea they are not doing now, add it as an `open` task so it is not lost. A claim more
than 7 days old with no related commits is probably abandoned: tell your user, and take it over only if they
say so.

## Decisions: `docs/decisions/YYYY-MM-DD-<short-slug>.md`

One file per decision. Keep them short; they are read at the start of every session.

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
- **Choices that affect everyone** need a proposal first: reversing an accepted decision; adding a dependency,
  build step, server, account, or API key; moving or splitting files; removing or heavily changing a feature
  someone else built; changing this file. Write the decision as `proposed`, push it, and do not build it yet.
- **When you see a proposal** your user has not answered, ask them and add their line under Responses.
- A proposal becomes `accepted` once one other teammate agrees and nobody objects, or after 3 days with no
  objection. If anyone objects, the people talk it over and whoever proposed it records the outcome.
- Never edit the substance of an accepted decision. Write a new one and mark the old one superseded.

## Verifying a change

1. `node tools/check.mjs` must pass. It checks that the app's script still parses and that every local file
   the page refers to exists.
2. If the change affects what a user sees or downloads, exercise it in a browser. Use browser tools if you
   have them. Otherwise ask your user to open `index.html`, then: choose "Upload a 3D model", load
   `sample-models/pawn.stl`, go through Build and Manual, and download the STL; and for photo changes, use
   `sample-photos/1-front.png`, `2-side.png`, `3-top.png`. Tell them exactly what they should see.

There are no automated tests of behaviour yet, so step 2 is the only thing that catches a wrong result.

## The project

BrickSnap turns a real object into a kit of 3D-printable snap-together bricks plus an instruction booklet,
from three photos with a ruler or from an uploaded 3D model. `README.md` has the user-facing description and
a summary of the algorithm.

- `index.html` is the whole app: HTML, CSS, and one inline script, divided by `// ---------- name ----------`
  comments (illustrations, image processing, screens, uploaded 3D model, 3D, instruction book). `build()` is
  the core: voxel grid, colours, hollowing, brick merging, STL export, and the 3D preview.
- `sample-photos/`, `sample-models/`: test inputs. `tools/*.ps1`: Windows PowerShell scripts that generated
  them, plus `serve.ps1`, a local web server. `tools/check.mjs`: the pre-push check.

Things that must stay true (changing any of them needs a proposal):

- The app works when `index.html` is opened by double-click. That means no build step, no npm packages, no
  ES modules, and no `fetch` of local files. Libraries load from `<script>` tags as globals.
- three.js is pinned to r128, the global (non-module) build. Later versions dropped that build, so bumping
  the version is a migration, not a one-line change.
- Photos and models never leave the user's computer. No uploads, analytics, or accounts.
- Units are millimetres. Axes: x is width, y is depth with the front of the object at y = 0, z is up. One
  grid cell is one stud: the stud pitch (8, 12, or 16 mm) wide and 1.2 times that tall.
- Text that reaches the page from a file name, file contents, or an input box goes in with `textContent`,
  never `innerHTML`.
