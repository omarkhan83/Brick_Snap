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
    with pytest.raises(freebuild.FreeBuildError, match="20 to 300"):
        freebuild.create(tmp_path, "a cat", parts=500)
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
    assert "one AI run" in out and "ten to twenty minutes" in out and "experimental" in out
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
        ({"words": "a cat", "parts": 10}, "20 to 300"),
        ({"words": "a cat", "parts": True}, "20 to 300"),
        ({"words": "a cat", "parts": "80"}, "20 to 300"),
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
        assert "Checked: no problems" in (free_card.text_content() or "")
        assert "Experimental" in (free_card.text_content() or "")
        assert page.locator("#freeRef option").all_text_contents() == [
            "No, just from my words",
            "Pawn",
        ]
        page.click("#freeGo")
        assert "Say what to build first" in tab.text("#freeMsg")
        page.fill("#freeWords", f"a sunflower in a pot {MARKUP}")
        page.locator("#freeMore summary").click()
        page.select_option("#freeRef", "pawn")
        page.click("#freeGo")
        assert page.locator("#freeConfirm").is_visible()
        assert tab.text("#freeQuote") == f"“a sunflower in a pot {MARKUP}”"
        assert "pictures of “Pawn” from five sides" in tab.text("#freeSends")
        assert "hinges and ball joints" in tab.text("#freeCaveat")
        assert page.locator("#freeStart").is_disabled()
        page.check("#freeUnderstood")
        page.fill("#freeWords", "a sunflower in a pot")  # a change takes the agreement back
        assert not page.locator("#freeUnderstood").is_checked()
        page.check("#freeUnderstood")
        shot(tab, "home-consent")
        monkeypatch.setattr(
            freebuild, "reference_sheet", lambda src, out: Image.new("RGB", (8, 8)).save(out) or out
        )
        page.click("#freeStart")
        page.wait_for_selector("#freeJobs .job .progress li")
        assert gate.reached.wait(20)
        page.wait_for_function(
            "() => document.querySelector('#freeJobs .job').textContent.includes('Check 2')"
        )
        text = page.locator("#freeJobs .job").text_content() or ""
        assert "AI is building a new model from parts" in text
        assert "someone@example.com" not in text
        assert page.evaluate("() => window.__pwned") is None
        page.wait_for_function(
            "() => document.querySelectorAll('.pcard[data-kind=\"free\"]').length === 2"
        )
        shot(tab, "job-running")
        gate.open.set()
        page.wait_for_selector("#freeJobs .job.done a.button")
        tab.assert_clean()
    finally:
        gate.open.set()
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open()
    try:
        phone.no_sideways_scroll()
        shot(phone, "home-phone")
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
    assert code == 2 and "--guide go only with a new model" in err
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
    status, data = running.post("/api/p/sunflower/change", {"words": "taller", **AGREED})
    assert running.wait(data["job"])["state"] == "done" and fake.calls[1]["guide"] is True
    status, data = running.post("/api/free", {"words": "a boat", "name": "Boat", **AGREED})
    assert running.wait(data["job"])["state"] == "done" and fake.calls[2]["guide"] is False
    assert running.get_json("/api/p/boat")["guide"] is False


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
        assert box.is_visible() and not box.is_checked()
        label = page.locator("label:has(#freeGuide)").text_content() or ""
        assert "Build it the way set designers do (experimental)" in label
        assert "a core first, sides built flat and pressed on" in label
        box.check()
        page.click("#freeGo")
        assert "built the way set designers do" in tab.text("#freeWhat")
        page.check("#freeUnderstood")
        box.uncheck()  # a change takes the agreement back
        assert not page.locator("#freeUnderstood").is_checked()
        assert "set designers" not in tab.text("#freeWhat")
        box.check()
        page.check("#freeUnderstood")
        page.locator("#freeMore").scroll_into_view_if_needed()
        shot(tab, "home-guide")
        page.click("#freeStart")
        page.wait_for_selector("#freeJobs .job.done a.button")
        assert fake.calls[0]["guide"] is True
        assert not page.locator("#freeGuide").is_checked()  # the form starts afresh
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
        assert "Built the way set designers do" in page_tab.text("#guideNote")
        run_text = page_tab.text("#runs .rguide")
        assert run_text == "Built the way set designers do; playbook it asked for: Plant, 100 parts"
        shot(page_tab, "project-guide")
        page_tab.assert_clean()
    finally:
        page_tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open("p/sunflower")
    try:
        phone.page.wait_for_selector("#runs li")
        phone.no_sideways_scroll()
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
    finally:
        car.close()
