"""The scorecard: build every test model and measure the result, so that we can tell whether
a change made things better. "Measured, not guessed" (docs/VISION.md, principle 6).

CONTRACT (tests go in tests/test_bench.py)

``run_bench(models_dir, out_dir, studs=16, catalog=None, names=None) -> list[Row]``
- For every model file in ``models_dir`` (``.stl``, ``.obj``, ``.glb``, ``.gltf``, ``.3mf``,
  ``.ply``; sorted by name; only those whose stem is in ``names`` when given): make a project
  in ``out_dir/projects/<name>`` with ``bricksnap.pipeline.create_project`` (deleting an
  older one of the same name), build it with ``pipeline.rebuild`` and the rough version with
  ``pipeline.rough_build``, and save the three-row comparison picture
  (``pipeline.render_compare(project, rough=True)``) as ``out_dir/<name>.png``.
- A model that cannot be loaded or built gives a Row with ``error`` set to the plain
  message and the other fields at their defaults. One bad model never stops the run.
- Writes ``out_dir/scorecard.json`` (the rows, plus ``studs``) and ``out_dir/scorecard.md``
  (the table from ``format_table`` under a one-line heading).

``Row`` fields
- ``name``; ``ok`` (the check report's verdict); ``parts``; ``loose`` (must be 0 for a good
  build); ``pieces``; ``weak_spots``; ``part_types`` (distinct part ids); ``colours``
  (distinct colour codes);
- ``shaped``: the share, from 0 to 1, of the build's upward-facing surface that is not plain
  studs: cells whose top is a tile, a slanted face or a detail part, divided by all cells
  that have nothing above them. This is the rough measure of "looks designed";
- ``rough_parts`` and ``rough_shaped``: the same two numbers for the rough build;
- ``match_front``, ``match_right``, ``match_top``: how closely the build's outline matches
  the seed's, from 0 to 1: the area both silhouettes cover divided by the area either
  covers (``bricksnap.render.silhouette`` of the seed and of the Build in the same frame);
- ``notes``: how many notes the make-buildable and finishing passes left;
- ``seconds``: time to build (not counting pictures; including the seatings tried, see
  below); ``error``: "" when all went well.
- (stage 4) ``seat``: where the model sits on the grid, "" where it always sat, otherwise
  "x", "y" or "x and y" for half a stud over on those axes (``pipeline.create_project``
  chooses it). ``format_table`` says under the table which models sit half a stud over,
  and ``compare`` says first when a model's seating moved, so that a seating that flips can
  be told apart from a change in the engine.
- (added, see the notes below) ``picture_error``: "" unless the model was built and measured
  but its picture could not be drawn.

``format_table(rows) -> str``: a Markdown table, one row per model, numbers rounded sensibly
(shares and matches as percentages), with a last line of totals or averages. Readable as
plain text in a terminal.

``compare(old_rows, new_rows) -> str``: one line per model whose ``ok``, ``loose``,
``parts``, ``shaped`` or match values changed, saying what went up or down; "No change." when
nothing did. Used to compare a run against ``samples/scorecard.json``.

Speed: the eleven sample models at 16 studs in under two minutes.

Implementation notes
--------------------
- Folders and names. A model's row is named after its file name without the extension. Its
  project folder is ``out_dir/projects/<slug of the name>`` (``bricksnap.project.slug``,
  the same folder ``create_project`` makes); an older folder there is deleted first, and so
  is an older ``out_dir/<name>.png``, so a model that fails this time never leaves last
  run's picture looking current. When two files share a name (``cat.glb`` and
  ``cat.obj``), the first in name order is built and the other gets an error row. The same
  happens when two names make the same folder (``My Cat.stl`` and ``my-cat.stl``): the
  second would delete the first's project, so it is left out with an error row naming the
  folder. A name in ``names`` with no model file gets an error row too. A missing
  ``models_dir`` is not a bad model: it raises ``FileNotFoundError`` with a plain message.
- ``seconds`` counts loading and voxelising the model (``create_project``, which since stage
  4 also builds it in each seating it tries, up to ``pipeline.SEAT_STUDS`` studs) and
  ``pipeline.rebuild`` (make buildable, lay out, finish, check): the steps a user waits for.
  The rough build, the measuring and the picture are not counted. Rounded to 0.01 s.
- ``shaped`` (``shaped_share``). The cells come from ``connect.occupancy``, so detail
  parts count as cells like any other part. An upward-facing cell is a covered cell with no
  covered cell directly above it (the top layer of the grid always faces up). Its top is
  shaped when the part covering it is of a detail kind that is not a slope (tile,
  round tile, round plate, round brick, cone, dish, detail: "any cell of a detail part"),
  or when the part has no stud at that (x, y) (``Catalog.stud_cells``): the slanted
  columns of a slope, curved slope or cheese slope. A brick, a plate, a side-stud brick,
  an inverted slope or the high row of a slope has studs there: plain. An empty Build
  scores 0. Shares are rounded to 0.0001.
- Outline match (``outline_match``). ``render.silhouette`` of the seed with
  ``grid_shape=build.shape`` and the Design's ``seed_offset``, against the silhouette of
  the Build, at the default 8 pixels per stud (studs are left out of both). Using the
  Build's own grid for the seed's frame guarantees the two pictures line up. The share is
  the pixels both cover over the pixels either covers; when neither covers any pixel the
  two outlines are the same, so it is 1, and when only one does it is 0. "right" is the
  view looked at from +x, as in ``bricksnap.render``.
- Counts: ``parts`` is every placement in the Build, details included; ``pieces`` is the
  report's ``components``; ``notes`` is ``len(build.notes)``. ``weak_spots`` is the real
  number of weak spots (``weak_spot_count``), not the number of sentences: ``Report`` lists
  at most ten, so the total is read from the start of the report's heading line "N weak
  spots to strengthen", as ``bricksnap.cli`` does for its short report (never less than
  the number of sentences). ``Report`` has no field for it; if ``checks`` ever words that
  line differently, the count falls back to the sentences and a test here fails.
- Errors. A ``SeedError`` or ``ProjectError`` keeps its own plain message. Anything else
  is a fault in BrickSnap, not in the model, and the message says so and names the step
  ("while building it") and the kind of fault, so a teammate can find it. Absolute paths
  are cut down to the file name and the home folder is written as "~", so nothing private
  reaches the table or the JSON.
- A missing picture is not a failed build. ``error`` always means "could not be built" (the
  other fields are then at their defaults). When the numbers were measured but the picture
  could not be drawn, the row keeps its numbers, ``error`` stays "" and ``picture_error``
  says what went wrong. ``scorecard.md`` lists both kinds under "Problems:".
- ``scorecard.json`` is ``{"studs": N, "rows": [...]}`` with every ``Row`` field.
  ``load_scorecard(path) -> (studs, rows)`` and ``load_rows(path) -> rows`` read it back,
  and also a bare list of rows. They are forgiving: unknown fields are ignored, missing or
  wrongly typed fields take the default (a whole number is fine for a share), entries
  without a model name are skipped. A file that is not JSON, or holds no list of rows,
  raises ``ValueError`` with a plain sentence.
- ``format_table``: right-aligned numbers, padded so the columns line up in a terminal.
  Shares and matches are whole percentages, except that a value that is not exactly 100%
  (or 0%) is never shown as 100% (or 0%): 99.7% shows as 99%. A row that failed shows
  "failed" and dashes. The last row adds up parts, loose parts, weak spots, rough parts,
  notes and seconds and averages the percentages, over the models that built (rows whose
  ``error`` is set are left out, whatever numbers they hold). A short key under the table
  says what each column means.
- ``compare``: percentages are compared to a tenth of a point and shown with one decimal,
  both from the same rounded number, so a change is never shown as "from 0.1% to 0.1%";
  smaller differences are "no change". Weak spots are compared too, so the work on fewer
  weak spots can be judged from it. Judgements are added only where they are unambiguous:
  becoming buildable or not, fewer or more loose parts, fewer or more weak spots, a closer
  or looser outline, starting or stopping to fail. Part count and the shaped share are just
  stated. Rows are paired by name and, when a run holds two rows of one name (a left-out
  duplicate file), by their order among the rows of that name, so an unchanged run always
  says "No change.". A model only in the new rows, or only in the old ones, gets a line
  saying so. Scorecards saved before the weak-spot count was fixed hold at most 10; the
  first comparison against one may report more weak spots for that reason alone.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import MISSING, asdict, dataclass, fields
from pathlib import Path
from typing import Any

from bricksnap.catalog import DETAIL_KINDS, SLOPE_KINDS, Catalog
from bricksnap.types import Build, Report, Seed

MODEL_SUFFIXES = (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply")

VIEWS = ("front", "right", "top")
"""The views the outline is matched in, in the order of the ``match_*`` fields."""


@dataclass
class Row:
    name: str
    ok: bool = False
    parts: int = 0
    loose: int = 0
    pieces: int = 0
    weak_spots: int = 0
    part_types: int = 0
    colours: int = 0
    shaped: float = 0.0
    rough_parts: int = 0
    rough_shaped: float = 0.0
    match_front: float = 0.0
    match_right: float = 0.0
    match_top: float = 0.0
    notes: int = 0
    seconds: float = 0.0
    error: str = ""
    picture_error: str = ""
    seat: str = ""


# ---- measures -------------------------------------------------------------------------------


def shaped_share(build: Build, catalog: Catalog) -> float:
    """Share (0 to 1) of the Build's upward-facing cells whose top is not plain studs."""
    import numpy as np

    from bricksnap.connect import occupancy

    occ = occupancy(build, catalog)[0]
    filled = occ >= 0
    covered_above = np.zeros_like(filled)
    covered_above[:, :, :-1] = filled[:, :, 1:]
    top = filled & ~covered_above
    total = int(top.sum())
    if total == 0:
        return 0.0
    always: dict[int, bool] = {}
    studs: dict[int, set[tuple[int, int]]] = {}
    shaped = 0
    xs, ys, zs = np.nonzero(top)
    for x, y, z in zip(xs.tolist(), ys.tolist(), zs.tolist(), strict=True):
        i = int(occ[x, y, z])
        if i not in always:
            p = build.parts[i]
            kind = catalog.parts[p.part].kind
            always[i] = kind in DETAIL_KINDS and kind not in SLOPE_KINDS
            studs[i] = set(catalog.stud_cells(p))
        if always[i] or (x, y) not in studs[i]:
            shaped += 1
    return shaped / total


def outline_match(
    seed: Seed,
    build: Build,
    catalog: Catalog,
    view: str,
    seed_offset: tuple[int, int, int],
) -> float:
    """How closely the Build's outline matches the seed's in one view, from 0 to 1."""
    from bricksnap.render import silhouette

    a = silhouette(seed, catalog, view, grid_shape=build.shape, seed_offset=seed_offset)
    b = silhouette(build, catalog, view)
    if a.shape != b.shape:  # cannot happen when both use the Build's grid; never guess
        raise ValueError("The outlines of the model and of the build are not the same size.")
    either = int((a | b).sum())
    if either == 0:
        return 1.0
    return int((a & b).sum()) / either


_WEAK_HEADING = re.compile(r"^(\d+) weak spots? to strengthen\b")


def weak_spot_count(report: Report) -> int:
    """How many weak spots the report found, also those it does not list."""
    listed = len(report.weak_spots)
    for line in report.text.splitlines():
        found = _WEAK_HEADING.match(line)
        if found:
            return max(int(found.group(1)), listed)
    return listed


# ---- running --------------------------------------------------------------------------------


def run_bench(
    models_dir: str | Path,
    out_dir: str | Path,
    studs: int = 16,
    catalog: Catalog | None = None,
    names: list[str] | None = None,
) -> list[Row]:
    from bricksnap.catalog import load_catalog

    models_dir = Path(models_dir)
    out_dir = Path(out_dir)
    if not models_dir.is_dir():
        raise FileNotFoundError(f"Cannot find the folder of test models {models_dir.name}.")
    catalog = catalog or load_catalog()
    files = sorted(
        (p for p in models_dir.iterdir() if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES),
        key=lambda p: p.name,
    )
    if names is not None:
        wanted = set(names)
        files = [p for p in files if p.stem in wanted]
    out_dir.mkdir(parents=True, exist_ok=True)
    hide = [models_dir, out_dir]

    from bricksnap.project import slug

    rows: list[Row] = []
    seen: set[str] = set()
    folders: dict[str, Path] = {}  # project folder name -> the model file that has it
    for path in files:
        if path.stem in seen:
            rows.append(
                Row(
                    path.stem,
                    error=f"Another model file is also called {path.stem}, so {path.name} "
                    "was left out. Give each test model its own name.",
                )
            )
            continue
        seen.add(path.stem)
        first = folders.get(slug(path.stem))
        if first is not None:
            rows.append(
                Row(
                    path.stem,
                    error=f"{path.name} would use the same project folder "
                    f"(projects/{slug(path.stem)}) as {first.name}, so it was left out. Give "
                    "each test model a name that differs in more than capitals, spaces and "
                    "punctuation.",
                )
            )
            continue
        folders[slug(path.stem)] = path
        rows.append(_bench_one(path, out_dir, studs, catalog, hide))
    for name in names or []:
        if name not in seen and name not in {r.name for r in rows}:
            rows.append(Row(name, error=f"There is no model file called {name} in the folder."))

    data = {"studs": int(studs), "rows": [asdict(r) for r in rows]}
    (out_dir / "scorecard.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    lines = [f"# BrickSnap scorecard: {_count(len(rows), 'model')} at {studs} studs", ""]
    lines.append(format_table(rows).rstrip())
    problems = [f"- {r.name}: {r.error or r.picture_error}" for r in rows if r.error]
    problems += [f"- {r.name}: {r.picture_error}" for r in rows if r.picture_error and not r.error]
    if problems:
        lines += ["", "Problems:", ""] + problems
    (out_dir / "scorecard.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def _bench_one(path: Path, out_dir: Path, studs: int, catalog: Catalog, hide: list[Path]) -> Row:
    from bricksnap import pipeline
    from bricksnap.checks import check
    from bricksnap.project import ProjectError, slug
    from bricksnap.types import SeedError

    name = path.stem
    projects = out_dir / "projects"
    picture = out_dir / f"{name}.png"
    step = "clearing out the last run"
    try:
        folder = projects / slug(name)
        if folder.is_dir() and not folder.is_symlink():
            shutil.rmtree(folder)
        elif folder.exists() or folder.is_symlink():
            folder.unlink()
        picture.unlink(missing_ok=True)

        step = "loading the model"
        start = time.perf_counter()
        project = pipeline.create_project(
            path, studs=studs, name=name, directory=projects, catalog=catalog
        )
        step = "building it"
        build = pipeline.rebuild(project, catalog=catalog)
        seconds = time.perf_counter() - start

        step = "making the plain conversion"
        rough = pipeline.rough_build(project, catalog=catalog)

        step = "measuring it"
        report = build.report or check(build, catalog)
        design = project.load_design()
        seed = pipeline.load_project_seed(project)
        matches = [
            round(outline_match(seed, build, catalog, view, design.seed_offset), 4)
            for view in VIEWS
        ]
        row = Row(
            name,
            ok=bool(report.ok),
            parts=len(build.parts),
            loose=len(report.loose),
            pieces=int(report.components),
            weak_spots=weak_spot_count(report),
            part_types=len({p.part for p in build.parts}),
            colours=len({p.color for p in build.parts}),
            shaped=round(shaped_share(build, catalog), 4),
            rough_parts=len(rough.parts),
            rough_shaped=round(shaped_share(rough, catalog), 4),
            match_front=matches[0],
            match_right=matches[1],
            match_top=matches[2],
            notes=len(build.notes),
            seconds=round(seconds, 2),
            seat=" and ".join(a for a, s in zip(("x", "y"), project.seat, strict=True) if s),
        )
    except (SeedError, ProjectError) as e:
        return Row(name, error=_private(str(e), hide))
    except Exception as e:
        return Row(name, error=_fault(e, step, hide))

    try:
        drawn = pipeline.render_compare(project, catalog=catalog, rough=True, name=f"{name}.png")
        shutil.copyfile(drawn, picture)
    except Exception as e:
        row.picture_error = (
            "It was built and measured, but the picture could not be drawn. "
            + _fault(e, "drawing the picture", hide)
        )
    return row


def _fault(e: BaseException, step: str, hide: list[Path]) -> str:
    detail = str(e).strip() or "no further detail"
    return _private(
        f"BrickSnap went wrong while {step} ({type(e).__name__}: {detail}). This is a fault "
        "in BrickSnap, not in the model.",
        hide,
    )


_UNIX_PATH = re.compile(r"(?<![\w.~])/(?:[^\s/'\"]+/)+([^\s/'\"]+)")
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\(?:[^\s\\'\"]+\\)*([^\s\\'\"]+)")


def _private(text: str, hide: list[Path]) -> str:
    """The text with folder names that could say who or where the user is taken out."""
    known: list[tuple[str, str]] = []
    for p in hide:
        known.append((str(p.resolve()), p.resolve().name))
        if p.is_absolute():
            known.append((str(p), p.name))
    for long, short in sorted(known, key=lambda k: -len(k[0])):
        if len(long) > 1:
            text = text.replace(long, short)
    home = str(Path.home())
    if len(home) > 1:
        text = text.replace(home, "~")
    text = _UNIX_PATH.sub(r"\1", text)
    return _WINDOWS_PATH.sub(r"\1", text)


# ---- reading a saved scorecard --------------------------------------------------------------


def row_from_dict(item: dict[str, Any]) -> Row:
    """A Row from one saved row. Unknown fields are ignored; a missing or wrongly typed field
    takes its default (a whole number is accepted for a share)."""
    values: dict[str, Any] = {"name": str(item.get("name", ""))}
    for f in fields(Row):
        if f.name == "name" or f.name not in item or f.default is MISSING:
            continue
        value, want = item[f.name], type(f.default)
        if want is bool:
            ok = isinstance(value, bool)
        elif want is int:
            ok = isinstance(value, int) and not isinstance(value, bool)
        elif want is float:
            ok = isinstance(value, int | float) and not isinstance(value, bool)
            value = float(value) if ok else value
        else:
            ok = isinstance(value, want)
        if ok:
            values[f.name] = value
    return Row(**values)


def load_scorecard(path: str | Path) -> tuple[int | None, list[Row]]:
    """(studs, rows) from a scorecard file as ``run_bench`` writes it, or a bare list of rows.

    ``studs`` is None when the file does not say. Raises ``ValueError`` with a plain sentence
    when the file cannot be used at all.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as e:
        raise ValueError(f"The scorecard {path.name} is not a text file.") from e
    except OSError as e:
        raise ValueError(f"The scorecard {path.name} cannot be opened.") from e
    except ValueError as e:
        raise ValueError(f"The scorecard {path.name} is not valid JSON.") from e
    raw = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise ValueError(f"The scorecard {path.name} holds no list of rows.")
    studs = data.get("studs") if isinstance(data, dict) else None
    if isinstance(studs, bool) or not isinstance(studs, int):
        studs = None
    rows = [
        row_from_dict(item)
        for item in raw
        if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip()
    ]
    return studs, rows


def load_rows(path: str | Path) -> list[Row]:
    """The rows of a scorecard file (see ``load_scorecard``)."""
    return load_scorecard(path)[1]


# ---- the table ------------------------------------------------------------------------------

_COLUMNS = (
    "model",
    "buildable",
    "parts",
    "loose",
    "pieces",
    "weak",
    "kinds",
    "colours",
    "shaped",
    "rough parts",
    "rough shaped",
    "front",
    "right",
    "top",
    "notes",
    "secs",
)

_KEY = (
    "Key: buildable = one piece that stands. loose = parts not attached to the rest "
    "(should be 0). weak = places held by a single stud or a single part (all of them, also "
    "those the check report does not list). "
    "kinds, colours = different parts and colours used. shaped = share of the top surface "
    "that is tiles, slopes or detail parts instead of plain studs. rough = the plain "
    "conversion before finishing. front, right, top = how closely the outline matches the "
    "model seen from that side (100% is exact). notes = remarks the passes left. secs = "
    "time to build, including the seatings tried. In the last row numbers are totals and "
    "percentages are averages, over the models that built."
)


def _percent(value: float) -> str:
    """A share as a whole percentage that never rounds to 0% or 100% unless it is."""
    p = round(value * 100)
    if p >= 100 and value < 1:
        p = 99
    elif p <= 0 < value:
        p = 1
    return f"{p}%"


def _failed(r: Row) -> bool:
    """True for a model that could not be built (a missing picture is ``picture_error``)."""
    return bool(r.error)


def _cells(r: Row) -> list[str]:
    if _failed(r):
        return [r.name, "failed"] + ["-"] * (len(_COLUMNS) - 2)
    return [
        r.name,
        "yes" if r.ok else "no",
        str(r.parts),
        str(r.loose),
        str(r.pieces),
        str(r.weak_spots),
        str(r.part_types),
        str(r.colours),
        _percent(r.shaped),
        str(r.rough_parts),
        _percent(r.rough_shaped),
        _percent(r.match_front),
        _percent(r.match_right),
        _percent(r.match_top),
        str(r.notes),
        f"{r.seconds:.1f}",
    ]


def _total_cells(rows: list[Row]) -> list[str]:
    built = [r for r in rows if not _failed(r)]
    label = f"total ({len(built)} of {len(rows)} built)"
    if not built:
        return [label] + [""] * (len(_COLUMNS) - 1)

    def avg(values: list[float]) -> str:
        return _percent(sum(values) / len(values))

    return [
        label,
        f"{sum(r.ok for r in built)} of {len(built)}",
        str(sum(r.parts for r in built)),
        str(sum(r.loose for r in built)),
        "",
        str(sum(r.weak_spots for r in built)),
        "",
        "",
        avg([r.shaped for r in built]),
        str(sum(r.rough_parts for r in built)),
        avg([r.rough_shaped for r in built]),
        avg([r.match_front for r in built]),
        avg([r.match_right for r in built]),
        avg([r.match_top for r in built]),
        str(sum(r.notes for r in built)),
        f"{sum(r.seconds for r in built):.1f}",
    ]


def format_table(rows: list[Row]) -> str:
    if not rows:
        return "No models were built.\n"
    table = [list(_COLUMNS)] + [_cells(r) for r in rows] + [_total_cells(rows)]
    widths = [max(len(line[i]) for line in table) for i in range(len(_COLUMNS))]

    def line(cells: list[str]) -> str:
        padded = [
            c.ljust(w) if i == 0 else c.rjust(w)
            for i, (c, w) in enumerate(zip(cells, widths, strict=True))
        ]
        return "| " + " | ".join(padded) + " |"

    rule = (
        "| "
        + " | ".join(("-" * w if i == 0 else "-" * (w - 1) + ":") for i, w in enumerate(widths))
        + " |"
    )
    out = [line(table[0]), rule] + [line(c) for c in table[1:]]
    seated = [f"{r.name} ({r.seat})" for r in rows if r.seat and not r.error]
    if seated:
        out += ["", f"Sitting half a stud over on the grid: {', '.join(seated)}."]
    return "\n".join(out) + "\n\n" + _KEY + "\n"


# ---- comparing two runs ---------------------------------------------------------------------

_MATCH_WORDS = {"match_front": "front", "match_right": "right", "match_top": "top"}


def _tenths(value: float) -> int:
    """A share in tenths of a percentage point: what is compared, and what is shown."""
    return round(value * 1000)


def _shown(value: float) -> str:
    """A share as a percentage with one decimal, from the same number ``_tenths`` gives."""
    return f"{_tenths(value) / 10:.1f}%"


def _changes(old: Row, new: Row) -> list[str]:
    said: list[str] = []
    if old.seat != new.seat:
        where = lambda s: f"half a stud over in {s}" if s else "where it always sat"  # noqa: E731
        said.append(f"its seating moved from {where(old.seat)} to {where(new.seat)}")
    if old.ok != new.ok:
        said.append("became buildable (better)" if new.ok else "is no longer buildable (worse)")
    if old.loose != new.loose:
        way, verdict = ("down", "better") if new.loose < old.loose else ("up", "worse")
        said.append(f"loose parts went {way} from {old.loose} to {new.loose} ({verdict})")
    if old.parts != new.parts:
        way = "down" if new.parts < old.parts else "up"
        said.append(f"parts went {way} from {old.parts} to {new.parts}")
    if old.weak_spots != new.weak_spots:
        way, verdict = ("down", "better") if new.weak_spots < old.weak_spots else ("up", "worse")
        said.append(f"weak spots went {way} from {old.weak_spots} to {new.weak_spots} ({verdict})")
    if _tenths(old.shaped) != _tenths(new.shaped):
        way = "down" if _tenths(new.shaped) < _tenths(old.shaped) else "up"
        said.append(
            f"the shaped share of the top went {way} from {_shown(old.shaped)} to "
            f"{_shown(new.shaped)}"
        )
    for key, view in _MATCH_WORDS.items():
        a, b = float(getattr(old, key)), float(getattr(new, key))
        if _tenths(a) != _tenths(b):
            closer = _tenths(b) > _tenths(a)
            way, verdict = ("up", "closer, better") if closer else ("down", "less close, worse")
            said.append(
                f"the {view} outline match went {way} from {_shown(a)} to {_shown(b)} ({verdict})"
            )
    return said


def _keyed(rows: list[Row]) -> list[tuple[tuple[str, int], Row]]:
    """Each row with (name, how many rows of that name came before it)."""
    count: dict[str, int] = {}
    keyed = []
    for r in rows:
        n = count.get(r.name, 0)
        count[r.name] = n + 1
        keyed.append(((r.name, n), r))
    return keyed


def compare(old_rows: list[Row], new_rows: list[Row]) -> str:
    old_by_key = dict(_keyed(old_rows))
    new_keys = {key for key, _ in _keyed(new_rows)}
    lines: list[str] = []
    for key, new in _keyed(new_rows):
        old = old_by_key.get(key)
        if old is None:
            lines.append(f"{new.name}: new, it is not in the saved scorecard.")
            continue
        old_failed, new_failed = _failed(old), _failed(new)
        if old_failed and new_failed:
            continue
        if new_failed:
            lines.append(
                f"{new.name}: it could be built before, but now it fails (worse): {new.error}"
            )
            continue
        if old_failed:
            state = "buildable" if new.ok else "not buildable"
            lines.append(
                f"{new.name}: it failed before and now it builds (better): {new.parts} parts, "
                f"{state}, {new.loose} loose."
            )
            continue
        said = _changes(old, new)
        if said:
            lines.append(f"{new.name}: " + "; ".join(said) + ".")
    for key, old in _keyed(old_rows):
        if key not in new_keys:
            lines.append(f"{old.name}: in the saved scorecard but not in this run.")
    return "\n".join(lines) + "\n" if lines else "No change.\n"


def _count(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"
