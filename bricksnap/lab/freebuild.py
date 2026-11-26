"""Free-build projects: models an AI built itself from the whole parts library (EXPERIMENTAL).

The lab (``bricksnap.lab.run``) runs one AI session in a work folder. This module turns such
sessions into projects a person keeps: in the same projects folder as the models made from a
3D file, with the current model, its checker report, the AI's own notes, the parts list and
pictures, and every run kept so an earlier one can be brought back. It holds no web code, so
the command line (``bricksnap make``) and the web app use the same functions.

CONTRACT (tests in tests/test_freebuild.py, the outside eye and polishing in
tests/test_polish.py; no test starts a real AI session: ``lab.run.build`` and
``runner.run_session`` are replaced, and pictures are drawn by stand-ins for
``picture.model_sheet`` and ``picture.turntable``)

A free-build project is a folder ``<projects>/<slug>/`` holding:

    project.json   {"kind": "free", "experimental": true, "name", "words" (what the person
                   typed; may be "" when there are pictures or a 3D model), "parts_wanted"
                   (or null), "reference" (the folder name of the project whose pictures
                   the AI was shown, or null), "reference_pictures" (["picture-1.png", ...],
                   in references/), "reference_model" ({"file", "name" as the person gave
                   it, "sheet"}, or null), "model" (the AI model asked for, or null: the
                   default, ``DEFAULT_MODEL``; a change that names one makes it the
                   project's), "created" (seconds since 1970), "guide" (whether
                   the builder is given the set designers' guide, ``lab.guide``; false
                   when missing), "runs": [...], "current": the number of the run shown
                   now, or null}
    model.ldr      the current model, as the AI left it (LDraw; BrickLink Studio, LeoCAD
                   and LDView open it; removed parts are "0 removed: ..." comment lines, so
                   the line numbers in the report still match)
    report.txt     the lab checker's full report on it
    notes.txt      the AI's closing words (through ``runner.redact``)
    parts.csv      the parts list: part, description, colour, colour_name, quantity (one row
                   per part in one colour; the description and colour name come from the
                   LDraw library and are left empty when it is not on this computer)
    pictures/      card.png (the home page's card, 4:3), sheet.png (three views), turn-00.png to
                   turn-11.png (twelve views round the model, from the front-left on), and for
                   a model with joints (``joints``) opened.png: three views with every joint
                   opened as far as the check says it goes (``movement.open_angles``: a swing
                   to the end of what it really reaches, a spin an eighth of a turn, a joint
                   that cannot move left shut), when it could be drawn
    references/    what the person gave to build from: picture-1.png to picture-4.png (each
                   ``clean_picture``'s PNG), their 3D model file under a name chosen here,
                   and model-sheet.png (it from five sides, ``model_sheet``). Every run, a
                   change too, is shown these (``references_of``), with reference.png (the
                   five sides of the "reference" project) when there is one.
    runs/NNNN/     each run (the first build, each change, an imported model): the same
                   files, record.json (what the run entry says), and for a run made here
                   work/, the lab's work folder (attempts, calls.jsonl, the redacted
                   transcript). Nothing in work/ is ever shown by the web app. A run an
                   outside eye looked at (``critique``) also has critique.json (its answer)
                   and critic/ (what it was shown and its redacted transcript; never served).

A run entry (``project.json`` "runs", oldest first) is ``{"n", "kind": "first" | "change" |
"imported", "words", "created", "ok", "error", "has_model", "parts", "kinds", "summary",
"clean", "problems", "unchecked", "moves", "seconds", "turns", "cost_usd_reported", "model"
(the session's, or null), "pictures" (whether they were drawn), "picture_problem", "guide"
(whether the run had the
guide: true or false, or null for an imported model whose run did not say), "playbook" (the
title of the playbook the builder asked for last, or null)}``; a run made with the guide
whose record has the art direction (``lab.art.record``) also has "art": true, "brief"
(its last, or null), "brief_story" (versions, whether it was carried from an earlier run and
which, how many parts were in when it was first written, the last reason), "critique" (its
last, with the facts it answered and their mismatches with the brief, or null), "critiques",
"first_no", "built_without_brief" and "ended_without_critique". A change made by ``polish``
also has "polish" (the outside eye's fixes it was asked for, below). ``summary`` is the checker's
one-line summary; ``clean`` is true when it found no problems; ``unchecked`` counts the
joints known by name only, whose fit it has not measured (hinges, ball joints: counted as
joined without proof). Since 20 November studs, pins, axles, bars, wheels and most clips on bars
are tested for fit and not counted there; numbers stored by earlier runs are kept as they were;
``moves`` is the report's MOVEMENT section, one sentence per joint ("'lid' (lid-hinge, lines
9, 10): swings from 0 to 90 degrees with nothing in the way"), empty when nothing moves
(``read_movement``).

A run entry with a model also has ``"looks"``: how the model looks (``looks.record``: the
numbers, not the sentences), measured when the run is kept, outside the builder's session and
whether the run had the guide or not, so runs stay comparable; null when it could not be
measured (no library) and missing in runs kept before it existed. ``describe`` gives the
current run's ``looks`` and ``looks_lines`` (``looks.page_lines``: three or four short
sentences with the official range; empty when the run has no record). With
``measure_missing=True`` (the web page's request) a current run with a model but no record is
measured then from its model.ldr (``remembered_looks``), kept in memory for the process by the
file's path, size and modification time, never written to project.json; when measuring fails
the lines are simply empty.

Functions
- ``is_free(folder)``: whether a project folder is a free-build project (never raises).
- ``create(projects_dir, words, name=..., parts=..., reference=..., model=..., folder=...,
  guide=False, pictures=None, model_file=None, model_name=None)``: a new project with no
  runs yet, remembering whether to give the builder the guide; the folder is ``folder`` when
  given (it must not exist), else ``slug(name or words)`` made unique with a number (with no
  words: the 3D file's name, or "Built from pictures"). Words and names are cut to
  ``MAX_WORDS`` and ``MAX_NAME`` characters, control characters removed. Words may be empty
  only with something else to build from. Pictures (at most ``MAX_PICTURES``, together
  ``MAX_PICTURES_BYTES``) go through ``clean_picture``; a 3D file is drawn first, so one that
  cannot be read makes nothing (``FreeBuildError`` in the converter's words).
- ``clean_picture(data)``: an untrusted picture as safe PNG bytes (its docstring says how),
  or ``FreeBuildError`` in plain words. ``model_sheet(file, out_png, shown)``: a 3D model
  file from five sides. ``references_of(folder)``: what every run is shown.
- ``MODELS`` (the two Claude models a person may choose, the default first), ``model_name``,
  ``other_model``; ``estimate`` and ``time_and_cost`` take the model too: for Opus 5.5 the
  dollars are half of Fable's (its list price is half; one Opus build is on record, at about
  half), said as an estimate.
- ``build(folder, words=None, on_say=None, references=None)``: runs one lab session into
  the next ``runs/NNNN/work`` and keeps what it made (``adopt``): the first build from the
  project's words when it has no model yet, otherwise ``words`` is a change to the current
  model (``lab.run.build`` with ``start`` and ``change_of``), with the replies, checks and
  time ``limits`` gives for the parts asked for (a change: the model's actual size); they
  grow with the size, which ``size`` keeps from 20 to 600. ``minutes``, ``estimate`` and
  ``time_and_cost`` say how long a build of that size usually takes, when it is stopped,
  and what builds that size have used of the person's subscription. Every run of a project,
  a change too, has the guide or not as the project's "guide" says; with it, the session is
  told the size, and a change is given the current run's brief to build to (``lab.art``).
  ``on_say`` gets the progress as plain sentences (``Progress``). Returns the run entry;
  raises ``FreeBuildError`` when the session could not start or made no model, after keeping
  the run's entry, and ``UsageLimitError`` (its ``model``, ``other`` and ``resets``) when
  the subscription's usage limit stopped it: said plainly, with when it resets and the
  other model to choose; it never switches by itself. ``model`` (optional) becomes the
  project's model before the run; ``references`` default to ``references_of``.
- Usage limits are remembered for the projects folder in ``.state/usage-limits.json``
  (``note_limit`` when a run hits one, with its reset time; ``clear_limit`` when a run with
  that model finishes); ``usage_limits(projects_dir)`` lists those of ``MODELS`` not reset
  yet, with "until_words" ("1 Dec, 2am") and the other model, for the web app's bar. A limit
  with no time is taken to last ``LIMIT_GUESS_S`` (a day).
- ``adopt(folder, n, work, kind, words)``: keep lab work folder ``work`` as run ``n``; when it
  holds a model, the run's files and pictures are written and it becomes the current one.
- ``import_run(projects_dir, source, name=None, words=None)``: a new project from a
  finished lab run folder (final.ldr, final-report.txt, session.json, final.png) or from
  one .ldr file (with ``<stem>-report.txt`` beside it, when there is one; otherwise the
  checker is run when the library is here). Only those files are copied: never a
  transcript or calls.jsonl.
- ``restore(folder, n)``: make run ``n`` the current one again (its files copied back to the
  top of the folder); the other runs stay.
- ``describe(folder)``: everything a page or the command line shows about the project
  (with ``moves`` and ``opened``, the path of pictures/opened.png or None, ``guide``, the
  current run's art direction fields, ``ART_KEYS``, each None when it has none, and its
  ``polish``, or None).
- An outside eye (25 November; the builder's own critique is lenient). ``critique(folder,
  on_say=None, model=None)``: one short clean-room session (``lab.critic``: our tools only,
  the person's own login, the project's model unless ``model``, ``critic.MAX_TURNS`` replies
  and ``critic.TIMEOUT_S`` seconds) shown only ``critic_inputs``: the current run's
  pictures/sheet.png and turn views ``CRITIC_VIEWS``, the reference pictures, the project's
  words and the person's changes since (the latest ``MAX_CHANGES_SHOWN``; never a polish's
  words), the run's brief (``art.brief_lines``) and its HOW IT LOOKS lines (``looks.section``
  of the run's record, else measured as ``remembered_looks``). Never the builder's
  transcript, notes, report or self-critique. It answers with up to five fixes, each
  ``{"where", "fix"}``, the most visible first, and what to ``keep``, kept as
  runs/NNNN/critique.json of the run it looked at and returned. No model, no pictures, or no
  list (a session that failed or never called its tool) is a ``FreeBuildError`` and the
  usage limit a ``UsageLimitError``, as for ``build``; nothing is changed.
- ``polish(folder, on_say=None, on_critique=None, model=None)``: ``critique``, then one change
  (``build``) whose words are ``polish_words``: the fixes numbered, what to keep, and
  ``POLISH_TAIL`` ("Keep everything else as it is; then look from every side and hand it
  in."). The new run's entry and record get "polish" (``{"of_run", "fixes", "keep", "model",
  "seconds", "cost_usd_reported"}``); ``on_critique`` gets the critique as soon as it exists.
  No fix asked for: ``NothingToPolish`` (with the critique) and no change run.
  ``critic_time_and_cost``, ``polish_time_and_cost(parts, model)`` and ``polish_estimate(parts,
  model, after_build)`` say what it costs (``CRITIC_MINUTES``, ``CRITIC_DOLLARS``: an
  estimate, none on record), the page by the same arithmetic.
- ``missing()``: None when a run can start, else what is missing (the LDraw library zip,
  LeoCAD, xvfb-run) and exactly where to put it, in plain words.
- ``reference_sheet(project_folder, out_png)``: pictures of an ordinary project's 3D model
  from five sides in one sheet (``render.render_seed``), as the experiments showed the AI.
- ``Progress(work, say)``: turns the session's stream-json events into plain sentences
  ("The builder is looking for parts: curved slope 2 x 2", "It placed a part (31 so far)",
  "Check 2: 3 problems to fix", "Check 3: no problems"), reading the work folder for the
  part count and the checker's summary; every text from the AI goes through
  ``runner.redact`` and is shortened.
"""

from __future__ import annotations

import contextlib
import csv
import io
import json
import math
import os
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bricksnap.lab.run import DEFAULT_MODEL
from bricksnap.project import slug

KIND = "free"
MAX_WORDS = 2000
MAX_NAME = 80
MIN_PARTS, MAX_PARTS, DEFAULT_PARTS = 20, 600, 80
MAX_TURNS = 120  # the least a session gets; ``limits`` gives more for more parts
MAX_CHECKS = 25
TIMEOUT_S = 5400
# Claude Code's --max-turns limits the model's replies (one reply may call several tools);
# the "turns" a session reports (num_turns) count its tool calls and its answer. The Cessna of
# 20 November reported 103 turns under a limit of 90 and finished: its 102 tool calls came in
# 43 replies. Replies per part on record: 0.21 (Cessna, 206 parts), 0.08 (guitar, 283), 0.32
# (cat, 96). On 25 November a guide-mode build on Opus 5.5 (a sports car asked at 300 parts) used
# all of its 105 replies at 174 parts, about 0.6 a part: Opus makes fewer calls in each reply,
# and guide mode adds the brief, the halfway look and the critique. ``REPLIES_PER_PART`` leaves
# room above that, so a build stops because it is done, not because its replies ran out.
REPLIES_PER_PART = 1.0
PARTS_PER_CHECK = 8  # no run on record used more than 7 checks
SECONDS_PER_PART = 18
# How long builds took (minutes per part, low and high, in hundredths): 71 parts in 5
# minutes, 84 in 9, 96 in 17 and 18, 156 in 15, 206 in 36, 283 in 26.
MINUTES_PER_PART_100 = (9, 20)
# What they used of the person's subscription at list prices, in dollars per 100 parts, low
# and high: $1.72 for 71 parts, $3.60 for 84, $5.41 for 84, $5.72 and $6.60 for 96, $5.25 for
# 156, $13.53 for 206, $8.68 for 283. Above ``LARGEST_ON_RECORD`` it is an estimate.
DOLLARS_PER_100_PARTS = (2, 7)
LARGEST_ON_RECORD = 290
EFFORT = "high"
# The outside eye (``critique``, ``lab.critic``): what it is shown of the model (the sheet and
# four of the twelve turn views: front-left, front-right, back-right, back-left), where its
# files go in the run it looked at, and what a person is told it costs. No run of it is on
# record yet: a few pictures and three replies, well under a dollar at Fable's list price.
CRITIC_DIR = "critic"
CRITIQUE_FILE = "critique.json"
CRITIC_EFFORT = "high"
CRITIC_VIEWS = (0, 3, 6, 9)
CRITIC_MINUTES = (2, 5)
CRITIC_DOLLARS = 1
MAX_CHANGES_SHOWN = 5  # the person's latest changes the outside eye is told of
# The Claude models a person may choose for a free build, the default first. Fable 5.2 builds
# the more refined models (docs/decisions/2026-11-19-the-designer-uses-fable-5-2-unless-told-
# otherwise.md); Opus 5.5 costs half as much per word at list prices ($4 and $20 for a
# million words in and out, against $8 and $40), and its one build on record, the sports car
# of 19 November, used about half of what Fable's took ($4.15 against $8.11).
MODELS = {DEFAULT_MODEL: "Claude Fable 5.2", "claude-opus-5-5": "Claude Opus 5.5"}
PRICE_SHARE = {"claude-opus-5-5": (1, 2)}  # list price against Fable 5.2's, as a fraction
# What a person gives the AI to build from besides words, kept in ``REFS_DIR``: up to
# ``MAX_PICTURES`` pictures (``clean_picture``) and one 3D model file drawn from five sides.
REFS_DIR = "references"
MAX_PICTURES = 4
PICTURE_FORMATS = ("JPEG", "PNG", "WEBP")
MAX_PICTURE_BYTES = 8 * 1024 * 1024
MAX_PICTURES_BYTES = 20 * 1024 * 1024  # all the pictures of one request together
MAX_PICTURE_PIXELS = 60_000_000
PICTURE_SIDE = 1600
MIN_PICTURE_SIDE = 32
MODEL_SHEET = "model-sheet.png"
SHEET_STUDS = 24  # the size a 3D model file is drawn at for its sheet
REFERENCE_SHEET = "reference.png"
NO_WORDS = "what the reference pictures show"
STATE_DIR = ".state"  # in the projects folder: what the app remembers between runs
LIMITS_FILE = "usage-limits.json"
LIMIT_GUESS_S = 24 * 3600  # how long a usage limit with no reset time is taken to last
_HEIC = (b"ftypheic", b"ftypheix", b"ftyphevc", b"ftypmif1", b"ftypmsf1")
SAID_CHARS = 240
RUNS_DIR = "runs"
PICTURES_DIR = "pictures"
TURN_FRAMES = 12
CARD_PX = 640
CURRENT_FILES = ("model.ldr", "report.txt", "notes.txt", "parts.csv")
CSV_HEADER = ("part", "description", "colour", "colour_name", "quantity")
LEOCAD_SITE = "https://www.leocad.org"
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_PROBLEMS = re.compile(r"\b(\d+) problems?\b")
_UNCHECKED = re.compile(r"\b(\d+) joints? not checked\b")


class FreeBuildError(Exception):
    """A free build that could not be made or changed; the message is for a person."""


class UsageLimitError(FreeBuildError):
    """A run the subscription's usage limit stopped: ``model`` is the model that was asked
    for, ``other`` the other one a person may choose (or None), ``resets`` when the limit
    resets, in words ("" when not known), ``resets_at`` in seconds since 1970 (or None)."""

    def __init__(
        self,
        message: str,
        model: str,
        other: str | None,
        resets: str,
        resets_at: float | None = None,
    ) -> None:
        super().__init__(message)
        self.model, self.other, self.resets, self.resets_at = model, other, resets, resets_at


# ---- small helpers ---------------------------------------------------------------------------


def clean(text: str, limit: int) -> str:
    """Text a person typed, as one line: control characters gone, at most ``limit`` long."""
    return _CONTROL.sub(" ", text).strip()[:limit].strip()


def _short(text: str, limit: int = SAID_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word if n == 1 else word + 's'}"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def read_meta(folder: Path) -> dict[str, Any]:
    try:
        meta = json.loads((folder / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise FreeBuildError(
            f"This project's file project.json is damaged and cannot be read ({folder.name})."
        ) from e
    if not isinstance(meta, dict):
        raise FreeBuildError(f"This project's file project.json is damaged ({folder.name}).")
    return meta


def save_meta(folder: Path, meta: dict[str, Any]) -> None:
    _write(folder / "project.json", json.dumps(meta, indent=1) + "\n")


def is_free(folder: Path) -> bool:
    try:
        meta = json.loads((folder / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(meta, dict) and meta.get("kind") == KIND


def model_name(model: Any) -> str:
    """What a person calls an AI model: "Claude Fable 5.2" (the default when ``model`` is
    None or empty), else the id as given."""
    model = str(model or DEFAULT_MODEL)
    return MODELS.get(model, model)


def other_model(model: Any) -> str | None:
    """The other model of ``MODELS`` a person may choose instead of ``model``, or None."""
    model = str(model or DEFAULT_MODEL)
    return next((m for m in MODELS if m != model), None) if model in MODELS else None


def part_lines(text: str) -> list[tuple[int, str]]:
    """(colour, file name) of every part line of an LDraw model."""
    out = []
    for raw in text.splitlines():
        tok = raw.split()
        if len(tok) < 15 or tok[0] != "1":
            continue
        try:
            colour = int(tok[1], 0)
        except ValueError:
            continue
        out.append((colour, " ".join(tok[14:])))
    return out


def count_parts(text: str) -> tuple[int, int]:
    """How many parts a model has, and of how many kinds (file names, any colour)."""
    lines = part_lines(text)
    return len(lines), len({name.lower().replace("\\", "/") for _, name in lines})


def read_summary(report: str) -> dict[str, Any]:
    """The checker's verdict from its report text: its summary line, whether it found no
    problems, how many problems, and how many joints it could not check."""
    first = next((ln for ln in report.splitlines() if ln.startswith("SUMMARY:")), "")
    summary = first.removeprefix("SUMMARY:").strip()
    if not summary:
        return {"summary": "", "clean": None, "problems": None, "unchecked": None}
    m = _PROBLEMS.search(summary)
    problems = int(m.group(1)) if m else 0
    u = _UNCHECKED.search(summary)
    nothing = "nothing to check" in summary
    return {
        "summary": summary,
        "clean": (problems == 0 and "no problems" in summary) and not nothing,
        "problems": problems,
        "unchecked": int(u.group(1)) if u else 0,
    }


def read_movement(report: str) -> list[str]:
    """The report's MOVEMENT section: one sentence per joint, without the leading "- "."""
    out: list[str] = []
    inside = False
    for ln in report.splitlines():
        if ln.startswith("MOVEMENT"):
            inside = True
            continue
        if inside:
            if not ln.startswith("- "):
                break
            out.append(ln[2:].strip())
    return out


def parts_csv(text: str) -> str:
    """The parts list of an LDraw model as CSV (``CSV_HEADER``), most used first."""
    counts: dict[tuple[str, int], int] = {}
    for colour, name in part_lines(text):
        key = (name.lower().replace("\\", "/"), colour)
        counts[key] = counts.get(key, 0) + 1
    names: dict[int, str] = {}
    lib = None
    with contextlib.suppress(Exception):  # no library here: the list has no descriptions
        from bricksnap.lab.ldraw_lib import library

        lib = library()
        names = lib.colours()
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for (name, colour), n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        description = ""
        if lib is not None:
            with contextlib.suppress(Exception):
                description = lib.header(name).description
        writer.writerow((name, description, colour, names.get(colour, ""), n))
    return out.getvalue()


# ---- what a run needs ------------------------------------------------------------------------


def missing() -> str | None:
    """None when a free build can start here, else what is missing and where it goes."""
    from bricksnap.lab import ldraw_lib, picture

    base = Path.home() / ".cache" / "bricksnap" / "leocad"
    problems = []
    has_leocad = True
    try:
        has_leocad = picture.leocad().exists()
    except picture.PictureError:
        has_leocad = False
    if not has_leocad:
        problems.append(
            "LeoCAD, the free program that draws the pictures, is not on this computer. "
            f"Download the Linux AppImage from {LEOCAD_SITE} and save it as "
            f"{base / 'LeoCAD.AppImage'}."
        )
    if shutil.which("xvfb-run") is None:
        problems.append(
            "xvfb-run, which lets LeoCAD draw without a screen, is not installed. On Ubuntu "
            "or Debian it comes with the package xvfb (sudo apt install xvfb)."
        )
    zip_file = ldraw_lib.zip_path()
    if not zip_file.is_file():
        inside = base / "squashfs-root" / "usr" / "share" / "leocad" / "library.bin"
        problems.append(
            f"The LDraw parts library was not found at {zip_file}. It is the library that "
            "comes with LeoCAD: copy LeoCAD's library.bin there under that name"
            + (f" (it is at {inside})" if inside.is_file() else "")
            + ", or download the parts library from LeoCAD's site."
        )
    if not problems:
        return None
    return "The AI cannot build from parts on this computer yet. " + " ".join(problems)


# ---- creating a project ----------------------------------------------------------------------


def _free_folder(projects_dir: Path, wanted: str) -> Path:
    base = slug(wanted)[:60].strip("-") or "model"
    name, n = base, 1
    while os.path.lexists(projects_dir / name):
        n += 1
        name = f"{base}-{n}"
    return projects_dir / name


def name_from(words: str) -> str:
    """A short name for a model from the words that describe it: its first few words."""
    first = re.split(r"[.,;:!?\n]", words.strip(), maxsplit=1)[0]
    kept = " ".join(first.split()[:6]) or "Free build"
    return kept[:1].upper() + kept[1:]


def create(
    projects_dir: Path,
    words: str,
    *,
    name: str | None = None,
    parts: int | None = DEFAULT_PARTS,
    reference: str | None = None,
    model: str | None = None,
    folder: str | None = None,
    guide: bool = False,
    pictures: list[bytes] | None = None,
    model_file: Path | None = None,
    model_name: str | None = None,
) -> Path:
    """A new free-build project with no runs yet; returns its folder. ``pictures`` are the
    pictures the person gave, as they came (each made safe by ``clean_picture`` before it is
    kept); ``model_file`` a 3D model file (copied in and drawn from five sides,
    ``model_sheet``), called ``model_name`` by the person. The words may be empty when there
    is something else to build from."""
    words = clean(words, MAX_WORDS)
    pictures = list(pictures or [])
    if not words and not (pictures or model_file or reference):
        raise FreeBuildError(
            'Say what to build, for example "a small red fire truck", or add a picture or a '
            "3D model of it."
        )
    if parts is not None and not MIN_PARTS <= parts <= MAX_PARTS:
        raise FreeBuildError(
            f"Choose about how many parts, a whole number from {MIN_PARTS} to {MAX_PARTS}."
        )
    if len(pictures) > MAX_PICTURES:
        raise FreeBuildError(f"Add at most {MAX_PICTURES} pictures.")
    if sum(len(p) for p in pictures) > MAX_PICTURES_BYTES:
        raise FreeBuildError(
            f"The pictures are too large together: at most {MAX_PICTURES_BYTES // 2**20} MB in "
            "all. Choose fewer, or smaller ones."
        )
    pngs = [clean_picture(p) for p in pictures]
    shown_file = clean(model_name or (model_file.name if model_file else ""), MAX_NAME)
    with contextlib.ExitStack() as stack:
        sheet = None
        if model_file is not None:  # drawn first, so a file that cannot be read makes nothing
            import tempfile

            tmp = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="bricksnap-")))
            sheet = model_sheet(model_file, tmp / MODEL_SHEET, shown_file or model_file.name)
        fallback = Path(shown_file).stem if shown_file else "Built from pictures"
        shown = clean(name or "", MAX_NAME) or (name_from(words) if words else fallback)
        projects_dir.mkdir(parents=True, exist_ok=True)
        path = projects_dir / folder if folder else _free_folder(projects_dir, shown)
        path.mkdir()
        refs = path / REFS_DIR
        kept_pictures = []
        for k, png in enumerate(pngs, 1):
            refs.mkdir(exist_ok=True)
            (refs / f"picture-{k}.png").write_bytes(png)
            kept_pictures.append(f"picture-{k}.png")
        kept_model = None
        if model_file is not None and sheet is not None:
            refs.mkdir(exist_ok=True)
            suffix = model_file.suffix.lower()
            inside = (slug(Path(shown_file).stem)[:60].strip("-") or "model") + suffix
            shutil.copyfile(model_file, refs / inside)
            shutil.copyfile(sheet, refs / MODEL_SHEET)
            kept_model = {"file": inside, "name": shown_file, "sheet": MODEL_SHEET}
    meta = {
        "kind": KIND,
        "experimental": True,
        "name": shown,
        "words": words,
        "parts_wanted": parts,
        "reference": reference,
        "reference_pictures": kept_pictures,
        "reference_model": kept_model,
        "model": model,
        "created": time.time(),
        "guide": bool(guide),
        "runs": [],
        "current": None,
    }
    save_meta(path, meta)
    return path


# ---- what it is built from ---------------------------------------------------------------


def clean_picture(data: bytes) -> bytes:
    """The picture a person gave, made safe to keep and to show the AI, as PNG bytes.

    Untrusted: at most ``MAX_PICTURE_BYTES``; only what Pillow decodes as JPEG, PNG or WebP
    (the first frame of a moving one), from ``MIN_PICTURE_SIDE`` pixels a side to
    ``MAX_PICTURE_PIXELS`` in all; turned upright as the camera was held; transparent parts
    on white; in sRGB when it carried a colour profile; scaled down so its longest side is
    at most ``PICTURE_SIDE``; and drawn afresh into a new image, so nothing the file carried
    besides its pixels (GPS position, camera, date, comments, the profile) is kept. Anything
    else raises ``FreeBuildError`` with a plain sentence."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    mb = MAX_PICTURE_BYTES // (1024 * 1024)
    if not data:
        raise FreeBuildError("A picture is empty. Choose another one.")
    if len(data) > MAX_PICTURE_BYTES:
        raise FreeBuildError(
            f"A picture is too large: BrickSnap takes pictures of up to {mb} MB each. Choose "
            "a smaller one, or save it smaller first."
        )
    if data[4:12] in _HEIC:
        raise FreeBuildError(
            "That is a HEIC photo, as iPhones save them, which BrickSnap cannot read. Save it "
            "as JPEG or PNG first, then choose that."
        )
    try:
        with Image.open(io.BytesIO(data), formats=list(PICTURE_FORMATS)) as im:
            w, h = im.size
            if w * h > MAX_PICTURE_PIXELS:
                raise FreeBuildError(
                    f"A picture is too big ({w:,} x {h:,} pixels): BrickSnap takes pictures "
                    f"of up to {MAX_PICTURE_PIXELS // 1_000_000} million pixels. Save it "
                    "smaller first."
                )
            if min(w, h) < MIN_PICTURE_SIDE:
                raise FreeBuildError(
                    f"A picture is too small ({w} x {h} pixels) to show the AI anything. "
                    f"Choose one at least {MIN_PICTURE_SIDE} pixels on each side."
                )
            im.draft("RGB", (PICTURE_SIDE, PICTURE_SIDE))  # a JPEG is read at a smaller size
            icc = im.info.get("icc_profile")
            pic = ImageOps.exif_transpose(im)  # upright, as the camera was held
            pic = _flat(pic)
    except FreeBuildError:
        raise
    except UnidentifiedImageError:
        raise FreeBuildError(
            "That file is not a picture BrickSnap can use. Choose a photo or a drawing saved "
            "as JPEG, PNG or WebP."
        ) from None
    except Exception:  # whatever a damaged or hostile file makes the decoder do
        raise FreeBuildError(
            "A picture could not be read: the file may be damaged or incomplete. Choose "
            "another one."
        ) from None
    if isinstance(icc, bytes) and icc:
        with contextlib.suppress(Exception):  # a profile that cannot be used: as it is
            from PIL import ImageCms

            source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
            pic = ImageCms.profileToProfile(pic, source, srgb, outputMode="RGB") or pic
    pic.thumbnail((PICTURE_SIDE, PICTURE_SIDE), Image.Resampling.LANCZOS)
    fresh = Image.new("RGB", pic.size, "white")  # no info, no EXIF, no profile: pixels only
    fresh.paste(pic)
    out = io.BytesIO()
    fresh.save(out, format="PNG")
    return out.getvalue()


def model_sheet(model_file: Path, out_png: Path, shown: str) -> Path:
    """A 3D model file (any the converter reads, ``seed.load_seed``) drawn from five sides in
    one sheet, as ``reference_sheet`` draws an ordinary project's. A file that cannot be read
    raises ``FreeBuildError`` with the converter's own plain words."""
    import numpy as np

    from bricksnap.render import contact_sheet, render_seed
    from bricksnap.seed import load_seed
    from bricksnap.types import SeedError

    try:
        seed = load_seed(model_file, studs=SHEET_STUDS)
    except SeedError as e:
        raise FreeBuildError(str(e)) from None
    top = seed.vertices.max(axis=0)
    shape = (
        max(1, int(np.ceil(top[0] / 8 - 1e-9))),
        max(1, int(np.ceil(top[1] / 8 - 1e-9))),
        max(1, int(np.ceil(top[2] / 3.2 - 1e-9))),
    )
    items = [(said, render_seed(seed, view, shape)) for view, said in _FIVE_SIDES.items()]
    title = f"{shown}: the 3D model to build from, from five sides"
    contact_sheet(items, columns=3, title=title).save(out_png)
    return out_png


_FIVE_SIDES = {
    "front": "from the front",
    "right": "from the right",
    "back": "from the back",
    "left": "from the left",
    "iso": "from the front right, above",
}


def _flat(pic: Any) -> Any:
    """``pic`` as RGB, with anything transparent on white."""
    from PIL import Image

    if pic.mode in ("RGBA", "LA", "PA", "RGBa", "La") or (
        pic.mode == "P" and "transparency" in pic.info
    ):
        rgba = pic.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return pic.convert("RGB")


def references_of(folder: Path) -> list[Path]:
    """What every run of a project is shown, those files that are there: the person's
    pictures, the sheet of their 3D model file, and the sheet of an ordinary project's model
    ("reference"). Only names this module chose are read."""
    meta = read_meta(folder)
    refs = folder / REFS_DIR
    out = []
    listed = meta.get("reference_pictures") or []
    for k in range(1, MAX_PICTURES + 1):
        if f"picture-{k}.png" in listed and (refs / f"picture-{k}.png").is_file():
            out.append(refs / f"picture-{k}.png")
    if meta.get("reference_model") and (refs / MODEL_SHEET).is_file():
        out.append(refs / MODEL_SHEET)
    if meta.get("reference") and (folder / REFERENCE_SHEET).is_file():
        out.append(folder / REFERENCE_SHEET)
    return out


def size(parts: Any) -> int:
    """``parts`` as a size the limits accept: a whole number from ``MIN_PARTS`` to
    ``MAX_PARTS`` (``DEFAULT_PARTS`` when it is missing or not a number)."""
    if not isinstance(parts, int) or isinstance(parts, bool):
        return DEFAULT_PARTS
    return min(MAX_PARTS, max(MIN_PARTS, parts))


def limits(parts: Any) -> dict[str, int]:
    """What one session may use for a model of about ``parts`` parts (``size``): replies
    (``--max-turns``), checks and seconds, each the larger of the fixed least (``MAX_TURNS``,
    ``MAX_CHECKS``, ``TIMEOUT_S``) and a share per part (one reply, one check for every 8
    parts, 18 seconds). 600 parts get 600 replies, 75 checks and three hours."""
    n = size(parts)
    return {
        "max_turns": max(MAX_TURNS, math.ceil(n * REPLIES_PER_PART)),
        "max_checks": max(MAX_CHECKS, math.ceil(n / PARTS_PER_CHECK)),
        "timeout": max(TIMEOUT_S, math.ceil(n * SECONDS_PER_PART / 60) * 60),
    }


def _five(hundredths: int) -> int:
    """Minutes from hundredths of a minute, to the nearest five, halves up (as the page)."""
    return 5 * ((hundredths + 250) // 500)


def minutes(parts: Any) -> tuple[int, int]:
    """About how long a build of ``parts`` parts usually takes, in minutes (low, high),
    from the runs on record, each end to the nearest five minutes. Whole-number arithmetic,
    so ``viewer/app.js`` gives the same at every size."""
    n = size(parts)
    low = max(5, _five(n * MINUTES_PER_PART_100[0]))
    return low, max(low + 5, _five(n * MINUTES_PER_PART_100[1]))


def estimate(parts: Any, model: Any = None) -> dict[str, Any]:
    """What a person is told before a build of ``parts`` parts: the usual minutes, the
    minutes after which it is stopped, the dollars of their subscription it has used at
    list prices (low, high), and whether the size is beyond the runs on record. With a
    model of ``PRICE_SHARE`` the dollars are that share of Fable's (an estimate)."""
    n = size(parts)
    low, high = minutes(n)
    num, den = PRICE_SHARE.get(str(model or ""), (1, 1))
    dollars = [(n * k * num + 50 * den) // (100 * den) for k in DOLLARS_PER_100_PARTS]
    return {
        "parts": n,
        "minutes": [low, high],
        "stop_minutes": limits(n)["timeout"] // 60,
        "dollars": [max(1, dollars[0]), max(dollars[0] + 1, dollars[1])],
        "estimated": n > LARGEST_ON_RECORD,
    }


def next_size(meta: dict[str, Any]) -> int:
    """The size the next run of a project works at: the parts asked for in a first build,
    the current model's own size in a change."""
    current = meta.get("current")
    now = next((r for r in meta.get("runs") or [] if r.get("n") == current), None)
    if now and isinstance(now.get("parts"), int) and now["parts"] > 0:
        return size(now["parts"])
    return size(meta.get("parts_wanted"))


def time_and_cost(parts: Any, model: Any = None) -> str:
    """The sentence a person reads before a build of ``parts`` parts (as the pages say it),
    for ``model`` (the default when None)."""
    e = estimate(parts, model)
    lo, hi = e["minutes"]
    d0, d1 = e["dollars"]
    if str(model or "") in PRICE_SHARE:
        large = "; no build this large is on record" if e["estimated"] else ""
        return (
            f"A model of about {e['parts']} parts usually takes {lo} to {hi} minutes and is "
            f"stopped at {e['stop_minutes']} minutes; with {model_name(model)} it should use "
            f"about ${d0} to ${d1} of your Claude subscription at list prices, about half what "
            f"builds this size have used with {model_name(None)} (an estimate: its list price "
            f"is half, and one build with it is on record{large})."
        )
    guess = " (an estimate: no build this large is on record)" if e["estimated"] else ""
    return (
        f"A model of about {e['parts']} parts usually takes {lo} to {hi} minutes and is "
        f"stopped at {e['stop_minutes']} minutes; builds this size have used about ${d0} to "
        f"${d1} of your Claude subscription at list prices{guess}."
    )


def task_words(words: str, parts: int | None) -> str:
    """What the AI is asked to build: the person's words and about how many parts. With no
    words (there are pictures or a 3D model): to build what the references show and say
    what it is."""
    words = words.strip()
    if not words:
        words = (
            f"Build {NO_WORDS}. There are no words, so decide what it is from them and say "
            "what it is in your closing words (and in your brief, if you write one)."
        )
    if parts:
        words = words.rstrip(".") + f". About {parts} parts."
    return words


# ---- pictures ----------------------------------------------------------------------------


def draw_pictures(text: str, dest: Path, title: str = "") -> str | None:
    """Draw the sheet, the turntable and the card for model ``text`` into ``dest``
    (``pictures/``). Returns None, or a plain sentence saying why there are no pictures."""
    from PIL import Image

    from bricksnap.lab import picture

    dest.mkdir(parents=True, exist_ok=True)
    try:
        picture.model_sheet(text, dest / "sheet.png", title=title)
        frames = picture.turntable(text, dest, views=TURN_FRAMES)
    except picture.PictureError as e:
        return f"No pictures were drawn: {e}"
    except Exception as e:  # pictures are extras: never lose a model for them
        return f"No pictures were drawn ({type(e).__name__}: {e})."
    with contextlib.suppress(Exception):  # an extra: the model and its other pictures stay
        from bricksnap.lab.joints import opened
        from bricksnap.lab.movement import open_angles

        angles = open_angles(text)  # each only as far as the check says it goes
        if angles:
            picture.model_sheet(opened(text, angles), dest / "opened.png", title="Opened")
    if frames:
        with Image.open(frames[0]) as im:
            shot = im.convert("RGB")
        shot.thumbnail((CARD_PX, CARD_PX * 3 // 4))
        card = Image.new("RGB", (CARD_PX, CARD_PX * 3 // 4), "white")  # 4:3, as the cards are
        card.paste(shot, ((card.width - shot.width) // 2, (card.height - shot.height) // 2))
        card.save(dest / "card.png")
    return None


def reference_sheet(project_folder: Path, out_png: Path) -> Path:
    """Pictures of an ordinary project's 3D model from five sides, in one sheet."""
    from bricksnap.pipeline import load_project_seed
    from bricksnap.project import Project
    from bricksnap.render import contact_sheet, render_seed

    project = Project(project_folder)
    design = project.load_design()
    seed = load_project_seed(project)
    words = {
        "front": "from the front",
        "right": "from the right",
        "back": "from the back",
        "left": "from the left",
        "iso": "from the front right, above",
    }
    items = [
        (said, render_seed(seed, view, design.shape, seed_offset=design.seed_offset))
        for view, said in words.items()
    ]
    title = f"{project.name}: the model to build, from five sides (one square is one stud)"
    contact_sheet(items, columns=3, title=title).save(out_png)
    return out_png


# ---- runs --------------------------------------------------------------------------------


def run_dir(folder: Path, n: int) -> Path:
    return folder / RUNS_DIR / f"{n:04d}"


def next_run(folder: Path) -> int:
    meta = read_meta(folder)
    taken = [r.get("n", 0) for r in meta.get("runs") or [] if isinstance(r, dict)]
    with contextlib.suppress(OSError):
        taken += [int(p.name) for p in (folder / RUNS_DIR).iterdir() if p.name.isdigit()]
    return max(taken, default=0) + 1


def _use(folder: Path, n: int) -> None:
    """Copy run ``n``'s files to the top of the project, as the current model."""
    src = run_dir(folder, n)
    for name in CURRENT_FILES:
        if (src / name).is_file():
            shutil.copyfile(src / name, folder / f".{name}.tmp")
            os.replace(folder / f".{name}.tmp", folder / name)
        else:
            with contextlib.suppress(FileNotFoundError):
                (folder / name).unlink()
    pics = folder / PICTURES_DIR
    tmp = folder / f".{PICTURES_DIR}.tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    if (src / PICTURES_DIR).is_dir():
        shutil.copytree(src / PICTURES_DIR, tmp)
    else:
        tmp.mkdir()
    old = folder / f".{PICTURES_DIR}.old"
    shutil.rmtree(old, ignore_errors=True)
    if pics.exists():
        os.replace(pics, old)
    os.replace(tmp, pics)
    shutil.rmtree(old, ignore_errors=True)


def keep_model(
    folder: Path,
    n: int,
    *,
    kind: str,
    words: str,
    text: str,
    report: str | None,
    notes: str = "",
    record: dict[str, Any] | None = None,
    sheet: Path | None = None,
) -> dict[str, Any]:
    """Keep model ``text`` as run ``n`` (its files and pictures), make it the current one,
    and add its entry to project.json. Returns the entry."""
    from bricksnap.designer.runner import redact

    dest = run_dir(folder, n)
    dest.mkdir(parents=True, exist_ok=True)
    if report is None:
        report = check_text(text)
    parts, kinds = count_parts(text)
    verdict = read_summary(report)
    _write(dest / "model.ldr", text)
    _write(dest / "report.txt", report.rstrip("\n") + "\n")
    notes = redact(notes).strip()
    if notes:
        _write(dest / "notes.txt", notes + "\n")
    _write(dest / "parts.csv", parts_csv(text))
    title = f"Run {n}: {verdict['summary']}" if verdict["summary"] else ""
    problem = draw_pictures(text, dest / PICTURES_DIR, title=title or "")
    if sheet is not None and sheet.is_file() and not (dest / PICTURES_DIR / "sheet.png").is_file():
        shutil.copyfile(sheet, dest / PICTURES_DIR / "sheet.png")
    rec = record or {}
    entry = {
        "n": n,
        "kind": kind,
        "words": words,
        "created": time.time(),
        "ok": bool(rec.get("ok", True)),
        "error": redact(str(rec.get("error") or "")),
        "has_model": parts > 0,
        "parts": parts,
        "kinds": kinds,
        **verdict,
        "moves": read_movement(report),
        "seconds": rec.get("seconds"),
        "turns": rec.get("turns"),
        "cost_usd_reported": rec.get("cost_usd_reported"),
        "model": rec.get("model") if isinstance(rec.get("model"), str) else None,
        "pictures": problem is None,
        "picture_problem": problem,
        **_guide_fields(rec),
        "looks": measure_looks(text),
    }
    _write(dest / "record.json", json.dumps(entry, indent=1) + "\n")
    _use(folder, n)
    meta = read_meta(folder)
    meta["runs"] = [r for r in meta.get("runs") or [] if r.get("n") != n] + [entry]
    meta["current"] = n
    save_meta(folder, meta)
    return entry


def _guide_fields(record: dict[str, Any]) -> dict[str, Any]:
    """Whether a run had the guide, and which playbook it asked for, from its record."""
    guide = record.get("guide")
    playbook = record.get("playbook")
    return {
        "guide": guide if isinstance(guide, bool) else None,
        "playbook": playbook if isinstance(playbook, str) else None,
        **_art_fields(record),
    }


ART_KEYS = (
    "art",
    "brief",
    "brief_story",
    "critique",
    "critiques",
    "first_no",
    "built_without_brief",
    "ended_without_critique",
)


def _art_fields(record: dict[str, Any]) -> dict[str, Any]:
    """A guided run's art direction (``lab.art.record``): its last brief and the story of
    its versions, its critique, and the flags; nothing for a run without them (an older run
    keeps its entry as it was)."""
    if record.get("art") is not True:
        return {}
    brief, critique = record.get("brief"), record.get("critique")
    briefs = [b for b in record.get("briefs") or [] if isinstance(b, dict)]
    story = None
    if briefs:
        first, last = briefs[0], briefs[-1]
        story = {
            "versions": len(briefs),
            "carried_from": first.get("from_run") if first.get("carried") else None,
            "carried": bool(first.get("carried")),
            "parts_before": first.get("parts_before"),
            "last_reason": last.get("reason"),
        }
    first_no = record.get("first_no")
    return {
        "art": True,
        "brief": brief if isinstance(brief, dict) else None,
        "brief_story": story,
        "critique": critique if isinstance(critique, dict) else None,
        "critiques": record.get("critiques") if isinstance(record.get("critiques"), int) else 0,
        "first_no": first_no if isinstance(first_no, list) else None,
        "built_without_brief": record.get("built_without_brief") is True,
        "ended_without_critique": not isinstance(critique, dict),
    }


def measure_looks(text: str) -> dict[str, Any] | None:
    """How the model looks (``looks.record``), or None when it cannot be measured."""
    from bricksnap.lab import looks

    got = looks.measure_text(text)
    return looks.record(got) if got is not None else None


def check_text(text: str) -> str:
    """The checker's report on ``text``, or a short note when the library is not here."""
    try:
        from bricksnap.lab.validate import check

        return check(text).text()
    except (FileNotFoundError, OSError) as e:
        return f"SUMMARY: not checked ({e})"


def adopt(folder: Path, n: int, work: Path, kind: str, words: str) -> dict[str, Any]:
    """Keep the lab work folder ``work`` as run ``n``. A run that left no model is listed
    (``has_model`` false) but does not change the current model."""
    from bricksnap.designer.runner import redact

    try:
        record = json.loads((work / "session.json").read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            record = {}
    except (OSError, ValueError):
        record = {}
    text = _read(work / "final.ldr") or _read(work / "model.ldr")
    if count_parts(text)[0] == 0:
        entry = {
            "n": n,
            "kind": kind,
            "words": words,
            "created": time.time(),
            "ok": False,
            "error": redact(str(record.get("error") or "The builder made no model.")),
            "has_model": False,
            "parts": 0,
            "kinds": 0,
            "summary": "",
            "clean": None,
            "problems": None,
            "unchecked": None,
            "seconds": record.get("seconds"),
            "turns": record.get("turns"),
            "cost_usd_reported": record.get("cost_usd_reported"),
            "model": record.get("model") if isinstance(record.get("model"), str) else None,
            "pictures": False,
            "picture_problem": None,
            **_guide_fields(record),
        }
        run_dir(folder, n).mkdir(parents=True, exist_ok=True)
        _write(run_dir(folder, n) / "record.json", json.dumps(entry, indent=1) + "\n")
        meta = read_meta(folder)
        meta["runs"] = [r for r in meta.get("runs") or [] if r.get("n") != n] + [entry]
        save_meta(folder, meta)
        return entry
    report = _read(work / "final-report.txt") or None
    return keep_model(
        folder,
        n,
        kind=kind,
        words=words,
        text=text,
        report=report,
        notes=str(record.get("closing_words") or ""),
        record=record,
        sheet=work / "final.png",
    )


def build(
    folder: Path,
    words: str | None = None,
    on_say: Callable[[str], None] | None = None,
    references: list[Path] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """One AI session: the first build from the project's words, or ``words`` as a change
    to the current model. Keeps the run and returns its entry. ``references`` (default: the
    project's own, ``references``) are shown to the AI; ``model``, when given, becomes the
    project's model before the run."""
    from bricksnap.lab import run as lab_run

    say = on_say or (lambda line: None)
    meta = read_meta(folder)
    current = meta.get("current")
    refs = references_of(folder) if references is None else list(references)
    start = folder / "model.ldr" if current is not None else None
    if start is not None and not start.is_file():
        start = None
    if start is None:
        kind, change_of = "first", None
        asked = clean(words or "", MAX_WORDS) or str(meta.get("words") or "")
        task = task_words(asked, meta.get("parts_wanted"))
        if not asked and not refs:
            raise FreeBuildError("Say what to build.")
    else:
        asked = clean(words or "", MAX_WORDS)
        if not asked:
            raise FreeBuildError('Say what to change, for example "make the roof blue".')
        kind, change_of, task = "change", str(meta.get("words") or "") or NO_WORDS, asked
    if model and model != meta.get("model"):  # the model asked for now is kept from now on
        meta["model"] = model
        save_meta(folder, meta)
    n = next_run(folder)
    work = run_dir(folder, n) / "work"
    work.parent.mkdir(parents=True, exist_ok=True)
    say("The builder is getting ready: preparing the parts index")
    hear = Progress(work, say)
    options: dict[str, Any] = {}
    if meta.get("model"):
        options["model"] = str(meta["model"])
    now = next((r for r in meta.get("runs") or [] if r.get("n") == current), None) or {}
    parts = size(meta.get("parts_wanted")) if kind == "first" else next_size(meta)
    allowed = limits(parts)
    if meta.get("guide") is True:  # the art direction (``lab.art``)
        options["parts"] = parts
        if kind == "change" and isinstance(now.get("brief"), dict):
            options["brief"], options["brief_run"] = now["brief"], current
    try:
        record = lab_run.build(
            task,
            work,
            effort=EFFORT,
            max_turns=allowed["max_turns"],
            max_checks=allowed["max_checks"],
            timeout=allowed["timeout"],
            references=refs,
            start=start,
            change_of=change_of,
            on_event=hear,
            guide=meta.get("guide") is True,
            **options,
        )
    except SystemExit as e:  # the lab's own refusals are plain sentences
        raise FreeBuildError(str(e.code)) from None
    except FileNotFoundError as e:  # the parts library went missing
        raise FreeBuildError(str(e)) from None
    say("The builder has stopped. Drawing the pictures of what it built")
    entry = adopt(folder, n, work, kind, asked)
    used = str(meta.get("model") or DEFAULT_MODEL)
    if record.get("usage_limit"):
        at = record.get("limit_resets_at")
        at = float(at) if isinstance(at, int | float) and not isinstance(at, bool) else None
        error = usage_limit_error(used, str(record.get("limit_resets") or ""), entry, kind, at)
        note_limit(folder.parent, error)
        raise error
    if record.get("ok"):
        clear_limit(folder.parent, used)
    if not entry["has_model"]:
        raise FreeBuildError(
            f"The builder did not make a model: {entry['error'] or 'it stopped.'} Nothing was "
            "changed."
        )
    if not record.get("ok"):
        error = entry["error"] or "it stopped without saying why."
        raise FreeBuildError(
            f"The builder did not finish: {error} What it built is kept as run {n}"
            + (" and shown now; the earlier runs are still in the list." if n > 1 else ".")
        )
    return entry


def usage_limit_error(
    model: str, resets: str, entry: dict[str, Any], kind: str, resets_at: float | None = None
) -> UsageLimitError:
    """What a person is told when the subscription's usage limit stopped run ``entry``."""
    other = other_model(model)
    said = f"Your Claude subscription has reached its usage limit for {model_name(model)}"
    said += f"; it resets {resets}." if resets else ". Claude Code did not say when it resets."
    if entry.get("has_model"):
        said += f" What it built is kept as run {entry['n']}."
    else:
        said += " Nothing was built." if kind == "first" else " Nothing was changed."
    if other:
        said += (
            f" You can choose {model_name(other)} instead and try again, or wait until the "
            "limit resets; BrickSnap does not switch by itself."
        )
    else:
        said += " Try again once the limit has reset."
    return UsageLimitError(said, model, other, resets, resets_at)


# ---- usage limits remembered for the projects folder -------------------------------------


def _limits_file(projects_dir: Path) -> Path:
    return projects_dir / STATE_DIR / LIMITS_FILE


def _read_limits(projects_dir: Path) -> dict[str, Any]:
    try:
        data = json.loads(_limits_file(projects_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def note_limit(projects_dir: Path, error: UsageLimitError) -> None:
    """Remember that ``error.model`` is at its usage limit, and until when. Never fails."""
    data = _read_limits(projects_dir)
    data[error.model] = {"until": error.resets_at, "resets": error.resets, "seen": time.time()}
    with contextlib.suppress(OSError):
        _write(_limits_file(projects_dir), json.dumps(data, indent=1) + "\n")


def clear_limit(projects_dir: Path, model: str) -> None:
    """Forget a usage limit of ``model`` (a run with it has finished). Never fails."""
    data = _read_limits(projects_dir)
    if data.pop(model, None) is not None:
        with contextlib.suppress(OSError):
            _write(_limits_file(projects_dir), json.dumps(data, indent=1) + "\n")


def _until_words(at: float) -> str:
    """'1 Dec, 2am' or '1 Dec, 2:30pm', on this computer's clock."""
    from datetime import datetime

    t = datetime.fromtimestamp(at)
    hour = t.hour % 12 or 12
    minutes = f":{t.minute:02d}" if t.minute else ""
    return f"{t.day} {t:%b}, {hour}{minutes}{'am' if t.hour < 12 else 'pm'}"


def usage_limits(projects_dir: Path, now: float | None = None) -> list[dict[str, Any]]:
    """The models of ``MODELS`` still at a usage limit a run reported: each ``{"model",
    "name", "until" (seconds since 1970, or None), "until_words" ("1 Dec, 2am", or Claude
    Code's own words), "other", "other_name"}``. A limit without a time counts for
    ``LIMIT_GUESS_S`` after it was seen."""
    now = time.time() if now is None else now
    out = []
    for model, seen in _read_limits(projects_dir).items():
        if model not in MODELS or not isinstance(seen, dict):
            continue
        until = seen.get("until")
        until = float(until) if isinstance(until, int | float) else None
        stamp = seen.get("seen")
        stamp = float(stamp) if isinstance(stamp, int | float) else 0.0
        over = now >= until if until is not None else now >= stamp + LIMIT_GUESS_S
        if over:
            continue
        other = other_model(model)
        words = _until_words(until) if until is not None else str(seen.get("resets") or "")
        out.append(
            {
                "model": model,
                "name": model_name(model),
                "until": until,
                "until_words": words,
                "other": other,
                "other_name": model_name(other) if other else None,
            }
        )
    return out


# ---- an outside eye, and polishing with what it asks for ----------------------------------


class NothingToPolish(FreeBuildError):
    """The outside eye asked for no fix, so no change was made; its critique is ``critique``."""

    def __init__(self, message: str, critique: dict[str, Any]) -> None:
        super().__init__(message)
        self.critique = critique


_CRITIC_VIEWS = {
    0: "from the front-left, a little above",
    3: "from the front-right, a little above",
    6: "from the back-right, a little above",
    9: "from the back-left, a little above",
}


def critic_inputs(folder: Path) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]], str]:
    """Everything the outside eye is shown of the current model, and nothing else: its
    pictures (the sheet and four of the turn views, ``CRITIC_VIEWS``), the reference pictures
    (``references_of``), and the message (``critic.message``: the words it was built from,
    the person's changes since, the brief's lines and the HOW IT LOOKS lines)."""
    from bricksnap.lab import critic

    meta = read_meta(folder)
    current = meta.get("current")
    runs = [r for r in meta.get("runs") or [] if isinstance(r, dict)]
    now = next((r for r in runs if r.get("n") == current), None) or {}
    pics = folder / PICTURES_DIR
    pictures: list[tuple[Path, str]] = []
    if (pics / "sheet.png").is_file():
        pictures.append(
            (
                pics / "sheet.png",
                "a sheet of three views: from the front-left above, from the back-right above, "
                "and straight from the front",
            )
        )
    for k in CRITIC_VIEWS:
        if (pics / f"turn-{k:02d}.png").is_file():
            pictures.append((pics / f"turn-{k:02d}.png", _CRITIC_VIEWS.get(k, f"view {k + 1}")))
    if not pictures:
        raise FreeBuildError(
            "This model has no pictures, so an outside eye has nothing to look at. Nothing was "
            "changed."
        )
    references = []
    for path in references_of(folder):
        if path.name == MODEL_SHEET:
            said = "the 3D model the person gave, drawn from five sides"
        elif path.name == REFERENCE_SHEET:
            said = "the 3D model of one of their models it should look like, from five sides"
        else:
            said = "a picture the person gave of what to build"
        references.append((path, said))
    changes = [
        _short(str(r.get("words") or ""), 300)
        for r in runs
        if r.get("kind") == "change"
        and not r.get("polish")
        and str(r.get("words") or "").strip()
        and isinstance(r.get("n"), int)
        and isinstance(current, int)
        and r["n"] <= current
    ][-MAX_CHANGES_SHOWN:]
    brief = ""
    if isinstance(now.get("brief"), dict):
        with contextlib.suppress(Exception):  # a damaged brief is simply not shown
            from bricksnap.lab.art import brief_lines

            brief = brief_lines(now["brief"])
    text = critic.message(
        str(meta.get("words") or ""), changes, brief, _critic_looks(folder, now), len(references)
    )
    return pictures, references, text


def _critic_looks(folder: Path, now: dict[str, Any]) -> str:
    """The HOW IT LOOKS lines for the current run (``looks.section``), or ""."""
    import dataclasses

    from bricksnap.lab import looks

    rec = now.get("looks") if isinstance(now.get("looks"), dict) else None
    if rec is None and now.get("has_model"):
        rec = remembered_looks(folder / "model.ldr")
    if not rec:
        return ""
    try:
        got = looks.Looks(**{f.name: rec[f.name] for f in dataclasses.fields(looks.Looks)})
        return looks.section(got)
    except Exception:  # advice only: a record that cannot be read is not shown
        return ""


def critique(
    folder: Path, on_say: Callable[[str], None] | None = None, model: str | None = None
) -> dict[str, Any]:
    """An outside eye on the current model: one short clean-room session (``lab.critic``)
    shown only ``critic_inputs``, with the project's model (or ``model``). Keeps what it was
    shown and its transcript in ``runs/NNNN/critic/`` and its answer in
    ``runs/NNNN/critique.json`` (the run it looked at) and returns that: ``{"run", "fixes":
    [{"where", "fix"}, ...], "keep", "model", "created", "seconds", "turns",
    "cost_usd_reported", "shown"}``. Raises ``FreeBuildError`` when there is no model or no
    list came back, ``UsageLimitError`` at the usage limit; nothing is changed either way."""
    from bricksnap.lab import critic

    say = on_say or (lambda line: None)
    meta = read_meta(folder)
    current = meta.get("current")
    now = next(
        (r for r in meta.get("runs") or [] if isinstance(r, dict) and r.get("n") == current), None
    )
    if not isinstance(current, int) or not now or not (folder / "model.ldr").is_file():
        raise FreeBuildError(
            "There is no model here yet, so there is nothing for an outside eye to look at. "
            "Build it first."
        )
    pictures, references, text = critic_inputs(folder)
    used = str(model or meta.get("model") or DEFAULT_MODEL)
    dest = run_dir(folder, current) / CRITIC_DIR
    critic.prepare(dest, pictures, references)
    say(
        "An outside eye looks at the model: only its pictures, the words it was built from, its "
        "art direction and how it measures, never how it was built"
    )

    def hear(event: dict[str, Any]) -> None:
        for line in critic.progress(event):
            say(line)

    done = critic.run(dest, text, model=used, effort=CRITIC_EFFORT, on_event=hear)
    if done.usage_limit:
        error = usage_limit_error(
            used, done.limit_resets, {"has_model": False}, "change", done.limit_resets_at
        )
        note_limit(folder.parent, error)
        raise error
    answer = critic.read_answer(dest)
    if not done.ok or answer is None:
        why = done.error or "it stopped without giving its list."
        raise FreeBuildError(f"The outside eye did not give its list: {why} Nothing was changed.")
    clear_limit(folder.parent, used)
    found = {
        "run": current,
        "fixes": answer["fixes"],
        "keep": answer["keep"],
        "model": used,
        "created": time.time(),
        "seconds": round(done.duration_s, 1),
        "turns": done.turns,
        "cost_usd_reported": done.cost_usd,
        "shown": {"pictures": [said for _, said in pictures], "references": len(references)},
    }
    _write(run_dir(folder, current) / CRITIQUE_FILE, json.dumps(found, indent=1) + "\n")
    return found


POLISH_HEAD = (
    "An outside eye looked at the model's pictures and asked for these fixes, the most visible "
    "first:"
)
POLISH_TAIL = "Keep everything else as it is; then look from every side and hand it in."


def polish_words(found: dict[str, Any]) -> str:
    """The change a polish asks for: the critic's fixes, numbered, what to keep, and
    ``POLISH_TAIL``. The critic's limits keep it within ``MAX_WORDS``."""

    def sentence(text: str) -> str:
        text = text.strip()
        return text if text.endswith((".", "!", "?")) else text + "."

    lines = [POLISH_HEAD]
    for k, f in enumerate(found.get("fixes") or [], 1):
        where = str(f["where"]).strip()
        lines.append(f"{k}. {where[:1].upper() + where[1:]}: {sentence(str(f['fix']))}")
    keep = str(found.get("keep") or "").strip()
    if keep:
        lines.append(f"What already works, and must be kept: {sentence(keep)}")
    lines.append(POLISH_TAIL)
    return "\n".join(lines)


def polish(
    folder: Path,
    on_say: Callable[[str], None] | None = None,
    *,
    on_critique: Callable[[dict[str, Any]], None] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """``critique``, then one change run (``build``) whose words are ``polish_words``. The new
    run's entry gets ``"polish"``: ``{"of_run", "fixes", "keep", "model", "seconds",
    "cost_usd_reported"}`` (the critique; also when the change stopped part way, if it kept a
    run). ``on_critique`` gets the critique as soon as it exists. Returns the entry. When the
    critic asked for no fix, raises ``NothingToPolish`` and changes nothing."""
    say = on_say or (lambda line: None)
    found = critique(folder, on_say=say, model=model)
    if on_critique is not None:
        with contextlib.suppress(Exception):  # showing it must never stop the work
            on_critique(found)
    fixes = found["fixes"]
    if not fixes:
        raise NothingToPolish(
            "The outside eye found nothing it would change, so the model was not changed. What "
            f"it said works: {found['keep']}",
            found,
        )
    say(
        f"An outside eye asked for {len(fixes)} fix{'' if len(fixes) == 1 else 'es'}. The "
        "builder now makes them and keeps the rest"
    )
    attached = {
        "of_run": found["run"],
        "fixes": fixes,
        "keep": found["keep"],
        "model": found["model"],
        "seconds": found["seconds"],
        "cost_usd_reported": found["cost_usd_reported"],
    }
    n = next_run(folder)
    try:
        entry = build(folder, polish_words(found), on_say=say, model=model)
    finally:
        _attach_polish(folder, n, attached)
    return {**entry, "polish": attached}


def _attach_polish(folder: Path, n: int, attached: dict[str, Any]) -> None:
    """Add ``attached`` as ``"polish"`` to run ``n``'s entry and record, when it was kept."""
    with contextlib.suppress(FreeBuildError, OSError, ValueError):
        meta = read_meta(folder)
        runs = [r for r in meta.get("runs") or [] if isinstance(r, dict) and r.get("n") == n]
        if not runs:
            return
        for r in runs:
            r["polish"] = attached
        save_meta(folder, meta)
        record = run_dir(folder, n) / "record.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data["polish"] = attached
            _write(record, json.dumps(data, indent=1) + "\n")


def critic_time_and_cost() -> str:
    """What a person is told about the outside eye's run (an estimate)."""
    lo, hi = CRITIC_MINUTES
    return (
        f"The outside eye is one short AI run: usually {lo} to {hi} minutes and under "
        f"${CRITIC_DOLLARS} of your Claude subscription (an estimate: no run of it is on record "
        "yet)."
    )


def polish_time_and_cost(parts: Any, model: Any = None) -> str:
    """The sentences a person reads before polishing a model of ``parts`` parts (as the page
    says them): the outside eye's run, then one change (``time_and_cost``)."""
    return (
        critic_time_and_cost() + " Then one change makes its fixes. " + time_and_cost(parts, model)
    )


def polish_estimate(parts: Any, model: Any = None, after_build: bool = False) -> dict[str, Any]:
    """The AI runs, minutes and dollars of a polish (the outside eye and one change of a model
    of ``parts`` parts), or with ``after_build`` of a first build polished once: whole-number
    arithmetic on ``estimate``, as ``viewer/app.js`` does it."""
    e = estimate(parts, model)
    k = 2 if after_build else 1
    (lo, hi), (d0, d1) = e["minutes"], e["dollars"]
    return {
        "parts": e["parts"],
        "runs": k + 1,
        "minutes": [k * lo + CRITIC_MINUTES[0], k * hi + CRITIC_MINUTES[1]],
        "dollars": [k * d0, k * d1 + CRITIC_DOLLARS],
    }


def import_run(
    projects_dir: Path, source: Path, *, name: str | None = None, words: str | None = None
) -> Path:
    """A new free-build project from a finished lab run folder or one .ldr file."""
    source = Path(source)
    record: dict[str, Any] = {}
    sheet = None
    if source.is_dir():
        text = _read(source / "final.ldr") or _read(source / "model.ldr")
        report = _read(source / "final-report.txt") or None
        with contextlib.suppress(OSError, ValueError):
            loaded = json.loads((source / "session.json").read_text(encoding="utf-8"))
            record = loaded if isinstance(loaded, dict) else {}
        sheet = source / "final.png"
        default_name = source.name
    elif source.is_file():
        text = _read(source)
        beside = source.with_name(f"{source.stem}-report.txt")
        report = _read(beside) or None
        png = source.with_suffix(".png")
        sheet = png if png.is_file() else None
        default_name = source.stem
    else:
        raise FreeBuildError(f"{source} was not found.")
    if count_parts(text)[0] == 0:
        raise FreeBuildError(f"{source} holds no model (no part lines).")
    said = clean(words or str(record.get("task") or ""), MAX_WORDS) or default_name
    path = create(
        projects_dir,
        said,
        name=name or name_from(said),
        parts=None,
        model=record.get("model"),
    )
    keep_model(
        path,
        1,
        kind="imported",
        words=said,
        text=text,
        report=report,
        notes=str(record.get("closing_words") or ""),
        record=record,
        sheet=sheet,
    )
    return path


def restore(folder: Path, n: int) -> dict[str, Any]:
    """Make run ``n`` the current one again. Returns its entry."""
    meta = read_meta(folder)
    entry = next((r for r in meta.get("runs") or [] if r.get("n") == n), None)
    if entry is None:
        raise FreeBuildError(f"This model has no run {n}, so nothing was changed.")
    if not entry.get("has_model") or not (run_dir(folder, n) / "model.ldr").is_file():
        raise FreeBuildError(f"Run {n} made no model, so there is nothing to bring back.")
    _use(folder, n)
    meta["current"] = n
    save_meta(folder, meta)
    return entry


def turn_frames(folder: Path) -> list[str]:
    """The turntable's pictures that exist, as paths inside the project, in order."""
    out = []
    for k in range(TURN_FRAMES):
        rel = f"{PICTURES_DIR}/turn-{k:02d}.png"
        if (folder / rel).is_file():
            out.append(rel)
    return out


def describe(folder: Path, measure_missing: bool = False) -> dict[str, Any]:
    """What a page or the command line shows about a free-build project."""
    meta = read_meta(folder)
    runs = [r for r in meta.get("runs") or [] if isinstance(r, dict)]
    current = meta.get("current")
    now = next((r for r in runs if r.get("n") == current), None) or {}
    pics = folder / PICTURES_DIR
    rec = now.get("looks") if isinstance(now.get("looks"), dict) else None
    if rec is None and measure_missing and now.get("has_model"):
        rec = remembered_looks(folder / "model.ldr")
    return {
        "kind": KIND,
        "experimental": True,
        "name": str(meta.get("name") or folder.name),
        "words": str(meta.get("words") or ""),
        "parts_wanted": meta.get("parts_wanted"),
        "reference": meta.get("reference"),
        "reference_pictures": [
            f"{REFS_DIR}/{p.name}" for p in references_of(folder) if p.name.startswith("picture-")
        ],
        "reference_model": _model_reference(folder, meta),
        "model": meta.get("model") if isinstance(meta.get("model"), str) else None,
        "guide": meta.get("guide") is True,
        "parts": now.get("parts"),
        "kinds": now.get("kinds"),
        "summary": now.get("summary") or "",
        "clean": now.get("clean"),
        "problems": now.get("problems"),
        "unchecked": now.get("unchecked"),
        "moves": list(now.get("moves") or []),
        "looks": rec,
        "looks_lines": _looks_lines(rec),
        **{k: now.get(k) for k in ART_KEYS},
        "polish": now.get("polish") if isinstance(now.get("polish"), dict) else None,
        "current_run": current,
        "runs": runs,
        "notes": _read(folder / "notes.txt").strip(),
        "report": _read(folder / "report.txt").strip(),
        "turntable": turn_frames(folder),
        "card": f"{PICTURES_DIR}/card.png" if (pics / "card.png").is_file() else None,
        "sheet": f"{PICTURES_DIR}/sheet.png" if (pics / "sheet.png").is_file() else None,
        "opened": f"{PICTURES_DIR}/opened.png" if (pics / "opened.png").is_file() else None,
        "picture_problem": now.get("picture_problem"),
        "files": [f for f in ("model.ldr", "parts.csv", "report.txt") if (folder / f).is_file()],
        "created": meta.get("created"),
    }


def _model_reference(folder: Path, meta: dict[str, Any]) -> dict[str, Any] | None:
    """The 3D model file a project was built from: its name as the person gave it and the
    path of its sheet (or None when the sheet is not there)."""
    kept = meta.get("reference_model")
    if not isinstance(kept, dict):
        return None
    sheet = folder / REFS_DIR / MODEL_SHEET
    return {
        "name": str(kept.get("name") or kept.get("file") or "a 3D model"),
        "sheet": f"{REFS_DIR}/{MODEL_SHEET}" if sheet.is_file() else None,
    }


_LOOKS_SEEN: dict[tuple[str, int, int], dict[str, Any] | None] = {}


def remembered_looks(model: Path) -> dict[str, Any] | None:
    """How a model kept before runs had a ``looks`` record looks, measured once per process
    for each version of the file (its path, size and modification time); None when it cannot
    be read or measured. Nothing is written."""
    try:
        st = model.stat()
        key = (str(model.resolve()), st.st_size, st.st_mtime_ns)
    except OSError:
        return None
    if key not in _LOOKS_SEEN:
        try:
            _LOOKS_SEEN[key] = measure_looks(model.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # advice only: a model that cannot be measured shows nothing
            _LOOKS_SEEN[key] = None
    return _LOOKS_SEEN[key]


def _looks_lines(rec: Any) -> list[str]:
    from bricksnap.lab import looks

    return looks.page_lines(rec) if isinstance(rec, dict) else []


# ---- progress ----------------------------------------------------------------------------


TOOL_WORDS = {
    "part_info": "The builder is reading about a part",
    "model": "The builder is reading its model line by line",
    "look": "The builder is looking at its model from another side",
    "reference": "The builder is looking at the reference pictures",
    "brief": "The builder is writing its art direction",
    "hand-in sheet": "The builder is looking at its model beside its art direction, to hand it in",
}


class Progress:
    """Plain sentences for one session's stream-json events (see the module's contract)."""

    def __init__(self, work: Path, say: Callable[[str], None]) -> None:
        self.work = work
        self.say = say
        self.pending: dict[str, str] = {}

    def _parts(self) -> int:
        return count_parts(_read(self.work / "model.ldr"))[0]

    def _check_line(self) -> str | None:
        attempts = sorted((self.work / "attempts").glob("attempt-*-report.txt"))
        attempts = [a for a in attempts if a.name != "attempt-000-report.txt"]
        if not attempts:
            return None
        verdict = read_summary(_read(attempts[-1]))
        n = len(attempts)
        if verdict["clean"]:
            return f"Check {n}: no problems"
        if verdict["problems"]:
            return f"Check {n}: {_plural(verdict['problems'], 'problem')} to fix"
        return f"Check {n}: nothing to check yet"

    def __call__(self, event: dict[str, Any]) -> None:
        from bricksnap.designer.runner import TOOL_PREFIX, StreamParser, _tool_result_text, redact

        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            self.say("The builder has started")
            return
        for item in StreamParser._content(event):
            if kind == "assistant" and item.get("type") == "tool_use":
                name = str(item.get("name", "")).removeprefix(TOOL_PREFIX)
                raw = item.get("input")
                args: dict[str, Any] = raw if isinstance(raw, dict) else {}
                if name == "submit" and "ldraw" not in args:  # guide mode's hand-in
                    name = "hand-in" if "critique" in args else "hand-in sheet"
                self.pending[str(item.get("id", ""))] = name
                if name == "search_parts":
                    query = _short(redact(str(args.get("query") or "")), 60)
                    self.say(f"The builder is looking for parts: {query}")
                elif name in TOOL_WORDS:
                    self.say(TOOL_WORDS[name])
            elif kind == "assistant" and item.get("type") == "text":
                said = str(item.get("text") or "").strip()
                if said:
                    self.say("The builder says: " + _short(redact(said)))
            elif kind == "user" and item.get("type") == "tool_result":
                name = self.pending.pop(str(item.get("tool_use_id", "")), "")
                text = _tool_result_text(item).lstrip()
                if name == "hand-in" and text.startswith("Your critique was not recorded"):
                    self.say(TOOL_WORDS["hand-in sheet"])  # it was given the sheet instead
                if name == "hand-in" and not text.startswith("Critique recorded"):
                    name = ""
                self._after(name, bool(item.get("is_error")) or text.startswith("ERROR:"))

    def _after(self, name: str, failed: bool) -> None:
        if name == "hand-in":
            if not failed:
                self.say("The builder handed in its critique of its own pictures")
            return
        if name in ("check", "submit"):
            line = self._check_line()
            if line:
                self.say(line)
            return
        if failed or name not in ("place", "add", "remove", "remove_box", "fill", "mirror"):
            return
        n = self._parts()
        if name == "place":
            self.say(f"It placed a part ({n:,} so far)")
        elif name == "add":
            self.say(f"It added parts by position ({n:,} so far)")
        elif name == "fill":
            self.say(f"It filled a space with bricks ({n:,} so far)")
        elif name == "mirror":
            self.say(f"It copied one side to the other ({n:,} so far)")
        else:
            self.say(f"It took parts away ({n:,} left)")
