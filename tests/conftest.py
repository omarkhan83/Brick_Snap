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
