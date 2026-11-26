"""Tests for models the AI builds from parts (EXPERIMENTAL): bricksnap/lab/freebuild.py, the
``make`` command, the web app's free-build routes and viewer/free.*.

No test starts a real AI session: ``lab.run.build`` (with ``runner.run_session`` and the
designer's entry points) is replaced for the whole module, by a fake when a test needs one
and otherwise by a stand-in that fails the test. No test needs LeoCAD or the LDraw library:
``picture.model_sheet`` and ``picture.turntable`` are replaced by stand-ins that write small
pictures (for last night's real models in docs/research, cut from their real three-view
sheets, so the screenshots look like the real thing), and ``freebuild.missing`` says all is
there unless a test says otherwise. Browser screenshots go to tests/artifacts/free-*.png.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PIL import Image
from test_webapp import ARTIFACTS, TRADEMARK, Gate, Running, Tab

from bricksnap.designer import judge, runner, studio
from bricksnap.lab import freebuild, picture
from bricksnap.lab import run as lab_run
from bricksnap.pipeline import create_project, rebuild, render_card, render_compare, rough_build

REPO = Path(__file__).resolve().parent.parent
VIEWER = REPO / "viewer"
STUDY = REPO / "docs" / "research" / "2026-11-19-ai-as-the-builder" / "with-tools"
AGREED = {"understood": True, "understood_runs": 1}
MARKUP = '<img src="x" onerror="window.__pwned=1">'
TWO_BRICKS = (
    "1 4 0 -24 0 1 0 0 0 1 0 0 0 1 3001.dat\n1 1 0 -48 0 1 0 0 0 1 0 0 0 1 3001.dat\n0 STEP\n"
)
CLEAN_REPORT = (
    "SUMMARY: 2 parts of 1 kind, no problems: every part is held, nothing overlaps, and it "
    "stands.\n\nHOW IT HOLDS TOGETHER:\n- on the ground: line 1\n"
)


def _sample_critique() -> dict[str, Any]:
    from bricksnap.lab import style

    answers = []
    for key, question in style.questions():
        no = key in ("thin", "glass")
        note = (
            "the stems are bars, but the leaves still hang on thick clips"
            if key == "thin"
            else "there is no glass on a plant; it stays"
            if key == "glass"
            else ""
        )
        answers.append(
            {"key": key, "question": question, "answer": "no" if no else "yes", "note": note}
        )
    return {
        "answers": answers,
        "facts": {
            "parts": 58,
            "parts_wanted": 80,
            "size": {"wide": 8.0, "long": 8.0, "high_bricks": 9.3},
            "colours": [
                {"code": 288, "name": "Dark Green", "share": 0.41},
                {"code": 70, "name": "Reddish Brown", "share": 0.3},
                {"code": 191, "name": "Bright Light Orange", "share": 0.2},
            ],
            "glass": [],
            "body_colours": 3,
            "not_in_brief": [{"code": 70, "name": "Reddish Brown", "share": 0.3}],
            "brief_unused": [],
        },
        "changed_after": False,
        "unexplained": [],
        "mismatches": [
            "The brief said: Dark Green 60%, Bright Light Orange 30%, Dark Brown under 10%, "
            "Trans Black. The model, by bulk: Dark Green 41%, Reddish Brown 30%, Bright Light "
            "Orange 20%."
        ],
    }


# What a guided run's record holds (lab.art.record), as a session made with the guide leaves it.
SAMPLE_BRIEF = {
    "scale": "a pot 6 studs across; the flower head forced it",
    "colours": [
        {
            "code": 288,
            "job": "stems and leaves",
            "share": "60%",
            "name": "Dark Green",
            "value": "#00451A",
        },
        {
            "code": 191,
            "job": "petals",
            "share": "30%",
            "name": "Bright Light Orange",
            "value": "#FCAC00",
        },
        {
            "code": 308,
            "job": "the centre",
            "share": "under 10%",
            "name": "Dark Brown",
            "value": "#352100",
        },
        {"code": 10375, "job": "none", "share": "", "name": "Trans Black", "value": "#212121"},
    ],
    "pattern": "green below, orange above, a dark centre",
    "shapes": [
        {"shape": "the round head", "part": "petals on clips round a hub"},
        {"shape": "the drooping leaves", "part": "curved slopes on clip plates"},
        {"shape": "the pot", "part": "a tiled drum of round plates"},
    ],
    "sideways": "the pot's rim panels",
    "thin": "the stem, a bar",
    "studs": "a patch in the centre, for seeds",
    "glass": "no glass; it stands on its pot",
}
SAMPLE_CRITIQUE = _sample_critique()


def never_start(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("a test tried to start a real AI session")


@pytest.fixture(scope="module", autouse=True)
def no_real_ai() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lab_run, "build", never_start)
        mp.setattr(runner, "run_session", never_start)
        mp.setattr(runner, "run_designer", never_start)
        mp.setattr(judge, "design_best_of", never_start)
        mp.setattr(studio, "run_studio", never_start)
        yield


# ---- stand-ins for LeoCAD ---------------------------------------------------------------------


def _study_panels() -> dict[str, list[Image.Image]]:
    """The three views of each of last night's models, cut from its real sheet."""
    out = {}
    for name in ("car", "cat", "flower"):
        with Image.open(STUDY / f"{name}.png") as sheet:
            sheet = sheet.convert("RGB")
        panels = []
        for k in range(3):
            panel = sheet.crop((k * 560 + 4, 80, (k + 1) * 560 - 4, sheet.height))
            grey = panel.convert("L").point(lambda v: 255 if v < 250 else 0)
            panels.append(panel.crop(grey.getbbox() or (0, 0, panel.width, panel.height)))
        out[(STUDY / f"{name}.ldr").read_text("utf-8")] = panels
    return out


PANELS: dict[str, list[Image.Image]] = {}


class FakePictures:
    """Stands in for LeoCAD: twelve views and a sheet, from the study's real pictures when
    the model is one of them, else small plain pictures."""

    def __init__(self) -> None:
        self.calls = 0
        self.fail: str | None = None

    def sheet(self, text: str, out_png: Path, title: str = "") -> Path:
        if self.fail:
            raise picture.PictureError(self.fail)
        Image.new("RGB", (60, 20), (255, 255, 255)).save(out_png)
        return out_png

    def turntable(self, text: str, out_dir: Path, views: int = 12, **kw: Any) -> list[Path]:
        self.calls += 1
        if not PANELS:
            PANELS.update(_study_panels())
        panels = PANELS.get(text)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for k in range(views):
            if panels:
                im = panels[(0, 2, 1)[k % 3]]
                im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if k % 2 else im
                frame = Image.new("RGB", (640, 480), "white")
                im = im.copy()
                im.thumbnail((620, 460))
                frame.paste(im, ((640 - im.width) // 2, (480 - im.height) // 2))
            else:
                frame = Image.new("RGB", (40, 30), (200, 20 * k, 20))
            path = out_dir / f"turn-{k:02d}.png"
            frame.save(path)
            paths.append(path)
        return paths


@pytest.fixture(autouse=True)
def pictures(monkeypatch: pytest.MonkeyPatch) -> FakePictures:
    fake = FakePictures()
    monkeypatch.setattr(picture, "model_sheet", fake.sheet)
    monkeypatch.setattr(picture, "turntable", fake.turntable)
    monkeypatch.setattr(freebuild, "missing", lambda: None)
    return fake


# ---- a stand-in for one AI session ------------------------------------------------------------


def tool_use(name: str, args: dict[str, Any], n: int) -> dict[str, Any]:
    item = {"type": "tool_use", "id": f"t{n}", "name": runner.TOOL_PREFIX + name, "input": args}
    return {"type": "assistant", "message": {"content": [item]}}


def tool_result(n: int, text: str = "ok") -> dict[str, Any]:
    item = {
        "type": "tool_result",
        "tool_use_id": f"t{n}",
        "content": [{"type": "text", "text": text}],
    }
    return {"type": "user", "message": {"content": [item]}}


def said(text: str) -> dict[str, Any]:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


class FakeLab:
    """Stands in for ``lab.run.build``: talks through ``on_event`` as a session does, and
    leaves a work folder as the lab does."""

    def __init__(
        self,
        *,
        ok: bool = True,
        model: str = TWO_BRICKS,
        report: str = CLEAN_REPORT,
        gate: Gate | None = None,
        no_model: bool = False,
    ) -> None:
        self.ok, self.model, self.report, self.gate, self.no_model = (
            ok,
            model,
            report,
            gate,
            no_model,
        )
        self.calls: list[dict[str, Any]] = []

    def __call__(self, task: str, out: Path, **kw: Any) -> dict[str, Any]:
        self.calls.append({"task": task, "out": out, **kw})
        tell = kw.get("on_event") or (lambda e: None)
        out.mkdir(parents=True)
        (out / "attempts").mkdir()
        tell({"type": "system", "subtype": "init", "tools": []})
        tell(tool_use("search_parts", {"query": "curved slope 2 x 2"}, 1))
        tell(tool_result(1))
        if not self.no_model:
            (out / "model.ldr").write_text(TWO_BRICKS.splitlines()[0] + "\n", "utf-8")
            tell(tool_use("place", {"part": "3001.dat", "colour": 4, "line": 0}, 2))
            tell(tool_result(2))
            tell(tool_use("check", {}, 3))
            (out / "attempts" / "attempt-001-report.txt").write_text(
                "SUMMARY: 1 part of 1 kind, 3 problems, 1 warning.\n", "utf-8"
            )
            tell(tool_result(3))
            tell(tool_use("place", {"part": "nope.dat", "colour": 4, "line": 1}, 4))
            tell(tool_result(4, "ERROR: there is no part nope.dat"))
            (out / "model.ldr").write_text(self.model, "utf-8")
            tell(tool_use("check", {}, 5))
            (out / "attempts" / "attempt-002-report.txt").write_text(self.report, "utf-8")
            tell(tool_result(5))
        home = str(Path.home())
        tell(said(f"Done. Mail someone@example.com, see {home}/notes. {MARKUP}"))
        if self.gate is not None:
            self.gate.wait()
        record = {
            "ok": self.ok,
            "error": "" if self.ok else "The session used all its turns (90) before it finished.",
            "turns": 12,
            "seconds": 600.0,
            "cost_usd_reported": 1.5,
            "task": task,
            "closing_words": f"I built two bricks. Write to someone@example.com. {MARKUP}",
            "guide": kw.get("guide", False),
            "playbook": "Plant, 100 parts" if kw.get("guide") else None,
        }
        if kw.get("guide"):  # what lab.art.record adds to a guided session's record
            record.update(
                art=True,
                brief=SAMPLE_BRIEF,
                briefs=[
                    {"n": 1, "brief": SAMPLE_BRIEF, "reason": None, "parts_before": 0},
                    {
                        "n": 2,
                        "brief": SAMPLE_BRIEF,
                        "reason": "orange petals read better than yellow",
                        "parts_before": 30,
                    },
                ],
                critiques=2,
                first_no=["thin", "glass", "stance"],
                ended_without_critique=False,
                built_without_brief=False,
                critique=SAMPLE_CRITIQUE,
                handed_in_without_critique=False,
            )
        if not self.no_model:
            (out / "final.ldr").write_text(self.model, "utf-8")
            (out / "final-report.txt").write_text(self.report, "utf-8")
        (out / "session.json").write_text(json.dumps(record), "utf-8")
        (out / "transcript").mkdir()
        (out / "transcript" / "x.jsonl").write_text('{"secret": "someone@example.com"}\n')
        (out / "calls.jsonl").write_text("{}\n")
        return record


def free_project(projects: Path, name: str = "car", words: str = "a red roadster") -> Path:
    """A free-build project from one of last night's models, as ``import_run`` makes it."""
    folder = freebuild.import_run(projects, STUDY / f"{name}.ldr", words=words)
    return folder


# ---- the project layer ------------------------------------------------------------------------


def test_import_of_a_model_with_its_report(tmp_path: Path, pictures: FakePictures) -> None:
    folder = free_project(tmp_path, "car", "A red open-top roadster")
    assert folder.name == "a-red-open-top-roadster"
    meta = json.loads((folder / "project.json").read_text())
    assert meta["kind"] == "free" and meta["experimental"] is True and meta["current"] == 1
    info = freebuild.describe(folder)
    assert (info["parts"], info["kinds"]) == (102, 33)
    assert info["clean"] is True and info["problems"] == 0 and info["unchecked"] == 13
    assert info["summary"].startswith("102 parts of 33 kinds, no problems")
    assert info["turntable"] == [f"pictures/turn-{k:02d}.png" for k in range(12)]
    assert info["card"] == "pictures/card.png" and info["sheet"] == "pictures/sheet.png"
    with Image.open(folder / "pictures" / "card.png") as card:
        assert card.width * 3 == card.height * 4
    assert info["runs"][0]["kind"] == "imported" and info["runs"][0]["has_model"]
    assert (folder / "model.ldr").read_text() == (STUDY / "car.ldr").read_text()
    assert (folder / "report.txt").read_text() == (STUDY / "car-report.txt").read_text()
    rows = list(csv.reader(io.StringIO((folder / "parts.csv").read_text())))
    assert rows[0] == list(freebuild.CSV_HEADER)
    assert sum(int(r[4]) for r in rows[1:]) == 102 and len({r[0] for r in rows[1:]}) == 33
    assert all(re.fullmatch(r"\d+", r[2]) for r in rows[1:])
    for f in ("model.ldr", "report.txt", "parts.csv", "record.json", "pictures/turn-11.png"):
        assert (folder / "runs" / "0001" / f).is_file()


def test_import_of_a_lab_run_copies_no_transcript(tmp_path: Path) -> None:
    run_folder = tmp_path / "lab-run"
    FakeLab()("Build two bricks. About 80 parts.", run_folder)
    folder = freebuild.import_run(tmp_path / "projects", run_folder, name="Two bricks")
    assert folder.name == "two-bricks"
    assert freebuild.read_meta(folder)["words"] == "Build two bricks. About 80 parts."
    notes = (folder / "notes.txt").read_text()
    assert "someone@example.com" not in notes and "<account email>" in notes
    found = {p.name for p in folder.rglob("*")}
    assert not found & {"transcript", "x.jsonl", "calls.jsonl", "session.json", "work"}
    with pytest.raises(freebuild.FreeBuildError, match="not found"):
        freebuild.import_run(tmp_path, tmp_path / "nothing-here")
    (tmp_path / "empty.ldr").write_text("0 nothing\n")
    with pytest.raises(freebuild.FreeBuildError, match="no model"):
        freebuild.import_run(tmp_path, tmp_path / "empty.ldr")


def test_build_change_and_restore(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    folder = freebuild.create(tmp_path, "  a small red\x00 fire truck ", parts=40, name="")
    assert folder.name == "a-small-red-fire-truck"
    lines: list[str] = []
    entry = freebuild.build(folder, on_say=lines.append)
    call = fake.calls[0]
    assert call["task"] == "a small red  fire truck. About 40 parts."
    assert call["start"] is None and call["change_of"] is None
    assert call["out"] == folder / "runs" / "0001" / "work"
    assert call["max_turns"] == freebuild.MAX_TURNS and call["timeout"] == freebuild.TIMEOUT_S
    assert call["max_checks"] == freebuild.MAX_CHECKS  # 40 parts: the least a session gets
    assert entry["n"] == 1 and entry["kind"] == "first" and entry["clean"] is True
    assert "The builder is looking for parts: curved slope 2 x 2" in lines
    assert "It placed a part (1 so far)" in lines
    assert "Check 1: 3 problems to fix" in lines and "Check 2: no problems" in lines
    assert sum(1 for line in lines if line.startswith("It placed")) == 1  # the error is not a part
    told = next(line for line in lines if line.startswith("The builder says"))
    assert "someone@example.com" not in told and str(Path.home()) not in told
    assert "It placed a part" in " ".join(lines)

    fake.model = TWO_BRICKS + "1 14 0 -72 0 1 0 0 0 1 0 0 0 1 3003.dat\n"
    entry = freebuild.build(folder, "make it taller", on_say=lines.append)
    call = fake.calls[1]
    assert call["task"] == "make it taller" and call["start"] == folder / "model.ldr"
    assert call["change_of"] == "a small red  fire truck"
    assert entry["n"] == 2 and entry["kind"] == "change" and entry["parts"] == 3
    assert freebuild.describe(folder)["current_run"] == 2
    with pytest.raises(freebuild.FreeBuildError, match="what to change"):
        freebuild.build(folder, "   ")
    back = freebuild.restore(folder, 1)
    assert back["n"] == 1 and freebuild.describe(folder)["parts"] == 2
    assert (folder / "model.ldr").read_text() == TWO_BRICKS
    assert len(freebuild.describe(folder)["runs"]) == 2
    with pytest.raises(freebuild.FreeBuildError, match="no run 7"):
        freebuild.restore(folder, 7)


def test_a_big_model_gets_more_turns_checks_and_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    folder = freebuild.create(tmp_path, "a Cessna 172", parts=600)
    freebuild.build(folder)
    call = fake.calls[0]
    assert (call["max_turns"], call["max_checks"], call["timeout"]) == (210, 75, 3 * 3600)
    assert "parts" not in call  # told only in guide mode
    assert call["task"].endswith("About 600 parts.")


def test_a_failed_run_keeps_what_it_made(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lab_run, "build", FakeLab(ok=False))
    folder = freebuild.create(tmp_path, "a boat")
    with pytest.raises(freebuild.FreeBuildError, match="did not finish: The session used all"):
        freebuild.build(folder)
    info = freebuild.describe(folder)
    assert info["current_run"] == 1 and info["parts"] == 2 and info["runs"][0]["ok"] is False
    monkeypatch.setattr(lab_run, "build", FakeLab(no_model=True))
    with pytest.raises(freebuild.FreeBuildError, match="did not make a model"):
        freebuild.build(folder, "add a mast")
    info = freebuild.describe(folder)
    assert info["current_run"] == 1 and [r["has_model"] for r in info["runs"]] == [True, False]
    with pytest.raises(freebuild.FreeBuildError, match="made no model"):
        freebuild.restore(folder, 2)


def test_no_pictures_never_loses_the_model(tmp_path: Path, pictures: FakePictures) -> None:
    pictures.fail = "LeoCAD was not found (/somewhere/LeoCAD.AppImage)."
    folder = free_project(tmp_path, "flower", "a sunflower in a pot")
    info = freebuild.describe(folder)
    assert info["parts"] == 58 and info["turntable"] == [] and info["card"] is None
    assert "LeoCAD was not found" in info["picture_problem"]


def test_create_checks_its_input(tmp_path: Path) -> None:
    with pytest.raises(freebuild.FreeBuildError, match="Say what to build"):
        freebuild.create(tmp_path, " \n ")
    with pytest.raises(freebuild.FreeBuildError, match="20 to 600"):
        freebuild.create(tmp_path, "a cat", parts=601)
    assert (
        freebuild.read_meta(freebuild.create(tmp_path, "a big plane", parts=600))["parts_wanted"]
        == 600
    )
    a = freebuild.create(tmp_path, "A cat. Orange.", name="x" * 200)
    b = freebuild.create(tmp_path, "A cat. Orange.")
    assert len(freebuild.read_meta(a)["name"]) == freebuild.MAX_NAME
    assert b.name == "a-cat" and freebuild.create(tmp_path, "a cat").name == "a-cat-2"
    assert freebuild.is_free(b) and not freebuild.is_free(tmp_path)


def test_read_summary() -> None:
    clean = freebuild.read_summary((STUDY / "car-report.txt").read_text())
    assert clean == {
        "summary": clean["summary"],
        "clean": True,
        "problems": 0,
        "unchecked": 13,
    }
    bad = freebuild.read_summary("SUMMARY: 9 parts of 4 kinds, 1 problem, 2 joints not checked.")
    assert (bad["clean"], bad["problems"], bad["unchecked"]) == (False, 1, 2)
    none = freebuild.read_summary("SUMMARY: 0 parts of 0 kinds: there is nothing to check.")
    assert none["clean"] is False
    assert freebuild.read_summary("hello")["summary"] == ""


def test_missing_says_what_to_put_where(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bricksnap.lab import ldraw_lib

    monkeypatch.undo()  # the real ``missing``
    monkeypatch.setattr(ldraw_lib, "zip_path", lambda: tmp_path / "nolib.zip")
    monkeypatch.setenv("BRICKSNAP_LEOCAD", str(tmp_path / "no-leocad"))
    monkeypatch.setattr(shutil, "which", lambda name: None)
    text = freebuild.missing()
    assert text is not None
    assert "leocad.org" in text and "LeoCAD.AppImage" in text
    assert str(tmp_path / "nolib.zip") in text and "library.bin" in text
    assert "xvfb" in text


# ---- the command ------------------------------------------------------------------------------


def _cli(capsys: Any, *argv: str) -> tuple[int, str, str]:
    from bricksnap.cli import main

    code = main(list(argv))
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    return code, captured.out, captured.err


def test_make_command(
    capsys: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pawn_path: Path
) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    projects = tmp_path / "projects"
    code, out, err = _cli(capsys, "make", "--dir", str(projects))
    assert code == 2 and "Say what to build" in err
    assert _cli(capsys, "make", "a cat", "--parts", "5", "--dir", str(projects))[0] == 2
    monkeypatch.setattr(freebuild, "missing", lambda: "LeoCAD is not here. Put it there.")
    code, out, err = _cli(capsys, "make", "a cat", "--dir", str(projects))
    assert code == 2 and "LeoCAD is not here" in err and not projects.exists()
    monkeypatch.setattr(freebuild, "missing", lambda: None)

    code, out, err = _cli(capsys, "make", "a fire truck", "--name", "Truck", "--dir", str(projects))
    assert code == 0, err
    assert "sends the words you typed to the AI provider" in out
    assert "one AI run" in out and "experimental" in out
    assert "A model of about 80 parts usually takes 5 to 15 minutes and is stopped at 90" in out
    assert "$2 to $6 of your Claude subscription" in out
    assert "  It placed a part (1 so far)" in out and "no problems" in out
    assert "someone@example.com" not in out and fake.calls[0]["task"].endswith("About 80 parts.")
    truck = projects / "truck"
    assert freebuild.describe(truck)["current_run"] == 1

    monkeypatch.chdir(tmp_path)
    code, out, err = _cli(capsys, "make", "--change", "truck", "make it blue")
    assert code == 0, err
    assert "the words the model was first built from" in out
    assert fake.calls[1]["change_of"] == "a fire truck" and fake.calls[1]["task"] == "make it blue"
    assert _cli(capsys, "make", "--change", "truck")[0] == 2
    code, out, err = _cli(capsys, "build", "truck")
    assert code == 2 and "built from parts" in err and "make --change" in err

    ordinary = create_project(pawn_path, studs=8, directory=projects, name="Pawn")
    code, out, err = _cli(capsys, "make", "--change", "pawn", "make it red")
    assert code == 2 and "not one the AI built from parts" in err
    assert ordinary.path.name == "pawn"

    code, out, err = _cli(
        capsys, "make", "--import", str(STUDY / "cat.ldr"), "--name", "Cat", "--dir", "projects"
    )
    assert code == 0 and "78 parts of 35 kinds, no problems" in out
    assert len(fake.calls) == 2  # importing starts no AI


# ---- the web app: fixtures ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_pawn(tmp_path_factory: pytest.TempPathFactory, pawn_path: Path) -> Path:
    base = tmp_path_factory.mktemp("free-base")
    project = create_project(pawn_path, studs=8, directory=base, name="Pawn")
    rebuild(project)
    render_compare(project)
    render_card(project)
    rough_build(project)
    return project.path


@pytest.fixture(scope="module")
def made_car(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The car from last night as a free build, made once and copied for each test."""
    base = tmp_path_factory.mktemp("free-car")
    with pytest.MonkeyPatch.context() as mp:
        fake = FakePictures()
        mp.setattr(picture, "model_sheet", fake.sheet)
        mp.setattr(picture, "turntable", fake.turntable)
        folder = freebuild.import_run(
            base, STUDY / "car.ldr", words="A red roadster", name="Roadster"
        )
    return folder


@pytest.fixture
def projects(tmp_path: Path, built_pawn: Path, made_car: Path) -> Path:
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(built_pawn, root / "pawn")
    shutil.copytree(made_car, root / "car")
    (tmp_path / "secret.txt").write_text("TOP SECRET", "utf-8")
    return root


@pytest.fixture
def running(projects: Path) -> Iterator[Running]:
    r = Running(projects)
    yield r
    r.close()


# ---- the web app: routes -----------------------------------------------------------------------


def test_free_builds_are_listed_and_described(running: Running) -> None:
    cards = {c["project"]: c for c in running.get_json("/api/projects")["projects"]}
    car, pawn = cards["car"], cards["pawn"]
    assert pawn["kind"] == "model" and car["kind"] == "free"
    assert car["name"] == "Roadster" and car["parts"] == 102 and car["valid"] is True
    assert car["problems"] == 0 and car["unchecked"] == 13 and car["studs"] is None
    assert car["checked"].startswith("102 parts") and car["problem"] is None
    assert car["picture"].startswith("/p/car/files/pictures/card.png?v=")
    info = running.get_json("/api/p/car")
    assert info["words"] == "A red roadster" and info["kinds"] == 33 and info["current_run"] == 1
    assert len(info["turntable"]) == 12 and info["turntable"][0].startswith(
        "/p/car/files/pictures/turn-00.png?v="
    )
    assert set(info["files"]) == {"model.ldr", "parts.csv", "report.txt"}
    assert info["report"].startswith("SUMMARY:") and info["job"] is None
    assert info["runs"][0]["picture"].startswith("/p/car/files/runs/0001/pictures/card.png")
    for url in [
        *info["turntable"],
        *info["files"].values(),
        info["runs"][0]["picture"],
        info["sheet"],
    ]:
        status, _, _ = running.request(url)
        assert status == 200, url


def test_the_free_page_is_its_own(running: Running) -> None:
    status, headers, body = running.request("/p/car")
    page = body.decode()
    assert status == 200 and "free-page" in page and "/viewer/free.js" in page
    assert running.token in page and 'data-project="car"' in page
    assert 'data-first="/p/car/files/pictures/turn-00.png?v=' in page
    assert "viewer.js" not in page and TRADEMARK in page
    assert running.request("/p/car/project-files.json")[0] == 404


@pytest.mark.parametrize(
    "inner",
    [
        "project.json",
        "runs/0001/record.json",
        "runs/0001/work/calls.jsonl",
        "runs/0001/work/transcript/x.jsonl",
        "runs/0001/work/final.ldr",
        "runs/0002/pictures/card.png",
        "runs/1/pictures/card.png",
        "runs/0001/model.ldr",
        "notes.txt",
        "reference.png",
        "pictures/other.png",
        "build.json",
        "../pawn/build.json",
        "..%2Fpawn%2Fbuild.json",
        "calls.jsonl",
    ],
)
def test_only_the_model_lists_and_pictures_are_served(
    running: Running, projects: Path, inner: str
) -> None:
    car = projects / "car"
    work = car / "runs" / "0001" / "work"
    (work / "transcript").mkdir(parents=True)
    for f in ("calls.jsonl", "transcript/x.jsonl", "final.ldr"):
        (work / f).write_text("someone@example.com")
    (car / "calls.jsonl").write_text("x")
    (car / "reference.png").write_bytes(b"x")
    (car / "pictures" / "other.png").write_bytes(b"x")
    (car / "runs" / "0002" / "pictures").mkdir(parents=True)
    (car / "runs" / "0002" / "pictures" / "card.png").write_bytes(b"x")  # not listed
    (car / "runs" / "1" / "pictures").mkdir(parents=True)
    (car / "runs" / "1" / "pictures" / "card.png").write_bytes(b"x")
    status, _, data = running.request(f"/p/car/files/{inner}")
    assert status == 404 and b"someone" not in data


def test_a_symlink_out_of_a_free_build_is_not_served(running: Running, projects: Path) -> None:
    (projects / "car" / "report.txt").unlink()
    os.symlink(projects.parent / "secret.txt", projects / "car" / "report.txt")
    status, _, data = running.request("/p/car/files/report.txt")
    assert status == 404 and b"SECRET" not in data


@pytest.mark.parametrize(
    ("body", "words"),
    [
        ({}, "Say in words"),
        ({"words": "   "}, "Say in words"),
        ({"words": 5}, "Say in words"),
        ({"words": "x" * 2001}, "too long"),
        ({"words": "a cat", "parts": 10}, "20 to 600"),
        ({"words": "a cat", "parts": 601}, "20 to 600"),
        ({"words": "a cat", "parts": True}, "20 to 600"),
        ({"words": "a cat", "parts": "80"}, "20 to 600"),
        ({"words": "a cat", "name": 4}, "must be text"),
        ({"words": "a cat", "reference": "car"}, "built by the AI from parts"),
        ({"words": "a cat", "reference": 3}, "Choose the model"),
    ],
)
def test_a_free_build_request_is_checked(running: Running, body: dict, words: str) -> None:
    status, data = running.post("/api/free", {**body, **AGREED})
    assert status == 400 and words in data["error"]
    assert sorted(p.name for p in running.app.root.iterdir()) == ["car", "pawn"]


@pytest.mark.parametrize(
    "agreement",
    [
        {},
        {"understood": True},
        {"understood": "yes", "understood_runs": 1},
        {"understood": True, "understood_runs": 2},
    ],
)
def test_a_free_build_needs_the_persons_agreement(running: Running, agreement: dict) -> None:
    status, data = running.post("/api/free", {"words": "a cat", **agreement})
    assert status == 400 and "was not started" in data["error"]
    status, data = running.post("/api/p/car/change", {"words": "bluer", **agreement})
    assert status == 400 and "was not started" in data["error"]


def test_a_free_build_request_needs_the_token_and_this_site(running: Running) -> None:
    body = {"words": "a cat", **AGREED}
    status, _ = running.post("/api/free", body, token=False)
    assert status == 403
    status, _ = running.post("/api/free", body, headers={"Origin": "http://evil.example"})
    assert status == 403
    status, _ = running.post("/api/free", body, host="evil.example")
    assert status == 404


def test_missing_leocad_is_said_plainly_and_starts_nothing(
    running: Running, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(freebuild, "missing", lambda: "LeoCAD is not on this computer. Get it.")
    status, data = running.post("/api/free", {"words": "a cat", **AGREED})
    assert status == 400 and data["error"] == "LeoCAD is not on this computer. Get it."
    status, data = running.post("/api/p/car/change", {"words": "bluer", **AGREED})
    assert status == 400 and "LeoCAD" in data["error"]
    assert running.get_json("/api/projects")["jobs"] == []


def test_a_new_free_build_from_words(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    monkeypatch.setattr(
        freebuild, "reference_sheet", lambda src, out: Image.new("RGB", (8, 8)).save(out) or out
    )
    status, data = running.post(
        "/api/free",
        {
            "words": f"a fire\x07 truck {MARKUP}",
            "parts": 120,
            "reference": "pawn",
            "name": "Truck",
            **AGREED,
        },
    )
    assert status == 202 and data["project"] == "truck"
    job = running.wait(data["job"])
    assert job["state"] == "done", job
    assert job["kind"] == "free" and job["result"]["project"] == "truck" and job["result"]["clean"]
    said = job["progress"]
    assert "The builder is looking for parts: curved slope 2 x 2" in said
    assert "Check 2: no problems" in said
    assert all("someone@example.com" not in line and str(Path.home()) not in line for line in said)
    call = fake.calls[0]
    assert call["task"] == f"a fire  truck {MARKUP}. About 120 parts."
    assert [p.name for p in call["references"]] == ["reference.png"]
    meta = freebuild.read_meta(projects / "truck")
    assert meta["reference"] == "pawn" and meta["name"] == "Truck"
    card = next(c for c in running.get_json("/api/projects")["projects"] if c["project"] == "truck")
    assert card["kind"] == "free" and card["parts"] == 2 and card["valid"] is True


def test_a_change_a_run_brought_back_and_the_bin(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLab(model=TWO_BRICKS + "1 14 0 -72 0 1 0 0 0 1 0 0 0 1 3003.dat\n")
    monkeypatch.setattr(lab_run, "build", fake)
    status, data = running.post("/api/p/car/change", {"words": "make it yellow", **AGREED})
    assert status == 202
    job = running.wait(data["job"])
    assert job["state"] == "done" and job["kind"] == "change" and job["result"]["run"] == 2
    assert 'This is one change to the model: "make it yellow"' in job["progress"]
    assert fake.calls[0]["start"] == projects / "car" / "model.ldr"
    assert fake.calls[0]["change_of"] == "A red roadster"
    info = running.get_json("/api/p/car")
    assert info["current_run"] == 2 and info["parts"] == 3 and len(info["runs"]) == 2
    assert "<account email>" in info["notes"]
    for bad in ({}, {"run": "1"}, {"run": 0}, {"run": True}):
        status, data = running.post("/api/p/car/use", bad)
        assert status == 400 and "which run" in data["error"]
    status, data = running.post("/api/p/car/use", {"run": 9})
    assert running.wait(data["job"])["error"] == "This model has no run 9, so nothing was changed."
    status, data = running.post("/api/p/car/use", {"run": 1})
    assert running.wait(data["job"])["state"] == "done"
    assert running.get_json("/api/p/car")["parts"] == 102
    status, data = running.post("/api/p/car/delete")
    assert status == 200 and data["moved_to"] == ".trash/car"
    assert (projects / ".trash" / "car" / "runs" / "0002" / "model.ldr").is_file()


@pytest.mark.parametrize("action", ["build", "design", "export", "instructions", "restore"])
def test_actions_for_ordinary_models_refuse_a_free_build(running: Running, action: str) -> None:
    body = {"version": 1} if action == "restore" else AGREED if action == "design" else {}
    status, data = running.post(f"/api/p/car/{action}", body)
    assert status == 400 and "built by the AI from parts" in data["error"]
    status, data = running.post(
        "/api/p/car/design", {"mode": "passes", "understood": True, "understood_runs": 6}
    )
    assert status == 400 and "built by the AI from parts" in data["error"]


def test_free_actions_refuse_an_ordinary_model(running: Running) -> None:
    status, data = running.post("/api/p/pawn/change", {"words": "bluer", **AGREED})
    assert status == 400 and "made from a 3D file" in data["error"]
    status, data = running.post("/api/p/pawn/use", {"run": 1})
    assert status == 400 and "made from a 3D file" in data["error"]
    status, data = running.post("/api/p/nothing/change", {"words": "bluer", **AGREED})
    assert status == 404


def test_one_ai_job_for_the_whole_server(running: Running, monkeypatch: pytest.MonkeyPatch) -> None:
    gate = Gate()
    monkeypatch.setattr(lab_run, "build", FakeLab(gate=gate))
    status, data = running.post("/api/free", {"words": "a boat", **AGREED})
    assert status == 202
    assert gate.reached.wait(20)
    status, other = running.post("/api/free", {"words": "a plane", **AGREED})
    assert status == 409 and 'already building "a-boat"' in other["error"]
    status, other = running.post("/api/p/pawn/design", AGREED)
    assert status == 409
    status, other = running.post("/api/p/car/change", {"words": "bluer", **AGREED})
    assert status == 409
    status, other = running.post("/api/p/a-boat/delete")
    assert status == 409 and "busy" in other["error"]
    card = next(
        c for c in running.get_json("/api/projects")["projects"] if c["project"] == "a-boat"
    )
    assert card["job"] == data["job"]
    gate.open.set()
    assert running.wait(data["job"])["state"] == "done"


def test_a_failed_free_build_says_why_and_keeps_what_was_made(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(lab_run, "build", FakeLab(ok=False))
    status, data = running.post("/api/free", {"words": "a boat", **AGREED})
    job = running.wait(data["job"])
    assert job["state"] == "failed"
    assert job["error"].startswith("The builder did not finish: The session used all its turns")
    assert "kept as run 1" in job["error"] and "Traceback" not in job["error"]
    assert freebuild.describe(projects / "a-boat")["parts"] == 2

    def broken(*a: Any, **k: Any) -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(lab_run, "build", broken)
    status, data = running.post("/api/p/a-boat/change", {"words": "add a sail", **AGREED})
    job = running.wait(data["job"])
    assert job["state"] == "failed" and "Something went wrong inside BrickSnap" in job["error"]
    assert running.get_json("/api/p/a-boat")["current_run"] == 1


def test_pages_have_the_trademark_and_fetch_nothing_from_the_internet() -> None:
    assert TRADEMARK in (VIEWER / "free.html").read_text("utf-8")
    for name in ("free.html", "free.js", "home.html", "home.js"):
        text = (VIEWER / name).read_text("utf-8")
        urls = re.findall(r"https?://[^\s\"')]+", text)
        assert all(u.startswith("http://www.w3.org/") for u in urls), (name, urls)
    js = (VIEWER / "free.js").read_text("utf-8")
    for sink in (r"\.innerHTML\b", r"\.outerHTML\b", r"insertAdjacentHTML\(", r"document\.write"):
        assert not re.search(sink, js), sink


# ---- browser tests ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except sync_api.Error as e:
            pytest.skip(
                "Headless Chromium is not installed. Run 'uv run playwright install chromium' "
                f"once, then run the tests again. ({str(e).splitlines()[0]})"
            )
        yield b
        b.close()


def shot(tab: Tab, name: str, full: bool = True) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    tab.page.screenshot(path=str(ARTIFACTS / f"free-{name}.png"), full_page=full)


@pytest.mark.browser
def test_browser_home_form_consent_and_a_running_build(
    browser: Any, running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = Gate()
    fake = FakeLab(
        gate=gate,
        model=(STUDY / "flower.ldr").read_text(),
        report=(STUDY / "flower-report.txt").read_text(),
    )
    monkeypatch.setattr(lab_run, "build", fake)
    tab = Tab(browser, running.url, width=1280, height=900).open()
    try:
        page = tab.page
        free_card = page.locator('.pcard[data-kind="free"]')
        assert free_card.count() == 1
        assert page.locator(".pcard").first.get_attribute("data-kind") == "free"  # first
        assert "Checked: no problems" in (free_card.text_content() or "")
        assert "Experimental" in (free_card.text_content() or "")
        assert not page.locator("#freeMore").get_attribute("open")  # options folded away
        assert not page.locator("#older").get_attribute("open")  # the older way too
        page.click("#freeGo")
        assert "Say what to build first" in tab.text("#freeMsg")
        page.fill("#freeWords", f"a sunflower in a pot {MARKUP}")
        assert tab.text("#freeSends") == (
            "Build sends your words to Anthropic through Claude Code; nothing else leaves this "
            "computer."
        )
        assert tab.text("#freeCost") == (
            "One AI run by Claude Fable 5.2, designed first: usually 20 to 40 minutes, about "
            "$4 to $14 of your Claude subscription."
        )
        assert tab.text("#freeCostFull") == freebuild.time_and_cost(200)  # 200 unless changed
        assert "hinges, ball joints and the other clips" in tab.text("#freeCaveat")
        page.click("#freeGo")  # not agreed yet: nothing starts
        assert "Tick “I understand" in tab.text("#freeMsg") and fake.calls == []
        page.check("#freeUnderstood")
        tab.open()  # the agreement is remembered in this browser
        assert page.locator("#freeUnderstood").is_checked()
        page.fill("#freeWords", f"a sunflower in a pot {MARKUP}")
        shot(tab, "home-bar")
        page.click("#freeGo")
        page.wait_for_url("**/p/a-sunflower-in-a-pot-img", timeout=20000)  # its own page
        assert gate.reached.wait(20)
        page.wait_for_function(
            "() => (document.querySelector('#appJob .job') || {}).textContent?.includes('Check 2')"
        )
        text = page.locator("#appJob .job").text_content() or ""
        assert "AI is building a new model from parts" in text
        assert "someone@example.com" not in text
        assert tab.text("#asked") == f"Asked for: “a sunflower in a pot {MARKUP}”"
        assert page.evaluate("() => window.__pwned") is None
        shot(tab, "job-running")
        call = fake.calls[0]
        assert call["guide"] is True and call["max_checks"] == 25  # the guide is on by default
        assert call["task"].endswith("About 200 parts.")
        gate.open.set()
        page.wait_for_selector("#appJob .job.done", timeout=30000)
        tab.assert_clean()
    finally:
        gate.open.set()
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open()
    try:
        phone.no_sideways_scroll()
        shot(phone, "home-phone", full=False)
        phone.assert_clean()
    finally:
        phone.close()


@pytest.mark.browser
def test_browser_the_project_page_turns_the_model(
    browser: Any, running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = projects / "car"
    (folder / "notes.txt").write_text(
        "The model is a red open-top roadster with a white racing stripe.\n\n"
        f"**Wheels:** four rims with tyres on wheel-pin plates. {MARKUP}\n"
        "- **Arches:** four mudguards.\n- **Windscreen:** a curved smoke screen.\n",
        "utf-8",
    )
    tab = Tab(browser, running.url, width=1280, height=900).open("p/car")
    try:
        page = tab.page
        page.wait_for_function("() => document.querySelector('#turn').complete")
        first = page.get_attribute("#turn", "src")
        assert first and "turn-00.png" in first
        assert (
            tab.text("#freeName") == "Roadster"
            and tab.text("#asked") == "Asked for: “A red roadster”"
        )
        assert "Checked: no problems" in tab.text("#chips") and "13 joints not checked" in tab.text(
            "#chips"
        )
        page.focus("#turnBox")
        page.keyboard.press("ArrowRight")
        assert "turn-01.png" in (page.get_attribute("#turn", "src") or "")
        assert page.input_value("#turnSlider") == "1"
        page.keyboard.press("ArrowLeft")
        page.keyboard.press("ArrowLeft")
        assert "turn-11.png" in (page.get_attribute("#turn", "src") or "")
        page.locator("#turnSlider").fill("0")
        assert "turn-00.png" in (page.get_attribute("#turn", "src") or "")
        assert page.locator("#aiNotes strong").first.text_content() == "Wheels:"
        assert page.evaluate("() => window.__pwned") is None
        assert page.locator("#downloads a").count() == 3
        assert page.get_attribute('#downloads a[href*="model.ldr"]', "download") == "car-model.ldr"
        assert page.locator("#runs li").count() == 1 and "In use" in tab.text("#runs")
        page.fill("#askText", f"make it yellow {MARKUP}")
        page.click("#askBtn")
        assert tab.text("#changeQuote") == f"“make it yellow {MARKUP}”"
        assert page.locator("#changeStart").is_disabled()
        page.keyboard.press("Escape")
        assert not page.locator("#changeConfirm").is_visible()
        shot(tab, "project")
        tab.assert_clean()
    finally:
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open("p/car")
    try:
        phone.page.wait_for_function("() => document.querySelector('#turn').complete")
        phone.no_sideways_scroll()
        shot(phone, "project-phone", full=False)
        phone.assert_clean()
    finally:
        phone.close()


@pytest.mark.browser
def test_browser_the_project_page_says_what_moves(
    browser: Any, running: Running, projects: Path, tmp_path: Path
) -> None:
    """A free build with joints (a rolling chassis from the moving modules): the page lists
    what moves under the checker's verdict, in plain words, and the run records it."""
    from bricksnap.lab import ldraw_lib
    from bricksnap.lab.modules import place_module

    if not ldraw_lib.zip_path().is_file():
        pytest.skip("the LDraw library is not on this machine")
    text = ""
    for z, name in ((-40, "front"), (40, "back")):
        got = place_module(text, "wheels-small", 72, 0, x=0, z=z, joint_name=name)
        text += "\n".join(got.lines) + "\n"
    text += "1 4 0 -31 0 0 0 1 0 1 0 -1 0 0 3034.dat\n"
    ldr = tmp_path / "cart.ldr"
    ldr.write_text(text, "utf-8")
    folder = freebuild.import_run(projects, ldr, words="A cart that rolls", name="Cart")
    about = freebuild.describe(folder)
    assert about["moves"] == [
        "'front' (wheels-small, lines 1 to 5): the wheels turn freely all the way round, and "
        "the model rests on its wheels.",
        "'back' (wheels-small, lines 7 to 11): the wheels turn freely all the way round, and "
        "the model rests on its wheels.",
    ]
    tab = Tab(browser, running.url, width=1280, height=900).open(f"p/{folder.name}")
    try:
        page = tab.page
        page.wait_for_selector("#moves li")
        assert page.locator("#moves li").count() == 2
        assert tab.text("#movesTitle") == "What moves"
        assert "'front' (wheels-small, lines 1 to 5): the wheels turn freely" in tab.text("#moves")
        shot(tab, "project-moves")
        tab.assert_clean()
    finally:
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open(f"p/{folder.name}")
    try:
        phone.page.wait_for_selector("#moves li")
        phone.no_sideways_scroll()
        phone.page.locator("#movesBox").scroll_into_view_if_needed()
        shot(phone, "project-moves-phone", full=False)
        phone.assert_clean()
    finally:
        phone.close()
    # a model with nothing that moves shows no such list
    car = Tab(browser, running.url, width=1280, height=900).open("p/car")
    try:
        car.page.wait_for_function("() => document.querySelector('#turn').complete")
        assert car.page.locator("#movesBox").is_hidden()
    finally:
        car.close()


# ---- the set designers' guide (lab.guide), chosen per model ----------------------------------


def test_the_guide_is_remembered_and_kept_by_a_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    usual = freebuild.create(tmp_path, "a boat")
    assert freebuild.read_meta(usual)["guide"] is False
    entry = freebuild.build(usual)
    assert fake.calls[-1]["guide"] is False
    assert entry["guide"] is False and entry["playbook"] is None
    assert freebuild.describe(usual)["guide"] is False

    folder = freebuild.create(tmp_path, "a sunflower in a pot", guide=True)
    assert freebuild.read_meta(folder)["guide"] is True
    entry = freebuild.build(folder)
    assert fake.calls[-1]["guide"] is True
    assert entry["guide"] is True and entry["playbook"] == "Plant, 100 parts"
    entry = freebuild.build(folder, "make the pot blue")
    assert fake.calls[-1]["guide"] is True and fake.calls[-1]["change_of"]
    assert entry["kind"] == "change" and entry["guide"] is True
    about = freebuild.describe(folder)
    assert about["guide"] is True
    assert [(r["guide"], r["playbook"]) for r in about["runs"]] == [
        (True, "Plant, 100 parts"),
        (True, "Plant, 100 parts"),
    ]
    record = json.loads((folder / "runs" / "0002" / "record.json").read_text())
    assert record["guide"] is True and record["playbook"] == "Plant, 100 parts"
    assert record["art"] is True and record["brief"] == SAMPLE_BRIEF
    assert record["brief_story"] == {
        "versions": 2,
        "carried_from": None,
        "carried": False,
        "parts_before": 0,
        "last_reason": "orange petals read better than yellow",
    }
    assert record["critique"] == SAMPLE_CRITIQUE and record["critiques"] == 2
    assert record["first_no"] == ["thin", "glass", "stance"]
    assert record["built_without_brief"] is False and record["ended_without_critique"] is False
    assert about["brief"] == SAMPLE_BRIEF and about["critique"] == SAMPLE_CRITIQUE
    # the change was given the first build's brief to build to, and told the model's size
    assert fake.calls[-1]["brief"] == SAMPLE_BRIEF and fake.calls[-1]["brief_run"] == 1
    assert fake.calls[-1]["parts"] == 20 and fake.calls[1]["parts"] == 80  # 2 parts: held to 20
    assert freebuild.describe(usual)["brief"] is None and freebuild.describe(usual)["art"] is None
    assert "brief" not in json.loads((usual / "runs" / "0001" / "record.json").read_text())
    assert "parts" not in fake.calls[0] or not fake.calls[0].get("guide")
    # a project made before the choice existed has it off; an imported run does not know
    meta = freebuild.read_meta(usual)
    del meta["guide"]
    freebuild.save_meta(usual, meta)
    freebuild.build(usual, "make it longer")
    assert fake.calls[-1]["guide"] is False
    imported = freebuild.import_run(tmp_path, STUDY / "cat.ldr", words="a cat")
    assert freebuild.describe(imported)["runs"][0]["guide"] is None


def test_make_with_the_guide(capsys: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from bricksnap import cli

    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    projects = tmp_path / "projects"
    code, out, err = _cli(capsys, "make", "a fire truck", "--guide", "--dir", str(projects))
    assert code == 0, err
    assert cli.GUIDE_WORDS in out and fake.calls[0]["guide"] is True
    assert freebuild.read_meta(projects / "a-fire-truck")["guide"] is True
    monkeypatch.chdir(tmp_path)
    code, out, err = _cli(capsys, "make", "--change", "a-fire-truck", "make it blue", "--guide")
    assert code == 2 and "--guide and --picture go only with a new model" in err
    code, out, err = _cli(capsys, "make", "--change", "a-fire-truck", "make it blue")
    assert code == 0, err
    assert "the change is made so too" in out and fake.calls[1]["guide"] is True
    code, out, err = _cli(capsys, "make", "a cat", "--dir", str(projects))
    assert code == 0 and cli.GUIDE_WORDS not in out and fake.calls[2]["guide"] is False
    code, out, err = _cli(capsys, "make", "--import", str(STUDY / "cat.ldr"), "--guide")
    assert code == 2 and "--import goes only with" in err


def test_a_free_build_with_the_guide_over_the_web(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    for bad in ("yes", 1, None):
        status, data = running.post("/api/free", {"words": "a cat", "guide": bad, **AGREED})
        assert status == 400 and "set designers do" in data["error"], bad
    assert fake.calls == []
    status, data = running.post(
        "/api/free", {"words": "a sunflower", "name": "Sunflower", "guide": True, **AGREED}
    )
    assert status == 202
    job = running.wait(data["job"])
    assert job["state"] == "done", job
    assert any("the way set designers do" in line for line in job["progress"])
    assert fake.calls[0]["guide"] is True
    info = running.get_json("/api/p/sunflower")
    assert info["guide"] is True
    assert info["runs"][0]["guide"] is True and info["runs"][0]["playbook"] == "Plant, 100 parts"
    assert info["brief"] == SAMPLE_BRIEF and info["critique"] == SAMPLE_CRITIQUE
    assert info["art"] is True and info["brief_story"]["versions"] == 2
    assert info["first_no"] == ["thin", "glass", "stance"] and info["critiques"] == 2
    assert info["ended_without_critique"] is False and info["built_without_brief"] is False
    said = freebuild.time_and_cost(80)
    assert any(said in line for line in job["progress"])
    status, data = running.post("/api/p/sunflower/change", {"words": "taller", **AGREED})
    assert running.wait(data["job"])["state"] == "done" and fake.calls[1]["guide"] is True
    status, data = running.post("/api/free", {"words": "a boat", "name": "Boat", **AGREED})
    assert running.wait(data["job"])["state"] == "done" and fake.calls[2]["guide"] is False
    boat = running.get_json("/api/p/boat")
    assert boat["guide"] is False and boat["brief"] is None and boat["critique"] is None
    assert boat["art"] is None and boat["ended_without_critique"] is None


@pytest.mark.browser
def test_browser_the_guide_box_and_what_the_page_says(
    browser: Any, running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeLab(
        model=(STUDY / "flower.ldr").read_text(),
        report=(STUDY / "flower-report.txt").read_text(),
    )
    monkeypatch.setattr(lab_run, "build", fake)
    tab = Tab(browser, running.url, width=1280, height=900).open()
    try:
        page = tab.page
        page.fill("#freeWords", "a sunflower in a pot")
        page.locator("#freeMore summary").click()
        page.fill("#freeName", "Sunflower")
        box = page.locator("#freeGuide")
        assert box.is_visible() and box.is_checked()  # on unless taken off: the main way now
        label = page.locator("label:has(#freeGuide)").text_content() or ""
        assert "Design it first, then build it the way set designers do" in label
        hint = page.locator("label:has(#freeGuide) + .hint").text_content() or ""
        assert "art direction" in hint and "judges its own pictures" in hint
        page.locator("#freeParts").fill("400")
        assert "big models take longer and use more of your subscription" in tab.text(
            "#freePartsHint"
        )
        assert tab.text("#freeCostFull") == freebuild.time_and_cost(400)
        assert tab.text("#freeCost").endswith("(an estimate).")  # no build this large on record
        page.locator("#freeParts").fill("80")
        assert tab.text("#freeCostFull") == freebuild.time_and_cost(80)
        assert "is stopped at 90 minutes" in tab.text("#freeCostFull")
        box.uncheck()
        assert "designed first" not in tab.text("#freeCost")
        box.check()
        assert "designed first" in tab.text("#freeCost")
        page.select_option("#freeModel", "claude-opus-5-5")
        assert tab.text("#freeCostFull") == freebuild.time_and_cost(80, "claude-opus-5-5")
        assert "$1 to $3 of your Claude subscription (an estimate)" in tab.text("#freeCost")
        page.select_option("#freeModel", "claude-fable-5-2")
        page.check("#freeUnderstood")
        shot(tab, "home-guide")
        page.click("#freeGo")
        page.wait_for_url("**/p/sunflower", timeout=20000)
        page.wait_for_selector("#runs li", timeout=30000)
        assert fake.calls[0]["guide"] is True
        assert fake.calls[0]["model"] == "claude-fable-5-2"
        tab.assert_clean()
    finally:
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open()
    try:
        phone.page.locator("#freeMore summary").click()
        phone.page.locator("#freeGuide").scroll_into_view_if_needed()
        phone.no_sideways_scroll()
        shot(phone, "home-guide-phone", full=False)
        phone.assert_clean()
    finally:
        phone.close()
    page_tab = Tab(browser, running.url, width=1280, height=900).open("p/sunflower")
    try:
        page = page_tab.page
        page.wait_for_selector("#runs li")
        assert page.locator("#guideNote").is_visible()
        assert "Designed first, then built the way set designers do" in page_tab.text("#guideNote")
        run_text = page_tab.text("#runs .rguide")
        assert run_text == "Built the way set designers do; playbook it asked for: Plant, 100 parts"
        # pictures first: the art direction below them, then the notes, then the critique
        assert page.locator("#artCard").is_visible() and page.locator("#critiqueCard").is_visible()
        art_box = page.locator("#artCard").bounding_box()
        turn_box = page.locator("#turnBox").bounding_box()
        notes_box = page.locator("#notesCard").bounding_box()
        critique_box = page.locator("#critiqueCard").bounding_box()
        assert art_box and turn_box and notes_box and critique_box
        assert turn_box["y"] + turn_box["height"] <= art_box["y"]
        assert art_box["y"] + art_box["height"] <= notes_box["y"]
        assert notes_box["y"] + notes_box["height"] <= critique_box["y"]
        assert turn_box["y"] < 400  # the pictures are on the first screen
        assert page_tab.text("#artTitle") == "The AI's art direction"
        assert page_tab.text("#artSays") == (
            "Written before the first part: the look it then built to. Changed once; the last "
            "reason: “orange petals read better than yellow”. This is the last version."
        )
        terms = page.locator("#artBrief dt").all_text_contents()
        assert terms == ["Scale", "Colours", "Pattern"]  # the rest behind "more"
        assert (
            page.locator("#artMore").is_visible() and not page.locator("#artBriefMore").is_visible()
        )
        page.locator("#artMore summary").click()
        more = page.locator("#artBriefMore dt").all_text_contents()
        assert more == ["Shapes", "Built sideways", "Kept thin", "Studs", "Glass and stance"]
        flags = page.locator("#critiqueFlags li").all_text_contents()
        assert flags[0].startswith("Its first critique said no to 3 questions; it was sent back")
        assert flags[1].startswith("The brief said: Dark Green 60%")
        assert "Colours by bulk: Dark Green 41%, Reddish Brown 30%" in page_tab.text("#facts")
        assert page.locator("#artBrief .swatch").count() == 4
        colour = page.locator("#artBrief .swatch").first.evaluate(
            "e => getComputedStyle(e).backgroundColor"
        )
        assert colour == "rgb(0, 69, 26)"
        assert "Dark Green (288): stems and leaves, 60%" in page_tab.text("#artBrief")
        assert page_tab.text("#critiqueTitle") == "Its own critique"
        assert page_tab.text("#critiqueSays") == "8 yes, 2 no."
        items = page.locator("#critique li")
        assert items.count() == 10
        assert [items.nth(k).get_attribute("class") for k in range(3)] == ["no", "no", "yes"]
        assert "Is everything thin that is thin on the real thing?" in (
            items.nth(0).text_content() or ""
        )
        assert "the leaves still hang on thick clips" in (items.nth(0).text_content() or "")
        shot(page_tab, "project-guide")
        page.locator("#artCard").screenshot(path=str(ARTIFACTS / "free-art-direction.png"))
        page.locator("#critiqueCard").screenshot(path=str(ARTIFACTS / "free-critique.png"))
        page.fill("#askText", "make the pot blue")
        page.click("#askBtn")
        assert freebuild.time_and_cost(58) in page_tab.text("#changeTime")  # its own size
        page_tab.assert_clean()
    finally:
        page_tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open("p/sunflower")
    try:
        phone.page.wait_for_selector("#runs li")
        phone.no_sideways_scroll()
        box = phone.page.locator("#turnBox").bounding_box()
        assert box and box["y"] < 700  # the pictures on a phone's first screen
        shot(phone, "project-guide-phone-first-screen", full=False)
        phone.page.locator("#runs").scroll_into_view_if_needed()
        shot(phone, "project-guide-phone", full=False)
        phone.assert_clean()
    finally:
        phone.close()
    car = Tab(browser, running.url, width=1280, height=900).open("p/car")
    try:
        car.page.wait_for_selector("#runs li")
        assert car.page.locator("#guideNote").is_hidden()
        assert car.page.locator("#runs .rguide").count() == 0  # an imported run does not know
        assert car.page.locator("#artCard").is_hidden()  # an old run: neither block
        assert car.page.locator("#critiqueCard").is_hidden()
    finally:
        car.close()


def _guided_run(projects: Path, name: str, record: dict[str, Any], notes: str = "") -> Path:
    """A free build with one guided run whose record is ``record`` (what lab.art keeps)."""
    folder = freebuild.create(projects, f"a {name}", name=name, folder=name, guide=True)
    freebuild.keep_model(
        folder,
        1,
        kind="first",
        words=f"a {name}",
        text=TWO_BRICKS,
        report=CLEAN_REPORT,
        notes=notes,
        record={"guide": True, "playbook": "Plant, 100 parts", "art": True, **record},
    )
    return folder


@pytest.mark.browser
def test_browser_the_flags_a_guided_run_keeps_and_hostile_text(
    browser: Any, running: Running, projects: Path
) -> None:
    hostile = {
        **SAMPLE_BRIEF,
        "scale": MARKUP,
        "pattern": MARKUP,
        "sideways": MARKUP,
        "thin": MARKUP,
        "studs": MARKUP,
        "glass": MARKUP,
        "why_more": MARKUP,
        "colours": [
            {"code": 288, "job": MARKUP, "share": MARKUP, "name": MARKUP, "value": "red;x:1"}
        ],
        "shapes": [{"shape": MARKUP, "part": MARKUP}] * 3,
    }
    critique = {
        **SAMPLE_CRITIQUE,
        "answers": [{**a, "note": MARKUP, "question": MARKUP} for a in SAMPLE_CRITIQUE["answers"]],
        "changed_after": True,
        "mismatches": [MARKUP],
        "facts": {**SAMPLE_CRITIQUE["facts"], "looks": [MARKUP]},
    }
    _guided_run(
        projects,
        "xss",
        {
            "brief": hostile,
            "briefs": [{"n": 1, "brief": hostile, "reason": MARKUP, "parts_before": 12}],
            "critique": critique,
            "critiques": 1,
        },
        notes=MARKUP,
    )
    _guided_run(projects, "nobrief", {"brief": None, "briefs": [], "built_without_brief": True})
    _guided_run(
        projects,
        "carried",
        {
            "brief": SAMPLE_BRIEF,
            "briefs": [
                {"n": 1, "brief": SAMPLE_BRIEF, "carried": True, "from_run": 3, "parts_before": 58}
            ],
        },
    )
    tab = Tab(browser, running.url, width=1280, height=900).open("p/xss")
    try:
        page = tab.page
        page.wait_for_selector("#artCard:not([hidden])")
        page.locator("#artMore summary").click()
        assert MARKUP in tab.text("#artBrief") and MARKUP in tab.text("#artBriefMore")
        assert tab.text("#artSays") == "Written after 12 parts were already in."
        assert MARKUP in tab.text("#critique") and MARKUP in tab.text("#facts")
        flags = page.locator("#critiqueFlags li").all_text_contents()
        assert any("changed after this critique" in f for f in flags)
        assert MARKUP in flags
        assert page.evaluate("() => window.__pwned") is None
        assert page.locator("img[src='x']").count() == 0
        shot(tab, "project-hostile")
        tab.assert_clean()
    finally:
        tab.close()
    tab = Tab(browser, running.url, width=1280, height=900).open("p/nobrief")
    try:
        page = tab.page
        page.wait_for_selector("#artCard:not([hidden])")
        assert tab.text("#artSays") == (
            "The AI wrote no art direction for this run: it built without one."
        )
        assert tab.text("#critiqueSays").startswith("The run ended without a critique")
        assert page.locator("#critique li").count() == 0
        tab.assert_clean()
    finally:
        tab.close()
    tab = Tab(browser, running.url, width=1280, height=900).open("p/carried")
    try:
        tab.page.wait_for_selector("#artCard:not([hidden])")
        assert tab.text("#artSays").startswith("Carried over from run 3, when the model was built")
        tab.assert_clean()
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_the_page_and_the_server_give_the_same_time_and_cost(
    browser: Any, running: Running
) -> None:
    tab = Tab(browser, running.url, width=800, height=600).open()
    try:
        got = tab.page.evaluate(
            """async () => {
                const m = await import('/viewer/app.js');
                const out = [];
                for (let n = 20; n <= 600; n++) out.push([m.freeEstimate(n), m.freeTimeAndCost(n)]);
                out.push([m.freeEstimate(6000), m.freeTimeAndCost('x')]);
                return out;
            }"""
        )
        for n, (estimate, words) in zip(range(20, 601), got, strict=False):
            assert estimate == freebuild.estimate(n), n
            assert words == freebuild.time_and_cost(n), n
        assert got[-1][0] == freebuild.estimate(6000)
        assert got[-1][1] == freebuild.time_and_cost("x")
    finally:
        tab.close()


# ---- what a free build is built from: pictures, a 3D model, the choice of Claude ---------------


def photo(size: tuple[int, int] = (80, 40), fmt: str = "JPEG", orientation: int = 6) -> bytes:
    """A small photo as a phone saves it: EXIF with the camera, a GPS position and a turn."""
    im = Image.new("RGB", size, (200, 30, 30))
    im.paste((30, 30, 200), (0, 0, size[0] // 2, size[1]))  # left half blue
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # Make
    exif[0x0112] = orientation
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2] = "N", (51.0, 30.0, 0.0)
    out = io.BytesIO()
    im.save(out, fmt, exif=exif.tobytes())
    return out.getvalue()


def form(fields: dict[str, str], files: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    boundary = "FreeBuildTestBoundary"
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        out.write(value.encode() + b"\r\n")
    for field, filename, data in files:
        out.write(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        )
        out.write(data + b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


AGREED_FORM = {"understood": "true", "understood_runs": "1"}


def post_form(
    running: Running, fields: dict[str, str], files: list[tuple[str, str, bytes]], **kw: Any
) -> tuple[int, Any]:
    body, ctype = form(fields, files)
    kw.setdefault("token", True)
    status, _, data = running.request(
        "/api/free", "POST", body=body, headers={"Content-Type": ctype}, **kw
    )
    return status, json.loads(data) if data.startswith(b"{") else data


def test_a_picture_is_turned_upright_shrunk_and_stripped_of_everything_else() -> None:
    for fmt in ("JPEG", "WEBP"):
        png = freebuild.clean_picture(photo(fmt=fmt))
        with Image.open(io.BytesIO(png)) as im:
            assert im.format == "PNG" and im.size == (40, 80)  # turned as the camera was held
            assert not im.info.get("exif") and not im.getexif() and "icc_profile" not in im.info
            blue = im.getchannel("B").getpixel((20, 4))
            assert isinstance(blue, int) and blue > 150  # the blue half is now on top
        assert b"TestCam" not in png and b"GPS" not in png and b"Exif" not in png
    big = io.BytesIO()
    Image.new("RGBA", (3200, 1000), (0, 0, 0, 0)).save(big, "PNG")
    with Image.open(io.BytesIO(freebuild.clean_picture(big.getvalue()))) as im:
        assert im.size == (1600, 500) and im.mode == "RGB"
        assert im.getpixel((5, 5)) == (255, 255, 255)  # transparent is white
    for data, words in (
        (b"", "empty"),
        (b"GIF89a" + b"\0" * 40, "not a picture BrickSnap can use"),
        (b"<svg></svg>", "not a picture BrickSnap can use"),
        (b"\0\0\0\x18ftypheic" + b"\0" * 40, "HEIC"),
        (photo()[:200], "could not be read"),
        (b"x" * (freebuild.MAX_PICTURE_BYTES + 1), "up to 8 MB"),
        (photo(size=(10, 10)), "too small"),
    ):
        with pytest.raises(freebuild.FreeBuildError, match=words):
            freebuild.clean_picture(data)


def test_the_cost_words_for_each_model() -> None:
    fable = freebuild.time_and_cost(80)
    assert freebuild.time_and_cost(80, "claude-fable-5-2") == fable
    opus = freebuild.time_and_cost(80, "claude-opus-5-5")
    assert "with Claude Opus 5.5 it should use about $1 to $3" in opus and "$2 to $6" in fable
    assert "its list price is half, and one build with it is on record" in opus
    assert list(freebuild.MODELS)[0] == lab_run.DEFAULT_MODEL == "claude-fable-5-2"
    assert freebuild.other_model(None) == "claude-opus-5-5"
    assert freebuild.other_model("claude-opus-5-5") == "claude-fable-5-2"


def test_pictures_and_a_3d_model_over_the_web_and_kept_for_a_change(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch, pawn_path: Path
) -> None:
    fake = FakeLab()
    monkeypatch.setattr(lab_run, "build", fake)
    status, data = post_form(
        running,
        {"words": "", "parts": "120", "model": "claude-opus-5-5", "guide": "true", **AGREED_FORM},
        [
            ("picture", "IMG_0001.JPG", photo()),
            ("picture", "../../secret.webp", photo(fmt="WEBP")),
            ("model_file", "Pawn Piece.stl", pawn_path.read_bytes()),
        ],
    )
    assert status == 202, data
    assert data["project"] == "pawn-piece"  # no words: named after the 3D file
    job = running.wait(data["job"])
    assert job["state"] == "done", job
    assert "It is shown 3 reference pictures of what to build" in job["progress"]
    assert any(line.startswith("One AI run, by Claude Opus 5.5.") for line in job["progress"])
    folder = projects / "pawn-piece"
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5" and call["guide"] is True
    assert [p.name for p in call["references"]] == [
        "picture-1.png",
        "picture-2.png",
        "model-sheet.png",
    ]
    assert "Build what the reference pictures show" in call["task"]
    meta = freebuild.read_meta(folder)
    assert meta["words"] == "" and meta["model"] == "claude-opus-5-5"
    assert meta["reference_pictures"] == ["picture-1.png", "picture-2.png"]
    assert meta["reference_model"] == {
        "file": "pawn-piece.stl",
        "name": "Pawn Piece.stl",
        "sheet": "model-sheet.png",
    }
    for f in ("picture-1.png", "picture-2.png", "model-sheet.png", "pawn-piece.stl"):
        assert (folder / "references" / f).is_file()
    assert b"TestCam" not in (folder / "references" / "picture-1.png").read_bytes()
    assert not list((projects / ".incoming").glob("*"))  # nothing left behind
    info = running.get_json("/api/p/pawn-piece")
    assert info["model"] == "claude-opus-5-5" and info["model_name"] == "Claude Opus 5.5"
    assert info["reference_model"]["name"] == "Pawn Piece.stl"
    assert info["runs"][0]["model"] is None  # the fake's record does not say
    for url in [*info["reference_pictures"], info["reference_model"]["sheet"]]:
        status, headers, body = running.request(url)
        assert status == 200 and body.startswith(b"\x89PNG"), url
    assert running.request("/p/pawn-piece/files/references/pawn-piece.stl")[0] == 404

    status, data = running.post("/api/p/pawn-piece/change", {"words": "make it red", **AGREED})
    assert running.wait(data["job"])["state"] == "done"
    call = fake.calls[1]
    assert call["model"] == "claude-opus-5-5" and len(call["references"]) == 3  # the same
    assert call["change_of"] == freebuild.NO_WORDS
    status, data = running.post(
        "/api/p/pawn-piece/change",
        {"words": "bluer", "model": "claude-fable-5-2", **AGREED},
    )
    assert running.wait(data["job"])["state"] == "done"
    assert fake.calls[2]["model"] == "claude-fable-5-2"
    assert freebuild.read_meta(folder)["model"] == "claude-fable-5-2"  # kept from now on


@pytest.mark.parametrize(
    ("fields", "files", "status", "words"),
    [
        ({"words": "a cat"}, [("picture", "a.png", b"not a picture")], 400, "not a picture"),
        (
            {"words": "a cat"},
            [("picture", f"{k}.jpg", photo()) for k in range(5)],
            400,
            "at most 4",
        ),
        ({"words": "a cat"}, [("model_file", "cat.exe", b"x")], 400, "cannot open cat.exe"),
        ({"words": "a cat"}, [("model_file", "cat.stl", b"")], 400, "is empty"),
        (
            {"words": ""},
            [("model_file", "cat.stl", b"solid x\nendsolid x\n")],
            202,
            "",
        ),
        ({"words": "a cat", "model": "claude-haiku-5-5"}, [], 400, "Choose which Claude"),
        ({"words": ""}, [], 400, "Say in words"),
    ],
)
def test_what_a_free_build_is_built_from_is_checked(
    running: Running,
    monkeypatch: pytest.MonkeyPatch,
    fields: dict[str, str],
    files: list[Any],
    status: int,
    words: str,
) -> None:
    monkeypatch.setattr(lab_run, "build", FakeLab())
    got, data = post_form(running, {**fields, **AGREED_FORM}, files)
    assert got == status, data
    if status == 202:  # a 3D file the converter cannot read fails the job plainly, makes nothing
        job = running.wait(data["job"])
        assert job["state"] == "failed" and "no triangles" in job["error"]
        assert not (running.app.root / data["project"]).exists()
    else:
        assert words in data["error"]
        assert sorted(p.name for p in running.app.root.iterdir() if p.name[0] != ".") == [
            "car",
            "pawn",
        ]
    status, data = running.post("/api/free", {"words": "a cat", "model": "gpt", **AGREED})
    assert status == 400 and "Claude Fable 5.2 or Claude Opus 5.5" in data["error"]


def test_a_free_build_form_needs_the_token_and_the_agreement(running: Running) -> None:
    files = [("picture", "a.jpg", photo())]
    assert post_form(running, {"words": "a cat", **AGREED_FORM}, files, token=False)[0] == 403
    status, data = post_form(running, {"words": "a cat"}, files)
    assert status == 400 and "was not started" in data["error"]
    status, data = post_form(running, {"words": "a cat", **AGREED_FORM}, files, host="evil.example")
    assert status == 404
    assert running.get_json("/api/projects")["jobs"] == []


LIMIT_LINE = "You've hit your Fable limit · resets 2am (Etc/UTC)"


def test_the_usage_limit_is_said_plainly_with_the_other_model(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Limited(FakeLab):
        def __call__(self, task: str, out: Path, **kw: Any) -> dict[str, Any]:
            self.calls.append({"task": task, "out": out, **kw})
            out.mkdir(parents=True)
            record = {
                "ok": False,
                "error": "Your Claude subscription has reached its Fable usage limit ...",
                "usage_limit": LIMIT_LINE,
                "limit_resets": "2am (Etc/UTC)",
                "turns": 1,
                "seconds": 1.0,
            }
            (out / "session.json").write_text(json.dumps(record), "utf-8")
            return record

    monkeypatch.setattr(lab_run, "build", Limited())
    status, data = running.post("/api/free", {"words": "a boat", **AGREED})
    job = running.wait(data["job"])
    assert job["state"] == "failed"
    assert job["error"] == (
        "Your Claude subscription has reached its usage limit for Claude Fable 5.2; it resets "
        "2am (Etc/UTC). Nothing was built. You can choose Claude Opus 5.5 instead and try "
        "again, or wait until the limit resets; BrickSnap does not switch by itself."
    )
    assert job["todo"].startswith("Choose “Claude Opus 5.5” under “Options”")
    status, data = running.post("/api/p/car/change", {"words": "bluer", **AGREED})
    job = running.wait(data["job"])
    assert "Nothing was changed." in job["error"] and "Your model is safe" in job["todo"]


def test_the_runner_reads_the_usage_limit_from_claude_codes_lines() -> None:
    """The lines Claude Code printed when the limit was reached on 23 November, as stream-json
    carries them (the text, its "error" mark and the rejected rate-limit event; the time zone
    and the ids changed)."""
    lines = [
        {"type": "system", "subtype": "init", "model": "claude-fable-5-2", "tools": []},
        {
            "type": "rate_limit_event",
            "rate_limit_info": {
                "status": "rejected",
                "resetsAt": 1795510800,
                "rateLimitType": "seven_day_overage_included",
                "overageStatus": "rejected",
                "isUsingOverage": False,
            },
        },
        {
            "type": "assistant",
            "message": {
                "id": "00000000-0000-0000-0000-000000000000",
                "model": "<synthetic>",
                "role": "assistant",
                "content": [{"type": "text", "text": LIMIT_LINE}],
            },
            "error": "rate_limit",
        },
        {"type": "result", "subtype": "success", "is_error": True, "result": LIMIT_LINE},
    ]
    parser = runner.StreamParser()
    for event in lines:
        parser.feed(json.dumps(event))
    assert parser.usage_limit == LIMIT_LINE and parser.limit_resets() == "2am (Etc/UTC)"
    assert parser.limit_error() == (
        "Your Claude subscription has reached its Fable usage limit (Claude Code said so "
        "instead of answering), so the run stopped. The limit resets 2am (Etc/UTC)."
    )
    quiet = runner.StreamParser()  # no words of when: the event's time, on this clock
    quiet.feed(json.dumps(lines[1]))
    quiet.feed(json.dumps({**lines[3], "result": "You've hit your limit"}))
    assert quiet.usage_limit and quiet.limit_resets().startswith("on ")
    ordinary = runner.StreamParser()  # the model saying the words is not a limit
    ordinary.feed(
        json.dumps({"type": "assistant", "message": {"content": lines[2]["message"]["content"]}})
    )
    assert ordinary.usage_limit == ""


@pytest.mark.browser
def test_browser_the_prompt_bar_with_pictures_and_a_3d_model(
    browser: Any,
    running: Running,
    projects: Path,
    monkeypatch: pytest.MonkeyPatch,
    pawn_path: Path,
) -> None:
    fake = FakeLab(
        model=(STUDY / "flower.ldr").read_text(),
        report=(STUDY / "flower-report.txt").read_text(),
    )
    monkeypatch.setattr(lab_run, "build", fake)
    with Image.open(STUDY / "flower.png") as sheet:
        drawn = io.BytesIO()
        sheet.convert("RGB").crop((0, 0, 560, sheet.height)).save(drawn, "JPEG")
    tab = Tab(browser, running.url, width=1280, height=900).open()
    try:
        page = tab.page
        page.fill("#freeWords", "a sunflower in a pot, like this drawing")
        page.set_input_files(
            "#freeFiles",
            [
                {"name": "drawing.jpg", "mimeType": "image/jpeg", "buffer": drawn.getvalue()},
                {"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": photo((400, 300))},
            ],
        )
        assert page.locator("#freeThumbs li").count() == 2
        page.locator("#freeThumbs li").nth(1).locator("button").click()  # take one back
        assert page.locator("#freeThumbs li").count() == 1
        page.set_input_files("#freeFiles", str(pawn_path))
        assert page.locator("#freeThumbs li").count() == 2
        assert "pawn.stl" in tab.text("#freeThumbs .model3d")
        page.locator("#freeMore summary").click()
        page.select_option("#freeModel", "claude-opus-5-5")
        says = tab.text("#freeSays")
        assert "your words, your picture and pictures of pawn.stl from five sides" in says
        assert "One AI run by Claude Opus 5.5" in says
        page.wait_for_function(
            "() => [...document.querySelectorAll('#freeThumbs img')].every(i => i.complete)"
        )
        page.check("#freeUnderstood")
        shot(tab, "home-bar-with-pictures", full=False)
        page.click("#freeGo")
        page.wait_for_url("**/p/a-sunflower-in-a-pot", timeout=20000)
        page.wait_for_selector("#runs li", timeout=30000)
        page.wait_for_selector("#refPics li")
        assert page.locator("#refPics li").count() == 2
        assert "Built from: pawn.stl" in tab.text("#refPics")
        page.wait_for_function(
            "() => [...document.querySelectorAll('#refPics img')]"
            ".every(i => i.complete && i.naturalWidth > 0)"
        )
        call = fake.calls[0]
        assert call["model"] == "claude-opus-5-5"
        assert [p.name for p in call["references"]] == ["picture-1.png", "model-sheet.png"]
        shot(tab, "project-built-from")
        page.fill("#askText", "make the pot blue")
        page.click("#askBtn")
        assert page.locator("#changeModel").input_value() == "claude-opus-5-5"
        assert "with the pictures it was built from" in tab.text("#changeSends")
        assert freebuild.time_and_cost(58, "claude-opus-5-5") in tab.text("#changeTime")
        tab.assert_clean()
    finally:
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open()
    try:
        phone.page.set_input_files(
            "#freeFiles",
            [{"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": photo((400, 300))}],
        )
        phone.no_sideways_scroll()
        shot(phone, "home-bar-phone", full=False)
        phone.assert_clean()
    finally:
        phone.close()


def limited_record(resets_at: float) -> dict[str, Any]:
    """What lab.run.build records for a session stopped by the usage limit, read by the
    runner from Claude Code's lines as they came on 23 November (time zone and ids changed)."""
    parser = runner.StreamParser()
    for event in (
        {"type": "system", "subtype": "init", "model": "claude-fable-5-2", "tools": []},
        {
            "type": "rate_limit_event",
            "rate_limit_info": {"status": "rejected", "resetsAt": resets_at},
        },
        {
            "type": "assistant",
            "message": {"model": "<synthetic>", "content": [{"type": "text", "text": LIMIT_LINE}]},
            "error": "rate_limit",
        },
        {"type": "result", "subtype": "success", "is_error": True, "result": LIMIT_LINE},
    ):
        parser.feed(json.dumps(event))
    return {
        "ok": False,
        "error": parser.limit_error(),
        "usage_limit": parser.usage_limit,
        "limit_resets": parser.limit_resets(),
        "limit_resets_at": parser.resets_at,
        "turns": 1,
        "seconds": 1.0,
    }


class LimitedLab(FakeLab):
    def __init__(self, resets_at: float) -> None:
        super().__init__()
        self.resets_at = resets_at

    def __call__(self, task: str, out: Path, **kw: Any) -> dict[str, Any]:
        self.calls.append({"task": task, "out": out, **kw})
        out.mkdir(parents=True)
        record = limited_record(self.resets_at)
        (out / "session.json").write_text(json.dumps(record), "utf-8")
        return record


def test_a_usage_limit_is_remembered_until_it_resets(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import time

    later = time.time() + 3 * 86400
    monkeypatch.setattr(lab_run, "build", LimitedLab(later))
    status, data = running.post("/api/free", {"words": "a boat", **AGREED})
    assert running.wait(data["job"])["state"] == "failed"
    [limit] = running.get_json("/api/projects")["limits"]
    assert limit["model"] == "claude-fable-5-2" and limit["until"] == later
    assert limit["other"] == "claude-opus-5-5" and limit["other_name"] == "Claude Opus 5.5"
    assert limit["until_words"] == freebuild._until_words(later)
    assert (projects / ".state" / "usage-limits.json").is_file()
    assert freebuild.usage_limits(projects, now=later + 1) == []  # over once it has reset
    names = [c["project"] for c in running.get_json("/api/projects")["projects"]]
    assert ".state" not in names
    monkeypatch.setattr(lab_run, "build", FakeLab())  # a run with it that works: forgotten
    status, data = running.post("/api/free", {"words": "a plane", **AGREED})
    assert running.wait(data["job"])["state"] == "done"
    assert running.get_json("/api/projects")["limits"] == []


@pytest.mark.browser
def test_browser_the_bar_chooses_the_other_claude_at_a_usage_limit(
    browser: Any, running: Running, projects: Path
) -> None:
    import time

    tab = Tab(browser, running.url, width=1280, height=900).open()
    try:
        page = tab.page
        assert page.locator("#freeModel").input_value() == "claude-fable-5-2"
        assert page.locator("#freeLimit").is_hidden()
        page.locator("#freeMore summary").click()
        page.select_option("#freeModel", "claude-opus-5-5")
        tab.open()  # the person's own choice is remembered in this browser
        assert page.locator("#freeModel").input_value() == "claude-opus-5-5"
        page.locator("#freeMore summary").click()
        page.select_option("#freeModel", "claude-fable-5-2")
        later = time.time() + 3 * 86400
        error = freebuild.usage_limit_error(
            "claude-fable-5-2", "2am (Etc/UTC)", {"has_model": False}, "first", later
        )
        freebuild.note_limit(projects, error)
        tab.open()
        page.wait_for_function("() => !document.querySelector('#freeLimit').hidden")
        assert page.locator("#freeModel").input_value() == "claude-opus-5-5"
        when = freebuild._until_words(later)
        assert tab.text("#freeLimit") == (
            f"Claude Fable 5.2 is at its usage limit until {when}; Claude Opus 5.5 is chosen."
        )
        assert "One AI run by Claude Opus 5.5" in tab.text("#freeCost")
        shot(tab, "home-bar-usage-limit", full=False)
        page.locator("#freeMore summary").click()
        page.select_option("#freeModel", "claude-fable-5-2")  # still allowed, and said
        assert tab.text("#freeLimit").startswith(
            f"Claude Fable 5.2 is at its usage limit until {when}: a build with it would stop"
        )
        tab.assert_clean()
    finally:
        tab.close()
