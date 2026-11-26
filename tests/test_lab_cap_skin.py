"""The builder's cap and skin tools (bricksnap/lab/cover.py, served by bricksnap/lab/tools.py in
guide mode): small constructions put together through ``place`` (as the builder does), covered
by one call, and what the checker and the looks measure say about the result.

They need the LDraw parts library and skip without it. No AI session is started.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from bricksnap.lab import cover, ldraw_lib, looks, tools
from bricksnap.lab.edit import fill
from bricksnap.lab.place import place
from bricksnap.lab.validate import check

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)

HELD = "no problems: every part is held"


def on(text: str, part: str, colour: int, line: int, **where) -> str:  # type: ignore[no-untyped-def]
    return text + "\n" + place(text, part, colour, line, **where).line


def b(x: float, z: float) -> int:
    """The number of the 6 x 8 base plate's stud at (x, z)."""
    return int((x + 70) / 20) + 1 + 8 * int((z + 50) / 20)


def base() -> str:
    return place("", "3036.dat", 71, 0).line


def same_as_place(text: str, new: list[cover.New]) -> None:
    """Every new line is the one place itself writes for that connection."""
    for n in new:
        line, stud, socket, turn = n.via
        assert place(text, n.key, 15, line, stud=stud, socket=socket, turn=turn).line == n.line


def bracket_body() -> str:
    """The guide's 2-stud core: a 2 x 4 brick on the base, two brackets on each long side."""
    t = on(base(), "3001.dat", 72, 1, stud=b(-30, -10))
    t = on(t, "99781.dat", 72, 2, stud=1)
    t = on(t, "99781.dat", 72, 2, stud=3)
    t = on(t, "99781.dat", 72, 2, stud=6, turn=2)
    return on(t, "99781.dat", 72, 2, stud=8, turn=2)


# ---- cap -----------------------------------------------------------------------------------


def test_cap_tiles_a_4_x_6_plate_with_two_parts():
    t = place("", "3032.dat", 71, 0).line  # Plate 4 x 6
    r = cover.cap(t, 15, lines=[1])
    assert r.covered == 24 and not r.left and len(r.lines) == 2
    assert HELD in r.report.summary() and not r.report.problems
    same_as_place(t, r.heights[0].parts)


def test_cap_keeps_the_studs_asked_and_caps_each_step():
    t = on(base(), "3001.dat", 72, 1, stud=b(-30, -10))
    t = on(t, "3003.dat", 72, 2, stud=1)
    r = cover.cap(t, 15, lines=[1, 2, 3], keep=[(1, 1), (1, 2)])
    assert [s.number for s in r.kept] == [1, 2]
    assert sorted(h.depth for h in r.heights) == [8, 32, 56]  # base, brick top, 2 x 2 top
    assert HELD in r.report.summary() and not r.report.problems
    covered = {(s.line, s.number) for h in r.heights for p in h.parts for s in p.studs}
    assert (1, 1) not in covered and (1, 2) not in covered


def test_cap_says_which_part_is_in_the_way():
    t = on(base(), "87087.dat", 4, 1, stud=b(-10, -30))
    t = on(t, "3024.dat", 15, 2, stud=2)  # a 1 x 1 plate on the side stud, over the front row
    r = cover.cap(t, 15, box=(np.array([-30, -10, -60.0]), np.array([10, 0, -40.0])))
    assert [(s.line, s.number, why) for s, why in r.left] == [
        (1, 4, "line 3 (3024.dat) is in the way")
    ]
    assert r.covered == 2 and not r.report.problems


def test_cap_with_curved_edges_rounds_a_top_off():
    """A 4 x 6 plate: curved slopes from both sides meet in a crest; the corners, where a
    curve's side would face a drop and show the opening under its high end, stay flat tiles.
    A 6 x 8 plate: the middle lifted a plate and tiled, level with the crests (16 LDU up)."""
    narrow = place("", "3032.dat", 71, 0).line
    r = cover.cap(narrow, 15, lines=[1], edges="curved")
    (h,) = r.heights
    assert r.covered == 24 and not r.left and sorted(h.curved) == ["+x", "+z", "-x", "-z"]
    keys = [p.key for p in h.parts]
    assert keys.count("15068.dat") == 4 and keys.count("3069b.dat") == 4
    assert HELD in r.report.summary()
    same_as_place(narrow, h.parts)
    wide = base()
    r = cover.cap(wide, 15, lines=[1], edges="curved")
    (h,) = r.heights
    keys = [p.key for p in h.parts]
    assert r.covered == 48 and not r.left and not r.report.problems and HELD in r.report.summary()
    assert keys.count("15068.dat") == 8 and "3020.dat" in keys and "87079.dat" in keys
    tops = [looks.world_box(p)[0][1] for p in r.report.placed if p.line > 1]
    assert round(min(tops), 1) == -24  # the crests and the lifted middle: 8 + 16 LDU


def test_cap_curves_no_edge_that_meets_a_wall():
    """A brick standing at the back of the plate: the edge against it is no drop."""
    t = on(place("", "3032.dat", 71, 0).line, "3010.dat", 4, 1, stud=1)  # 1 x 4 brick, front row
    r = cover.cap(t, 15, lines=[1], edges="curved")
    (h,) = r.heights
    assert "-z" not in h.curved and not r.report.problems and HELD in r.report.summary()


# ---- skin ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "build, lines, up, plate, tile",
    [
        (lambda: _row("87087.dat"), [2, 3, 4, 5], 20, "3710.dat", "2431.dat"),
        # the bricks under the brackets are core within a plate behind: the panel covers them
        (lambda: _brackets("99780.dat"), [3, 5], 40, "3020.dat", "87079.dat"),
    ],
    ids=["87087 row", "99780 pair"],
)
def test_skin_presses_one_plate_on_four_side_studs_and_tiles_it(build, lines, up, plate, tile):
    t = build()
    r = cover.skin(t, 15, lines=lines)
    (pn,) = r.panels
    assert pn.facing == "-z" and (pn.across, pn.up) == (80, up) and pn.held == 4
    assert [p.key for p in pn.plates] == [plate] and [p.key for p in pn.tiles] == [tile]
    assert not pn.turnable and not r.left and HELD in r.report.summary()
    same_as_place(t, pn.plates)


def _row(part: str) -> str:
    t = base()
    for x in (-30, -10, 10, 30):
        t = on(t, part, 4, 1, stud=b(x, -50))
    return t


def _brackets(bracket: str) -> str:
    t = on(base(), "3004.dat", 4, 1, stud=b(-30, -50))
    t = on(t, bracket, 14, 2, stud=1)
    t = on(t, "3004.dat", 4, 1, stud=b(10, -50))
    return on(t, bracket, 14, 4, stud=1)


def test_skin_says_which_faces_have_no_side_studs_and_where_core_shows():
    r = cover.skin(bracket_body(), 15, lines=[3, 4, 5, 6])
    assert r.no_studs == ["-x", "+x"]
    for pn in r.panels:  # the brick's lower half under the brackets' flanges still shows
        assert pn.bare > 0 and pn.bare_box[2:] == (-18, -10) and 2 in pn.over


def test_skin_makes_the_aircraft_body_4_studs_wide():
    """Style guide, aircraft: on brackets, wall 4 + plate 8 + tile 8 = 20 LDU a side."""
    r = cover.skin(bracket_body(), 15, lines=[3, 4, 5, 6])
    assert sorted((p.facing, p.back, p.face) for p in r.panels) == [
        ("+z", 24, 40),
        ("-z", -24, -40),
    ]
    assert HELD in r.report.summary() and not r.report.problems
    zs = [looks.world_box(p) for p in r.report.placed if p.line > 1]
    assert min(lo[2] for lo, _ in zs) == -40 and max(hi[2] for _, hi in zs) == 40  # 4 studs


def test_skin_reports_a_plate_in_the_way_and_one_that_can_turn():
    alone = on(base(), "87087.dat", 4, 1, stud=b(-10, -30))
    r = cover.skin(alone, 15, lines=[2])
    assert len(r.panels[0].turnable) == 1 and HELD in r.report.summary()
    blocked = on(alone, "3024.dat", 1, 1, stud=b(-10, -50))  # in front of the side stud
    r = cover.skin(blocked, 15, lines=[2])
    assert not r.lines and "line 3 (3024.dat)" in r.left[0][1]


def test_skin_and_cap_bring_the_looks_into_the_official_ranges():
    """The guide's 4-wide body on brackets, standing on the ground, before and after skin and
    cap, against the slab fill makes in the same box (4 x 4 studs, 5 plates)."""
    t = place("", "3001.dat", 72, 0).line
    t = on(t, "99781.dat", 72, 1, stud=1)
    t = on(t, "99781.dat", 72, 1, stud=3)
    t = on(t, "99781.dat", 72, 1, stud=6, turn=2)
    t = on(t, "99781.dat", 72, 1, stud=8, turn=2)
    before = looks.measure(check(t, movement=False))
    skinned = cover.skin(t, 15, lines=[2, 3, 4, 5])
    capped = cover.cap(skinned.text, 15, lines=[1, 2, 3, 4, 5])
    after = looks.measure(capped.report)
    slab = looks.measure(check("\n".join(fill((-40, 0, -40), (4, 4, 5), 15, top="tiles").lines)))
    assert before is not None and after is not None and slab is not None
    assert not capped.report.problems and HELD in capped.report.summary()
    assert looks.outside(before.side_top_faces, looks.SIDE_TOP_FACES)
    assert not looks.outside(after.side_top_faces, looks.SIDE_TOP_FACES)
    assert not looks.outside(after.seams_per_stud, looks.SEAMS)
    assert looks.outside(slab.seams_per_stud, looks.SEAMS) and slab.side_top_faces == 0
    assert after.studs_showing == 0 < before.studs_showing
    print(
        f"seams per stud {before.seams_per_stud} -> {after.seams_per_stud} (the slab "
        f"{slab.seams_per_stud}; official {looks.SEAMS[0]}..{looks.SEAMS[1]}); sideways share "
        f"{before.side_top_faces} -> {after.side_top_faces} (the slab {slab.side_top_faces}; "
        f"official {looks.SIDE_TOP_FACES[0]}..{looks.SIDE_TOP_FACES[1]})"
    )


# ---- the tools -----------------------------------------------------------------------------


def _folder(tmp_path: Path, guide: bool) -> Path:
    f = tmp_path / ("on" if guide else "off")
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"mode": "tools", "guide": guide}))
    return f


def test_the_tools_exist_only_with_the_guide_on_and_answer(tmp_path):
    off = _folder(tmp_path, guide=False)
    assert "cap" not in {t["name"] for t in tools.tools_for(off)}
    assert tools.call_tool(off, "cap", {"colour": 15})[0]["text"].startswith("ERROR: there is")
    on_ = _folder(tmp_path, guide=True)
    (on_ / "model.ldr").write_text(bracket_body() + "\n")
    (on_ / "art.json").write_text(json.dumps({"build_refused": True}))  # past the brief's gate
    said = tools.call_tool(on_, "skin", {"lines": [3, 4, 5, 6], "colour": 15})[0]["text"]
    assert said.startswith("Skinned 2 panels (White, 15): lines 7 to 10, then a 0 STEP.")
    assert "held by 4 side studs" in said and "its face at z -40" in said
    said = tools.call_tool(on_, "cap", {"lines": [1], "colour": 72})[0]["text"]
    assert said.startswith("Capped 40 studs with ") and "No stud you named is left" in said
    assert HELD in check((on_ / "model.ldr").read_text()).summary()
