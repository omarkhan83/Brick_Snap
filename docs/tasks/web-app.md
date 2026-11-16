# A web app: use BrickSnap without a terminal
- status: open
- owner: nobody
- stage: 4

`uv run bricksnap serve` starts a server on your own computer and opens a page where a person can: choose
a model file and a size; watch it become a brick build; see the plain conversion next to the designed
build; start the AI designer and read its brief; type a change ("add a red collar"); and download the
LDraw file, the parts list, and the wanted list. Everything the page does goes through the same pipeline
the command line uses.

Done when a person who has never used a terminal (beyond starting it, or being given a link) turns one of
the sample models into a designed set and downloads its files, with nobody helping.

## Notes
See the decision `docs/decisions/2026-11-15-a-web-app-on-a-server-once-it-works-well.md`.

- The viewer page (`viewer/`) and its server (`bricksnap/viewserver.py`) are the starting point. That
  server only reads files today and uses nothing beyond Python itself; uploads, long-running jobs, and
  progress updates will probably need a small web framework, which is a new dependency and so needs its
  own decision.
- Starting the AI designer sends pictures to the AI provider and, for now, only works on a computer that
  is signed in to Claude Code. The page must say so before it starts a run, as the command line does.
- A model file a person uploads is untrusted: size limits, a fixed set of file types, and never a path
  taken from the browser.
- A hosted copy for the group is a later step (see the roadmap): it needs the designer to run on the API,
  which costs money per run.
