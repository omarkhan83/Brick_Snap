"""Free-build projects: models an AI built itself from the whole parts library (EXPERIMENTAL).

The lab (``bricksnap.lab.run``) runs one AI session in a work folder. This module turns such
sessions into projects a person keeps: in the same projects folder as the models made from a
3D file, with the current model, its checker report, the AI's own notes, the parts list and
pictures, and every run kept so an earlier one can be brought back. It holds no web code, so
the command line (``bricksnap make``) and the web app use the same functions.

CONTRACT (tests in tests/test_freebuild.py; no test starts a real AI session: ``lab.run.build``
is replaced, and pictures are drawn by stand-ins for ``picture.model_sheet`` and
``picture.turntable``)

A free-build project is a folder ``<projects>/<slug>/`` holding:

    project.json   {"kind": "free", "experimental": true, "name", "words" (what the person
                   typed), "parts_wanted" (or null), "reference" (the folder name of the
                   project whose pictures the AI was shown, or null), "model" (the AI model
                   asked for, or null), "created" (seconds since 1970), "runs": [...],
                   "current": the number of the run shown now, or null}
    model.ldr      the current model, as the AI left it (LDraw; BrickLink Studio, LeoCAD
                   and LDView open it; removed parts are "0 removed: ..." comment lines, so
                   the line numbers in the report still match)
    report.txt     the lab checker's full report on it
    notes.txt      the AI's closing words (through ``runner.redact``)
    parts.csv      the parts list: part, description, colour, colour_name, quantity (one row
                   per part in one colour; the description and colour name come from the
                   LDraw library and are left empty when it is not on this computer)
    pictures/      card.png (the home page's card, 4:3), sheet.png (three views), turn-00.png to
                   turn-11.png (twelve views round the model, from the front-left on)
    runs/NNNN/     each run (the first build, each change, an imported model): the same
                   files, record.json (what the run entry says), and for a run made here
                   work/, the lab's work folder (attempts, calls.jsonl, the redacted
                   transcript). Nothing in work/ is ever shown by the web app.

A run entry (``project.json`` "runs", oldest first) is ``{"n", "kind": "first" | "change" |
"imported", "words", "created", "ok", "error", "has_model", "parts", "kinds", "summary",
"clean", "problems", "unchecked", "seconds", "turns", "cost_usd_reported", "pictures"
(whether they were drawn), "picture_problem"}``. ``summary`` is the checker's one-line
summary; ``clean`` is true when it found no problems; ``unchecked`` counts the joints it
could not confirm (clips, bars, pins, axles: counted as joined without proof).

Functions
- ``is_free(folder)``: whether a project folder is a free-build project (never raises).
- ``create(projects_dir, words, name=..., parts=..., reference=..., model=..., folder=...)``:
  a new project with no runs yet; the folder is ``folder`` when given (it must not exist),
  else ``slug(name or words)`` made unique with a number. Words and names are cut to
  ``MAX_WORDS`` and ``MAX_NAME`` characters, control characters removed.
- ``build(folder, words=None, on_say=None, references=None)``: runs one lab session into
  the next ``runs/NNNN/work`` and keeps what it made (``adopt``): the first build from the
  project's words when it has no model yet, otherwise ``words`` is a change to the current
  model (``lab.run.build`` with ``start`` and ``change_of``). ``on_say`` gets the progress
  as plain sentences (``Progress``). Returns the run entry; raises ``FreeBuildError`` when
  the session could not start or made no model, after keeping the run's entry.
- ``adopt(folder, n, work, kind, words)``: keep lab work folder ``work`` as run ``n``; when it
  holds a model, the run's files and pictures are written and it becomes the current one.
- ``import_run(projects_dir, source, name=None, words=None)``: a new project from a
  finished lab run folder (final.ldr, final-report.txt, session.json, final.png) or from
  one .ldr file (with ``<stem>-report.txt`` beside it, when there is one; otherwise the
  checker is run when the library is here). Only those files are copied: never a
  transcript or calls.jsonl.
- ``restore(folder, n)``: make run ``n`` the current one again (its files copied back to the
  top of the folder); the other runs stay.
- ``describe(folder)``: everything a page or the command line shows about the project.
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
import os
import re
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bricksnap.project import slug

KIND = "free"
MAX_WORDS = 2000
MAX_NAME = 80
MIN_PARTS, MAX_PARTS, DEFAULT_PARTS = 20, 300, 80
MAX_TURNS = 90
MAX_CHECKS = 25
TIMEOUT_S = 5400
EFFORT = "high"
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
) -> Path:
    """A new free-build project with no runs yet; returns its folder."""
    words = clean(words, MAX_WORDS)
    if not words:
        raise FreeBuildError('Say what to build, for example "a small red fire truck".')
    if parts is not None and not MIN_PARTS <= parts <= MAX_PARTS:
        raise FreeBuildError(
            f"Choose about how many parts, a whole number from {MIN_PARTS} to {MAX_PARTS}."
        )
    shown = clean(name or "", MAX_NAME) or name_from(words)
    projects_dir.mkdir(parents=True, exist_ok=True)
    path = projects_dir / folder if folder else _free_folder(projects_dir, shown)
    path.mkdir()
    meta = {
        "kind": KIND,
        "experimental": True,
        "name": shown,
        "words": words,
        "parts_wanted": parts,
        "reference": reference,
        "model": model,
        "created": time.time(),
        "runs": [],
        "current": None,
    }
    save_meta(path, meta)
    return path


def task_words(words: str, parts: int | None) -> str:
    """What the AI is asked to build: the person's words and about how many parts."""
    words = words.strip()
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
        "seconds": rec.get("seconds"),
        "turns": rec.get("turns"),
        "cost_usd_reported": rec.get("cost_usd_reported"),
        "pictures": problem is None,
        "picture_problem": problem,
    }
    _write(dest / "record.json", json.dumps(entry, indent=1) + "\n")
    _use(folder, n)
    meta = read_meta(folder)
    meta["runs"] = [r for r in meta.get("runs") or [] if r.get("n") != n] + [entry]
    meta["current"] = n
    save_meta(folder, meta)
    return entry


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
            "pictures": False,
            "picture_problem": None,
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
) -> dict[str, Any]:
    """One AI session: the first build from the project's words, or ``words`` as a change
    to the current model. Keeps the run and returns its entry."""
    from bricksnap.lab import run as lab_run

    say = on_say or (lambda line: None)
    meta = read_meta(folder)
    current = meta.get("current")
    start = folder / "model.ldr" if current is not None else None
    if start is not None and not start.is_file():
        start = None
    if start is None:
        kind, change_of = "first", None
        asked = clean(words or "", MAX_WORDS) or str(meta.get("words") or "")
        task = task_words(asked, meta.get("parts_wanted"))
    else:
        asked = clean(words or "", MAX_WORDS)
        if not asked:
            raise FreeBuildError('Say what to change, for example "make the roof blue".')
        kind, change_of, task = "change", str(meta.get("words") or ""), asked
    if not asked:
        raise FreeBuildError("Say what to build.")
    n = next_run(folder)
    work = run_dir(folder, n) / "work"
    work.parent.mkdir(parents=True, exist_ok=True)
    say("The builder is getting ready: preparing the parts index")
    hear = Progress(work, say)
    options: dict[str, Any] = {}
    if meta.get("model"):
        options["model"] = str(meta["model"])
    try:
        record = lab_run.build(
            task,
            work,
            effort=EFFORT,
            max_turns=MAX_TURNS,
            max_checks=MAX_CHECKS,
            timeout=TIMEOUT_S,
            references=references,
            start=start,
            change_of=change_of,
            on_event=hear,
            **options,
        )
    except SystemExit as e:  # the lab's own refusals are plain sentences
        raise FreeBuildError(str(e.code)) from None
    except FileNotFoundError as e:  # the parts library went missing
        raise FreeBuildError(str(e)) from None
    say("The builder has stopped. Drawing the pictures of what it built")
    entry = adopt(folder, n, work, kind, asked)
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


def describe(folder: Path) -> dict[str, Any]:
    """What a page or the command line shows about a free-build project."""
    meta = read_meta(folder)
    runs = [r for r in meta.get("runs") or [] if isinstance(r, dict)]
    current = meta.get("current")
    now = next((r for r in runs if r.get("n") == current), None) or {}
    pics = folder / PICTURES_DIR
    return {
        "kind": KIND,
        "experimental": True,
        "name": str(meta.get("name") or folder.name),
        "words": str(meta.get("words") or ""),
        "parts_wanted": meta.get("parts_wanted"),
        "reference": meta.get("reference"),
        "parts": now.get("parts"),
        "kinds": now.get("kinds"),
        "summary": now.get("summary") or "",
        "clean": now.get("clean"),
        "problems": now.get("problems"),
        "unchecked": now.get("unchecked"),
        "current_run": current,
        "runs": runs,
        "notes": _read(folder / "notes.txt").strip(),
        "report": _read(folder / "report.txt").strip(),
        "turntable": turn_frames(folder),
        "card": f"{PICTURES_DIR}/card.png" if (pics / "card.png").is_file() else None,
        "sheet": f"{PICTURES_DIR}/sheet.png" if (pics / "sheet.png").is_file() else None,
        "picture_problem": now.get("picture_problem"),
        "files": [f for f in ("model.ldr", "parts.csv", "report.txt") if (folder / f).is_file()],
        "created": meta.get("created"),
    }


# ---- progress ----------------------------------------------------------------------------


TOOL_WORDS = {
    "part_info": "The builder is reading about a part",
    "model": "The builder is reading its model line by line",
    "look": "The builder is looking at its model from another side",
    "reference": "The builder is looking at the reference pictures",
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
                self.pending[str(item.get("id", ""))] = name
                raw = item.get("input")
                args: dict[str, Any] = raw if isinstance(raw, dict) else {}
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
                self._after(name, bool(item.get("is_error")) or text.startswith("ERROR:"))

    def _after(self, name: str, failed: bool) -> None:
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
