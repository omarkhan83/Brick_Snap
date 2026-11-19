from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from bricksnap.catalog import Catalog, load_catalog  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PAWN = REPO / "samples" / "models" / "pawn.stl"


@pytest.fixture(scope="session")
def catalog() -> Catalog:
    return load_catalog()


@pytest.fixture(scope="session")
def pawn_path() -> Path:
    return PAWN


_REBUILT: dict[tuple[str, str], tuple[bytes, bytes]] = {}


def remember_rebuilds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``pipeline.rebuild`` run once per distinct design in the session, then replay it.

    A Build depends only on what ``Design.fingerprint`` covers (and the LDraw title on the
    project's name), ``rebuild`` gives the same files every time, and a saved Build loads back
    equal to the one returned, so writing the files a real rebuild of the same design wrote is
    exactly what a rebuild would do. Only for tests that change nothing inside the engine
    (a test that patches the solver or a pass must not use it), and that use a handful of
    designs many times: a rebuild of the 8-stud pawn costs about 0.9 s.
    """
    from bricksnap import pipeline

    real = pipeline.rebuild

    def remembered(project, *, catalog=None):
        key = (project.load_design().fingerprint(), project.name)
        if key not in _REBUILT:
            build = real(project, catalog=catalog)
            _REBUILT[key] = (project.build_path.read_bytes(), project.ldraw_path.read_bytes())
            return build
        project.build_path.write_bytes(_REBUILT[key][0])
        project.ldraw_path.write_bytes(_REBUILT[key][1])
        return project.load_build()

    monkeypatch.setattr(pipeline, "rebuild", remembered)


@pytest.fixture
def remembered_rebuild(monkeypatch) -> None:
    """``remember_rebuilds`` for one test; ask for it in a module that may use it."""
    remember_rebuilds(monkeypatch)
