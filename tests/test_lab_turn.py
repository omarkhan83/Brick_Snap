"""The builder's turn tool (``edit.turn``, served by bricksnap/lab/tools.py in guide mode): a
group of parts built lying flat, turned as one rigid piece by quarter turns and pressed onto
side studs of the core, as skilled builders make a tapering side profile.

They need the LDraw parts library and skip without it. No AI session is started.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bricksnap.lab import cover, ldraw_lib, tools
from bricksnap.lab.edit import EditError, turn
from bricksnap.lab.place import place
from bricksnap.lab.validate import check

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)

HELD = "no problems: every part is held"

# a 2 x 4 plate on the ground, a 1 x 1 plate on its stud 1, and a brick off to the side
PLATES = (
    "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 3020.dat\n"
    "1 4 -30 -16 -10 1 0 0 0 1 0 0 0 1 3024.dat\n"
    "1 1 100 -24 0 1 0 0 0 1 0 0 0 1 3005.dat\n"
)


def on(text: str, part: str, colour: int, line: int, **where) -> str:  # type: ignore[no-untyped-def]
    return text + "\n" + place(text, part, colour, line, **where).line


def _folder(tmp_path: Path, model: str) -> Path:
    f = tmp_path / "on"
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"mode": "tools", "guide": True}))
    (f / "art.json").write_text(json.dumps({"build_refused": True}))  # past the brief's gate
    (f / "model.ldr").write_text(model)
    return f


def _say(folder: Path, args: dict) -> str:  # type: ignore[type-arg]
    blocks = tools.call_tool(folder, "turn", args)
    assert len(blocks) == 1
    return blocks[0]["text"]


def test_a_group_of_plates_turned_a_quarter_about_x_lands_where_hand_computed():
    """The group's box is x -40..40, y -16..0, z -20..20, so it turns about (0, -8, 0); about
    x a quarter turn takes (x, y, z) to (x, -z, y); then it moves 20 up."""
    t = turn(PLATES, [1, 2], "x", 1, then_move=(0, -20, 0))
    lines = t.text.splitlines()
    assert lines[0] == "1 15 0 -28 0 1 0 0 0 0 -1 0 1 0 3020.dat"
    assert lines[1] == "1 4 -30 -18 -8 1 0 0 0 0 -1 0 1 0 3024.dat"
    assert lines[2] == PLATES.splitlines()[2]  # the rest untouched
    assert t.up_now == "-z" and t.lines == [1, 2]
    assert (t.lo.tolist(), t.hi.tolist()) == ([-40, -48, -8], [40, -8, 8])

    def relative(text: str) -> tuple[np.ndarray, np.ndarray]:
        a, b = (q for q in check(text, movement=False).placed if q.line in (1, 2))
        return a.m.T @ (b.pos - a.pos), a.m.T @ b.m

    for before, after in zip(relative(PLATES), relative(t.text), strict=True):
        assert np.allclose(before, after)  # rigid: the two keep their places in the group
    assert any(x.holder == 1 and x.held == 2 for x in t.report.links)  # still joined


def test_the_tool_turns_in_place_and_says_where_the_group_now_is(tmp_path):
    f = _folder(tmp_path, PLATES)
    said = _say(f, {"lines": [1, 2], "axis": "x", "quarter_turns": 1, "then_move": [0, -20, 0]})
    assert said.startswith(
        "Turned 2 parts (lines 1 to 2): one quarter turn about x, about the point (0, -8, 0) "
        "(the middle of its box), then moved by (0, -20, 0). They keep their line numbers."
    )
    assert "spans x -40..40, y -48..-8, z -8..8; its top (what faced up) now faces -z" in said
    assert "Nothing holds it" in said
    assert (f / "model.ldr").read_text().splitlines()[0].endswith("0 0 -1 0 1 0 3020.dat")


def _tapered_profile() -> str:
    """A fuselage core 2 studs wide (a 2 x 12 plate and three 1 x 4 bricks with side studs on
    each side, facing out), and beside it, lying flat on the ground, the right flank's side
    profile: a 2 x 8 plate with a wing 2 x 4 wedge plate at its tail end (wide end against the
    plate, its chamfer on the edge that will be the top), a 1 x 4 plate locking the two, two
    curved slopes on the front falling towards that edge, and tiles over the rest (cap)."""
    t = place("", "2445", 72, 0, x=0, z=40, turn=1).line  # 1
    for stud in (24, 20, 16):  # 2, 3, 4: +x side, z -80..160
        t = on(t, "30414", 72, 1, stud=stud, turn=3)
    for stud in (12, 8, 4):  # 5, 6, 7: -x side
        t = on(t, "30414", 72, 1, stud=stud, socket=4, turn=1)
    t += "\n" + place(t, "3034", 15, 0, x=200, z=0, turn=1).line  # 8: z -80..80
    t += "\n" + place(t, "41770b", 15, 0, x=200, z=120, turn=2).line  # 9: z 80..160
    t = on(t, "3710", 15, 8, stud=10, socket=4, turn=1)  # 10
    t = on(t, "15068", 15, 8, stud=8, socket=2, turn=1)  # 11
    t = on(t, "15068", 15, 8, stud=6, socket=2, turn=1)  # 12
    return cover.cap(t, 15, lines=[8, 9, 10]).text  # 13 to 16


def _top_at(report, lines: list[int], z: float) -> float:  # type: ignore[no-untyped-def]
    """The highest point (least y) of those parts' filled bodies at that z, 4 LDU out from the
    core's face (x 24)."""
    ys = np.arange(-70.0, 0.0, 1.0)
    pts = np.stack([np.full_like(ys, 24.0), ys, np.full_like(ys, z)], axis=1)
    inside = np.zeros(len(ys), dtype=bool)
    for p in report.placed:
        if p.line in lines:
            inside |= p.part.inside(p.to_local(pts), tol=0.0)
    return float(ys[inside].min())


def test_a_tapered_side_profile_built_flat_is_turned_up_onto_side_studs(tmp_path):
    model = _tapered_profile()
    flat = check(model, movement=False)
    assert not flat.problems and len(flat.placed) == 16
    f = _folder(tmp_path, model)
    group = list(range(8, 17))
    said = _say(
        f,
        {
            "lines": group,
            "axis": "z",
            "quarter_turns": 1,
            "onto": {"line": 2, "stud": 5, "own_line": 8, "own_socket": 16},
        },
    )
    assert said.startswith(
        "Turned 9 parts (lines 8 to 16): one quarter turn about z, and socket 16 of line 8 "
        "pressed on stud 5 of line 2."
    )
    assert "spans x 20..44, y -52..-12, z -80..160; its top (what faced up) now faces +x" in said
    assert "It is held by 12 side studs (lines 2, 3, 4)." in said
    assert "PROBLEM" not in said
    report = check((f / "model.ldr").read_text())
    assert HELD in report.summary() and not report.problems
    # the profile's top line, seen from the side: full height over the cabin, falling along the
    # wedge plate towards the tail
    assert _top_at(report, group, -60) == pytest.approx(-52, abs=1)
    assert _top_at(report, group, 90) < -45
    assert _top_at(report, group, 150) > -38


def test_a_group_that_would_go_into_the_model_is_refused_and_nothing_changes(tmp_path):
    model = _tapered_profile()
    f = _folder(tmp_path, model)
    said = _say(
        f,
        {"lines": list(range(8, 17)), "axis": "z", "quarter_turns": 1, "then_move": [-180, -20, 0]},
    )
    assert said.startswith(
        "ERROR: Not turned: so turned, the group (now x 8..32, y -52..-12, z -80..160) would "
        "go into the rest of the model: its line 8 into line 2 (30414.dat Brick 1 x 4 with "
        "Studs on Side)"
    )
    assert "The model is unchanged" in said
    assert (f / "model.ldr").read_text() == model
    with pytest.raises(EditError, match="below the ground"):
        turn(PLATES, [1, 2], "x", 1)  # about its middle, half of it goes under y = 0


@pytest.mark.parametrize(
    "args, words",
    [
        ({"lines": [1], "axis": "w", "quarter_turns": 1}, 'axis is "x", "y" or "z"'),
        ({"lines": [1], "axis": "x", "quarter_turns": 1.5}, "quarter_turns must be a whole"),
        ({"lines": [1], "axis": "x"}, "quarter_turns is needed"),
        ({"lines": [], "axis": "x", "quarter_turns": 1}, "lines must be a list of line numbers"),
        ({"lines": [9], "axis": "x", "quarter_turns": 1}, "there is no line 9 (the model has 4"),
        ({"lines": [4], "axis": "x", "quarter_turns": 1}, "line 4 is not a part"),
        ({"lines": [1], "axis": "x", "quarter_turns": 0}, "that moves nothing"),
        (
            {"lines": [2], "axis": "x", "quarter_turns": 1, "then_move": [0, 0, 1], "onto": {}},
            "not both",
        ),
        (
            {"lines": [1, 2], "axis": "x", "quarter_turns": 1, "onto": {"line": 2, "stud": 1}},
            "line 2 is in the group",
        ),
        (
            {
                "lines": [2],
                "axis": "y",
                "quarter_turns": 1,
                "onto": {"line": 3, "stud": 1, "own_line": 1},
            },
            "own_line 1 is not one of the group's lines",
        ),
        (
            {"lines": [2], "axis": "x", "quarter_turns": 1, "onto": {"line": 3, "stud": 1}},
            "takes a stud pointing -z, but stud 1 of line 3 points up. The quarter turns that "
            "face it that way: 0 (it faces that way as it is)",
        ),
        (
            {"lines": [2], "axis": "x", "quarter_turns": 0, "onto": {"line": 3, "stud": 7}},
            "has 1 studs, numbered 1 to 1; there is no stud 7",
        ),
    ],
)
def test_bad_input_is_refused_in_plain_words(tmp_path, args, words):
    f = _folder(tmp_path, PLATES + "0 STEP\n")
    said = _say(f, args)
    assert said.startswith("ERROR: ") and words in said, said
    assert (f / "model.ldr").read_text() == PLATES + "0 STEP\n"


def test_turn_is_a_guide_mode_tool_gated_by_the_brief(tmp_path):
    off = tmp_path / "off"
    off.mkdir()
    (off / "config.json").write_text(json.dumps({"mode": "tools", "guide": False}))
    assert "turn" not in {t["name"] for t in tools.tools_for(off)}
    on_ = tmp_path / "gate"
    on_.mkdir()
    (on_ / "config.json").write_text(json.dumps({"mode": "tools", "guide": True}))
    (on_ / "model.ldr").write_text(PLATES)
    assert "turn" in {t["name"] for t in tools.tools_for(on_)}
    args = {"lines": [1, 2], "axis": "x", "quarter_turns": 1, "then_move": [0, -20, 0]}
    first = tools.call_tool(on_, "turn", args)[0]["text"]
    assert "brief" in first and (on_ / "model.ldr").read_text() == PLATES
