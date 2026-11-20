"""Tests for what moves in a free build: joints, the moving modules, the movement check and
the builder's tools for them (bricksnap/lab/joints.py, modules.py, movement.py, tools.py).

They read the real LDraw library zip (skipped when it is not on this machine); the picture
tests also need LeoCAD and skip without it. No test starts an AI session: the test models
are built by calling the tools exactly as the builder would.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

from bricksnap.lab import ldraw_lib

pytestmark = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(),
    reason=f"these tests read the LDraw parts library, which is not on this machine "
    f"({ldraw_lib.zip_path()}); the rest of BrickSnap does not need it",
)

ARTIFACTS = Path(__file__).parent / "artifacts" / "moving"
STUDY = (
    Path(__file__).resolve().parent.parent / "docs" / "research" / "2026-11-19-ai-as-the-builder"
)


def check(text: str):
    from bricksnap.lab.validate import check as run

    return run(text)


def moving_problems(report) -> list[str]:
    return [i.text for i in report.problems if i.kind == "movement"]


# ---- the joint format -------------------------------------------------------------------------

LINE = (
    "0 !BRICKSNAP JOINT left-door SWING 0 90 AT 40 -32 0 AXIS 0 1 0 FIXED 4 MOVING 5 "
    "MODULE door-hinge-left"
)


def test_joint_line_reads_and_writes_back():
    from bricksnap.lab.joints import joint_line, parse_line

    j = parse_line(LINE, 6)
    assert (j.name, j.kind, j.low, j.high, j.fixed, j.moving, j.module, j.line) == (
        "left-door",
        "SWING",
        0,
        90,
        [4],
        [5],
        "door-hinge-left",
        6,
    )
    assert np.allclose(j.at, [40, -32, 0]) and np.allclose(j.axis, [0, 1, 0])
    assert joint_line(j) == LINE
    w = parse_line("0 !bricksnap joint w wheel at 0 -18 0 axis 2 0 0 fixed 1 moving 2 3")
    assert w.kind == "WHEEL" and np.allclose(w.axis, [1, 0, 0]) and w.turns_freely


@pytest.mark.parametrize(
    ("line", "words"),
    [
        ("0 !BRICKSNAP JOINT d HOP AT 0 0 0 AXIS 0 1 0 FIXED 1 MOVING 2", "SWING, SPIN or WHEEL"),
        ("0 !BRICKSNAP JOINT d SWING 0 90 AT 0 0 0 FIXED 1 MOVING 2", "AXIS"),
        ("0 !BRICKSNAP JOINT d SWING 10 90 AT 0 0 0 AXIS 0 1 0 FIXED 1 MOVING 2", "-360 to 0"),
        ("0 !BRICKSNAP JOINT d SPIN AT 0 0 0 AXIS 0 0 0 FIXED 1 MOVING 2", "0 0 0"),
        ("0 !BRICKSNAP JOINT d SPIN AT 0 0 0 AXIS 0 1 0 FIXED 1 MOVING 1", "both FIXED and MOVING"),
        ("0 !BRICKSNAP JOINT d SPIN AT 0 0 0 AXIS 0 1 0 FIXED x MOVING 2", "not a line number"),
        ("0 !BRICKSNAP JOINT two words SPIN AT 0 0 0 AXIS 0 1 0 FIXED 1 MOVING 2", "kind"),
    ],
)
def test_bad_joint_lines_say_what_is_wrong(line, words):
    from bricksnap.lab.joints import parse_line

    with pytest.raises(ValueError, match=re.escape(words)):
        parse_line(line)


def test_joint_lines_in_a_model():
    from bricksnap.lab.joints import parse, shifted

    text = "\n".join(
        [
            "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat",
            LINE,
            "0 removed: " + LINE.replace("left-door", "old"),
            LINE,
            "0 !BRICKSNAP JOINT broken",
        ]
    )
    joints, errors = parse(text)
    assert [j.name for j in joints] == ["left-door"] and joints[0].line == 2
    assert [n for n, _ in errors] == [4, 5] and "already called" in errors[0][1]
    moved = parse(shifted(text, -20))[0][0]
    assert np.allclose(moved.at, [20, -32, 0])
    # the checker reads a joint line as a comment: same parts, no format warnings
    report = check(
        "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n" + LINE.replace("4 MOVING 5", "1 MOVING 1")
    )
    assert len(report.placed) == 1


def test_a_model_without_joints_gets_the_report_it_always_got():
    text = "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 1 0 -48 0 1 0 0 0 1 0 0 0 1 3003.dat\n"
    report = check(text)
    assert report.movement == [] and "MOVEMENT" not in report.text()
    assert report.summary() == (
        "2 parts of 2 kinds, no problems: every part is held, nothing overlaps, and it stands."
    )


def test_centre_x_moves_the_joints_too():
    from bricksnap.lab.edit import centre_x
    from bricksnap.lab.joints import parse
    from bricksnap.lab.modules import place_module

    got = place_module("", "door-hinge-left", 4, 0, x=100, z=0)
    text, shift = centre_x("\n".join(got.lines) + "\n")
    assert shift != 0
    j = parse(text)[0][0]
    assert np.isclose(j.at[0], 100 + shift)
    assert check(text).moving_ok == 1


# ---- the modules ------------------------------------------------------------------------------


def module_names():
    from bricksnap.lab.modules import MODULES

    return list(MODULES)


@pytest.mark.parametrize("name", module_names())
def test_module_is_proven(name):
    """Parts exist; the checker passes it at rest apart from its own joint; it moves freely
    over its whole range; and its joint matches the module."""
    from bricksnap.lab.joints import parse
    from bricksnap.lab.modules import MODULES, module_text, verify

    mod = MODULES[name]
    lib = ldraw_lib.library()
    for p in mod.parts:
        assert lib.resolve(p.file) == ("part", p.file), p.file
    text = module_text(name)
    report = check(text)
    assert report.problems == [] and report.warnings == [], report.text()
    assert [i.kind for i in report.unchecked].count("joint") == 1  # the module's own, folded
    assert report.moving_ok == 1, report.text()
    j = parse(text)[0][0]
    assert verify(j, {p.line: p for p in report.placed}) is None
    assert mod.official and mod.attach and mod.moves


@pytest.mark.parametrize("name", module_names())
def test_module_turned_and_attached_stays_the_module(name):
    from bricksnap.lab.modules import place_module

    base = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3958.dat\n"  # a 6 x 6 plate on the ground
    got = place_module(base, name, 4, 1, stud=15, turn=1)
    text = base + "\n".join(got.lines) + "\n"
    report = check(text)
    # (on a plate the moving half of a hinge stands on studs, which ties it: that is the
    # model's business; here only whether the joint is still the module's)
    assert not [i for i in report.problems if "not the module" in i.text], report.text()
    assert len(report.movement) == 1
    assert got.joint.fixed[0] == 2 and got.joint.line == 2 + len(got.lines) - 1


def test_hand_written_module_joint_must_match_the_module():
    from bricksnap.lab.modules import module_text

    text = module_text("door-hinge-left")
    moved = text.replace(
        "1 71 0 -24 0 1 0 0 0 1 0 0 0 1 3830.dat", "1 71 0 -24 20 1 0 0 0 1 0 0 0 1 3830.dat"
    )
    assert moved != text
    report = check(moved)
    assert any("not where the module puts it" in t for t in moving_problems(report))
    wider = text.replace("SWING 0 90", "SWING 0 120")
    assert any("smaller range" in t for t in moving_problems(check(wider)))


def test_module_pictures(tmp_path):
    """The module sheet (at rest and opened) and LeoCAD drawing a module file as it is,
    joint line and all, with real parts rather than its placeholder boxes."""
    from PIL import Image

    from bricksnap.lab import modules, picture

    if not picture.available():
        pytest.skip("LeoCAD or xvfb-run is not here")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    for name in modules.MODULES:
        out = modules.module_sheet(name, ARTIFACTS / f"module-{name}.png")
        with Image.open(out) as im:
            arr = np.asarray(im.convert("RGB"))
        half = arr.shape[1] // 2
        for panel in (arr[60:, :half], arr[60:, half:]):
            assert (panel.min(axis=2) < 200).sum() > 2000  # something drawn in each
    # LeoCAD on the raw file
    ldr = tmp_path / "door.ldr"
    ldr.write_text("0 door hinge module\n" + modules.module_text("door-hinge-left", 4))
    png = tmp_path / "door.png"
    subprocess.run(
        [
            "xvfb-run",
            "-a",
            str(picture.leocad()),
            str(ldr),
            "-l",
            str(ldraw_lib.zip_path()),
            "-i",
            str(png),
            "-w",
            "400",
            "-h",
            "400",
        ],
        capture_output=True,
        timeout=120,
        check=False,
    )
    with Image.open(png) as im:
        a = np.asarray(im.convert("RGBA"))
    shades = np.unique(a[a[..., 3] > 250][:, :3] // 4, axis=0)
    assert len(shades) > 45  # a placeholder box has three flat faces (about 30 shades)


# ---- building test models through the tools ---------------------------------------------------


@pytest.fixture
def work(tmp_path: Path, monkeypatch) -> Path:
    from bricksnap.lab import picture

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    (tmp_path / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 30}))
    return tmp_path


def texts(blocks) -> str:
    return "\n".join(b["text"] for b in blocks if b["type"] == "text")


def call(work: Path, name: str, args: dict) -> str:
    from bricksnap.lab import tools

    t = texts(tools.call_tool(work, name, args))
    assert not t.startswith("ERROR:"), (name, args, t)
    return t


def stud(work: Path, line: int, x: float, z: float) -> int:
    t = call(work, "part_info", {"line": line})
    for m in re.finditer(r"stud (\d+): at \(([-\d.]+), ([-\d.]+), ([-\d.]+)\) pointing up", t):
        if abs(float(m[2]) - x) < 0.1 and abs(float(m[4]) - z) < 0.1:
            return int(m[1])
    raise AssertionError(f"no stud at {x}, {z} on line {line}")


def socket(work: Path, line: int, x: float, z: float) -> int:
    t = call(work, "part_info", {"line": line})
    for m in re.finditer(r"socket (\d+): at \(([-\d.]+), ([-\d.]+), ([-\d.]+)\)", t):
        if abs(float(m[2]) - x) < 0.1 and abs(float(m[4]) - z) < 0.1:
            return int(m[1])
    raise AssertionError(f"no socket at {x}, {z} on line {line}")


def checked(work: Path):
    from bricksnap.lab.tools import _model

    return check(_model(work))


def build_chassis(work: Path) -> None:
    """A bare rolling chassis: two pairs of small wheels and a 2 x 8 spine (lines 1 to 13)."""
    call(
        work,
        "place_module",
        {"module": "wheels-small", "colour": 72, "line": 0, "x": 0, "z": -40, "name": "front"},
    )
    call(
        work,
        "place_module",
        {"module": "wheels-small", "colour": 72, "line": 0, "x": 0, "z": 40, "name": "back"},
    )
    call(
        work,
        "place",
        {"part": "3034.dat", "colour": 4, "line": 1, "stud": 1, "socket": 7, "turn": 1},
    )


def test_rolling_chassis_rolls(work):
    build_chassis(work)
    t = call(work, "check", {})
    assert "all 2 joints move freely" in t.splitlines()[2]
    assert (
        "- 'front' (wheels-small, lines 1 to 5): the wheels turn freely all the way round, and "
        "the model rests on its wheels." in t
    )
    assert "PROBLEMS" not in t


def test_bumper_lower_than_the_wheels(work):
    build_chassis(work)
    call(
        work,
        "place",
        {
            "part": "3010.dat",
            "colour": 0,
            "line": 13,
            "under_socket": socket(work, 13, -10, -70),
            "turn": 1,
        },
    )
    report = checked(work)
    assert any(
        t.startswith("It does not rest on its wheels alone: line 14 (3010.dat Brick 1 x 4")
        for t in moving_problems(report)
    ), report.text()
    assert "1 about what moves" in report.summary() or "about what moves" in report.summary()


def test_wheels_that_rub(work):
    build_chassis(work)
    call(work, "place", {"part": "3031.dat", "colour": 4, "line": 13, "stud": 8, "socket": 2})
    report = checked(work)
    rub = [t for t in moving_problems(report) if "rub as they turn" in t]
    assert rub and "line 14 (3031.dat Plate 4 x 4" in rub[0] and "by 5 LDU" in rub[0], report.text()


def test_wheels_that_do_not_reach_the_ground(work):
    build_chassis(work)
    # a third axle hung under the spine, its plate level with the others: its tyres touch the
    # ground; one hung from a plate under the spine is a plate higher... instead raise one:
    from bricksnap.lab.tools import _model, _save_model

    lines = _model(work).splitlines()
    for n in range(7, 12):  # lift the back axle by 4 LDU
        tok = lines[n - 1].split()
        tok[3] = str(float(tok[3]) - 4)
        lines[n - 1] = " ".join(tok)
    j = lines[11].split()
    j[j.index("AT") + 2] = str(float(j[j.index("AT") + 2]) - 4)
    lines[11] = " ".join(j)
    _save_model(work, "\n".join(lines) + "\n")
    report = checked(work)
    assert any(
        "does not reach the ground: its lowest point is 4 LDU above it" in t
        for t in moving_problems(report)
    ), report.text()


def build_box(work: Path, floor_turned: bool = True) -> None:
    """A box with a lid on the lid hinge (lines 1 to 12; the lid is line 12, its joint 11)."""
    call(work, "place", {"part": "3032.dat", "colour": 15, "line": 0, "x": 0, "z": 0, "turn": 1})
    call(
        work,
        "place",
        {"part": "3010.dat", "colour": 15, "line": 1, "stud": stud(work, 1, -30, -30)},
    )
    call(
        work,
        "place",
        {"part": "3004.dat", "colour": 15, "line": 1, "stud": stud(work, 1, -30, 10), "turn": 1},
    )
    call(
        work,
        "place",
        {"part": "3004.dat", "colour": 15, "line": 1, "stud": stud(work, 1, 30, 10), "turn": 1},
    )
    call(work, "place", {"part": "2431.dat", "colour": 15, "line": 2, "stud": 1})
    call(work, "place", {"part": "3069b.dat", "colour": 15, "line": 3, "stud": 1, "turn": 1})
    call(work, "place", {"part": "3069b.dat", "colour": 15, "line": 4, "stud": 1, "turn": 1})
    call(
        work,
        "place",
        {"part": "3023b.dat", "colour": 15, "line": 1, "stud": stud(work, 1, -10, 30)},
    )
    t = call(
        work,
        "place_module",
        {
            "module": "lid-hinge",
            "colour": 71,
            "line": 8,
            "stud": stud(work, 8, 10, 30),
            "name": "lid",
        },
    )
    assert "joint 'lid' on line 11" in t
    call(
        work,
        "place",
        {
            "part": "3031.dat",
            "colour": 4,
            "line": 10,
            "stud": stud(work, 10, -10, 30),
            "socket": 14,
        },
    )


def test_box_lid_opens(work):
    build_box(work)
    t = call(work, "check", {})
    assert "no problems" in t.splitlines()[2]
    assert (
        "- 'lid' (lid-hinge, lines 9, 10): swings from 0 to 90 degrees with nothing in the way; "
        "2 parts move with it (lines 10, 12)." in t
    )


def test_brick_in_the_lids_swing(work):
    build_box(work)
    call(
        work, "place", {"part": "3004.dat", "colour": 1, "line": 1, "stud": stud(work, 1, -10, 50)}
    )
    call(work, "place", {"part": "3004.dat", "colour": 1, "line": 13, "stud": 1})
    call(work, "place", {"part": "3004.dat", "colour": 1, "line": 14, "stud": 1})
    report = checked(work)
    blocked = [t for t in moving_problems(report) if "opens only to" in t]
    assert blocked, report.text()
    assert re.search(
        r"opens only to \d+ degrees of 90: by \d+ degrees? line 12 \(3031.dat Plate 4 x 4\) "
        r"hits line 1[45]",
        blocked[0],
    )
    assert "swings only from 0 to" in "\n".join(report.movement)


def build_door(work: Path) -> None:
    """A small car side with one door on the door hinge (door: lines 5, 9, 10)."""
    call(work, "place", {"part": "3035.dat", "colour": 72, "line": 0, "x": 0, "z": 0, "turn": 1})
    call(
        work,
        "place",
        {"part": "3023b.dat", "colour": 4, "line": 1, "stud": stud(work, 1, 30, -10), "turn": 1},
    )
    call(
        work,
        "place",
        {
            "part": "3069b.dat",
            "colour": 71,
            "line": 1,
            "stud": stud(work, 1, 30, 10),
            "socket": 2,
            "turn": 1,
        },
    )
    call(
        work,
        "place_module",
        {
            "module": "door-hinge-left",
            "colour": 4,
            "line": 2,
            "stud": stud(work, 2, 30, -10),
            "socket": 2,
            "turn": 3,
            "name": "door",
        },
    )
    call(
        work,
        "place",
        {
            "part": "3004.dat",
            "colour": 4,
            "line": 4,
            "stud": stud(work, 4, 30, -30),
            "socket": 2,
            "turn": 1,
        },
    )
    call(work, "place", {"part": "3004.dat", "colour": 4, "line": 7, "stud": 1, "turn": 1})
    call(
        work,
        "place",
        {
            "part": "3004.dat",
            "colour": 4,
            "line": 5,
            "stud": stud(work, 5, 30, 10),
            "socket": 2,
            "turn": 1,
        },
    )
    call(work, "place", {"part": "3004.dat", "colour": 4, "line": 9, "stud": 1, "turn": 1})
    for n in (1, 11, 12):  # the wall behind the door, a stud's gap behind it
        call(
            work,
            "place",
            {
                "part": "3005.dat",
                "colour": 4,
                "line": n,
                "stud": stud(work, 1, 30, 70) if n == 1 else 1,
            },
        )


def test_door_opens(work):
    build_door(work)
    report = checked(work)
    assert report.ok and report.moving_ok == 1, report.text()
    assert report.movement == [
        "'door' (door-hinge-left, lines 4, 5): swings from 0 to 90 degrees with nothing in the "
        "way; 3 parts move with it (lines 5, 9, 10)."
    ]


def test_plate_bridging_door_and_body(work):
    build_door(work)
    call(
        work,
        "place",
        {
            "part": "3710.dat",
            "colour": 15,
            "line": 10,
            "stud": stud(work, 10, 30, 10),
            "socket": 2,
            "turn": 1,
        },
    )
    report = checked(work)
    tied = [t for t in moving_problems(report) if "cannot open" in t]
    assert tied == [
        "The joint 'door' (door-hinge-left, lines 4, 5) cannot open: something holds what moves "
        "to what stays. line 14 (3710.dat Plate 1 x 4, white, at 30 -96 0) is joined to line 10, "
        "which moves, and to line 8, which stays. Hold each part to one side only: remove it, or "
        "move it so it touches only the moving side or only the side that stays."
    ], report.text()


def test_door_on_studs_is_tied_by_what_it_stands_on(work):
    """The top half of a hinge brick standing on studs is held by them: the door cannot open."""
    call(work, "place", {"part": "3035.dat", "colour": 72, "line": 0, "x": 0, "z": 0, "turn": 1})
    call(
        work,
        "place_module",
        {
            "module": "door-hinge-left",
            "colour": 4,
            "line": 1,
            "stud": stud(work, 1, 30, -10),
            "socket": 2,
            "turn": 3,
        },
    )
    report = checked(work)
    assert any(
        "cannot open" in t and "line 1 (3035.dat Plate 4 x 8" in t for t in moving_problems(report)
    )


def test_door_jams_against_a_wall_at_its_far_end(work):
    """A door exactly as long as its opening: its far inner corner swings past the jamb."""
    build_door(work)
    for n in (11, 12, 13):
        call(work, "remove", {"lines": [n]})
    call(
        work,
        "place",
        {
            "part": "3004.dat",
            "colour": 4,
            "line": 1,
            "stud": stud(work, 1, 30, 50),
            "socket": 2,
            "turn": 1,
        },
    )
    call(work, "place", {"part": "3004.dat", "colour": 4, "line": 14, "stud": 1, "turn": 1})
    call(work, "place", {"part": "3004.dat", "colour": 4, "line": 15, "stud": 1, "turn": 1})
    report = checked(work)
    assert any("opens only to" in t for t in moving_problems(report)), report.text()


def test_head_on_a_turntable(work):
    call(work, "place", {"part": "3031.dat", "colour": 15, "line": 0, "x": 0, "z": 0})
    call(
        work,
        "place_module",
        {
            "module": "turntable-small",
            "colour": 72,
            "line": 1,
            "stud": stud(work, 1, -10, -10),
            "name": "head",
        },
    )
    call(work, "place", {"part": "3003.dat", "colour": 14, "line": 3, "stud": 1})  # the head
    report = checked(work)
    assert report.movement == [
        "'head' (turntable-small, lines 2, 3): turns freely all the way round with nothing in the "
        "way; 2 parts move with it (lines 3, 5)."
    ], report.text()
    # a 1 x 1 brick beside the head (not touching it), in the circle its corners sweep
    call(
        work, "place", {"part": "3005.dat", "colour": 1, "line": 1, "stud": stud(work, 1, 10, -10)}
    )
    report = checked(work)
    assert not [i for i in report.problems if i.kind == "overlap"]
    assert any(
        "cannot turn all the way round" in t and "line 6 (3005.dat" in t
        for t in moving_problems(report)
    ), report.text()


def test_joint_naming_a_removed_line(work):
    build_door(work)
    call(work, "remove", {"lines": [5]})
    report = checked(work)
    assert any(
        "names line 5 as MOVING, but line 5 is not a part" in t for t in moving_problems(report)
    )


# ---- the tools --------------------------------------------------------------------------------


def test_modules_tool(work, monkeypatch):
    from bricksnap.lab import modules, tools

    t = call(work, "modules", {})
    for name in modules.MODULES:
        assert f"- {name}: " in t
    monkeypatch.setattr(modules, "module_sheet", lambda name, out: _png(out))
    blocks = tools.call_tool(work, "modules", {"name": "lid-hinge"})
    assert [b["type"] for b in blocks] == ["text", "image"]
    card = blocks[0]["text"]
    assert "3937.dat Hinge 1 x 2 Base: fixed (the anchor)" in card and "3937c01" in card
    assert "designed to be used" in card


def _png(out: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (20, 20), "red").save(out)
    return out


def test_tools_are_listed():
    from bricksnap.lab.tools import TOOLS

    names = [t["name"] for t in TOOLS]
    assert names[-3:] == ["modules", "place_module", "joint"]
    json.dumps(TOOLS)


@pytest.mark.parametrize(
    ("name", "args", "words"),
    [
        ("modules", {"name": "flux-capacitor"}, "no module"),
        ("place_module", {"module": "flux", "colour": 4, "line": 0}, "no module"),
        ("place_module", {"module": "lid-hinge", "colour": "red", "line": 0}, "whole number"),
        ("place_module", {"module": "lid-hinge", "colour": 4, "line": 9, "stud": 1}, "no line 9"),
        (
            "place_module",
            {"module": "lid-hinge", "colour": 4, "line": 0, "name": "two words!"},
            "one word",
        ),
        (
            "place_module",
            {"module": "lid-hinge", "colour": 4, "line": 0, "turn": 5},
            "from 0 to 3",
        ),
        (
            "joint",
            {
                "name": "j",
                "kind": "hop",
                "fixed": [1],
                "moving": [2],
                "at": [0, 0, 0],
                "axis": [0, 1, 0],
            },
            "kind",
        ),
        (
            "joint",
            {
                "name": "j",
                "kind": "spin",
                "fixed": [1],
                "moving": [1],
                "at": [0, 0, 0],
                "axis": [0, 1, 0],
            },
            "both",
        ),
        (
            "joint",
            {
                "name": "j",
                "kind": "spin",
                "fixed": [1],
                "moving": [2],
                "at": [0, 0],
                "axis": [0, 1, 0],
            },
            "at must be",
        ),
        (
            "joint",
            {
                "name": "j",
                "kind": "swing",
                "fixed": [1],
                "moving": [2],
                "at": [0, 0, 0],
                "axis": [0, 1, 0],
            },
            "min and max",
        ),
        (
            "joint",
            {
                "name": "j",
                "kind": "spin",
                "fixed": [1],
                "moving": [7],
                "at": [0, 0, 0],
                "axis": [0, 1, 0],
            },
            "not a part",
        ),
        ("look", {"latitude": 30, "longitude": 0, "open": "all"}, "no joints"),
    ],
)
def test_bad_calls_say_what_to_fix(work, name, args, words):
    from bricksnap.lab import tools

    call(work, "place", {"part": "3001.dat", "colour": 4, "line": 0})
    call(work, "place", {"part": "3001.dat", "colour": 4, "line": 1, "stud": 1})
    blocks = tools.call_tool(work, name, args)
    assert len(blocks) == 1 and blocks[0]["text"].startswith("ERROR:"), blocks
    assert words in blocks[0]["text"]


def test_place_module_refuses_a_name_twice(work):
    from bricksnap.lab import tools

    call(
        work, "place_module", {"module": "turntable-small", "colour": 4, "line": 0, "name": "head"}
    )
    t = texts(
        tools.call_tool(
            work,
            "place_module",
            {"module": "turntable-small", "colour": 4, "line": 0, "x": 60, "name": "head"},
        )
    )
    assert t.startswith("ERROR:") and "already a joint called 'head'" in t


def test_joint_tool_declares_and_refuses(work):
    """A wheel placed by hand on a wheel pin may be declared about the pin's own line; the same
    parts about another line, or two bricks held by studs, may not."""
    from bricksnap.lab import tools

    call(
        work,
        "add",
        {
            "ldraw": "\n".join(
                [
                    "1 72 0 -30 0 1 0 0 0 1 0 0 0 1 4488.dat",
                    "1 71 30 -25 0 0 0 -1 0 1 0 1 0 0 6014b.dat",
                    "1 0 36 -25 0 0 0 -1 0 1 0 1 0 0 6015.dat",
                    "1 4 -100 -24 0 1 0 0 0 1 0 0 0 1 3001.dat",
                    "1 4 -100 -48 0 1 0 0 0 1 0 0 0 1 3001.dat",
                ]
            )
        },
    )
    bad = {"name": "w", "kind": "wheel", "fixed": [1], "moving": [2, 3]}
    t = texts(tools.call_tool(work, "joint", {**bad, "at": [0, -25, 5], "axis": [1, 0, 0]}))
    assert t.startswith("ERROR:") and "not the joint's own" in t and "(22, -25, 0)" in t
    t = texts(tools.call_tool(work, "joint", {**bad, "at": [0, -25, 0], "axis": [0, 1, 0]}))
    assert t.startswith("ERROR:") and "not the joint's own" in t
    t = texts(
        tools.call_tool(
            work,
            "joint",
            {
                "name": "s",
                "kind": "swing",
                "fixed": [4],
                "moving": [5],
                "at": [-100, -48, 0],
                "axis": [1, 0, 0],
                "min": 0,
                "max": 90,
            },
        )
    )
    assert t.startswith("ERROR:") and "held by studs do not turn" in t
    t = texts(tools.call_tool(work, "joint", {**bad, "fixed": [1, 4]}))
    assert t.startswith("ERROR:")
    t = call(work, "joint", {**bad, "at": [0, -25, 0], "axis": [1, 0, 0]})
    assert "Added the joint 'w' as line 6" in t and "the wheels turn freely" in t
    report = checked(work)
    assert any("declared yourself" in i.text for i in report.warnings)
    # the tyre left out of MOVING is found by itself, with no false complaints
    call(work, "remove", {"lines": [6]})
    call(work, "joint", {**bad, "name": "w2", "moving": [2], "at": [0, -25, 0], "axis": [1, 0, 0]})
    report = checked(work)
    about_wheel = [i for i in report.problems if i.kind == "movement" and {2, 3} & set(i.lines)]
    assert not about_wheel, report.text()
    assert "'w2' (declared by the builder, lines 1 to 3): the wheels turn freely" in report.text()


def _matrix_for(axis: np.ndarray) -> np.ndarray:
    """A rotation taking a bar's own length (its y) to ``axis`` (an axis direction)."""
    a = np.round(axis).astype(int)
    k = int(np.argmax(np.abs(a)))
    if k == 1:
        return np.eye(3).ravel()
    if k == 0:
        return np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]]).ravel()
    return np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]]).ravel()


def test_look_with_joints_open(work, monkeypatch):
    from bricksnap.lab import picture, tools

    seen = []

    def fake_view(text, out, lat, lon, title=""):
        seen.append(text)
        return _png(out)

    monkeypatch.setattr(picture, "view", fake_view)
    build_box(work)
    blocks = tools.call_tool(work, "look", {"latitude": 20, "longitude": 90, "open": {"lid": 90}})
    assert [b["type"] for b in blocks] == ["image"]
    lid = seen[-1].splitlines()[11].split()
    assert lid[-1] == "3031.dat" and float(lid[3]) < -48  # it stands up
    t = texts(tools.call_tool(work, "look", {"latitude": 20, "longitude": 0, "open": {"lid": 120}}))
    assert t.startswith("ERROR:") and "swings from 0 to 90 degrees" in t
    t = texts(tools.call_tool(work, "look", {"latitude": 20, "longitude": 0, "open": {"hood": 10}}))
    assert t.startswith("ERROR:") and "The joints are: lid" in t
    tools.call_tool(work, "look", {"latitude": 20, "longitude": 0, "open": "all"})
    assert seen[-1] == seen[0]
    # the model itself is unchanged
    assert "1 4 0 -48 0 1 0 0 0 1 0 0 0 1 3031.dat" in tools._model(work)


def test_opened_carries_what_rides_on_the_joint():
    from bricksnap.lab.joints import opened, parse
    from bricksnap.lab.modules import module_text

    text = module_text("door-hinge-left") + "1 4 20 -48 10 1 0 0 0 1 0 0 0 1 3004.dat\n"
    assert check(text).movement[0].endswith("2 parts move with it (lines 2, 4).")
    j = parse(text)[0][0]
    out = opened(text, {j.name: 90}).splitlines()
    assert out[0] == text.splitlines()[0]  # the base stays
    brick = out[3].split()
    assert np.allclose([float(v) for v in brick[2:5]], [10, -48, -20])  # swung toward -z


# ---- last night's car ------------------------------------------------------------------------


def test_last_nights_car_is_unchanged_without_joints():
    text = (STUDY / "with-tools" / "car.ldr").read_text()
    report = check(text)
    assert report.movement == [] and "MOVEMENT" not in report.text()
    assert report.ok


# ---- the prompt ------------------------------------------------------------------------------


def test_prompt_has_the_method_for_what_moves():
    from bricksnap.lab import run

    text = run.PROMPT_FILE.read_text()
    assert "# When the subject moves" in text
    for words in (
        "A vehicle's wheels always turn",
        "only when the person asks for it",
        "mechanics first",
        "In a change, keep the joints there are",
        "mirror refuses a module's parts",
        '"open"',
    ):
        assert words in text, words
    for kept in (
        "# When you start from a model",
        "# When you are asked for a change",
        "points DOWN",
    ):
        assert kept in text
    assert len(text) < 1.15 * 9251  # main's prompt is 9251 characters


# ---- the free-build project ------------------------------------------------------------------


def test_free_build_records_what_moves_and_an_opened_picture(tmp_path, monkeypatch):
    from PIL import Image

    from bricksnap.lab import freebuild, picture
    from bricksnap.lab.modules import module_text

    drawn = {}

    def sheet(text, out, title=""):
        drawn[out.name] = text
        Image.new("RGB", (20, 20), "white").save(out)
        return out

    def turntable(text, out_dir, views=12, **kw):
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = [out_dir / f"turn-{k:02d}.png" for k in range(views)]
        for p in paths:
            Image.new("RGB", (20, 20), "white").save(p)
        return paths

    monkeypatch.setattr(picture, "model_sheet", sheet)
    monkeypatch.setattr(picture, "turntable", turntable)
    ldr = tmp_path / "box.ldr"
    ldr.write_text(module_text("lid-hinge") + "1 4 0 -32 -10 1 0 0 0 1 0 0 0 1 3020.dat\n")
    folder = freebuild.import_run(tmp_path / "projects", ldr, words="a lid", name="Lid")
    about = freebuild.describe(folder)
    assert about["moves"] and "swings from 0 to 90 degrees" in about["moves"][0]
    assert about["opened"] == "pictures/opened.png"
    assert drawn["opened.png"] != drawn["sheet.png"]  # drawn with the lid up
    assert freebuild.read_movement("SUMMARY: x\n\nHOW IT HOLDS TOGETHER:\n- y\n") == []


# ---- joint-free models: the whole report is main's ------------------------------------------

MAIN = json.loads((Path(__file__).parent / "moving_main_reports.json").read_text())


@pytest.mark.parametrize("key", [k for k in MAIN if not k.startswith("turntable")])
def test_joint_free_report_is_mains_word_for_word(key):
    v = MAIN[key]
    if key.startswith("study:"):
        text, want = (STUDY / key.split(":", 1)[1]).read_text(), v
    else:
        text, want = v["model"], v["report"]
    assert check(text).text() == want


def test_a_turntable_without_a_joint_line_is_the_one_documented_change():
    v = MAIN["turntable on a plate, no joint line"]
    assert "occupy the same space" in v["report"] and "2 problems" in v["report"]
    got = check(v["model"]).text()
    assert got.startswith(
        "SUMMARY: 4 parts of 4 kinds, no problems: every part is held (2 of them only by joints "
        "the checker cannot confirm), nothing overlaps, and it stands. (2 joints not checked)"
    )
    assert "line 2 (3680.dat) and line 3 (3679.dat): a turntable joint" in got
    assert "MOVEMENT" not in got


# ---- each module's seat, proved against the library itself ----------------------------------


def _shortcut(name: str) -> list[tuple[str, np.ndarray, np.ndarray]]:
    lib = ldraw_lib.library()
    out = []
    found = lib.resolve(name)
    assert found is not None
    for raw in lib.text(*found).splitlines():
        tok = raw.split()
        if len(tok) >= 15 and tok[0] == "1":
            nums = [float(v) for v in tok[2:14]]
            out.append((tok[14].lower(), np.array(nums[0:3]), np.array(nums[3:12]).reshape(3, 3)))
    return out


def _rel(a_pos, a_m, b_pos, b_m):
    """Where b is in a's frame: (position, matrix)."""
    inv = np.linalg.inv(a_m)
    return inv @ (b_pos - a_pos), inv @ b_m


def _line_off(p: np.ndarray, d: np.ndarray, q: np.ndarray, e: np.ndarray) -> float:
    """How far apart two lines are, or 99 when they are not parallel."""
    d, e = d / np.linalg.norm(d), e / np.linalg.norm(e)
    if abs(float(np.dot(d, e))) < 0.9999:
        return 99.0
    r = q - p
    return float(np.linalg.norm(r - np.dot(r, d) * d))


def seat_errors(mod) -> list[str]:
    """What is wrong with a module's numbers, judged by the library: its parts' places from the
    library's assembled shortcut files where there is one, else from the connectors' own axes
    and the parts' real surfaces."""
    from bricksnap.lab import solid
    from bricksnap.lab.modules import _matrix

    lib = ldraw_lib.library()
    errs = []
    parts = [(p.file, np.array(p.pos, float), _matrix(p.m), p) for p in mod.parts]
    at, axis = np.array(mod.at, float), np.array(mod.axis, float)
    anchor = parts[0]
    sc = {
        ("3937.dat", "3938.dat"): "3937c01.dat",
        ("3680.dat", "3679.dat"): "3680c01.dat",
        ("3403.dat", "3404.dat"): "3403c01.dat",
        ("4624.dat", "3641.dat"): "4624c01.dat",
        ("6014b.dat", "6015.dat"): "6014bc01.dat",
    }

    def check_pair(a, b):
        name = sc.get((a[0], b[0]))
        if not name or np.linalg.norm(a[1] - b[1]) > 15:  # each wheel with its own tyre
            return
        ref = {f: (p, m) for f, p, m in _shortcut(name)}
        want = _rel(*ref[a[0]], *ref[b[0]])
        got = _rel(a[1], a[2], b[1], b[2])
        if np.linalg.norm(got[0] - want[0]) > 0.01 or np.abs(got[1] - want[1]).max() > 1e-6:
            errs.append(f"{b[0]} is not where {name} puts it beside {a[0]}")

    for a in parts:
        for b in parts:
            if a is not b:
                check_pair(a, b)
    files = [p[0] for p in parts]
    if mod.kind == "WHEEL":
        plate = lib.part(anchor[0])
        pins = [c for c in plate.others if c.kind == "wheel pin"]
        for c in pins:  # the module's axle line is every pin's line
            if _line_off(anchor[2] @ c.pos + anchor[1], anchor[2] @ c.axis, at, axis) > 0.01:
                errs.append("the axle line is not the wheel pins' line")
        for f, pos, m, p in parts[1:]:
            if p.role == "tyre":
                continue
            # the rim's own axis (its z) through its origin, on a pin's line
            if (
                min(
                    _line_off(
                        pos,
                        m @ np.array([0, 0, 1.0]),
                        anchor[2] @ c.pos + anchor[1],
                        anchor[2] @ c.axis,
                    )
                    for c in pins
                )
                > 0.01
            ):
                errs.append(f"{f} is not on a wheel pin's line")
            # its inner face against the end of the pin's fillet (the pin's base, 2 LDU out
            # from the plate's side, where the wheel pin primitive starts)
            pts = solid.surface(f) @ m.T + pos
            c = min(pins, key=lambda c: float(np.linalg.norm(anchor[2] @ c.pos - pos)))
            base = anchor[2] @ c.pos + anchor[1]
            out = -(anchor[2] @ c.axis)  # the pin points into the plate; out is away from it
            face = float(np.min((pts - base) @ out))
            if abs(face) > 0.05:
                errs.append(f"{f}'s inner face is {face:.2f} LDU from the pin's base, not on it")
    if mod.kind == "SWING" and "3830.dat" in files:
        top = next(p for p in parts if p[0] == "3830.dat")
        pin = next(c for c in lib.part("3830.dat").others if c.kind == "pin")
        if _line_off(top[2] @ pin.pos + top[1], top[2] @ pin.axis, at, axis) > 0.01:
            errs.append("the axis is not the hinge pin's line")
        base = next(p for p in parts if p[0] == "3831.dat")
        if np.linalg.norm(base[1] - top[1]) > 0.01:
            errs.append("the two halves of the hinge brick are not at one place")
    if "3937.dat" in files:
        base = next(p for p in parts if p[0] == "3937.dat")
        centres = []
        found = lib.resolve("3937.dat")
        assert found is not None
        for raw in lib.text(*found).splitlines():
            tok = raw.split()
            if len(tok) >= 15 and tok[0] == "1" and "cyl" in tok[14]:
                nums = [float(v) for v in tok[2:14]]
                m = np.array(nums[3:12]).reshape(3, 3)
                if abs(abs((m @ [0, 1.0, 0])[0]) - np.linalg.norm(m @ [0, 1.0, 0])) < 1e-6:
                    centres.append(np.array(nums[0:3]))
        knuckle = base[2] @ np.median(np.array(centres), axis=0) + base[1]
        if _line_off(knuckle, base[2] @ np.array([1.0, 0, 0]), at, axis) > 0.01:
            errs.append("the axis is not the line of 3937's knuckle cylinders")
    if mod.kind == "SPIN":
        lo, hi = lib.part(anchor[0]).bbox_min, lib.part(anchor[0]).bbox_max
        centre = anchor[2] @ ((lo + hi) / 2) + anchor[1]
        if _line_off(centre, anchor[2] @ np.array([0, 1.0, 0]), at, axis) > 0.01:
            errs.append("the axis is not the vertical line through the base's centre")
    return errs


@pytest.mark.parametrize("name", module_names())
def test_module_seat_agrees_with_the_library(name):
    from bricksnap.lab.modules import MODULES

    assert seat_errors(MODULES[name]) == []


def _moved(name, **changes):
    import dataclasses

    from bricksnap.lab.modules import MODULES

    mod = MODULES[name]
    parts = list(mod.parts)
    for i, kw in changes.pop("parts", {}).items():
        parts[i] = dataclasses.replace(parts[i], **kw)
    return dataclasses.replace(mod, parts=tuple(parts), **changes)


@pytest.mark.parametrize(
    ("name", "changes"),
    [
        (
            "wheels-large",
            {
                "parts": {
                    1: {"pos": (-36, 5, 0)},
                    2: {"pos": (-42, 5, 0)},
                    3: {"pos": (36, 5, 0)},
                    4: {"pos": (42, 5, 0)},
                }
            },
        ),
        ("wheels-large", {"parts": {1: {"pos": (-27, 5, 0)}, 3: {"pos": (27, 5, 0)}}}),
        ("wheels-large", {"parts": {2: {"pos": (-30, 5, 0)}, 4: {"pos": (30, 5, 0)}}}),
        ("wheels-large", {"at": (0, 8, 0)}),
        ("wheels-small", {"parts": {1: {"pos": (-30, 5, 3)}}}),
        ("door-hinge-left", {"at": (6, 0, 6)}),
        ("lid-hinge", {"at": (0, 4, 0)}),
        ("turntable-small", {"at": (5, 0, 0)}),
        ("turntable-large", {"at": (10, 0, 0)}),
        ("turntable-small", {"parts": {1: {"pos": (0, -4, 0)}}}),
    ],
)
def test_a_module_with_wrong_numbers_fails_its_seat(name, changes):
    assert seat_errors(_moved(name, **changes)), changes


def test_a_module_said_to_open_the_wrong_way_fails_its_sweep():
    """The sweep proves the direction and the range: the door hinge cannot open toward its own
    base, the lid hinge tips only one way, and the lid hinge stops before 120 degrees."""
    import dataclasses

    from bricksnap.lab import modules

    for name, changes in (
        ("door-hinge-left", {"low": -90, "high": 0}),
        ("lid-hinge", {"axis": (1, 0, 0)}),
        ("lid-hinge", {"high": 120}),
    ):
        orig = modules.MODULES[name]
        modules.MODULES[name] = dataclasses.replace(orig, **changes)
        try:
            assert check(modules.module_text(name)).moving_ok == 0, (name, changes)
        finally:
            modules.MODULES[name] = orig


def test_the_fit_radius_is_what_lets_a_hinge_turn():
    """The two halves of the library's hinges go into one another round the pin; without the
    fit radius the check would call every hinge stuck."""
    import dataclasses

    from bricksnap.lab import modules

    for name in ("lid-hinge", "door-hinge-left"):
        orig = modules.MODULES[name]
        modules.MODULES[name] = dataclasses.replace(orig, fit_radius=0.0)
        try:
            assert check(modules.module_text(name)).moving_ok == 0
        finally:
            modules.MODULES[name] = orig


def test_module_cards_are_measured():
    from bricksnap.lab.modules import MODULES, card, measure, size_words

    m = measure(MODULES["wheels-small"])
    assert (m["x"], m["z"], m["tyre"], m["top"]) == (3.8, 2.0, 36.0, 23.0)
    m = measure(MODULES["wheels-large"])
    assert (m["x"], m["tyre"], m["top"]) == (5.0, 50.0, 30.0)
    assert measure(MODULES["wheel-large-single"])["x"] == 3.5
    for mod in MODULES.values():
        assert size_words(mod) in card(mod)
        assert "one stud through its ring" not in card(mod)


# ---- the review's cases -----------------------------------------------------------------------

HINGE = (
    "0 !BRICKSNAP JOINT door SWING 0 90 AT 0 -32 0 AXIS 0 1 0 FIXED 2 MOVING 3 "
    "MODULE door-hinge-left"
)
DOOR_BASE = [
    "1 15 -20 -8 10 1 0 0 0 1 0 0 0 1 3023b.dat",
    "1 4 0 -32 0 1 0 0 0 1 0 0 0 1 3831.dat",
    "1 14 0 -32 0 1 0 0 0 1 0 0 0 1 3830.dat",
    HINGE,
]


def _text(lines):
    return "\n".join(lines) + "\n"


def test_studs_stand_in_a_doors_way():
    free = check(_text(DOOR_BASE + ["1 2 20 -8 -20 1 0 0 0 1 0 0 0 1 3068b.dat"]))
    assert free.moving_ok == 1
    studs = check(_text(DOOR_BASE + ["1 2 20 -8 -20 1 0 0 0 1 0 0 0 1 3022.dat"]))
    assert any("opens only to" in t and "line 5 (3022.dat" in t for t in moving_problems(studs))


def test_a_stud_stands_in_a_turning_arms_way():
    base = [
        "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3031.dat",
        "1 4 -20 -16 0 1 0 0 0 1 0 0 0 1 3680.dat",
        "1 4 -20 -16 0 1 0 0 0 1 0 0 0 1 3679.dat",
        "0 !BRICKSNAP JOINT head SPIN AT -20 -16 0 AXIS 0 -1 0 FIXED 2 MOVING 3 "
        "MODULE turntable-small",
        "1 1 -20 -24 0 1 0 0 0 1 0 0 0 1 3795.dat",
    ]
    assert check(_text(base)).moving_ok == 1
    r = check(_text([*base, "1 2 30 -16 30 1 0 0 0 1 0 0 0 1 3024.dat"]))
    assert any(
        "cannot turn all the way round" in t and "line 6 (3024.dat" in t for t in moving_problems(r)
    )


@pytest.mark.parametrize(("studs", "part"), [(2, "3004.dat"), (4, "3010.dat"), (8, "3008.dat")])
def test_the_smallest_interference_seen(studs, part):
    """A door's far inner corner swings past its end by sqrt(L^2 + 20^2) - L; a jamb that far
    minus d away is d LDU in its way. 0.25 LDU is never reported, 1 LDU always."""
    length = studs * 20
    corner = float(np.hypot(length, 20) - length)
    for depth, blocked in ((0.25, False), (1.0, True)):
        if corner - depth < 0:
            continue
        lines = list(DOOR_BASE)
        for k in range(3):
            lines.append(f"1 1 {length / 2} {-56 - 24 * k} 10 1 0 0 0 1 0 0 0 1 {part}")
        for k in range(5):
            lines.append(
                f"1 2 {round(length + corner - depth + 10, 3)} {-24 * (k + 1)} 10 "
                "1 0 0 0 1 0 0 0 1 3005.dat"
            )
        got = bool([t for t in moving_problems(check(_text(lines))) if "opens only to" in t])
        assert got == blocked, (studs, depth)


def test_nothing_moving_goes_into_the_ground():
    from bricksnap.lab.modules import place_module

    got = place_module("", "lid-hinge", 4, 0, joint_name="ramp")
    lines = got.lines + [
        "1 1 0 -32 0 0 0 1 0 1 0 -1 0 0 3021.dat",
        "1 14 0 -40 90 0 0 1 0 1 0 -1 0 0 3034.dat",
    ]
    r = check(_text(lines))
    stop = [t for t in moving_problems(r) if "into the ground" in t]
    assert stop and "opens only to 10 degrees of 90" in stop[0], r.text()


def _two_lids(second_declared=True, second_turn=0, offset=0.0):
    from bricksnap.lab.modules import place_module

    text = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3032.dat\n"
    got = place_module(text, "lid-hinge", 4, 1, stud=21, joint_name="lid-a")
    text += "\n".join(got.lines) + "\n"
    got = place_module(text, "lid-hinge", 4, 1, stud=23, turn=second_turn, joint_name="lid-b")
    lines = got.lines if second_declared else got.lines[:-1]
    if offset:
        lines = [ln if not ln.startswith("1 ") else ln for ln in lines]
    text += "\n".join(lines) + "\n"
    return text


def test_two_lid_hinges_under_one_lid_act_as_one():
    text = _two_lids()
    text += "1 1 0 -40 20 1 0 0 0 1 0 0 0 1 3795.dat\n"  # a 2 x 6 plate on both tops
    r = check(text)
    assert r.moving_ok == 2 and not moving_problems(r), r.text()
    assert "2 hinges on one line acting as one" in r.movement[0]
    assert (
        r.movement[1]
        == "'lid-b': on the same line as 'lid-a' and holding the same parts: checked with it."
    )
    from bricksnap.lab.joints import opened

    assert opened(text, {"lid-a": 60, "lid-b": 60}) == opened(text, {"lid-a": 60})
    # the second pair placed by hand, with no joint line: still one hinge
    text = _two_lids(second_declared=False) + "1 1 0 -40 20 1 0 0 0 1 0 0 0 1 3795.dat\n"
    r = check(text)
    assert r.moving_ok == 1 and not moving_problems(r) and "acting as one" in r.movement[0]


def test_hinges_that_open_opposite_ways_hold_the_lid_still():
    text = _two_lids(second_turn=2) + "1 1 0 -40 20 1 0 0 0 1 0 0 0 1 3795.dat\n"
    r = check(text)
    assert any("open opposite ways" in t for t in moving_problems(r)), r.text()


def test_two_hinges_not_in_line_are_named():
    """A 1 x 4 brick on a door hinge (vertical line) and on a lid hinge (level line) at once
    cannot move; with the lid hinge placed by hand or declared, the report says why."""
    lines = list(DOOR_BASE) + [
        "1 1 40 -56 10 1 0 0 0 1 0 0 0 1 3010.dat",
        "1 15 60 -8 10 1 0 0 0 1 0 0 0 1 3023b.dat",
        "1 4 60 -32 10 1 0 0 0 1 0 0 0 1 3937.dat",
        "1 4 60 -32 10 1 0 0 0 1 0 0 0 1 3938.dat",
    ]
    lid = (
        "0 !BRICKSNAP JOINT lid SWING 0 90 AT 60 -22 10 AXIS 1 0 0 FIXED 7 MOVING 8 "
        "MODULE lid-hinge"
    )
    for extra in ([], [lid]):
        r = check(_text(lines + extra))
        assert r.moving_ok == 0
        assert any(
            "the hinge on lines 7, 8 holds the same parts, and these two hinges do not turn about "
            "the same line" in t
            for t in moving_problems(r)
        ), r.text()


def test_a_door_on_two_hinge_bricks_on_one_line():
    lines = [
        "1 15 -20 -8 10 1 0 0 0 1 0 0 0 1 3023b.dat",
        "1 4 0 -32 0 1 0 0 0 1 0 0 0 1 3831.dat",
        "1 14 0 -32 0 1 0 0 0 1 0 0 0 1 3830.dat",
        "0 !BRICKSNAP JOINT door-low SWING 0 90 AT 0 -32 0 AXIS 0 1 0 FIXED 2 MOVING 3 "
        "MODULE door-hinge-left",
        "1 4 -20 -56 10 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 4 -20 -80 10 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 1 20 -56 10 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 1 20 -80 10 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 4 0 -104 0 1 0 0 0 1 0 0 0 1 3831.dat",
        "1 14 0 -104 0 1 0 0 0 1 0 0 0 1 3830.dat",
        "0 !BRICKSNAP JOINT door-high SWING 0 90 AT 0 -104 0 AXIS 0 1 0 FIXED 9 MOVING 10 "
        "MODULE door-hinge-left",
    ]
    r = check(_text(lines))
    assert r.moving_ok == 2 and not moving_problems(r), r.text()
    from bricksnap.lab.joints import opened

    a = opened(_text(lines), {"door-low": 60, "door-high": 60})
    assert a == opened(_text(lines), {"door-low": 60})
    top = [float(v) for v in a.splitlines()[9].split()[2:5]]
    assert np.allclose(top, [0, -104, 0])  # turned in place about its own line, once


def test_lid_hinge_faces_the_same_way_on_a_stud_and_on_the_ground():
    from bricksnap.lab.modules import place_module

    plate = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3958.dat\n"
    for turn in range(4):
        a = place_module("", "lid-hinge", 4, 0, turn=turn)
        b = place_module(plate, "lid-hinge", 4, 1, stud=15, turn=turn)
        assert np.allclose(a.joint.axis, b.joint.axis), turn
    got = place_module(plate, "lid-hinge", 4, 1, stud=15)
    assert "Build the panel toward -z (to the front)" in got.note
    assert "opening moves it up" in got.note
    door = place_module(plate, "door-hinge-left", 4, 1, stud=15)
    assert "Build the panel toward +x (to the right)" in door.note
    assert "opening moves it toward -z (to the front)" in door.note
    door = place_module(plate, "door-hinge-left", 4, 1, stud=15, turn=1)
    assert "Build the panel toward -z (to the front)" in door.note
    assert "opening moves it toward -x (to the left)" in door.note


def test_a_wheel_on_its_side_and_a_spare():
    import numpy as np

    from bricksnap.lab import modules
    from bricksnap.lab.joints import joint_line
    from bricksnap.lab.place import ldraw_line

    def placed(name, R, P, jname, first=1):
        mod = modules.MODULES[name]
        out = []
        for p in mod.parts:
            out.append(
                ldraw_line(
                    0 if p.role == "tyre" else 4,
                    R @ np.array(p.pos, float) + P,
                    R @ np.array(p.m, float).reshape(3, 3),
                    p.file,
                )
            )
        j = mod.joint(jname)
        j.at, j.axis = R @ j.at + P, R @ j.axis
        j.fixed = [first + n - 1 for n in j.fixed]
        j.moving = [first + n - 1 for n in j.moving]
        return [*out, joint_line(j)]

    flat = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1.0]])
    r = check(_text(placed("wheel-large-single", flat, np.array([0, -50.0, 0]), "foot")))
    assert any("lies on its side" in t for t in moving_problems(r))
    # a spare on the back of a chassis that rests on its own wheels
    car = modules.place_module("", "wheels-small", 4, 0, z=-40, joint_name="front")
    text = "\n".join(car.lines) + "\n"
    car = modules.place_module(text, "wheels-small", 4, 0, z=40, joint_name="rear")
    text += "\n".join(car.lines) + "\n1 4 0 -31 0 0 0 1 0 1 0 -1 0 0 3034.dat\n"
    n = len(text.splitlines())
    text += _text(
        placed("wheel-large-single", np.eye(3), np.array([0, -80.0, 100]), "spare", n + 1)
    )
    r = check(text)
    spare = next(m for m in r.movement if m.startswith("'spare'"))
    assert "a spare" in spare and not any("spare" in t for t in moving_problems(r)), r.text()


def test_mirror_refuses_a_modules_parts(work):
    from bricksnap.lab import tools

    call(work, "add", {"ldraw": "1 72 0 -38 0 1 0 0 0 1 0 0 0 1 3795.dat"})
    call(
        work,
        "place_module",
        {
            "module": "wheel-large-single",
            "colour": 4,
            "line": 1,
            "under_socket": 6,
            "name": "right",
        },
    )
    t = texts(tools.call_tool(work, "mirror", {"lines": [2, 3, 4]}))
    assert t.startswith("ERROR:") and "part of the joint 'right'" in t and "place_module" in t
    call(
        work,
        "place_module",
        {"module": "door-hinge-left", "colour": 4, "line": 1, "stud": 1, "name": "d"},
    )
    t = texts(tools.call_tool(work, "mirror", {"lines": [7]}))
    assert "door-hinge-right" in t


def test_a_tyre_left_without_its_joint_is_named(work):
    build_chassis(work)
    call(work, "remove", {"lines": [12]})  # the rear axle's joint line
    r = checked(work)
    named = [
        t
        for t in moving_problems(r)
        if "belong to no wheel joint" in t or "belongs to no wheel joint" in t
    ]
    assert named and not any("Raise" in t and "Tyre" in t for t in moving_problems(r)), r.text()


def test_place_module_refuses_bad_numbers_and_appends_nothing(work):
    from bricksnap.lab import tools
    from bricksnap.lab.tools import _model

    for args in (
        {"module": "lid-hinge", "colour": 4, "line": 0, "x": 1e308},
        {"module": "lid-hinge", "colour": 4, "line": 0, "x": float("nan")},
        {"module": "lid-hinge", "colour": 4, "line": 0, "z": float("inf")},
        {"module": "lid-hinge", "colour": 4, "line": 0, "turn": 1.5},
        {"module": "lid-hinge", "colour": 4, "line": 1, "stud": 1.9},
    ):
        t = texts(tools.call_tool(work, "place_module", args))
        assert t.startswith("ERROR:") and "failed inside" not in t, (args, t)
    assert _model(work) == ""
    t = texts(
        tools.call_tool(work, "place", {"part": "3001.dat", "colour": 4, "line": 0, "turn": 2.5})
    )
    assert t.startswith("ERROR:") and "whole number" in t


def test_the_modules_list_says_how_each_attaches_and_what_moves(work):
    t = call(work, "modules", {})
    assert t.count("Attaches:") == 8 and t.count("Moves:") == 8
    assert "must not stand on studs" in t


def test_open_all_opens_each_only_as_far_as_it_goes(work, monkeypatch):
    from bricksnap.lab import tools
    from bricksnap.lab.movement import open_angles

    build_box(work)
    call(
        work, "place", {"part": "3004.dat", "colour": 1, "line": 1, "stud": stud(work, 1, -10, 50)}
    )
    for n in (13, 14):
        call(work, "place", {"part": "3004.dat", "colour": 1, "line": n, "stud": 1})
    angles = open_angles(tools._model(work))
    assert 0 < angles["lid"] < 30
    # a tied joint stays shut
    from bricksnap.lab.modules import module_text

    tied = module_text("door-hinge-left").replace(
        "\n0 !BRICKSNAP", "\n1 4 0 -32 10 1 0 0 0 1 0 0 0 1 3710.dat\n0 !BRICKSNAP"
    )
    assert check(tied).movement[0].endswith("tied shut (see problems).")
    assert open_angles(tied) == {}


def test_the_movement_check_runs_after_place_only_near_a_joint(work, monkeypatch):
    from bricksnap.lab import movement

    calls = []
    real = movement.apply
    monkeypatch.setattr(movement, "apply", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    build_chassis(work)
    calls.clear()
    call(work, "place", {"part": "3001.dat", "colour": 1, "line": 0, "x": 400, "z": 400})
    assert calls == []  # far from every joint
    call(work, "place", {"part": "3023b.dat", "colour": 1, "line": 13, "stud": 1})
    assert calls  # on the chassis, among the wheels


# ---- what the contracts promise ---------------------------------------------------------------


def test_negative_ranges_and_a_joint_declared_on_a_hinge_pin(work):
    """A hinge brick's two halves placed by hand and declared about the pin's own line: the
    positive way is free, the negative way runs the top into its base."""
    call(work, "add", {"ldraw": _text(DOOR_BASE[:3])})
    t = call(
        work,
        "joint",
        {
            "name": "flap",
            "kind": "swing",
            "fixed": [2],
            "moving": [3],
            "at": [0, -32, 0],
            "axis": [0, 1, 0],
            "min": -90,
            "max": 90,
        },
    )
    assert "swings only from" in t and "to 90 degrees of -90 to 90" in t


def test_chained_joints_are_turned_by_both():
    from bricksnap.lab.joints import opened
    from bricksnap.lab.modules import place_module

    text = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3032.dat\n"
    got = place_module(text, "lid-hinge", 4, 1, stud=14, joint_name="lid")
    text += "\n".join(got.lines) + "\n1 1 0 -40 0 1 0 0 0 1 0 0 0 1 3031.dat\n"
    text += "1 15 -20 -48 -10 1 0 0 0 1 0 0 0 1 3023b.dat\n"
    got = place_module(text, "door-hinge-left", 2, 6, stud=1, joint_name="flap")
    text += "\n".join(got.lines) + "\n"
    both = opened(text, {"lid": 30, "flap": 45})
    assert both == opened(text, {"flap": 45, "lid": 30})
    rows = both.splitlines()
    base, top = rows[6].split(), rows[7].split()
    assert np.allclose([float(v) for v in base[2:5]], [float(v) for v in top[2:5]])
    assert rows[6] != text.splitlines()[6]  # the flap's base rode on the lid
    from bricksnap.lab.joints import all_open

    assert all_open(text) == {"lid": 90.0, "flap": 90.0}


def test_what_overlaps_at_rest_is_not_counted_again():
    """A tile already reaching 1 LDU into the door half at rest (a known overlap, reported as
    such) does not stop the door, which moves away from it."""
    r = check(_text(DOOR_BASE + ["1 2 20 -33 10 1 0 0 0 1 0 0 0 1 3070b.dat"]))
    assert not [t for t in moving_problems(r) if "opens only" in t], r.text()


def test_a_face_that_only_touches_a_wheels_end_is_not_in_the_way():
    from bricksnap.lab.modules import place_module

    got = place_module("", "wheels-small", 4, 0, joint_name="w")
    # a 1 x 1 brick standing right against the outer face of the +x tyre (x 38 .. 58)
    r = check("\n".join(got.lines) + "\n1 1 48 -24 0 1 0 0 0 1 0 0 0 1 3005.dat\n")
    assert not [t for t in moving_problems(r) if "rub" in t], r.text()
    r = check("\n".join(got.lines) + "\n1 1 46 -24 0 1 0 0 0 1 0 0 0 1 3005.dat\n")
    assert [t for t in moving_problems(r) if "rub" in t]


def test_check_refuses_a_hand_written_joint_line():
    text = _text(
        DOOR_BASE[:3]
        + ["0 !BRICKSNAP JOINT flap SWING 0 90 AT 40 -32 20 AXIS 1 0 0 FIXED 2 MOVING 3"]
    )
    r = check(text)
    assert any(
        "is not accepted: the line given is not the joint's own" in t for t in moving_problems(r)
    )
    assert r.movement == [
        "'flap' (declared by the builder, lines 2, 3): not checked (see problems)."
    ]


def test_check_without_movement_and_verify_on_another_axis():
    from bricksnap.lab.validate import check as run

    text = _text(DOOR_BASE)
    assert run(text, movement=False).movement == []
    other = text.replace("AXIS 0 1 0", "AXIS 1 0 0")
    assert any(
        "its AT and AXIS are not the module's axis" in t for t in moving_problems(check(other))
    )


# ---- the second review ----------------------------------------------------------------------

YZ = "1 0 0 0 0 -1 0 1 0"  # a bar's length (its y) along z
PIN_Z = "0 0 -1 0 1 0 1 0 0"  # a Technic pin's length (its x) along z
QZ = "0 0 1 0 1 0 -1 0 0"


def _declare(text, f, m, at, axis, kind="SPIN", low=0.0, high=0.0):
    from bricksnap.lab.joints import Joint
    from bricksnap.lab.movement import confirm
    from bricksnap.lab.validate import check as run

    a = np.array(axis, dtype=float)
    j = Joint("j", kind, np.array(at, dtype=float), a / np.linalg.norm(a), [f], [m], low, high)
    return confirm(j, run(text, movement=False), ldraw_lib.library())


@pytest.mark.parametrize(
    ("text", "at", "axis"),
    [
        # a Bar 4L in the bore of 12825's clip (along z, 6 LDU above the tile), both lines tried
        (
            "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 12825.dat\n1 0 0 -14 -40 " + YZ + " 30374.dat\n",
            [0, -14, 0],
            [0, 0, 1],
        ),
        (
            "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 12825.dat\n1 0 0 -14 -40 " + YZ + " 30374.dat\n",
            [0, -14, 0],
            [0, 1, 0],
        ),
        # a vertical bar in 4085c's clip
        (
            "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 4085c.dat\n1 0 0 -60 -17 1 0 0 0 1 0 0 0 1 30374.dat\n",
            [0, -20, -17],
            [0, 1, 0],
        ),
        # the ordinary plate hinge: 2540's handle in 11476's clip
        (
            "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 11476.dat\n"
            "1 4 0 -10.5 -40 -1 0 0 0 1 0 0 0 -1 2540.dat\n",
            [0, -8, -20],
            [1, 0, 0],
        ),
    ],
)
def test_a_clip_joint_cannot_be_declared_yet(text, at, axis):
    report = check(text)
    assert any(i.kind == "joint" and set(i.lines) == {1, 2} for i in report.unchecked)
    why = _declare(text, 1, 2, at, axis)
    assert why == "the checker cannot yet confirm how a clip turns: use a module instead"


def test_a_technic_pin_joint_is_confirmed_about_its_own_line():
    text = f"1 7 0 -24 0 1 0 0 0 1 0 0 0 1 3700.dat\n1 0 0 -14 -10 {PIN_Z} 3673.dat\n"
    assert _declare(text, 1, 2, [0, -14, 0], [0, 0, 1]) is None
    assert "not the joint's own" in _declare(text, 1, 2, [0, -4, 0], [0, 0, 1])
    assert "not the joint's own" in _declare(text, 1, 2, [0, -14, 0], [1, 0, 0])
    r = check(text + "0 !BRICKSNAP JOINT p SPIN AT 0 -14 0 AXIS 0 0 1 FIXED 1 MOVING 2\n")
    assert r.movement == [
        "'p' (declared by the builder, lines 1, 2): turns freely all the way round with nothing "
        "in the way."
    ]


def _lorry(fifth):
    from bricksnap.lab.modules import place_module

    t = ""
    for z, n in ((-100, "front"), (-20, "drive")):
        g = place_module(t, "wheels-small", 4, 0, z=z, joint_name=n)
        t += "\n".join(g.lines) + "\n"
    t += f"1 72 0 -31 -60 {QZ} 3795.dat\n"  # the tractor's chassis
    n = len(t.splitlines())
    t += (
        "1 71 0 -39 -20 1 0 0 0 1 0 0 0 1 3680.dat\n1 71 0 -39 -20 1 0 0 0 1 0 0 0 1 3679.dat\n"
        f"0 !BRICKSNAP JOINT fifth {fifth} AT 0 -39 -20 AXIS 0 -1 0 FIXED {n + 1} MOVING {n + 2} "
        "MODULE turntable-small\n"
    )
    t += f"1 1 0 -47 40 {QZ} 3034.dat\n"  # the trailer's bed, on the turntable
    g = place_module(t, "wheels-small", 4, 0, z=100, joint_name="trailer")
    t += "\n".join(g.lines) + "\n"
    t += "1 72 0 -31 100 1 0 0 0 1 0 0 0 1 3022.dat\n1 72 0 -39 100 1 0 0 0 1 0 0 0 1 3022.dat\n"
    return t


def test_an_articulated_lorry_turns_with_its_trailer_on_the_ground():
    r = check(_lorry("SWING -40 40"))
    assert r.ok and r.moving_ok == 4, r.text()
    fifth = next(m for m in r.movement if m.startswith("'fifth'"))
    assert fifth.startswith(
        "'fifth' (turntable-small, lines 14, 15): swings from -40 to 40 degrees"
    )
    # all the way round, the trailer would meet the tractor: true, and said
    r = check(_lorry("SPIN"))
    assert any("cannot turn all the way round" in t for t in moving_problems(r))
    assert not any("holds what moves to what stays" in t for t in moving_problems(r))


def test_a_gate_with_a_foot_on_the_ground_swings():
    lines = DOOR_BASE[:3] + [
        "0 !BRICKSNAP JOINT gate SWING 0 90 AT 0 -32 0 AXIS 0 1 0 FIXED 2 MOVING 3 "
        "MODULE door-hinge-left",
        "1 1 40 -56 10 1 0 0 0 1 0 0 0 1 3010.dat",
        "1 1 60 -32 10 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 1 60 -8 10 1 0 0 0 1 0 0 0 1 3023b.dat",  # the foot, on the ground
    ]
    r = check(_text(lines))
    assert r.movement == [
        "'gate' (door-hinge-left, lines 2, 3): swings from 0 to 90 degrees with nothing in the "
        "way; 4 parts move with it (lines 3, 5 to 7)."
    ], r.text()


def test_a_flap_with_a_leg_opens_up_and_the_ground_stops_it_going_down():
    from bricksnap.lab.modules import place_module

    t = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3032.dat\n"
    g = place_module(t, "lid-hinge", 4, 1, stud=14, joint_name="flap")
    t += "\n".join(g.lines) + "\n"
    t += f"1 1 -40 -40 -40 {QZ} 3795.dat\n"
    t += "1 1 -40 -32 -80 1 0 0 0 1 0 0 0 1 3003.dat\n1 1 -40 -8 -80 1 0 0 0 1 0 0 0 1 3022.dat\n"
    r = check(t)
    assert r.moving_ok == 1 and "swings from 0 to 90 degrees" in r.movement[0], r.text()
    # an arm on a Technic pin with a leg at its far end: up is free, down meets the ground
    arm = [
        "1 7 0 -24 0 1 0 0 0 1 0 0 0 1 3004.dat",
        "1 7 0 -48 0 1 0 0 0 1 0 0 0 1 3700.dat",
        f"1 0 0 -38 -10 {PIN_Z} 3673.dat",
        "1 4 20 -48 -20 1 0 0 0 1 0 0 0 1 3701.dat",
        "1 4 40 -24 -20 1 0 0 0 1 0 0 0 1 3004.dat",
        "0 !BRICKSNAP JOINT arm SWING -90 90 AT 0 -38 0 AXIS 0 0 1 FIXED 3 MOVING 4",
    ]
    r = check(_text(arm))
    assert r.movement == [
        "'arm' (declared by the builder, lines 3, 4): swings only from -90 to 0 degrees of -90 "
        "to 90 (see problems)."
    ], r.text()
    assert any(
        "toward 90 degrees: by 1 degree it would go into the ground" in t
        for t in moving_problems(r)
    )


def test_a_spin_sees_the_ground():
    base = f"1 7 0 -24 0 1 0 0 0 1 0 0 0 1 3700.dat\n1 0 0 -14 -10 {PIN_Z} 3673.dat\n"
    pole = base + "1 4 0 -24 -20 1 0 0 0 1 0 0 0 1 3701.dat\n"
    r = check(pole + "0 !BRICKSNAP JOINT arm SPIN AT 0 -14 0 AXIS 0 0 1 FIXED 2 MOVING 3\n")
    assert any(
        "cannot turn all the way round: line 3 (3701.dat Technic Brick 1 x 4 with Holes" in t
        and "LDU into the ground (y = 0) as it turns" in t
        for t in moving_problems(r)
    ), r.text()


def test_one_axle_with_a_stand_is_a_note_two_axles_a_problem():
    from bricksnap.lab.modules import place_module

    g = place_module("", "wheels-small", 4, 0, z=0, joint_name="axle")
    bed = "\n".join(g.lines) + "\n1 1 0 -31 0 0 0 1 0 1 0 -1 0 0 3034.dat\n"
    r = check(bed + "1 15 0 -23 -70 1 0 0 0 1 0 0 0 1 3004.dat\n")
    assert not moving_problems(r)
    assert any(
        i.text.startswith("All its road wheels are on one axle line, so it also stands on line 8")
        for i in r.warnings
    )


def test_two_parallel_hinges_on_different_lines_do_not_act_as_one():
    from bricksnap.lab.modules import place_module

    t = "1 72 0 -8 0 1 0 0 0 1 0 0 0 1 3032.dat\n"
    g = place_module(t, "lid-hinge", 4, 1, stud=21, joint_name="lid-a")
    t += "\n".join(g.lines) + "\n"
    g = place_module(t, "lid-hinge", 4, 1, stud=17, joint_name="lid-b")  # 20 LDU in front
    t += "\n".join(g.lines) + "\n1 1 0 -40 20 1 0 0 0 1 0 0 0 1 3795.dat\n"
    r = check(t)
    assert r.moving_ok == 0 and not any("acting as one" in m for m in r.movement)
    assert any("do not turn about the same line" in x for x in moving_problems(r))


def test_the_fit_radius_for_a_declared_joint_is_only_round_the_pin():
    """Declared by the builder, a hinge brick's halves turned the wrong way run into each other
    beyond the pin: that must still be seen (the fit radius is not a licence)."""
    text = (
        "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3831.dat\n1 14 0 -24 0 1 0 0 0 1 0 0 0 1 3830.dat\n"
        "0 !BRICKSNAP JOINT flap SWING -90 90 AT 0 -24 0 AXIS 0 1 0 FIXED 1 MOVING 2\n"
    )
    r = check(text)
    assert r.reach["flap"] is not None and r.reach["flap"][0] > -90, r.text()
    assert r.reach["flap"][1] == 90


def test_the_coarse_pass_looks_against_the_grown_solid():
    """A point moving 4 LDU per coarse step must still meet a slab 2 LDU thick that lies
    between two coarse steps."""
    import math

    from bricksnap.lab import movement as M
    from bricksnap.lab import solid as S

    lib = ldraw_lib.library()
    p = check("1 4 0 0 0 1 0 0 0 1 0 0 0 1 3001.dat\n").placed[0]
    at, axis = np.zeros(3), np.array([0, 1.0, 0])
    sw = M._Swing(at, axis, [], [], set(), set(), 10.0)
    u, e1, e2 = sw.basis
    r = 40.0
    dt = M.ARC / r
    th = (M.COARSE * 3 + M.COARSE / 2) * dt
    c = r * (math.cos(th) * e1 + math.sin(th) * e2)
    tang = -math.sin(th) * e1 + math.cos(th) * e2
    rad = c / np.linalg.norm(c)
    q = np.array(
        [
            c + sx * tang + sy * 5 * rad + sz * 5 * u
            for sx in (-1, 1)
            for sy in (-1, 1)
            for sz in (-1, 1)
        ]
    )
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = np.array([[q[f[0]], q[f[i]], q[f[i + 1]]] for f in faces for i in (1, 2)])
    target = M._Body(p, lib)
    target.solid = S.build_solid(tris)
    pts = M._Polar(np.array([0.0]), np.array([r]), np.array([0.0]))
    rings = M._Rings(M._polar(S.sample_triangles(tris), at, sw.basis))
    k = sw._first(pts, target, rings, dt, 200, 1, False)
    assert k < 200 and abs((k + 1) * dt - th) * r < 2


def test_a_damaged_solid_cache_entry_is_built_again(tmp_path, monkeypatch):
    import pickle

    from bricksnap.lab import solid as S

    monkeypatch.setenv("BRICKSNAP_LAB_CACHE", str(tmp_path))
    lib = ldraw_lib.library()
    for bad in ({"shape": None}, {"h": 0.0}, {"lo": [float("nan")] * 3}, {"full": b""}):
        S._SOLIDS.clear()
        path = S._cache_file("3005.dat", lib)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "stamp": lib.stamp,
            "lo": np.zeros(3),
            "h": 0.5,
            "shape": (4, 4, 4),
            "full": np.packbits(np.ones(64, bool)),
            "deep": np.packbits(np.ones(64, bool)),
        }
        entry.update(bad)
        path.write_bytes(pickle.dumps(entry))
        got = S.solid("3005.dat", lib)
        assert got.full.size > 64 and got.h == S.CELL, bad
    S._SOLIDS.clear()
