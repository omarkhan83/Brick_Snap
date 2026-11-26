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


def test_place_refuses_a_covered_stud_and_names_free_ones(tmp_path):
    f = folder(tmp_path)
    tools._place(f, {"part": "3003", "colour": 4, "line": 1, "stud": 1})  # studs 1, 2, 9, 10
    reply = said(tools._place(f, {"part": "3069b", "colour": 1, "line": 1, "stud": 2}))
    assert reply.startswith(
        "ERROR: Not added: stud 2 of line 1 already has line 2 (3003.dat Brick 2 x 2) on it."
    )
    assert "Free studs of line 1 that take it with this socket and turn, nearest first: 3," in reply
    assert len(lines(f)) == 2  # nothing added


def test_place_refuses_a_part_that_would_go_into_a_neighbour(tmp_path):
    f = folder(tmp_path)
    tools._place(f, {"part": "3005", "colour": 4, "line": 1, "stud": 3})  # a 1 x 1 brick
    # a 2 x 4 brick on stud 1 reaches over stud 3 and into the 1 x 1 brick
    reply = said(tools._place(f, {"part": "3001", "colour": 1, "line": 1, "stud": 1}))
    assert "Not added:" in reply and "line 2 (3005.dat Brick 1 x 1)" in reply
    assert len(lines(f)) == 2
    ok = said(tools._place(f, {"part": "3001", "colour": 1, "line": 1, "stud": 17}))
    assert ok.startswith("Added as line 3")


@pytest.mark.parametrize(
    "part, turn, falls", [("11477", 0, "-z"), ("11477", 1, "-x"), ("3040b", 2, "+z")]
)
def test_place_says_which_way_a_slope_falls(tmp_path, part, turn, falls):
    f = folder(tmp_path)
    reply = said(tools._place(f, {"part": part, "colour": 4, "line": 1, "stud": 20, "turn": turn}))
    assert f"Its slope falls towards {falls}; turn " in reply
    assert "would make it fall towards" in reply


def test_place_says_nothing_of_a_slope_for_a_brick_or_a_double_curve(tmp_path):
    f = folder(tmp_path)
    assert "slope falls" not in said(
        tools._place(f, {"part": "3001", "colour": 4, "line": 1, "stud": 1})
    )
    assert "slope falls" not in said(
        tools._place(f, {"part": "93273", "colour": 4, "line": 1, "stud": 30})
    )


THREE_ON_STUDS = (  # three 1 x 2 plates typed by hand onto the base's studs
    "1 4 -60 -16 -50 1 0 0 0 1 0 0 0 1 3023b.dat\n"
    "1 4 -20 -16 -50 1 0 0 0 1 0 0 0 1 3023b.dat\n"
    "1 4 20 -16 -50 1 0 0 0 1 0 0 0 1 3023b.dat"
)


@pytest.mark.parametrize("guide", [False, True])
def test_add_points_to_place_when_most_of_its_parts_sit_on_studs(tmp_path, guide):
    f = folder(tmp_path, guide=guide)
    reply = said(tools._add(f, {"ldraw": THREE_ON_STUDS}))
    assert "3 of these 3 parts sit on studs: place attaches a part by naming the stud" in reply
    assert ('It takes a list too ({"parts": [...]})' in reply) == guide


def test_add_says_nothing_of_place_for_parts_off_studs(tmp_path):
    f = folder(tmp_path)
    floating = "\n".join(ln.replace(" -16 ", " -40 ") for ln in THREE_ON_STUDS.splitlines())
    assert "sit on studs" not in said(tools._add(f, {"ldraw": floating}))
