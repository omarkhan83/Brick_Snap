"""Tests for the web app (bricksnap/webapp.py and viewer/home.*, viewer/app.*).

Server tests talk HTTP to a real server on a free port. Browser tests (marked ``browser``)
open the pages in headless Chromium and save screenshots to tests/artifacts/webapp-*.png.
No test starts the real AI designer: ``runner.run_designer`` and ``judge.design_best_of``
are replaced for every test, by a fake when a test needs one and otherwise by a stand-in
that fails the test.
"""

from __future__ import annotations

import http.client
import io
import json
import os
import re
import shutil
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image

from bricksnap import pipeline, render, webapp
from bricksnap.designer import judge, runner
from bricksnap.designer.judge import BestOf
from bricksnap.designer.runner import DesignerRun
from bricksnap.pipeline import create_project, rebuild, render_card, render_compare, rough_build
from bricksnap.project import Project, ProjectError
from bricksnap.webapp import Refused, make_app_server, read_form, serve_app

REPO = Path(__file__).resolve().parent.parent
VIEWER = REPO / "viewer"
ARTIFACTS = REPO / "tests" / "artifacts"
TRADEMARK = (
    "LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse "
    "this project."
)
BRIEF = {
    "object": "A chess pawn, standing upright.",
    "features": ["a round head", "a wide base"],
    "plan": "Keep the head round.",
    "colours": [71, 4],
    "finish": "Studs everywhere.",
}
MARKUP = '<img src="x" onerror="window.__pwned=1">'
AGREED = {"understood": True, "understood_runs": 1}
PAINT = [{"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [9, 9, 2]}, "color": 4}]


# ---- helpers ------------------------------------------------------------------------------


class Running:
    """The app's server running in a background thread."""

    def __init__(self, projects: Path) -> None:
        self.server = make_app_server(projects, port=0)
        self.app = self.server.app
        self.token = self.app.token
        self.port = int(self.server.server_address[1])
        self.url = f"http://127.0.0.1:{self.port}/"
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        self.thread.start()

    def request(
        self,
        path: str,
        method: str = "GET",
        *,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        host: str | None = None,
        token: bool = False,
    ) -> tuple[int, dict[str, str], bytes]:
        """Send ``path`` exactly as written; ``token`` adds the server's token header."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        try:
            conn.putrequest(method, path, skip_host=host is not None, skip_accept_encoding=True)
            if host is not None:
                conn.putheader("Host", host)
            sent = dict(headers or {})
            if token:
                sent[webapp.TOKEN_HEADER] = self.token
            if method == "POST" and not {"Content-Length", "Transfer-Encoding"} & set(sent):
                sent["Content-Length"] = str(len(body))
            for key, value in sent.items():
                conn.putheader(key, value)
            conn.endheaders()
            if body:
                conn.send(body)
            res = conn.getresponse()
            data = res.read()
            return res.status, {k.lower(): v for k, v in res.getheaders()}, data
        finally:
            conn.close()

    def get_json(self, path: str) -> Any:
        status, _, data = self.request(path)
        assert status == 200, (status, data)
        return json.loads(data)

    def post(self, path: str, value: Any = None, **kw: Any) -> tuple[int, Any]:
        body = b"" if value is None else json.dumps(value).encode()
        kw.setdefault("token", True)
        headers = {"Content-Type": "application/json", **kw.pop("headers", {})}
        status, _, data = self.request(path, "POST", body=body, headers=headers, **kw)
        return status, json.loads(data) if data.startswith(b"{") else data

    def upload(
        self,
        content: bytes,
        filename: str = "pawn.stl",
        fields: dict[str, str] | None = None,
        **kw: Any,
    ) -> tuple[int, Any]:
        body, ctype = multipart(content, filename, fields or {"studs": "8"})
        kw.setdefault("token", True)
        status, _, data = self.request(
            "/api/projects", "POST", body=body, headers={"Content-Type": ctype}, **kw
        )
        return status, json.loads(data) if data.startswith(b"{") else data

    def wait(self, job: str, timeout: float = 60) -> dict[str, Any]:
        end = time.time() + timeout
        while time.time() < end:
            state = self.get_json(f"/api/jobs/{job}")
            if state["state"] in ("done", "failed"):
                return state
            time.sleep(0.05)
        raise AssertionError(f"job {job} did not finish: {state}")

    def close(self) -> None:
        idle = self.app.wait_idle(30)  # no job thread may outlive its test
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        assert idle, "a job was still running when the test ended"


def multipart(
    content: bytes, filename: str, fields: dict[str, str], boundary: str = "BrickSnapTestBoundary"
) -> tuple[bytes, str]:
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        out.write(value.encode() + b"\r\n")
    out.write(
        f'--{boundary}\r\nContent-Disposition: form-data; name="model"; '
        f'filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
    )
    out.write(content + f"\r\n--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


class Gate:
    """Holds a pipeline step (or a fake) until the test opens it."""

    def __init__(self) -> None:
        self.reached = threading.Event()
        self.open = threading.Event()

    def wait(self) -> None:
        self.reached.set()
        assert self.open.wait(30), "the test never opened the gate"


def wait_for(check: Callable[[], bool], timeout: float = 20) -> None:
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return
        time.sleep(0.02)
    raise AssertionError("timed out")


class FakeDesigner:
    """Stands in for ``runner.run_designer``: reports events, paints, writes a brief."""

    def __init__(self, *, ok: bool = True, gate: Gate | None = None) -> None:
        self.ok = ok
        self.gate = gate
        self.calls: list[dict[str, Any]] = []

    def __call__(self, project: Project, **options: Any) -> DesignerRun:
        from bricksnap.catalog import load_catalog
        from bricksnap.design import apply_ops

        self.calls.append(options)
        tell = options.get("on_event") or (lambda event: None)
        tell({"type": "system", "subtype": "init", "tools": ["mcp__bricksnap__describe"]})
        tell(tool_use("describe", {}))
        tell(tool_use("render", {"view": "front"}))
        design = project.load_design()
        apply_ops(design, PAINT, load_catalog())
        project.save_design(design)
        project.meta["brief"] = BRIEF
        project.save_meta()
        tell(tool_use("apply_ops", {"ops": PAINT * 3}))
        home = str(Path.home())
        say = f"I painted the base red. Mail me at someone@example.com, see {home}/notes."
        tell({"type": "assistant", "message": {"content": [{"type": "text", "text": say}]}})
        if self.gate is not None:
            self.gate.wait()
        if not self.ok:
            return DesignerRun(ok=False, error="Claude Code is not signed in.", kind="first pass")
        return DesignerRun(ok=True, turns=7, final_text="Painted the base red.")


def tool_use(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    item = {"type": "tool_use", "name": runner.TOOL_PREFIX + name, "input": arguments}
    return {"type": "assistant", "message": {"content": [item]}}


def never_start(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("a test tried to start the real AI designer")


@pytest.fixture(scope="module", autouse=True)
def no_real_designer() -> Iterator[None]:
    """For the whole module, not per test: a job thread that outlives its test must still
    find the stand-in when a test's own fake has been taken away again."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(runner, "run_designer", never_start)
        mp.setattr(judge, "design_best_of", never_start)
        mp.setattr(judge, "run_judge", never_start)
        mp.setattr(runner, "run_session", never_start)
        yield


@pytest.fixture(scope="module")
def built_pawn(tmp_path_factory: pytest.TempPathFactory, pawn_path: Path) -> Path:
    base = tmp_path_factory.mktemp("webapp-base")
    project = create_project(pawn_path, studs=8, directory=base, name="Pawn")
    rebuild(project)
    render_compare(project)
    render_card(project)
    rough_build(project)
    return project.path


def add_project(projects: Path, built: Path, folder: str, **meta: Any) -> Path:
    dest = projects / folder
    shutil.copytree(built, dest)
    if meta:
        project = Project(dest)
        project.meta.update(meta)
        project.save_meta()
    return dest


@pytest.fixture
def projects(tmp_path: Path, built_pawn: Path) -> Path:
    root = tmp_path / "projects"
    root.mkdir()
    add_project(root, built_pawn, "pawn")
    (tmp_path / "secret.txt").write_text("TOP SECRET", "utf-8")
    return root


@pytest.fixture
def running(projects: Path) -> Iterator[Running]:
    r = Running(projects)
    yield r
    r.close()


def gate_rebuild(monkeypatch: pytest.MonkeyPatch) -> Gate:
    """Make ``pipeline.rebuild`` wait for the test before it runs."""
    gate = Gate()
    real = pipeline.rebuild

    def held(project: Project, **kw: Any) -> Any:
        gate.wait()
        return real(project, **kw)

    monkeypatch.setattr(pipeline, "rebuild", held)
    return gate


# ---- pages and routes ---------------------------------------------------------------------


def test_server_binds_localhost_on_a_free_port(running: Running) -> None:
    assert running.server.server_address[0] == "127.0.0.1"
    assert running.port > 0
    status, headers, body = running.request("/")
    assert status == 200 and headers["content-type"].startswith("text/html")
    assert headers["cache-control"] == "no-store"
    assert headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["content-security-policy"]


def test_home_page_carries_the_token_and_the_trademark(running: Running) -> None:
    _, _, body = running.request("/")
    page = body.decode()
    assert f'<meta name="bricksnap-token" content="{running.token}">' in page
    assert webapp.TOKEN_PLACEHOLDER not in page
    assert TRADEMARK in page and "/viewer/home.js" in page


def test_project_page_is_the_viewer_with_the_action_bar(running: Running) -> None:
    status, _, body = running.request("/p/pawn")
    assert status == 200
    page = body.decode()
    viewer_page = (VIEWER / "index.html").read_text("utf-8")
    assert 'data-project-files="/p/pawn/files"' in page
    assert 'data-project-list="/p/pawn/project-files.json"' in page
    assert running.token in page and "/viewer/app.js" in page and "/viewer/app.css" in page
    assert TRADEMARK in page and 'id="view"' in page
    assert running.token not in viewer_page  # the file itself is unchanged
    assert running.request("/p/pawn/")[0] == 200


def test_project_files_and_the_viewer_list(running: Running, projects: Path) -> None:
    status, headers, body = running.request("/p/pawn/files/build.json")
    assert status == 200 and headers["content-type"].startswith("application/json")
    assert body == (projects / "pawn" / "build.json").read_bytes()
    assert "sandbox" in headers["content-security-policy"]
    files = running.get_json("/p/pawn/project-files.json")
    assert files == {
        "files": ["project.json", "build.json", "build.rough.json"],
        "versions": [],
        "current": None,
    }
    status, headers, _ = running.request("/p/pawn/files/renders/compare.png?v=1")
    assert status == 200 and headers["content-type"] == "image/png"
    for name in ("parts.json", "colours.json"):
        assert running.request(f"/catalog/{name}")[0] == 200
    assert running.request("/viewer/viewer.js")[0] == 200
    assert running.request("/viewer/app.js")[0] == 200


def test_the_list_of_projects(running: Running, projects: Path, built_pawn: Path) -> None:
    newer = add_project(projects, built_pawn, "newer", name="The newer one")
    os.utime(newer / "build.json", (time.time() + 60, time.time() + 60))
    (newer / "renders" / "card.png").unlink()  # an older project: the comparison sheet
    (projects / "not-a-project").mkdir()
    add_project(projects, built_pawn, "Bad Name")  # not a slug: cannot be addressed
    add_project(projects, built_pawn, ".hidden")
    listing = running.get_json("/api/projects")
    assert [c["project"] for c in listing["projects"]] == ["newer", "pawn"]
    card = listing["projects"][1]
    built = json.loads((projects / "pawn" / "build.json").read_text())
    assert card["name"] == "Pawn" and card["studs"] == 8
    assert card["parts"] == len(built["parts"]) and card["valid"] is True
    assert card["picture"].startswith("/p/pawn/files/renders/card.png?v=")
    assert listing["projects"][0]["picture"].startswith("/p/newer/files/renders/compare.png?v=")
    assert card["job"] is None and card["problem"] is None
    assert listing["jobs"] == []


def test_a_damaged_project_is_listed_with_a_plain_problem(running: Running, projects: Path) -> None:
    (projects / "pawn" / "build.json").write_text("{not json", "utf-8")
    card = running.get_json("/api/projects")["projects"][0]
    assert card["problem"] and "damaged" in card["problem"]


def test_project_info(running: Running, projects: Path) -> None:
    info = running.get_json("/api/p/pawn")
    assert info["name"] == "Pawn" and info["studs"] == 8 and info["current"] is True
    assert info["files"] == ["build.ldr", "renders/compare.png"]
    assert info["brief"] is None and info["job"] is None
    assert "one connected piece" in info["verdict"]
    assert all(isinstance(n, str) for n in info["notes"])
    status, data = running.post("/api/p/missing/build")
    assert status == 404 and "no project called" in data["error"]
    assert running.request("/api/p/missing")[0] == 404
    assert running.request("/api/jobs/nope")[0] == 404


def test_other_methods_are_refused(running: Running) -> None:
    for method in ("PUT", "DELETE", "PATCH", "OPTIONS"):
        assert running.request("/api/projects", method)[0] == 405


def test_head_answers_without_a_body(running: Running) -> None:
    status, headers, body = running.request("/p/pawn/files/build.json", "HEAD")
    assert status == 200 and body == b"" and int(headers["content-length"]) > 0


# ---- safety -------------------------------------------------------------------------------


@pytest.mark.parametrize("host", ["evil.example", "127.0.0.1.evil.example", "localhost:80x", ""])
def test_wrong_host_is_refused(running: Running, projects: Path, host: str) -> None:
    assert running.request("/", host=host)[0] == 404
    assert running.request("/api/projects", host=host)[0] == 404
    status, _ = running.post("/api/p/pawn/delete", {}, host=host)
    assert status == 404
    assert (projects / "pawn").is_dir()


def test_local_host_names_are_answered(running: Running) -> None:
    for host in ("localhost", f"127.0.0.1:{running.port}", "[::1]"):
        assert running.request("/", host=host)[0] == 200


def test_post_without_the_token_is_refused_and_changes_nothing(
    running: Running, projects: Path, pawn_path: Path
) -> None:
    before = sorted(p.name for p in projects.rglob("*"))
    for path in ("/api/p/pawn/delete", "/api/p/pawn/build", "/api/p/pawn/export"):
        status, data = running.post(path, {}, token=False)
        assert status == 403 and "Reload the page" in data["error"]
        status, data = running.post(path, {}, token=False, headers={webapp.TOKEN_HEADER: "x"})
        assert status == 403
    status, _ = running.upload(pawn_path.read_bytes(), token=False)
    assert status == 403
    status, _ = running.post(
        "/api/p/pawn/design", {"understood": True}, token=False
    )  # the fake that fails the test is never reached
    assert status == 403
    time.sleep(0.2)
    assert sorted(p.name for p in projects.rglob("*")) == before
    assert running.app.jobs == {}


def test_post_from_another_site_is_refused(running: Running, projects: Path) -> None:
    for origin in ("http://evil.example", "null", f"http://evil.example:{running.port}"):
        status, data = running.post("/api/p/pawn/delete", {}, headers={"Origin": origin})
        assert status == 403 and "another web site" in data["error"]
    assert (projects / "pawn").is_dir()
    status, _ = running.post(
        "/api/p/pawn/delete", {}, headers={"Origin": f"http://127.0.0.1:{running.port}"}
    )
    assert status == 200
    assert not (projects / "pawn").exists()


def test_an_oversize_upload_is_refused_before_it_is_read(running: Running, projects: Path) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", running.port, timeout=10)
    try:
        conn.putrequest("POST", "/api/projects")
        conn.putheader("Content-Type", "multipart/form-data; boundary=abc")
        conn.putheader("Content-Length", str(webapp.MAX_UPLOAD_BYTES + 2 * 1024 * 1024))
        conn.putheader(webapp.TOKEN_HEADER, running.token)
        conn.endheaders()  # and no body at all: the answer must come anyway
        res = conn.getresponse()
        data = json.loads(res.read())
    finally:
        conn.close()
    assert res.status == 413 and "60 MB" in data["error"]
    assert sorted(p.name for p in projects.iterdir()) == ["pawn"]


def test_an_upload_that_runs_over_is_stopped(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webapp, "MAX_UPLOAD_BYTES", 100_000)
    status, data = running.upload(b"solid x\n" + b"x" * 300_000)
    assert status == 413 and "too large" in data["error"]
    assert sorted(p.name for p in projects.iterdir() if p.name != ".incoming") == ["pawn"]
    assert not any((projects / ".incoming").glob("*"))


def test_an_upload_without_a_length_is_refused(running: Running) -> None:
    status, _, body = running.request(
        "/api/projects",
        "POST",
        headers={"Content-Type": "multipart/form-data; boundary=a", "Transfer-Encoding": "chunked"},
        token=True,
        body=b"",
    )
    assert status == 411


@pytest.mark.parametrize("name", ["virus.exe", "pawn.stl.exe", "pawn", "model.STL.zip", ".stl/x"])
def test_a_file_of_the_wrong_kind_is_refused(running: Running, projects: Path, name: str) -> None:
    status, data = running.upload(b"solid x\n", filename=name)
    assert status == 400 and "3D model file" in data["error"]
    assert sorted(p.name for p in projects.iterdir() if p.name != ".incoming") == ["pawn"]


def test_names_from_the_browser_are_never_paths(
    running: Running, projects: Path, pawn_path: Path, tmp_path: Path
) -> None:
    data = pawn_path.read_bytes()
    status, answer = running.upload(
        data, filename="../../escape.stl", fields={"studs": "8", "name": "../../Pawn"}
    )
    assert status == 202
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    assert job["result"]["project"] == "pawn-2"  # "pawn" is taken
    project = Project(projects / "pawn-2")
    assert project.name == "../../Pawn"  # shown as text, never used as a path
    assert project.meta["seed_original_name"] == "escape.stl"
    assert not (tmp_path / "escape.stl").exists() and not (projects.parent / "Pawn").exists()
    assert not any((projects / ".incoming").glob("*"))


@pytest.mark.parametrize(
    "path",
    [
        "/p/..",
        "/p/../secret.txt",
        "/p/.trash",
        "/p/.trash/files/project.json",
        "/p/.incoming",
        "/p/%2e%2e/files/secret.txt",
        "/p/pawn/files/../../secret.txt",
        "/p/pawn/files/%2e%2e/%2e%2e/secret.txt",
        "/p/pawn%2Ffiles%2Fbuild.json",
        "/p/pawn/files/renders%2Fcompare.png",
        "/p/pawn/files/renders%5Ccompare.png",
        "/p/pawn/files/renders\\compare.png",
        "/p/pawn/files/designer/run.jsonl",
        "/p/pawn/files/candidates/1/designer/run.jsonl",
        "/p/pawn/files/.hidden",
        "/p/pawn/files/%00",
        "/p/Pawn",
        "/p/pawn/files/",
        "/p/pawn/other",
        "/api/p/..%2Fpawn",
        "/api/p/.trash",
        "/viewer/../bricksnap/webapp.py",
        "/catalog/../webapp.py",
        "/project/build.json",
        "/p/pawn/files/candidates/judging/20261118T120000Z.jsonl",
        "/p/pawn/files/candidates/1/renders/compare.png",
        "/p/pawn/files/Designer/run.jsonl",
        "/p/pawn/files/renders/notes.jsonl",
        "/p/pawn/files/renders/sub/x.png",
        "/p/pawn/files/renders/leak.png",
        "/p/pawn/files/seed.stl",
        "/p/pawn/files/design.json",
        "/p/pawn/files/BUILD.JSON",
    ],
)
def test_paths_outside_the_projects_are_never_served(
    running: Running, projects: Path, built_pawn: Path, path: str
) -> None:
    (projects / "pawn" / "designer").mkdir()
    (projects / "pawn" / "designer" / "run.jsonl").write_text("someone@example.com")
    (projects / "pawn" / "candidates" / "1" / "designer").mkdir(parents=True)
    (projects / "pawn" / "candidates" / "1" / "designer" / "run.jsonl").write_text("x")
    (projects / "pawn" / ".hidden").write_text("x")
    for name in (
        "candidates/judging/20261118T120000Z.jsonl",
        "candidates/1/renders/compare.png",
        "Designer/run.jsonl",
        "renders/notes.jsonl",
        "renders/sub/x.png",
    ):
        (projects / "pawn" / name).parent.mkdir(parents=True, exist_ok=True)
        (projects / "pawn" / name).write_text("someone@example.com")
    (projects / "pawn" / "renders" / "leak.png").symlink_to("../designer/run.jsonl")
    trash = projects / ".trash"
    shutil.copytree(built_pawn, trash / "old")
    shutil.copytree(built_pawn, trash, dirs_exist_ok=True)  # a project.json right in .trash
    status, _, body = running.request(path)
    assert status == 404, path
    assert b"TOP SECRET" not in body and b"example.com" not in body


def test_a_symlink_out_of_the_projects_is_not_served(
    running: Running, projects: Path, built_pawn: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside"
    shutil.copytree(built_pawn, outside)
    (projects / "linked").symlink_to(outside, target_is_directory=True)
    (projects / "pawn" / "renders" / "secret.txt").symlink_to(tmp_path / "secret.txt")
    assert running.request("/p/linked")[0] == 404
    assert running.request("/api/p/linked")[0] == 404
    assert running.request("/p/pawn/files/renders/secret.txt")[0] == 404
    assert "linked" not in [c["project"] for c in running.get_json("/api/projects")["projects"]]


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/p/pawn/files/versions/0001/build.json", 200),
        ("/p/pawn/files/versions/0001/card.png", 200),
        ("/p/pawn/files/versions/0001/design.json", 404),
        ("/p/pawn/files/versions/0001/design.npz", 404),
        ("/p/pawn/files/versions/0001/notes.jsonl", 404),
        ("/p/pawn/files/versions/0001/leak.png", 404),
        ("/p/pawn/files/versions/0002/card.png", 404),  # a symlink to a transcript
        ("/p/pawn/files/versions/index.json", 404),
        ("/p/pawn/files/versions/1/build.json", 404),
        ("/p/pawn/files/versions/00001/build.json", 404),
        ("/p/pawn/files/versions/0009/build.json", 404),  # a folder the index does not list
        ("/p/pawn/files/versions/0001/../../secret.txt", 404),
        ("/p/pawn/files/versions%2F0001%2Fbuild.json", 404),
        ("/p/pawn/files/VERSIONS/0001/build.json", 404),
    ],
)
def test_only_a_versions_build_and_card_are_served(
    running: Running, projects: Path, path: str, status: int
) -> None:
    from bricksnap import versions

    project = Project(projects / "pawn")
    assert versions.record(project, "converted", "First") == 1
    (projects / "pawn" / "designer").mkdir()
    (projects / "pawn" / "designer" / "run.jsonl").write_text("someone@example.com")
    kept = projects / "pawn" / "versions"
    project.meta["brief"] = BRIEF  # a second version, whose card leads to a transcript
    project.save_meta()
    assert versions.record(project, "designed", "Second") == 2
    (kept / "0001" / "notes.jsonl").write_text("someone@example.com")
    (kept / "0001" / "leak.png").write_text("someone@example.com")
    shutil.copytree(kept / "0001", kept / "0009")
    (kept / "0002" / "card.png").unlink()
    (kept / "0002" / "card.png").symlink_to("../../designer/run.jsonl")
    got, _, body = running.request(path)
    assert got == status, path
    assert b"example.com" not in body and b"TOP SECRET" not in body
    if status == 200:
        assert body == (projects / "pawn" / path.split("/files/")[1]).read_bytes()


def test_jobs_keep_versions_and_one_can_be_brought_back(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch, remembered_rebuild: None
) -> None:
    folder = projects / "pawn"
    info = running.get_json("/api/p/pawn")
    assert info["versions"] == [] and info["current_version"] is None
    # building a model made before versions were kept keeps its present state, once
    job = running.wait(running.post("/api/p/pawn/build", {})[1]["job"])
    assert job["state"] == "done", job
    assert not any(line.startswith("Kept as version") for line in job["progress"])
    monkeypatch.setattr(runner, "run_designer", FakeDesigner())
    job = running.wait(running.post("/api/p/pawn/design", AGREED)[1]["job"])
    assert job["state"] == "done", job
    assert "Kept as version 2: AI design" in job["progress"]
    request = {**AGREED, "request": "make the base blue"}
    job = running.wait(running.post("/api/p/pawn/design", request)[1]["job"])
    assert job["state"] == "done", job  # the fake paints the same: nothing new to keep
    info = running.get_json("/api/p/pawn")
    assert [(v["n"], v["kind"], v["label"], v["valid"]) for v in info["versions"]] == [
        (1, "converted", "The model as it was", True),
        (2, "designed", "AI design", True),
    ]
    assert info["current_version"] == 2 and info["current"] is True
    first = info["versions"][0]
    assert first["picture"] == "/p/pawn/files/versions/0001/card.png"
    assert first["parts"] > 0 and first["created"].endswith("Z") and first["note"] == ""
    assert running.request(first["picture"])[0] == 200

    # restoring: the token and a version number are needed
    assert running.post("/api/p/pawn/restore", {"version": 1}, token=False)[0] == 403
    for bad in ({}, {"version": "1"}, {"version": 0}, {"version": True}):
        status, answer = running.post("/api/p/pawn/restore", bad)
        assert status == 400 and "which version" in answer["error"], bad
    job = running.wait(running.post("/api/p/pawn/restore", {"version": 7})[1]["job"])
    assert job["state"] == "failed" and job["error"].startswith("This model has no version 7")
    (folder / "parts.csv").write_text("from an older build")
    compare = (folder / "renders" / "compare.png").stat().st_mtime_ns
    job = running.wait(running.post("/api/p/pawn/restore", {"version": 1})[1]["job"])
    assert job["state"] == "done", job
    assert job["progress"][0] == "Going back to version 1: The model as it was"
    assert job["result"]["version"] == 1 and job["result"]["valid"] is True
    project = Project(folder)
    assert "brief" not in project.meta and project.build_is_current()
    assert (folder / "parts.csv").read_text().startswith("Part,")
    assert (folder / "renders" / "compare.png").stat().st_mtime_ns != compare
    assert (folder / "build.rough.json").is_file()
    info = running.get_json("/api/p/pawn")
    assert info["current_version"] == 1 and len(info["versions"]) == 2
    assert info["brief"] is None


# ---- jobs ---------------------------------------------------------------------------------


def test_a_new_project_from_an_upload(running: Running, projects: Path, pawn_path: Path) -> None:
    status, answer = running.upload(
        pawn_path.read_bytes(), filename="My Pawn.STL", fields={"studs": "8", "hollow": "on"}
    )
    assert status == 202
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    assert job["kind"] == "new" and job["error"] is None
    assert job["progress"][0] == "Reading My Pawn.STL and turning it into bricks"
    assert any("Laying out the bricks" in line for line in job["progress"])
    assert job["result"]["project"] == "my-pawn" and job["result"]["valid"] is True
    project = Project(projects / "my-pawn")
    assert project.name == "My Pawn" and project.meta["hollow"] is True
    assert project.meta["studs"] == 8
    for name in ("build.json", "build.ldr", "build.rough.json", "renders/compare.png"):
        assert (project.path / name).is_file(), name
    assert project.build_is_current()
    names = [c["project"] for c in running.get_json("/api/projects")["projects"]]
    assert names[0] == "my-pawn"


@pytest.mark.parametrize(
    ("fields", "words"),
    [({"studs": "3"}, "between 4 and 96"), ({"studs": "ten"}, "whole number"), ({}, None)],
)
def test_the_size_is_checked_before_anything_starts(
    running: Running, projects: Path, fields: dict[str, str], words: str | None
) -> None:
    if words is None:  # no file at all
        body = b'--b\r\nContent-Disposition: form-data; name="studs"\r\n\r\n8\r\n--b--\r\n'
        status, _, data = running.request(
            "/api/projects",
            "POST",
            body=body,
            headers={"Content-Type": "multipart/form-data; boundary=b"},
            token=True,
        )
        assert status == 400 and b"Choose a 3D model file" in data
        return
    status, data = running.upload(b"solid x\n", fields=fields)
    assert status == 400 and words in data["error"]
    assert running.app.jobs == {} and running.app.busy == {}


def test_a_failed_job_says_why_in_plain_words(running: Running, projects: Path) -> None:
    status, answer = running.upload(b"this is not a model\n", filename="broken.stl")
    assert status == 202
    job = running.wait(answer["job"])
    assert job["state"] == "failed"
    assert "contains no triangles" in job["error"]  # load_seed's own message, as the CLI prints
    assert "Traceback" not in job["error"]
    assert sorted(p.name for p in projects.iterdir() if p.name != ".incoming") == ["pawn"]
    assert not any((projects / ".incoming").glob("*"))
    assert running.app.busy == {}


def test_a_fault_is_logged_and_the_server_carries_on(
    running: Running, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken(project: Project, **kw: Any) -> Any:
        raise RuntimeError("the inside of the machine")

    monkeypatch.setattr(pipeline, "rebuild", broken)
    status, answer = running.post("/api/p/pawn/build", {})
    assert status == 202
    job = running.wait(answer["job"])
    assert job["state"] == "failed"
    assert "went wrong inside BrickSnap" in job["error"]
    assert "the inside of the machine" not in job["error"] and "Traceback" not in job["error"]
    err = capsys.readouterr().err
    assert "Traceback" in err and "the inside of the machine" in err
    assert running.request("/")[0] == 200
    assert running.app.busy == {}


def test_one_job_at_a_time_per_project(
    running: Running,
    projects: Path,
    built_pawn: Path,
    monkeypatch: pytest.MonkeyPatch,
    remembered_rebuild: None,
) -> None:
    add_project(projects, built_pawn, "rook")
    gate = gate_rebuild(monkeypatch)
    status, first = running.post("/api/p/pawn/build", {})
    assert status == 202
    assert gate.reached.wait(10)
    for action in ("build", "export", "instructions", "delete"):
        status, data = running.post(f"/api/p/pawn/{action}", {})
        assert status == 409, action
        assert '"pawn" is busy: rebuilding the bricks' in data["error"]
    info = running.get_json("/api/p/pawn")
    assert info["job"]["id"] == first["job"] and info["job"]["state"] == "running"
    assert running.get_json("/api/projects")["projects"][0]["job"] == first["job"]
    status, other = running.post("/api/p/rook/build", {})  # another project runs side by side
    assert status == 202
    gate.open.set()
    assert running.wait(first["job"])["state"] == "done"
    assert running.wait(other["job"])["state"] == "done"
    status, again = running.post("/api/p/pawn/build", {})
    assert status == 202
    assert running.wait(again["job"])["state"] == "done"


def test_only_one_ai_job_for_the_whole_server(
    running: Running,
    projects: Path,
    built_pawn: Path,
    monkeypatch: pytest.MonkeyPatch,
    remembered_rebuild: None,
) -> None:
    add_project(projects, built_pawn, "rook")
    gate = Gate()
    fake = FakeDesigner(gate=gate)
    monkeypatch.setattr(runner, "run_designer", fake)
    status, first = running.post("/api/p/pawn/design", AGREED)
    assert status == 202
    assert gate.reached.wait(20)
    status, data = running.post("/api/p/rook/design", AGREED)
    assert status == 409 and 'already working on "pawn"' in data["error"]
    status, other = running.post("/api/p/rook/build", {})  # other jobs are fine
    assert status == 202
    gate.open.set()
    assert running.wait(first["job"])["state"] == "done"
    assert running.wait(other["job"])["state"] == "done"
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "body",
    [{}, {"understood": False}, {"understood": "true"}, {"understood": 1}, {"request": "red"}],
)
def test_the_designer_needs_the_persons_agreement(running: Running, body: dict) -> None:
    status, data = running.post("/api/p/pawn/design", body)
    assert status == 400
    assert "your own Claude Code login" in data["error"]
    assert running.app.jobs == {}


@pytest.mark.parametrize(
    ("body", "words"),
    [
        ({"request": "   "}, "The request is empty"),
        ({"request": 5}, "must be text"),
        ({"request": "x" * 2001}, "too long"),
        ({"best_of": 0}, "from 1 to 5"),
        ({"best_of": 6}, "from 1 to 5"),
        ({"best_of": "3"}, "from 1 to 5"),
        ({"best_of": True}, "from 1 to 5"),
    ],
)
def test_design_requests_are_checked(running: Running, body: dict, words: str) -> None:
    status, data = running.post("/api/p/pawn/design", {**body, "understood": True})
    assert status == 400 and words in data["error"]
    assert running.app.jobs == {}


def test_a_design_job_reports_progress_in_plain_words(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch, remembered_rebuild: None
) -> None:
    fake = FakeDesigner()
    monkeypatch.setattr(runner, "run_designer", fake)
    status, answer = running.post("/api/p/pawn/design", AGREED)
    assert status == 202
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    progress = job["progress"]
    assert "This is a first design of the model" in progress
    assert "The designer has started" in progress
    assert "The designer is looking at the model" in progress
    assert "The designer changed the design (3 edits)" in progress
    said = [line for line in progress if line.startswith("The designer says:")]
    assert said and "<account email>" in said[0]
    assert "someone@example.com" not in json.dumps(job)
    assert str(Path.home()) not in json.dumps(job)
    assert fake.calls[0].get("instruction") is None
    assert job["result"]["edits"] == 1 and job["result"]["said"] == "Painted the base red."
    project = Project(projects / "pawn")
    assert project.build_is_current()  # rebuilt after the run, as the command line does
    assert running.get_json("/api/p/pawn")["brief"] == BRIEF


def test_a_change_in_words_is_passed_on_as_an_edit(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch, remembered_rebuild: None
) -> None:
    project = Project(projects / "pawn")
    project.meta["brief"] = BRIEF
    project.save_meta()
    fake = FakeDesigner()
    monkeypatch.setattr(runner, "run_designer", fake)
    status, answer = running.post(
        "/api/p/pawn/design", {**AGREED, "request": "  add a red collar "}
    )
    assert status == 202
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    assert fake.calls[0]["instruction"] == "add a red collar"
    assert job["result"]["kind"] == "edit"
    assert (
        'This is one change to a model that is already designed: "add a red collar"'
        in (job["progress"])
    )


def test_a_design_run_that_fails_says_so(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch, remembered_rebuild: None
) -> None:
    monkeypatch.setattr(runner, "run_designer", FakeDesigner(ok=False))
    status, answer = running.post("/api/p/pawn/design", AGREED)
    job = running.wait(answer["job"])
    assert job["state"] == "failed"
    assert job["error"].startswith("The AI designer did not finish: Claude Code is not signed in.")
    assert "kept" in job["error"]
    assert Project(projects / "pawn").build_is_current()
    assert running.app.ai_job is None


def test_best_of_several_goes_through_the_judge(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[int, dict[str, Any]]] = []

    def fake_best_of(project: Project, n: int, **options: Any) -> BestOf:
        calls.append((n, options))
        tell = options["on_event"]
        for i in range(1, n + 1):
            tell({"event": "designing", "candidate": i, "of": n})
            tell({"event": "designed", "candidate": i, "of": n, "valid": i != 2, "why": "loose"})
        tell({"event": "judging", "candidates": n - 1})
        tell({"event": "judged", "ok": True, "error": ""})
        tell({"event": "kept", "winner": 3, "by_measurement": False})
        return BestOf(winner=3, ranking=[3, 1], summary="Three is best.")

    monkeypatch.setattr(judge, "design_best_of", fake_best_of)
    status, answer = running.post(
        "/api/p/pawn/design", {**AGREED, "understood_runs": 4, "best_of": 3}
    )
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    assert calls[0][0] == 3 and "instruction" not in calls[0][1]
    for line in (
        "Starting 4 AI runs one after another: 3 designs and one judging run",
        "Designing 1 of 3",
        "Design 2 cannot be used: loose",
        "Judging the two designs",
        "Kept design 3",
    ):
        assert line in job["progress"], line
    assert job["result"]["winner"] == 3 and job["result"]["summary"] == "Three is best."


def test_best_of_with_no_winner_fails_plainly(
    running: Running, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        judge, "design_best_of", lambda *a, **k: BestOf(error="No design holds together.")
    )
    status, answer = running.post(
        "/api/p/pawn/design", {**AGREED, "understood_runs": 3, "best_of": 2}
    )
    job = running.wait(answer["job"])
    assert job["state"] == "failed" and job["error"].startswith("No design holds together.")


def test_export_and_instructions(running: Running, projects: Path) -> None:
    status, answer = running.post("/api/p/pawn/export", {})
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    assert job["result"]["files"] == ["build.ldr", "parts.csv", "wanted_list.xml"]
    assert any(line.startswith("The model needs") for line in job["progress"])
    status, answer = running.post("/api/p/pawn/instructions", {})
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    assert job["progress"][-1].startswith("Wrote the booklet")
    info = running.get_json("/api/p/pawn")
    assert info["files"] == list(webapp.DOWNLOADS)
    status, headers, body = running.request("/p/pawn/files/instructions.pdf")
    assert status == 200 and headers["content-type"] == "application/pdf"
    assert body.startswith(b"%PDF")
    status, headers, _ = running.request("/p/pawn/files/instructions.html")
    assert status == 200 and "sandbox" in headers["content-security-policy"]
    assert running.request("/p/pawn/files/parts.csv")[1]["content-type"].startswith("text/csv")


def test_downloads_follow_the_build(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whatever changes the build writes the parts list and the wanted list again, and the
    booklet too when there was one, so the files a person downloads are never those of an
    older build."""
    folder = projects / "pawn"
    for name in ("parts.csv", "wanted_list.xml", "instructions.pdf", "instructions.html"):
        (folder / name).unlink(missing_ok=True)
    # a build with no booklet: the two lists appear, no booklet is made
    job = running.wait(running.post("/api/p/pawn/build", {})[1]["job"])
    assert job["state"] == "done", job
    files = running.get_json("/api/p/pawn")["files"]
    assert "parts.csv" in files and "wanted_list.xml" in files
    assert "instructions.pdf" not in files and "instructions.html" not in files
    # stale files from an older build are replaced, the booklet included once there is one
    for name in ("parts.csv", "wanted_list.xml", "instructions.pdf", "instructions.html"):
        (folder / name).write_text("from an older build")
    job = running.wait(running.post("/api/p/pawn/build", {})[1]["job"])
    assert job["state"] == "done", job
    assert "Bringing the instruction booklet up to date" in job["progress"]
    assert (folder / "parts.csv").read_text().startswith("Part,")
    assert "<INVENTORY>" in (folder / "wanted_list.xml").read_text()
    assert (folder / "instructions.pdf").read_bytes().startswith(b"%PDF")
    assert "from an older build" not in (folder / "instructions.html").read_text()

    # files that cannot be written again are removed, said in the progress, and the build stands
    def broken(*args: Any, **kwargs: Any) -> None:
        raise ValueError("no")

    monkeypatch.setattr("bricksnap.export.write_exports", broken)
    monkeypatch.setattr("bricksnap.instructions.make_instructions", broken)
    job = running.wait(running.post("/api/p/pawn/build", {})[1]["job"])
    assert job["state"] == "done", job
    assert sum("the older one was removed" in line for line in job["progress"]) == 2
    files = running.get_json("/api/p/pawn")["files"]
    assert files == ["build.ldr", "renders/compare.png"]


def test_a_new_model_has_its_lists_from_the_start(
    running: Running, projects: Path, pawn_path: Path
) -> None:
    status, answer = running.upload(pawn_path.read_bytes())
    assert status == 202, answer
    job = running.wait(answer["job"])
    assert job["state"] == "done", job
    files = running.get_json(f"/api/p/{job['result']['project']}")["files"]
    assert files == ["build.ldr", "parts.csv", "wanted_list.xml", "renders/compare.png"]


def test_instructions_for_a_build_that_does_not_hold_fail_plainly(
    running: Running, projects: Path
) -> None:
    path = projects / "pawn" / "build.json"
    data = json.loads(path.read_text())
    data["parts"] = data["parts"] + [{**data["parts"][0], "x": 40, "y": 40, "z": 0}]
    path.write_text(json.dumps(data))
    status, answer = running.post("/api/p/pawn/instructions", {})
    job = running.wait(answer["job"])
    assert job["state"] == "failed"
    assert "does not pass its checks" in job["error"]


def test_delete_moves_the_project_to_the_trash(
    running: Running, projects: Path, built_pawn: Path
) -> None:
    status, data = running.post("/api/p/pawn/delete", {})
    assert status == 200 and data == {
        "deleted": "pawn",
        "moved_to": ".trash/pawn",
        "folder": str(projects / ".trash" / "pawn"),
    }
    assert (projects / ".trash" / "pawn" / "project.json").is_file()
    assert running.get_json("/api/projects")["projects"] == []
    add_project(projects, built_pawn, "pawn")
    status, data = running.post("/api/p/pawn/delete", {})
    assert status == 200 and data["moved_to"].startswith(".trash/pawn-")
    assert len(list((projects / ".trash").iterdir())) == 2
    status, data = running.post("/api/p/pawn/delete", {})
    assert status == 404


def test_unknown_actions_are_refused(running: Running, remembered_rebuild: None) -> None:
    for path in ("/api/p/pawn/explode", "/api/p/pawn", "/api/other", "/api/p/../x/build"):
        assert running.post(path, {})[0] == 404, path
    status, data = running.post("/api/p/pawn/build", None, headers={"Content-Type": "x"})
    assert status == 202
    running.wait(data["job"])
    status, _, _ = running.request("/api/p/pawn/build", "POST", body=b"[1, 2]", token=True)
    assert status == 400


# ---- the server itself --------------------------------------------------------------------


def test_bad_ports_and_folders_are_plain_errors(running: Running, tmp_path: Path) -> None:
    with pytest.raises(ProjectError, match="whole number from 0 to 65535"):
        make_app_server(tmp_path, port=70000)
    with pytest.raises(ProjectError, match="already in use"):
        make_app_server(tmp_path, port=running.port)
    (tmp_path / "file").write_text("x")
    with pytest.raises(ProjectError, match="is a file"):
        make_app_server(tmp_path / "file", port=0)
    server = make_app_server(tmp_path / "new" / "projects", port=0)  # made when missing
    server.server_close()
    assert (tmp_path / "new" / "projects").is_dir()


def test_serve_app_prints_the_address_and_stops_on_ctrl_c(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def interrupted(self: Any, poll_interval: float = 0.5) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(webapp.AppServer, "serve_forever", interrupted)
    serve_app(tmp_path, port=0, open_browser=False)
    out = capsys.readouterr().out
    assert re.search(r"BrickSnap is running at http://127\.0\.0\.1:\d+/", out)
    assert "Ctrl+C" in out and "BrickSnap stopped." in out


def test_read_form_handles_boundaries_split_across_reads(tmp_path: Path) -> None:
    content = bytes(range(256)) * 700 + b"\r\n--BrickSnapTestBoundar"  # almost a boundary
    body, _ = multipart(content, "a.stl", {"studs": "12", "name": "Rook"})
    saved: list[str] = []

    def save(name: str) -> Path:
        saved.append(name)
        return tmp_path / "upload.stl"

    fields, name, size = read_form(io.BytesIO(body), len(body), b"BrickSnapTestBoundary", save)
    assert fields == {"studs": "12", "name": "Rook"} and name == "a.stl" == saved[0]
    assert size == len(content) and (tmp_path / "upload.stl").read_bytes() == content

    # The socket hands over a few bytes at a time, so every boundary arrives in pieces.
    small = b"\r\n--BrickSnapTest" + bytes(range(256)) * 8 + b"\r\n--BrickSnapTestBoundar\r"
    body, _ = multipart(small, "a.stl", {"studs": "12", "name": "Rook"})
    for step in (1, 2, 5, 7, 13, 23, 64):
        reader = Trickle(body, step)
        fields, name, size = read_form(reader, len(body), b"BrickSnapTestBoundary", save)
        assert fields == {"studs": "12", "name": "Rook"}, step
        assert (tmp_path / "upload.stl").read_bytes() == small, step
        assert reader.reads >= (len(body) - 2) // step  # all but the closing CRLF, in pieces
    with pytest.raises(Refused, match="stopped before"):
        read_form(io.BytesIO(body[:-100]), len(body), b"BrickSnapTestBoundary", save)
    with pytest.raises(Refused):
        read_form(io.BytesIO(b"garbage" * 10), 70, b"BrickSnapTestBoundary", save)


class Trickle:
    """A body that arrives at most ``step`` bytes per read, as a slow socket gives it."""

    def __init__(self, data: bytes, step: int) -> None:
        self.data, self.step, self.at, self.reads = data, step, 0, 0

    def read(self, size: int, /) -> bytes:
        self.reads += 1
        piece = self.data[self.at : self.at + min(size, self.step)]
        self.at += len(piece)
        return piece


def test_progress_sentences_unit() -> None:
    assert webapp.designer_progress({"type": "user"}) == []
    lines = webapp.designer_progress(tool_use("mystery", {}))
    assert lines == ["The designer is using its mystery tool"]
    long = {"type": "assistant", "message": {"content": [{"type": "text", "text": "a " * 400}]}}
    assert len(webapp.designer_progress(long)[0]) <= len("The designer says: ") + 240
    assert webapp.best_of_progress({"event": "kept", "winner": 2, "by_measurement": True}) == (
        "Kept design 2 (chosen by measurement)"
    )
    assert webapp.best_of_progress({"event": "judged", "ok": False, "error": "x"}) == (
        "The judge did not finish: x"
    )


def test_a_refused_request_never_touches_a_project_with_a_running_job(
    running: Running, projects: Path, monkeypatch: pytest.MonkeyPatch, remembered_rebuild: None
) -> None:
    gate = gate_rebuild(monkeypatch)
    status, first = running.post("/api/p/pawn/build", {})
    assert status == 202 and gate.reached.wait(10)
    # what a best-of run has half done while it puts its winner in place
    held = [projects / "pawn" / judge.STAGING_DIR, projects / "pawn" / judge.BACKUP_DIR]
    for folder in held:
        folder.mkdir()
        (folder / "marker").write_text("x")
    monkeypatch.setattr(runner, "run_designer", FakeDesigner())
    for action, body in (
        ("export", {}),
        ("instructions", {}),
        ("build", {}),
        ("design", AGREED),
        ("delete", {}),
    ):
        status, data = running.post(f"/api/p/pawn/{action}", body)
        assert status == 409 and "is busy" in data["error"], action
        assert all((folder / "marker").is_file() for folder in held), action
    for folder in held:
        shutil.rmtree(folder)
    gate.open.set()
    assert running.wait(first["job"])["state"] == "done"


def test_a_job_that_is_refused_or_stopped_is_marked_failed(
    running: Running, capsys: pytest.CaptureFixture[str]
) -> None:
    def binned(job: Any) -> dict[str, Any]:
        raise Refused("There is no project called 'pawn' here.", 404)

    state = running.wait(running.app.start("build", "pawn", binned).id)
    assert state["state"] == "failed"
    assert state["error"] == "There is no project called 'pawn' here."
    assert "Traceback" not in capsys.readouterr().err

    def stopped(job: Any) -> dict[str, Any]:
        raise SystemExit(3)

    state = running.wait(running.app.start("build", "pawn", stopped).id)
    assert state["state"] == "failed" and "went wrong inside BrickSnap" in state["error"]
    assert running.app.busy == {}


def test_an_idle_connection_is_closed_but_a_slow_upload_works(
    projects: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(webapp, "REQUEST_TIMEOUT_S", 0.5)
    r = Running(projects)
    try:
        sock = socket.create_connection(("127.0.0.1", r.port), timeout=5)
        started = time.time()
        assert sock.recv(100) == b""  # nothing was sent, so the server gave up
        assert time.time() - started < 4
        sock.close()
        body, ctype = multipart(b"solid x\n" + b"x" * (1024 * 1024), "slow.stl", {"studs": "8"})
        conn = http.client.HTTPConnection("127.0.0.1", r.port, timeout=10)
        conn.putrequest("POST", "/api/projects")
        conn.putheader("Content-Type", ctype)
        conn.putheader("Content-Length", str(len(body)))
        conn.putheader(webapp.TOKEN_HEADER, r.token)
        conn.endheaders()
        for at in range(0, len(body), 64 * 1024):  # longer than the timeout in all
            conn.send(body[at : at + 64 * 1024])
            time.sleep(0.05)
        res = conn.getresponse()
        answer = json.loads(res.read())
        conn.close()
        assert res.status == 202, answer
        r.wait(answer["job"])
    finally:
        r.close()


def test_command_line_advice_becomes_which_button_to_press(
    running: Running, projects: Path
) -> None:
    (projects / "pawn" / "build.json").write_text("{not json", "utf-8")
    status, answer = running.post("/api/p/pawn/export", {})
    job = running.wait(answer["job"])
    assert job["state"] == "failed"
    assert "is damaged" in job["error"]
    assert "uv run" not in job["error"] and "bricksnap build" not in job["error"]
    assert job["error"].endswith('Press "Build the bricks again" on the model\'s page.')
    page = webapp.for_the_page
    assert page("x has no design yet. Run 'bricksnap new' first.") == (
        'x has no design yet. Make the model again from its file on the home page ("Make a new '
        'model").'
    )
    assert "Ask the AI designer" in page(
        "It does not pass. Look at the check report ('bricksnap check /p') and fix it first."
    )
    plain = "The file /home/me/bricksnap/projects/cat/build.json cannot be read."
    assert page(plain) == plain  # a folder called bricksnap is not advice


def test_a_gltf_that_needs_other_files_is_refused_plainly(running: Running, projects: Path) -> None:
    gltf = {"asset": {"version": "2.0"}, "buffers": [{"uri": "cat.bin", "byteLength": 12}]}
    status, data = running.upload(json.dumps(gltf).encode(), filename="cat.gltf")
    assert status == 400
    assert "cat.gltf keeps its data in separate files" in data["error"] and ".glb" in data["error"]
    assert sorted(p.name for p in projects.iterdir() if p.name != ".incoming") == ["pawn"]
    inside = {**gltf, "buffers": [{"uri": "data:application/octet-stream;base64,AAAA"}]}
    assert not webapp.gltf_needs_other_files(_write(projects.parent / "in.gltf", inside))


def _write(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value), "utf-8")
    return path


@pytest.mark.parametrize(
    "body",
    [
        {"understood": True},
        {**AGREED, "best_of": 3},
        {**AGREED, "understood_runs": True},
        {**AGREED, "understood_runs": 4, "best_of": 2},
        {**AGREED, "understood_runs": "1"},
    ],
)
def test_the_agreement_must_be_for_the_number_of_runs(running: Running, body: dict) -> None:
    status, data = running.post("/api/p/pawn/design", body)
    assert status == 400 and "not the number you agreed to" in data["error"]
    assert running.app.jobs == {}


def test_an_unknown_project_gets_a_friendly_page(running: Running, projects: Path) -> None:
    for path in ("/p/missing", "/p/missing/", "/p/.trash"):
        status, headers, body = running.request(path)
        assert status == 404 and headers["content-type"].startswith("text/html"), path
        assert b"This model is not here" in body and b'href="/"' in body
        assert TRADEMARK.encode() in body.replace(b",\n  ", b", ")
    assert running.get_json("/api/p/pawn")["bin"] == str(projects / ".trash")


def test_the_card_picture_is_the_finished_build(
    running: Running, projects: Path, remembered_rebuild: None
) -> None:
    card = projects / "pawn" / "renders" / "card.png"
    card.unlink()
    status, answer = running.post("/api/p/pawn/build", {})
    assert running.wait(answer["job"])["state"] == "done"
    image = Image.open(card)
    assert image.size == pipeline.CARD_SIZE
    pixels = np.asarray(image.convert("RGB")).astype(int)
    drawn = np.abs(pixels - np.array(render.BACKGROUND)).sum(axis=2) > 30
    assert drawn.mean() > 0.15  # the bricks fill the card
    for edge in (drawn[:12], drawn[-12:], drawn[:, :12], drawn[:, -12:]):
        assert not edge.any()  # no labels, ticks or captions round it
    picture = running.get_json("/api/projects")["projects"][0]["picture"]
    assert picture.startswith("/p/pawn/files/renders/card.png?v=")
    assert running.request(picture)[0] == 200


def test_pages_have_the_trademark_and_fetch_nothing_from_the_internet() -> None:
    assert TRADEMARK in (VIEWER / "home.html").read_text("utf-8")
    for name in ("home.html", "home.js", "app.js", "app.css"):
        text = (VIEWER / name).read_text("utf-8")
        urls = re.findall(r"https?://[^\s\"')]+", text)
        assert all(u.startswith("http://www.w3.org/") for u in urls), (name, urls)
        assert "@import" not in text
    for name in ("home.js", "app.js"):
        js = (VIEWER / name).read_text("utf-8")
        for sink in (
            r"\.innerHTML\b",
            r"\.outerHTML\b",
            r"insertAdjacentHTML\(",
            r"document\.write",
        ):
            assert not re.search(sink, js), (name, sink)


# ---- browser tests ------------------------------------------------------------------------


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


class Tab:
    """A browser tab that records console errors, failed and external requests."""

    def __init__(self, browser: Any, base: str, width: int = 1200, height: int = 860) -> None:
        self.base = base
        self.context = browser.new_context(viewport={"width": width, "height": height})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.failed: list[str] = []
        self.external: list[str] = []
        self.page.on("console", lambda m: m.type == "error" and self.errors.append(m.text))
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("requestfailed", lambda r: self.failed.append(r.url))
        self.page.on(
            "request",
            lambda r: r.url.startswith((base, "data:", "blob:")) or self.external.append(r.url),
        )
        self.page.on("response", lambda r: r.status >= 400 and self.failed.append(r.url))

    def open(self, path: str = "") -> Tab:
        self.page.goto(self.base + path)
        self.page.wait_for_function("window.__bricksnapApp && window.__bricksnapApp.ready")
        return self

    def text(self, selector: str) -> str:
        return self.page.locator(selector).text_content() or ""

    def shot(self, name: str, full: bool = True) -> None:
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(ARTIFACTS / f"webapp-{name}.png"), full_page=full)

    def no_sideways_scroll(self) -> None:
        wide = self.page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert wide <= 0, wide

    def assert_clean(self) -> None:
        assert self.errors == [], self.errors
        assert self.failed == [], self.failed
        assert self.external == [], self.external

    def close(self) -> None:
        self.context.close()


@pytest.mark.browser
def test_browser_home_page_lists_the_projects(
    browser: Any, running: Running, projects: Path, built_pawn: Path
) -> None:
    add_project(projects, built_pawn, "evil", name=f"Rook {MARKUP} & co")
    tab = Tab(browser, running.url).open()
    try:
        cards = tab.page.locator(".pcard")
        assert cards.count() == 2
        names = tab.page.locator(".pcard .pname").all_text_contents()
        assert f"Rook {MARKUP} & co" in names
        assert tab.page.evaluate("() => window.__pwned") is None
        assert tab.page.locator(".pcard img[src='x']").count() == 0
        tab.page.wait_for_function(
            "() => [...document.querySelectorAll('.pcard img')]"
            ".every(i => i.complete && i.naturalWidth > 0)"
        )
        assert tab.page.locator(".pcard .badge.ok").count() == 2
        assert TRADEMARK in (tab.page.locator("#trademark").text_content() or "")
        tab.shot("home-two-projects")
        tab.assert_clean()
    finally:
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open()
    try:
        phone.no_sideways_scroll()
        phone.shot("home-phone")
        phone.assert_clean()
    finally:
        phone.close()


@pytest.mark.browser
def test_browser_home_page_with_no_projects(browser: Any, tmp_path: Path) -> None:
    r = Running(tmp_path / "empty")
    tab = Tab(browser, r.url).open()
    try:
        assert tab.page.locator("#empty").is_visible()
        assert tab.page.locator("#go").is_visible()
        tab.shot("home-empty")
        tab.assert_clean()
    finally:
        tab.close()
        r.close()


@pytest.mark.browser
def test_browser_making_a_new_model(
    browser: Any, running: Running, projects: Path, pawn_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    gate = gate_rebuild(monkeypatch)
    tab = Tab(browser, running.url).open()
    try:
        page = tab.page
        page.locator("#go").click()
        assert "Choose a 3D model file first." in (page.locator("#formMsg").text_content() or "")
        page.set_input_files("#model", str(pawn_path))
        page.eval_on_selector(
            "#studs", "e => { e.value = '8'; e.dispatchEvent(new Event('input')); }"
        )
        assert page.locator("#studsOut").text_content() == "8 studs"
        page.locator("#go").click()
        page.wait_for_selector(".job ul.progress li >> text=Laying out the bricks")
        assert gate.reached.wait(20)
        assert "safe to leave this page" in (page.locator(".job .leave").text_content() or "")
        tab.shot("new-project-running")
        gate.open.set()
        page.wait_for_selector("a.button.primary >> text=Open your model", timeout=30000)
        page.wait_for_selector(".pcard[data-project='pawn-2']")
        tab.assert_clean()
        page.locator("a >> text=Open your model").click()
        page.wait_for_function("window.__bricksnap && window.__bricksnap.ready === true")
        assert page.url.endswith("/p/pawn-2")
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_a_failed_job_says_what_to_do(
    browser: Any, running: Running, tmp_path: Path
) -> None:
    broken = tmp_path / "broken.stl"
    broken.write_text("this is not a model\n")
    tab = Tab(browser, running.url).open()
    try:
        page = tab.page
        page.set_input_files("#model", str(broken))
        page.locator("#go").click()
        page.wait_for_selector(".job.failed")
        assert "contains no triangles" in (page.locator(".job .error").text_content() or "")
        assert (page.locator(".job .todo").text_content() or "").startswith("What to do:")
        tab.shot("failed-job")
        tab.assert_clean()
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_project_page_and_a_design_run(
    browser: Any,
    running: Running,
    projects: Path,
    monkeypatch: pytest.MonkeyPatch,
    remembered_rebuild: None,
) -> None:
    gate = Gate()
    fake = FakeDesigner(gate=gate)
    monkeypatch.setattr(runner, "run_designer", fake)
    tab = Tab(browser, running.url).open("p/pawn")
    try:
        page = tab.page
        page.wait_for_function("window.__bricksnap && window.__bricksnap.ready === true")
        state = page.evaluate(
            "() => ({parts: window.__bricksnap.partCount,"
            " compare: window.__bricksnap.inspect().compare})"
        )
        assert state["parts"] > 0 and state["compare"]["active"] is True  # plain beside designed
        # no AI design yet: the right-hand view is BrickSnap's own finishing
        assert tab.text("#designedTag .pane-title") == "Finished"
        assert "tiles and slopes" in tab.text("#designedTag")
        assert tab.text('#compare button[data-show="designed"]') == "Finished"
        assert tab.text("#stepsFor") == "The steps are for the finished build."
        assert page.locator("#actions").is_visible()
        assert page.locator("#aiOpen").is_visible()
        links = page.locator("#downloads a")
        assert links.count() == 2 and links.first.get_attribute("href") == "/p/pawn/files/build.ldr"
        tab.shot("project-page")
        page.locator("#aiOpen").click()
        confirm = page.locator("#aiConfirm")
        assert confirm.is_visible()
        text = confirm.text_content() or ""
        assert "Anthropic" in text and "own Claude Code login" in text
        assert "It starts 1 AI run." in text
        page.select_option("#bestOf", "3")
        assert "It starts 4 AI runs" in (page.locator("#aiRuns").text_content() or "")
        page.select_option("#bestOf", "1")
        assert page.locator("#aiStart").is_disabled()
        tab.shot("ai-confirm", full=False)
        page.locator("#aiUnderstood").check()
        assert page.locator("#aiStart").is_enabled()
        page.locator("#aiStart").click()
        page.wait_for_selector("#appJob li >> text=The designer changed the design (3 edits)")
        assert gate.reached.wait(20)
        assert page.locator("#actBuild").is_disabled()
        tab.shot("design-running", full=False)
        gate.open.set()
        page.wait_for_selector("#appJob .job.done")
        page.wait_for_selector("#askText")  # the model has a brief now: ask for a change
        assert len(fake.calls) == 1
        page.wait_for_function(
            "document.querySelector('#designedTag .pane-title').textContent === 'AI design'"
        )  # the model now has versions: what it was, and this design, which is in use
        assert tab.text("#designedTag .pane-what") == "Version 2 (in use) · "
        assert tab.text('#compare button[data-show="designed"]') == "Right"
        assert tab.text("#stepsFor") == "The steps are for version 2."
        # after a finished run the confirmation still closes
        page.locator("#askText").fill("make the base blue")
        page.locator("#askBtn").click()
        assert page.locator("#aiCancel").is_enabled()
        page.locator("#aiCancel").click()
        assert page.locator("#aiConfirm").is_hidden()
        tab.assert_clean()
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_the_confirmation_can_always_be_closed(
    browser: Any, running: Running, projects: Path
) -> None:
    tab = Tab(browser, running.url).open("p/pawn")
    try:
        page = tab.page
        confirm = page.locator("#aiConfirm")
        page.locator("#actExport").click()  # any action first: it disables every button
        page.wait_for_selector("#appJob .job.done")
        page.wait_for_function("!document.querySelector('#aiOpen').disabled")
        page.locator("#aiOpen").click()
        assert page.locator("#aiCancel").is_enabled()
        page.locator("#aiCancel").click()
        assert confirm.is_hidden()
        page.locator("#aiOpen").click()
        page.keyboard.press("Escape")
        assert confirm.is_hidden()

        # the number of runs is part of the agreement: changing it asks again
        page.locator("#aiOpen").click()
        page.locator("#aiUnderstood").check()
        page.select_option("#bestOf", "2")
        assert not page.locator("#aiUnderstood").is_checked()
        assert page.locator("#aiStart").is_disabled()
        assert "It starts 3 AI runs" in tab.text("#aiRuns")
        tab.shot("ai-confirm-cancel", full=False)

        # a refused start: the message shows and the confirmation still closes
        refusal = 'The AI designer is already working on "rook". Only one design runs at a time.'
        page.route(
            "**/api/p/pawn/design",
            lambda route: route.fulfill(
                status=409, content_type="application/json", body=json.dumps({"error": refusal})
            ),
        )
        page.select_option("#bestOf", "1")
        page.locator("#aiUnderstood").check()
        page.locator("#aiStart").click()
        page.wait_for_function(
            "(t) => document.querySelector('#actMsg').textContent === t", arg=refusal
        )
        page.wait_for_function("!document.querySelector('#aiOpen').disabled")
        page.locator("#aiOpen").click()
        assert page.locator("#aiCancel").is_enabled()
        page.keyboard.press("Escape")
        assert confirm.is_hidden()
        tab.failed = [url for url in tab.failed if not url.endswith("/api/p/pawn/design")]
        tab.errors = [e for e in tab.errors if "409 (Conflict)" not in e]  # the refusal above
        tab.assert_clean()
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_an_unknown_project_page(browser: Any, running: Running) -> None:
    tab = Tab(browser, running.url)
    try:
        tab.page.goto(running.url + "p/moved-away")
        assert tab.text("h1") == "This model is not here"
        assert tab.page.locator("#allModels").get_attribute("href") == "/"
        assert TRADEMARK in " ".join(tab.text("#trademark").split())
        tab.shot("not-found")
        # the page itself answers 404, which the browser notes; nothing else may fail
        assert [e for e in tab.errors if "404 (Not Found)" not in e] == []
        assert tab.failed == [running.url + "p/moved-away"] and tab.external == []
        tab.page.locator("#allModels").click()
        tab.page.wait_for_function("window.__bricksnapApp && window.__bricksnapApp.ready")
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_a_typed_change_is_shown_as_text(
    browser: Any,
    running: Running,
    projects: Path,
    monkeypatch: pytest.MonkeyPatch,
    remembered_rebuild: None,
) -> None:
    project = Project(projects / "pawn")
    project.meta["brief"] = BRIEF
    project.meta["name"] = f"Pawn {MARKUP}"
    project.save_meta()
    fake = FakeDesigner()
    monkeypatch.setattr(runner, "run_designer", fake)
    request = f"{MARKUP} make the base red"
    tab = Tab(browser, running.url).open("p/pawn")
    try:
        page = tab.page
        page.wait_for_function("window.__bricksnap && window.__bricksnap.ready === true")
        page.locator("#askText").fill(request)
        page.locator("#askBtn").click()
        assert page.locator("#aiQuote").text_content() == f"“{request}”"
        page.locator("#aiUnderstood").check()
        page.locator("#aiStart").click()
        page.wait_for_selector("#appJob .job.done")
        lines = page.locator("#appJob li").all_text_contents()
        assert any(MARKUP in line for line in lines)
        assert fake.calls[0]["instruction"] == request
        assert page.evaluate("() => window.__pwned") is None
        assert page.locator("img[src='x']").count() == 0
        tab.assert_clean()
    finally:
        tab.close()


@pytest.mark.browser
def test_browser_the_action_bar_stays_on_top_beside_a_brief(
    browser: Any, running: Running, projects: Path
) -> None:
    """A model with a brief is laid out in two columns on a wide screen: the action bar
    must still come first, above the views, not after everything else."""
    project = Project(projects / "pawn")
    project.meta["brief"] = BRIEF
    project.save_meta()
    tab = Tab(browser, running.url).open("p/pawn")
    try:
        page = tab.page
        page.set_viewport_size({"width": 1400, "height": 900})
        page.wait_for_function("window.__bricksnap && window.__bricksnap.ready === true")
        page.wait_for_selector("#askText")
        assert page.evaluate("() => document.body.classList.contains('has-brief')")
        tops = page.evaluate(
            """() => Object.fromEntries(['.actions', '.viewcard', '.brief', '.steps'].map(
                s => [s, document.querySelector(s).getBoundingClientRect()]).map(
                ([s, r]) => [s, [Math.round(r.top), Math.round(r.bottom), Math.round(r.width)]]))"""
        )
        assert tops[".actions"][1] <= tops[".viewcard"][0], tops
        assert tops[".actions"][1] <= tops[".brief"][0], tops
        assert tops[".actions"][2] > tops[".viewcard"][2], tops  # it spans both columns
        view = page.evaluate("() => document.querySelector('#view').getBoundingClientRect().top")
        assert view <= 900 - 280, view  # the 3D views begin on the first screen
        page.screenshot(path=str(ARTIFACTS / "webapp-project-with-brief.png"))
        tab.assert_clean()
    finally:
        tab.close()


def test_missing_card_pictures_are_drawn_once(running: Running, projects: Path) -> None:
    """A project made with the command line has no card picture; the app draws one, skips
    projects that have one or have no build, and survives a damaged project."""
    card = projects / "pawn" / "renders" / "card.png"
    card.unlink(missing_ok=True)
    shutil.copytree(projects / "pawn", projects / "broken")
    (projects / "broken" / "build.json").write_text("not json")
    shutil.copytree(projects / "pawn", projects / "unbuilt")
    (projects / "unbuilt" / "build.json").unlink()
    assert running.server.app.make_missing_cards() == 1
    assert card.is_file() and not (projects / "unbuilt" / "renders" / "card.png").exists()
    assert not (projects / "broken" / "renders" / "card.png").exists()
    before = card.stat().st_mtime_ns
    assert running.server.app.make_missing_cards() == 0
    assert card.stat().st_mtime_ns == before
    cards = {c["project"]: c for c in running.get_json("/api/projects")["projects"]}
    assert "/renders/card.png" in cards["pawn"]["picture"]


# ---- the command line: bricksnap serve ----------------------------------------------------


def _cli(capsys, *argv: str) -> tuple[int, str, str]:
    from bricksnap.cli import main

    code = main(list(argv))
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out + captured.err
    return code, captured.out, captured.err


def test_serve_starts_the_web_app(capsys, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "bricksnap.webapp.serve_app",
        lambda projects_dir, port, open_browser: calls.append((projects_dir, port, open_browser)),
    )
    assert _cli(capsys, "serve")[0] == 0
    assert _cli(capsys, "serve", "--dir", "elsewhere", "--port", "0", "--no-open")[0] == 0
    assert calls == [("projects", 8765, True), ("elsewhere", 0, False)]


def test_serve_reports_problems_plainly(capsys, monkeypatch):
    from bricksnap.project import ProjectError

    def busy(projects_dir, port, open_browser):
        raise ProjectError("Port 8765 is already in use. Try another with --port.")

    monkeypatch.setattr("bricksnap.webapp.serve_app", busy)
    code, _, err = _cli(capsys, "serve")
    assert code == 2
    assert err.startswith("Error: Port 8765 is already in use")
    code, _, err = _cli(capsys, "serve", "--port", "99999")
    assert code == 2
    assert "65535" in err


def test_serve_with_examples_copies_them_once(capsys, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr("bricksnap.webapp.serve_app", lambda **kwargs: calls.append(kwargs))
    target = tmp_path / "mine"
    code, out, _ = _cli(capsys, "serve", "--dir", str(target), "--examples", "--no-open")
    assert code == 0 and len(calls) == 1
    names = sorted(p.name for p in target.iterdir())
    assert names == ["car-showcase", "cat-showcase", "duck-showcase"]
    assert "Copied 3 example models" in out
    assert (target / "cat-showcase" / "build.json").is_file()
    # a second time nothing is copied and what the person changed is left alone
    (target / "cat-showcase" / "build.ldr").write_text("mine")
    code, out, _ = _cli(capsys, "serve", "--dir", str(target), "--examples", "--no-open")
    assert code == 0 and "Copied" not in out
    assert (target / "cat-showcase" / "build.ldr").read_text() == "mine"
    # without --examples nothing is copied
    code, _, _ = _cli(capsys, "serve", "--dir", str(tmp_path / "empty"), "--no-open")
    assert code == 0 and not (tmp_path / "empty").exists()


def test_serve_is_listed_in_the_help(capsys):
    code, out, _ = _cli(capsys, "--help")
    assert code == 0
    assert "serve" in out and "web browser" in out


@pytest.mark.browser
def test_browser_versions_can_be_compared_and_one_brought_back(
    browser: Any,
    running: Running,
    projects: Path,
    remembered_rebuild: None,
) -> None:
    """Four versions (the conversion and three passes of an AI design): the strip lists them
    newest first, a click shows one on the right, "Use this version" brings it back after a
    confirmation, and the choosers put any two AI versions side by side. The 3D views stay
    on the first screen, and the strip works at phone width."""
    from bricksnap import versions
    from bricksnap.catalog import load_catalog
    from bricksnap.design import apply_ops

    project = Project(projects / "pawn")
    versions.record(project, "converted", "Converted from pawn.stl")
    passes = ("Pass 1: the main shapes", "Pass 2: colours", "Pass 3: surface and details")
    for i, (colour, label) in enumerate(zip((4, 1, 14), passes, strict=True)):
        design = project.load_design()
        box = {"type": "box", "min": [0, 0, 0], "max": [9, 9, 2 + 3 * i]}
        paint = [{"op": "paint", "shape": box, "color": colour}]
        assert all(r.applied for r in apply_ops(design, paint, load_catalog()))
        project.save_design(design)
        project.meta["brief"] = {**BRIEF, "object": f"A chess pawn, pass {i + 1}."}
        project.save_meta()
        pipeline.rebuild(project)
        render_card(project)
        versions.record(project, "pass", label)
    tab = Tab(browser, running.url, width=1400, height=900).open("p/pawn")
    try:
        page = tab.page
        page.wait_for_function("window.__bricksnap && window.__bricksnap.ready === true")
        page.wait_for_selector("#versions .vcard")
        cards = page.locator("#versions .vcard")
        assert [c.get_attribute("data-n") for c in cards.all()] == ["4", "3", "2", "1"]
        assert tab.text("#versions .vcard[data-n='4'] .vlabel") == passes[2]
        assert page.locator("#versions .vcard[data-n='4'] .vnow").is_visible()
        assert page.locator("#useVersion").count() == 0  # the one on the right is in use
        page.wait_for_function(
            "() => [...document.querySelectorAll('#versions img')]"
            ".every(i => i.complete && i.naturalWidth > 0)"
        )
        # the page stays compact: the 3D views begin on the first screen
        view = page.evaluate("() => document.querySelector('#view').getBoundingClientRect().top")
        assert view <= 900 - 280, view
        assert tab.text("#pickRight option:checked") == f"4 · {passes[2]} (in use)"

        # a click shows a version on the right, with its own brief
        cards.nth(2).click()
        page.wait_for_function("window.__bricksnap.choice.right === 2")
        assert tab.text("#designedTag .pane-title") == passes[0]
        assert "A chess pawn, pass 1." in tab.text("#brief")
        assert cards.nth(2).get_attribute("aria-pressed") == "true"
        said: list[str] = []
        page.once("dialog", lambda d: (said.append(d.message), d.accept()))
        page.locator("#useVersion").click()
        page.wait_for_selector("#appJob .job.done")
        assert "stays in the list" in said[0] and passes[0] in said[0]
        assert "Going back to version 2: Pass 1: the main shapes" in tab.text("#appJob")
        page.wait_for_selector("#versions .vcard[data-n='2'] .vnow")
        assert running.get_json("/api/p/pawn")["current_version"] == 2
        page.wait_for_function("document.querySelector('#designedTag .pane-what')"
                               ".textContent.includes('(in use)')")  # fmt: skip
        assert page.locator("#useVersion").count() == 0
        page.screenshot(path=str(ARTIFACTS / "versions-project-page.png"))

        # any two versions side by side: two AI passes
        page.select_option("#pickLeft", "3")
        page.select_option("#pickRight", "4")
        page.wait_for_function(
            "() => { const c = window.__bricksnap.choice; return c.left === 3 && c.right === 4 }"
        )
        assert tab.text("#roughTag .pane-title") == passes[1]
        assert tab.text("#designedTag .pane-title") == passes[2]
        assert tab.text("#stepsFor") == "The steps are for version 4."
        state = page.evaluate("() => window.__bricksnap.inspect().compare")
        assert state == {"active": True, "show": "both"}
        page.locator('#compare button[data-show="rough"]').click()
        assert page.evaluate("() => window.__bricksnap.inspect().views.designed.shown") is False
        page.locator('#compare button[data-show="both"]').click()
        page.wait_for_selector("#versions .vcard[data-n='4'][aria-pressed='true']")
        assert page.locator("#useVersion").is_visible()
        page.evaluate("() => new Promise(r => requestAnimationFrame(() => setTimeout(r, 50)))")
        page.screenshot(path=str(ARTIFACTS / "versions-two-ai-side-by-side.png"), full_page=True)
        tab.assert_clean()
    finally:
        tab.close()
    phone = Tab(browser, running.url, width=390, height=844).open("p/pawn")
    try:
        phone.page.wait_for_selector("#versions .vcard")
        # the choosers are drawn a moment after the strip: wait for them rather than assume
        phone.page.wait_for_function(
            "() => [...document.querySelectorAll('#choose .pick-side')].map(e => e.textContent)"
            ".join() === 'Top,Bottom'"
        )
        phone.no_sideways_scroll()
        phone.page.screenshot(path=str(ARTIFACTS / "versions-phone.png"), full_page=True)
        phone.assert_clean()
    finally:
        phone.close()
