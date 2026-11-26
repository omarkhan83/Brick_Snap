"""Tests for the outside eye and polishing (EXPERIMENTAL): bricksnap/lab/critic.py,
``freebuild.critique`` and ``freebuild.polish``, ``make --polish``, the web app's polish route
and the button and option on the pages.

No test starts a real AI session: ``runner.run_session`` (and ``lab.run.build`` and the
designer's entry points) are replaced for the whole module by a stand-in that fails the test,
and by fakes where a test needs one. ``FakeCritic`` works the critic's real tools in this
process, as a session would, and keeps every text and picture they gave it, so a test can
say exactly what the critic saw. Browser screenshots go to tests/artifacts/polish-*.png.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_freebuild import (
    AGREED,
    MARKUP,
    SAMPLE_BRIEF,
    STUDY,
    FakeLab,
    FakePictures,
    _cli,
    never_start,
    photo,
    said,
    tool_use,
)
from test_webapp import ARTIFACTS, Gate, Running, Tab

from bricksnap.designer import judge, runner, studio
from bricksnap.lab import critic, freebuild, picture
from bricksnap.lab import run as lab_run

POLISH = {"understood": True, "understood_runs": 2}
FIXES = [
    {"where": "the canopy", "fix": "studs show through the trans-black glass: tile the plates"},
    {"where": "the bonnet", "fix": "the round parts there have studs: use 2 x 2 round tiles"},
    {"where": "the rear wing", "fix": "it stands on thick blocks: hold it on two bars in clips"},
]
KEEP = "the low wide stance and the red and black livery"
SECRETS = (
    "BUILDER-TRANSCRIPT-SECRET",
    "BUILDER-NOTES-SECRET",
    "BUILDER-REPORT-SECRET",
    "BUILDER-CALLS-SECRET",
    "the leaves still hang on thick clips",  # the builder's own critique (SAMPLE_CRITIQUE)
    "orange petals read better than yellow",  # the builder's reason for changing its brief
    "I built two bricks",  # its closing words
)
LOOKS = {
    "parts": 2,
    "seams_per_stud": 0.9,
    "not_upright": 0.05,
    "side_top_faces": 0.02,
    "largest_colour": 0.7,
    "largest_colour_name": "Red",
    "colours_5pct": 2,
    "patch_coherence": 0.4,
    "primary_share": 0.7,
    "open_holes": 0,
    "plain_bricks": 1.0,
    "clips_bars": 0.0,
    "studs": 16,
    "studs_showing": 8,
    "studs_showing_share": 0.5,
}


@pytest.fixture(scope="module", autouse=True)
def no_real_ai() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lab_run, "build", never_start)
        mp.setattr(runner, "run_session", never_start)
        mp.setattr(runner, "run_designer", never_start)
        mp.setattr(judge, "design_best_of", never_start)
        mp.setattr(studio, "run_studio", never_start)
        yield


@pytest.fixture(autouse=True)
def pictures(monkeypatch: pytest.MonkeyPatch) -> FakePictures:
    fake = FakePictures()
    monkeypatch.setattr(picture, "model_sheet", fake.sheet)
    monkeypatch.setattr(picture, "turntable", fake.turntable)
    monkeypatch.setattr(freebuild, "missing", lambda: None)
    return fake


class FakeCritic:
    """Stands in for ``runner.run_session`` for the outside eye: works the critic's real tools
    (looks at the model, at the references when there are any, then answers) and keeps what
    it was told and shown."""

    def __init__(
        self,
        fixes: list[dict[str, str]] | None = None,
        keep: str = KEEP,
        *,
        answer: bool = True,
        careless: bool = False,
        limit: bool = False,
    ) -> None:
        self.fixes = FIXES if fixes is None else fixes
        self.keep, self.answer, self.careless, self.limit = keep, answer, careless, limit
        self.calls: list[dict[str, Any]] = []
        self.texts: list[str] = []
        self.images: list[str] = []
        self.replies: list[list[dict[str, Any]]] = []

    def __call__(self, **kw: Any) -> runner.DesignerRun:
        assert kw["prompt_file"] == critic.PROMPT_FILE, "only the critic may run here"
        server = kw["mcp"]["mcpServers"]["bricksnap"]
        folder = Path(server["args"][-1])
        self.calls.append({**kw, "folder": folder})
        self.texts.append(kw["message"])
        tell = kw.get("on_event") or (lambda e: None)
        tell({"type": "system", "subtype": "init", "tools": []})
        tools = critic.Critic(folder)
        refs = json.loads((folder / critic.SHOWN_FILE).read_text())["references"]

        def use(name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
            tell(tool_use(name, args, len(self.replies)))
            blocks = tools.call(name, args)
            self.replies.append(blocks)
            for b in blocks:
                if b["type"] == "text":
                    self.texts.append(b["text"])
                else:
                    self.images.append(b["data"])
            return blocks

        answer = {"fixes": self.fixes, "keep": self.keep}
        if self.careless:
            use("critique", answer)  # before looking: refused
        use("look", {"what": "model"})
        if refs:
            use("look", {"what": "references"})
        if self.answer:
            use("critique", answer)
        tell(said("Done."))
        kw["transcript"].write_text('{"account": "someone@example.com"}\n', "utf-8")
        run = runner.DesignerRun(
            ok=not self.limit, transcript=kw["transcript"], turns=4, duration_s=42.0, cost_usd=0.3
        )
        if self.limit:
            run.usage_limit = "You've hit your Fable limit · resets 2am"
            run.limit_resets = "2am"
            run.error = "Your usage limit was reached."
        return run


def guided_project(root: Path) -> Path:
    """A guided free build with a picture to build from, built once and changed once by
    ``FakeLab``, with secrets planted wherever the builder's own words are kept."""
    folder = freebuild.create(root, "a sunflower in a pot", guide=True, pictures=[photo()])
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(lab_run, "build", FakeLab())
        freebuild.build(folder)
        freebuild.build(folder, "make the petals orange")
    for n in (1, 2):
        work = freebuild.run_dir(folder, n) / "work"
        (work / "transcript" / "x.jsonl").write_text('{"text": "BUILDER-TRANSCRIPT-SECRET"}\n')
        (work / "calls.jsonl").write_text('{"text": "BUILDER-CALLS-SECRET"}\n')
    (folder / "notes.txt").write_text("I built two bricks. BUILDER-NOTES-SECRET\n")
    (folder / "report.txt").write_text("SUMMARY: no problems. BUILDER-REPORT-SECRET\n")
    meta = freebuild.read_meta(folder)
    meta["runs"][-1]["looks"] = LOOKS
    freebuild.save_meta(folder, meta)
    return folder


# ---- what the outside eye is shown --------------------------------------------------------


def test_the_outside_eye_sees_only_the_pictures_words_brief_references_and_numbers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = guided_project(tmp_path)
    fake = FakeCritic()
    monkeypatch.setattr(runner, "run_session", fake)
    lines: list[str] = []
    found = freebuild.critique(folder, on_say=lines.append)

    call = fake.calls[0]
    assert call["folder"] == folder / "runs" / "0002" / "critic"
    assert call["mcp"]["mcpServers"]["bricksnap"]["args"][:2] == ["-m", "bricksnap.lab.critic"]
    assert call["max_turns"] == critic.MAX_TURNS == 8 and call["timeout_s"] == critic.TIMEOUT_S
    assert call["model"] == "claude-fable-5-2" and call["role"] is critic.ROLE
    told = call["message"]
    assert '"a sunflower in a pot"' in told and '- "make the petals orange"' in told
    assert f"Pattern: {SAMPLE_BRIEF['pattern']}" in told  # the brief's lines
    assert "Plate seams on the sides: 0.90 per stud of height" in told  # HOW IT LOOKS
    assert "There is 1 reference picture" in told
    # what it saw: the sheet and four turn views, then the person's picture; nothing else
    assert len(fake.images) == 6
    pics = folder / "pictures"
    sent = sorted(p.name for p in call["folder"].iterdir())
    assert sent == [
        f"{call['transcript'].name}",
        "answer.json",
        "model-1.png",
        "model-2.png",
        "model-3.png",
        "model-4.png",
        "model-5.png",
        "reference-1.png",
        "shown.json",
    ]
    for k, turn in zip(range(2, 6), (0, 3, 6, 9), strict=True):
        assert (call["folder"] / f"model-{k}.png").read_bytes() == (
            pics / f"turn-{turn:02d}.png"
        ).read_bytes()
    seen = "\n".join(fake.texts) + "".join(
        p.read_text("utf-8") for p in call["folder"].glob("*.json")
    )
    for secret in SECRETS:
        assert secret not in seen, secret
    assert str(folder) not in seen and "someone@example.com" not in call["transcript"].read_text()
    # its answer is kept with the run it looked at, and returned
    assert found["run"] == 2 and found["fixes"] == FIXES and found["keep"] == KEEP
    kept = json.loads((folder / "runs" / "0002" / "critique.json").read_text())
    assert kept["fixes"] == FIXES and kept["shown"]["references"] == 1
    assert len(kept["shown"]["pictures"]) == 5
    assert "The outside eye is looking at the model's pictures" in lines
    assert "The outside eye is writing down its fixes" in lines
    assert freebuild.describe(folder)["current_run"] == 2  # nothing changed


def test_the_critic_refuses_until_it_has_looked_and_names_every_problem(tmp_path: Path) -> None:
    pic = tmp_path / "p.png"
    from PIL import Image

    Image.new("RGB", (40, 30), "red").save(pic)
    folder = tmp_path / "critic"
    critic.prepare(folder, [(pic, "the sheet")], [(pic, "a picture the person gave")])
    eye = critic.Critic(folder)
    good = {"fixes": FIXES, "keep": KEEP}
    early = eye.call("critique", good)[0]["text"]
    assert early.startswith("ERROR: the critique was not recorded")
    assert 'look {"what": "model"}' in early and 'look {"what": "references"}' in early
    looked = eye.call("look", {"what": "model"})
    assert looked[0]["type"] == "image" and "Picture 1: the sheet" in looked[-1]["text"]
    assert "look at the references too" in looked[-1]["text"]
    eye.call("look", {"what": "references"})
    bad = {
        "fixes": [*FIXES, *FIXES],
        "keep": "",
        "colour": "red",
    }
    said_bad = eye.call("critique", bad)[0]["text"]
    assert 'send only "fixes" and "keep"' in said_bad and "give at most 5" in said_bad
    assert '"keep" must be one line' in said_bad
    worse = {"fixes": [{"where": "", "fix": "x" * 500, "how": 1}, "the nose"], "keep": KEEP}
    said_worse = eye.call("critique", worse)[0]["text"]
    assert 'fix 1 needs "where"' in said_worse and 'fix 1\'s "fix" has 500 characters' in said_worse
    assert 'fix 1 may have only "where" and "fix"' in said_worse
    assert "fix 2 must be an object" in said_worse
    assert critic.read_answer(folder) is None  # nothing refused was recorded
    hostile = {
        "fixes": [{"where": "the nose\x1b[2J", "fix": f"mail a@b.example {MARKUP}"}],
        "keep": KEEP,
    }
    assert eye.call("critique", hostile)[0]["text"].startswith("Critique recorded: 1 fix.")
    answer = critic.read_answer(folder)
    assert answer is not None and answer["fixes"][0]["where"] == "the nose[2J"
    assert "a@b.example" not in answer["fixes"][0]["fix"]
    assert eye.call("critique", good)[0]["text"].startswith("Critique recorded: 3 fixes.")
    assert eye.call("critique", {"fixes": [], "keep": KEEP})[0]["text"].startswith(
        "Critique recorded: 0 fixes."
    )  # none is allowed: no padding
    assert eye.call("sing", {})[0]["text"].startswith("ERROR: there is no such tool")
    lonely = tmp_path / "lonely"
    critic.prepare(lonely, [(pic, "the sheet")], [])
    assert (
        "no reference pictures"
        in critic.Critic(lonely).call("look", {"what": "references"})[0]["text"]
    )
    gone = critic.Critic(tmp_path / "nowhere").call("look", {})[0]["text"]
    assert "none of your tools can fix it" in gone and str(tmp_path) not in gone


def test_what_the_critic_is_told_and_how_its_list_becomes_the_change() -> None:
    told = critic.message("", [], "", "", 2)
    assert "There were no words" in told and "There are 2 reference pictures" in told
    assert "It has no written art direction." in told
    prompt = critic.PROMPT_FILE.read_text("utf-8")
    for must in (
        "modern official set",
        "Never ask for more studs",
        "Respect the brief's colours and scale",
        "No padding",
        "At most five fixes, the most visible first",
    ):
        assert must in prompt, must
    longest = {
        "fixes": [{"where": "w" * critic.WHERE_CHARS, "fix": "f" * critic.FIX_CHARS}] * 5,
        "keep": "k" * critic.KEEP_CHARS,
    }
    words = freebuild.polish_words(longest)
    assert len(freebuild.clean(words, 10**6)) <= freebuild.MAX_WORDS  # never cut short
    words = freebuild.polish_words({"fixes": FIXES, "keep": KEEP})
    assert words.splitlines() == [
        freebuild.POLISH_HEAD,
        "1. The canopy: studs show through the trans-black glass: tile the plates.",
        "2. The bonnet: the round parts there have studs: use 2 x 2 round tiles.",
        "3. The rear wing: it stands on thick blocks: hold it on two bars in clips.",
        f"What already works, and must be kept: {KEEP}.",
        "Keep everything else as it is; then look from every side and hand it in.",
    ]


# ---- polishing ----------------------------------------------------------------------------


def test_polish_makes_the_fixes_as_one_change_with_the_critique_on_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = guided_project(tmp_path)
    eye, lab = FakeCritic(), FakeLab()
    monkeypatch.setattr(runner, "run_session", eye)
    monkeypatch.setattr(lab_run, "build", lab)
    seen: list[dict[str, Any]] = []
    entry = freebuild.polish(folder, on_critique=seen.append)
    assert seen and seen[0]["fixes"] == FIXES  # given as soon as it existed
    call = lab.calls[0]
    assert call["task"] == freebuild.clean(freebuild.polish_words(seen[0]), freebuild.MAX_WORDS)
    assert call["change_of"] == "a sunflower in a pot" and call["start"] == folder / "model.ldr"
    assert call["brief"] == SAMPLE_BRIEF  # a change builds to the model's brief
    assert entry["n"] == 3 and entry["kind"] == "change"
    assert entry["polish"]["of_run"] == 2 and entry["polish"]["fixes"] == FIXES
    record = json.loads((folder / "runs" / "0003" / "record.json").read_text())
    assert record["polish"]["keep"] == KEEP
    about = freebuild.describe(folder)
    assert about["polish"]["fixes"] == FIXES and about["runs"][-1]["polish"]["of_run"] == 2
    # a second polish is not told the first one's words as a change the person asked for
    monkeypatch.setattr(runner, "run_session", again := FakeCritic())
    freebuild.critique(folder)
    assert "The canopy" not in again.calls[0]["message"]
    assert '- "make the petals orange"' in again.calls[0]["message"]


def test_refusals_and_failures_change_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lab = FakeLab()
    monkeypatch.setattr(lab_run, "build", lab)
    empty = freebuild.create(tmp_path, "a boat")
    with pytest.raises(freebuild.FreeBuildError, match="nothing for an outside eye to look at"):
        freebuild.polish(empty)
    folder = freebuild.import_run(tmp_path, STUDY / "car.ldr", words="A red roadster")
    monkeypatch.setattr(runner, "run_session", FakeCritic(answer=False))
    with pytest.raises(freebuild.FreeBuildError, match="did not give its list"):
        freebuild.polish(folder)
    monkeypatch.setattr(runner, "run_session", FakeCritic(limit=True))
    with pytest.raises(freebuild.UsageLimitError, match="Nothing was changed"):
        freebuild.polish(folder)
    assert freebuild.usage_limits(tmp_path)[0]["model"] == "claude-fable-5-2"
    monkeypatch.setattr(runner, "run_session", FakeCritic(fixes=[]))
    with pytest.raises(freebuild.NothingToPolish, match="found nothing it would change") as e:
        freebuild.polish(folder)
    assert e.value.critique["keep"] == KEEP
    monkeypatch.setattr(runner, "run_session", careless := FakeCritic(careless=True))
    assert freebuild.critique(folder)["fixes"] == FIXES  # refused once, then it looked
    assert careless.replies[0][0]["text"].startswith("ERROR: the critique was not recorded")
    assert lab.calls == [] and freebuild.describe(folder)["current_run"] == 1
    assert len(freebuild.describe(folder)["runs"]) == 1


def test_make_polish(capsys: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freebuild.import_run(tmp_path / "projects", STUDY / "car.ldr", words="A red roadster")
    monkeypatch.chdir(tmp_path)
    eye, lab = FakeCritic(), FakeLab()
    monkeypatch.setattr(runner, "run_session", eye)
    monkeypatch.setattr(lab_run, "build", lab)
    assert _cli(capsys, "make", "--polish", "a-red-roadster", "make it blue")[0] == 2
    assert _cli(capsys, "make", "--polish", "nothing-here")[0] == 2
    code, out, err = _cli(capsys, "make", "--polish", "a-red-roadster")
    assert code == 0, err
    assert "It is two AI runs" in out and freebuild.critic_time_and_cost() in out
    assert freebuild.time_and_cost(102) in out
    assert out.index("It is two AI runs") < out.index("What the outside eye asked for:")
    assert "  1. the canopy: studs show through" in out and f"  Keep: {KEEP}" in out
    assert "Built " in out and lab.calls[0]["task"].startswith(freebuild.POLISH_HEAD)


# ---- the web app --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def made_car(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("polish-car")
    with pytest.MonkeyPatch.context() as mp:
        fake = FakePictures()
        mp.setattr(picture, "model_sheet", fake.sheet)
        mp.setattr(picture, "turntable", fake.turntable)
        return freebuild.import_run(
            base, STUDY / "car.ldr", words="A red roadster", name="Roadster"
        )


@pytest.fixture
def running(tmp_path: Path, made_car: Path) -> Iterator[Running]:
    root = tmp_path / "projects"
    root.mkdir()
    shutil.copytree(made_car, root / "car")
    (root / "pawn").mkdir()
    (root / "pawn" / "project.json").write_text('{"name": "Pawn"}')  # an ordinary project
    r = Running(root)
    yield r
    r.close()


def test_polish_over_the_web(running: Running, monkeypatch: pytest.MonkeyPatch) -> None:
    eye, lab = FakeCritic(), FakeLab()
    monkeypatch.setattr(runner, "run_session", eye)
    monkeypatch.setattr(lab_run, "build", lab)
    for agreement in ({}, AGREED, {"understood": True, "understood_runs": 3}):
        status, data = running.post("/api/p/car/polish", agreement)
        assert status == 400 and "Polishing was not started" in data["error"]
    status, data = running.post("/api/p/pawn/polish", POLISH)
    assert status == 400 and "made from a 3D file" in data["error"]
    status, data = running.post("/api/p/car/polish", POLISH, token=False)
    assert status == 403
    status, data = running.post("/api/p/car/polish", {**POLISH, "model": "gpt"})
    assert status == 400 and eye.calls == []
    status, data = running.post("/api/p/car/polish", POLISH)
    assert status == 202
    job = running.wait(data["job"])
    assert job["state"] == "done" and job["kind"] == "polish", job
    assert job["critique"] == {"fixes": FIXES, "keep": KEEP}
    assert job["result"]["run"] == 2
    assert any("Two AI runs, by Claude Fable 5.2" in line for line in job["progress"])
    info = running.get_json("/api/p/car")
    assert info["polish"]["fixes"] == FIXES and info["runs"][-1]["polish"]["of_run"] == 1
    assert info["runs"][0]["polish"] is None
    for served in ("runs/0001/critique.json", "runs/0001/critic/shown.json"):
        assert running.request(f"/p/car/files/{served}")[0] == 404

    monkeypatch.setattr(runner, "run_session", FakeCritic(fixes=[]))
    status, data = running.post("/api/p/car/polish", POLISH)
    job = running.wait(data["job"])
    assert job["state"] == "done" and job["result"] == {
        "project": "car",
        "run": None,
        "nothing": True,
    }
    assert len(running.get_json("/api/p/car")["runs"]) == 2  # no change was made


def test_build_and_polish_once_in_one_job(
    running: Running, monkeypatch: pytest.MonkeyPatch
) -> None:
    eye, lab = FakeCritic(), FakeLab()
    monkeypatch.setattr(runner, "run_session", eye)
    monkeypatch.setattr(lab_run, "build", lab)
    for bad in (
        {**AGREED, "polish": True},
        {"understood": True, "understood_runs": 3, "polish": "yes"},
    ):
        status, data = running.post("/api/free", {"words": "a boat", **bad})
        assert status == 400, data
    status, data = running.post(
        "/api/free", {"words": "a boat", "polish": True, "understood": True, "understood_runs": 3}
    )
    assert status == 202
    job = running.wait(data["job"])
    assert job["state"] == "done" and job["kind"] == "free" and job["critique"]["fixes"] == FIXES
    assert len(lab.calls) == 2 and lab.calls[1]["task"].startswith(freebuild.POLISH_HEAD)
    info = running.get_json(f"/api/p/{data['project']}")
    assert [r["kind"] for r in info["runs"]] == ["first", "change"] and info["polish"]


# ---- the pages ----------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except sync_api.Error as e:
            pytest.skip(f"Headless Chromium is not installed ({str(e).splitlines()[0]})")
        yield b
        b.close()


def shot(tab: Tab, name: str, full: bool = True) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    tab.page.screenshot(path=str(ARTIFACTS / f"polish-{name}.png"), full_page=full)


@pytest.mark.browser
def test_browser_the_polish_button_its_list_and_the_option(
    browser: Any, running: Running, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = Gate()
    hostile = [{"where": f"the nose {MARKUP}", "fix": "press curved slopes on side studs"}, *FIXES]
    eye, lab = FakeCritic(fixes=hostile), FakeLab(gate=gate)
    monkeypatch.setattr(runner, "run_session", eye)
    monkeypatch.setattr(lab_run, "build", lab)
    tab = Tab(browser, running.url, width=1280, height=900).open("p/car")
    try:
        page = tab.page
        assert page.locator("#askBtn").is_visible() and page.locator("#polishBtn").is_visible()
        assert not page.locator("#polishCard").is_visible()
        page.click("#polishBtn")
        assert page.locator("#polishConfirm").is_visible()
        assert tab.text("#polishTime") == (
            "It is two AI runs by Claude Fable 5.2. "
            + freebuild.polish_time_and_cost(102)
            + " You can leave this page while it works."
        )
        assert page.locator("#polishStart").is_disabled()
        shot(tab, "confirm")
        page.check("#polishUnderstood")
        page.click("#polishStart")
        assert gate.reached.wait(20)  # the outside eye has answered; the change is running
        page.wait_for_selector("#appJob .outside-eye", timeout=20000)
        box = tab.text("#appJob .outside-eye")
        assert "What an outside eye asked for" in box and f"the nose {MARKUP}" in box
        assert "Keep: the low wide stance" in box
        assert page.evaluate("() => window.__pwned") is None
        shot(tab, "job-running")
        gate.open.set()
        page.wait_for_selector("#appJob .job.done", timeout=30000)
        page.wait_for_selector("#polishCard:not([hidden])", timeout=20000)
        assert page.locator("#polishCard .eye-fixes li").count() == 4
        assert "Polished" in tab.text("#runs") and "The 4 fixes an outside eye" in tab.text("#runs")
        shot(tab, "project-polished")
        tab.assert_clean()
    finally:
        gate.open.set()
        tab.close()

    home = Tab(browser, running.url, width=1280, height=900).open()
    try:
        page = home.page
        page.click("#freeMore summary")
        assert page.locator("#freePolish").is_checked()  # on unless the person turns it off
        page.fill("#freeWords", "a sports car")
        page.uncheck("#freePolish")
        one = home.text("#freeCost")
        assert one.startswith("One AI run by Claude Fable 5.2")
        page.check("#freePolish")
        both = freebuild.polish_estimate(200, None, after_build=True)
        assert home.text("#freeCost") == (
            "Three AI runs by Claude Fable 5.2, designed first, then polished once: usually "
            f"{both['minutes'][0]} to {both['minutes'][1]} minutes, about ${both['dollars'][0]} "
            f"to ${both['dollars'][1]} of your Claude subscription (an estimate)."
        )
        added = freebuild.polish_estimate(200)
        assert f"it adds about {added['minutes'][0]} to {added['minutes'][1]} minutes" in home.text(
            "#freePolishHint"
        )
        got = page.evaluate(
            """async () => {
                const m = await import('/viewer/app.js');
                const out = [];
                for (const n of [20, 80, 200, 600, 'x']) {
                  for (const model of [null, 'claude-opus-5-5']) {
                    out.push([m.freePolishEstimate(n, model), m.freePolishEstimate(n, model, true),
                              m.freePolishTimeAndCost(n, model)]);
                  }
                }
                return out;
            }"""
        )
        k = 0
        for n in (20, 80, 200, 600, "x"):
            for model in (None, "claude-opus-5-5"):
                alone, after, words = got[k]
                k += 1
                assert alone == freebuild.polish_estimate(n, model), (n, model)
                assert after == freebuild.polish_estimate(n, model, after_build=True), (n, model)
                assert words == freebuild.polish_time_and_cost(n, model), (n, model)
        shot(home, "home-option")
        page.check("#freeUnderstood")
        page.click("#freeGo")  # the form: "polish" true and three AI runs agreed to
        page.wait_for_url("**/p/a-sports-car", timeout=20000)
        page.wait_for_selector("#appJob .job.done", timeout=30000)
        assert "What an outside eye asked for" in home.text("#appJob .job")
        assert len(lab.calls) == 3 and lab.calls[2]["task"].startswith(freebuild.POLISH_HEAD)
        page.wait_for_selector("#polishCard:not([hidden])", timeout=20000)
        home.assert_clean()
    finally:
        home.close()
