# The viewer shows the rough and the designed build side by side
- status: open
- owner: nobody
- stage: 3

The viewer shows one build. For showing people what BrickSnap does, it should show the plain conversion
(`build.rough.json`) next to the finished build, turning together, with a switch to hide either, and the
designer's brief (`project.json`) beside them. The step slider should keep working on the finished build.

Done when `uv run bricksnap view PROJECT` shows both builds for a project that has both, one for a project
that has only one, and the browser tests cover both cases with screenshots.

## Notes
Lives in `viewer/` and `bricksnap/viewserver.py`. The page already draws every part kind and follows a
project as it is rebuilt.
