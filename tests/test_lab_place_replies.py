"""What the builder's place and add tools say back (bricksnap/lab/tools.py), from a study of
18 real builds of where the builder wasted turns: old part numbers retyped, parts placed
onto covered studs, slopes placed facing the wrong way, parts typed by hand that place could
have attached. They need the LDraw parts library and skip without it; no AI session is
started."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bricksnap.lab import ldraw_lib, tools

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)

BASE = "1 7 0 -8 0 1 0 0 0 1 0 0 0 1 3036.dat\n"  # Plate 6 x 8: studs x -70..70, z -50..50


def folder(tmp_path: Path, model: str = BASE, guide: bool = False) -> Path:
    f = tmp_path / "work"
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"mode": "tools", "guide": guide}))
    tools._save_model(f, model)
    return f


def said(blocks: list[dict]) -> str:
    return " ".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def lines(f: Path) -> list[str]:
    return tools._model(f).splitlines()


def test_place_with_an_old_number_uses_the_current_one(tmp_path):
    f = folder(tmp_path)
    reply = said(tools._place(f, {"part": "3023", "colour": 4, "line": 1, "stud": 1}))
    assert reply.startswith("3023 is an old number: placed 3023b. Added as line 2:")
    assert lines(f)[1].endswith(" 3023b.dat")
    assert "old number" not in said(
        tools._place(f, {"part": "3023b", "colour": 4, "line": 1, "stud": 3})
    )


def test_add_with_an_old_number_uses_the_current_one_in_the_same_place(tmp_path):
    f = folder(tmp_path)
    reply = said(
        tools._add(
            f,
            {
                "ldraw": "1 4 -70 -16 -50 1 0 0 0 1 0 0 0 1 4073.dat\n"
                "1 4 -40 -16 -10 1 0 0 0 1 0 0 0 1 2301.dat"  # its move turns it a quarter
            },
        )
    )
    assert "4073 is an old number: used 6141, in the same place." in reply
    assert "2301 is an old number: used 2301b, in the same place." in reply
    assert lines(f)[1] == "1 4 -70 -16 -50 1 0 0 0 1 0 0 0 1 6141.dat"
    assert lines(f)[2] == "1 4 -40 -16 -10 0 0 -1 0 1 0 1 0 0 2301b.dat"
    assert "old number" not in said(
        tools._add(f, {"ldraw": "1 4 30 -16 -50 1 0 0 0 1 0 0 0 1 6141.dat"})
    )


def test_current_number_follows_a_move_and_leaves_a_current_part_alone():
    got = ldraw_lib.current_number("3023")
    assert got is not None and got[0] == "3023b.dat"
    assert ldraw_lib.current_number("3023b") is None and ldraw_lib.current_number("nosuch") is None
