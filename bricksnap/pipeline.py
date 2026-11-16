"""The steps from a model file to a checked Build, as used by the command line, the AI
designer's tools and the tests. Keeping them here means everything runs the same pipeline.
"""

from __future__ import annotations

from pathlib import Path

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
    """Design to Build to checks. Saves build.json and build.ldr; returns the checked Build."""
    from bricksnap.checks import check
    from bricksnap.layout import solve
    from bricksnap.ldraw import to_ldraw

    catalog = catalog or load_catalog()
    design = project.load_design()
    build = solve(design, catalog)
    build.design_id = design.fingerprint()
    build.report = check(build, catalog)
    project.save_build(build)
    write_text_atomic(project.ldraw_path, to_ldraw(build, catalog, title=project.name))
    return build


def render_compare(
    project: Project, *, catalog: Catalog | None = None, name: str = "compare.png"
) -> Path:
    """Write renders/<name>: the seed's views above the current build's (or design's) views."""
    from bricksnap.render import compare_sheet

    catalog = catalog or load_catalog()
    design = project.load_design()
    build = project.load_build() if project.has_build() else None
    try:
        seed: Seed | None = load_project_seed(project)
    except Exception:  # a picture without the seed row is better than no picture
        seed = None
    out = project.renders_dir / name
    compare_sheet(seed, design, build, catalog).save(out)
    return out
