"""The steps from a model file to a checked Build, as used by the command line, the AI
designer's tools and the tests. Keeping them here means everything runs the same pipeline.

STAGE 4 ADDITION: the model sits where its build comes out best
``create_project`` (which ``bricksnap new``, the web app's upload job and ``bench`` all use)
chooses where the model sits on the grid, once, and the project remembers it:
- Seatings: (0, 0) is where the model has always sat (centred in whole studs); on each of
  x and y it may also sit half a stud over, when that side is not a whole number of studs
  and the grid on that axis is then no longer than the size asked for
  (``bricksnap.seed.seatings``). So one to four seatings. Only for models of at most
  ``SEAT_STUDS`` studs on their longest side; above that, and when there is only one
  seating, nothing is tried and the project is made exactly as before.
- Each seating is built as a new project is built (convert, make buildable, solve, finish,
  check: ``_finished``) and its outline match is measured in the three views of
  ``bricksnap.bench`` against the seed in that seating.
- Today's seating is kept unless another is better, and another is better only when ALL of
  these hold:
  * it has no loose parts;
  * it is no less sturdy, by the project's shared measure (``connect.sturdiness``: the
    largest load of any lone link in parts, and the number of lone links): its largest load
    is lower than today's, or is at most ``SEAT_LOAD_SLACK`` (1) part higher and it has no
    more lone links. The one part is layout luck (the knight at 12 studs comes out with a
    largest load of 5 one way and 4 the other), not weakness. So a column one stud across,
    every level a lone link, is never "sturdier" than a 2 x 2 one with one weak spot;
  * it joins no more of the model's own sections than today's seating does (``voxelize``,
    "sections fused": two legs a stud apart must not come out as one block);
  * no view's outline match is worse by more than ``SEAT_TOLERANCE`` (1 point);
  * the mean of the three views is better by at least ``SEAT_GAIN`` (1 point), and, when it
    needs more parts than today's seating, by one point more for every ``SEAT_PARTS`` (10
    per cent) of extra parts: more parts must buy more likeness (p per cent more parts
    needs 1 + p / 10 points; so the bottle at 12 studs, 84% more parts for 12 points,
    moves, and the pawn at 16, 53% more for under 3, does not).
  A seating that keeps apart sections today's seating joins has that in its favour: a view
  may be worse by up to ``SEAT_APART_TOLERANCE`` (5 points) instead of 1, and it needs no
  gain beyond what its extra parts ask (its mean may not be lower than today's). Among
  several that qualify, the one that joins fewest sections wins, then the best mean, then
  (1, 1). When the winner is half a stud over on one axis only and its twin on the other
  axis has a mean within ``SEAT_GAIN`` of it (measured, whether the twin qualifies or not),
  neither decides: (1, 1) if it qualifies, otherwise today's seating. No clock and no
  randomness: the same file gives the same seating every time. A model turned a quarter
  about z usually, not always, sits the same way turned: the solver can lay the turned model
  differently (the knight at 12 studs has 5 weak spots one way and 6 the other), and that
  can decide.
- The project keeps the seating in project.json ("seat", with "seat_note": a sentence such
  as "When this project was made the model was set half a stud over in x and y on the
  grid: its outline matched 83/89/82% that way against 70/74/72%.", written as history
  because it stays first in the notes of every later build), only when it is not (0, 0).
  ``load_project_seed`` gives the seed in that seating, so everything that lines a build up
  with its model (the outline match, the comparison pictures, the designer's pictures and
  tools, the judge, versions) agrees without knowing about it; ``Design.seed_offset`` stays
  whole cells. ``rebuild`` puts the sentence first in ``Build.notes``. A project without
  "seat" sits at (0, 0) and is built exactly as before. A "seat" that is not two values of 0
  or 1, or that marks a side that is a whole number of studs, is a ProjectError with one
  plain message, whichever way the project is opened (``Project`` reads it when opened;
  ``load_project_seed`` and ``check_seat`` find a whole side marked seated).
- ``create_project(..., say=...)``: a function given one plain line while the seatings are
  tried (the web app shows it as progress; the command line prints it).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from bricksnap.catalog import Catalog, load_catalog
from bricksnap.project import Project, slug
from bricksnap.types import Build, Design, Seed, write_text_atomic

SEAT_STUDS = 16  # models up to this size (longest side, studs) try the other seatings
SEAT_GAIN = 0.01  # another seating must raise the mean outline match by this much
SEAT_TOLERANCE = 0.01  # and may lower no single view's by more than this
SEAT_PARTS = 0.10  # each this share of extra parts asks for SEAT_GAIN more of the mean
SEAT_LOAD_SLACK = 1  # parts: a largest load this much higher is layout luck, not weakness
SEAT_APART_TOLERANCE = 0.05  # a seating that keeps sections apart may lose this much a view


def create_project(
    model_path: str | Path,
    *,
    studs: int,
    name: str | None = None,
    directory: str | Path = "projects",
    up: str | None = None,
    hollow: bool = False,
    catalog: Catalog | None = None,
    piece: int | None = None,
    piece_box: Any = None,
    say: Callable[[str], None] | None = None,
) -> Project:
    """Make a project folder from a model file and voxelise it. Does not build.

    ``piece`` (1, 2, ...) builds only that piece of a file that looks like several
    (``bricksnap.pieces``); the project keeps the number and the piece's box in the file's
    own coordinates, and every later step finds the piece again by that box. None builds the
    whole file. A caller that has just found the pieces passes the piece's box as
    ``piece_box`` too, which saves searching the file once more."""
    from bricksnap.seed import load_seed
    from bricksnap.voxelize import voxelize

    catalog = catalog or load_catalog()
    model_path = Path(model_path)
    # load first, so a bad model fails before any folder is created
    box = piece_box if piece is not None else None
    if piece is not None and box is None:
        from bricksnap.pieces import find_pieces

        found = find_pieces(model_path, up=up)
        if found.several:
            box = found.piece(piece, any_piece=True).box
        elif piece != 1:
            found.piece(piece)  # raises: a one-object file has no piece 2
        piece = None if box is None else piece
    seed = load_seed(model_path, studs=studs, up=up, piece_box=box)
    design = voxelize(seed, catalog, hollow=hollow)
    seat, design, note = choose_seat(seed, design, studs, hollow=hollow, catalog=catalog, say=say)
    project = Project.create(
        Path(directory) / slug(name or model_path.stem),
        model_path,
        studs=studs,
        up=up,
        hollow=hollow,
        name=name or model_path.stem,
        piece=piece,
        piece_box=box,
        seat=seat,
        seat_note=note,
    )
    project.save_design(design, base=True)
    return project


def load_project_seed(project: Project) -> Seed:
    from bricksnap.project import DAMAGED_SEAT, ProjectError
    from bricksnap.seed import load_seed, seated

    seat = project.seat
    seed = load_seed(
        project.seed_path,
        studs=int(project.meta["studs"]),
        up=project.meta.get("up"),
        piece_box=project.piece_box,
    )
    if seat == (0, 0):
        return seed
    try:
        return seated(seed, seat)
    except ValueError as e:  # a whole side marked seated: impossible, so damaged
        raise ProjectError(DAMAGED_SEAT.format(path=project.path)) from e


def check_seat(project: Project) -> None:
    """ProjectError when the project's seat cannot be used (see the contract); reads the
    model file only for a seated project."""
    if project.seat != (0, 0):
        load_project_seed(project)


def _finished(design: Design, catalog: Catalog) -> Build:
    """Design to checked Build, as ``rebuild`` makes it (make buildable, lay out, finish,
    check), without saving anything."""
    from bricksnap.buildable import make_buildable
    from bricksnap.checks import check
    from bricksnap.finish import finish

    fixed = make_buildable(design, catalog)  # works on a copy and returns its own layout
    build = fixed.build
    build.notes = list(fixed.notes)
    build = finish(build, fixed.design, catalog)
    build.design_id = design.fingerprint()
    build.report = check(build, catalog)
    return build


def _seat_measures(
    seed: Seed, design: Design, fused: list[int], catalog: Catalog
) -> dict[str, Any]:
    """What the choice of seating compares: the outline match in the three views, loose
    parts, sturdiness (``connect.sturdiness``: largest load in parts, lone links, sum of
    loads), parts, and the model's sections that the Design joins (``fused``, from
    ``voxelize``)."""
    from bricksnap.bench import VIEWS, outline_match
    from bricksnap.connect import sturdiness

    build = _finished(design, catalog)
    report = build.report
    assert report is not None
    return {
        "match": [outline_match(seed, build, catalog, v, design.seed_offset) for v in VIEWS],
        "loose": len(report.loose),
        "sturdy": tuple(sturdiness(build, catalog)),
        "parts": len(build.parts),
        "fused": int(sum(fused)),
    }


def _no_less_sturdy(m: dict[str, Any], today: dict[str, Any]) -> bool:
    """Its largest load (in parts) is lower than today's, or is at most ``SEAT_LOAD_SLACK``
    parts higher and it has no more lone links."""
    (load, links, _), (load0, links0, _) = m["sturdy"], today["sturdy"]
    return load < load0 or (load <= load0 + SEAT_LOAD_SLACK and links <= links0)


def better_seat(tried: dict[tuple[int, int], dict[str, Any]]) -> tuple[int, int]:
    """The seating to use, given the measures of each one tried ((0, 0) among them): see
    "the model sits where its build comes out best" above."""
    today = tried[(0, 0)]
    mean = {k: sum(m["match"]) / 3 for k, m in tried.items()}

    def needed(m: dict[str, Any]) -> float:
        """The gain in mean outline match that a seating with these measures must show."""
        extra = max(0, m["parts"] - today["parts"]) / max(today["parts"], 1)
        gain = SEAT_GAIN * (1 + extra / SEAT_PARTS)
        return gain - SEAT_GAIN if m["fused"] < today["fused"] else gain

    def qualifies(k: tuple[int, int], m: dict[str, Any]) -> bool:
        if k == (0, 0) or m["loose"] or not _no_less_sturdy(m, today):
            return False
        if m["fused"] > today["fused"]:
            return False
        apart = m["fused"] < today["fused"]
        tolerance = SEAT_APART_TOLERANCE if apart else SEAT_TOLERANCE
        if any(a < b - tolerance for a, b in zip(m["match"], today["match"], strict=True)):
            return False
        return mean[k] >= mean[(0, 0)] + needed(m) - 1e-12

    good = [k for k, m in tried.items() if qualifies(k, m)]
    if not good:
        return (0, 0)
    best = min(good, key=lambda k: (tried[k]["fused"], -mean[k], k != (1, 1)))
    if best in ((1, 0), (0, 1)):
        twin = (best[1], best[0])
        if twin in tried and abs(mean[best] - mean[twin]) <= SEAT_GAIN + 1e-12:
            return (1, 1) if (1, 1) in good else (0, 0)
    return best


def seat_note(seat: tuple[int, int], new: list[float], old: list[float], apart: int = 0) -> str:
    """The plain sentence, written as history, that says where the model was set and what
    that gained."""
    axes = " and ".join(a for a, s in zip(("x", "y"), seat, strict=True) if s)
    shown = lambda m: "/".join(str(round(100 * v)) for v in m)  # noqa: E731
    kept = f", and {apart} of its sections that came out joined were kept apart" if apart else ""
    return (
        f"When this project was made the model was set half a stud over in {axes} on the "
        f"grid: its outline matched {shown(new)}% that way against {shown(old)}%{kept}."
    )


def choose_seat(
    seed: Seed,
    design: Design,
    studs: int,
    *,
    hollow: bool,
    catalog: Catalog,
    say: Callable[[str], None] | None = None,
) -> tuple[tuple[int, int], Design, str | None]:
    """(the seating, its Design, the sentence for the project or None) for a seed loaded
    with seat (0, 0) and its ``design``: see the module's contract."""
    from bricksnap.seed import seated, seatings
    from bricksnap.voxelize import voxelize

    ways = seatings(seed, studs) if studs <= SEAT_STUDS else [(0, 0)]
    if len(ways) == 1:
        return (0, 0), design, None
    if say is not None:
        say(
            f"Trying {len(ways)} ways of setting the model on the grid, to keep the one "
            "whose bricks fit it best"
        )
    designs: dict[tuple[int, int], Design] = {}
    tried: dict[tuple[int, int], dict[str, Any]] = {}
    for way in ways:
        moved = seed if way == (0, 0) else seated(seed, way)
        fused: list[int] = []
        designs[way] = voxelize(moved, catalog, hollow=hollow, fused=fused)
        tried[way] = _seat_measures(moved, designs[way], fused, catalog)
    way = better_seat(tried)
    if way == (0, 0):
        return (0, 0), design, None
    apart = tried[(0, 0)]["fused"] - tried[way]["fused"]
    note = seat_note(way, tried[way]["match"], tried[(0, 0)]["match"], apart)
    return way, designs[way], note


def rebuild(project: Project, *, catalog: Catalog | None = None) -> Build:
    """Design to checked Build: make buildable, lay out, finish, check.

    Saves build.json and build.ldr and returns the Build. ``Build.notes`` says what the
    make-buildable and finishing passes changed by themselves. The saved Design is never
    changed here: the make-buildable pass works on a copy.
    """
    from bricksnap.buildable import make_buildable
    from bricksnap.checks import check
    from bricksnap.finish import finish
    from bricksnap.ldraw import to_ldraw

    catalog = catalog or load_catalog()
    design = project.load_design()
    fixed = make_buildable(design, catalog)  # works on a copy and returns its own layout
    build = fixed.build
    build.notes = list(fixed.notes)
    build = finish(build, fixed.design, catalog)
    build.design_id = design.fingerprint()
    build.report = check(build, catalog)
    if project.seat_note:
        build.notes.insert(0, project.seat_note)
    project.save_build(build)
    write_text_atomic(project.ldraw_path, to_ldraw(build, catalog, title=project.name))
    return build


def rough_build(project: Project, *, catalog: Catalog | None = None) -> Build:
    """The plain conversion, made to hold together: the untouched base Design through the
    make-buildable pass and the layout, with no finishing and no edits, so bricks and
    plates only.

    This is the "before" of every before-and-after picture. It is saved as build.rough.json
    and reused for as long as the base Design is the one it was made from. ``Build.notes``
    says what the make-buildable pass changed. (The conversion fills a cell only when the
    model fills most of it, so on its own it can leave a thin feature loose; the rough
    build is the plainest build that holds.)
    """
    from bricksnap.buildable import make_buildable
    from bricksnap.checks import check

    catalog = catalog or load_catalog()
    base = project.load_design(base=True)
    if project.rough_build_path.exists():
        try:
            saved = Build.load(project.rough_build_path)
            if saved.design_id == base.fingerprint():
                return saved
        except (ValueError, KeyError, TypeError, OSError):
            pass  # unreadable: make it again
    fixed = make_buildable(base, catalog)  # works on a copy and returns its own layout
    build = fixed.build
    build.notes = list(fixed.notes)
    build.design_id = base.fingerprint()
    build.report = check(build, catalog)
    build.save(project.rough_build_path)
    return build


def render_compare(
    project: Project,
    *,
    catalog: Catalog | None = None,
    name: str | None = None,
    rough: bool = False,
    views: tuple[str, ...] | None = None,
) -> Path:
    """Write a comparison picture into renders/ and return its path.

    The seed's views are on the top row and the current build's (or, before any build, the
    design's) on the bottom row. With ``rough=True`` the plain conversion is drawn on a row
    in between, so the picture reads seed, rough, build. ``name`` defaults to compare.png,
    or compare-rough.png with ``rough=True``.
    """
    from bricksnap.render import compare_sheet

    catalog = catalog or load_catalog()
    design = project.load_design()
    build = project.load_build() if project.has_build() else None
    from bricksnap.project import ProjectError

    try:
        seed: Seed | None = load_project_seed(project)
    except ProjectError:  # a damaged seat is said, never drawn round
        raise
    except Exception:  # a picture without the seed row is better than no picture
        seed = None
    options: dict[str, Any] = {}
    if views is not None:
        options["views"] = tuple(views)
    if rough:
        options["rough"] = rough_build(project, catalog=catalog)
    out = project.renders_dir / (name or ("compare-rough.png" if rough else "compare.png"))
    compare_sheet(seed, design, build, catalog, **options).save(out)
    return out


CARD_SIZE = (640, 480)
"""renders/card.png: a 4:3 card on the web app's home page, at twice its size on the page."""


def render_card(project: Project, *, catalog: Catalog | None = None) -> Path:
    """Write renders/card.png, one clean picture of the current build, and return its path.

    The three-quarter view in real part shapes (``render.render_build``, "iso", no labels or
    ticks), cut to the model and centred on a ``CARD_SIZE`` picture with a small margin, so a
    project card on the web app's home page shows the bricks rather than the comparison
    sheet. Written beside the old picture first and then moved into place.
    """
    import os

    from PIL import Image, ImageChops

    from bricksnap.render import BACKGROUND, render_build

    catalog = catalog or load_catalog()
    build = project.load_build()
    nx, ny, nz = build.shape
    px = max(4, min(64, int(1200 / max(nx, ny, nz * 0.4, 1))))
    picture = render_build(build, catalog, "iso", px_per_stud=px, labels=False).convert("RGB")
    box = ImageChops.difference(picture, Image.new("RGB", picture.size, BACKGROUND)).getbbox()
    if box is not None:
        picture = picture.crop(box)
    width, height = CARD_SIZE
    margin = 24
    scale = min((width - 2 * margin) / picture.width, (height - 2 * margin) / picture.height)
    size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
    picture = picture.resize(size, Image.Resampling.LANCZOS)
    card = Image.new("RGB", CARD_SIZE, BACKGROUND)
    card.paste(picture, ((width - size[0]) // 2, (height - size[1]) // 2))
    out = project.renders_dir / "card.png"
    tmp = out.with_name(f".card.{os.getpid()}.png")
    try:
        card.save(tmp)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    return out
