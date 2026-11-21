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

Words such as stud, plate, Design, Build, and clean-room runner are explained in the glossary at the end of
`docs/ARCHITECTURE.md`.

## People

| Person | GitHub | Role |
|---|---|---|
| Alec | `Alec-42` | Lead developer. His agent owns the roadmap and the architecture |
| Omar | `omarkhan83` | Owns the GitHub repository; wrote the original prototype |

The first time you work here for someone not in this table, add a row for them (name, GitHub user, what they
like working on) in your first commit. Your user's name for task files is whatever `git config user.name`
prints.

## Every session

**Before any work**

1. If there are uncommitted changes left from an earlier session, tell the user and finish or commit them first.
2. `git checkout main && git pull --rebase`.
3. Read `docs/VISION.md`, `docs/ROADMAP.md`, every file in `docs/decisions/` and `docs/tasks/`, and look at
   the commits the pull brought in.
4. Give the user a short catch-up (a few lines): what teammates changed, which proposals are waiting for
   their opinion, and what is in progress and by whom. Skip it if nothing is new. In a first session on a
   fresh clone, instead say in two sentences what the project is, which stage it is at, and what is open.

**Before you change code**

- Check `docs/tasks/`. If someone else owns a task covering what your user asked for, do not do it. Tell the
  user who has it and offer something else. Prefer tasks from the current stage in `docs/ROADMAP.md`.
- For anything larger than a quick single-spot fix, claim it first: create or update the task file with
  `status: in-progress` and your user as owner, then commit and push just that file. The push is what makes
  the claim visible to everyone else.
- Check the request against `docs/decisions/` and `docs/VISION.md`. If it conflicts with an accepted
  decision, say so and follow "Decisions" below instead of quietly building it.

**While working**

- Change only what the task needs. Stay inside the files your task covers; `docs/ROADMAP.md` groups files
  into "lanes" so that people working side by side do not touch the same ones. Do not reformat, rename,
  reorder, or tidy code you are not changing.
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
- Only the lead's agent changes this file, `docs/VISION.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`, and
  `bricksnap/types.py`. Anyone else proposes the change (see "Decisions"). The one exception is adding
  your user's row to the People table above.

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
  days and nobody has objected, it is accepted: whichever agent notices changes the status line and adds a
  Responses line saying so. The lead's agent may record the lead's own decisions as `accepted` directly.
- **Anyone may object** to any decision, including the lead's, by adding a line under Responses. The lead
  must answer it in writing.
- Never edit the substance of an accepted decision. Write a new one and mark the old one superseded.

## Verifying a change

1. Run all three; all must pass:
   - `uv run pytest` (about six minutes; a proposal to run it in parallel is open)
   - `uv run ruff check`
   - `uv run ty check`
2. If the change affects what a user sees (the viewer page, a picture, an exported file), look at the result
   yourself: the tests drive the viewer in a headless browser and save screenshots in `tests/artifacts/`,
   and `uv run bricksnap render <project>` writes pictures you can open. If you cannot look, ask your user
   to and tell them exactly what they should see.
3. If the change is meant to alter how models come out (the conversion, the solver, the make-buildable or
   finishing pass, the parts table, the designer's prompt or tools), run `uv run bricksnap bench` and tell
   your user what it reports against the saved scorecard, `samples/scorecard.json`. Every model must still
   build with no loose parts. Save a new scorecard (`--save`) in the same commit only when the numbers and
   the pictures show an improvement.
   Also run `uv run pytest -m thorough` (about three minutes): the slow sweeps that the everyday run leaves
   out, such as every sample model at three sizes, long random runs, and speed checks on big models. The
   lead's agent runs them again before closing a stage.
4. A change to documents only needs no checks beyond making sure the files it mentions exist.

## Setup and common snags

- **You need** git (signed in to GitHub, and your user added as a collaborator on the repository by Omar)
  and `uv` (https://docs.astral.sh/uv/). Run `uv sync` once after cloning and after any pull that changes
  `pyproject.toml`. Nothing else has to be installed by hand. For browser tests, run
  `uv run playwright install chromium` once.
- **`git push` is rejected:** someone pushed first. `git pull --rebase`, re-run the checks, push again.
- **`git pull --rebase` stops with a conflict:** resolve it following the merge-conflict rule above. If you
  cannot, run `git rebase --abort` (this loses nothing) and ask your user.
- **Nothing you may work on:** tell your user what is in progress and by whom, and offer the "No code" lane
  in `docs/ROADMAP.md` or adding ideas as `open` tasks.
- **You need a decision from the lead:** write it as a proposal. Decision files are how this team talks
  across schedules; your user can also message Alec directly.

## State of the code

- **The engine** is `bricksnap/`, a Python package: a model file goes in, a checked build of real parts
  comes out. `docs/ARCHITECTURE.md` describes every module; `docs/ROADMAP.md` says which stage we are in.
  `uv run bricksnap --help` lists the commands. Each module starts with a CONTRACT in its opening comment:
  keep the code, its tests, and that text in agreement.
- **The web app** is `uv run bricksnap serve`: BrickSnap in the browser, for people who do not use a
  terminal (upload a model, see it built, start the designer, download the files). When your user asks to
  open or start BrickSnap, run it in the background, give them the address it prints, and stop it when
  they are done. Its pages and the 3D viewer (`uv run bricksnap view <project>`) are in `viewer/`, with
  no build step.
- **The AI design step** (`uv run bricksnap design <project>`, with `--studio` for the design in passes,
  or the designer button in the web app) runs through the user's own Claude Code login and uses their
  subscription. Never start it unless your user asks. The tests that would start it are skipped unless
  asked for by name.
- **Versions.** Every job or command that changes a model keeps its design and build as a numbered
  version (`uv run bricksnap versions <project>`; the strip of versions in the web app). Nothing a user
  made is lost by trying something.
- **Free builds** (experimental) are a second kind of model: `uv run bricksnap make "a sitting cat"`, or
  "Describe it and let the AI build it" in the web app. The AI builds from the whole parts library with
  the tools in `bricksnap/lab/`, and a checker stands in for the solver. Things that should move
  (wheels, doors, lids, a turning head) go in as proven moving modules, and the checker says in words
  whether each can really move. It is an AI run like the design
  step: never start one unless your user asks. It needs LeoCAD in `~/.cache/bricksnap/leocad/`; without it
  the feature says so and the rest works.
- **Research** is in `docs/research/`, one folder per question, with the experiments' own files. Read
  `docs/research/2026-11-19-ai-as-the-builder/README.md` before working on how the AI designs or builds,
  and `docs/research/2026-11-19-how-real-sets-are-built/README.md` (how official sets are built, with a
  draft guide for the AI builder) before changing what the builder is told or how models are structured.
  `docs/research/2026-11-20-what-makes-a-model-look-styled/README.md` is about how a model looks (what
  reads as dated or as designed, measured, with a style guide): read it before judging or changing
  anything that affects a build's appearance. How a build looks is what its owner judges it by.
- **The prototype** is `legacy/index.html`: one page that fills a shape with custom 3D-printed bricks. It
  still opens by double-click. It is not developed further: do not fix or extend it.
- `projects/` holds whatever you build locally and is ignored by git. Examples worth keeping go in
  `samples/projects/`.

Things that must stay true are listed in `docs/ARCHITECTURE.md`. The three that matter most: in an
ordinary model the AI never places parts directly, and every part and colour comes from the parts table
(a free build is the stated exception, and is checked instead); and nothing leaves the user's computer
except through an AI run the user started.
