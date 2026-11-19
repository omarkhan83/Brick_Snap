"""The steps from a model file to a checked Build, as used by the command line, the AI
designer's tools and the tests. Keeping them here means everything runs the same pipeline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bricksnap.catalog import Catalog, load_catalog
from bricksnap.project import Project, slug
from bricksnap.types import Build, Seed, write_text_atomic


def create_project(
    model_path: str | Path,
    *,
    studs: int,
    name: str | None = None,
    directory: str | Path = "projects",
    up: str | None = None,
    hollow: bool = False,
    catalog: Catalog | None = None,
) -> Project:
    """Make a project folder from a model file and voxelise it. Does not build."""
    from bricksnap.seed import load_seed
    from bricksnap.voxelize import voxelize

    catalog = catalog or load_catalog()
    model_path = Path(model_path)
    # load first, so a bad model fails before any folder is created
    seed = load_seed(model_path, studs=studs, up=up)
    design = voxelize(seed, catalog, hollow=hollow)
    project = Project.create(
        Path(directory) / slug(name or model_path.stem),
        model_path,
        studs=studs,
        up=up,
        hollow=hollow,
        name=name or model_path.stem,
    )
    project.save_design(design, base=True)
    return project


def load_project_seed(project: Project) -> Seed:
    from bricksnap.seed import load_seed

    return load_seed(project.seed_path, studs=int(project.meta["studs"]), up=project.meta.get("up"))


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
    try:
        seed: Seed | None = load_project_seed(project)
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
