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

Implementation notes
--------------------
- Folders. ``<project>/candidates/<number>/`` is each candidate, a project folder of its
  own (``COPIED`` and the seed file are copied; the designer's transcripts land in its own
  ``designer/``). ``candidates/judging/`` holds only what the judge is shown and what it
  answered (see judge_server.py): ``judging.json`` (letters and facts), ``<letter>.png``,
  ``all.png``, ``verdict.json``, and the judge's transcripts (``<UTC time>.jsonl``, kept when
  the candidates are judged again). ``candidates/result.json`` is the record.
- A candidate's run is passed ``instruction``, ``model`` and ``effort`` through
  ``runner.run_designer`` (looked up on the module at call time, so the command line's and
  the tests' fakes apply). Afterwards the candidate is rebuilt when its build is not made
  from its design as it now is (a run can end with edits it never rebuilt), and its
  comparison picture (``pipeline.render_compare``, the designer's ``render`` picture) is
  drawn. A run that raised counts as a run that failed, with the exception's message; a
  Ctrl+C is not caught.
- Faults while judging. A fault while the judge's pictures are prepared, or a judge session
  that raises, counts as a judging that failed (a ``DesignerRun`` with ``ok`` false, kind
  "judging", and the fault in plain words), so the winner is chosen by measurement and the
  designs already paid for are not lost; a Ctrl+C is not caught.
- Facts (shown to the judge, and in result.json): ``parts`` (every placement), ``weak_spots``
  (``bench.weak_spot_count``) and ``most_hanging``, the largest number of parts that hang on
  a single part or a single stud (``connect.sturdiness(...)[0]``, the load of the heaviest
  lone link, which is what the weak spots describe). result.json also has ``outline_match``
  (the measurement).
- Letters: ``deal_letters(name, n, valid)`` shuffles the valid candidates' numbers with
  ``random.Random`` seeded by the text "<name>/<n>" (string seeds are hashed with SHA-512,
  so the shuffle is the same on every computer and every run) and deals A, B, ... in that
  order.
- result.json is written as soon as the candidates are made (``"status": "designing"``, no
  run finished), again after each design run, before the judge starts (``"judging"``) and at
  the end (``"done"``), so a run stopped at any point leaves a true record of which designs
  finished. Besides the contract's fields it holds ``n``, ``instruction``, ``started_from``
  (a fingerprint of the project's design and edit log when the candidates were made),
  ``run_finished``, ``run_ok`` and ``run_error`` per candidate, ``outline_match``, ``note``
  (how the winner was chosen, in a sentence) and ``error``.
- The judge's session is ``run_judge(folder, letters, model=..., effort=...)``: one
  ``runner.run_session`` with ``judge_prompt.md``, the tool server
  ``bricksnap.designer.judge_server`` for the candidates folder, the message
  ``judge_message(letters)`` (how many builds, their letters, what to do; nothing else), at
  most ``JUDGE_MAX_TURNS`` turns and ``JUDGE_TIMEOUT_S`` seconds, and the judge's words for
  its errors (``runner.JUDGE``). Its ``DesignerRun.kind`` is "judging". The verdict is read
  from ``judging/verdict.json`` and counts only when it ranks every letter once and has a
  reason for each; an older verdict is removed before the judge starts. Its reasons and
  summary are cleaned (``judge_server.clean``: e-mail addresses and the home folder hidden,
  control characters removed) before they reach result.json, ``BestOf`` or the screen.
- The "all" sheet (``all_sheet``) has one column per entry (the seed, then the candidates
  in letter order) and two rows (front, three-quarter view), drawn without axis numbers and
  cropped to the same box in every picture of a row (the union of their outlines, from
  ``render.silhouette``, plus room for studs), so they stay at one scale and line up. The
  scale is chosen so the sheet is at most ``SHEET_MAX`` pixels each way, which keeps five
  candidates readable without the picture being shrunk again on the way to the model.
- Measurement ranks the valid candidates by their outline match, best first, ties to the
  lower number; each one's reason states its match.
- Keeping the winner. The files are ``design.npz``, ``design.json``, ``build.json``,
  ``build.ldr``, every picture in the winner's ``renders/`` and ``project.json`` (the
  project's own settings with the winner's brief). They are copied into ``.best-of-staging``
  inside the project and the originals into ``.best-of-backup``; then ``manifest.json`` is
  written into the backup folder (every target, and whether the project had it), and only
  then are the files moved into place one by one (``_move``, which is ``os.replace``). The
  manifest is removed after the last move, and then both folders. The backup copies and the
  manifest are flushed to disk before the first move (best effort).
- Putting back (``recover(path)``). When the manifest is there the swap had started and not
  finished: every listed file is moved back from the backup with ``os.replace`` (or removed,
  when the project had none), and the project is as it was before. Folders without a
  manifest are leftovers of a swap that had not started moving or had finished, and are
  removed. A failure while putting back is raised and the backup is kept. ``recover`` runs
  when ``_keep`` fails (any exception, Ctrl+C included; if putting back fails too, an
  ``OSError`` says so and that it will be finished later), at the start of ``_keep``,
  ``design_best_of`` and ``judge_candidates``, and whenever the command line opens a project.
  So a process killed part way (closed terminal, power cut) leaves the project half
  replaced only until the next BrickSnap command opens it. The project's other files (the
  seed, the base design, earlier transcripts, other pictures) are left alone. Two best-of
  runs on the same project at the same moment are not supported.
- ``judge_candidates(project, ...)`` judges the candidates already on disk again (the
  command line's hidden ``--judge-again``): no designer runs. A candidate counts only when
  result.json records its run as finished (a candidate without a record, or one whose run
  was stopped, is not valid); a recorded failure stays a failure; the builds are checked
  again, and the winner is kept as above. It refuses, changing nothing, when the project's
  design and edit log match neither ``started_from`` nor any candidate's (the project was
  changed since, and keeping a candidate would throw that change away).
- ``on_event`` receives ``{"event": "designing", "candidate": i, "of": n}``,
  ``{"event": "designed", "candidate": i, "of": n, "valid": bool, "why": text}``,
  ``{"event": "judging", "candidates": k}``, ``{"event": "judged", "ok": bool, "error":
  text}`` and finally ``{"event": "kept", "winner": number or None, "by_measurement":
  bool}``. An ``on_event`` that raises never stops the work.
- ``n`` outside 2 to 5 raises ``ValueError`` (the command line checks it first); a project
  without a design raises ``ProjectError`` before anything is created.
"""

from __future__ import annotations

import contextlib
import json
import os
import random
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bricksnap.designer import runner
from bricksnap.designer.runner import DEFAULT_MODEL, DesignerRun
from bricksnap.project import Project, ProjectError
from bricksnap.types import write_text_atomic

MIN_CANDIDATES = 2
MAX_CANDIDATES = 5

JUDGE_PROMPT_FILE = Path(__file__).parent / "judge_prompt.md"
JUDGE_SERVER_MODULE = "bricksnap.designer.judge_server"
JUDGE_MAX_TURNS = 20
JUDGE_TIMEOUT_S = 1200
CANDIDATES_DIR = "candidates"
RESULT_FILE = "result.json"
LETTERS = "ABCDE"
SHEET_MAX = 1500
"""The "all" sheet's largest width and height in pixels (the model's pictures are shrunk
beyond about 1568)."""

COPIED = (
    "project.json",
    "design.base.npz",
    "design.npz",
    "design.json",
    "build.json",
    "build.rough.json",
    "build.ldr",
)
"""What a candidate starts from (with the seed file), when the project has it."""

KEPT = ("design.npz", "design.json", "build.json", "build.ldr")
"""The winner's files that replace the project's own (with its pictures and its brief)."""

STAGING_DIR = ".best-of-staging"
BACKUP_DIR = ".best-of-backup"
MANIFEST = "manifest.json"
"""Where ``_keep`` prepares the winner's files and keeps the project's own until the swap is
done; the manifest in the backup folder lists what to put back if it never finished."""

_NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five"}

# Moving one file into place; the tests replace it to make a move fail.
_move = os.replace


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


@dataclass
class _Candidate:
    number: int
    path: Path
    run_finished: bool = False
    run_ok: bool = True
    run_error: str = ""
    valid: bool = False
    why_not_valid: str = ""
    parts: int = 0
    weak_spots: int = 0
    most_hanging: int = 0
    outline_match: float = 0.0
    letter: str | None = None
    rank: int | None = None
    reason: str = ""

    def facts(self) -> str:
        """The one line of facts the judge reads."""
        parts = f"{self.parts} part" + ("" if self.parts == 1 else "s")
        if not self.weak_spots:
            return f"{parts}; no weak spots (no group of parts hangs on a single part or stud)."
        spots = f"{self.weak_spots} weak spot" + ("" if self.weak_spots == 1 else "s")
        return (
            f"{parts}; {spots} (places where a group of parts hangs on a single part or a "
            f"single stud); the largest group hanging on one part or stud: {self.most_hanging} "
            "parts."
        )

    def record(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "letter": self.letter,
            "valid": self.valid,
            "why_not_valid": self.why_not_valid,
            "run_finished": self.run_finished,
            "run_ok": self.run_ok,
            "run_error": self.run_error,
            "parts": self.parts,
            "weak_spots": self.weak_spots,
            "most_hanging": self.most_hanging,
            "outline_match": round(self.outline_match, 4),
            "rank": self.rank,
            "reason": self.reason,
        }


def _tell(on_event: Callable[[dict[str, Any]], None] | None, **event: Any) -> None:
    if on_event is not None:
        with contextlib.suppress(Exception):  # progress output must never stop the work
            on_event(event)


def _words(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ---- candidates ---------------------------------------------------------------------------


def candidates_dir(project: Project) -> Path:
    return project.path / CANDIDATES_DIR


def _make_candidates(project: Project, n: int) -> list[_Candidate]:
    folder = candidates_dir(project)
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir()
    names = [*COPIED, str(project.meta.get("seed", ""))]
    out = []
    for number in range(1, n + 1):
        dest = folder / str(number)
        dest.mkdir()
        for name in dict.fromkeys(names):
            if name and (project.path / name).is_file():
                shutil.copy2(project.path / name, dest / name)
        out.append(_Candidate(number=number, path=dest))
    return out


def _settle(candidate: _Candidate, catalog: Any) -> None:
    """Make the candidate's build match its design, draw its picture, measure it."""
    from bricksnap import pipeline
    from bricksnap.bench import VIEWS, outline_match, weak_spot_count
    from bricksnap.connect import sturdiness

    try:
        cand = Project(candidate.path)
        design = cand.load_design()
        if not cand.build_is_current(design):
            pipeline.rebuild(cand, catalog=catalog)
        build = cand.load_build()
        pipeline.render_compare(cand, catalog=catalog)
        report = build.report
        candidate.parts = len(build.parts)
        candidate.weak_spots = weak_spot_count(report) if report is not None else 0
        candidate.most_hanging = sturdiness(build, catalog)[0]
        seed = pipeline.load_project_seed(cand)
        matches = [outline_match(seed, build, catalog, v, design.seed_offset) for v in VIEWS]
        candidate.outline_match = sum(matches) / len(matches)
        build_ok = bool(report is not None and report.ok)
    except Exception as e:  # a damaged candidate is not valid; it never stops the others
        candidate.valid = False
        candidate.why_not_valid = runner.redact(
            f"its build could not be made or measured: {str(e) or type(e).__name__}"
        )
        return
    if not candidate.run_finished:
        candidate.valid = False
        candidate.why_not_valid = "its design run never finished (it was stopped part way)."
    elif not candidate.run_ok:
        candidate.valid = False
        candidate.why_not_valid = "the design run did not finish: " + (
            candidate.run_error or "it gave no reason."
        )
    elif not build_ok:
        candidate.valid = False
        candidate.why_not_valid = "its build does not pass the checks (it does not hold together "
        candidate.why_not_valid += "as one standing model)."
    else:
        candidate.valid = True
        candidate.why_not_valid = ""


# ---- letters, pictures and the judge's folder ---------------------------------------------


def deal_letters(name: str, n: int, valid: list[int]) -> dict[str, int]:
    """Letter -> candidate number for the valid candidates, by a shuffle seeded from the
    project's name and the number of candidates (the same every time)."""
    numbers = sorted(valid)
    random.Random(f"{name}/{n}").shuffle(numbers)
    return {LETTERS[i]: number for i, number in enumerate(numbers)}


def _crop_box(masks: list[Any], pad: int) -> tuple[int, int, int, int]:
    import numpy as np

    union = np.zeros_like(masks[0])
    for m in masks:
        union |= m
    rows, cols = np.nonzero(union)
    h, w = union.shape
    if not len(rows):
        return (0, 0, w, h)
    return (
        max(int(cols.min()) - pad, 0),
        max(int(rows.min()) - pad, 0),
        min(int(cols.max()) + pad + 1, w),
        min(int(rows.max()) + pad + 1, h),
    )


def all_sheet(seed: Any, design: Any, builds: list[tuple[str, Any]], catalog: Any) -> Any:
    """The seed and every build, one column each, from the front and the three-quarter view,
    cropped alike and drawn at the largest scale that keeps the sheet within SHEET_MAX."""
    from bricksnap.render import contact_sheet, render_build, render_seed, silhouette

    views = ("front", "iso")

    def sheet(px: int) -> Any:
        items = []
        for view in views:
            masks = [
                b_mask
                for _, b in builds
                for b_mask in [silhouette(b, catalog, view, px_per_stud=px)]
            ]
            if seed is not None:
                masks.append(
                    silhouette(
                        seed,
                        catalog,
                        view,
                        grid_shape=design.shape,
                        seed_offset=design.seed_offset,
                        px_per_stud=px,
                    )
                )
            box = _crop_box(masks, pad=px // 2 + 4)
            if seed is not None:
                im = render_seed(
                    seed,
                    view,
                    design.shape,
                    seed_offset=design.seed_offset,
                    px_per_stud=px,
                    labels=False,
                )
                items.append((f"seed - {_VIEW_WORDS[view]}", im.crop(box)))
            for letter, build in builds:
                im = render_build(build, catalog, view, px_per_stud=px, labels=False)
                items.append((f"{letter} - {_VIEW_WORDS[view]}", im.crop(box)))
        columns = len(builds) + (1 if seed is not None else 0)
        title = (
            "The seed (first column) and every candidate, from the front (top row) and from "
            "the front right (bottom row)"
        )
        return contact_sheet(items, columns=columns, title=title)

    px = 16
    img = sheet(px)
    while (img.width > SHEET_MAX or img.height > SHEET_MAX) and px > 6:
        px = max(6, int(px * min(SHEET_MAX / img.width, SHEET_MAX / img.height)))
        img = sheet(px)
        if px == 6:
            break
    return img


_VIEW_WORDS = {"front": "front", "iso": "front right"}


def _prepare_judging(
    folder: Path, letters: dict[str, int], cands: dict[int, _Candidate], catalog: Any
) -> None:
    from bricksnap import pipeline
    from bricksnap.designer.judge_server import JUDGING_DIR, JUDGING_FILE, VERDICT_FILE

    judging = folder / JUDGING_DIR
    judging.mkdir(exist_ok=True)
    for old in [*judging.glob("*.png"), judging / VERDICT_FILE, judging / JUDGING_FILE]:
        old.unlink(missing_ok=True)
    builds = []
    seed = design = None
    for letter, number in letters.items():
        cand = Project(cands[number].path)
        shutil.copyfile(cand.renders_dir / "compare.png", judging / f"{letter}.png")
        builds.append((letter, cand.load_build()))
        if design is None:
            design = cand.load_design()
            with contextlib.suppress(Exception):  # a sheet without the seed is still useful
                seed = pipeline.load_project_seed(cand)
    all_sheet(seed, design, builds, catalog).save(judging / "all.png")
    setup = {
        "letters": list(letters),
        "facts": {letter: cands[number].facts() for letter, number in letters.items()},
    }
    write_text_atomic(judging / JUDGING_FILE, json.dumps(setup, indent=1) + "\n")


def judge_message(letters: list[str]) -> str:
    """The judge's user message: how many builds there are and their letters, nothing else."""
    count = _NUMBER_WORDS.get(len(letters), str(len(letters)))
    return (
        f"There are {count} brick builds of the same object to compare: {_words(letters)}. "
        "Look at all of them together and at each one on its own with look, compare them, "
        "and give your verdict with choose."
    )


def run_judge(
    folder: Path,
    letters: list[str],
    *,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> DesignerRun:
    """One clean-room judging session on the prepared candidates folder."""
    from bricksnap.designer.judge_server import JUDGING_DIR

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run = runner.run_session(
        prompt_file=JUDGE_PROMPT_FILE,
        mcp=runner.mcp_config(folder, module=JUDGE_SERVER_MODULE),
        message=judge_message(letters),
        transcript=folder / JUDGING_DIR / f"{stamp}.jsonl",
        model=model,
        effort=effort,
        max_turns=JUDGE_MAX_TURNS,
        timeout_s=JUDGE_TIMEOUT_S,
        on_event=on_event,
        role=runner.JUDGE,
    )
    run.kind = "judging"
    return run


def _read_verdict(folder: Path, letters: list[str]) -> dict[str, Any] | None:
    """The judge's verdict when it is complete (every letter ranked once, each with a
    reason), else None."""
    from bricksnap.designer.judge_server import JUDGING_DIR, VERDICT_FILE

    try:
        data = json.loads((folder / JUDGING_DIR / VERDICT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    ranking, reasons = data.get("ranking"), data.get("reasons")
    if not isinstance(ranking, list) or sorted(map(str, ranking)) != sorted(letters):
        return None
    if len(ranking) != len(letters) or not isinstance(reasons, dict):
        return None
    if not all(isinstance(reasons.get(x), str) and reasons[x].strip() for x in letters):
        return None
    from bricksnap.designer.judge_server import clean

    summary = data.get("summary")
    return {
        "ranking": [str(x) for x in ranking],
        "reasons": {x: clean(reasons[x]) for x in letters},
        "summary": clean(summary) if isinstance(summary, str) else "",
    }


# ---- keeping the winner -------------------------------------------------------------------


def _durable(path: Path) -> None:
    """Ask the system to write the file to disk now (best effort), so a backup is really
    there before the first move even after a power cut."""
    with contextlib.suppress(OSError), path.open("rb+") as f:
        os.fsync(f.fileno())


def recover(path: Path) -> bool:
    """Finish what an interrupted ``_keep`` left behind in the project folder ``path``.

    When the backup's manifest is there, the swap had started: every file it lists is put
    back from the backup (or removed, when the project had none) and the project is as it
    was before. Leftover staging or backup folders without a manifest are removed (nothing
    had been moved yet, or every move had been made). Returns True when files were put back.
    A failure is raised, and the backup is kept for the next try.
    """
    staging, backup = path / STAGING_DIR, path / BACKUP_DIR
    if not staging.exists() and not backup.exists():
        return False
    manifest = backup / MANIFEST
    put_back = False
    if manifest.is_file():
        try:
            entries = json.loads(manifest.read_text(encoding="utf-8"))["targets"]
            targets = [(str(e["path"]), str(e["stored"]), bool(e["had"])) for e in entries]
        except (ValueError, KeyError, TypeError) as e:
            raise ProjectError(
                f"The list of files to put back after an interrupted best-of run "
                f"({BACKUP_DIR}/{MANIFEST} in the project) is damaged, so the project could not "
                "be put back as it was. The earlier files are still in that folder."
            ) from e
        for rel, stored, _had in targets:
            if Path(rel).is_absolute() or ".." in Path(rel).parts or "/" in stored:
                raise ProjectError(
                    f"The list of files to put back ({BACKUP_DIR}/{MANIFEST}) names a file "
                    "outside the project, so nothing was put back."
                )
        for rel, stored, had in targets:
            live, kept = path / rel, backup / stored
            if had:
                if kept.is_file():  # not already put back by an earlier try
                    _move(kept, live)
            else:
                live.unlink(missing_ok=True)
        manifest.unlink()
        put_back = True
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    return put_back


def _keep(project: Project, winner: Path) -> None:
    """Replace the project's design, brief, build, LDraw file and pictures with the winner's,
    all or nothing, even if the process dies part way (see the implementation notes)."""
    if recover(project.path):
        project.meta = Project(project.path).meta
    files = [name for name in KEPT if (winner / name).is_file()]
    pictures = sorted(p.name for p in (winner / "renders").glob("*.png"))
    targets = [*files, *(f"renders/{p}" for p in pictures), "project.json"]
    meta = dict(project.meta)
    meta["brief"] = Project(winner).meta.get("brief")

    staging = project.path / STAGING_DIR
    backup = project.path / BACKUP_DIR
    try:
        staging.mkdir()
        backup.mkdir()
        entries: list[tuple[str, str, bool]] = []
        for rel in targets:
            stored = rel.replace("/", "__")
            dest = staging / stored
            if rel == "project.json":
                dest.write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
            else:
                shutil.copy2(winner / rel, dest)
            original = project.path / rel
            had = original.is_file()
            if had:
                shutil.copy2(original, backup / stored)
                _durable(backup / stored)
            entries.append((rel, stored, had))
        # the manifest is written last: from here on the swap can always be undone
        tmp = backup / (MANIFEST + ".tmp")
        listing = [{"path": rel, "stored": stored, "had": had} for rel, stored, had in entries]
        tmp.write_text(json.dumps({"targets": listing}, indent=1) + "\n", encoding="utf-8")
        _durable(tmp)
        os.replace(tmp, backup / MANIFEST)
        (project.path / "renders").mkdir(exist_ok=True)
        for rel, stored, _had in entries:
            _move(staging / stored, project.path / rel)
        (backup / MANIFEST).unlink()  # every file is in place: the swap is done
    except BaseException as first:
        try:
            recover(project.path)
        except Exception as again:
            raise OSError(
                f"The chosen design could not be put in place ({_why(first)}), and the "
                f"project could not be put back as it was either ({_why(again)}). Its earlier "
                f"files are kept in {BACKUP_DIR} inside the project, and BrickSnap puts them "
                "back the next time it opens the project."
            ) from again
        raise
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    project.meta = meta


def _why(e: BaseException) -> str:
    if isinstance(e, OSError) and e.strerror:
        return runner.redact(e.strerror)
    return runner.redact(str(e) or type(e).__name__)


def _fingerprint(folder: Path) -> str:
    """A fingerprint of a project folder's design and edit log."""
    import hashlib

    digest = hashlib.sha256()
    for name in ("design.npz", "design.json"):
        try:
            digest.update((folder / name).read_bytes())
        except OSError:
            digest.update(b"missing")
        digest.update(b"\0")
    return digest.hexdigest()


# ---- judging and keeping ------------------------------------------------------------------


def _write_result(
    project: Project, cands: list[_Candidate], result: BestOf, extra: dict[str, Any]
) -> None:
    data = {
        **extra,
        "winner": result.winner,
        "by_measurement": result.by_measurement,
        "summary": result.summary,
        "error": result.error,
        "candidates": [c.record() for c in cands],
    }
    path = candidates_dir(project) / RESULT_FILE
    write_text_atomic(path, json.dumps(data, indent=1) + "\n")


def _by_measurement(valid: list[_Candidate]) -> list[_Candidate]:
    return sorted(valid, key=lambda c: (-round(c.outline_match, 6), c.number))


def _failed_judging(what: str, e: Exception) -> DesignerRun:
    run = DesignerRun(ok=False, error=f"{what} ({_why(e)}).")
    run.kind = "judging"
    return run


def _judge(
    project: Project,
    cands: list[_Candidate],
    result: BestOf,
    extra: dict[str, Any],
    letters: dict[str, int],
    by_number: dict[int, _Candidate],
    catalog: Any,
    *,
    model: str,
    effort: str,
    on_event: Callable[[dict[str, Any]], None] | None,
) -> DesignerRun:
    """Prepare the judge's folder and run the judge. A fault in either is a judging that
    failed (the winner is then chosen by measurement); a Ctrl+C is not caught."""
    folder = candidates_dir(project)
    try:
        _prepare_judging(folder, letters, by_number, catalog)
    except Exception as e:
        return _failed_judging("The pictures for the judge could not be made", e)
    _write_result(project, cands, result, {**extra, "status": "judging", "note": ""})
    _tell(on_event, event="judging", candidates=len(letters))
    try:
        return run_judge(folder, list(letters), model=model, effort=effort)
    except Exception as e:
        return _failed_judging("The judge could not be run", e)


def _judge_and_keep(
    project: Project,
    cands: list[_Candidate],
    result: BestOf,
    extra: dict[str, Any],
    *,
    model: str,
    effort: str,
    on_event: Callable[[dict[str, Any]], None] | None,
    catalog: Any,
) -> BestOf:
    n = len(cands)
    valid = [c for c in cands if c.valid]
    folder = candidates_dir(project)
    if not valid:
        whys = "; ".join(f"design {c.number}: {c.why_not_valid}" for c in cands)
        result.error = (
            f"None of the {n} designs could be used, so the project was left as it was "
            f"({whys}). The designs are kept in {CANDIDATES_DIR}/ to look at."
        )
        _write_result(project, cands, result, {**extra, "status": "done", "note": ""})
        _tell(on_event, event="kept", winner=None, by_measurement=False)
        return result

    note = ""
    if len(valid) == 1:
        only = valid[0]
        only.rank, only.reason = 1, "The only design whose run finished and whose build is valid."
        result.ranking = [only.number]
        note = f"Design {only.number} was the only valid one, so it was kept without judging."
    else:
        letters = deal_letters(project.name, n, [c.number for c in valid])
        by_number = {c.number: c for c in cands}
        for letter, number in letters.items():
            by_number[number].letter = letter
        result.judge = _judge(
            project,
            cands,
            result,
            extra,
            letters,
            by_number,
            catalog,
            model=model,
            effort=effort,
            on_event=on_event,
        )
        verdict = _read_verdict(folder, list(letters))
        _tell(on_event, event="judged", ok=result.judge.ok, error=result.judge.error)
        if result.judge.ok and verdict is not None:
            for rank, letter in enumerate(verdict["ranking"], start=1):
                c = by_number[letters[letter]]
                c.rank, c.reason = rank, verdict["reasons"][letter]
            result.ranking = [letters[x] for x in verdict["ranking"]]
            result.summary = verdict["summary"]
            note = "Chosen by the judge."
        else:
            result.by_measurement = True
            why = (
                result.judge.error
                if not result.judge.ok
                else "it ended without giving a complete ranking."
            )
            note = (
                "The judge could not give a verdict, so the winner was chosen by measurement: "
                f"the build whose outline matches the seed best. (Why: {why})"
            )
            for rank, c in enumerate(_by_measurement(valid), start=1):
                c.rank = rank
                c.reason = (
                    f"Its outline matches the seed's by {c.outline_match:.0%} (the mean over the "
                    "front, the right side and the top)."
                )
            result.ranking = [c.number for c in _by_measurement(valid)]
            result.summary = ""

    for c in cands:
        if c.rank is not None:
            result.reasons[c.number] = c.reason
    result.winner = result.ranking[0]
    _keep(project, folder / str(result.winner))
    _write_result(project, cands, result, {**extra, "status": "done", "note": note})
    _tell(on_event, event="kept", winner=result.winner, by_measurement=result.by_measurement)
    return result


def design_best_of(
    project: Project,
    n: int,
    instruction: str | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> BestOf:
    from bricksnap.catalog import load_catalog

    if not isinstance(n, int) or not MIN_CANDIDATES <= n <= MAX_CANDIDATES:
        raise ValueError(
            f"Choose how many designs to make from {MIN_CANDIDATES} to {MAX_CANDIDATES}, not {n}."
        )
    if recover(project.path):  # an earlier best-of that died while keeping its winner
        project.meta = Project(project.path).meta
    project.load_design()  # a project with nothing to design fails here, before any copy
    catalog = load_catalog()
    extra = {"n": n, "instruction": instruction, "started_from": _fingerprint(project.path)}
    cands = _make_candidates(project, n)
    result = BestOf()
    _write_result(project, cands, result, {**extra, "status": "designing", "note": ""})
    for c in cands:
        _tell(on_event, event="designing", candidate=c.number, of=n)
        try:
            run = runner.run_designer(
                Project(c.path), instruction=instruction, model=model, effort=effort
            )
        except Exception as e:  # a fault in one run must not lose the others
            run = DesignerRun(ok=False, error=runner.redact(str(e) or type(e).__name__))
        result.runs.append(run)
        c.run_finished, c.run_ok, c.run_error = True, run.ok, run.error
        _settle(c, catalog)
        _write_result(project, cands, result, {**extra, "status": "designing", "note": ""})
        _tell(
            on_event, event="designed", candidate=c.number, of=n, valid=c.valid, why=c.why_not_valid
        )
    return _judge_and_keep(
        project,
        cands,
        result,
        extra,
        model=model,
        effort=effort,
        on_event=on_event,
        catalog=catalog,
    )


def judge_candidates(
    project: Project,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> BestOf:
    """Judge the candidates already in ``<project>/candidates`` again and keep the winner;
    no designer runs (see the implementation notes)."""
    from bricksnap.catalog import load_catalog

    if recover(project.path):  # an earlier best-of that died while keeping its winner
        project.meta = Project(project.path).meta
    folder = candidates_dir(project)
    numbers = sorted(
        int(p.name)
        for p in (folder.iterdir() if folder.is_dir() else [])
        if p.is_dir() and p.name.isdigit() and (p / "project.json").is_file()
    )
    if not numbers:
        return BestOf(
            error="This project has no candidates to judge. Make them with: bricksnap design "
            "PROJECT --best-of 3"
        )
    old: dict[int, dict[str, Any]] = {}
    extra: dict[str, Any] = {"n": len(numbers), "instruction": None}
    started_from = None
    with contextlib.suppress(OSError, ValueError, TypeError, AttributeError, KeyError):
        saved = json.loads((folder / RESULT_FILE).read_text(encoding="utf-8"))
        old = {int(c["number"]): c for c in saved.get("candidates", []) if isinstance(c, dict)}
        extra["instruction"] = saved.get("instruction")
        started_from = saved.get("started_from")
    # Keeping a winner replaces the project's design: only when the project still holds the
    # design the candidates started from, or one of them (an earlier winner), is nothing lost.
    known = {started_from, *(_fingerprint(folder / str(number)) for number in numbers)}
    if _fingerprint(project.path) not in known:
        return BestOf(
            error="The project's design has been changed since these designs were made, so "
            "keeping one of them now would throw that change away. Nothing was judged and the "
            "project was left as it is. To choose among new designs, make them with: "
            "bricksnap design PROJECT --best-of 3"
        )
    if started_from is not None:
        extra["started_from"] = started_from
    catalog = load_catalog()
    cands = []
    for number in numbers:
        record = old.get(number, {})
        c = _Candidate(number=number, path=folder / str(number))
        # a design counts only when its run is recorded as finished (a record written before
        # "run_finished" existed was written after every run had finished)
        c.run_finished = bool(record) and record.get("run_finished", True) is True
        c.run_ok = bool(record.get("run_ok", False))
        c.run_error = str(record.get("run_error", "") or "")
        _settle(c, catalog)
        cands.append(c)
    extra["judged_again"] = True
    return _judge_and_keep(
        project,
        cands,
        BestOf(),
        extra,
        model=model,
        effort=effort,
        on_event=on_event,
        catalog=catalog,
    )
