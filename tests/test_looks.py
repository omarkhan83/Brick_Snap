"""Tests for how a model looks against official sets: bricksnap/lab/looks.py, the HOW IT LOOKS
section of the guide-mode check, the "looks" record of a free build's run and the page's
"How it looks" block.

Every model here is made in the test (no official model file is used). They need the LDraw
parts library and skip without it. The browser test uses test_freebuild's web app fixtures
(no AI session is ever started: test_freebuild replaces them for its module, and this module
imports that guard too).
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_freebuild import (  # noqa: F401 (pytest fixtures used by the browser test)
    browser,
    built_pawn,
    made_car,
    no_real_ai,
    projects,
    running,
)
from test_webapp import ARTIFACTS, Tab

from bricksnap.lab import freebuild, ldraw_lib, looks, picture, tools
from bricksnap.lab.validate import check

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)

I3 = "1 0 0 0 1 0 0 0 1"
SCRATCH = Path.home() / ".cache" / "bricksnap" / "research" / "style" / "looks"


def ldr(lines: list[str]) -> str:
    return "\n".join(lines) + "\n"


def measure(lines: list[str]) -> looks.Looks:
    got = looks.measure(check(ldr(lines), movement=False))
    assert got is not None
    return got


def above_shares(lines: list[str]) -> dict[str, float]:
    sk = looks.skin(check(ldr(lines), movement=False).placed)
    k = sk.views["above"].kind
    tot = int((k > 0).sum())
    return {name: float((k == n).sum()) / tot for n, name in enumerate(looks.KINDS, 1)}


# ---- hand-made models (the study's sanity checks) ---------------------------------------

PLATE = [f"1 15 0 0 0 {I3} 3958.dat"]  # a 6 x 6 plate
TILED = PLATE + [f"1 15 {x} -8 {z} {I3} 3068b.dat" for x in (-40, 0, 40) for z in (-40, 0, 40)]
WALL = []  # 1 x 4 bricks, 8 long, 4 courses, running bond
for _k in range(4):
    if _k % 2 == 0:
        WALL += [f"1 4 {x} {-24 * _k - 24} 0 {I3} 3010.dat" for x in (-40, 40)]
    else:
        WALL += [f"1 4 {x} {-24 * _k - 24} 0 {I3} 3004.dat" for x in (-60, 60)]
        WALL += [f"1 4 0 {-24 * _k - 24} 0 {I3} 3010.dat"]
STACK = [f"1 14 {x} {-8 * k} 0 {I3} 3710.dat" for k in range(12) for x in (-40, 40)]
ROOF = [f"1 1 0 0 0 {I3} 3001.dat", f"1 1 -20 0 0 {I3} 15068.dat", f"1 1 20 0 0 {I3} 15068.dat"]
STAIRS = [f"1 2 0 {-8 * k} {20 * k} {I3} 3020.dat" for k in range(4)]
TECHNIC = [f"1 0 {x} 0 0 {I3} 3700.dat" for x in (-40, 0, 40)] + [
    "1 7 0 10 -10 0 0 1 0 1 0 -1 0 0 3673.dat"
]


def test_a_studded_plate_shows_every_stud():
    lk = measure(PLATE)
    assert (lk.studs, lk.studs_showing) == (36, 36)
    assert above_shares(PLATE)["studded"] == 1.0
    assert lk.seams_per_stud == 0.0 and lk.largest_colour == 1.0 and lk.colours_5pct == 1


def test_the_same_plate_tiled_shows_none():
    lk = measure(TILED)
    assert (lk.studs, lk.studs_showing) == (36, 0)
    assert above_shares(TILED)["smooth flat"] == 1.0
    assert lk.seams_per_stud == pytest.approx(1.111, abs=0.02)  # one seam in 16 LDU


def test_a_brick_wall_has_flat_sides_and_a_seam_per_course():
    lk = measure(WALL)
    assert (lk.studs, lk.studs_showing) == (32, 8)  # the top course
    assert lk.seams_per_stud == pytest.approx(0.596, abs=0.02)  # 3 seams in 100 LDU
    assert lk.plain_bricks == 1.0 and lk.not_upright == 0.0 and lk.side_top_faces == 0.0


def test_stacked_plates_have_many_seams():
    lk = measure(STACK)
    assert lk.seams_per_stud == pytest.approx(2.184, abs=0.03)  # 11 seams in 100 LDU
    assert lk.studs_showing == 8 and lk.plain_bricks == 0.0


def test_a_curved_slope_roof_is_curved_from_above_and_covers_its_studs():
    lk = measure(ROOF)
    shares = above_shares(ROOF)
    assert shares["curved or sloped"] == pytest.approx(0.761, abs=0.03)
    assert shares["studded"] == 0.0
    assert (lk.studs, lk.studs_showing) == (8, 0)  # the high end's hollow covers two of them
    assert lk.plain_bricks == pytest.approx(1 / 3, abs=0.01)


def test_a_staircase_of_plates_shows_its_treads():
    lk = measure(STAIRS)
    assert (lk.studs, lk.studs_showing) == (32, 20)
    assert above_shares(STAIRS)["studded"] == 1.0
    # seams only where the plates are flush (the stair's sides), not on its stepped front,
    # where each plate's face is 20 LDU behind the one below
    assert lk.seams_per_stud == pytest.approx(0.273, abs=0.02)


def test_a_plate_at_45_degrees_is_not_upright():
    c = "0.707107"
    tilted = f"1 0 0 0 {c} -{c} 0 {c} {c} 3020.dat"
    lk = measure([f"1 4 0 -8 0 {I3} 3020.dat", f"1 4 0 -60 100 {tilted}"])
    assert lk.not_upright == 0.5


def test_a_jumper_plate_is_half_studded_from_above():
    shares = above_shares([f"1 15 0 -8 0 {I3} 3794b.dat"])  # one stud in a 1 x 2 plate
    assert shares["studded"] == pytest.approx(0.48, abs=0.04)


def test_a_part_far_above_a_stud_does_not_cover_it():
    lk = measure([f"1 15 0 -8 0 {I3} 3958.dat", f"1 15 0 -30 0 {I3} 3958.dat"])  # 14 LDU gap
    assert (lk.studs, lk.studs_showing) == (72, 72)


def test_a_pin_fills_only_its_own_hole():
    lk = measure(
        [f"1 0 {x} -24 0 {I3} 6541.dat" for x in (-20, 0, 20)]  # holes 20 LDU apart
        + ["1 7 0 -14 -10 0 0 1 0 1 0 -1 0 0 3673.dat"]
    )
    assert lk.open_holes == 2


def test_a_colour_under_five_percent_is_not_counted():
    lines = [f"1 4 0 {-8 * k - 8} 0 {I3} 3710.dat" for k in range(20)]
    lines.append(f"1 15 50 -8 0 {I3} 3024.dat")
    r = check(ldr(lines), movement=False)
    shares = looks.colour_shares(looks.skin(r.placed))
    assert 0.01 < shares[15] < 0.05
    got = looks.measure(r)
    assert got is not None and got.colours_5pct == 1


def test_technic_bricks_show_their_open_holes_but_not_the_filled_one():
    lk = measure(TECHNIC)
    sk = looks.skin(check(ldr(TECHNIC), movement=False).placed)
    assert sk.holes == 3 and len(sk.filled) == 1
    assert lk.open_holes == 2
    assert lk.studs_showing == 6


# ---- sideways panels against stacked plates; stripes against one colour ------------------

CORE = [
    ("place", {"part": "3031.dat", "colour": 71, "line": 0, "x": 0, "z": 0}),
    ("place", {"part": "3003.dat", "colour": 71, "line": 1, "stud": 6, "socket": 1}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 2}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 3}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 14, "turn": 2}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 15, "turn": 2}),
]
PANEL = [
    ("place", {"part": "3020.dat", "colour": 4, "line": 3, "stud": 2, "socket": 2}),
    ("place", {"part": "3069b.dat", "colour": 15, "line": 7, "stud": 1, "turn": 3}),
    ("place", {"part": "3069b.dat", "colour": 15, "line": 7, "stud": 4, "turn": 3}),
    ("place", {"part": "11477.dat", "colour": 4, "line": 7, "stud": 2}),
    ("place", {"part": "11477.dat", "colour": 4, "line": 7, "stud": 3}),
]


def _folder(tmp_path: Path, name: str = "work", **config: Any) -> Path:
    f = tmp_path / name
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 9, **config}))
    return f


def _text(blocks: list[dict[str, Any]]) -> str:
    assert len(blocks) == 1 and blocks[0]["type"] == "text"
    return blocks[0]["text"]


@pytest.fixture
def no_pictures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)


def _built(tmp_path: Path, steps: list[tuple[str, dict[str, Any]]], name: str) -> str:
    f = _folder(tmp_path, name)
    for tool, args in steps:
        assert "ERROR" not in _text(tools.call_tool(f, tool, args))
    return (f / "model.ldr").read_text()


def test_a_tiled_sideways_panel_against_the_same_face_as_stacked_plates(tmp_path, no_pictures):
    panel = looks.measure(check(_built(tmp_path, CORE + PANEL, "panel"), movement=False))
    # the same core, its front face made of 1 x 4 plates stacked flat instead
    core = _built(tmp_path, CORE, "core")
    plates = core + ldr([f"1 4 0 {-16 - 8 * k} -50 {I3} 3710.dat" for k in range(5)])
    stacked = looks.measure(check(plates, movement=False))
    assert panel is not None and stacked is not None
    assert panel.seams_per_stud < stacked.seams_per_stud - 0.1
    assert panel.side_top_faces > stacked.side_top_faces + 0.05
    assert panel.not_upright > stacked.not_upright
    # and the panel's own numbers, as measured when this test was written
    assert panel.seams_per_stud == pytest.approx(0.105, abs=0.005)
    assert panel.not_upright == pytest.approx(5 / 11, abs=0.001)  # the 87087s, the panel, tiles
    assert panel.side_top_faces == pytest.approx(0.255, abs=0.005)
    assert stacked.seams_per_stud == pytest.approx(0.904, abs=0.01)


def test_stripes_against_one_colour():
    one = measure([f"1 4 0 {-8 * k} 0 {I3} 3710.dat" for k in range(8)])
    two = measure([f"1 {(4, 15)[k % 2]} 0 {-8 * k} 0 {I3} 3710.dat" for k in range(8)])
    assert one.largest_colour == 1.0 and one.colours_5pct == 1
    assert two.largest_colour == pytest.approx(0.5, abs=0.12) and two.colours_5pct == 2
    assert two.patch_coherence < one.patch_coherence / 2
    assert one.primary_share == 1.0 and two.primary_share < 0.65


def test_clips_bars_and_plain_bricks_by_description():
    parts = [
        f"1 4 0 0 0 {I3} 3001.dat",  # Brick 2 x 4
        f"1 4 0 -24 0 {I3} 4085c.dat",  # Plate 1 x 1 with Clip Vertical (Thick U-Clip)
        f"1 4 40 -24 0 {I3} 87994.dat",  # Bar 3L
        f"1 4 0 -48 0 {I3} 3700.dat",  # Technic Brick 1 x 2 with Hole: neither
    ]
    lk = measure(parts)
    assert lk.plain_bricks == 0.25 and lk.clips_bars == 0.5
    # a Technic part named with a handle is not a clip or bar; a sticker is not counted
    more = measure(
        [f"1 4 0 -24 0 {I3} 3001.dat", f"1 4 0 -48 0 {I3} 6221.dat"]  # Technic Handle
        + [f"1 4 60 -8 0 {I3} 003238a.dat"]  # Sticker Minifig Shield ...
    )
    assert more.plain_bricks == 0.5 and more.clips_bars == 0.0
    assert looks.PLAIN_BRICK.match("Brick 1 x 1 x 3") and looks.PLAIN_BRICK.match(
        "Brick 2 x 2 Corner"
    )
    assert not looks.PLAIN_BRICK.match("Brick 1 x 2 with Grille")
    assert looks.CLIP_BAR.search("Tile 1 x 2 with Bar Handle")
    assert not looks.CLIP_BAR.search("Plate 2 x 4") and not looks.CLIP_BAR.search("Barrel")


# ---- the words -----------------------------------------------------------------------------


def _looks(**kw: Any) -> looks.Looks:
    base: dict[str, Any] = dict(
        parts=100,
        seams_per_stud=0.3,
        not_upright=0.3,
        side_top_faces=0.15,
        largest_colour=0.4,
        largest_colour_name="White",
        colours_5pct=5,
        patch_coherence=0.18,
        primary_share=0.05,
        open_holes=0,
        plain_bricks=0.05,
        clips_bars=0.05,
        studs=500,
        studs_showing=50,
        studs_showing_share=0.1,
    )
    return looks.Looks(**{**base, **kw})


def test_a_model_inside_every_range_is_told_so_and_given_no_advice():
    got = looks.lines(_looks())
    assert len(got) == 6
    assert all("in range" in ln for ln in got)


def test_advice_only_outside_the_range_on_the_side_that_matters():
    bad = looks.lines(
        _looks(
            seams_per_stud=0.84,
            not_upright=0.03,
            largest_colour=0.77,
            open_holes=12,
            clips_bars=0.0,
            studs_showing_share=0.01,
        )
    )
    assert len(bad) == 6  # studs below the official range: a number, no line of advice
    assert "0.84 per stud" in bad[0] and "stacked plates" in bad[0]
    assert "panels on side studs" in bad[1]
    assert "white is 77%" in bad[2] and "big plain areas" in bad[2]
    assert "in range" in bad[3]
    assert "12 (official 0 to 2)" in bad[4] and "Turn them inward" in bad[4]
    assert "Use clips, bars and handles" in bad[5] and "plain bricks." not in bad[5]
    faces = looks.lines(_looks(side_top_faces=0.03))  # parts sideways, but no faces show
    assert "panels on side studs" in faces[1]
    patches = looks.lines(_looks(patch_coherence=0.5))  # largest colour in range
    assert "big plain areas" in patches[2]
    fine = looks.lines(_looks(seams_per_stud=0.1, open_holes=0))
    assert "below the range, which is fine" in fine[0]
    many = looks.lines(_looks(studs_showing_share=0.4))
    assert len(many) == 7 and many[-1].startswith("Studs showing: 40% of studs")
    assert not any("score" in ln.lower() or "/100" in ln for ln in bad + many)


def test_the_section_and_the_page_lines():
    lk = _looks(not_upright=0.03)
    sec = looks.section(lk)
    assert sec.startswith("HOW IT LOOKS (advice, never a problem")
    assert sec.count("\n- ") == 6
    page = looks.page_lines(looks.record(lk))
    assert page[1] == "Built sideways: 3% of parts (official sets: 17% to 43%)"
    assert 3 <= len(page) <= 4
    assert looks.page_lines({}) == [] and looks.section(None) == ""


# ---- determinism, the cache, speed ---------------------------------------------------------


def test_the_same_model_gives_the_same_numbers():
    text = ldr(WALL + TECHNIC)
    a = looks.measure(check(text, movement=False))
    looks._POINTS.clear()
    b = looks.measure(check(text, movement=False))
    assert a == b


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "looks-cache"
    monkeypatch.setattr(looks, "_cache_file", lambda key: root / f"{key}.v{looks.VERSION}.npz")
    looks._POINTS.clear()
    yield root
    looks._POINTS.clear()


def _same(a: looks.PartPoints, b: looks.PartPoints) -> bool:
    return all(np.array_equal(getattr(a, k), getattr(b, k)) for k in looks._FIELDS)


def test_the_disk_cache_is_faster_and_gives_the_same_points(cache_dir: Path):
    t0 = time.perf_counter()
    built = looks.part_points("3001.dat")
    cold = time.perf_counter() - t0
    assert (cache_dir / "3001.dat.v1.npz").is_file()
    looks._POINTS.clear()
    t0 = time.perf_counter()
    read = looks.part_points("3001.dat")
    warm = time.perf_counter() - t0
    assert _same(built, read)
    assert warm < cold / 2
    assert not list(cache_dir.glob("*.tmp"))


@pytest.mark.parametrize("damage", ["garbage", "short", "stamp"])
def test_a_damaged_cache_file_is_built_again(cache_dir: Path, damage: str):
    good = looks.part_points("3001.dat")
    path = cache_dir / "3001.dat.v1.npz"
    lib = ldraw_lib.library()
    if damage == "garbage":
        path.write_bytes(b"not a cache file at all")
    elif damage == "short":  # arrays that do not agree in length
        fields = {k: getattr(good, k) for k in looks._FIELDS}
        fields["stud"] = fields["stud"][:-5]
        with path.open("wb") as f:
            np.savez(f, stamp=np.array(lib.stamp), **fields)
    else:  # a cache from another library
        fields = {k: getattr(good, k) for k in looks._FIELDS}
        fields["pts"] = fields["pts"] + 100
        with path.open("wb") as f:
            np.savez(f, stamp=np.array("another-library"), **fields)
    looks._POINTS.clear()
    assert looks._read_cache(path, lib.stamp) is None
    again = looks.part_points("3001.dat")
    assert _same(good, again)
    assert looks._read_cache(path, lib.stamp) is not None  # written again, properly


def _block_of(n: int) -> list[str]:
    """``n`` parts: a block of 2 x 4 bricks in layers, in five colours."""
    out = []
    for k in range(n):
        layer, i = divmod(k, 50)
        x, z = divmod(i, 5)
        out.append(f"1 {(4, 15, 71, 0, 14)[k % 5]} {x * 80} {-24 * layer} {z * 40} {I3} 3001.dat")
    return out


def test_speed_on_a_250_part_model_once_warm():
    report = check(ldr(_block_of(250)), movement=False)
    looks.measure(report)  # warm
    best = min(_timed(lambda: looks.measure(report)) for _ in range(3))
    assert best < 0.5, best


def _timed(fn: Any) -> float:
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


# ---- the builder's check: guide mode only, advice only -------------------------------------


def test_guide_off_the_check_reply_has_no_looks_and_guide_on_ends_with_them(
    tmp_path: Path, no_pictures: None
):
    model = ldr(WALL)
    replies = {}
    for on in (False, True):
        f = _folder(tmp_path, f"g{on}", guide=on)
        (f / "model.ldr").write_text(model)
        replies[on] = _text(tools.call_tool(f, "check", {}))
    assert "HOW IT LOOKS" not in replies[False]
    head, sep, tail = replies[True].partition("\n\nHOW IT LOOKS (")
    assert sep and head == replies[False]
    assert tail.count("\n- ") == 7  # the wall shows 25% of its studs: above the range
    on_tools = {t["name"]: t for t in tools.tools_for(tmp_path / "gTrue")}
    off_tools = {t["name"]: t for t in tools.tools_for(tmp_path / "gFalse")}
    assert off_tools["check"] is tools.TOOLS[[t["name"] for t in tools.TOOLS].index("check")]
    extra = on_tools["check"]["description"].removeprefix(off_tools["check"]["description"])
    assert extra.startswith(" Its reply ends with a HOW IT LOOKS section")
    assert extra.count(". ") == 0 and "advice, never a problem" in extra


def test_looks_never_changes_a_check_submit_or_clean(
    tmp_path: Path, no_pictures: None, monkeypatch: pytest.MonkeyPatch
):
    model = ldr(WALL)

    def run_one(name: str) -> tuple[str, str]:
        f = _folder(tmp_path, name, guide=True)
        (f / "model.ldr").write_text(model)
        got = _text(tools.call_tool(f, "check", {}))
        sub = "\n".join(
            b["text"] for b in tools.call_tool(f, "submit", {"ldraw": model}) if b["type"] == "text"
        )
        return got.split("\n\nHOW IT LOOKS")[0], sub

    normal = run_one("normal")

    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("looks broke")

    monkeypatch.setattr(looks, "measure", broken)
    assert "SUMMARY: 10 parts of 2 kinds, no problems" in normal[0]
    assert "HOW IT LOOKS" not in normal[1]  # submit never has it
    assert run_one("broken") == normal
    monkeypatch.setattr(looks, "measure", lambda *a, **k: _looks(seams_per_stud=9.0))
    assert run_one("odd") == normal
    # a kept run: clean comes from the checker alone, looks is a record beside it
    monkeypatch.setattr(picture, "turntable", lambda text, out, **kw: [])
    monkeypatch.setattr(freebuild, "missing", lambda: None)
    path = tmp_path / "wall.ldr"
    path.write_text(model)
    monkeypatch.setattr(looks, "measure_text", lambda text: None)
    a = freebuild.describe(freebuild.import_run(tmp_path / "pa", path, name="A"))
    monkeypatch.setattr(looks, "measure_text", lambda text: _looks(seams_per_stud=9.0))
    b = freebuild.describe(freebuild.import_run(tmp_path / "pb", path, name="B"))
    assert a["clean"] == b["clean"] and a["summary"] == b["summary"]
    assert a["looks"] is None and a["looks_lines"] == []
    assert b["looks"]["seams_per_stud"] == 9.0 and len(b["looks_lines"]) == 4


def test_a_kept_run_records_how_it_looks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    monkeypatch.setattr(picture, "turntable", lambda text, out, **kw: [])
    path = tmp_path / "wall.ldr"
    path.write_text(ldr(WALL))
    folder = freebuild.import_run(tmp_path / "p", path, name="Wall")
    meta = json.loads((folder / "project.json").read_text())
    rec = meta["runs"][0]["looks"]
    assert rec == looks.record(measure(WALL))
    assert json.loads((folder / "runs" / "0001" / "record.json").read_text())["looks"] == rec


# ---- the page ------------------------------------------------------------------------------


@pytest.mark.browser
def test_browser_the_page_shows_how_it_looks(browser: Any, running: Any, projects: Path) -> None:  # noqa: F811
    about = freebuild.describe(projects / "car")
    assert len(about["looks_lines"]) == 4
    tab = Tab(browser, running.url, width=1280, height=900).open("p/car")
    try:
        page = tab.page
        page.wait_for_selector("#looks li")
        assert tab.text("#looksTitle") == "How it looks"
        items = page.locator("#looks li").all_text_contents()
        assert items == about["looks_lines"]
        assert any(
            t.startswith("Built sideways:") and "(official sets: 17% to 43%)" in t for t in items
        )
        page.locator("#looksBox").scroll_into_view_if_needed()
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / "free-looks.png"), full_page=True)
        with_ok = SCRATCH.parent.is_dir()
        if with_ok:
            SCRATCH.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ARTIFACTS / "free-looks.png", SCRATCH / "free-looks.png")
        tab.assert_clean()
    finally:
        tab.close()
    # a run kept before the record existed is measured when the page asks; nothing is written
    meta = json.loads((projects / "car" / "project.json").read_text())
    for r in meta["runs"]:
        r.pop("looks", None)
    (projects / "car" / "project.json").write_text(json.dumps(meta))
    before = (projects / "car" / "project.json").read_bytes()
    old = Tab(browser, running.url, width=1280, height=900).open("p/car")
    try:
        old.page.wait_for_selector("#looks li")
        assert old.page.locator("#looks li").all_text_contents() == about["looks_lines"]
        old.assert_clean()
    finally:
        old.close()
    assert (projects / "car" / "project.json").read_bytes() == before


def _old_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A free build kept before runs had a looks record."""
    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    monkeypatch.setattr(picture, "turntable", lambda text, out, **kw: [])
    path = tmp_path / "wall.ldr"
    path.write_text(ldr(WALL))
    folder = freebuild.import_run(tmp_path / "p", path, name="Wall")
    meta = json.loads((folder / "project.json").read_text())
    for r in meta["runs"]:
        r.pop("looks", None)
    (folder / "project.json").write_text(json.dumps(meta, indent=1))
    return folder


def test_an_old_run_is_measured_when_the_page_asks_once_and_never_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    folder = _old_project(tmp_path, monkeypatch)
    before = (folder / "project.json").read_bytes()
    calls = []
    real = freebuild.measure_looks
    monkeypatch.setattr(freebuild, "measure_looks", lambda text: calls.append(1) or real(text))
    assert freebuild.describe(folder)["looks_lines"] == []  # the cards and the CLI: no measuring
    assert calls == []
    first = freebuild.describe(folder, measure_missing=True)
    assert first["looks"] == looks.record(measure(WALL)) and len(first["looks_lines"]) == 4
    second = freebuild.describe(folder, measure_missing=True)
    assert second["looks_lines"] == first["looks_lines"] and len(calls) == 1
    assert (folder / "project.json").read_bytes() == before
    # a new version of the model file is measured again
    text = (folder / "model.ldr").read_text()
    (folder / "model.ldr").write_text(text + "0 STEP\n")
    freebuild.describe(folder, measure_missing=True)
    assert len(calls) == 2


def test_an_old_run_that_cannot_be_measured_shows_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    folder = _old_project(tmp_path, monkeypatch)
    before = (folder / "project.json").read_bytes()

    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("looks broke")

    monkeypatch.setattr(looks, "measure", broken)
    got = freebuild.describe(folder, measure_missing=True)
    assert got["looks"] is None and got["looks_lines"] == []
    assert got["clean"] is True and got["summary"].startswith("10 parts")
    monkeypatch.setattr(freebuild, "measure_looks", broken)  # even a failure outside looks
    (folder / "model.ldr").write_text((folder / "model.ldr").read_text() + "\n")
    assert freebuild.describe(folder, measure_missing=True)["looks_lines"] == []
    assert (folder / "project.json").read_bytes() == before


# ---- where (the facing pairs) -----------------------------------------------------------------


R90 = "0 0 1 0 1 0 -1 0 0"  # turned a quarter about y
FLANKS = [f"1 7 0 -24 0 {R90} 3001.dat"] + [  # a 2 x 4 brick along z, and either side of it
    f"1 14 {x} {-8 * k - 8} 0 {R90} 3710.dat" for x in (-30, 30) for k in range(3)
]  # three 1 x 4 plates stacked: the left and right flanks are plate seams end to end


def test_the_seams_line_says_which_flank_and_which_lines_and_how_to_fix_it():
    got = looks.measure_where(check(ldr(FLANKS), movement=False))
    assert got is not None
    lk, fs = got
    assert fs["left/right"].seams > fs["front/back"].seams > looks.SEAMS[1]
    first = looks.lines(lk, fs)[0]
    where = first.split("Where: ")[1]
    assert where.startswith("left/right 1.39, mostly lines 3, 6, 2, 4 (Plate 1 x 4); front/back")
    assert 'Skin those flanks: skin with facing "-x" or "+x" or "-z" or "+z"' in first, first
    assert "Where:" not in looks.lines(lk)[0]  # without the faces, the line as before
    inside = looks.lines(dataclasses.replace(lk, seams_per_stud=0.3), fs)[0]
    assert "Where:" not in inside  # in range: nothing to say where


def test_the_guide_mode_check_says_where_from_the_first_check():
    said = tools._looks_section(check(ldr(FLANKS), movement=False))
    assert "Where: left/right" in said and "Skin those flanks" in said
