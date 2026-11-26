"""Tests for the art direction the AI builder works to in guide mode: the style guide
(bricksnap/lab/style.py), the brief, the hand-in and the critique (bricksnap/lab/art.py), and
the limits and the words about time and cost that grow with the parts asked for
(bricksnap/lab/freebuild.py).

No test starts a real AI session: ``runner.run_session`` is replaced by a stand-in, and the
tools are called directly, often with a stand-in for the tool that would change the model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from bricksnap.lab import art, freebuild, guide, ldraw_lib, run, style, tools

ROOT = Path(__file__).resolve().parent.parent
STUDY = ROOT / "docs" / "research" / "2026-11-20-what-makes-a-model-look-styled"
SETS_STUDY = ROOT / "docs" / "research" / "2026-11-19-how-real-sets-are-built"

needs_library = pytest.mark.skipif(
    not ldraw_lib.zip_path().is_file(), reason="needs the LDraw parts library"
)

GOOD: dict[str, Any] = {
    "scale": "6 studs wide, 62 span: the width that fits a cabin behind clear glass",
    "colours": [
        {"code": 15, "job": "roof, upper flanks, wing", "share": "70%"},
        {"code": 72, "job": "belly, sweeping up to take the fin", "share": "20%"},
        {"code": 25, "job": "one line along the division, the wingtips", "share": "under 10%"},
        {"code": 10375, "job": "glass"},
        {"code": 0, "job": "frames, tyres"},
    ],
    "pattern": "grey below a low level line, sweeping up behind the cabin",
    "shapes": [
        {"shape": "the high straight wing", "part": "curved slope 11477 on the leading edge"},
        {"shape": "the raked screen", "part": "windscreen 30841"},
        {"shape": "the tapering tail cone", "part": "wedge plates 43722b/43723b"},
    ],
    "sideways": "both flanks, the nose face, the fin",
    "thin": "struts, aerials",
    "studs": "none on the body; one row at the flap line",
    "glass": "a dark band set into the flank; level, belly 3 studs up",
}

FULL = {k: {"answer": "yes"} for k in style.CRITIQUE_KEYS}
BRICK = "1 15 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat"


def _folder(tmp_path: Path, **config: Any) -> Path:
    f = tmp_path / "work"
    f.mkdir()
    (f / "config.json").write_text(
        json.dumps({"mode": "tools", "max_checks": 5, "guide": True, **config})
    )
    return f


def _text(blocks: list[dict[str, Any]]) -> str:
    assert len(blocks) >= 1 and blocks[0]["type"] == "text"
    return "\n".join(b["text"] for b in blocks if b["type"] == "text")


class Stand:
    """Stands in for the tools that change or show the model: with ``write`` it adds a part
    line to model.ldr, as a tool that builds does, whatever it answers."""

    def __init__(self, write: bool = False, reply: str = "Added as line 1.") -> None:
        self.calls: list[dict[str, Any]] = []
        self.write = write
        self.reply = reply

    def __call__(self, folder: Path, args: dict[str, Any]) -> list[dict[str, Any]]:
        self.calls.append(args)
        if self.write:
            with (folder / "model.ldr").open("a", encoding="utf-8") as f:
                f.write(BRICK + "\n")
        return [{"type": "text", "text": self.reply}]


def _call(f: Path, name: str, args: dict[str, Any], stand: Stand | None = None) -> str:
    return _text(art.call(f, name, args, stand or Stand()))


@pytest.fixture
def no_pictures(monkeypatch):
    """The hand-in sheet draws its three views with LeoCAD: a small stand-in here."""
    from PIL import Image

    from bricksnap.lab import picture

    def sheet(text: str, out: Path, title: str = "") -> Path:
        Image.new("RGB", (8, 8), "white").save(out)
        return out

    monkeypatch.setattr(picture, "model_sheet", sheet)


def _handed(f: Path, critique: dict[str, Any] | None = None) -> str:
    """Ask for the hand-in sheet, then answer it."""
    sheet = _call(f, "submit", {})
    assert sheet.startswith("HAND-IN SHEET"), sheet[:200]
    return _call(f, "submit", {"critique": critique or FULL})


# ---- the style guide and its reader ---------------------------------------------------------


def test_the_two_copies_of_each_guide_agree():
    """The studies' files are the record; the package's are what the builder reads."""
    assert style.STYLE_FILE.read_bytes() == (STUDY / "style-guide.md").read_bytes()
    assert guide.GUIDE_FILE.read_bytes() == (SETS_STUDY / "guide.md").read_bytes()


@pytest.mark.parametrize(
    "heading",
    [style.BRIEF_HEADING, style.RULES_HEADING, style.SUBJECTS_HEADING, style.CRITIQUE_HEADING],
)
def test_the_headings_the_reader_needs_are_there(heading):
    assert ("\n" + heading) in style.text()


def test_the_parts_of_the_style_guide():
    lines = style.brief_lines()
    assert [k for k, _, _ in lines] == list(style.BRIEF_KEYS)
    assert [t for _, t, _ in lines][-1] == "Glass and stance"
    rules = style.rules().splitlines()
    assert len(rules) == 13 and [r.split(".")[0] for r in rules] == [str(n) for n in range(1, 14)]
    assert "[" not in style.rules() and "]" not in style.rules()
    assert rules[0].startswith("1. **Cap every upward face**")
    assert "Use clear 47 over an interior, or trans-black 10375 with none." in rules[9]
    assert list(style.subjects()) == list(style.SUBJECT_NAMES)
    assert all(text.count("\n") >= 5 for text in style.subjects().values())
    assert "[" not in "".join(style.subjects().values())
    qs = style.questions()
    assert len(qs) == 10 and qs[0][1] == "Does the outline alone say what it is?"
    assert style.critique_intro().startswith("Look at your pictures and answer yes or no.")


def test_a_stripe_is_tiles_on_a_skin_or_a_sideways_band_not_a_stack_of_plates():
    rule = next(ln for ln in style.text().splitlines() if ln.startswith("6. **One livery.**"))
    division = rule.split("Carry a division unbroken across parts: ")[1]
    assert division.startswith("a row of tiles of the stripe's colour on a skin, a sideways band")
    assert "Never a stripe as a stack of plate courses" in rule
    assert "a plate course only where it is hidden or holds the structure" in rule


def test_scale_is_the_largest_the_parts_pay_for():
    scale = dict((k, w) for k, _, w in style.brief_lines())["scale"]
    assert "the largest scale the parts asked for will pay for" in scale
    assert "never below the smallest at which the subject's signature shapes" in scale
    assert "what that width lets you show that the next size down would not" in scale
    assert "not on hidden filling or an interior nobody sees" in scale
    text = guide.system_prompt(run.PROMPT_FILE.read_text(encoding="utf-8"))
    for said in (text, art.BRIEF["description"]):
        assert "Take the smallest scale" not in said and "take the smallest scale" not in said
        assert "largest scale the parts asked for will pay for" in said
    aircraft = style.subjects()["Aircraft"]
    assert "about 300 parts pay for 4 wide and about 600 for 6 wide" in aircraft


def test_a_leg_is_held_by_studs_and_a_clip_holds_only_what_carries_nothing():
    rules = guide.rules().splitlines()
    assert len(rules) == 12
    assert "hangs well on one clip on" in rules[4] and "(a strut, rail, aerial" in rules[4]
    assert "the checker tests that clip for fit as it does studs" in rules[4]
    assert (
        "a leg the model stands on is fixed by studs, a pin, or a bar seated in a hollow"
        in (rules[4])
    )
    assert "A clip gripping a bar or handle holds by its shape" in rules[8]
    thin = style.rules().splitlines()[7]
    assert "only what carries nothing" in thin
    assert "a leg the model stands on is fixed by studs" in thin


def test_the_aircraft_playbooks():
    assert list(guide.kinds())[1] == "aircraft" and guide.sizes("aircraft") == [100, 400]
    for parts in (100, 400):
        title, body, _ = guide.playbook("aircraft", parts)
        assert title == f"Aircraft, {parts} parts"
        assert body.startswith("[") and "sets" in body.splitlines()[0]
        heads = re.findall(r"^- \*\*([^:*]+):\*\*", body, re.M)
        assert heads == ["Core", "Strong", "Outside", "Moves", "Order", "Not"]
    small = guide.playbook("aircraft", 100)[1]
    assert "spine 2 studs wide of side-stud bricks" in small
    assert "one long course of plates passing over or through the body" in small
    assert "jumper plates on the centre line" in small and "struts, aerials" in small


def _numbers_in_rules() -> tuple[set[int], set[str]]:
    """Every LDraw colour code and part number the style guide's rules and sections name."""
    colours: set[int] = set()
    parts: set[str] = set()
    text = style.rules() + "\n" + "\n".join(style.subjects().values())
    colour_words = (
        r"(?:dark blue|dark red|dark green|sand blue|sand green|dark azure|dark orange"
        r"|medium nougat|dark tan|greys|clear|trans-black|trans-brown)"
    )
    for m in re.finditer(colour_words + r" (\d+)(?: (\d+))?", text):
        colours.update(int(g) for g in m.groups() if g)
    stripped = re.sub(colour_words + r" \d+(?: \d+)?", "", text)
    # "about 300 parts" is a count, not a part number
    for m in re.finditer(r"(?<![\w.%-])(?<!about )(\d{3,6}[a-z]?)(?![\w%-])", stripped):
        if not re.fullmatch(r"(19|20)\d\ds", m.group(1)):  # "the 1980s" is a decade
            parts.add(m.group(1))
    return colours, parts


@needs_library
def test_every_colour_and_part_the_style_guide_names_is_in_the_library():
    colours, parts = _numbers_in_rules()
    assert {272, 320, 288, 379, 378, 321, 484, 84, 28, 71, 72, 47, 10375, 40} <= colours
    assert len(parts) > 60 and {"3070b", "11477", "99780", "23443", "77180"} <= parts
    lib = ldraw_lib.library()
    names = lib.colours()
    assert [c for c in sorted(colours) if c not in names] == []
    assert [p for p in sorted(parts) if lib.resolve(p + ".dat") is None] == []
    assert not parts & {"150", "300", "600"}  # counts of parts
    moved = [p for p in sorted(parts) if lib.header(p + ".dat").description.startswith("~")]
    assert moved == []


# ---- the guide-mode instructions ---------------------------------------------------------------


def _prompt(session: str = "first") -> str:
    return guide.system_prompt(run.PROMPT_FILE.read_text(encoding="utf-8"), session)


def test_clips_on_bars_are_offered_as_a_tested_joint_not_warned_off():
    on = _prompt()
    assert "A clip on a bar or handle is tested for fit as a stud is" in on
    assert "do not move such a part onto studs to have it confirmed" in on
    assert "make sure each of those is a real joint" not in on
    off = run.PROMPT_FILE.read_text(encoding="utf-8")
    assert "most clips on bars (a clip on a bar is a proper joint for a thin part)" in off


def test_the_guide_mode_instructions_carry_the_art_direction():
    text = _prompt()
    assert style.rules() in text and "# Art direction" in text and "## Rules of finish" in text
    assert "[S" not in text and "[D" not in text and "[T]" not in text
    assert (
        "the check ends with a section HOW IT LOOKS: treat each line outside its range as "
        "something to fix before you answer the critique"
    ) in text.replace("The check ends", "the check ends")
    assert "three body colours carry the look; the other colours a model has are small parts" in (
        text
    )
    assert "where they disagree about how the body is made, the style guide wins" in text
    assert "the person's words, then your brief" in text
    assert (
        text.index("7. Stop when")
        < text.index("# How set designers build")
        < text.index("# Panels")
        < text.index("# Art direction")
        < text.index("# When the subject moves")
    )
    assert "# Art direction" not in run.PROMPT_FILE.read_text(encoding="utf-8")


def test_the_working_order_is_the_order_things_must_happen():
    text = _prompt()
    order = text[text.index("Work in this order:") : text.index("# How set designers build")]
    steps = re.findall(r"^(\d)\. (.*)$", order, re.M)
    assert [n for n, _ in steps] == [str(n) for n in range(1, 8)]
    said = [s for _, s in steps]
    assert said[0].startswith("Decide what the subject is")
    assert said[1].startswith("Then call playbook once")
    assert said[2].startswith("Find the parts that make the subject's signature shapes")
    assert said[3].startswith("Write the art direction and give it with brief")
    assert said[4].startswith("Build to it")
    assert "submit {}" in said[6] and "critique" in said[6]


def test_what_repeats_is_cut_and_turns_are_spent_truly():
    text = _prompt()
    assert "# What makes a model look designed rather than stacked" not in text
    assert "Thin members that carry nothing" not in text  # rules 5 and 8 say it
    assert "# When you start from a model" not in text
    assert "# When you are asked for a change" not in text
    assert "Use place for every part that connects by studs" not in text
    assert "give it a list of placements to do several in one call" in text
    assert "regular runs whose positions you can work out" in text and "mirror" in text
    assert len(text) < 21_000


def test_the_first_message_in_guide_mode():
    off = run.message("a plane", "tools", 25, 0)
    on = run.message("a plane", "tools", 25, 0, guide=True)
    assert off == run.message("a plane", "tools", 25, 0, guide=False)
    assert "check and submit each use one" in off and "brief" not in off
    assert "check and submit with ldraw each use one; handing in does not" in on
    assert "hand in with submit {}" in on and "critique" in on and "playbook" in on
    colours = [{**c, "name": ""} for c in GOOD["colours"]]
    lines = art.brief_lines({**GOOD, "colours": colours})
    change = run.message(
        "make it blue",
        "tools",
        25,
        0,
        start="1 4 ...",
        change_of="a plane",
        guide=True,
        brief=lines,
    )
    assert "The model's art direction (its brief)" in change and "Scale: 6 studs wide" in change
    assert "first call brief with the new version and your reason" in change


def test_out_of_checks_in_guide_mode_says_to_hand_in(tmp_path):
    f = _folder(tmp_path, max_checks=0)
    (f / "model.ldr").write_text(BRICK + "\n")
    said = _text(tools._check_text(f, BRICK + "\n", "the model as built"))
    assert said.startswith("ERROR: this session has used all 0 checks. Hand in now: submit {}")
    off = tmp_path / "off"
    off.mkdir()
    (off / "config.json").write_text(json.dumps({"mode": "tools", "max_checks": 0}))
    assert "Stop here and say in a few lines" in _text(tools._check_text(off, BRICK, "x"))


# ---- the playbook ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "words", "sections"),
    [
        ("aircraft", "", ["Aircraft"]),
        ("vehicle", "a Cessna 172 high-wing plane", ["Aircraft"]),
        ("vehicle", "a red fire truck", ["Car"]),
        ("vehicle", "a sports car", ["Car"]),
        ("vehicle", "a steam train", ["Aircraft", "Car"]),
        ("creature", "a sitting cat", ["Creature or character"]),
        ("hollow", "a corner shop", ["Building"]),
        ("hollow", "a treasure chest", ["Object"]),
        ("machine", "a crane", ["Object"]),
        ("machine", "a technic car", ["Car"]),
        ("plant", "a sunflower in a pot", ["Object"]),
    ],
)
def test_which_style_section_a_subject_gets(kind, words, sections):
    chosen, why = style.subject_for(kind, words)
    assert chosen == sections and why


@pytest.mark.parametrize(
    ("subject", "kind", "book", "head"),
    [
        ("a Cessna 172", "vehicle", "Aircraft, 100 parts", "(style guide, Aircraft)."),
        ("a Cessna 172", "aircraft", "Aircraft, 100 parts", "(style guide, Aircraft)."),
        ("a small red fire truck", "vehicle", "Vehicle, 100 parts", "(style guide, Car)."),
        ("a boat", "vehicle", "Vehicle, 100 parts", "(style guide, Aircraft and Car)."),
        ("a sitting cat", "creature", "Creature", "(style guide, Creature or character)."),
        ("a sunflower", "plant", "Plant, 100 parts", "(style guide, Object)."),
    ],
)
def test_playbook_hands_over_the_structure_then_what_governs_then_the_style(
    tmp_path, subject, kind, book, head
):
    f = _folder(tmp_path, subject=subject)
    reply = _text(tools.call_tool(f, "playbook", {"kind": kind, "parts": 150}))
    assert reply.startswith(f"Playbook: {book}")
    assert "HOW IT SHOULD LOOK " + head in reply
    body = guide.playbook(guide.refine(guide.kind_of(kind) or kind, subject), 150)[1]
    assert reply.index(body) < reply.index(art.PRECEDENCE) < reply.index("HOW IT SHOULD")
    assert "the style section wins" in art.PRECEDENCE
    names = head.split("style guide, ")[1].split(")")[0].split(" and ")
    for name in names:
        assert style.subjects()[name] in reply
    assert json.loads((f / "playbook.json").read_text())["style"] == names
    if "Cessna" in subject:  # the aircraft's own structure, not the truck's
        assert "bumpers hang from clip plates" not in reply and "brick walls" not in reply


# ---- the tools in guide mode ------------------------------------------------------------------


def test_the_guide_mode_tools(tmp_path):
    f = _folder(tmp_path)
    listed = tools.tools_for(f)
    names = [t["name"] for t in listed]
    assert names[-2:] == ["playbook", "brief"] and names.count("submit") == 1
    submit = next(t for t in listed if t["name"] == "submit")
    assert submit is art.SUBMIT and "critique" in submit["input_schema"]["properties"]
    assert submit["input_schema"].get("required") is None
    assert "First {}" in submit["description"]
    for _, q in style.questions():
        assert q in submit["description"]
    for _, title, what in style.brief_lines():
        assert f"({title}): {what}" in art.BRIEF["description"]
    place = next(t for t in listed if t["name"] == "place")
    assert (
        "parts" in place["input_schema"]["properties"] and "required" not in place["input_schema"]
    )
    assert "Many at once" in place["description"]
    off = tmp_path / "off"
    off.mkdir()
    (off / "config.json").write_text(json.dumps({"mode": "tools", "guide": False}))
    plain = tools.tools_for(off)
    assert "brief" not in [t["name"] for t in plain]
    assert (
        "parts" not in next(t for t in plain if t["name"] == "place")["input_schema"]["properties"]
    )


# ---- the brief ----------------------------------------------------------------------------


@needs_library
def test_a_good_brief_is_recorded_with_two_lines(tmp_path):
    f = _folder(tmp_path)
    reply = _call(f, "brief", GOOD)
    first, *rest = reply.split("\n")
    assert first.startswith("Brief 1 recorded. It commits you to: 6 studs wide")
    assert "15 White (roof, upper flanks, wing, 70%)" in first
    assert "10375 Trans Black (glass)" in first
    assert len(rest) == 1 and rest[0].startswith("Build these shapes: the high straight wing")
    kept = art.record(f)["brief"]
    assert kept["colours"][0] == {
        "code": 15,
        "name": "White",
        "job": "roof, upper flanks, wing",
        "share": "70%",
        "value": "#F4F4F4",
    }
    assert list(kept) == list(style.BRIEF_KEYS)
    assert art.record(f)["briefs"][0]["parts_before"] == 0


@needs_library
def test_a_bad_brief_names_everything_that_is_missing(tmp_path):
    f = _folder(tmp_path)
    bad = {k: v for k, v in GOOD.items() if k not in ("pattern", "studs")}
    bad["shapes"] = GOOD["shapes"][:2]
    reply = _call(f, "brief", bad)
    assert reply.startswith("ERROR: the brief is not complete: ")
    assert '"pattern" (pattern)' in reply and '"studs" (studs)' in reply
    assert "give three to five shapes (you gave 2)" in reply
    assert art.record(f)["brief"] is None


@needs_library
@pytest.mark.parametrize("count", [2, 6, 9])
def test_three_to_five_shapes(tmp_path, count):
    f = _folder(tmp_path)
    shapes = [{"shape": f"shape {k}", "part": "3001"} for k in range(count)]
    reply = _call(f, "brief", {**GOOD, "shapes": shapes})
    assert f"give three to five shapes (you gave {count})" in reply


@needs_library
@pytest.mark.parametrize("code", [99999, 16, 24])
def test_a_brief_with_an_unknown_colour_is_refused(tmp_path, code):
    f = _folder(tmp_path)
    brief = {**GOOD, "colours": [*GOOD["colours"], {"code": code, "job": "trim"}]}
    reply = _call(f, "brief", brief)
    assert reply.startswith("ERROR:") and f"there is no colour {code} in the library" in reply


@needs_library
def test_a_shape_must_name_a_real_part(tmp_path):
    f = _folder(tmp_path)
    shapes = [
        {"shape": "the wing", "part": "wing plate 41769b and an invented 99999z"},
        {"shape": "the nose", "part": "curved slopes"},
        {"shape": "the screen", "part": "30841.dat"},
    ]
    reply = _call(f, "brief", {**GOOD, "shapes": shapes})
    assert "there is no part 99999z in the library (named for 'the wing')" in reply
    assert "name the part that makes 'the nose' by its LDraw number" in reply
    assert "41769b" not in reply.split("there is no part")[1] and "30841" not in reply


@needs_library
def test_more_than_three_body_colours_need_a_reason(tmp_path):
    f = _folder(tmp_path)
    more = [{"code": 320, "job": "spinner"}, {"code": 272, "job": "a pinstripe"}]
    four = {**GOOD, "colours": [*GOOD["colours"], *more]}
    reply = _call(f, "brief", four)
    assert "it has 4 body colours (15 White, 25 Orange, 320 Dark Red, 272 Dark Blue)" in reply
    three = {**GOOD, "colours": [*GOOD["colours"], {"code": 71, "job": "legs"}]}
    assert _call(f, "brief", three).startswith("Brief 1 recorded.")
    ok = _call(f, "brief", {**four, "why_more": "the spinner is red", "reason": "a red nose"})
    assert ok.startswith("Brief 2 recorded (the change and its reason are kept).")


@needs_library
def test_a_brief_may_be_changed_on_purpose_and_every_version_is_kept(tmp_path):
    f = _folder(tmp_path)
    assert _call(f, "brief", GOOD).startswith("Brief 1 recorded.")
    _call(f, "add", {}, Stand(write=True))
    again = {**GOOD, "scale": "8 studs wide"}
    assert 'say why in "reason"' in _call(f, "brief", again)
    reply = _call(f, "brief", {**again, "reason": "600 parts pay for it"})
    assert reply.startswith("Brief 2 recorded")
    briefs = art.record(f)["briefs"]
    assert [(b["n"], b["reason"], b["parts_before"]) for b in briefs] == [
        (1, None, 0),
        (2, "600 parts pay for it", 1),
    ]


# ---- building before the brief, and what counts as a change -----------------------------------


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("place", {}),
        ("place", {"parts": [{}, {}]}),
        ("add", {}),
        ("fill", {}),
        ("place_module", {}),
        ("submit", {"ldraw": BRICK}),
    ],
)
def test_the_first_build_call_before_a_brief_is_refused_once_and_only_once(tmp_path, name, args):
    f = _folder(tmp_path)
    stand = Stand(write=True)
    reply = _call(f, name, args, stand)
    assert reply.startswith("ERROR: write the art direction first: call brief")
    assert stand.calls == [] and not (f / "model.ldr").exists()
    _call(f, name, args, stand)
    _call(f, "add", {}, stand)
    assert stand.calls
    assert art.record(f)["built_without_brief"] is True


def test_other_tools_are_never_refused_for_want_of_a_brief(tmp_path):
    f = _folder(tmp_path)
    for name in ("search_parts", "part_info", "check", "look", "mirror", "remove", "model"):
        assert _call(f, name, {}) == "Added as line 1."
    assert _call(f, "place", {}).startswith("ERROR: write the art direction first")


@pytest.mark.parametrize(
    "name", ["place", "add", "fill", "place_module", "mirror", "remove", "remove_box", "joint"]
)
def test_every_tool_that_changes_the_file_is_a_change(tmp_path, name, no_pictures):
    f = _folder(tmp_path, start={"file": "x.ldr"})
    art.seed(f, GOOD)  # a brief, so nothing is refused
    (f / "model.ldr").write_text(BRICK + "\n")
    _handed(f)
    assert art.record(f)["critique"]["changed_after"] is False
    _call(f, name, {}, Stand(write=True))
    assert art.record(f)["critique"]["changed_after"] is True
    head = _call(f, "submit", {"critique": FULL})
    assert head.startswith("Your critique was not recorded: the model has changed since its")


def test_a_reply_that_says_nothing_changed_does_not_hide_a_change(tmp_path, no_pictures):
    """submit with ldraw when the checks are used up answers with an error, but the model
    file was replaced: a critique given before stands for a model it never saw."""
    f = _folder(tmp_path, max_checks=0)
    art.seed(f, GOOD)
    (f / "model.ldr").write_text(BRICK + "\n")
    _handed(f)
    reply = _text(tools.call_tool(f, "submit", {"ldraw": BRICK.replace(" 15 ", " 4 ")}))
    assert reply.startswith("ERROR: this session has used all 0 checks")
    assert " 4 " in (f / "model.ldr").read_text()
    assert art.record(f)["critique"]["changed_after"] is True


def test_a_call_that_changes_nothing_is_not_a_change(tmp_path, no_pictures):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    (f / "model.ldr").write_text(BRICK + "\n")
    _handed(f)
    for name in ("check", "look", "model", "search_parts", "remove"):
        _call(f, name, {}, Stand(write=False))
    assert art.record(f)["critique"]["changed_after"] is False


@needs_library
def test_place_takes_a_list_and_stops_at_the_first_that_fails(tmp_path, monkeypatch):
    f = _folder(tmp_path)
    monkeypatch.setattr(tools, "_quick", lambda folder, text, lines, report=None: "fine")
    _call(f, "brief", GOOD)
    items = [
        {"part": "3001.dat", "colour": 15, "line": 0, "x": 0, "z": 0},
        {"part": "3001.dat", "colour": 15, "line": 1, "stud": 1},
        {"part": "nope.dat", "colour": 15, "line": 2, "stud": 1},
        {"part": "3001.dat", "colour": 15, "line": 2, "stud": 1},
    ]
    reply = _text(tools.call_tool(f, "place", {"parts": items}))
    assert reply.startswith("1. Added as line 1:") and "\n\n2. Added as line 2:" in reply
    assert "\n\n3. ERROR:" in reply and "Stopped at placement 3; the 2 before it are in" in reply
    assert "\n\n4." not in reply
    assert sum(1 for ln in (f / "model.ldr").read_text().splitlines() if ln.startswith("1 ")) == 2
    too_many = _text(tools.call_tool(f, "place", {"parts": [items[0]] * (art.MAX_BATCH + 1)}))
    assert too_many.startswith(f"ERROR: place at most {art.MAX_BATCH}")


# ---- handing in ---------------------------------------------------------------------------


@needs_library
def test_the_hand_in_sheet(tmp_path, no_pictures):
    f = _folder(tmp_path, parts=300)
    _call(f, "brief", GOOD)
    (f / "model.ldr").write_text(
        "\n".join(
            [
                "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat",
                "1 4 0 -48 0 1 0 0 0 1 0 0 0 1 3001.dat",
                "1 1 0 -72 0 1 0 0 0 1 0 0 0 1 3001.dat",
                "1 15 0 -80 0 1 0 0 0 1 0 0 0 1 3020.dat",
                "1 10375 0 -88 0 1 0 0 0 1 0 0 0 1 3020.dat",
            ]
        )
        + "\n"
    )
    blocks = art.call(f, "submit", {}, tools._submit)
    said = _text(blocks)
    assert said.startswith("HAND-IN SHEET: the model as it stands, from three sides")
    assert "YOUR BRIEF (version 1):\nScale: 6 studs wide" in said
    assert "Parts: 5 of about 300 asked for." in said
    assert "Size: 4 studs wide (x), 2 long (z), 3.7 bricks high." in said
    assert "Colours as seen from five sides: Red 4 " in said
    assert "HOW IT LOOKS (measured on the model as it stands):\n- " in said
    assert "Over 5% and not in your brief: Red 4" in said and "Blue 1" in said
    assert "In your brief but not in the model: Dark Bluish Grey 72, Orange 25, Black 0." in said
    assert "Transparent parts: Trans Black 10375 (1 parts)." in said
    assert "Body colours used (not black, grey or transparent): 3." in said
    for i, (key, q) in enumerate(style.questions(), 1):
        assert f"{i}. {key}: {q}" in said
    assert any(b["type"] == "image" for b in blocks)
    sheet = art._state(f)["sheet"]
    assert sheet["facts"]["parts"] == 5 and sheet["changes"] == 0


def test_a_critique_without_a_sheet_gets_the_sheet_and_is_not_recorded(tmp_path, no_pictures):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    reply = _call(f, "submit", {"critique": FULL})
    assert reply.startswith("Your critique was not recorded: a critique answers the hand-in sheet")
    assert "HAND-IN SHEET" in reply and art.record(f)["critique"] is None
    assert _call(f, "submit", {"critique": FULL}).startswith("Critique recorded: 10 yes, 0 no.")


def test_a_failed_look_does_not_matter_any_more(tmp_path, no_pictures):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    _call(f, "look", {}, Stand(reply="ERROR: LeoCAD is not here."))
    assert _handed(f).startswith("Critique recorded")


def test_a_no_needs_a_note_that_says_something_once(tmp_path, no_pictures):
    f = _folder(tmp_path, max_checks=0)  # no checks left: no rebuild asked
    art.seed(f, GOOD)
    answers = {**FULL, "thin": {"answer": "no", "note": "."}, "glass": {"answer": "no"}}
    reply = _handed(f, answers)
    assert reply.startswith('ERROR: a "no" needs a note of at least 3 words')
    assert "thin: Is everything thin" in reply and "glass: Does the glass" in reply
    assert "outline:" not in reply
    again = _call(f, "submit", {"critique": answers})
    assert again.startswith("Critique recorded: 8 yes, 2 no. The model is handed in")
    assert art.record(f)["critique"]["unexplained"] == ["thin", "glass"]


def test_a_no_sends_it_back_to_rebuild_once(tmp_path, no_pictures):
    f = _folder(tmp_path)  # five checks, none used
    art.seed(f, GOOD)
    answers = {**FULL, "thin": {"answer": "no", "note": "the struts are still thick beams"}}
    reply = _handed(f, answers)
    assert reply.startswith("Critique recorded: 9 yes, 1 no. You answered no to: thin:")
    assert "Rebuild those regions now" in reply and "This is asked once" in reply
    _call(f, "add", {}, Stand(write=True))
    kept = {**FULL, "glass": {"answer": "no", "note": "no glass on this model, it stays"}}
    second = _handed(f, kept)
    assert second.startswith("Critique recorded: 9 yes, 1 no. The model is handed in")
    record = art.record(f)
    assert record["critiques"] == 2 and record["first_no"] == ["thin"]
    assert [a["key"] for a in record["critique"]["answers"] if a["answer"] == "no"] == ["glass"]
    assert record["critique"]["changed_after"] is False
    assert record["ended_without_critique"] is False


R90 = "0 0 1 0 1 0 -1 0 0"
FLANKS = "".join(
    [f"1 7 0 -24 0 {R90} 3001.dat\n"]
    + [f"1 14 {x} {-8 * k - 8} 0 {R90} 3710.dat\n" for x in (-30, 30) for k in range(3)]
)  # a brick with three plates stacked on either side: plate seams, nothing sideways


def test_flanks_out_of_range_send_the_first_hand_in_back_once_with_where(tmp_path, no_pictures):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    (f / "model.ldr").write_text(FLANKS)
    reply = _handed(f)  # every answer yes
    assert reply.startswith("Critique recorded: 10 yes, 0 no. The flanks are outside")
    assert "- Plate seams on the sides: 1.04 per stud" in reply and "Where: left/right" in reply
    assert "- Built sideways: 0% of parts" in reply and "Colour areas" not in reply
    assert "Rebuild those regions now" in reply and "This is asked once" in reply
    assert art._state(f)["critiques"][0]["looks_gate"][0].startswith("Plate seams")
    second = _handed(f)  # nothing rebuilt: accepted, as a no is the second time
    assert second.startswith("Critique recorded: 10 yes, 0 no. The model is handed in")


def test_flanks_out_of_range_are_not_sent_back_with_no_checks_left(tmp_path, no_pictures):
    f = _folder(tmp_path, max_checks=0)
    art.seed(f, GOOD)
    (f / "model.ldr").write_text(FLANKS)
    assert _handed(f).startswith("Critique recorded: 10 yes, 0 no. The model is handed in")


def test_the_record_keeps_the_last_critique(tmp_path, no_pictures):
    f = _folder(tmp_path, max_checks=0)
    art.seed(f, GOOD)
    _handed(f, {**FULL, "stance": {"answer": "no", "note": "it tips onto its tail wheel"}})
    _handed(f)
    record = art.record(f)
    assert record["critiques"] == 2
    assert all(a["answer"] == "yes" for a in record["critique"]["answers"])
    assert record["first_no"] is None  # the first was not sent back: no checks were left


def test_a_critique_that_is_not_complete_is_an_error(tmp_path, no_pictures):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    _call(f, "submit", {})
    part = {k: v for k, v in FULL.items() if k != "stance"}
    reply = _call(f, "submit", {"critique": {**part, "outline": {"answer": "maybe"}, "x": {}}})
    assert reply.startswith("ERROR: the critique is not complete: no answer to stance")
    assert '"answer" must be "yes" or "no" for outline' in reply and "no question x" in reply
    assert _call(f, "submit", {"critique": "all fine"}).startswith("ERROR: critique must be")


def test_submit_with_ldraw_rewrites_and_a_critique_with_it_is_not_kept(tmp_path, no_pictures):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    stand = Stand(write=True)
    reply = _call(f, "submit", {"ldraw": BRICK, "critique": FULL}, stand)
    assert stand.calls == [{"ldraw": BRICK}]
    assert "Your critique was not recorded: the model has just been replaced." in reply
    assert art.record(f)["critique"] is None


def test_a_session_that_ends_without_a_critique_says_so(tmp_path):
    f = _folder(tmp_path)
    art.seed(f, GOOD)
    record = art.record(f)
    assert record["art"] is True and record["ended_without_critique"] is True


def test_halfway_the_check_shows_the_brief_once(tmp_path):
    f = _folder(tmp_path, parts=4)
    art.seed(f, GOOD)
    (f / "model.ldr").write_text(BRICK + "\n")
    assert "HALFWAY" not in _call(f, "check", {})
    (f / "model.ldr").write_text(BRICK + "\n" + BRICK + "\n")
    said = _call(f, "check", {})
    assert "HALFWAY (about 2 of 4 parts are in). Your brief:\nScale: 6 studs wide" in said
    assert "Does what stands so far follow it? If not, fix it now" in said
    assert "HALFWAY" not in _call(f, "check", {})


# ---- a change run builds to the model's brief ---------------------------------------------------


def test_a_change_run_carries_the_brief(tmp_path):
    f = _folder(tmp_path, start={"file": "model.ldr"})
    (f / "model.ldr").write_text(BRICK + "\n")
    art.seed(f, GOOD, from_run=3)
    assert _call(f, "place", {}, Stand(write=True)) == "Added as line 1."  # not refused
    record = art.record(f)
    assert record["built_without_brief"] is False
    assert record["briefs"][0]["carried"] is True and record["briefs"][0]["from_run"] == 3
    assert 'say why in "reason"' in _call(f, "brief", GOOD)


# ---- the record of a session ----------------------------------------------------------------


@pytest.fixture
def session(monkeypatch) -> dict[str, Any]:
    """Stands in for the session: the builder writes a brief, builds and hands in."""
    from bricksnap.designer import runner
    from bricksnap.lab import picture, search

    seen: dict[str, Any] = {}

    def fake_session(**kw: Any) -> runner.DesignerRun:
        folder = Path(kw["mcp"]["mcpServers"]["bricksnap"]["args"][-1])
        seen["config"] = json.loads((folder / "config.json").read_text())
        seen["message"] = kw["message"]
        seen["prompt"] = kw["prompt_file"].read_text()
        if seen["config"].get("guide"):
            if not seen.get("skip_brief"):
                tools.call_tool(folder, "brief", GOOD)
            tools.call_tool(folder, "add", {"ldraw": BRICK})
            tools.call_tool(folder, "submit", {})
            seen["handed"] = tools.call_tool(folder, "submit", {"critique": FULL})
        transcript = kw["transcript"]
        transcript.parent.mkdir(parents=True, exist_ok=True)
        events = [{"type": "assistant", "message": {"id": f"m{k % 3}"}} for k in range(7)]
        transcript.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        out = runner.DesignerRun(ok=True, transcript=transcript)
        out.final_text = "A plane."
        return out

    monkeypatch.setattr(runner, "run_session", fake_session)
    monkeypatch.setattr(search, "load_index", lambda: None)
    monkeypatch.setattr(picture, "view", lambda text, out, lat, lon: _png(out))
    monkeypatch.setattr(picture, "model_sheet", lambda text, out, title="": _png(out))
    monkeypatch.setattr(tools, "_quick", lambda folder, text, lines, report=None: "fine")
    return seen


def _png(out: Path) -> Path:
    from PIL import Image

    out.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), "white").save(out)
    return out


@needs_library
def test_the_session_record_holds_the_brief_and_the_critique(tmp_path, session):
    record = run.build("a Cessna 172", tmp_path / "s", guide=True, parts=300)
    assert session["config"]["subject"] == "a Cessna 172" and session["config"]["parts"] == 300
    assert session["handed"][0]["text"].startswith("Critique recorded: 10 yes")
    saved = json.loads((tmp_path / "s" / "session.json").read_text())
    for r in (record, saved):
        assert r["art"] is True and r["brief"]["scale"].startswith("6 studs wide")
        assert len(r["briefs"]) == 1 and r["built_without_brief"] is False
        assert len(r["critique"]["answers"]) == 10 and r["critiques"] == 1
        assert r["critique"]["facts"]["parts"] == 1
        assert r["ended_without_critique"] is False
        assert r["replies"] == 3  # three distinct replies in the transcript


@needs_library
def test_a_change_session_is_given_the_brief(tmp_path, session):
    start = tmp_path / "start.ldr"
    start.write_text(BRICK + "\n")
    session["skip_brief"] = True
    record = run.build(
        "make it blue",
        tmp_path / "s",
        guide=True,
        start=start,
        change_of="a Cessna 172",
        brief=GOOD,
        brief_run=2,
    )
    assert "The model's art direction (its brief)" in session["message"]
    assert "# When you are asked for a change" in session["prompt"]
    assert "# When you start from a model" not in session["prompt"]
    assert record["briefs"][0]["carried"] is True and record["built_without_brief"] is False


def test_a_session_without_the_guide_records_no_art_direction(tmp_path, session):
    record = run.build("a red car", tmp_path / "s")
    assert "subject" not in session["config"] and "parts" not in session["config"]
    assert "brief" not in record and "critique" not in record and "art" not in record


# ---- limits, time and cost ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("parts", "replies", "checks", "minutes"),
    [
        (None, 120, 25, 90),
        (20, 120, 25, 90),
        (80, 120, 25, 90),
        (206, 206, 26, 90),
        (257, 257, 33, 90),
        (300, 300, 38, 90),
        (400, 400, 50, 120),
        (600, 600, 75, 180),
        (6000, 600, 75, 180),  # a hand-edited project.json is held to 600
        (-5, 120, 25, 90),
        ("300", 120, 25, 90),
    ],
)
def test_the_limits_grow_with_the_parts_asked_for(parts, replies, checks, minutes):
    got = freebuild.limits(parts)
    assert got == {"max_turns": replies, "max_checks": checks, "timeout": minutes * 60}


def test_six_hundred_parts_may_be_asked_for():
    assert (freebuild.MIN_PARTS, freebuild.MAX_PARTS) == (20, 600)


@pytest.mark.parametrize(
    ("parts", "low", "high", "stop", "dollars", "estimated"),
    [
        (80, 5, 15, 90, [2, 6], False),
        (100, 10, 20, 90, [2, 7], False),
        (206, 20, 40, 90, [4, 14], False),
        (283, 25, 55, 90, [6, 20], False),
        (375, 35, 75, 113, [8, 26], True),
        (600, 55, 120, 180, [12, 42], True),
    ],
)
def test_what_a_person_is_told_before_a_build(parts, low, high, stop, dollars, estimated):
    e = freebuild.estimate(parts)
    assert e == {
        "parts": parts,
        "minutes": [low, high],
        "stop_minutes": stop,
        "dollars": dollars,
        "estimated": estimated,
    }
    said = freebuild.time_and_cost(parts)
    assert f"usually takes {low} to {high} minutes and is stopped at {stop} minutes" in said
    assert f"about ${dollars[0]} to ${dollars[1]} of your Claude subscription" in said
    assert ("an estimate" in said) is estimated
    assert "largest" not in said


def test_the_runs_on_record_fall_in_the_ranges():
    """The builds the words are drawn from (parts, minutes, dollars at list prices)."""
    for parts, minutes, dollars in [
        (71, 5.0, 1.72),
        (84, 8.9, 3.60),
        (84, 14.3, 5.41),
        (95, 16.8, 5.72),
        (96, 18.0, 6.60),
        (156, 15.2, 5.25),
        (206, 35.9, 13.53),
        (283, 25.9, 8.68),
    ]:
        e = freebuild.estimate(parts)
        assert e["minutes"][0] - 5 <= minutes <= e["minutes"][1] + 5, parts
        assert e["dollars"][0] - 1 <= dollars <= e["dollars"][1], parts


def test_progress_says_when_the_builder_writes_its_brief_and_hands_in(tmp_path):
    from bricksnap.designer.runner import TOOL_PREFIX

    said: list[str] = []
    hear = freebuild.Progress(tmp_path, said.append)
    calls = [
        ("brief", GOOD, "Brief 1 recorded."),
        ("submit", {}, "HAND-IN SHEET"),
        ("submit", {"critique": FULL}, "Your critique was not recorded"),
        ("submit", {"critique": FULL}, "Critique recorded: 10 yes, 0 no."),
    ]
    for n, (name, args, reply) in enumerate(calls):
        use = {"type": "tool_use", "id": f"t{n}", "name": TOOL_PREFIX + name, "input": args}
        hear({"type": "assistant", "message": {"content": [use]}})
        done = {
            "type": "tool_result",
            "tool_use_id": f"t{n}",
            "content": [{"type": "text", "text": reply}],
        }
        hear({"type": "user", "message": {"content": [done]}})
    assert said == [
        "The builder is writing its art direction",
        "The builder is looking at its model beside its art direction, to hand it in",
        "The builder is looking at its model beside its art direction, to hand it in",
        "The builder handed in its critique of its own pictures",
    ]
