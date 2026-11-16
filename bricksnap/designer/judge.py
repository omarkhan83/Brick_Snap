"""Pick the best of several designs of one model, with a judge that cannot tell which is which.

Two runs of the AI designer on the same model give different results, and some are clearly
better. So: design the model several times, have a second, separate model look at the
results side by side without knowing how each was made, and keep the one it ranks first.

CONTRACT (tests go in tests/test_designer_judge.py; no test starts a real AI session)

``design_best_of(project, n, instruction=None, model=..., effort=..., on_event=None) -> BestOf``

Candidates
- ``n`` is 2 to 5. The project folder is copied ``n`` times to
  ``<project>/candidates/1`` .. ``candidates/n`` (its design, base design, build, seed and
  project.json as they are now; earlier transcripts, pictures and candidates are not copied;
  an older ``candidates`` folder is removed first). The designer then runs once on each copy,
  one after another, through ``bricksnap.designer.runner.run_designer`` with the same
  instruction, so each run is a first pass or an edit exactly as it would be on the project.
- A candidate is *valid* when its run finished without an error and its build passes the
  checks (``report.ok``). The others stay on disk, marked not valid, and cannot win.
- If ``on_event`` is given it is called with plain progress events (which candidate is being
  designed, that judging has started), so the command line can show progress.

Judging
- With two or more valid candidates, the judge ranks them (see "The judge"). With exactly
  one, it wins and no judge runs. With none, the project is left exactly as it was and
  ``BestOf.error`` says why in plain words.
- If the judge's session fails, or ends without a complete ranking, the winner is chosen by
  measurement instead, and the result says so: the valid candidate whose build's outline
  matches the seed best (the mean of ``bricksnap.bench.outline_match`` over front, right and
  top), ties to the lower candidate number.

Keeping the winner
- The winner's design (with its edit log), brief, build, LDraw file and pictures replace the
  project's own. The project is never left half replaced: everything is prepared beside the
  originals and moved into place, and if anything fails before the last move the project is
  as it was. Afterwards ``project.build_is_current()`` is true.
- ``<project>/candidates/result.json`` records, for every candidate: its number, the letter
  it had in the judging, whether it was valid (and if not, why), its part count and weak
  spots, its rank and the judge's reason; and the judge's overall summary, or the note that
  the winner was chosen by measurement. The candidates stay on disk so a person can look at
  the ones that lost.

``BestOf``: ``winner`` (candidate number, or None), ``ranking`` (numbers, best first),
``reasons`` (number -> sentence), ``summary``, ``runs`` (the ``DesignerRun`` of each
candidate), ``judge`` (the judge's run, or None), ``by_measurement`` (bool), ``error``.

The judge
- A second clean-room session: the same command-line flags, the same scrubbed environment
  and the same refusals as the designer's (no API key in use, the tool server started, the
  model that was asked for answered), but its own prompt, ``judge_prompt.md`` in this folder,
  and exactly two tools, served by ``judge_server.py`` for the candidates folder:
    look    ``{"candidate": "A"}``: one picture, the seed's views on the top row and that
            candidate's build on the bottom row (the same picture the designer's ``render``
            gives), plus one line of facts: parts, weak spots, the most parts hanging on
            one part. ``{"candidate": "all"}``: one sheet with the seed and every candidate
            from the front and from the three-quarter view, each under its letter.
    choose  ``{"ranking": ["B", "A", "C"], "reasons": {"A": "...", "B": "...", "C": "..."},
            "summary": "..."}``: records the verdict. Every candidate letter must appear
            exactly once in the ranking and have a reason; anything else comes back as an
            "ERROR:" that says what to fix, and nothing is recorded.
- Blind. The judge sees letters, not candidate numbers. The letters are dealt by a shuffle
  seeded from the project's name and the number of candidates, so tests are repeatable; the
  mapping is written to result.json and never shown to the judge. The judge is not told how
  the candidates were made, in what order, what the designer wrote about them, or their
  briefs. Only valid candidates are shown.
- What it is asked (the prompt says this in plain prose, explaining why): which build would
  a person most readily recognise as this object and take for something designed on
  purpose. Faithful to the seed's shape and colours; the features that make the object
  recognisable clear at this size; clean, deliberate surfaces; and, between builds that are
  otherwise close, the sturdier one. It must look at every candidate before it chooses.
- No text sent to the judge holds the project's path, the home folder or an email address,
  as for the designer's tools.

Refactoring allowed for this: ``runner.run_designer`` may be split so that the part that
starts and watches a clean-room session (command, environment, stream parsing, refusals,
transcript) is shared by the designer and the judge. The designer's behaviour, its flag set
and what parity.py measures must not change.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from bricksnap.designer.runner import DEFAULT_MODEL, DesignerRun
from bricksnap.project import Project

MIN_CANDIDATES = 2
MAX_CANDIDATES = 5


@dataclass
class BestOf:
    winner: int | None = None
    ranking: list[int] = field(default_factory=list)
    reasons: dict[int, str] = field(default_factory=dict)
    summary: str = ""
    runs: list[DesignerRun] = field(default_factory=list)
    judge: DesignerRun | None = None
    by_measurement: bool = False
    error: str = ""


def design_best_of(
    project: Project,
    n: int,
    instruction: str | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> BestOf:
    raise NotImplementedError
