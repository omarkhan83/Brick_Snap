"""Tests for the best-of-several judge (bricksnap/designer/judge.py and judge_server.py).

No test starts a real AI session: the designer is replaced by a fake that edits each
candidate like the AI would, and the judge's session by a fake that calls the judge's real
tools in-process.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client
from PIL import Image

from bricksnap.designer import judge, runner
from bricksnap.designer.judge import (
    BestOf,
    deal_letters,
    design_best_of,
    judge_candidates,
)
from bricksnap.designer.judge_server import JUDGE_TOOLS, Judging
from bricksnap.designer.runner import DesignerRun
from bricksnap.pipeline import create_project, rebuild, render_compare
from bricksnap.project import Project

BRIEF = {
    "object": "A chess pawn, standing upright.",
    "features": ["a round head", "a wide base"],
    "plan": "Keep the head round.",
    "colours": [71, 4],
    "finish": "Studs everywhere.",
}
# A second block on the ground in a corner of the pawn's grid at 8 studs: two pieces, so the
# build fails its checks.
SPLIT = [{"op": "add", "shape": {"type": "box", "min": [0, 0, 0], "max": [0, 1, 2]}, "color": 4}]


def paint(color: int) -> list[dict]:
    return [
        {
            "op": "paint",
            "shape": {"type": "box", "min": [0, 0, 0], "max": [9, 9, 2]},
            "color": color,
        }
    ]


@pytest.fixture(scope="module")
def built_pawn(tmp_path_factory, pawn_path) -> Path:
    base = tmp_path_factory.mktemp("judge-base")
    project = create_project(pawn_path, studs=8, directory=base)
    rebuild(project)
    render_compare(project)
    return project.path


@pytest.fixture
def pawn(built_pawn, tmp_path) -> Project:
    dest = tmp_path / "work" / "pawn"
    shutil.copytree(built_pawn, dest)
    (dest / "designer").mkdir()
    (dest / "designer" / "old-run.jsonl").write_text("{}\n")
    return Project(dest)


class FakeDesigner:
    """Edits candidate N with ``plans[N]`` (a list of operations, or "fail")."""

    def __init__(self, plans: dict[int, object] | None = None) -> None:
        self.plans = plans or {}
        self.calls: list[tuple[Path, dict]] = []

    def __call__(self, project: Project, **options) -> DesignerRun:
        from bricksnap.catalog import load_catalog
        from bricksnap.design import apply_ops

        number = int(project.path.name)
        self.calls.append((project.path, options))
        plan = self.plans.get(number, paint(4))
        project.meta["brief"] = {**BRIEF, "object": f"A pawn, design {number}."}
        project.save_meta()
        if plan == "fail":
            return DesignerRun(ok=False, error="Claude Code is not installed here.")
        design = project.load_design()
        assert isinstance(plan, list)
        apply_ops(design, plan, load_catalog())
        project.save_design(design)
        if number % 2:  # some runs end with a rebuild, some do not
            rebuild(project)
        return DesignerRun(ok=True, turns=5, final_text=f"Design {number}.")


class FakeJudge:
    """Looks at everything through the real tools and ranks the candidates as told.

    ``prefer`` lists candidate NUMBERS, best first; the fake turns them into letters with
    ``deal_letters``, which the real judge never sees."""

    def __init__(self, prefer: list[int] | None = None, *, ok: bool = True, choose: bool = True):
        self.prefer = prefer
        self.ok = ok
        self.choose = choose
        self.calls: list[dict] = []
        self.texts: list[str] = []

    def __call__(self, folder: Path, letters: list[str], **options) -> DesignerRun:
        self.calls.append({"folder": folder, "letters": list(letters), **options})
        tools = Judging(folder)
        self.texts += [b.get("text", "") for b in tools.call("look", {"candidate": "all"})]
        for letter in letters:
            self.texts += [b.get("text", "") for b in tools.call("look", {"candidate": letter})]
        if self.choose:
            meta = json.loads((folder / "result.json").read_text())  # test-only peek
            to_letter = {c["number"]: c["letter"] for c in meta["candidates"] if c["letter"]}
            order = [to_letter[n] for n in self.prefer] if self.prefer else list(letters)
            reply = tools.call(
                "choose",
                {
                    "ranking": order,
                    "reasons": {x: f"Reason for {x}." for x in order},
                    "summary": "Close call.",
                },
            )
            assert not reply[0]["text"].startswith("ERROR"), reply
        return DesignerRun(ok=self.ok, error="" if self.ok else "The judge stopped.")


@pytest.fixture
def fakes(monkeypatch):
    def install(designer: FakeDesigner, judge_fake: FakeJudge | None = None):
        monkeypatch.setattr(runner, "run_designer", designer)
        judge_fake = judge_fake or FakeJudge()
        monkeypatch.setattr(judge, "run_judge", judge_fake)
        return designer, judge_fake

    return install


def snapshot(path: Path) -> dict[str, bytes]:
    return {
        str(f.relative_to(path)): f.read_bytes()
        for f in sorted(path.rglob("*"))
        if f.is_file() and "candidates" not in f.relative_to(path).parts
    }


# ---- the two tools ----------------------------------------------------------------------------


def test_exactly_two_tools_as_plain_json():
    assert [t["name"] for t in JUDGE_TOOLS] == ["look", "choose"]
    assert json.loads(json.dumps(JUDGE_TOOLS)) == JUDGE_TOOLS
    look, choose = JUDGE_TOOLS
    assert look["input_schema"]["required"] == ["candidate"]
    assert set(choose["input_schema"]["required"]) == {"ranking", "reasons", "summary"}
    for tool in JUDGE_TOOLS:
        assert tool["input_schema"]["additionalProperties"] is False
        assert len(tool["description"]) > 100


def prepared(pawn: Project, fakes, n: int = 3) -> BestOf:
    """Design n candidates and judge them with the fake judge; returns the result."""
    fakes(FakeDesigner({1: paint(4), 2: paint(1), 3: paint(14)}))
    return design_best_of(pawn, n)


def test_look_all_and_look_one(pawn: Project, fakes):
    prepared(pawn, fakes)
    folder = pawn.path / "candidates"
    tools = Judging(folder)
    letters = json.loads((folder / "judging" / "judging.json").read_text())["letters"]
    assert letters == ["A", "B", "C"]

    image, text = tools.call("look", {"candidate": "all"})
    assert image["type"] == "image" and image["media_type"] == "image/png"
    sheet = Image.open(io.BytesIO(base64.b64decode(image["data"])))
    assert sheet.width <= 1568 and sheet.height <= 1568
    assert "A, B and C" in text["text"]

    image, text = tools.call("look", {"candidate": "B"})
    assert image["type"] == "image"
    words = text["text"]
    assert "Candidate B" in words and "Top row: the seed" in words
    assert "Facts about B:" in words and "parts" in words and "weak spot" in words
    assert "Still to look at on their own: A and C." in words


def test_look_mistakes_are_errors_that_say_what_to_fix(pawn: Project, fakes):
    prepared(pawn, fakes)
    tools = Judging(pawn.path / "candidates")
    cases = [
        ("look", {"candidate": "D"}, "there is no candidate"),
        ("look", {"candidate": 3}, "as text"),
        ("look", {}, '"candidate"'),
        ("look", {"candidate": "A", "zoom": 2}, "only"),
        ("look", ["A"], "JSON object"),
        ("explode", {}, "no tool called"),
    ]
    for name, args, words in cases:
        reply = tools.call(name, args)
        assert len(reply) == 1 and reply[0]["text"].startswith("ERROR:"), (name, args)
        assert words in reply[0]["text"], (name, args, reply)


def test_choose_checks_everything_and_records_nothing_until_right(pawn: Project, fakes):
    prepared(pawn, fakes)
    folder = pawn.path / "candidates"
    verdict = folder / "judging" / "verdict.json"
    verdict.unlink(missing_ok=True)
    tools = Judging(folder)
    good = {
        "ranking": ["B", "A", "C"],
        "reasons": {"A": "a", "B": "b", "C": "c"},
        "summary": "B reads best.",
    }

    reply = tools.call("choose", good)[0]["text"]
    assert reply.startswith("ERROR:") and "not looked at A, B and C" in reply
    assert not verdict.exists()
    for letter in "ABC":
        tools.call("look", {"candidate": letter})

    bad_cases = [
        ({**good, "ranking": ["B", "A"]}, "leaves out C"),
        ({**good, "ranking": ["B", "A", "C", "B"]}, "more than once"),
        ({**good, "ranking": ["B", "A", "D"]}, "not a candidate"),
        ({**good, "ranking": "B, A, C"}, "must be a list"),
        ({**good, "reasons": {"A": "a", "B": "b"}}, "no reason for C"),
        ({**good, "reasons": {"A": "a", "B": "b", "C": " "}}, "reason for C"),
        ({**good, "reasons": {"A": "a", "B": "b", "C": "c", "D": "d"}}, "not a candidate"),
        ({**good, "reasons": "all fine"}, "must be an object"),
        ({**good, "summary": ""}, '"summary"'),
        ({**good, "winner": "B"}, "not part of the verdict"),
        ({"ranking": ["B", "A", "C"]}, 'missing: "reasons", "summary"'),
        ({**good, "reasons": {"A": "x" * 5000, "B": "b", "C": "c"}}, "characters"),
    ]
    for args, words in bad_cases:
        reply = tools.call("choose", args)
        text = reply[0]["text"]
        assert len(reply) == 1 and text.startswith("ERROR:"), args
        assert words in text, (args, text)
        assert len(text) < 2000
        assert not verdict.exists()

    reply = tools.call("choose", good)[0]["text"]
    assert reply.startswith("Verdict recorded. B, then A, then C.")
    assert json.loads(verdict.read_text()) == {
        "ranking": ["B", "A", "C"],
        "reasons": {"B": "b", "A": "a", "C": "c"},
        "summary": "B reads best.",
    }


@pytest.mark.parametrize(
    "args",
    [
        None,
        [],
        "all",
        {"candidate": None},
        {"candidate": ["A"]},
        {"candidate": {"a": 1}},
        {"candidate": "x" * 100_000},
        {"ranking": None, "reasons": None, "summary": None},
        {"ranking": [None, 1, {}, []], "reasons": {"A": 5, "": None}, "summary": 10**400},
        {"ranking": ["A"] * 1000, "reasons": {str(i): "r" for i in range(1000)}, "summary": "s"},
    ],
)
@pytest.mark.parametrize("name", ["look", "choose", None, 5])
def test_nothing_the_model_sends_makes_a_tool_raise(pawn: Project, fakes, name, args):
    prepared(pawn, fakes, n=2)
    reply = Judging(pawn.path / "candidates").call(name, args)
    assert isinstance(reply, list) and reply
    for block in reply:
        if block["type"] == "text":
            assert len(block["text"]) < 3000


def test_a_look_whose_picture_could_not_be_shown_does_not_count(pawn: Project, fakes):
    prepared(pawn, fakes)
    folder = pawn.path / "candidates"
    (folder / "judging" / "A.png").write_bytes(b"not a picture")
    (folder / "judging" / "B.png").unlink()
    tools = Judging(folder)
    for letter in "ABC":
        reply = tools.call("look", {"candidate": letter})
        assert reply[0]["type"] == ("image" if letter == "C" else "text"), letter
    (folder / "judging" / "verdict.json").unlink(missing_ok=True)
    reply = tools.call(
        "choose",
        {"ranking": ["B", "A", "C"], "reasons": {x: "r" for x in "ABC"}, "summary": "s"},
    )[0]["text"]
    assert reply.startswith("ERROR:") and "not looked at A and B" in reply
    assert not (folder / "judging" / "verdict.json").exists()


def test_a_folder_with_nothing_to_judge_says_so(tmp_path: Path):
    reply = Judging(tmp_path).call("look", {"candidate": "all"})
    assert reply[0]["text"].startswith("ERROR: there are no candidates to judge")
    assert "none of your tools can fix it" in reply[0]["text"]
    (tmp_path / "judging").mkdir()
    (tmp_path / "judging" / "judging.json").write_text("not json")
    reply = Judging(tmp_path).call("choose", {})
    assert reply[0]["text"].startswith("ERROR:") and "could not be read" in reply[0]["text"]


def test_no_text_for_the_judge_holds_a_path_or_a_candidate_number(
    pawn: Project, fakes, monkeypatch
):
    monkeypatch.setenv("HOME", str(pawn.path.parent))
    _, fake = fakes(FakeDesigner(), FakeJudge())
    design_best_of(pawn, 3)
    message = judge.judge_message(["A", "B", "C"])
    for text in [*fake.texts, message]:
        assert str(pawn.path.parent) not in text
        assert "candidates/" not in text and "pawn" not in text.lower()
    # what the judge's tools read holds letters and facts only
    setup = json.loads((pawn.path / "candidates" / "judging" / "judging.json").read_text())
    assert set(setup) == {"letters", "facts"}
    assert "design 1" not in json.dumps(setup).lower()


# ---- the server -------------------------------------------------------------------------------


def test_server_lists_the_two_tools_and_answers(pawn: Project, fakes):
    prepared(pawn, fakes, n=2)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "bricksnap.designer.judge_server", str(pawn.path / "candidates")],
    )

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            calls = [
                ("look", {"candidate": "all"}),
                ("look", {"candidate": "A"}),
                ("look", {"candidate": "B"}),
                (
                    "choose",
                    {"ranking": ["B", "A"], "reasons": {"A": "a", "B": "b"}, "summary": "s"},
                ),
                ("look", {"candidate": "Z"}),
            ]
            return listed.tools, [await session.call_tool(n, a) for n, a in calls]

    tools, results = anyio.run(go)
    assert [t.name for t in tools] == ["look", "choose"]
    for listed, ours in zip(tools, JUDGE_TOOLS, strict=True):
        assert listed.description == ours["description"]
        assert listed.input_schema == ours["input_schema"]
    every, a, b, chosen, wrong = results
    assert [c.type for c in every.content] == ["image", "text"]
    assert [c.type for c in a.content] == ["image", "text"] and not a.is_error
    assert not chosen.is_error and chosen.content[0].text.startswith("Verdict recorded")
    assert wrong.is_error and wrong.content[0].text.startswith("ERROR:")


def test_server_refuses_a_folder_without_candidates(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, "-m", "bricksnap.designer.judge_server", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2 and proc.stdout == ""
    assert "no candidates" in proc.stderr


# ---- design_best_of ---------------------------------------------------------------------------


def test_n_must_be_two_to_five(pawn: Project, fakes):
    fakes(FakeDesigner())
    for n in (0, 1, 6):
        with pytest.raises(ValueError, match="2 to 5"):
            design_best_of(pawn, n)
    assert not (pawn.path / "candidates").exists()


def test_candidates_are_copies_designed_one_after_another(pawn: Project, fakes):
    old = pawn.path / "candidates" / "9"
    old.mkdir(parents=True)
    designer, _ = fakes(FakeDesigner())
    events: list[dict] = []
    design_best_of(
        pawn, 3, instruction="make it red", model="m", effort="low", on_event=events.append
    )
    assert not old.exists()  # an older candidates folder is removed first
    assert [p.name for p, _ in designer.calls] == ["1", "2", "3"]
    for path, options in designer.calls:
        assert options == {"instruction": "make it red", "model": "m", "effort": "low"}
        # what was copied: the project as it was, not its transcripts, pictures or candidates
        for name in ("project.json", "seed.stl", "design.base.npz", "design.npz", "design.json"):
            assert (path / name).is_file(), name
    first = pawn.path / "candidates" / "1"
    assert not (first / "candidates").exists()
    assert not (first / "designer" / "old-run.jsonl").exists()
    kinds = [e["event"] for e in events]
    assert kinds[:6] == ["designing", "designed"] * 3
    assert "judging" in kinds and kinds[-1] == "kept"
    assert events[0]["candidate"] == 1 and events[0]["of"] == 3


def test_the_judges_first_choice_is_kept(pawn: Project, fakes):
    _, fake = fakes(
        FakeDesigner({1: paint(4), 2: paint(1), 3: paint(14)}), FakeJudge(prefer=[2, 3, 1])
    )
    result = design_best_of(pawn, 3, model="m", effort="low")
    assert result.error == "" and not result.by_measurement
    assert result.winner == 2 and result.ranking == [2, 3, 1]
    assert set(result.reasons) == {1, 2, 3} and result.summary == "Close call."
    assert len(result.runs) == 3 and result.judge is not None and result.judge.ok
    assert fake.calls[0]["model"] == "m" and fake.calls[0]["effort"] == "low"

    project = Project(pawn.path)
    assert project.meta["brief"]["object"] == "A pawn, design 2."
    assert project.build_is_current()
    assert any(p.color == 1 for p in project.load_build().parts)
    assert not any(p.color in (4, 14) for p in project.load_build().parts)
    winner = pawn.path / "candidates" / "2"
    assert (pawn.path / "design.npz").read_bytes() == (winner / "design.npz").read_bytes()
    assert (pawn.path / "design.json").read_bytes() == (winner / "design.json").read_bytes()
    assert (pawn.path / "build.ldr").read_bytes() == (winner / "build.ldr").read_bytes()
    assert (pawn.path / "renders" / "compare.png").read_bytes() == (
        winner / "renders" / "compare.png"
    ).read_bytes()
    assert (pawn.path / "designer" / "old-run.jsonl").exists()  # earlier records stay

    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    assert saved["winner"] == 2 and saved["by_measurement"] is False
    assert saved["summary"] == "Close call."
    rows = {c["number"]: c for c in saved["candidates"]}
    assert sorted(rows) == [1, 2, 3]
    for n, row in rows.items():
        assert row["valid"] is True and row["why_not_valid"] == ""
        assert row["letter"] in "ABC" and row["parts"] > 0 and "weak_spots" in row
        assert row["rank"] == [2, 3, 1].index(n) + 1
        assert row["reason"] == f"Reason for {row['letter']}."
    assert sorted(r["letter"] for r in rows.values()) == ["A", "B", "C"]


def test_letters_are_dealt_by_a_repeatable_shuffle():
    first = deal_letters("cat", 3, [1, 2, 3])
    assert first == deal_letters("cat", 3, [1, 2, 3])
    assert sorted(first) == ["A", "B", "C"] and sorted(first.values()) == [1, 2, 3]
    shuffles = {tuple(deal_letters(name, 4, [1, 2, 3, 4]).values()) for name in "abcdefgh"}
    assert len(shuffles) > 1  # not simply in order
    # only the valid candidates get letters, still A, B, ...
    assert sorted(deal_letters("cat", 4, [1, 3])) == ["A", "B"]


def test_a_candidate_that_failed_cannot_win_and_is_not_shown(pawn: Project, fakes):
    _, fake = fakes(FakeDesigner({1: "fail", 2: SPLIT, 3: paint(1), 4: paint(14)}))
    result = design_best_of(pawn, 4)
    assert fake.calls[0]["letters"] == ["A", "B"]
    assert result.winner in (3, 4) and set(result.ranking) == {3, 4}
    rows = {
        c["number"]: c
        for c in json.loads((pawn.path / "candidates" / "result.json").read_text())["candidates"]
    }
    assert rows[1]["valid"] is False and "not installed" in rows[1]["why_not_valid"]
    assert rows[2]["valid"] is False and "checks" in rows[2]["why_not_valid"]
    assert rows[1]["letter"] is None and rows[1]["rank"] is None
    assert (pawn.path / "candidates" / "2" / "design.npz").exists()  # losers stay on disk


def test_a_single_valid_candidate_wins_without_a_judge(pawn: Project, fakes):
    _, fake = fakes(FakeDesigner({1: SPLIT, 2: paint(1), 3: "fail"}))
    result = design_best_of(pawn, 3)
    assert fake.calls == [] and result.judge is None
    assert result.winner == 2 and result.ranking == [2] and not result.by_measurement
    assert Project(pawn.path).build_is_current()
    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    assert saved["winner"] == 2 and "only" in saved["note"]


def test_no_valid_candidate_leaves_the_project_exactly_as_it_was(pawn: Project, fakes):
    before = snapshot(pawn.path)
    _, fake = fakes(FakeDesigner({1: "fail", 2: SPLIT}))
    result = design_best_of(pawn, 2)
    assert result.winner is None and result.ranking == []
    assert "None of the 2 designs" in result.error
    assert fake.calls == []
    assert snapshot(pawn.path) == before
    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    assert saved["winner"] is None and saved["error"] == result.error


@pytest.mark.parametrize(
    "fake", [FakeJudge(ok=False), FakeJudge(choose=False)], ids=["failed", "no-verdict"]
)
def test_without_a_verdict_the_winner_is_chosen_by_measurement(pawn: Project, fakes, fake):
    fakes(FakeDesigner({1: paint(4), 2: paint(1), 3: paint(14)}), fake)
    result = design_best_of(pawn, 3)
    assert result.by_measurement
    # the three differ only in colour, so their outlines match the seed equally: ties go to
    # the lowest number
    assert result.winner == 1 and result.ranking == [1, 2, 3]
    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    assert saved["by_measurement"] is True and "measurement" in saved["note"]
    assert all("outline" in c["reason"] for c in saved["candidates"])
    assert Project(pawn.path).build_is_current()


def test_measurement_prefers_the_closer_outline(pawn: Project, fakes):
    shrink = [{"op": "remove", "shape": {"type": "box", "min": [0, 0, 12], "max": [9, 9, 25]}}]
    fakes(FakeDesigner({1: shrink, 2: paint(1)}), FakeJudge(ok=False))
    result = design_best_of(pawn, 2)
    assert result.by_measurement and result.winner == 2


def test_a_failure_while_keeping_the_winner_leaves_the_project_as_it_was(
    pawn: Project, fakes, monkeypatch
):
    before = snapshot(pawn.path)
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[2, 1]))
    real_move = judge._move
    moves = {"n": 0}

    def flaky(src, dst):
        moves["n"] += 1
        if moves["n"] == 3:
            raise OSError(28, "No space left on device")
        return real_move(src, dst)

    monkeypatch.setattr(judge, "_move", flaky)
    with pytest.raises(OSError):
        design_best_of(pawn, 2)
    assert snapshot(pawn.path) == before
    assert not list(pawn.path.glob(".best-of-*"))


def test_judge_again_uses_the_candidates_on_disk(pawn: Project, fakes):
    designer, _ = fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[1, 2]))
    assert design_best_of(pawn, 2).winner == 1
    designer.calls.clear()
    _, fake = fakes(designer, FakeJudge(prefer=[2, 1]))
    result = judge_candidates(pawn)
    assert designer.calls == [] and len(fake.calls) == 1
    assert result.winner == 2 and result.runs == []
    assert any(p.color == 1 for p in Project(pawn.path).load_build().parts)
    assert json.loads((pawn.path / "candidates" / "result.json").read_text())["winner"] == 2


def test_judge_again_without_candidates_says_so(pawn: Project, fakes):
    fakes(FakeDesigner())
    result = judge_candidates(pawn)
    assert result.winner is None and "no candidates" in result.error


# ---- review fixes: keeping the winner survives a process that dies ---------------------------

DIE_AT_MOVE = """
import os, sys
from pathlib import Path
from bricksnap.designer import judge
from bricksnap.project import Project

project, winner, k, when = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4]
real, count = judge._move, [0]

def dying(src, dst):
    count[0] += 1
    if count[0] == k and when == "before":
        os._exit(9)
    real(src, dst)
    if count[0] == k and when == "after":
        os._exit(9)

judge._move = dying
judge._keep(Project(project), project / "candidates" / winner)
"""


def die_while_keeping(project: Path, winner: int, k: int, when: str = "before") -> int:
    proc = subprocess.run(
        [sys.executable, "-c", DIE_AT_MOVE, str(project), str(winner), str(k), when],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return proc.returncode


def winner_files(project: Path, number: int) -> dict[str, bytes]:
    winner = project / "candidates" / str(number)
    return {
        name: (winner / name).read_bytes()
        for name in ("design.npz", "design.json", "build.json", "build.ldr", "renders/compare.png")
    }


@pytest.mark.parametrize("k", [1, 2, 3, 4, 5, 6])
def test_a_process_killed_during_the_moves_is_put_back_on_the_next_open(
    pawn: Project, fakes, k: int
):
    # the winner has six files to move: design.npz, design.json, build.json, build.ldr,
    # renders/compare.png and project.json
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[1, 2]))
    design_best_of(pawn, 2)
    before = snapshot(pawn.path)
    assert die_while_keeping(pawn.path, 2, k) == 9  # it died at move k, before making it
    assert snapshot(pawn.path) != before or k == 1  # half replaced (or not yet started)
    assert judge.recover(pawn.path) is True
    assert snapshot(pawn.path) == before
    assert not list(pawn.path.glob(".best-of-*"))
    assert judge.recover(pawn.path) is False  # nothing more to do
    # and a normal keep afterwards still works
    judge._keep(Project(pawn.path), pawn.path / "candidates" / "2")
    project = Project(pawn.path)
    assert project.build_is_current()
    for name, data in winner_files(pawn.path, 2).items():
        assert (pawn.path / name).read_bytes() == data, name


def test_a_process_killed_after_the_last_move_leaves_a_whole_project(pawn: Project, fakes):
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[1, 2]))
    design_best_of(pawn, 2)
    before = snapshot(pawn.path)
    assert die_while_keeping(pawn.path, 2, 6, when="after") == 9
    judge.recover(pawn.path)
    after = snapshot(pawn.path)
    assert not list(pawn.path.glob(".best-of-*"))
    whole_winner = all(
        (pawn.path / name).read_bytes() == data for name, data in winner_files(pawn.path, 2).items()
    )
    assert after == before or (whole_winner and Project(pawn.path).build_is_current())


def test_the_next_best_of_puts_an_interrupted_keep_back_first(pawn: Project, fakes):
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[1, 2]))
    design_best_of(pawn, 2)
    before = snapshot(pawn.path)
    assert die_while_keeping(pawn.path, 2, 3) == 9
    # judging again starts by putting the project back, so its check of the project's design
    # sees the design as it was, and the new winner is kept whole
    fakes(FakeDesigner(), FakeJudge(prefer=[2, 1]))
    result = judge_candidates(pawn)
    assert result.winner == 2, result.error
    assert not list(pawn.path.glob(".best-of-*"))
    assert Project(pawn.path).build_is_current()
    assert snapshot(pawn.path) != before


def test_leftovers_from_a_keep_that_never_started_moving_are_removed(pawn: Project):
    before = snapshot(pawn.path)
    for name in (".best-of-staging", ".best-of-backup"):
        (pawn.path / name).mkdir()
        (pawn.path / name / "design.npz").write_bytes(b"half copied")
    assert judge.recover(pawn.path) is False  # nothing had been moved, so nothing to put back
    assert not list(pawn.path.glob(".best-of-*"))
    assert snapshot(pawn.path) == before


def test_when_putting_back_fails_too_the_backup_is_kept_for_later(
    pawn: Project, fakes, monkeypatch
):
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[1, 2]))
    design_best_of(pawn, 2)
    before = snapshot(pawn.path)
    real_move = judge._move
    moves = {"n": 0}

    def flaky(src, dst):
        moves["n"] += 1
        if moves["n"] in (4, 5):  # move 4 fails, and so does the first move putting it back
            raise OSError(28, "No space left on device")
        return real_move(src, dst)

    monkeypatch.setattr(judge, "_move", flaky)
    with pytest.raises(OSError, match="put back"):
        judge._keep(Project(pawn.path), pawn.path / "candidates" / "2")
    assert (pawn.path / ".best-of-backup" / "manifest.json").is_file()  # not thrown away
    monkeypatch.setattr(judge, "_move", real_move)
    assert judge.recover(pawn.path) is True
    assert snapshot(pawn.path) == before


# ---- review fixes: the judge's own session, and what each letter stands for -------------------

FAKE_CLAUDE = r"""#!{python}
import json, os, sys
argv = sys.argv[1:]
cfg = json.load(open(argv[argv.index("--mcp-config") + 1]))
json.dump({{"argv": argv, "mcp": cfg, "stdin": sys.stdin.read()}}, open(os.environ["RECORD"], "w"))
for line in json.loads(os.environ["LINES"]):
    print(line, flush=True)
"""

JUDGE_INIT = {
    "type": "system",
    "subtype": "init",
    "tools": ["mcp__bricksnap__look", "mcp__bricksnap__choose"],
    "mcp_servers": [{"name": "bricksnap", "status": "connected"}],
    "model": "claude-opus-5-5",
    "apiKeySource": "none",
}


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch):
    import os
    import stat

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "claude"
    exe.write_text(FAKE_CLAUDE.format(python=sys.executable))
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    record = tmp_path / "record.json"
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    monkeypatch.setenv("RECORD", str(record))

    def configure(result: dict) -> Path:
        lines = [json.dumps(JUDGE_INIT), json.dumps(result)]
        monkeypatch.setenv("LINES", json.dumps(lines))
        return record

    return configure


def test_the_real_run_judge_starts_the_judges_own_session(fake_claude, tmp_path: Path):
    folder = tmp_path / "candidates"
    folder.mkdir()
    record = fake_claude(
        {"type": "result", "subtype": "success", "is_error": False, "num_turns": 6, "result": "B."}
    )
    run = judge.run_judge(folder, ["A", "B", "C"], model="claude-opus-5-5", effort="low")
    assert run.ok, run.error
    assert run.kind == "judging"
    assert run.transcript is not None and run.transcript.parent == folder / "judging"
    seen = json.loads(record.read_text())
    argv = seen["argv"]
    prompt = Path(argv[argv.index("--system-prompt-file") + 1])
    config = Path(argv[argv.index("--mcp-config") + 1])
    assert prompt == judge.JUDGE_PROMPT_FILE.resolve()
    assert (
        argv
        == runner.build_command(
            prompt, config, model="claude-opus-5-5", effort="low", max_turns=judge.JUDGE_MAX_TURNS
        )[1:]
    )
    server = seen["mcp"]["mcpServers"]["bricksnap"]
    assert server["args"] == ["-m", "bricksnap.designer.judge_server", str(folder.resolve())]
    assert seen["stdin"] == judge.judge_message(["A", "B", "C"])


def test_the_judges_errors_are_in_the_judges_words(fake_claude, tmp_path: Path):
    fake_claude({"type": "result", "subtype": "error_max_turns", "is_error": True})
    run = judge.run_judge(tmp_path, ["A", "B"])
    assert not run.ok and run.kind == "judging"
    assert (
        run.error
        == f"The judge used all its turns ({judge.JUDGE_MAX_TURNS}) before it gave its verdict."
    )
    assert "edits" not in run.error


# The pawn's top part: removing it from z 18 or z 12 up gives candidates with fewer parts.
def chop(z: int) -> list[dict]:
    return [{"op": "remove", "shape": {"type": "box", "min": [0, 0, z], "max": [9, 9, 30]}}]


def test_each_letter_shows_the_candidate_it_stands_for(pawn: Project, fakes):
    from bricksnap import pipeline
    from bricksnap.bench import VIEWS, outline_match
    from bricksnap.catalog import load_catalog

    fakes(FakeDesigner({1: paint(4), 2: chop(18), 3: chop(12)}), FakeJudge(prefer=[3, 1, 2]))
    result = design_best_of(pawn, 3)
    folder = pawn.path / "candidates"
    saved = json.loads((folder / "result.json").read_text())
    letters = {c["letter"]: c["number"] for c in saved["candidates"]}
    # the letters come from the seeded shuffle, which for this project is not simply in order
    assert letters == deal_letters("pawn", 3, [1, 2, 3])
    assert letters != {"A": 1, "B": 2, "C": 3}
    setup = json.loads((folder / "judging" / "judging.json").read_text())
    catalog = load_catalog()
    parts = set()
    for letter, number in letters.items():
        cand = Project(folder / str(number))
        assert (folder / "judging" / f"{letter}.png").read_bytes() == (
            cand.renders_dir / "compare.png"
        ).read_bytes(), letter
        build = cand.load_build()
        parts.add(len(build.parts))
        assert setup["facts"][letter].startswith(f"{len(build.parts)} parts;"), letter
        # the measurement is the mean over the front, the right side and the top
        design, seed = cand.load_design(), pipeline.load_project_seed(cand)
        views = [outline_match(seed, build, catalog, v, design.seed_offset) for v in VIEWS]
        assert len(VIEWS) == 3
        row = next(c for c in saved["candidates"] if c["number"] == number)
        assert row["outline_match"] == round(sum(views) / 3, 4)
    assert len(parts) == 3  # the three differ, so a mix-up would show
    assert result.winner == 3


# ---- review fixes: faults while designing or judging ---------------------------------------


def test_a_designer_run_that_raises_counts_as_failed_and_the_others_go_on(pawn: Project, fakes):
    designer = FakeDesigner({1: paint(4), 2: paint(1), 3: paint(14)})

    def flaky(project: Project, **options) -> DesignerRun:
        if project.path.name == "2":
            raise RuntimeError("the tool server fell over")
        return designer(project, **options)

    fakes(flaky, FakeJudge())
    result = design_best_of(pawn, 3)
    assert [r.ok for r in result.runs] == [True, False, True]
    assert "fell over" in result.runs[1].error
    assert result.winner in (1, 3)
    rows = {
        c["number"]: c
        for c in json.loads((pawn.path / "candidates" / "result.json").read_text())["candidates"]
    }
    assert rows[2]["valid"] is False and "fell over" in rows[2]["why_not_valid"]


def test_progress_output_that_raises_never_stops_the_work(pawn: Project, fakes):
    fakes(FakeDesigner(), FakeJudge())

    def broken(event: dict) -> None:
        raise ValueError("the terminal went away")

    result = design_best_of(pawn, 2, on_event=broken)
    assert result.winner in (1, 2) and result.error == ""


class RaisingJudge:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __call__(self, folder: Path, letters: list[str], **options) -> DesignerRun:
        raise self.error


def test_a_judge_that_raises_means_the_winner_is_chosen_by_measurement(pawn: Project, fakes):
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), RaisingJudge(RuntimeError("could not start")))
    result = design_best_of(pawn, 2)
    assert result.by_measurement and result.winner == 1
    assert result.judge is not None and not result.judge.ok
    assert result.judge.kind == "judging" and "could not start" in result.judge.error
    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    assert saved["status"] == "done" and saved["by_measurement"] is True
    assert "could not start" in saved["note"]
    assert Project(pawn.path).build_is_current()


def test_a_fault_preparing_the_pictures_means_measurement_too(pawn: Project, fakes, monkeypatch):
    _, fake = fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge())

    def broken(*args, **kwargs):
        raise MemoryError("the sheet is too big")

    monkeypatch.setattr(judge, "all_sheet", broken)
    result = design_best_of(pawn, 2)
    assert fake.calls == []  # the judge never ran
    assert result.by_measurement and result.winner == 1
    assert (
        "sheet is too big"
        in json.loads((pawn.path / "candidates" / "result.json").read_text())["note"]
    )


def test_ctrl_c_while_judging_is_not_swallowed(pawn: Project, fakes):
    before = snapshot(pawn.path)
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), RaisingJudge(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        design_best_of(pawn, 2)
    assert snapshot(pawn.path) == before


# ---- review fixes: the judge's words are cleaned before anyone sees them ---------------------


class LeakyJudge(FakeJudge):
    """Ranks in letter order, with reasons holding an address, a home path and an escape."""

    def __init__(self, home: Path) -> None:
        super().__init__()
        self.home = home

    def __call__(self, folder: Path, letters: list[str], **options) -> DesignerRun:
        tools = Judging(folder)
        for letter in letters:
            tools.call("look", {"candidate": letter})
        leak = f"someone@example.com saw {self.home}/secret \x1b[31mred\x1b[0m"
        reply = tools.call(
            "choose",
            {
                "ranking": list(letters),
                "reasons": {x: f"{x}: {leak}" for x in letters},
                "summary": f"Summary: {leak}",
            },
        )
        assert reply[0]["text"].startswith("Verdict recorded"), reply
        return DesignerRun(ok=True)


def test_the_judges_reasons_are_redacted_before_they_are_shown_or_saved(
    pawn: Project, fakes, monkeypatch
):
    home = pawn.path.parent
    monkeypatch.setenv("HOME", str(home))
    fakes(FakeDesigner(), LeakyJudge(home))
    result = design_best_of(pawn, 2)
    texts = [*result.reasons.values(), result.summary]
    saved = (pawn.path / "candidates" / "result.json").read_text()
    verdict = (pawn.path / "candidates" / "judging" / "verdict.json").read_text()
    for text in [*texts, saved, verdict]:
        assert "someone@example.com" not in text
        assert str(home) not in text
        assert "\x1b" not in text and "\\u001b" not in text
    assert all("<account email>" in t and "~/secret" in t for t in texts)


# ---- review fixes: judging again only judges designs that were finished -----------------------


class StoppingDesigner(FakeDesigner):
    """Designs like FakeDesigner, but Ctrl+C is pressed during design ``stop_at``."""

    def __init__(self, stop_at: int) -> None:
        super().__init__()
        self.stop_at = stop_at

    def __call__(self, project: Project, **options) -> DesignerRun:
        if int(project.path.name) == self.stop_at:
            raise KeyboardInterrupt
        return super().__call__(project, **options)


def test_designs_stopped_by_ctrl_c_are_recorded_and_never_judged_as_finished(pawn: Project, fakes):
    before = snapshot(pawn.path)
    fakes(StoppingDesigner(stop_at=1))
    with pytest.raises(KeyboardInterrupt):
        design_best_of(pawn, 2)
    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    assert saved["status"] == "designing"
    assert all(c["run_finished"] is False for c in saved["candidates"])
    _, fake = fakes(FakeDesigner(), FakeJudge())
    result = judge_candidates(pawn)
    assert fake.calls == [] and result.winner is None
    assert "None of the 2 designs" in result.error and "never finished" in result.error
    assert snapshot(pawn.path) == before


def test_the_record_is_updated_after_each_design(pawn: Project, fakes):
    fakes(StoppingDesigner(stop_at=2))
    with pytest.raises(KeyboardInterrupt):
        design_best_of(pawn, 3)
    saved = json.loads((pawn.path / "candidates" / "result.json").read_text())
    rows = {c["number"]: c for c in saved["candidates"]}
    assert rows[1]["run_finished"] is True and rows[1]["run_ok"] is True
    assert rows[2]["run_finished"] is False and rows[3]["run_finished"] is False


def test_judge_again_keeps_a_failed_run_out(pawn: Project, fakes):
    fakes(FakeDesigner({1: "fail", 2: paint(1), 3: paint(14)}), FakeJudge())
    design_best_of(pawn, 3)
    _, fake = fakes(FakeDesigner(), FakeJudge())
    result = judge_candidates(pawn)
    assert fake.calls[0]["letters"] == ["A", "B"]  # design 1 is still not shown
    assert result.winner in (2, 3)
    rows = {
        c["number"]: c
        for c in json.loads((pawn.path / "candidates" / "result.json").read_text())["candidates"]
    }
    assert rows[1]["valid"] is False and "not installed" in rows[1]["why_not_valid"]


def test_judge_again_never_uses_the_old_verdict(pawn: Project, fakes):
    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[2, 1]))
    assert design_best_of(pawn, 2).winner == 2
    assert (pawn.path / "candidates" / "judging" / "verdict.json").exists()
    fakes(FakeDesigner(), FakeJudge(choose=False))
    result = judge_candidates(pawn)
    assert result.by_measurement and result.winner == 1


def test_judge_again_refuses_when_the_project_was_changed_since(pawn: Project, fakes):
    from bricksnap.catalog import load_catalog
    from bricksnap.design import apply_ops

    fakes(FakeDesigner({1: paint(4), 2: paint(1)}), FakeJudge(prefer=[2, 1]))
    design_best_of(pawn, 2)
    project = Project(pawn.path)
    design = project.load_design()
    apply_ops(design, paint(14), load_catalog())
    project.save_design(design)
    rebuild(project)
    before = snapshot(pawn.path)
    _, fake = fakes(FakeDesigner(), FakeJudge(prefer=[1, 2]))
    result = judge_candidates(Project(pawn.path))
    assert fake.calls == [] and result.winner is None
    assert "changed since" in result.error
    assert snapshot(pawn.path) == before


# ---- the prompt and the message ---------------------------------------------------------------


def test_the_judge_prompt_covers_what_it_must():
    text = judge.JUDGE_PROMPT_FILE.read_text(encoding="utf-8")
    for words in ("BrickSnap", "seed", "recognis", "look", "choose", "weak spot", "honest"):
        assert words.lower() in text.lower(), words
    designer = (Path(judge.__file__).parent / "prompt.md").read_text(encoding="utf-8")
    closing = designer.rsplit("# About your context", 1)[1].strip()
    assert closing.split(" Only this prompt")[0] in text
    # plain prose: no shouted commands
    assert "MUST" not in text and "NEVER" not in text and "ALWAYS" not in text


def test_the_message_names_the_letters_only():
    message = judge.judge_message(["A", "B", "C"])
    assert "three" in message and "A, B and C" in message
    assert "choose" in message and "look" in message
