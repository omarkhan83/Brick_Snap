"""Tests for the set designers' guide given to the AI builder (bricksnap/lab/guide.py), and
for the switch that turns it on (``run.build(..., guide=True)``).

No test starts a real AI session: ``runner.run_session`` is replaced by a stand-in that
records what the builder would have been given.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from bricksnap.lab import art, guide, ldraw_lib, run, tools

ROOT = Path(__file__).resolve().parent.parent
STUDY_GUIDE = ROOT / "docs" / "research" / "2026-11-19-how-real-sets-are-built" / "guide.md"

# What the builder is given with the guide off, as it was before the switch existed: the
# baseline of the with-and-without comparison. If you change prompt.md or a tool on purpose,
# update these, knowing that guide-off runs before and after the change are no longer alike.
BASELINE_PROMPT_SHA256 = "151ea0bcd48aa3736678a1eae387fe4e40112c5c8e8cc0c49d5ff4290720b53e"
BASELINE_TOOLS_SHA256 = "2d3fc284e8048eddf66d45aac47390758487adaa707209360cb0d98053a3f990"
# On 20 November the colour line was changed on purpose (the style study: a fuller list, true
# names, trans black for glass). Before it, the prompt's pin was this, with this colour line:
# putting the old line back must give the old pin, so the change is that one line and no other.
# (Since then the check tool's sentence on joints changed twice more, for clips on bars, the
# second time to say a clip on a bar is a proper joint for a thin part: this pin is the old
# colour line with today's sentence.)
PROMPT_SHA256_BEFORE_COLOURS = "73eb0d82041a024c123029e0a60bff0b5df4ad139b897f2e86cbe6437349d681"
OLD_COLOUR_LINE = (
    "- Colours are LDraw codes: 0 black, 1 blue, 2 green, 4 red, 14 yellow, 15 white, 19 tan, "
    "25 orange, 27 lime, 28 dark tan, 70 reddish brown, 71 light bluish grey, 72 dark bluish "
    "grey, 5 dark pink, 13 pink, 22 purple, 10 bright green, 288 dark green, 320 dark red, 272 "
    "dark blue, 47 transparent clear, 40 transparent brown (smoke), 36 transparent red, 46 "
    "transparent yellow. Never use 16 or 24."
)

needs_library = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tools_sha(listed: list[dict[str, Any]]) -> str:
    return _sha(json.dumps(listed, sort_keys=True).encode())


def _folder(tmp_path: Path, **config: Any) -> Path:
    f = tmp_path / "work"
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 5, **config}))
    return f


def _text(blocks: list[dict[str, Any]]) -> str:
    assert len(blocks) == 1 and blocks[0]["type"] == "text"
    return blocks[0]["text"]


# ---- the guide and its reader ---------------------------------------------------------------


def test_the_two_copies_agree():
    """The study's guide.md is the record of what was tested; the package's is what the
    builder reads. They are the same text: change both together."""
    assert guide.GUIDE_FILE.read_bytes() == STUDY_GUIDE.read_bytes()


@pytest.mark.parametrize(
    "heading",
    [guide.RULES_HEADING, guide.PLAYBOOKS_HEADING, guide.TABLE_HEADING],
)
def test_the_headings_the_reader_needs_are_there(heading):
    assert ("\n" + heading + "\n") in guide.text()


def test_a_missing_heading_is_an_error(monkeypatch):
    real = guide.text()
    monkeypatch.setattr(guide, "text", lambda: real.replace(guide.TABLE_HEADING, "## Parts"))
    guide._playbooks.cache_clear()
    try:
        with pytest.raises(ValueError, match="Parts by job"):
            guide.parts_table()
        with pytest.raises(ValueError, match="Parts by job"):
            guide._playbooks()
    finally:
        guide._playbooks.cache_clear()


def test_the_rules():
    with_sources = guide.rules(evidence=True).splitlines()
    plain = guide.rules().splitlines()
    assert len(plain) == len(with_sources) == 12
    assert [r.split(".")[0] for r in plain] == [str(n) for n in range(1, 13)]
    assert plain[0].startswith("1. **Build the core first**")
    assert "[10 of 10]" in with_sources[0] and "[" not in "".join(plain)
    assert "86% of the way through" in plain[1]  # the figures in the sentences stay
    assert all("\n" not in r and "  " not in r for r in plain)


def test_the_words_and_the_table():
    assert guide.words().startswith("# How set designers build")
    assert "*panel*" in guide.words()
    table = guide.parts_table()
    assert "| Core that takes panels |" in table and "87087" in table
    assert "**Sizes that fit.**" in table


def test_twelve_playbooks_six_kinds():
    assert list(guide.kinds()) == ["vehicle", "aircraft", "hollow", "creature", "plant", "machine"]
    assert set(guide.KIND_LINES) == set(guide.kinds())
    assert all(guide.kinds().values())
    for kind in guide.kinds():
        assert guide.sizes(kind) == [100, 400]


@pytest.mark.parametrize("kind", ["vehicle", "aircraft", "hollow", "creature", "plant", "machine"])
@pytest.mark.parametrize(
    ("parts", "size"), [(20, 100), (100, 100), (200, 100), (250, 400), (400, 400), (2000, 400)]
)
def test_the_nearest_playbook(kind, parts, size):
    title, body, why = guide.playbook(kind, parts)
    assert title.endswith(f", {size} parts")
    assert body.startswith("[") and "- " in body and "###" not in body
    assert f"{parts:,}" in why or why == f"It is the {kind} playbook for {size} parts."


def test_kinds_from_words():
    assert guide.kind_of("a red fire truck") == "vehicle"
    assert guide.kind_of("a Cessna 172") == "aircraft" and guide.kind_of("planes") == "aircraft"
    assert guide.refine("vehicle", "a Cessna 172 Skyhawk") == "aircraft"
    assert guide.refine("vehicle", "a fire truck") == "vehicle"
    assert guide.refine("creature", "a plane") == "creature"
    assert guide.kind_of("House") == "hollow"
    assert guide.kind_of("cats") == "creature"
    assert guide.kind_of("flowers") == "plant"
    assert guide.kind_of("technic") == "machine"
    assert guide.kind_of("zzz") is None


# ---- the guide-mode instructions ----------------------------------------------------------


def test_the_guide_mode_instructions():
    base = run.PROMPT_FILE.read_text(encoding="utf-8")
    text = guide.system_prompt(base)
    assert guide.rules() in text and "# Panels" in text
    assert "Build from the ground up" not in text and "a sturdy core" not in text
    assert "call playbook once" in text and "which playbook you followed" in text
    assert "Write the art direction and give it with brief" in text
    assert "not of a ball joint, a hinge or a clip it cannot measure" in text
    assert "lifts off" in text and "hinged doors" in text
    # one method: the rules and Panels come after the working order, before what moves
    assert text.index("7. Stop when") < text.index("# How set designers build")
    assert text.index("# Panels") < text.index("# When the subject moves")
    # everything about coordinates is as it was; the tools as they were but for how to
    # spend turns (place, add) and what submit and brief do
    part = base[base.index("# The coordinates (LDraw)") : base.index("- place attaches")]
    assert part in text
    # a first build has neither the start-from-a-model nor the change section
    assert "# When you start from a model" not in text
    assert "# When you are asked for a change" not in text
    start = guide.system_prompt(base, "start")
    change = guide.system_prompt(base, "change")
    assert "# When you start from a model" in start and "# When you are asked" not in start
    assert "# When you are asked for a change" in change and "# When you start" not in change


def test_a_changed_prompt_cannot_slip_past(monkeypatch):
    base = run.PROMPT_FILE.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="exactly once"):
        guide.system_prompt(base.replace("Build from the ground up.", "Build upwards."))


# ---- the switch ---------------------------------------------------------------------------


def _colour_line(text: str) -> str:
    lines = [ln for ln in text.splitlines() if ln.startswith("- Colours are LDraw codes")]
    assert len(lines) == 1
    return lines[0]


def test_the_colour_line_is_the_only_change_to_the_pinned_prompt():
    text = run.PROMPT_FILE.read_text(encoding="utf-8")
    assert _sha(text.encode()) == BASELINE_PROMPT_SHA256
    before = text.replace(_colour_line(text), OLD_COLOUR_LINE)
    assert _sha(before.encode()) == PROMPT_SHA256_BEFORE_COLOURS


@needs_library
def test_every_colour_the_builder_is_told_is_in_the_library_by_that_name():
    import re

    line = _colour_line(run.PROMPT_FILE.read_text(encoding="utf-8"))
    body = line.split("Never use")[0]
    pairs = re.findall(r"\b(\d+) ([a-z][a-z ]*?)(?= \(|,|\.)", body)
    names = ldraw_lib.library().colours()
    assert len(pairs) == 38
    for code, name in pairs:
        assert names.get(int(code), "").lower() == name, (code, name, names.get(int(code)))
    for code in (272, 320, 288, 379, 378, 321, 322, 484, 191, 84, 28, 330, 308, 70, 19, 315, 297):
        assert str(code) in {c for c, _ in pairs}
    assert "10375 trans black (the neutral smoke for glass)" in line
    assert "smoke" not in line.split("10375")[0] and "(smoke)" not in line


def test_with_the_guide_off_the_tools_are_todays(tmp_path):
    assert _tools_sha(tools.TOOLS) == BASELINE_TOOLS_SHA256
    off = _folder(tmp_path, guide=False)
    assert tools.tools_for(off) == tools.TOOLS
    old = tmp_path / "old"  # a folder from before the switch: no "guide" at all
    old.mkdir()
    (old / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 5}))
    assert tools.tools_for(old) == tools.TOOLS
    assert "playbook" in _text(tools.call_tool(off, "playbook", {}))  # an ERROR naming the tools
    assert _text(tools.call_tool(off, "playbook", {})).startswith("ERROR: there is no tool")


def test_with_the_guide_on_playbook_is_offered(tmp_path):
    on = _folder(tmp_path, guide=True)
    names = [t["name"] for t in tools.tools_for(on)]
    assert names == [t["name"] for t in tools.TOOLS] + [
        "clip",
        "strut",
        "cap",
        "skin",
        "turn",
        "playbook",
        "brief",
    ]
    (on / "reference").mkdir()
    (on / "reference" / "reference-1.png").write_bytes(b"x")
    assert [t["name"] for t in tools.tools_for(on)][-3:] == ["playbook", "brief", "reference"]
    blind = tmp_path / "blind"
    blind.mkdir()
    (blind / "config.json").write_text(json.dumps({"mode": "blind", "guide": True}))
    assert [t["name"] for t in tools.tools_for(blind)] == ["submit"]


@pytest.mark.parametrize("kind", ["vehicle", "aircraft", "hollow", "creature", "plant", "machine"])
@pytest.mark.parametrize("parts", [20, 100, 250, 400, 2000])
def test_playbook_answers(tmp_path, kind, parts):
    f = _folder(tmp_path, guide=True)
    reply = _text(tools.call_tool(f, "playbook", {"kind": kind, "parts": parts}))
    size = 100 if parts < 200 else 400
    assert reply.startswith(f"Playbook: {guide.playbook(kind, size)[0]}.")
    after = "\n\n" + art.PRECEDENCE + "\n\nHOW IT SHOULD LOOK (style guide, "
    assert "\n\n" + guide.playbook(kind, size)[1] + after in reply
    saved = json.loads((f / "playbook.json").read_text())
    assert saved == {
        "kind": kind,
        "parts": parts,
        "playbook": guide.playbook(kind, size)[0],
        "style": saved["style"],
    }


def test_playbook_lists_and_tables_and_refuses(tmp_path):
    f = _folder(tmp_path, guide=True)
    listing = _text(tools.call_tool(f, "playbook", {}))
    for kind in guide.kinds():
        assert f"- {kind}: " in listing
    assert "| Job |" in _text(tools.call_tool(f, "playbook", {"table": True}))
    reply = _text(tools.call_tool(f, "playbook", {"kind": "a fire truck", "parts": 80}))
    assert reply.startswith("Playbook: Vehicle, 100 parts. 'a fire truck' is read as vehicle.")
    for bad in (
        {"kind": "zzz", "parts": 100},
        {"kind": "vehicle"},
        {"parts": 100},
        {"kind": "", "parts": 100},
        {"kind": "vehicle", "parts": 0},
        {"kind": "vehicle", "parts": 1.5},
        {"kind": "vehicle", "parts": True},
        {"kind": 3, "parts": 100},
        {"table": "yes"},
        {"table": True, "kind": "vehicle"},
    ):
        assert _text(tools.call_tool(f, "playbook", bad)).startswith("ERROR: "), bad


# ---- a session with and without the guide -------------------------------------------------


@pytest.fixture
def given(monkeypatch) -> dict[str, Any]:
    """Stands in for the session: records what the builder would have been given."""
    from bricksnap.designer import runner
    from bricksnap.lab import search

    seen: dict[str, Any] = {}

    def fake_session(**kw: Any) -> runner.DesignerRun:
        folder = Path(kw["mcp"]["mcpServers"]["bricksnap"]["args"][-1])
        seen["prompt"] = kw["prompt_file"].read_bytes()
        seen["prompt_file"] = kw["prompt_file"]
        seen["message"] = kw["message"]
        seen["tools"] = tools.tools_for(folder)
        seen["config"] = json.loads((folder / "config.json").read_text())
        if seen["config"].get("guide"):
            tools.call_tool(folder, "playbook", {"kind": "vehicle", "parts": 90})
        out = runner.DesignerRun(ok=True, transcript=kw["transcript"])
        out.final_text = "A car. I followed the vehicle playbook."
        return out

    monkeypatch.setattr(runner, "run_session", fake_session)
    monkeypatch.setattr(search, "load_index", lambda: None)
    return seen


def test_a_session_without_the_guide_is_given_todays_prompt(tmp_path, given):
    record = run.build("a red car", tmp_path / "s")
    assert given["prompt_file"] == run.PROMPT_FILE
    assert _sha(given["prompt"]) == BASELINE_PROMPT_SHA256
    assert _tools_sha(given["tools"]) == BASELINE_TOOLS_SHA256
    assert given["config"]["guide"] is False
    assert given["message"] == run.message("a red car", "tools", 25, 0)
    assert record["guide"] is False and record["playbook"] is None
    assert not (tmp_path / "s" / run.GUIDE_PROMPT_NAME).exists()


def test_a_session_with_the_guide(tmp_path, given):
    record = run.build("a red car", tmp_path / "s", guide=True)
    base = run.PROMPT_FILE.read_text(encoding="utf-8")
    assert given["prompt"].decode() == guide.system_prompt(base)
    assert given["prompt_file"] == tmp_path / "s" / run.GUIDE_PROMPT_NAME
    assert [t["name"] for t in given["tools"]][-2:] == ["playbook", "brief"]
    assert given["config"]["guide"] is True
    assert given["message"] == run.message("a red car", "tools", 25, 0, guide=True)
    assert "hand in with submit {}" in given["message"] and "brief" in given["message"]
    assert "check and submit each use one" not in given["message"]
    assert record["guide"] is True and record["playbook"] == "Vehicle, 100 parts"
    saved = json.loads((tmp_path / "s" / "session.json").read_text())
    assert saved["guide"] is True and saved["playbook"] == "Vehicle, 100 parts"


def test_a_blind_session_refuses_the_guide(tmp_path):
    with pytest.raises(SystemExit, match="blind"):
        run.prepare(tmp_path / "b", "blind", 1, [], guide=True)


def test_the_command_line_switch(tmp_path, given, capsys):
    with pytest.raises(SystemExit):
        run.main(["a red car", "--out", str(tmp_path / "s"), "--guide"])
    assert given["config"]["guide"] is True
    with pytest.raises(SystemExit):
        run.main(["a red car", "--out", str(tmp_path / "t")])
    assert given["config"]["guide"] is False


# ---- a panel, built with the tools as the builder would ------------------------------------

CORE = [
    ("place", {"part": "3031.dat", "colour": 71, "line": 0, "x": 0, "z": 0}),
    ("place", {"part": "3003.dat", "colour": 71, "line": 1, "stud": 6, "socket": 1}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 2}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 3}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 14, "turn": 2}),
    ("place", {"part": "87087.dat", "colour": 72, "line": 1, "stud": 15, "turn": 2}),
]
BRIEF = {
    "scale": "4 studs wide, forced by the narrowest roundable body",
    "colours": [
        {"code": 15, "job": "body", "share": "70%"},
        {"code": 72, "job": "belly", "share": "20%"},
        {"code": 25, "job": "one line", "share": "under 10%"},
        {"code": 10375, "job": "glass"},
    ],
    "pattern": "grey below a low level line",
    "shapes": [
        {"shape": "the core", "part": "87087"},
        {"shape": "a panel", "part": "3020"},
        {"shape": "a rounded top", "part": "11477"},
    ],
    "sideways": "both flanks",
    "thin": "none at this size",
    "studs": "none",
    "glass": "none; it sits flat on the ground",
}
PANEL = ("place", {"part": "3020.dat", "colour": 4, "line": 3, "stud": 2, "socket": 2})
SKIN = [
    ("place", {"part": "3069b.dat", "colour": 15, "line": 7, "stud": 1, "turn": 3}),
    ("place", {"part": "3069b.dat", "colour": 15, "line": 7, "stud": 4, "turn": 3}),
    ("place", {"part": "11477.dat", "colour": 4, "line": 7, "stud": 2}),
    ("place", {"part": "11477.dat", "colour": 4, "line": 7, "stud": 3}),
    ("place", {"part": "3031.dat", "colour": 71, "line": 2, "stud": 1, "socket": 6}),
]


@needs_library
@pytest.mark.parametrize("on", [False, True])
def test_a_panel_on_side_studs(tmp_path, on, monkeypatch):
    from bricksnap.lab import picture

    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": out)
    f = _folder(tmp_path, guide=on)
    if on:  # in guide mode the art direction comes before the first part
        assert _text(tools.call_tool(f, "brief", BRIEF)).startswith("Brief 1 recorded.")
    for name, args in CORE:
        assert "PROBLEM" not in _text(tools.call_tool(f, name, args))
    reply = _text(tools.call_tool(f, *PANEL))
    assert "line 7 is held by 1 stud of line 3 (sideways)" in reply
    assert "line 7 is held by 1 stud of line 4 (sideways)" in reply
    assert "y -52..-12, z -48..-40" in reply
    if on:
        assert "Its studs now (numbered for place on line 7):" in reply
        assert "stud 1: at (-30, -22, -48) pointing -z  (free)" in reply
        assert "stud 8: at (30, -42, -48) pointing -z  (free)" in reply
    else:
        assert "Its studs now" not in reply
    for name, args in SKIN:
        out = _text(tools.call_tool(f, name, args))
        assert "PROBLEM" not in out and "Its studs now" not in out
    report = _text(tools.call_tool(f, "check", {}))
    assert "12 parts of 6 kinds, no problems" in report
