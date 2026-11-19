"""Tests for the free-build lab (bricksnap/lab/), a research prototype.

They read the real LDraw library zip (skipped when it is not on this machine) and cache what
they parse under the lab cache, so after the first run they are quick. No test starts a real
AI session: the session runner is tried with a stand-in ``claude`` on PATH.
"""

from __future__ import annotations

import base64
import json
import os
import stat
import sys
from pathlib import Path

import numpy as np
import pytest

from bricksnap.lab import ldraw_lib

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(),
    reason=f"the lab's tests read the LDraw parts library, which is not on this machine "
    f"({ldraw_lib.zip_path()}); the rest of BrickSnap does not need it",
)

UP = "1 0 0 0 1 0 0 0 1"


def line(colour: int, x: float, y: float, z: float, name: str, m: str = UP) -> str:
    return f"1 {colour} {x} {y} {z} {m} {name}"


@pytest.fixture(scope="module")
def lib() -> ldraw_lib.Library:
    return ldraw_lib.library()


def check(text: str):
    from bricksnap.lab.validate import check as run

    return run(text)


def kinds(report) -> list[str]:
    return [i.kind for i in report.problems]


# ---- reading parts ----------------------------------------------------------------------------


def test_resolve_and_header(lib):
    assert lib.resolve("3001.dat") == ("part", "3001.dat")
    assert lib.resolve("S\\3001S01.DAT") == ("subpart", "s/3001s01.dat")
    assert lib.resolve("stud.dat") == ("primitive", "stud.dat")
    assert lib.resolve("48/4-4cyli.dat") == ("primitive", "48/4-4cyli.dat")
    assert lib.resolve("nosuchpart.dat") is None
    h = lib.header("3001.dat")
    assert h.description == "Brick 2 x 4" and h.org == "Part" and h.category == "Brick"


def test_brick_geometry_and_connectors(lib):
    p = lib.part("3001.dat")
    assert np.allclose(p.bbox_min, [-40, 0, -20]) and np.allclose(p.bbox_max, [40, 24, 20])
    assert p.size() == (4.0, 2.0, 3.0)
    top = p.top_studs()
    assert len(top) == 8 and all(abs(s.pos[1]) < 1e-6 for s in top)
    assert sorted({round(float(s.pos[0])) for s in top}) == [-30, -10, 10, 30]
    tubes = p.tubes
    assert len(tubes) == 3 and all(t.open for t in tubes)
    assert all(np.allclose(t.end[1], 24) for t in tubes if t.end is not None)
    # the hollow underside counts as solid
    assert p.inside(np.array([[0.0, 20.0, 0.0], [-30.0, 22.0, 10.0]])).all()
    assert not p.inside(np.array([[0.0, -2.0, 0.0], [50.0, 10.0, 0.0]])).any()


def test_side_stud_and_other_connectors(lib):
    p = lib.part("87087.dat")
    dirs = sorted(ldraw_lib.direction_word(s.axis) for s in p.studs)
    assert dirs == ["-z", "up"]
    side = next(s for s in p.studs if s.axis[1] > -0.5)
    assert np.allclose(side.pos, [0, 10, -10])
    wheels = lib.part("4600.dat")
    assert sorted(c.kind for c in wheels.others) == ["wheel pin", "wheel pin"]
    clip = lib.part("60897.dat")
    assert [c.kind for c in clip.others] == ["clip"]


def test_arch_span_stays_open(lib):
    from bricksnap.lab.place import sockets

    p = lib.part("3659.dat")
    assert p.bottom_at(-31, 1) == pytest.approx(24, abs=0.5)  # a leg
    assert p.bottom_at(1, 1) < 12  # under the span
    assert [tuple(np.round(s.pos[[0, 2]])) for s in sockets(p)] == [(-30, 0), (30, 0)]


def test_sockets(lib):
    from bricksnap.lab.place import sockets

    s = sockets(lib.part("3001.dat"))
    assert [x.kind for x in s].count("grid") == 8 and [x.kind for x in s].count("tube") == 3
    assert len(sockets(lib.part("3794b.dat"))) == 2  # a jumper plate: two cells, one stud
    assert len(sockets(lib.part("30028b.dat"))) == 0  # a tyre takes no stud
    leaf = lib.part("2417.dat")
    rings = {tuple(np.round(t.end[[0, 2]])) for t in leaf.tubes if t.end is not None}
    assert {tuple(np.round(x.pos[[0, 2]])) for x in sockets(leaf)} == rings  # only its rings
    assert len(sockets(lib.part("4032a.dat"))) == 5  # round 2 x 2: four corners and the centre


# ---- search -----------------------------------------------------------------------------------

# query -> acceptable first results
QUERIES = {
    "brick 2 x 4": {"3001.dat"},
    "plate 1 x 1 round": {"6141.dat"},
    "tile 1 x 2": {"3069b.dat"},
    "slope 45 2 x 2": {"3039.dat"},
    "wing 2 x 4 left": {"41770a.dat", "41770b.dat"},
    "curved slope 4 x 1": {"61678.dat"},
    "brick 1 x 1 with stud on side": {"87087.dat"},
    "plate 1 x 2 with clip": {"78256.dat", "92280.dat", "60470a.dat", "60470b.dat"},
    "cone 1 x 1": {"4589.dat"},
    "arch 1 x 4": {"3659.dat"},
    "headlight brick": {"4070.dat"},
    "jumper plate": {"3794b.dat"},
    "cheese slope": {"54200.dat"},
    "bracket 1 x 2 - 1 x 2": {"99780.dat", "99781.dat"},
    "technic pin": {"3673.dat"},
    "round brick 2 x 2": {"6143.dat", "3941.dat"},
    "leaf": {"2682a.dat", "2423.dat", "2417.dat"},
    "plant leaves": {"2423.dat", "2417.dat"},
    "plate 2 x 2 with wheel pins": {"4488.dat", "4600.dat", "4870.dat"},
    "wheel for wheel pin": {"30027b.dat", "30027c.dat"},
    "steering wheel": {"874.dat", "2819.dat", "2741.dat", "30663.dat"},
    "3001": {"3001.dat"},
}


def test_search_puts_obvious_answers_first():
    from bricksnap.lab.search import load_index

    index = load_index()
    wrong = {}
    for query, ok in QUERIES.items():
        first = index.search(query, 3)[0].name
        if first not in ok:
            wrong[query] = first
    assert not wrong


def test_index_leaves_out_what_it_should():
    from bricksnap.lab.search import exclusion_reason, load_index

    assert exclusion_reason("4073.dat", "~Moved to 6141", "Part", "Plate") == "moved"
    assert exclusion_reason("3001p11.dat", "Brick 2 x 4 with Pattern", "Part", "") == "patterned"
    assert exclusion_reason("x.dat", "=Tile 1 x 1", "Part", "") == "alias"
    assert exclusion_reason("x.dat", "Brick 2 x 2", "Shortcut", "") == "shortcut"
    assert exclusion_reason("x.dat", "Duplo Brick 2 x 2", "Part", "Duplo") == "other system"
    index = load_index()
    assert "3001.dat" in index.by_name and "4073.dat" not in index.by_name
    assert index.stats["indexed"] > 4000


def test_hit_line_says_size_studs_origin():
    from bricksnap.lab.search import load_index

    text = load_index().search("brick 2 x 4", 1)[0].line()
    assert "3001.dat: Brick 2 x 4" in text and "4 x 2 studs x 3 plates" in text
    assert "8 on top" in text and "origin at the centre of the top face" in text


# ---- checking ---------------------------------------------------------------------------------


def test_two_bricks_stacked_is_fine():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -48, 0, "3001.dat"))
    assert r.ok and not r.issues
    assert r.summary().startswith("2 parts of 1 kind, no problems")
    assert [(x.holder, x.held, len(x.studs)) for x in r.links] == [(1, 2, 8)]


def test_half_a_stud_off():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 10, -48, 0, "3001.dat"))
    assert "stud" in kinds(r) and "loose" in kinds(r)
    stud = next(i for i in r.problems if i.kind == "stud")
    assert "line 2" in stud.text and "10 LDU off" in stud.text and "to 0 -48 0" in stud.text


def test_overlap():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 20, -24, 0, "3003.dat"))
    over = next(i for i in r.problems if i.kind == "overlap")
    assert "line 1" in over.text and "line 2" in over.text and "same space" in over.text


def test_floating():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -56, 0, "3001.dat"))
    loose = next(i for i in r.problems if i.kind == "loose")
    assert loose.lines == [2] and "floats 8 LDU" in loose.text and "move it down by 8" in loose.text


def test_tile_on_side_stud():
    tile_m = "1 0 0 0 0 -1 0 1 0"  # its top faces -z, its underside the brick's side
    r = check(line(4, 0, -24, 0, "87087.dat") + "\n" + line(15, 0, -14, -18, "3070b.dat", tile_m))
    assert r.ok and r.links[0].how == "sideways"


def test_plate_under_brick():
    r = check(line(14, 0, -8, 0, "3020.dat") + "\n" + line(4, 0, -32, 0, "3001.dat"))
    assert r.ok and r.links[0].holder == 1 and len(r.links[0].studs) == 8


def test_unknown_file_name_gets_close_names():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -48, 0, "30001.dat"))
    unknown = next(i for i in r.problems if i.kind == "unknown part")
    assert "Line 2" in unknown.text and "3001.dat (Brick 2 x 4)" in unknown.text


def test_bad_lines_and_matrices():
    text = "\n".join(
        [
            "1 4 0 -24 0 1 0 0 0 1 0 3001.dat",  # too short
            "1 4 0 -24 0 2 0 0 0 1 0 0 0 1 3001.dat",  # stretched
            "1 4 0 -24 40 -1 0 0 0 1 0 0 0 1 3001.dat",  # mirrored
            "1 4 0 -24 80 1 0 0 0 1 0 0 0 1 s/3001s01.dat",  # a sub-part
            "1 4 0 0 120 1 0 0 0 1 0 0 0 1 3001.dat",  # below the ground
        ]
    )
    k = kinds(check(text))
    for expected in ("format", "matrix", "mirrored", "not a part", "below ground"):
        assert expected in k


def test_nothing_on_the_ground_and_tipping():
    r = check(line(4, 0, -48, 0, "3001.dat"))
    assert "ground" in kinds(r)
    tower = [line(4, 0, -8, 0, "3024.dat")] + [
        line(4, 30, -8 - 24 * (k + 1), 0, "3009.dat") for k in range(1)
    ]
    r = check("\n".join(tower))
    assert "tips over" in kinds(r) or "loose" in kinds(r)


def test_clip_and_bar_are_not_checked_but_joined():
    clip = line(72, 0, -8, 0, "60897.dat")
    bar = line(0, 0, -60, -20, "87994.dat")  # 60 LDU long, standing in the clip
    r = check(clip + "\n" + bar)
    assert not r.problems
    assert any(i.kind == "joint" and "bar in a clip" in i.text for i in r.unchecked)


def test_report_text_sections():
    r = check(line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 10, -48, 0, "3001.dat"))
    text = r.text()
    assert text.startswith("SUMMARY: 2 parts of 1 kind, 2 problems")
    assert "PROBLEMS (fix these):" in text and "HOW IT HOLDS TOGETHER:" in text
    assert "rough" in text


# ---- placing by connection -------------------------------------------------------------------


def test_place_builds_valid_models():
    from bricksnap.lab.place import place

    text = ""

    def put(**kw):
        nonlocal text
        p = place(text, **kw)
        text += p.line + "\n"
        return p

    put(part="3001.dat", colour=4, line=0, x=0, z=0)
    p = put(part="3024.dat", colour=14, line=1, stud=1)
    assert p.line == "1 14 -30 -32 -10 1 0 0 0 1 0 0 0 1 3024.dat"
    put(part="87087.dat", colour=1, line=1, stud=8)
    put(part="3070b.dat", colour=15, line=3, stud=2)  # on the side stud
    put(part="3003.dat", colour=2, line=1, stud=2, turn=1)
    put(part="2417.dat", colour=2, line=5, stud=4, socket=4)  # a leaf on its ring
    put(part="3005.dat", colour=1, line=0, x=100, z=0)
    put(part="3024.dat", colour=1, line=7, stud=1)
    r = check(text)
    assert r.ok, r.text()
    assert len(r.links) == 6


def test_place_turn_counts_in_the_model_frame():
    from bricksnap.lab.place import place

    base = place("", "3032.dat", 15, 0, turn=1).line + "\n"
    p = place(base, "3009.dat", 4, 1, stud=1, turn=1)
    assert p.line.split()[5:14] == ["0", "0", "1", "0", "1", "0", "-1", "0", "0"]  # turn 1
    assert "spans x -40..-20" in p.note
    assert check(base + p.line).ok


def test_place_under_a_socket():
    from bricksnap.lab.place import place

    text = place("", "3001.dat", 4, 0, x=0, z=0).line + "\n"
    hang = place(text, "3024.dat", 1, 1, under_socket=1)
    assert hang.line == "1 1 -30 0 -10 1 0 0 0 1 0 0 0 1 3024.dat"


def test_place_errors_are_plain():
    from bricksnap.lab.place import PlaceError, place

    text = place("", "3001.dat", 4, 0).line + "\n"
    with pytest.raises(PlaceError, match="8 studs"):
        place(text, "3001.dat", 4, 1, stud=9)
    with pytest.raises(PlaceError, match="socket"):
        place(text, "3001.dat", 4, 1, stud=1, socket=99)
    with pytest.raises(PlaceError, match="Say where"):
        place(text, "3001.dat", 4, 1)
    with pytest.raises(PlaceError, match="search_parts"):
        place(text, "nosuch.dat", 4, 1, stud=1)


# ---- the tools --------------------------------------------------------------------------------


@pytest.fixture
def work(tmp_path: Path) -> Path:
    (tmp_path / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 2}))
    return tmp_path


def texts(blocks) -> str:
    return "\n".join(b["text"] for b in blocks if b["type"] == "text")


def test_tools_build_and_check(work, monkeypatch):
    from bricksnap.lab import picture, tools

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)  # no LeoCAD
    t = texts(tools.call_tool(work, "search_parts", {"query": "brick 2 x 4", "limit": 2}))
    assert "3001.dat" in t
    t = texts(tools.call_tool(work, "place", {"part": "3001.dat", "colour": 4, "line": 0}))
    assert "Added as line 1" in t
    t = texts(
        tools.call_tool(work, "place", {"part": "3001.dat", "colour": 1, "line": 1, "stud": 1})
    )
    assert "line 2 is held by" in t
    t = texts(tools.call_tool(work, "part_info", {"line": 2}))
    assert "stud 1: at (-30, -48, -10) pointing up" in t
    t = texts(tools.call_tool(work, "add", {"ldraw": line(2, 200, -80, 0, "3005.dat")}))
    assert "Loose" in t
    t = texts(tools.call_tool(work, "remove", {"lines": [3]}))
    assert "Removed line 3" in t
    t = texts(tools.call_tool(work, "check", {}))
    assert "no problems" in t and "Checks left after this one: 1" in t
    assert (work / "attempts" / "attempt-001-report.txt").exists()
    t = texts(tools.call_tool(work, "submit", {"ldraw": line(4, 0, -24, 0, "3001.dat")}))
    assert "Attempt 2" in t
    t = texts(tools.call_tool(work, "check", {}))
    assert t.startswith("ERROR:") and "all 2 checks" in t
    assert texts(tools.call_tool(work, "model", {})).startswith("  1: 1 4 0 -24 0")
    calls = (work / "calls.jsonl").read_text().splitlines()
    assert len(calls) == 10 and json.loads(calls[-2])["error"] is True  # the refused check


def test_tool_errors_never_raise(work):
    from bricksnap.lab import tools

    for name, args in (
        ("place", {"part": "3001.dat", "colour": "red", "line": 0}),
        ("place", {"part": "3001.dat", "colour": 4, "line": 5, "stud": 1}),
        ("search_parts", {"query": ""}),
        ("part_info", {"part": "nosuch"}),
        ("remove", {"lines": [9]}),
        ("look", {"latitude": 30, "longitude": 0}),
        ("no_tool", {}),
    ):
        blocks = tools.call_tool(work, name, args)
        assert len(blocks) == 1 and blocks[0]["text"].startswith("ERROR:"), (name, blocks)


def test_text_is_scrubbed(work):
    from bricksnap.lab import tools

    t = texts(tools.call_tool(work, "add", {"ldraw": f"0 from someone@example.com in {work}"}))
    assert "someone@example.com" not in (work / "model.ldr").read_text()
    assert str(work) not in t


def test_blind_mode_has_one_submit(tmp_path):
    from bricksnap.lab import tools

    (tmp_path / "config.json").write_text(json.dumps({"mode": "blind"}))
    assert [t["name"] for t in tools.tools_for(tmp_path)] == ["submit"]
    assert texts(tools.call_tool(tmp_path, "search_parts", {"query": "x"})).startswith("ERROR:")
    t = texts(tools.call_tool(tmp_path, "submit", {"ldraw": line(4, 0, -24, 0, "3001.dat")}))
    assert t == "Saved. Your model has been handed in."
    assert "ERROR" in texts(tools.call_tool(tmp_path, "submit", {"ldraw": "1 4 0 0 0 3001.dat"}))
    assert (tmp_path / "final.ldr").exists()


def test_reference_tool_appears_with_pictures(tmp_path):
    from PIL import Image

    from bricksnap.lab import tools

    (tmp_path / "config.json").write_text(json.dumps({"mode": "blind"}))
    (tmp_path / "reference").mkdir()
    Image.new("RGB", (20, 20), "red").save(tmp_path / "reference" / "reference-1.png")
    assert [t["name"] for t in tools.tools_for(tmp_path)] == ["submit", "reference"]
    blocks = tools.call_tool(tmp_path, "reference", {})
    assert [b["type"] for b in blocks] == ["text", "image"]


# ---- pictures (LeoCAD) ------------------------------------------------------------------------


def test_pictures(tmp_path):
    from PIL import Image

    from bricksnap.lab import picture

    if not picture.available():
        pytest.skip("LeoCAD or xvfb-run is not here")
    text = line(4, 0, -24, 0, "3001.dat") + "\n" + line(1, 0, -48, 0, "3003.dat") + "\n"
    out = picture.model_sheet(text, tmp_path / "m.png", title="test")
    with Image.open(out) as im:
        assert im.width == 3 * picture.PANEL_PX
        arr = np.asarray(im.convert("RGB"))
    # three panels with something red drawn in each
    for k in range(3):
        panel = arr[100:, k * picture.PANEL_PX : (k + 1) * picture.PANEL_PX]
        red = (panel[..., 0] > 150) & (panel[..., 1] < 80) & (panel[..., 2] < 80)
        assert red.sum() > 500
    assert picture.part_sheet("87087.dat", tmp_path / "p.png").exists()


def test_projection_matches_a_front_view():
    from bricksnap.lab.picture import camera, project

    eye, target = camera(np.array([-40.0, -24, -20]), np.array([40.0, 0, 20]), 0, 0)
    px = project(np.array([[40.0, -12, 0], [-40.0, -12, 0], [0, -24, -20]]), eye, target, 900)
    assert px[0, 0] > 450 > px[1, 0]  # +x is to the right seen from the front
    assert px[2, 1] < 450  # up (-y) is up in the picture


# ---- the MCP server ---------------------------------------------------------------------------


def test_mcp_server_serves_the_tools(work):
    import anyio
    from mcp import ClientSession, StdioServerParameters, stdio_client

    from bricksnap.lab.tools import TOOLS

    params = StdioServerParameters(
        command=sys.executable, args=["-m", "bricksnap.lab.mcp_server", str(work)]
    )

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            a = await session.call_tool("place", {"part": "3001.dat", "colour": 4, "line": 0})
            b = await session.call_tool(
                "place", {"part": "3001.dat", "colour": 4, "line": 7, "stud": 1}
            )
            return listed.tools, a, b

    listed, a, b = anyio.run(go)
    assert [t.name for t in listed] == [t["name"] for t in TOOLS]
    assert not a.is_error and "Added as line 1" in a.content[0].text
    assert b.is_error and "There is no line 7" in b.content[0].text


# ---- running a session (with a stand-in claude) ---------------------------------------------

FAKE = r"""#!{python}
import json, os, sys
argv = sys.argv[1:]
cfg = json.load(open(argv[argv.index("--mcp-config") + 1]))
server = cfg["mcpServers"]["bricksnap"]
folder = server["args"][-1]
record = {{"argv": argv, "stdin": sys.stdin.read(), "server": server}}
json.dump(record, open(os.environ["FAKE_RECORD"], "w"))
mode = json.load(open(os.path.join(folder, "config.json")))["mode"]
model = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 1 0 -48 0 1 0 0 0 1 0 0 0 1 3001.dat\n"
open(os.path.join(folder, "final.ldr" if mode == "blind" else "model.ldr"), "w").write(model)
events = [
    {{"type": "system", "subtype": "init", "model": "claude-fable-5-2", "apiKeySource": "none",
      "tools": ["mcp__bricksnap__submit"],
      "mcp_servers": [{{"name": "bricksnap", "status": "connected"}}]}},
    {{"type": "assistant", "message": {{"model": "claude-fable-5-2", "content": [
        {{"type": "tool_use", "id": "t1", "name": "mcp__bricksnap__check", "input": {{}}}}]}}}},
    {{"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
      "result": "Two red bricks. Mail me at someone@example.com.", "total_cost_usd": 0.5,
      "usage": {{"input_tokens": 100, "output_tokens": 20}},
      "modelUsage": {{"claude-fable-5-2": {{}}}}}},
]
for e in events:
    print(json.dumps(e), flush=True)
"""


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(FAKE.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("FAKE_RECORD", str(record))
    return record


@pytest.mark.parametrize("mode", ["tools", "blind"])
def test_run_session_saves_everything(fake_claude, tmp_path, monkeypatch, mode, capsys):
    from bricksnap.lab import picture, run

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    out = tmp_path / "session"
    with pytest.raises(SystemExit) as stop:
        run.main(["Build two bricks", "--out", str(out), "--max-checks", "5"], mode=mode)
    assert stop.value.code == 0
    record = json.loads(fake_claude.read_text())
    argv = record["argv"]
    assert argv[argv.index("--model") + 1] == "claude-fable-5-2"
    assert argv[argv.index("--allowedTools") + 1] == "mcp__bricksnap"
    assert "--strict-mcp-config" in argv and "--bare" not in argv
    prompt = argv[argv.index("--system-prompt-file") + 1]
    assert prompt.endswith("blind_prompt.md" if mode == "blind" else "prompt.md")
    assert record["server"]["args"][:2] == ["-m", "bricksnap.lab.mcp_server"]
    assert '"Build two bricks"' in record["stdin"]
    assert ("5 checks" in record["stdin"]) == (mode == "tools")
    session = json.loads((out / "session.json").read_text())
    assert session["ok"] and session["turns"] == 3 and session["mode"] == mode
    assert session["usage_reported"]["usage"] == {"input_tokens": 100, "output_tokens": 20}
    assert session["tools_called"] == {"check": 1}
    assert session["final_summary"].startswith("2 parts of 1 kind, no problems")
    assert "<account email>" in session["closing_words"]
    assert (out / "final.ldr").exists() and (out / "final-report.txt").exists()
    transcript = next((out / "transcript").glob("*.jsonl")).read_text()
    assert "someone@example.com" not in transcript and "<account email>" in transcript
    assert "results in" in capsys.readouterr().out


def test_run_refuses_a_used_folder(tmp_path):
    from bricksnap.lab import run

    (tmp_path / "x").write_text("y")
    with pytest.raises(SystemExit, match="not empty"):
        run.prepare(tmp_path, "tools", 5, [])


def test_message_and_prompts():
    from bricksnap.lab import run

    m = run.message("a red fire truck", "tools", 12, 2)
    assert '"a red fire truck"' in m and "12 checks" in m and "call reference first" in m
    assert "submit" in run.message("x", "blind", 12, 0)
    for f in (run.PROMPT_FILE, run.BLIND_PROMPT_FILE):
        text = f.read_text()
        assert "points DOWN" in text and "0 0 1 0 1 0 -1 0 0" in text


def test_message_for_a_change():
    from bricksnap.lab import run

    m = run.message(
        "make it blue",
        "tools",
        25,
        0,
        start="1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat",
        change_of="a red car",
    )
    assert '"a red car"' in m and '"make it blue"' in m and "Call check first" in m
    assert "Build this model" not in m and "25 checks" in m
    assert "# When you are asked for a change" in run.PROMPT_FILE.read_text()


def test_image_blocks_are_png(tmp_path):
    from PIL import Image

    from bricksnap.lab.tools import _image_block

    Image.new("RGB", (40, 30), "blue").save(tmp_path / "a.png")
    block = _image_block(tmp_path / "a.png")
    assert block["media_type"] == "image/png"
    assert base64.b64decode(block["data"]).startswith(b"\x89PNG")


# ---- starting from a model; filling, clearing and mirroring ----------------------------------

DUCK = (
    Path(__file__).resolve().parent.parent / "samples" / "projects" / "duck-showcase" / "build.ldr"
)


def test_big_model_report_is_short():
    import time

    if not DUCK.exists():
        pytest.skip("the duck sample is not here")
    started = time.monotonic()
    r = check(DUCK.read_text())
    assert time.monotonic() - started < 20
    assert r.ok, r.text()  # BrickSnap's own output passes
    text = r.text()
    assert len(text.splitlines()) < 12
    assert "parts are held by studs" in text and "held by a single stud" in text


def test_long_issue_lists_are_cut_short():
    lines = [line(4, 40 * k, -100, 0, "3005.dat") for k in range(60)]  # 60 loose bricks
    lines.append(line(4, -400, -24, 0, "3001.dat"))
    text = check("\n".join(lines)).text()
    assert "... and" in text and "more (" in text


def test_fill_is_one_piece_and_checks_clean():
    from bricksnap.lab.edit import fill

    solid = fill((-40, 0, -20), (4, 2, 3), 4)
    assert solid.lines == ["1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat", "0 STEP"]
    assert len(solid.free_studs) == 8
    for top, hollow in (("tiles", False), ("studs", True), ("studs", False)):
        f = fill((-60, 0, -60), (6, 6, 6), 1, top=top, hollow=hollow)
        assert check("\n".join(f.lines)).ok
        assert (len(f.free_studs) == 0) == (top == "tiles")
    tiled = fill((0, -24, 0), (2, 1, 2), 14, top="tiles")
    assert tiled.lines[-2].endswith("3069b.dat")  # the plain tile, not the grille


def test_fill_refuses_off_grid_corners():
    from bricksnap.lab.edit import EditError, fill

    with pytest.raises(EditError, match="multiples of 10"):
        fill((5, 0, 0), (2, 2, 3), 4)
    with pytest.raises(EditError, match="3 by 3"):
        fill((0, 0, 0), (2, 2, 3), 4, hollow=True)


def test_parts_in_box_modes():
    from bricksnap.lab.edit import parts_in_box

    text = "\n".join(
        [
            line(4, 0, -24, 0, "3001.dat"),
            line(1, 0, -48, 0, "3003.dat"),
            line(2, 60, -24, 0, "3005.dat"),
        ]
    )
    lo, hi = np.array([-45.0, -60, -25]), np.array([45.0, -30, 25])
    assert [p.line for p in parts_in_box(text, lo, hi)] == [2]
    assert [p.line for p in parts_in_box(text, lo, hi, "touching")] == [2]
    big_lo = np.array([-45.0, -60, -25])
    assert [p.line for p in parts_in_box(text, big_lo, np.array([45.0, 0, 25]), "inside")] == [1, 2]


def test_mirror():
    from bricksnap.lab.edit import mirror

    text = "\n".join(
        [
            line(4, 40, -24, 0, "3039.dat"),
            line(4, 60, -8, -40, "41770a.dat"),
            line(2, 50, -24, 60, "87087.dat", "0 0 1 0 1 0 -1 0 0"),
            line(4, 0, -24, 0, "3001.dat"),
            line(2, 30, -40, 80, "3741a.dat"),
        ]
    )
    out = {m.line: m for m in mirror(text, [1, 2, 3, 4, 5])}
    assert out[1].new_line == "1 4 -40 -24 0 1 0 0 0 1 0 0 0 1 3039.dat"
    assert out[2].new_line == "1 4 -60 -8 -40 1 0 0 0 1 0 0 0 1 41769a.dat"
    assert "Right" in out[2].note
    assert out[3].new_line == "1 2 -50 -24 60 0 0 -1 0 1 0 1 0 0 87087.dat"  # stud now +x
    assert out[4].new_line is None and "its own copy" in out[4].note
    assert out[5].new_line is None and "build that side yourself" in out[5].note


def test_centre_x_keeps_the_stud_grid():
    from bricksnap.lab.edit import centre_x

    text, shift = centre_x(line(4, 180, -24, 0, "3001.dat") + "\n0 STEP\n")
    assert shift == -180 and text.startswith("1 4 0 -24 0 ")
    assert centre_x(line(4, 30, -24, 0, "3005.dat"))[1] == -30


def test_tools_fill_mirror_remove_box(work, monkeypatch):
    from bricksnap.lab import tools

    t = texts(tools.call_tool(work, "fill", {"at": [-40, 0, -40], "size": [4, 4, 3], "colour": 4}))
    assert "Added" in t and "studs free on top" in t
    stack = "\n".join(
        [
            line(4, 200, -24, 0, "3001.dat"),
            line(1, 200, -48, 0, "3001.dat"),
            line(14, 170, -56, -10, "3024.dat"),
            line(2, 230, -72, 0, "87087.dat", "0 0 1 0 1 0 -1 0 0"),
        ]
    )
    n = len(tools._model(work).splitlines())
    tools.call_tool(work, "add", {"ldraw": stack})
    t = texts(tools.call_tool(work, "mirror", {"lines": [n + 4], "plane_x": 200}))
    assert "Added 1 mirrored parts" in t and "its own mirror image, at 170 -72 0" in t
    t = texts(
        tools.call_tool(
            work, "remove_box", {"min": [9, -6, -1], "max": [11, -3, 1], "unit": "studs"}
        )
    )
    assert t.startswith("Removed 1 parts") and f"lines {n + 2} " in t
    assert f"Now loose (3 parts): lines {n + 3}, {n + 4}, {n + 5}" in t
    t = texts(tools.call_tool(work, "remove_box", {"min": [500, 0, 0], "max": [600, -10, 10]}))
    assert "No part is in that box" in t
    for bad in (
        {"at": [5, 0, 0], "size": [2, 2, 3], "colour": 4},
        {"at": [0, 0], "size": [1, 1, 1], "colour": 4},
    ):
        assert texts(tools.call_tool(work, "fill", bad)).startswith("ERROR:")


@pytest.mark.parametrize("mode", ["tools", "blind"])
def test_run_with_start(fake_claude, tmp_path, monkeypatch, mode):
    from bricksnap.lab import picture, run

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    start = tmp_path / "start.ldr"
    start.write_text("0 a start\n" + line(4, 180, -24, 0, "3001.dat") + "\n")
    out = tmp_path / "session"
    with pytest.raises(SystemExit):
        run.main(["Improve it", "--out", str(out), "--start", str(start)], mode=mode)
    cfg = json.loads((out / "config.json").read_text())
    assert cfg["start"] == {"file": "start.ldr", "moved_x_by": -180.0}
    assert (out / "attempts" / "attempt-000-report.txt").read_text().startswith("Attempt 0")
    stdin = json.loads(fake_claude.read_text())["stdin"]
    if mode == "blind":
        assert "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat" in stdin  # the model is in the message
    else:
        assert "Call check first" in stdin
    session = json.loads((out / "session.json").read_text())
    assert session["checks"] == 0 and session["start"] == "start.ldr"


def test_start_model_ends_with_a_step(work):
    from bricksnap.lab import tools

    tools.start_model(work, line(4, 0, -24, 0, "3001.dat") + "\n\n")
    assert tools._model(work).splitlines()[-1] == "0 STEP"
    assert tools._attempts(work) == []  # attempt 0 is not one of the checks
