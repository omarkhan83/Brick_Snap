"""Tests for the 3D viewer page (viewer/) and its local server (bricksnap/viewserver.py).

Server tests talk HTTP to a real server on a free port. Browser tests (marked ``browser``)
open the page in headless Chromium with Playwright, check what it shows and save
screenshots to tests/artifacts/viewer-*.png.
"""

from __future__ import annotations

import contextlib
import http.client
import io
import json
import re
import shutil
import socket
import struct
import threading
import time
from collections.abc import Generator, Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import numpy as np
import pytest
from PIL import Image

from bricksnap import viewserver
from bricksnap.catalog import Catalog
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Placement, Report
from bricksnap.viewserver import make_server, resolve_route, safe_join, serve

REPO = Path(__file__).resolve().parent.parent
VIEWER = REPO / "viewer"
CATALOG_DIR = REPO / "bricksnap" / "catalog"
ARTIFACTS = REPO / "tests" / "artifacts"
TRADEMARK = (
    "LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse "
    "this project."
)

RED, BLUE, YELLOW, GREEN = 4, 1, 14, 2


# ---- helpers ------------------------------------------------------------------------------


class Running:
    """A viewer server running in a background thread."""

    def __init__(self, project_path: Path) -> None:
        self.server = make_server(project_path, port=0)
        self.port = int(self.server.server_address[1])
        self.url = f"http://127.0.0.1:{self.port}/"
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        self.thread.start()

    def request(
        self, path: str, method: str = "GET", host: str | None = None
    ) -> tuple[int, dict[str, str], bytes]:
        """Send ``path`` exactly as written (no client-side normalising).

        ``host`` replaces the Host header that http.client would send.
        """
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=host is not None, skip_accept_encoding=True)
            if host is not None:
                conn.putheader("Host", host)
            conn.endheaders()
            res = conn.getresponse()
            body = res.read()
            return res.status, {k.lower(): v for k, v in res.getheaders()}, body
        finally:
            conn.close()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


def layered_build(layers: int = 4, report: Report | None = None) -> Build:
    """Layers of three 2x4 bricks, crossing direction each layer; red and blue alternate.

    Even layers lie along x (rot 0 or 180), odd layers along y (rot 90 or 270). Each layer is
    one building step, and a yellow 2x2 brick on top is the last step.
    """
    parts: list[Placement] = []
    for layer in range(layers):
        z = layer * 3
        colour = RED if layer % 2 == 0 else BLUE
        for i in range(3):
            if layer % 2 == 0:
                parts.append(
                    Placement("3001", colour, 0, i * 2, z, 0 if i != 1 else 180, layer + 1)
                )
            else:
                parts.append(
                    Placement("3001", colour, i * 2, 0, z, 90 if i != 1 else 270, layer + 1)
                )
    parts.append(Placement("3003", YELLOW, 1, 1, layers * 3, 0, layers + 1))
    if report is None:
        report = Report(
            ok=True,
            part_count=len(parts),
            text=f"Everything checks out: {len(parts)} parts in one piece.\nIt stands up.",
        )
    return Build(shape=(6, 6, layers * 3 + 3), parts=parts, report=report)


@pytest.fixture
def project(tmp_path: Path, pawn_path: Path) -> Project:
    """A project folder with a seed and a hand-made build; a secret file sits next to it."""
    proj = Project.create(tmp_path / "proj", pawn_path, studs=8, name="Pawn <b>bold</b> & co")
    proj.save_build(layered_build())
    renders = proj.renders_dir
    Image.new("RGB", (4, 4), (255, 0, 0)).save(renders / "front.png")
    (renders / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', "utf-8")
    (renders / "notes.css").write_text("body{}", "utf-8")
    (renders / "notes.js").write_text("export {}", "utf-8")
    (renders / "page.html").write_text("<p>hi</p>", "utf-8")
    (renders / "blob.bin").write_bytes(b"\x00\x01")
    (tmp_path / "secret.txt").write_text("TOP SECRET", "utf-8")
    return proj


@pytest.fixture
def running(project: Project) -> Iterator[Running]:
    r = Running(project.path)
    yield r
    r.close()


# ---- server: routes and headers -----------------------------------------------------------


def test_server_binds_localhost_on_a_free_port(running: Running) -> None:
    host, port = running.server.server_address[:2]
    assert host == "127.0.0.1"
    assert port != 0


@pytest.mark.parametrize(
    ("path", "source", "ctype"),
    [
        ("/", VIEWER / "index.html", "text/html"),
        ("/index.html", VIEWER / "index.html", "text/html"),
        ("/viewer/index.html", VIEWER / "index.html", "text/html"),
        ("/viewer/viewer.js", VIEWER / "viewer.js", "text/javascript"),
        ("/viewer/style.css", VIEWER / "style.css", "text/css"),
        (
            "/viewer/vendor/three.module.js",
            VIEWER / "vendor" / "three.module.js",
            "text/javascript",
        ),
        (
            "/viewer/vendor/OrbitControls.js",
            VIEWER / "vendor" / "OrbitControls.js",
            "text/javascript",
        ),
        ("/catalog/parts.json", CATALOG_DIR / "parts.json", "application/json"),
        ("/catalog/colours.json", CATALOG_DIR / "colours.json", "application/json"),
    ],
)
def test_static_routes(running: Running, path: str, source: Path, ctype: str) -> None:
    status, headers, body = running.request(path)
    assert status == 200
    assert headers["content-type"].startswith(ctype)
    assert headers["cache-control"] == "no-store"
    assert body == source.read_bytes()
    assert int(headers["content-length"]) == len(body)


@pytest.mark.parametrize(
    ("name", "ctype"),
    [
        ("build.json", "application/json"),
        ("project.json", "application/json"),
        ("renders/front.png", "image/png"),
        ("renders/icon.svg", "image/svg+xml"),
        ("renders/notes.css", "text/css"),
        ("renders/notes.js", "text/javascript"),
        ("renders/page.html", "text/html"),
        ("renders/blob.bin", "application/octet-stream"),
    ],
)
def test_project_files(running: Running, project: Project, name: str, ctype: str) -> None:
    status, headers, body = running.request("/project/" + name)
    assert status == 200
    assert headers["content-type"].startswith(ctype)
    assert headers["cache-control"] == "no-store"
    assert body == (project.path / name).read_bytes()


def test_build_json_is_served_fresh_after_a_rebuild(running: Running, project: Project) -> None:
    _, _, first = running.request("/project/build.json")
    project.save_build(layered_build(layers=2))
    _, _, second = running.request("/project/build.json")
    assert first != second
    assert len(json.loads(second)["parts"]) == 7


def test_query_string_is_ignored(running: Running) -> None:
    status, _, body = running.request("/project/build.json?t=12345#frag")
    assert status == 200
    assert json.loads(body)["shape"] == [6, 6, 15]


def test_percent_encoded_names_are_decoded(running: Running, project: Project) -> None:
    (project.path / "a b.json").write_text("{}", "utf-8")
    status, _, _ = running.request("/project/a%20b.json")
    assert status == 200


def test_head_has_headers_but_no_body(running: Running) -> None:
    status, headers, body = running.request("/project/build.json", method="HEAD")
    assert status == 200
    assert body == b""
    assert headers["cache-control"] == "no-store"
    assert int(headers["content-length"]) > 0


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
def test_other_methods_are_refused(running: Running, project: Project, method: str) -> None:
    before = project.build_path.read_bytes()
    status, headers, _ = running.request("/project/build.json", method=method)
    assert status == 405
    assert "GET" in headers["allow"]
    assert project.build_path.read_bytes() == before


@pytest.mark.parametrize(
    "path",
    [
        "/nothing",
        "/project/",
        "/project",
        "/project/missing.json",
        "/project/renders",
        "/project/renders/",
        "/viewer/",
        "/viewer/missing.js",
        "/catalog/",
        "/catalog/__init__.py",
        "/catalog/SOURCES.md",
        "/catalog/parts.json/",
        "/bricksnap/viewserver.py",
        "/pyproject.toml",
    ],
)
def test_unknown_paths_are_404(running: Running, path: str) -> None:
    status, headers, body = running.request(path)
    assert status == 404
    assert headers["cache-control"] == "no-store"
    assert b"Traceback" not in body


TRAVERSALS = [
    "/project/../secret.txt",
    "/project/../../secret.txt",
    "/project/renders/../../secret.txt",
    "/project/%2e%2e/secret.txt",
    "/project/%2E%2E/secret.txt",
    "/project/%2e%2e%2fsecret.txt",
    "/project/..%2fsecret.txt",
    "/project/%2e%2e%2f%2e%2e%2fsecret.txt",
    "/project/..%5csecret.txt",
    "/project/%2e%2e%5csecret.txt",
    "/project/..\\secret.txt",
    "/project/renders\\..\\..\\secret.txt",
    "/project/%252e%252e/secret.txt",
    "/project//etc/passwd",
    "/project/%2fetc%2fpasswd",
    "/project/C:/Windows/win.ini",
    "/project/C:%5cWindows%5cwin.ini",
    "/project/%00build.json",
    "/project/build.json%00",
    "/project/%ff%fe",
    "/project/./build.json",
    "/viewer/../bricksnap/viewserver.py",
    "/viewer/%2e%2e/pyproject.toml",
    "/viewer/..%2fpyproject.toml",
    "/viewer/vendor/../../pyproject.toml",
    "/catalog/../types.py",
    "/catalog/%2e%2e/types.py",
    "/catalog/..%2fcatalog%2fparts.json",
    "/../pyproject.toml",
    "/%2e%2e/pyproject.toml",
]


@pytest.mark.parametrize("path", TRAVERSALS)
def test_path_traversal_is_404(running: Running, path: str) -> None:
    status, _, body = running.request(path)
    assert status == 404
    assert b"TOP SECRET" not in body
    assert b"root:" not in body


def test_absolute_path_to_a_real_file_is_404(running: Running, project: Project) -> None:
    secret = (project.path.parent / "secret.txt").resolve()
    for path in (
        f"/project/{secret}",
        f"/project/{secret.as_posix().lstrip('/')}",
        f"/project{secret}",
    ):
        status, _, body = running.request(path)
        assert status == 404, path
        assert b"TOP SECRET" not in body


@pytest.mark.parametrize(
    "host",
    [
        "evil.example.com",
        "evil.example.com:{port}",
        "127.0.0.1.evil.example.com:{port}",
        "localhost.evil.example.com",
        "127.0.0.2:{port}",
        "",
    ],
)
def test_requests_for_another_host_name_are_refused(running: Running, host: str) -> None:
    """A web page in another tab could point its own host name at 127.0.0.1 (DNS
    rebinding) and read the project through the viewer. Only local names are answered."""
    status, headers, body = running.request(
        "/project/build.json", host=host.format(port=running.port)
    )
    assert status == 404
    assert headers["cache-control"] == "no-store"
    assert b"parts" not in body


@pytest.mark.parametrize(
    "host", ["127.0.0.1:{port}", "127.0.0.1", "localhost:{port}", "LocalHost", "[::1]:{port}"]
)
def test_requests_for_local_host_names_are_answered(running: Running, host: str) -> None:
    status, _, body = running.request("/project/build.json", host=host.format(port=running.port))
    assert status == 200
    assert json.loads(body)["shape"] == [6, 6, 15]


def test_request_without_a_host_header_is_refused(running: Running) -> None:
    with socket.create_connection(("127.0.0.1", running.port), timeout=10) as sock:
        sock.sendall(b"GET /project/build.json HTTP/1.0\r\n\r\n")
        reply = b""
        while chunk := sock.recv(65536):
            reply += chunk
    assert reply.startswith(b"HTTP/1.0 404")
    assert b'"parts"' not in reply


def test_closed_connections_do_not_print_tracebacks(
    running: Running, project: Project, capfd: pytest.CaptureFixture[str]
) -> None:
    """A tab closed while a file is being sent must not fill the terminal with a traceback."""
    (project.path / "big.json").write_bytes(b" " * 30_000_000)
    for _ in range(3):
        sock = socket.create_connection(("127.0.0.1", running.port), timeout=10)
        sock.sendall(b"GET /project/big.json HTTP/1.1\r\nHost: 127.0.0.1\r\n\r\n")
        sock.recv(1024)  # the server has started sending
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        sock.close()  # a reset, as when a browser tab is closed
    time.sleep(0.5)
    # the server still answers afterwards
    assert running.request("/project/build.json")[0] == 200
    err = capfd.readouterr().err
    assert "Traceback" not in err
    assert "Exception occurred" not in err


def test_connection_errors_are_ignored_but_real_errors_are_not(
    running: Running, capfd: pytest.CaptureFixture[str]
) -> None:
    for exc in (BrokenPipeError(32, "Broken pipe"), ConnectionResetError(104, "reset")):
        try:
            raise exc
        except OSError:
            running.server.handle_error(cast(Any, None), ("127.0.0.1", 1))
    assert capfd.readouterr().err == ""
    try:
        raise RuntimeError("a real bug")
    except RuntimeError:
        running.server.handle_error(cast(Any, None), ("127.0.0.1", 1))
    assert "a real bug" in capfd.readouterr().err


def test_symlink_out_of_the_project_is_404(running: Running, project: Project) -> None:
    link = project.path / "sneaky.txt"
    link.symlink_to(project.path.parent / "secret.txt")
    (project.path / "sneaky_dir").symlink_to(project.path.parent, target_is_directory=True)
    assert running.request("/project/sneaky.txt")[0] == 404
    assert running.request("/project/sneaky_dir/secret.txt")[0] == 404


def test_safe_join_unit(tmp_path: Path) -> None:
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "f.json").write_text("{}", "utf-8")
    (tmp_path / "outside.txt").write_text("x", "utf-8")
    assert safe_join(root, "sub/f.json") == (root / "sub" / "f.json").resolve()
    for bad in [
        "",
        "sub",
        "../outside.txt",
        "sub/../../outside.txt",
        "/etc/passwd",
        "sub\\f.json",
        "sub//f.json",
        "./sub/f.json",
        "C:/x",
        "sub/f.json\x00",
    ]:
        assert safe_join(root, bad) is None, bad


def test_resolve_route_unit(project: Project) -> None:
    assert resolve_route("/", project.path) == (VIEWER / "index.html").resolve()
    assert resolve_route("/project/build.json?x=1", project.path) == project.build_path.resolve()
    assert (
        resolve_route("/catalog/colours.json", project.path)
        == (CATALOG_DIR / "colours.json").resolve()
    )
    assert resolve_route("/catalog/../catalog/parts.json", project.path) is None
    assert resolve_route("/project/%2e%2e/secret.txt", project.path) is None


def test_content_types_unit() -> None:
    ct = viewserver.content_type
    assert ct(Path("a.html")).startswith("text/html")
    assert ct(Path("a.JS")).startswith("text/javascript")
    assert ct(Path("a.css")).startswith("text/css")
    assert ct(Path("a.json")).startswith("application/json")
    assert ct(Path("a.png")) == "image/png"
    assert ct(Path("a.svg")) == "image/svg+xml"
    assert ct(Path("a.weird")) == "application/octet-stream"


# ---- server: errors and serve() -----------------------------------------------------------


def test_missing_project_folder_is_a_plain_error(tmp_path: Path) -> None:
    with pytest.raises(ProjectError, match="Cannot find the project folder"):
        make_server(tmp_path / "nope", port=0)


def test_port_in_use_is_a_plain_error(running: Running, project: Project) -> None:
    with pytest.raises(ProjectError, match="already in use"):
        make_server(project.path, port=running.port)


@pytest.mark.parametrize("port", [99999, 65536, -1, "abc", "", None, 1.5, "80.5", True])
def test_bad_port_is_a_plain_error(project: Project, port: Any) -> None:
    with pytest.raises(ProjectError, match="whole number from 0 to 65535"):
        make_server(project.path, port=port)


def test_port_given_as_text_is_accepted(project: Project) -> None:
    server = make_server(project.path, port=cast(Any, "0"))
    try:
        assert server.server_address[1] != 0
    finally:
        server.server_close()


def test_serve_prints_address_and_stops_on_ctrl_c(
    project: Project, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    opened: list[str] = []

    class FakeTimer:
        def __init__(self, delay: float, fn: Any, args: tuple[str, ...] = ()) -> None:
            self.fn, self.args = fn, args

        def start(self) -> None:
            self.fn(*self.args)

    def interrupted(self: Any, poll_interval: float = 0.5) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(viewserver.threading, "Timer", FakeTimer)
    monkeypatch.setattr(viewserver.webbrowser, "open", lambda url: opened.append(url))
    monkeypatch.setattr(viewserver.ThreadingHTTPServer, "serve_forever", interrupted)
    serve(project.path, port=0, open_browser=True)
    out = capsys.readouterr().out
    assert re.search(r"http://127\.0\.0\.1:\d+/", out)
    assert "Ctrl+C" in out
    assert "stopped" in out
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:")

    opened.clear()
    serve(project.path, port=0, open_browser=False)
    assert opened == []


# ---- the page's files ---------------------------------------------------------------------


def test_page_has_trademark_footer_and_no_external_urls() -> None:
    html = (VIEWER / "index.html").read_text("utf-8")
    assert TRADEMARK in html
    for name in ("index.html", "viewer.js", "style.css"):
        text = (VIEWER / name).read_text("utf-8")
        # the only URL allowed is the SVG namespace, which is never fetched
        urls = re.findall(r"https?://[^\s\"')]+", text)
        assert all(u.startswith("http://www.w3.org/") for u in urls), (name, urls)
        assert "@import" not in text and "fonts.googleapis" not in text


def test_page_never_puts_file_text_into_html() -> None:
    js = (VIEWER / "viewer.js").read_text("utf-8")
    for sink in (r"\.innerHTML\b", r"\.outerHTML\b", r"insertAdjacentHTML\(", r"document\.write"):
        assert not re.search(sink, js), sink


def test_vendored_three_is_documented() -> None:
    vendor = VIEWER / "vendor"
    readme = (vendor / "README.md").read_text("utf-8")
    match = re.search(r"Version: \*\*0\.(\d+)\.(\d+)\*\*", readme)
    assert match, "the README must state the three.js version"
    assert "MIT" in readme
    assert "registry.npmjs.org/three/-/three-0." in readme
    core = (vendor / "three.core.js").read_text("utf-8")
    assert f"const REVISION = '{match.group(1)}';" in core
    assert "MIT" in (vendor / "LICENSE").read_text("utf-8")
    orbit = (vendor / "OrbitControls.js").read_text("utf-8")
    assert "from 'three'" in orbit
    assert "./three.core.js" in (vendor / "three.module.js").read_text("utf-8")


# ---- browser tests ------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser() -> Iterator[Any]:
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except sync_api.Error as e:  # the browser itself is a separate one-time download
            pytest.skip(
                "Headless Chromium is not installed. Run 'uv run playwright install chromium' "
                f"once, then run the tests again. ({str(e).splitlines()[0]})"
            )
        yield b
        b.close()


class Page:
    """A browser tab on the viewer that records console errors and odd requests."""

    def __init__(self, browser: Any, url: str, width: int = 1100, height: int = 820) -> None:
        self.url = url
        self.context = browser.new_context(viewport={"width": width, "height": height})
        self.page = self.context.new_page()
        self.errors: list[str] = []
        self.failed: list[str] = []
        self.external: list[str] = []
        self.page.on("console", self._console)
        self.page.on("pageerror", lambda e: self.errors.append(f"pageerror: {e}"))
        self.page.on("requestfailed", lambda r: self.failed.append(r.url))
        self.page.on("request", self._request)
        self.page.on("response", self._response)

    def _console(self, msg: Any) -> None:
        if msg.type == "error":
            self.errors.append(msg.text)

    def _request(self, req: Any) -> None:
        if not req.url.startswith(self.url) and not req.url.startswith("data:"):
            self.external.append(req.url)

    def _response(self, res: Any) -> None:
        if res.status >= 400:
            self.failed.append(f"{res.status} {res.url}")

    def open(self) -> Page:
        self.page.goto(self.url)
        self.page.wait_for_function(
            "window.__bricksnap && window.__bricksnap.ready === true", timeout=20000
        )
        return self

    def state(self) -> dict[str, Any]:
        return self.page.evaluate(
            "() => { const s = window.__bricksnap; return {ready: s.ready, partCount: s.partCount,"
            " visibleCount: s.visibleCount, step: s.step, maxStep: s.maxStep,"
            " showingAll: s.showingAll, highlightCount: s.highlightCount,"
            " buildVersion: s.buildVersion}; }"
        )

    def settle(self) -> None:
        """Wait two animation frames so the canvas shows the latest change."""
        self.page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )

    def view_pixels(self, name: str | None = None) -> np.ndarray:
        self.settle()
        png = self.page.locator("#view").screenshot()
        if name:
            ARTIFACTS.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(ARTIFACTS / f"viewer-{name}.png"))
            (ARTIFACTS / f"viewer-{name}-view.png").write_bytes(png)
        return np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(int)

    def inspect(self, detail: bool = False) -> dict[str, Any]:
        """What the page draws now, in world millimetres (see state.inspect in viewer.js);
        ``detail`` adds the slower measurements of edge lines and slopes."""
        return self.page.evaluate("(o) => window.__bricksnap.inspect(o)", {"detail": detail})

    def poll_now(self) -> None:
        """Make the page look at build.json now rather than at its next 2-second poll."""
        self.page.evaluate("() => window.__bricksnap.pollNow()")

    def error(self) -> str | None:
        return self.page.evaluate("() => window.__bricksnap.error")

    def text(self, selector: str) -> str:
        return self.page.locator(selector).text_content() or ""

    def assert_clean(self) -> None:
        assert self.errors == [], self.errors
        assert self.failed == [], self.failed
        assert self.external == [], self.external

    def close(self) -> None:
        self.context.close()


def colour_rgb(catalog: Catalog, code: int) -> np.ndarray:
    return np.array(catalog.colours[code].rgb)


def near(pixels: np.ndarray, rgb: np.ndarray, tol: float = 45.0) -> int:
    """Number of pixels within ``tol`` (RGB distance) of a colour."""
    return int((np.linalg.norm(pixels - rgb, axis=2) < tol).sum())


@contextlib.contextmanager
def viewing(
    browser: Any,
    folder: Path,
    pawn_path: Path,
    build: Build | str | None,
    width: int = 1100,
    height: int = 820,
    init_script: str | None = None,
) -> Generator[tuple[Page, Project]]:
    """A new project holding ``build`` (a Build, raw build.json text, or None), served and
    open in a browser tab."""
    proj = Project.create(folder, pawn_path, studs=4, name="Probe")
    if isinstance(build, Build):
        proj.save_build(build)
    elif isinstance(build, str):
        proj.build_path.write_text(build, "utf-8")
    r = Running(proj.path)
    p = Page(browser, r.url, width=width, height=height)
    if init_script:
        p.page.add_init_script(init_script)
    try:
        yield p.open(), proj
    finally:
        p.close()
        r.close()


CELL_MM = np.array([8.0, 8.0, 3.2])


def _box(entry: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    return np.array(entry["min"]), np.array(entry["max"])


def assert_bodies_match(catalog: Catalog, drawn: list[dict[str, Any]], parts: list[Placement]):
    """Each drawn box sits exactly on its part's cells (Catalog.footprint), in the part's
    colour, at most 1 mm smaller than the cells (the gap that keeps parts apart)."""
    expected = []
    for p in parts:
        lo = np.array([p.x, p.y, p.z]) * CELL_MM
        full = np.array(catalog.footprint(p)) * CELL_MM
        rgb = "#{:02x}{:02x}{:02x}".format(*catalog.colours[p.color].rgb)
        expected.append((tuple(np.round(lo + full / 2, 2)), tuple(np.round(full, 2)), rgb, p.step))
    got = []
    for b in drawn:
        lo, hi = _box(b)
        size = hi - lo
        got.append((tuple(np.round((lo + hi) / 2, 2)), size, b["colour"], b["step"]))
    assert len(got) == len(expected)
    expected.sort(key=lambda e: (e[0], e[3]))
    got.sort(key=lambda e: (e[0], e[3]))
    for (centre, full, rgb, step), (gcentre, gsize, grgb, gstep) in zip(expected, got, strict=True):
        assert gcentre == centre, (centre, gcentre)
        assert (gsize <= np.array(full) + 1e-3).all() and (gsize >= np.array(full) - 1.0).all(), (
            centre,
            full,
            gsize,
        )
        assert (grgb, gstep) == (rgb, step), centre


def assert_studs_match(catalog: Catalog, drawn: list[dict[str, Any]], parts: list[Placement]):
    """One stud on each cell Catalog.stud_cells names, standing on the part's top face:
    4.8 mm across and about 1.7 mm tall."""
    expected = []
    for p in parts:
        top = p.z + catalog.footprint(p)[2]
        for cx, cy in catalog.stud_cells(p):
            expected.append((round((cx + 0.5) * 8, 2), round((cy + 0.5) * 8, 2), top))
    got = []
    for st in drawn:
        lo, hi = _box(st)
        size = hi - lo
        assert abs(size[0] - 4.8) < 0.05 and abs(size[1] - 4.8) < 0.05, size
        assert 1.5 <= size[2] <= 1.9, size
        level = round(lo[2] / 3.2)
        assert level * 3.2 - 0.5 <= lo[2] <= level * 3.2 + 0.05, lo  # on the top face
        got.append((round((lo[0] + hi[0]) / 2, 2), round((lo[1] + hi[1]) / 2, 2), level))
    assert sorted(got) == sorted(expected)


def view_masks(px: np.ndarray, catalog: Catalog, code: int, tol: float = 45.0) -> np.ndarray:
    return np.linalg.norm(px - colour_rgb(catalog, code), axis=2) < tol


@pytest.fixture
def page(browser: Any, running: Running) -> Iterator[Page]:
    p = Page(browser, running.url).open()
    yield p
    p.close()


@pytest.mark.browser
def test_page_draws_the_build(page: Page, project: Project, catalog: Catalog) -> None:
    s = page.state()
    assert s["ready"] is True
    assert s["partCount"] == 13
    assert s["visibleCount"] == 13
    assert s["maxStep"] == 5
    assert s["showingAll"] is True

    pg = page.page
    # text from files is shown literally, never interpreted as HTML
    assert pg.locator("#name").text_content() == "Pawn <b>bold</b> & co"
    assert pg.locator("#name b").count() == 0
    assert pg.locator("#count").text_content() == "13 parts"
    report = pg.locator("#report")
    assert report.text_content() == "Everything checks out: 13 parts in one piece."
    assert "ok" in (report.get_attribute("class") or "")
    green = pg.evaluate("getComputedStyle(document.getElementById('report')).backgroundColor")
    assert green == "rgb(0, 166, 80)"
    assert pg.locator("footer").text_content().strip() == TRADEMARK

    px = page.view_pixels("all")
    # not blank: plenty of distinct colours
    assert len(np.unique(px.reshape(-1, 3), axis=0)) > 200
    assert near(px, colour_rgb(catalog, RED)) > 2000
    assert near(px, colour_rgb(catalog, BLUE)) > 2000
    assert near(px, colour_rgb(catalog, YELLOW)) > 300
    page.assert_clean()


@pytest.mark.browser
def test_step_slider_and_buttons(page: Page, catalog: Catalog) -> None:
    pg = page.page
    pg.locator("#step").fill("1")
    s = page.state()
    assert (s["step"], s["visibleCount"], s["highlightCount"], s["showingAll"]) == (1, 3, 3, False)
    assert pg.locator("#stepLabel").text_content() == "Step 1 of 5 · 3 new parts"
    assert pg.locator("#prev").is_disabled()
    px = page.view_pixels("step1")
    assert near(px, colour_rgb(catalog, RED)) > 1000
    assert near(px, colour_rgb(catalog, BLUE)) < 50  # the blue layers are not placed yet

    pg.locator("#next").click()
    s = page.state()
    assert (s["step"], s["visibleCount"], s["highlightCount"]) == (2, 6, 3)
    page.view_pixels("step2")

    pg.locator("#step").fill("4")
    assert page.state()["visibleCount"] == 12
    pg.keyboard.press("ArrowRight")
    s = page.state()
    assert (s["step"], s["visibleCount"], s["highlightCount"]) == (5, 13, 1)
    pg.locator("#next").click()  # past the last step shows everything
    assert page.state()["showingAll"] is True
    assert pg.locator("#next").is_disabled()

    pg.locator("#prev").click()  # from "all", back goes to the last step
    s = page.state()
    assert (s["step"], s["showingAll"]) == (5, False)
    pg.keyboard.press("ArrowLeft")
    assert page.state()["step"] == 4

    pg.locator("#all").click()
    s = page.state()
    assert (s["visibleCount"], s["highlightCount"], s["showingAll"]) == (13, 0, True)
    assert pg.locator("#all").get_attribute("aria-pressed") == "true"
    page.assert_clean()


@pytest.mark.browser
def test_page_follows_a_rebuild(page: Page, project: Project) -> None:
    pg = page.page
    version = page.state()["buildVersion"]
    pg.locator("#step").fill("2")
    bad = Report(ok=False, part_count=19, text="2 parts float in the air.\nFix them.")
    project.save_build(layered_build(layers=6, report=bad))
    # the page looks every 2 seconds, so the new build shows within about 3
    pg.wait_for_function(f"window.__bricksnap.buildVersion > {version}", timeout=3000)
    s = page.state()
    assert s["partCount"] == 19
    assert s["maxStep"] == 7
    assert (s["step"], s["visibleCount"]) == (2, 6)  # stays on the step being looked at
    report = pg.locator("#report")
    assert report.text_content() == "2 parts float in the air."
    assert "bad" in (report.get_attribute("class") or "")
    red = pg.evaluate("getComputedStyle(document.getElementById('report')).backgroundColor")
    assert red == "rgb(208, 16, 18)"
    assert pg.locator("#count").text_content() == "19 parts"
    pg.locator("#all").click()
    page.view_pixels("rebuilt")

    # an unchanged file does not redraw, though the page keeps looking every 2 seconds
    version = page.state()["buildVersion"]
    since = pg.evaluate("performance.now()")
    time.sleep(4.2)
    assert page.state()["buildVersion"] == version
    polls = pg.evaluate(
        "(since) => [since, ...performance.getEntriesByType('resource')"
        ".filter(e => e.name.includes('/project/build.json') && e.startTime > since)"
        ".map(e => e.startTime), performance.now()]",
        since,
    )
    assert len(polls) >= 4, polls  # at least two polls in 4.2 s
    assert max(b - a for a, b in zip(polls, polls[1:], strict=False)) < 2600, polls
    page.assert_clean()


@pytest.mark.browser
def test_studs_and_footprints_match_the_catalogue(page: Page, catalog: Catalog) -> None:
    cases = [(part.id, rot, 3, 5) for part in catalog.parts.values() for rot in (0, 90, 180, 270)]
    got = page.page.evaluate(
        "(cases) => cases.map(([id, rot, x, y]) => [window.__bricksnap.geometry.footprint(id, rot),"
        " window.__bricksnap.geometry.studCells(id, rot, x, y)])",
        cases,
    )
    for (pid, rot, x, y), (fp, studs) in zip(cases, got, strict=True):
        p = Placement(pid, 15, x, y, 0, rot)
        assert tuple(fp) == catalog.footprint(p), (pid, rot)
        assert [tuple(c) for c in studs] == catalog.stud_cells(p), (pid, rot)


@pytest.mark.browser
def test_drawn_parts_match_the_catalogue_in_millimetres(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """Every catalogue part at every rotation, spread over a grid: the boxes and studs the
    page draws (after every transform, so a mirrored or squashed model would show) are
    where the Python catalogue says, and a step shows exactly the parts up to it."""
    parts = []
    for i, (part, rot) in enumerate(
        (part, rot) for part in catalog.parts.values() for rot in (0, 90, 180, 270)
    ):
        colour = sorted(part.colours)[i % len(part.colours)]
        parts.append(
            Placement(part.id, colour, (i % 14) * 10, (i // 14) * 10, i % 5, rot, 1 + i % 7)
        )
    build = Build(shape=(140, 150, 10), parts=parts)
    with viewing(browser, tmp_path / "geom", pawn_path, build) as (p, _):
        drawn = p.inspect()
        assert_bodies_match(catalog, drawn["bodies"], parts)
        assert_studs_match(catalog, drawn["studs"], parts)
        assert drawn["outlines"] == [] and drawn["highlightEdgeParts"] == 0

        p.page.locator("#step").fill("3")
        early = [q for q in parts if q.step <= 3]
        drawn = p.inspect()
        assert_bodies_match(catalog, drawn["bodies"], early)
        assert_studs_match(catalog, drawn["studs"], early)
        p.assert_clean()


@pytest.mark.browser
def test_plates_are_a_third_of_a_brick(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """A red 2x2 brick next to a blue stack of three 2x2 plates: same height on screen."""
    parts = [Placement("3003", RED, 0, 0, 0, 0, 1)]
    parts += [Placement("3022", BLUE, 3, 0, z, 0, 1) for z in range(3)]
    with viewing(browser, tmp_path / "plates", pawn_path, Build((5, 2, 3), parts)) as (p, _):
        drawn = p.inspect()
        heights = sorted(b["max"][2] - b["min"][2] for b in drawn["bodies"])
        # a plate is 3.2 mm and a brick 9.6 mm, less the small gap between parts
        assert [h == pytest.approx(3.2, abs=0.3) for h in heights] == [True] * 3 + [False]
        assert heights[3] == pytest.approx(9.6, abs=0.3)
        tops = sorted(b["max"][2] for b in drawn["bodies"])
        assert tops[-1] == pytest.approx(tops[-2], abs=0.1)  # the stack is as tall as the brick
        px = p.view_pixels("plates")
        red, blue = view_masks(px, catalog, RED), view_masks(px, catalog, BLUE)
        ry, by = np.nonzero(red)[0], np.nonzero(blue)[0]
        assert len(ry) > 500 and len(by) > 500
        ratio = (by.max() - by.min()) / (ry.max() - ry.min())
        # the blue stack is nearer the camera so looks a little taller; a plate drawn as tall
        # as a brick would make it about three times taller
        assert 0.8 < ratio < 1.4, ratio
        p.assert_clean()


@pytest.mark.browser
def test_model_is_not_mirrored(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """Seen from the front: x = 0 is on the left, larger x to the right, larger y further
    back (higher up the screen)."""
    parts = [
        Placement("3003", RED, 0, 0, 0, 0, 1),
        Placement("3003", BLUE, 12, 0, 0, 0, 1),
        Placement("3003", YELLOW, 6, 12, 0, 0, 1),
    ]
    with viewing(browser, tmp_path / "mirror", pawn_path, Build((14, 14, 3), parts)) as (p, _):
        px = p.view_pixels("mirror")
        cols = {}
        rows = {}
        for code in (RED, BLUE, YELLOW):
            ys, xs = np.nonzero(view_masks(px, catalog, code))
            assert len(xs) > 300, code
            cols[code], rows[code] = xs.mean(), ys.mean()
        assert cols[RED] < cols[YELLOW] < cols[BLUE]
        assert rows[YELLOW] < rows[RED] and rows[YELLOW] < rows[BLUE]
        p.assert_clean()


HIGHLIGHT_RGB = np.array([0xFF, 0x3D, 0x7F])


@pytest.mark.browser
def test_current_step_is_highlighted(page: Page, catalog: Catalog) -> None:
    page.page.locator("#step").fill("2")
    drawn = page.inspect()
    assert drawn["outlineColour"] == "#ff3d7f"
    assert drawn["highlightEdgeParts"] == 3
    step2 = [b for b in drawn["bodies"] if b["step"] == 2]
    assert len(step2) == 3 and len(drawn["outlines"]) == 3
    for body in step2:  # each new part has an outline just around it
        lo, hi = _box(body)
        assert any(
            ((_box(o)[0] < lo - 0.2) & (_box(o)[0] > lo - 1.5)).all()
            and ((_box(o)[1] > hi + 0.2) & (_box(o)[1] < hi + 1.5)).all()
            for o in drawn["outlines"]
        ), body
    px = page.view_pixels("highlight")
    assert near(px, HIGHLIGHT_RGB, 30) > 300

    page.page.locator("#all").click()
    drawn = page.inspect()
    assert drawn["outlines"] == [] and drawn["highlightEdgeParts"] == 0
    assert near(page.view_pixels(), HIGHLIGHT_RGB, 30) < 20
    page.assert_clean()


@pytest.mark.browser
def test_highlight_is_the_part_s_own_shape(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """The outline round a new round part is round, and round a new slope it is a wedge
    running down the same way; its dark and highlight edge lines are the part's own."""
    parts = [Placement("3003", 15, x, 0, 0, 0, 1) for x in (0, 2, 4)]
    parts += [
        Placement("6143", RED, 0, 0, 3, 0, 2),
        Placement("3039", BLUE, 2, 0, 3, 90, 2),
        Placement("3003", YELLOW, 4, 0, 3, 0, 2),
    ]
    with viewing(browser, tmp_path / "outl", pawn_path, Build((6, 2, 6), parts)) as (p, _):
        p.page.locator("#step").fill("2")
        drawn = p.inspect(detail=True)
        new = [b for b in drawn["bodies"] if b["step"] == 2]
        assert len(new) == 3 and len(drawn["outlines"]) == 3
        assert drawn["highlightEdgeParts"] == 3
        for body in new:
            lo, hi = _box(body)
            centre = (lo + hi) / 2
            outline = min(
                drawn["outlines"],
                key=lambda o: np.abs((_box(o)[0] + _box(o)[1]) / 2 - centre).sum(),
            )
            # the outline is the same shape, grown by 0.7 mm on every side
            olo, ohi = _box(outline)
            assert np.allclose(olo, lo - 0.7, atol=0.05) and np.allclose(ohi, hi + 0.7, atol=0.05)
            assert outline["downhill"] == body["downhill"], body["part"]
            rim, orim = body["topRim"], outline["topRim"]
            assert orim["points"] == rim["points"], body["part"]
            if body["part"] == "3039":  # a wedge: its flat top grows with it, in proportion
                low = catalog.low_side(parts[4])
                assert low is not None and body["downhill"] == list(low)
                assert outline["downhill"] is not None
            else:  # a circle's radius grows by 0.7 mm, a square's corner by 0.7 x 1.41
                grow = 0.7 if body["shape"] == "cylinder" else 0.7 * np.sqrt(2)
                assert orim["diagonal"] == pytest.approx(rim["diagonal"] + grow, abs=0.05)
            assert body["edgeGap"] < 0.01
        assert sorted(b["shape"] for b in new) == ["box", "cylinder", "wedge"]
        round_outline = [o for o in drawn["outlines"] if o["topRim"]["points"] >= 24]
        assert len(round_outline) == 1
        assert round_outline[0]["topRim"]["diagonal"] == pytest.approx(7.8 + 0.7, abs=0.05)
        assert near(p.view_pixels("highlight-shapes"), HIGHLIGHT_RGB, 30) > 300
        p.assert_clean()


def _view_dir(p: Page) -> np.ndarray:
    cam = p.inspect()["camera"]
    d = np.array(cam["position"]) - np.array(cam["target"])
    return d / np.linalg.norm(d)


def _drag(p: Page, dx: float, dy: float) -> None:
    box = p.page.locator("#view").bounding_box()
    assert box
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    p.page.mouse.move(cx, cy)
    p.page.mouse.down()
    p.page.mouse.move(cx + dx, cy + dy, steps=8)
    p.page.mouse.up()
    p.settle()


@pytest.mark.browser
def test_a_rebuild_keeps_the_angle_the_view_was_turned_to(
    browser: Any, tmp_path: Path, pawn_path: Path
) -> None:
    """Turn the view, then rebuild with one more part on top (the model's box grows by a
    tile): the camera still looks from the person's angle, closer or further as needed, and
    the whole model stays in view. Turning a phone keeps that angle too. A view nobody has
    turned is framed from the usual front-right angle."""
    base = [
        Placement("3001", RED, x, y, z, 0, 1)
        for x in (0, 4)
        for y in (0, 2, 4, 6)
        for z in (0, 3, 6)
    ]
    shape = (8, 8, 12)
    with viewing(browser, tmp_path / "keep", pawn_path, Build(shape, base)) as (p, proj):
        default = _view_dir(p)
        _drag(p, 220, 40)
        turned = _view_dir(p)
        assert np.degrees(np.arccos(np.clip(turned @ default, -1, 1))) > 20  # really turned

        for extra in ("3068b", "3022", "3001"):  # a tile; a plate (studs only); a brick
            _show(p, proj, Build(shape, [*base, Placement(extra, BLUE, 0, 0, 9, 0, 2)]))
            p.settle()
            now = _view_dir(p)
            assert np.degrees(np.arccos(np.clip(now @ turned, -1, 1))) < 0.5, extra
            _fits(p)

        p.page.set_viewport_size({"width": 375, "height": 740})
        p.page.wait_for_function(
            "() => { const r = document.getElementById('view')"
            ".getBoundingClientRect(); return r.width < r.height; }"
        )
        p.settle()
        assert np.degrees(np.arccos(np.clip(_view_dir(p) @ turned, -1, 1))) < 0.5
        _fits(p)
        p.assert_clean()

    with viewing(browser, tmp_path / "fresh", pawn_path, Build(shape, base)) as (p, proj):
        first = _view_dir(p)
        _show(p, proj, Build(shape, [*base, Placement("3001", BLUE, 0, 0, 9, 0, 2)]))
        p.settle()
        assert np.allclose(_view_dir(p), first, atol=1e-6)
        assert np.allclose(first, default, atol=1e-6)
        p.assert_clean()


def _fits(p: Page) -> dict[str, float]:
    p.settle()
    ndc = p.inspect()["ndc"]
    assert ndc["minX"] > -1 and ndc["maxX"] < 1, ndc
    assert ndc["minY"] > -1 and ndc["maxY"] < 1, ndc
    return ndc


def _no_bricks_at_the_sides(px: np.ndarray, catalog: Catalog, codes: tuple[int, ...]) -> None:
    edge = max(2, px.shape[1] // 100)
    for code in codes:
        mask = view_masks(px, catalog, code)
        assert mask.sum() > 300, code
        assert not mask[:, :edge].any() and not mask[:, -edge:].any(), code


WIDE_ROW = Build((48, 4, 3), [Placement("3001", RED, x, 0, 0, 0, 1) for x in range(0, 48, 4)])


@pytest.mark.browser
@pytest.mark.parametrize("which", ["layers", "wide row"])
def test_whole_model_fits_a_phone_screen(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog, which: str
) -> None:
    build = layered_build(4) if which == "layers" else WIDE_ROW
    codes = (RED, BLUE) if which == "layers" else (RED,)
    with viewing(browser, tmp_path / "fit", pawn_path, build, width=375, height=740) as (p, _):
        _fits(p)
        _no_bricks_at_the_sides(p.view_pixels(), catalog, codes)
        p.assert_clean()


@pytest.mark.browser
def test_turning_the_screen_frames_the_model_again(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    with viewing(browser, tmp_path / "turn", pawn_path, WIDE_ROW) as (p, _):
        _fits(p)
        p.page.set_viewport_size({"width": 375, "height": 740})
        p.page.wait_for_function(
            "() => { const r = document.getElementById('view')"
            ".getBoundingClientRect(); return r.width < r.height; }"
        )
        p.settle()
        _fits(p)
        _no_bricks_at_the_sides(p.view_pixels(), catalog, (RED,))
        p.page.set_viewport_size({"width": 1100, "height": 820})
        p.settle()
        _fits(p)
        p.assert_clean()


UNREADABLE = "build.json cannot be read"


@pytest.mark.browser
@pytest.mark.parametrize("text", ['{"shape": [4, 4, 3], "parts": [', "", "null", "[1, 2]"])
def test_unreadable_build_json_is_reported(
    browser: Any, tmp_path: Path, pawn_path: Path, text: str
) -> None:
    with viewing(browser, tmp_path / "broken", pawn_path, text) as (p, proj):
        p.page.wait_for_function(
            f"window.__bricksnap.error === {json.dumps(UNREADABLE)}", timeout=3000
        )
        notice = p.page.locator("#notice")
        assert notice.is_visible()
        assert "cannot be read" in p.text("#notice") and "bricksnap build" in p.text("#notice")
        assert p.text("#name") == "Probe"
        assert p.text("#report") == "Cannot read the build"
        assert p.text("#count") == "0 parts"
        assert p.inspect()["bodies"] == []

        # fixed by the next build
        proj.save_build(layered_build(1))
        p.poll_now()
        assert p.state()["partCount"] == 4
        assert not notice.is_visible()
        assert p.error() is None
        assert p.text("#count") == "4 parts"
        p.assert_clean()


@pytest.mark.browser
def test_build_that_turns_unreadable_keeps_the_old_one_and_says_so(
    page: Page, project: Project
) -> None:
    pg = page.page
    project.build_path.write_text('{"shape": [6, 6, 6], "parts": [{"part"', "utf-8")
    page.poll_now()
    assert page.error() is None  # once may just be a file caught half-written
    page.poll_now()
    assert page.error() == UNREADABLE
    assert "still the previous build" in page.text("#notice")
    assert len(page.inspect()["bodies"]) == 13  # what is shown matches the counts
    assert page.text("#count") == "13 parts"
    assert page.text("#report") == "Everything checks out: 13 parts in one piece."

    project.save_build(layered_build(2))
    page.poll_now()
    assert page.error() is None
    assert not pg.locator("#notice").is_visible()
    assert page.text("#count") == "7 parts"
    page.assert_clean()


@pytest.mark.browser
def test_entries_that_are_not_parts_are_left_out(
    browser: Any, tmp_path: Path, pawn_path: Path
) -> None:
    good = layered_build(3).to_json()
    first = dict(good, parts=good["parts"] + [None])
    with viewing(browser, tmp_path / "nulls", pawn_path, json.dumps(first)) as (p, proj):
        assert p.error() is None
        assert p.text("#count") == "10 parts"
        assert len(p.inspect()["bodies"]) == 10
        assert "1 entry in build.json is not a part" in p.text("#notice")

        # the same arriving while the page is open
        later = dict(
            good,
            parts=good["parts"][:9] + [None, 7, [1]],
            report={"ok": False, "part_count": 9, "text": "NEW REPORT"},
        )
        proj.build_path.write_text(json.dumps(later), "utf-8")
        p.poll_now()
        assert p.text("#report") == "NEW REPORT"
        assert p.text("#count") == "9 parts"
        assert len(p.inspect()["bodies"]) == 9
        assert "3 entries in build.json are not a part" in p.text("#notice")
        p.assert_clean()


# Makes drawBuild fail (its sort of the normalised parts throws) while window.__breakDraw is
# set, to check what the page shows when drawing goes wrong for any reason.
BREAK_DRAW = """
const sort = Array.prototype.sort;
Array.prototype.sort = function (...args) {
  if (window.__breakDraw && this.length && this[0] && this[0].index !== undefined
      && this[0].rot !== undefined) throw new Error('drawing failed on purpose');
  return sort.apply(this, args);
};
"""


@pytest.mark.browser
def test_a_build_that_cannot_be_drawn_is_reported(
    browser: Any, tmp_path: Path, pawn_path: Path
) -> None:
    with viewing(
        browser, tmp_path / "nodraw", pawn_path, layered_build(3), init_script=BREAK_DRAW
    ) as (p, proj):
        assert p.text("#count") == "10 parts"
        p.page.evaluate("() => { window.__breakDraw = true; }")
        proj.save_build(layered_build(4, report=Report(ok=True, part_count=13, text="NEWER")))
        p.poll_now()
        assert p.error() == "drawing failed on purpose"
        assert "could not draw this build" in p.text("#notice")
        # the header agrees with the (empty) view instead of keeping the old build's numbers
        assert p.inspect()["bodies"] == []
        assert p.text("#count") == "0 parts"
        assert p.state()["partCount"] == 0
        assert p.text("#stepLabel") == "No parts yet"

        p.page.evaluate("() => { window.__breakDraw = false; }")
        proj.save_build(layered_build(2))
        p.poll_now()
        assert p.error() is None
        assert p.text("#count") == "7 parts"
        assert not p.page.locator("#notice").is_visible()
        assert p.errors == [] and p.failed == []


@pytest.mark.browser
def test_bricks_are_upright_with_studs_on_top(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """One tall green column on a red plate: the column must appear taller than wide, the
    plate below it, and every stud on top of its part."""
    proj = Project.create(tmp_path / "tower", pawn_path, studs=4, name="Tower")
    parts = [Placement("3034", RED, 0, 3, 0, 0, 1)]  # 8x2 plate along x
    parts += [Placement("3005", GREEN, 3, 3, 1 + 3 * i, 0, 2 + i) for i in range(6)]  # 1x1 column
    proj.save_build(Build(shape=(8, 6, 19), parts=parts, report=None))
    r = Running(proj.path)
    p = Page(browser, r.url)
    try:
        p.open()
        assert p.page.locator("#report").text_content() == "Not checked yet"
        px = p.view_pixels("tower")
        column = np.linalg.norm(px - colour_rgb(catalog, GREEN), axis=2) < 40
        ys, xs = np.nonzero(column)
        assert len(ys) > 200
        assert (ys.max() - ys.min()) > 2 * (xs.max() - xs.min())  # z is up on screen
        redmask = np.linalg.norm(px - colour_rgb(catalog, RED), axis=2) < 50
        assert np.nonzero(redmask)[0].mean() > ys.mean()  # the plate is below the column
        drawn = p.inspect()
        assert_bodies_match(catalog, drawn["bodies"], parts)
        assert_studs_match(catalog, drawn["studs"], parts)
        top_body = max(b["max"][2] for b in drawn["bodies"])
        top_stud = max(drawn["studs"], key=lambda st: st["max"][2])
        assert top_stud["min"][2] >= top_body - 0.05  # the highest stud stands on the column
        assert top_stud["max"][2] > top_body + 1.5
        assert top_body == pytest.approx(19 * 3.2, abs=0.2)
        p.assert_clean()
    finally:
        p.close()
        r.close()


@pytest.mark.browser
def test_unassigned_steps_and_unknown_parts(browser: Any, tmp_path: Path, pawn_path: Path) -> None:
    proj = Project.create(tmp_path / "flat", pawn_path, studs=4, name="Flat")
    parts = [
        Placement("3001", RED, 0, 0, 0, 0, 0),
        Placement("3001", BLUE, 0, 2, 0, 0, 0),
        Placement("no-such-part", 9999, 4, 0, 0, 0, 0),
    ]
    proj.save_build(Build(shape=(6, 4, 3), parts=parts))
    r = Running(proj.path)
    p = Page(browser, r.url)
    try:
        p.open()
        s = p.state()
        assert (s["partCount"], s["visibleCount"], s["maxStep"]) == (3, 3, 0)
        assert p.page.locator("#step").is_disabled()
        assert p.page.locator("#next").is_disabled()
        assert p.page.locator("#count").text_content() == "3 parts"
        p.assert_clean()
    finally:
        p.close()
        r.close()


@pytest.mark.browser
def test_project_not_built_yet(browser: Any, tmp_path: Path, pawn_path: Path) -> None:
    proj = Project.create(tmp_path / "new", pawn_path, studs=4, name="Brand new")
    r = Running(proj.path)
    p = Page(browser, r.url)
    try:
        p.open()
        s = p.state()
        assert (s["partCount"], s["visibleCount"]) == (0, 0)
        notice = p.page.locator("#notice")
        assert notice.is_visible()
        assert "not been built yet" in (notice.text_content() or "")
        assert p.page.locator("#report").text_content() == "Not built yet"
        # the only problem allowed is the missing build.json itself
        assert all("build.json" in f for f in p.failed), p.failed
        assert all("404" in e for e in p.errors), p.errors
        assert p.external == []

        proj.save_build(layered_build(layers=1))
        p.page.wait_for_function("window.__bricksnap.partCount === 4", timeout=8000)
        assert not notice.is_visible()
    finally:
        p.close()
        r.close()


@pytest.mark.browser
def test_thousands_of_parts(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    proj = Project.create(tmp_path / "big", pawn_path, studs=40, name="Big")
    parts = []
    colours = [RED, BLUE, YELLOW, 15, 2, 0]
    n = 0
    for layer in range(12):
        for i in range(10):
            for j in range(20):
                if layer % 2 == 0:
                    parts.append(
                        Placement("3001", colours[n % 6], i * 4, j * 2, layer * 3, 0, layer + 1)
                    )
                else:
                    parts.append(
                        Placement("3001", colours[n % 6], j * 2, i * 4, layer * 3, 90, layer + 1)
                    )
                n += 1
    proj.save_build(Build(shape=(40, 40, 36), parts=parts))
    r = Running(proj.path)
    p = Page(browser, r.url)
    try:
        start = time.monotonic()
        p.open()
        assert time.monotonic() - start < 15
        assert p.state()["partCount"] == 2400
        px = p.view_pixels("many")
        assert near(px, colour_rgb(catalog, YELLOW)) > 500
        p.page.locator("#step").fill("3")
        assert p.state()["visibleCount"] == 600
        p.assert_clean()
    finally:
        p.close()
        r.close()


@pytest.mark.browser
def test_narrow_screen_has_no_sideways_scroll(browser: Any, running: Running) -> None:
    p = Page(browser, running.url, width=375, height=740)
    try:
        p.open()
        overflow = p.page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 0
        p.view_pixels("phone")
        p.assert_clean()
    finally:
        p.close()


# ---- part shapes (stage 2) ----------------------------------------------------------------

ROUND_KINDS = ("round_brick", "round_plate", "round_tile")
SLOPE_KINDS = ("slope", "curved_slope", "slope_inverted")


def expected_shape(kind: str) -> str:
    """What the page should draw for a catalogue kind (the contract in viewserver.py)."""
    return {
        "slope": "wedge",
        "curved_slope": "curved",
        "slope_inverted": "inverted",
        "cone": "cone",
        "dish": "dish",
    }.get(kind, "cylinder" if kind in ROUND_KINDS else "box")


def every_part_at_every_turn(catalog: Catalog) -> list[Placement]:
    parts = []
    for i, (part, rot) in enumerate(
        (part, rot) for part in catalog.parts.values() for rot in (0, 90, 180, 270)
    ):
        colour = sorted(part.colours)[i % len(part.colours)]
        parts.append(Placement(part.id, colour, (i % 14) * 6, (i // 14) * 6, 0, rot, 1))
    return parts


def _extent(face: dict[str, Any] | None) -> tuple[np.ndarray, np.ndarray]:
    assert face is not None
    return np.array(face["min"]), np.array(face["max"])


def check_wedge(catalog: Catalog, p: Placement, body: dict[str, Any]) -> None:
    """The slanted face runs down towards Catalog.low_side; the part is full height over its
    stud cells (or, upside down, stands on its full rows) and has a low lip on the far side."""
    part = catalog.parts[p.part]
    low = catalog.low_side(p)
    assert low is not None
    assert body["downhill"] == list(low), (p, body["downhill"], low)
    lo, hi = _box(body)
    axis = 0 if low[0] else 1
    # the edge the face runs down to, and the high edge opposite it
    low_edge = hi[axis] if low[axis] > 0 else lo[axis]
    high_edge = lo[axis] if low[axis] > 0 else hi[axis]
    if part.kind == "slope_inverted":
        tlo, thi = _extent(body["top"])
        assert np.allclose(tlo, lo[:2], atol=1e-3) and np.allclose(thi, hi[:2], atol=1e-3)
        blo, bhi = _extent(body["bottom"])  # it stands on the rows at its low side only
        assert min(abs(blo[axis] - low_edge), abs(bhi[axis] - low_edge)) < 1e-3, p
        assert min(abs(blo[axis] - high_edge), abs(bhi[axis] - high_edge)) > 4, p
        return
    blo, bhi = _extent(body["bottom"])
    assert np.allclose(blo, lo[:2], atol=1e-3) and np.allclose(bhi, hi[:2], atol=1e-3)
    if not part.studs_top:
        assert body["top"] is None, p  # slanted all the way: the top is only its high edge
        return
    tlo, thi = _extent(body["top"])
    assert min(abs(tlo[axis] - high_edge), abs(thi[axis] - high_edge)) < 1e-3, p
    assert min(abs(tlo[axis] - low_edge), abs(thi[axis] - low_edge)) > 4, p
    for cx, cy in catalog.stud_cells(p):  # every stud stands on the flat top
        c = np.array([(cx + 0.5) * 8, (cy + 0.5) * 8])
        assert (c >= tlo + 2).all() and (c <= thi - 2).all(), (p, c, tlo, thi)


@pytest.mark.browser
def test_part_kinds_and_shapes_match_the_catalogue(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """Every catalogue part at every turn: the page reports the catalogue's kind, draws the
    shape the contract names, and every wedge runs down towards Catalog.low_side."""
    parts = every_part_at_every_turn(catalog)
    with viewing(browser, tmp_path / "kinds", pawn_path, Build((84, 90, 3), parts)) as (p, _):
        drawn = p.inspect(detail=True)
        bodies = sorted(drawn["bodies"], key=lambda b: b["entry"])
        assert [b["entry"] for b in bodies] == list(range(len(parts)))
        slopes = 0
        for placement, body in zip(parts, bodies, strict=True):
            part = catalog.parts[placement.part]
            assert body["part"] == part.id
            assert body["kind"] == part.kind, placement
            assert body["shape"] == expected_shape(part.kind), placement
            check_edges(body, placement)
            if part.kind in SLOPE_KINDS:
                check_wedge(catalog, placement, body)
                check_slope_surface(part.kind, placement, body)
                slopes += 1
            else:
                assert body["downhill"] is None, placement
                assert body["slope"] is None, placement
        assert slopes == 4 * len([q for q in catalog.parts.values() if q.kind in SLOPE_KINDS])
        p.assert_clean()


def check_edges(body: dict[str, Any], p: Placement) -> None:
    """The part's dark edge lines follow its own drawn shape: every line end lies on the
    drawn body, and together they reach its whole box. A cylinder's lines are its two rims."""
    assert body["edges"] > 0 and body["edges"] % 2 == 0, p
    assert body["edgeGap"] < 0.01, (p, body["edgeGap"])
    elo, ehi = _box(body["edgeBox"])
    lo, hi = _box(body)
    assert np.allclose(elo, lo, atol=1e-3) and np.allclose(ehi, hi, atol=1e-3), p
    if body["shape"] in ("cylinder", "cone", "dish"):
        assert body["edges"] >= 2 * 2 * 24, (p, body["edges"])  # two rims of 24+ lines each
    elif body["shape"] == "box":
        assert body["edges"] == 24, (p, body["edges"])  # 12 lines


def check_slope_surface(kind: str, p: Placement, body: dict[str, Any]) -> None:
    """Heights of the drawn slanted face, near its top, half way down and near the lip: a
    straight slope is a straight line; the curved slope bulges above that line."""
    height = body["max"][2] - body["min"][2]
    if kind == "slope_inverted":
        assert body["slope"] is None, p
        return
    s = body["slope"]
    assert s is not None and None not in s.values(), (p, s)
    assert s["high"] > 0.85 * height and s["low"] < 0.4 * height, (p, s, height)
    straight = (s["high"] + s["low"]) / 2
    if kind == "curved_slope":
        assert s["mid"] > straight + 0.3, (p, s)  # a curve, gentle at the top
    else:
        assert s["mid"] == pytest.approx(straight, abs=0.05), (p, s)


@pytest.mark.browser
def test_round_parts_cones_and_tiles(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """Round parts are round (as wide as their cells, not cut to boxes), a cone tapers, a dish
    widens upwards, and a tile is a flat box with no studs."""
    ids = ["6141", "98138", "3062b", "6143", "14769", "59900", "4740", "3068b", "3070b", "3001"]
    parts = [Placement(pid, 15, i * 4, 0, 0, 0, 1) for i, pid in enumerate(ids)]
    with viewing(browser, tmp_path / "round", pawn_path, Build((40, 2, 3), parts)) as (p, _):
        drawn = p.inspect()
        by_part = {b["part"]: b for b in drawn["bodies"]}
        for pid in ids:
            body = by_part[pid]
            lo, hi = _box(body)
            width = (hi - lo)[:2]
            tlo, thi = _extent(body["top"])
            blo, bhi = _extent(body["bottom"])
            top, bottom = thi - tlo, bhi - blo
            kind = catalog.parts[pid].kind
            if kind == "cone":
                assert np.allclose(bottom, width, atol=1e-3)
                assert (top < 0.75 * width).all() and (top > 4.8).all(), top  # a stud fits
            elif kind == "dish":
                assert np.allclose(top, width, atol=1e-3) and (bottom < 0.75 * width).all()
            else:
                assert np.allclose(top, width, atol=1e-3) and np.allclose(bottom, width, atol=1e-3)
            # Measured on the drawn faces: from its centre along the diagonal of its square, a
            # round face reaches only its radius (a box reaches 1.41 times as far, a diamond
            # 0.71 times), and its rim has many corners.
            for face, rim in ((top, body["topRim"]), (bottom, body["bottomRim"])):
                radius = face[0] / 2
                if kind in ROUND_KINDS or kind in ("cone", "dish"):
                    assert rim["diagonal"] == pytest.approx(radius, abs=0.05), (pid, rim, radius)
                    assert rim["points"] >= 24, (pid, rim)
                else:  # a box: the diagonal reaches the corner of its narrower side
                    corner = min(face) / 2 * np.sqrt(2)
                    assert rim["diagonal"] == pytest.approx(corner, abs=0.05), (pid, rim)
                    assert rim["points"] == 4, (pid, rim)
        assert by_part["3062b"]["topRim"]["diagonal"] == pytest.approx(3.8, abs=0.05)
        assert by_part["6143"]["topRim"]["diagonal"] == pytest.approx(7.8, abs=0.05)
        assert by_part["3062b"]["shape"] == "cylinder" and by_part["3001"]["shape"] == "box"
        assert by_part["3068b"]["shape"] == "box" and by_part["3068b"]["kind"] == "tile"
        stud_x = sorted(round((s["min"][0] + s["max"][0]) / 2 / 8 - 0.5) for s in drawn["studs"])
        expected = sorted(
            cx for q in parts for cx, _ in catalog.stud_cells(q) if catalog.parts[q.part].studs_top
        )
        assert stud_x == expected  # tiles, round tiles and the dish have none
        p.assert_clean()


def roof_build() -> Build:
    """Slopes in all four directions round a white base, and a row of every other slope in
    front of it (all turned to run down towards the front, -y)."""
    parts = [Placement("3003", 15, x, y, 0, 0, 1) for x in (2, 4, 6) for y in (5, 7, 9)]
    for x in (2, 4, 6):
        parts.append(Placement("3039", RED, x, 5, 3, 0, 2))  # runs down to the front (-y)
        parts.append(Placement("3039", YELLOW, x, 9, 3, 180, 2))  # to the back (+y)
    parts.append(Placement("3039", GREEN, 2, 7, 3, 270, 2))  # to the left (-x)
    parts.append(Placement("3039", BLUE, 6, 7, 3, 90, 2))  # to the right (+x)
    parts.append(Placement("3003", 15, 4, 7, 3, 0, 2))
    gallery = [("3040b", RED), ("54200", BLUE), ("85984", YELLOW), ("4286", GREEN)]
    gallery += [("11477", 15), ("3665b", 0)]
    for i, (pid, colour) in enumerate(gallery):
        parts.append(Placement(pid, colour, i * 2, 0, 0, 0, 3))
    return Build((12, 11, 9), parts)


def tiled_build() -> Build:
    """An 8 x 8 grey plate covered in tiles: square and round, in a few colours."""
    parts = [Placement("3034", 72, 0, y, 0, 0, 1) for y in (0, 2, 4, 6)]
    tiles = [
        ("14769", 15, 0, 0, 0),
        ("3068b", 1, 2, 0, 0),
        ("14769", 4, 4, 0, 0),
        ("3068b", 15, 6, 0, 0),
        ("87079", 14, 0, 2, 0),
        ("3069b", 4, 6, 2, 0),
        ("3069b", 0, 6, 3, 0),
        ("3068b", 4, 4, 4, 0),
        ("14769", 1, 6, 4, 0),
        ("2431", 0, 0, 6, 0),
        ("2431", 15, 0, 7, 0),
    ]
    tiles += [("98138", (14, 0)[(x + y) % 2], x, y, 0) for x in (4, 5) for y in (2, 3)]
    tiles += [("3070b", (15, 1)[(x + y) % 2], x, y, 0) for x in range(4) for y in (4, 5)]
    tiles += [("98138", (4, 15)[(x + y) % 2], x, y, 0) for x in range(4, 8) for y in (6, 7)]
    parts += [Placement(pid, c, x, y, 1, rot, 2) for pid, c, x, y, rot in tiles]
    return Build((8, 8, 2), parts)


def round_build() -> Build:
    """Round bricks, round plates, a dish and cones."""
    parts = [Placement("3062b", RED, 0, 0, z, 0, 1 + z // 3) for z in (0, 3, 6)]
    parts.append(Placement("59900", YELLOW, 0, 0, 9, 0, 4))
    parts += [Placement("6143", BLUE, 2, 0, z, 0, 1 + z // 3) for z in (0, 3)]
    parts.append(Placement("4740", 15, 2, 0, 6, 0, 3))
    parts += [Placement("6141", GREEN, 5, 0, z, 0, 1) for z in range(4)]
    parts.append(Placement("98138", 15, 5, 0, 4, 0, 2))
    parts.append(Placement("3795", 72, 0, 3, 0, 0, 1))
    parts += [Placement("59900", (RED, YELLOW, BLUE)[i], i * 2, 3, 1, 0, 2) for i in range(3)]
    parts += [Placement("3062b", 15, i * 2 + 1, 4, 1, 0, 2) for i in range(3)]
    return Build((7, 5, 12), parts)


def _show(p: Page, proj: Project, build: Build) -> dict[str, Any]:
    version = p.state()["buildVersion"]
    proj.save_build(build)
    p.poll_now()
    assert p.state()["buildVersion"] > version
    return p.inspect()


@pytest.mark.browser
def test_part_shapes_pictures(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """Pictures of a roof of slopes, a tiled plate and round parts, to look at by eye
    (tests/artifacts/viewer-roof.png, viewer-tiles.png, viewer-round.png)."""
    roof = roof_build()
    with viewing(browser, tmp_path / "shapes", pawn_path, roof) as (p, proj):
        drawn = p.inspect()
        downhill = {
            tuple(b["downhill"]) for b in drawn["bodies"] if b["part"] == "3039" and b["downhill"]
        }
        assert downhill == {(0, -1), (0, 1), (-1, 0), (1, 0)}
        px = p.view_pixels("roof")
        for code in (RED, YELLOW, GREEN, BLUE):
            assert near(px, colour_rgb(catalog, code)) > 300, code
        _fits(p)

        drawn = _show(p, proj, tiled_build())
        # a tiled plate is smooth: only the plate's own studs, hidden under the tiles
        assert len(drawn["studs"]) == 64
        assert all(st["max"][2] < 2 * 3.2 for st in drawn["studs"])
        assert sum(b["shape"] == "cylinder" for b in drawn["bodies"]) == 3 + 4 + 8
        px = p.view_pixels("tiles")
        assert near(px, colour_rgb(catalog, YELLOW)) > 1000
        _fits(p)

        drawn = _show(p, proj, round_build())
        shapes = [b["shape"] for b in drawn["bodies"]]
        assert shapes.count("cone") == 4 and shapes.count("dish") == 1
        px = p.view_pixels("round")
        for code in (RED, YELLOW, GREEN, BLUE):
            assert near(px, colour_rgb(catalog, code)) > 300, code
        _fits(p)
        p.assert_clean()


@pytest.mark.browser
def test_model_fills_the_view(browser: Any, tmp_path: Path, pawn_path: Path) -> None:
    """A 16-stud model fills most of the view (it used to fill about 40% of its height),
    while every part stays in view."""
    parts = [
        Placement("3003", (RED, BLUE)[(x + y + z) % 2], x * 2, y * 2, z * 3, 0, 1 + z)
        for x in range(8)
        for y in range(8)
        for z in range(4)
    ]
    with viewing(browser, tmp_path / "fill", pawn_path, Build((16, 16, 12), parts)) as (p, _):
        ndc = _fits(p)
        tall, wide = (ndc["maxY"] - ndc["minY"]) / 2, (ndc["maxX"] - ndc["minX"]) / 2
        assert max(tall, wide) > 0.85, ndc
        assert abs(ndc["maxY"] + ndc["minY"]) < 0.1 and abs(ndc["maxX"] + ndc["minX"]) < 0.1, ndc
        p.view_pixels("fill")
        p.assert_clean()


@pytest.mark.browser
def test_thousands_of_shaped_parts_stay_instanced(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """3,000 parts of every shape load quickly and are drawn with a handful of meshes."""
    ids = ["3001", "3039", "4286", "3665b", "11477", "3062b", "59900", "6143", "3068b", "4740"]
    parts = []
    for n in range(3000):
        layer, rest = divmod(n, 300)
        i, j = divmod(rest, 15)
        parts.append(
            Placement(
                ids[n % len(ids)],
                (RED, BLUE, YELLOW)[n % 3],
                i * 4,
                j * 4,
                layer * 3,
                (0, 90, 180, 270)[n % 4],
                layer + 1,
            )
        )
    start = time.monotonic()
    with viewing(browser, tmp_path / "many", pawn_path, Build((80, 60, 30), parts)) as (p, _):
        assert time.monotonic() - start < 15
        assert p.state()["partCount"] == 3000
        drawn = p.inspect()
        assert len(drawn["bodies"]) == 3000
        # one mesh per colour and shape (bodies and studs), plus edges and outlines
        assert drawn["meshCount"] < 80, drawn["meshCount"]
        p.view_pixels("many-shapes")
        p.assert_clean()


# ---- notes under the verdict --------------------------------------------------------------


@pytest.mark.browser
def test_build_notes_are_shown_under_the_verdict(
    browser: Any, tmp_path: Path, pawn_path: Path
) -> None:
    short = Build(
        shape=(6, 6, 15),
        parts=layered_build().parts,
        report=layered_build().report,
        notes=["Added 2 plates to hold the arm.", "Moved a brick <b>left</b> & down."],
    )
    with viewing(browser, tmp_path / "notes", pawn_path, layered_build()) as (p, proj):
        notes = p.page.locator("#notes")
        assert not notes.is_visible()  # no notes, no list

        proj.save_build(short)
        p.poll_now()
        assert notes.is_visible()
        assert p.text("#notes .notes-title") == "What the software changed"
        items = p.page.locator("#notes li")
        assert items.all_text_contents() == list(short.notes)
        assert p.page.locator("#notes li b").count() == 0  # shown as text, never as HTML
        assert p.page.locator("#notes details").count() == 0
        # under the verdict
        verdict = p.page.locator("#report").bounding_box()
        box = notes.bounding_box()
        assert verdict and box and box["y"] >= verdict["y"] + verdict["height"]
        p.view_pixels("notes-short")

        long_notes = [
            f"Change number {i + 1}: a plate was added at x={i}, y=2, z=3." for i in range(5)
        ]
        raw = short.to_json()
        raw["notes"] = long_notes[:2] + ["", 7, None] + long_notes[2:]
        proj.build_path.write_text(json.dumps(raw), "utf-8")
        p.poll_now()
        summary = p.page.locator("#notes summary")
        assert summary.text_content() == "What the software changed (5)"
        assert not p.page.locator("#notes li").first.is_visible()  # folded away
        p.view_pixels("notes-folded")
        summary.click()
        assert p.page.locator("#notes li").all_text_contents() == long_notes
        assert p.page.locator("#notes li").first.is_visible()
        p.view_pixels("notes-open")

        # a rebuild keeps the list open if the person opened it
        raw["notes"] = long_notes + ["One more change."]
        proj.build_path.write_text(json.dumps(raw), "utf-8")
        p.poll_now()
        assert p.text("#notes summary") == "What the software changed (6)"
        assert p.page.locator("#notes li").first.is_visible()

        proj.save_build(layered_build())
        p.poll_now()
        assert not notes.is_visible()
        p.assert_clean()


@pytest.mark.browser
def test_notes_fit_a_phone_screen(browser: Any, tmp_path: Path, pawn_path: Path) -> None:
    long = "A very long note that goes on and on " * 8
    build = Build((6, 6, 15), layered_build().parts, layered_build().report, notes=[long, "x"])
    with viewing(browser, tmp_path / "phone", pawn_path, build, width=375, height=740) as (p, _):
        assert p.page.locator("#notes").is_visible()
        overflow = p.page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 0
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        p.page.screenshot(path=str(ARTIFACTS / "viewer-notes-phone.png"))
        p.assert_clean()


# ---- the plain conversion and the designed build side by side (stage 3) -------------------

CAT = REPO / "samples" / "projects" / "cat-designed"
PAWN_PROJECT = REPO / "samples" / "projects" / "pawn"
ROUGH = "build.rough.json"


def copy_project(src: Path, dest: Path, *, rough: bool = True) -> Path:
    """The files the page reads from a sample project, copied so the test can change them."""
    dest.mkdir(parents=True)
    for name in ("project.json", "build.json", ROUGH):
        if (src / name).exists() and (rough or name != ROUGH):
            shutil.copy(src / name, dest / name)
    return dest


@contextlib.contextmanager
def serving(browser: Any, folder: Path, width: int = 1100, height: int = 820) -> Generator[Page]:
    r = Running(folder)
    p = Page(browser, r.url, width=width, height=height)
    try:
        yield p.open()
    finally:
        p.close()
        r.close()


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data), "utf-8")


def _drag_at(p: Page, rect: dict[str, float], dx: float, dy: float) -> None:
    """Drag from the middle of ``rect`` (page pixels)."""
    cx, cy = rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2
    p.page.mouse.move(cx, cy)
    p.page.mouse.down()
    p.page.mouse.move(cx + dx, cy + dy, steps=8)
    p.page.mouse.up()
    p.settle()


def _inside(ndc: dict[str, float] | None) -> bool:
    return bool(ndc) and -1 < ndc["minX"] < ndc["maxX"] < 1 and -1 < ndc["minY"] < ndc["maxY"] < 1


def _assert_drawn_in_panes(drawn: dict[str, Any]) -> None:
    """Each shown view was drawn by one pass of the renderer (in order, left to right), inside
    its own rectangle, with only its own build visible and the camera shaped like the
    rectangle. ``frame`` is what the page recorded while it drew, not worked out from the
    layout."""
    shown = [n for n in ("rough", "designed") if drawn["views"][n]["shown"]]
    passes = drawn["frame"]
    assert [ps["groups"] for ps in passes] == [[n] for n in shown]
    for ps, name in zip(passes, shown, strict=True):
        view = drawn["views"][name]
        rect = view["rect"]
        box = [rect["x"], rect["y"], rect["width"], rect["height"]]
        assert ps["viewport"] == pytest.approx(box, abs=1), name
        if drawn["compare"]["active"]:
            assert ps["scissor"] == pytest.approx(box, abs=1), name
        else:
            assert ps["scissor"] is None
        assert ps["aspect"] == pytest.approx(rect["width"] / rect["height"], rel=0.01), name
        assert ps["camera"] == view["camera"]["id"]


def _rect_mask(shape: tuple[int, ...], rect: dict[str, float], origin: dict[str, float]):
    """The pixels of a ``#view`` screenshot that lie in ``rect`` (page pixels), counting a
    pixel the rectangle only partly covers."""
    mask = np.zeros(shape[:2], dtype=bool)
    x0, y0 = rect["x"] - origin["x"], rect["y"] - origin["y"]
    x1, y1 = x0 + rect["width"], y0 + rect["height"]
    mask[
        max(0, int(np.floor(y0))) : int(np.ceil(y1)), max(0, int(np.floor(x0))) : int(np.ceil(x1))
    ] = True
    return mask


def _rendered_cameras(p: Page) -> tuple[list[float], list[float]]:
    """The camera position each view was last drawn with (both views must be shown)."""
    p.settle()
    views = p.inspect()["views"]
    return views["rough"]["camera"]["position"], views["designed"]["camera"]["position"]


def test_project_files_route_says_which_files_exist(running: Running, project: Project) -> None:
    """The page learns whether there is a plain conversion without asking for a file that is
    not there (a 404 shows as an error in the browser's console every two seconds)."""
    status, headers, body = running.request("/project-files.json?t=1")
    assert status == 200
    assert headers["content-type"].startswith("application/json")
    assert headers["cache-control"] == "no-store"
    none = {"versions": [], "current": None}  # a project with no versions
    assert json.loads(body) == {"files": ["project.json", "build.json"], **none}
    (project.path / ROUGH).write_text("{}", "utf-8")
    assert json.loads(running.request("/project-files.json")[2]) == {
        "files": ["project.json", "build.json", ROUGH],
        **none,
    }
    project.build_path.unlink()
    (project.path / ROUGH).unlink()
    (project.path / ROUGH).mkdir()  # a folder is not a file
    assert json.loads(running.request("/project-files.json")[2]) == {
        "files": ["project.json"],
        **none,
    }
    assert running.request("/project-files.json", method="HEAD")[2] == b""
    assert running.request("/project-files.json", host="evil.example.com")[0] == 404
    assert running.request("/project-files.json/")[0] == 404
    assert running.request("/project-files.json", method="POST")[0] == 405


@pytest.mark.browser
def test_plain_conversion_and_designed_side_by_side(
    browser: Any, tmp_path: Path, catalog: Catalog
) -> None:
    """The cat: the plain conversion on the left and the designed build on the right, each
    named with its part count, on one grid under one camera, with the designer's brief."""
    folder = copy_project(CAT, tmp_path / "cat")
    rough, build = Build.load(folder / ROUGH), Build.load(folder / "build.json")
    brief = json.loads((folder / "project.json").read_text("utf-8"))["brief"]
    with serving(browser, folder, width=1440, height=900) as p:
        pg = p.page
        drawn = p.inspect()
        assert drawn["compare"] == {"active": True, "show": "both"}
        r, d = drawn["views"]["rough"], drawn["views"]["designed"]
        assert (r["shown"], d["shown"]) == (True, True)
        assert (r["partCount"], d["partCount"]) == (174, 124)
        assert_bodies_match(catalog, r["bodies"], rough.parts)
        assert_bodies_match(catalog, d["bodies"], build.parts)
        assert d["bodies"] == drawn["bodies"]  # the page's own report is the designed build
        assert p.text("#count") == "124 parts"

        # side by side, the same size, the plain conversion on the left
        rr, dr = r["rect"], d["rect"]
        assert rr["x"] + rr["width"] <= dr["x"]
        assert rr["y"] == pytest.approx(dr["y"], abs=1)
        assert rr["width"] == pytest.approx(dr["width"], abs=2)
        assert rr["height"] == pytest.approx(dr["height"], abs=2)
        assert rr["width"] > 400 and rr["height"] > 400
        assert pg.locator("#roughTag").is_visible() and pg.locator("#designedTag").is_visible()
        assert p.text("#roughTag .pane-title") == "Plain conversion"
        assert p.text("#designedTag .pane-title") == "Designed"
        assert "174 parts" in p.text("#roughTag") and "124 parts" in p.text("#designedTag")
        tag = pg.locator("#roughTag").bounding_box()
        assert tag and rr["x"] <= tag["x"] < tag["x"] + tag["width"] <= rr["x"] + rr["width"]

        # one camera, one grid, one scale: both whole models in view, drawn the same way
        assert drawn["sharedCamera"] is True
        assert r["camera"] == d["camera"]
        assert _inside(r["ndc"]) and _inside(d["ndc"])
        # geometry and materials are shared between the two views
        colours = {q.color for q in rough.parts + build.parts}
        assert set(r["materials"]) & set(d["materials"])
        assert len(set(r["materials"]) | set(d["materials"])) == len(colours)
        assert set(r["geometries"]) & set(d["geometries"])

        # the brief, written as text
        box = pg.locator("#brief")
        assert box.is_visible()
        assert p.text("#brief .brief-object") == brief["object"]
        assert pg.locator("#brief .brief-features li").all_text_contents() == brief["features"]
        assert p.text("#brief .brief-plan") == brief["plan"]
        assert p.text("#brief .brief-finish") == brief["finish"]
        names = pg.locator("#brief .swatch-name").all_text_contents()
        assert names == ["Dark Bluish Grey", "Light Bluish Grey", "Black", "Bright Pink"]
        backgrounds = pg.locator("#brief .swatch").evaluate_all(
            "els => els.map(e => getComputedStyle(e).backgroundColor)"
        )
        assert backgrounds == [
            "rgb({}, {}, {})".format(*catalog.colours[c].rgb) for c in brief["colours"]
        ]
        # beside the views on a wide screen
        brief_box, view_box = box.bounding_box(), pg.locator("#view").bounding_box()
        assert brief_box and view_box and brief_box["x"] >= view_box["x"] + view_box["width"]

        # each pane is drawn with its own build, inside its frame, the camera shaped to it
        # (test_each_view_draws_its_own_build tells the two builds apart by colour)
        px = p.view_pixels("compare")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(ARTIFACTS / "viewer-compare-brief.png"), full_page=True)
        _assert_drawn_in_panes(p.inspect())
        grey = view_masks(px, catalog, 72)
        origin = pg.locator("#view").bounding_box()
        assert origin
        assert grey[_rect_mask(px.shape, rr, origin)].sum() > 3000
        assert grey[_rect_mask(px.shape, dr, origin)].sum() > 3000

        # turning one view turns the other, whichever is dragged
        start = _rendered_cameras(p)
        assert start[0] == start[1]
        _drag_at(p, rr, 160, 30)
        turned = _rendered_cameras(p)
        assert turned[0] == turned[1] and not np.allclose(turned[0], start[0], atol=1)
        _drag_at(p, dr, -120, -20)
        again = _rendered_cameras(p)
        assert again[0] == again[1] and not np.allclose(again[0], turned[0], atol=1)
        assert p.inspect()["sharedCamera"] is True

        # the step slider acts on the designed build, and the page says so
        assert pg.locator("#stepsFor").is_visible()
        assert p.text("#stepsFor") == "The steps are for the designed build."
        pg.locator("#step").fill("3")
        views = p.inspect()["views"]
        early = [q for q in build.parts if q.step <= 3]
        assert len(views["designed"]["bodies"]) == len(early) < 124
        assert len(views["rough"]["bodies"]) == 174
        pg.locator("#all").click()

        # the switch: either one alone, then both again
        pg.locator("#compare [data-show=designed]").click()
        views = p.inspect()["views"]
        assert (views["rough"]["shown"], views["designed"]["shown"]) == (False, True)
        assert views["designed"]["rect"]["width"] > 1.8 * dr["width"]
        assert not pg.locator("#roughTag").is_visible()
        assert pg.locator("#compare [data-show=designed]").get_attribute("aria-pressed") == "true"
        assert _inside(views["designed"]["ndc"])
        pg.screenshot(path=str(ARTIFACTS / "viewer-compare-designed-only.png"))

        pg.locator("#compare [data-show=rough]").click()
        views = p.inspect()["views"]
        assert (views["rough"]["shown"], views["designed"]["shown"]) == (True, False)
        assert not pg.locator("#designedTag").is_visible()
        assert _inside(views["rough"]["ndc"])
        pg.screenshot(path=str(ARTIFACTS / "viewer-compare-rough-only.png"))

        # the choice survives a rebuild
        version = p.state()["buildVersion"]
        _write_json(
            folder / "build.json", dict(build.to_json(), parts=build.to_json()["parts"][1:])
        )
        p.poll_now()
        assert p.state()["buildVersion"] > version
        assert p.inspect()["compare"] == {"active": True, "show": "rough"}
        assert "123 parts" in p.text("#designedTag") and p.text("#count") == "123 parts"
        pg.locator("#compare [data-show=both]").click()
        views = p.inspect()["views"]
        assert (views["rough"]["shown"], views["designed"]["shown"]) == (True, True)

        # a screen too narrow for the brief beside the views shows it under the steps
        pg.set_viewport_size({"width": 1100, "height": 820})
        p.settle()
        steps_box, brief_box = pg.locator(".steps").bounding_box(), box.bounding_box()
        assert steps_box and brief_box and brief_box["y"] >= steps_box["y"] + steps_box["height"]
        views = p.inspect()["views"]
        assert _inside(views["rough"]["ndc"]) and _inside(views["designed"]["ndc"])
        pg.screenshot(path=str(ARTIFACTS / "viewer-compare-1100.png"), full_page=True)

        # picking what to show keeps the person's zoom and the point they look at, though
        # one view alone is wide and two side by side are tall
        rr = p.inspect()["views"]["rough"]["rect"]
        pg.mouse.move(rr["x"] + rr["width"] / 2, rr["y"] + rr["height"] / 2)
        pg.mouse.wheel(0, -600)
        p.settle()
        zoomed = p.inspect()["camera"]
        for show in ("designed", "rough", "both"):
            pg.locator(f"#compare [data-show={show}]").click()
            p.settle()
            camera = p.inspect()["camera"]
            assert camera["position"] == pytest.approx(zoomed["position"], abs=1e-6), show
            assert camera["target"] == pytest.approx(zoomed["target"], abs=1e-6), show
        assert p.inspect()["sharedCamera"] is True

        # without the plain conversion the page is as it always was
        (folder / ROUGH).unlink()
        p.poll_now()
        drawn = p.inspect()
        assert drawn["compare"]["active"] is False
        assert drawn["views"]["rough"]["shown"] is False
        for hidden in ("#compare", "#roughTag", "#designedTag", "#stepsFor"):
            assert not pg.locator(hidden).is_visible(), hidden
        assert drawn["views"]["designed"]["rect"]["width"] > 1.6 * views["rough"]["rect"]["width"]
        assert _inside(drawn["ndc"])
        p.assert_clean()


@pytest.mark.browser
def test_side_by_side_stacks_on_a_phone(browser: Any, tmp_path: Path, catalog: Catalog) -> None:
    folder = copy_project(CAT, tmp_path / "cat")
    with serving(browser, folder, width=375, height=740) as p:
        views = p.inspect()["views"]
        rr, dr = views["rough"]["rect"], views["designed"]["rect"]
        assert rr["y"] + rr["height"] <= dr["y"]  # one above the other
        assert rr["x"] == pytest.approx(dr["x"], abs=1)
        assert rr["width"] == pytest.approx(dr["width"], abs=2)
        assert rr["height"] == pytest.approx(dr["height"], abs=2) and rr["height"] > 250
        assert _inside(views["rough"]["ndc"]) and _inside(views["designed"]["ndc"])
        overflow = p.page.evaluate(
            "document.documentElement.scrollWidth - document.documentElement.clientWidth"
        )
        assert overflow <= 0
        assert p.page.locator("#brief").is_visible()
        for name in ("rough", "designed"):  # the name tags are one short line
            tag = p.page.locator(f"#{name}Tag").bounding_box()
            assert tag and tag["height"] < 40 and tag["width"] < views[name]["rect"]["width"]
        assert p.text("#designedTag").split() == [
            "Designed",
            "What",
            "BrickSnap",
            "made",
            "of",
            "it",
            "·",
            "124",
            "parts",
        ]
        assert p.page.locator("#designedTag .pane-what").is_hidden()
        buttons = p.page.locator("#compare button").evaluate_all(
            "els => els.map(e => e.getBoundingClientRect().top)"
        )
        assert max(buttons) - min(buttons) < 2  # the three choices on one row
        px = p.view_pixels("compare-phone")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        p.page.screenshot(path=str(ARTIFACTS / "viewer-compare-phone-full.png"), full_page=True)
        grey = view_masks(px, catalog, 72)
        half = px.shape[0] // 2
        assert grey[:half].sum() > 1000 and grey[half:].sum() > 1000
        p.assert_clean()


@pytest.mark.browser
def test_one_build_and_no_brief(browser: Any, tmp_path: Path) -> None:
    """The pawn has one build and no brief: the page is as before. A brief, or a plain
    conversion that differs from the build, appears as soon as it is written; a plain
    conversion equal to the build changes nothing."""
    folder = copy_project(PAWN_PROJECT, tmp_path / "pawn")
    with serving(browser, folder) as p:
        pg = p.page
        drawn = p.inspect()
        assert drawn["compare"]["active"] is False
        assert drawn["views"]["rough"] == {**drawn["views"]["rough"], "shown": False}
        assert drawn["views"]["rough"]["partCount"] == 0
        assert drawn["views"]["designed"]["shown"] is True
        for hidden in ("#compare", "#roughTag", "#designedTag", "#stepsFor", "#brief"):
            assert not pg.locator(hidden).is_visible(), hidden
        rect, view = drawn["views"]["designed"]["rect"], pg.locator("#view").bounding_box()
        assert view and rect["width"] == pytest.approx(view["width"] - 6, abs=1)
        assert p.text("#count") == "294 parts"
        assert _inside(drawn["ndc"])
        _assert_drawn_in_panes(drawn)  # one pass over the whole canvas
        p.view_pixels("one-build")
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(ARTIFACTS / "viewer-one-build-full.png"), full_page=True)

        # a brief appears without a rebuild, every field shown as text: markup in any of them
        # makes no element, loads nothing and runs nothing
        hostile = '<img src="x" onerror="window.__pwned = 1"><script>window.__pwned = 2</script>'
        brief_tags = "els => [...new Set(els.map(e => e.tagName))]"
        meta = json.loads((folder / "project.json").read_text("utf-8"))
        meta["brief"] = {
            "object": f"A <b>chess</b> pawn.{hostile}",
            "features": ["round head", "", 7, f"wide <i>base</i>{hostile}"],
            "plan": f"Keep it simple.{hostile}",
            "colours": [71, 9999],
            "finish": f"Studs everywhere.{hostile}",
        }
        _write_json(folder / "project.json", meta)
        p.poll_now()
        p.settle()
        assert pg.locator("#brief").is_visible()
        assert p.text("#brief .brief-object") == meta["brief"]["object"]
        assert pg.locator("#brief .brief-features li").all_text_contents() == [
            "round head",
            f"wide <i>base</i>{hostile}",
        ]
        assert p.text("#brief .brief-plan") == meta["brief"]["plan"]
        assert p.text("#brief .brief-finish") == meta["brief"]["finish"]
        assert set(pg.locator("#briefBody *").evaluate_all(brief_tags)) == {
            "P",
            "H3",
            "UL",
            "LI",
            "SPAN",
        }
        names = pg.locator("#brief .swatch-name").all_text_contents()
        assert names == ["Light Bluish Grey", "Colour 9999"]
        meta["brief"] = f"An older brief written as one paragraph.{hostile}"
        _write_json(folder / "project.json", meta)
        p.poll_now()
        p.settle()
        assert p.text("#brief .brief-object") == meta["brief"]
        assert pg.locator("#brief .brief-features li").count() == 0
        assert set(pg.locator("#briefBody *").evaluate_all(brief_tags)) == {"P"}
        assert pg.evaluate("() => window.__pwned") is None

        # a plain conversion with nothing in it to draw counts as none
        for text in ("{}", '{"parts": []}', '{"parts": "x"}', '{"parts": [null, 3, "a"]}'):
            version = pg.evaluate("() => window.__bricksnap.roughVersion")
            (folder / ROUGH).write_text(text, "utf-8")
            p.poll_now()
            assert pg.evaluate("() => window.__bricksnap.roughVersion") > version, text
            drawn = p.inspect()
            assert drawn["compare"]["active"] is False, text
            assert drawn["views"]["rough"]["shown"] is False, text
            for hidden in ("#compare", "#roughTag", "#designedTag", "#stepsFor"):
                assert not pg.locator(hidden).is_visible(), (text, hidden)
            assert drawn["views"]["designed"]["rect"]["width"] == pytest.approx(rect["width"])

        # a plain conversion equal to the build changes nothing
        build = json.loads((folder / "build.json").read_text("utf-8"))
        _write_json(folder / ROUGH, build)
        p.poll_now()
        assert p.inspect()["compare"]["active"] is False
        assert not pg.locator("#compare").is_visible()

        # one that differs is shown beside it at once
        _write_json(folder / ROUGH, dict(build, parts=build["parts"][:-10]))
        p.poll_now()
        drawn = p.inspect()
        assert drawn["compare"] == {"active": True, "show": "both"}
        assert drawn["views"]["rough"]["partCount"] == 284
        assert pg.locator("#compare").is_visible() and pg.locator("#stepsFor").is_visible()
        p.assert_clean()


@pytest.mark.browser
def test_two_big_builds_stay_quick(browser: Any, tmp_path: Path, pawn_path: Path) -> None:
    """Two 600-part builds side by side load quickly and are drawn with few meshes that
    share materials."""
    proj = Project.create(tmp_path / "two", pawn_path, studs=4, name="Two")
    designed = [
        Placement(
            "3001",
            (RED, BLUE, YELLOW)[n % 3],
            (n % 10) * 4,
            (n // 10 % 6) * 2,
            n // 60 * 3,
            0,
            1 + n // 60,
        )
        for n in range(600)
    ]
    plain = [
        Placement("3003", (RED, BLUE)[n % 2], (n % 20) * 2, (n // 20 % 6) * 2, n // 120 * 3, 0, 1)
        for n in range(600)
    ]
    proj.save_build(Build((40, 12, 30), designed))
    Build((40, 12, 15), plain).save(proj.path / ROUGH)
    start = time.monotonic()
    with serving(browser, proj.path) as p:
        assert time.monotonic() - start < 15
        drawn = p.inspect()
        r, d = drawn["views"]["rough"], drawn["views"]["designed"]
        assert (len(r["bodies"]), len(d["bodies"])) == (600, 600)
        # Exactly: one body mesh and one stud mesh per colour, the two edge-line objects
        # (all edges, and the current step's), and one highlight outline per shape.
        assert (d["meshCount"], r["meshCount"]) == (3 + 3 + 2 + 1, 2 + 2 + 2 + 1)
        assert set(r["materials"]) <= set(d["materials"])
        # Drawing both views costs exactly what drawing each build alone costs, added up:
        # one pass per view, the same draw calls and triangles, nothing drawn twice. And in
        # time, loosely. (The headless browser draws in software, hundreds of times slower
        # than a graphics card, so the times themselves say little.)
        timed = p.page.evaluate(
            """() => Object.fromEntries(['designed', 'rough', 'both'].map((show) => {
                document.querySelector(`#compare [data-show=${show}]`).click();
                const ms = window.__bricksnap.timeFrames(2);
                return [show, {ms, frame: window.__bricksnap.inspect().frame}];
            }))"""
        )
        frames = {show: t["frame"] for show, t in timed.items()}
        ms = {show: t["ms"] for show, t in timed.items()}
        assert [ps["groups"] for ps in frames["designed"]] == [["designed"]]
        assert [ps["groups"] for ps in frames["rough"]] == [["rough"]]
        assert [ps["groups"] for ps in frames["both"]] == [["rough"], ["designed"]]
        for key in ("calls", "triangles"):
            assert frames["both"][0][key] == frames["rough"][0][key], key
            assert frames["both"][1][key] == frames["designed"][0][key], key
        assert frames["rough"][0]["triangles"] < frames["designed"][0]["triangles"]
        assert ms["both"] < 2 * (ms["designed"] + ms["rough"]), ms
        p.assert_clean()


@pytest.mark.browser
def test_each_view_draws_its_own_build(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """The designed build has blue the plain one lacks, the plain one green the designed one
    lacks, and both have red. Blue shows only in the designed build's pane and green only in
    the plain conversion's, and no brick colour shows outside the panes shown, whichever
    the person chose to see."""
    proj = Project.create(tmp_path / "own", pawn_path, studs=4, name="Own")
    designed = [
        Placement("3001", (RED, BLUE)[z % 2], 0, y, 3 * z, 0, 1 + z)
        for z in range(5)
        for y in (0, 2)
    ]
    plain = [
        Placement("3003", (GREEN, RED)[(x + z) % 2], x, y, 3 * z, 0, 1)
        for z in range(5)
        for x in (0, 2)
        for y in (0, 2)
    ]
    proj.save_build(Build((8, 8, 15), designed))
    Build((8, 8, 15), plain).save(proj.path / ROUGH)
    with serving(browser, proj.path) as p:
        pg = p.page
        for show in ("both", "rough", "designed"):
            pg.locator(f"#compare [data-show={show}]").click()
            px = p.view_pixels(f"own-panes-{show}")
            drawn = p.inspect()
            assert drawn["compare"] == {"active": True, "show": show}
            _assert_drawn_in_panes(drawn)
            origin = pg.locator("#view").bounding_box()
            assert origin
            panes = {
                name: _rect_mask(px.shape, v["rect"], origin)
                if v["shown"]
                else np.zeros(px.shape[:2], dtype=bool)
                for name, v in drawn["views"].items()
            }
            shown = [name for name, v in drawn["views"].items() if v["shown"]]
            assert shown == {"both": ["rough", "designed"]}.get(show, [show])
            for code, owner in ((BLUE, "designed"), (GREEN, "rough")):
                mask = view_masks(px, catalog, code)
                assert mask[~panes[owner]].sum() == 0, (show, code)
                if owner in shown:
                    assert mask[panes[owner]].sum() > 300, (show, code)
            red = view_masks(px, catalog, RED)
            assert red[~(panes["rough"] | panes["designed"])].sum() == 0, show
            for name in shown:
                assert red[panes[name]].sum() > 300, (show, name)
        p.assert_clean()


# ---- stage 4: parts lying on a face ------------------------------------------------------


def sideways_build(catalog: Catalog) -> tuple[Build, list[tuple[Placement, Placement]]]:
    """Four bricks with a stud on one side, turned to each face, each with a detail on that
    stud: a black round tile on the front, a round plate on the right (its stud outwards), a
    1 x 1 tile on the left and a round tile on the back."""
    from bricksnap.types import FACE_OUT

    pairs = []
    for i, (face, part) in enumerate(
        (("front", "98138"), ("right", "6141"), ("left", "3070b"), ("back", "98138"))
    ):
        bx, by = 2 + 4 * i, 2
        brick = replace(catalog.side_stud_brick(face, 71, bx, by, 0), step=1)
        ox, oy = FACE_OUT[face]
        pairs.append((brick, Placement(part, 0, bx + ox, by + oy, 0, 0, 2, face)))
    return Build((16, 5, 3), [q for pair in pairs for q in pair]), pairs


@pytest.mark.browser
def test_a_part_on_a_face_lies_on_its_bricks_side_stud(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """A part with a face is drawn on its side as bricksnap.ldraw places it: flat against its
    brick's face, one plate (3.2 mm) thick out of the face, one stud across, centred on the
    side stud 5.6 mm above the bottom of its column; no stud on top, and a round plate's stud
    points outwards. The step slider shows the bricks before the details."""
    from bricksnap.types import FACE_OUT

    build, pairs = sideways_build(catalog)
    with viewing(browser, tmp_path / "side", pawn_path, build) as (p, _):
        drawn = p.inspect()
        bodies = {b["entry"]: b for b in drawn["bodies"]}
        for k, (_brick, detail) in enumerate(pairs):
            body = bodies[2 * k + 1]
            assert body["face"] == detail.face and bodies[2 * k]["face"] == "top"
            lo, hi = _box(body)
            blo, bhi = _box(bodies[2 * k])
            ox, oy = FACE_OUT[detail.face]
            axis = 0 if ox else 1
            sign = ox or oy
            size = hi - lo
            # one plate thick out of the face (less the gap), one stud across and up
            assert size[axis] == pytest.approx(3.2 - 0.2, abs=0.05), (detail.face, size)
            assert size[1 - axis] == pytest.approx(8 - 0.4, abs=0.05)
            assert size[2] == pytest.approx(8 - 0.4, abs=0.05)
            assert (lo[2] + hi[2]) / 2 == pytest.approx(5.6, abs=0.05)  # on the side stud
            # against the brick's face, on the side the face points to
            face_at = bhi[axis] if sign > 0 else blo[axis]
            inner = lo[axis] if sign > 0 else hi[axis]
            assert abs(inner - face_at) < 0.5, (detail.face, inner, face_at)
            assert sign * ((lo[axis] + hi[axis]) / 2 - face_at) > 0
            # inside its column of three cells
            col_lo = np.array([detail.x, detail.y, 0]) * CELL_MM
            assert (lo >= col_lo - 1e-3).all() and (hi <= col_lo + [8, 8, 9.6]).all()
        # studs: one on top of each brick, and the round plate's, pointing out of the right face
        assert len(drawn["studs"]) == 5
        plate_hi = _box(bodies[3])[1][0]
        side = [s for s in drawn["studs"] if s["min"][2] < 9]
        assert len(side) == 1
        slo, shi = _box(side[0])
        assert slo[0] == pytest.approx(plate_hi + 0.1, abs=0.2) and shi[0] - slo[
            0
        ] == pytest.approx(1.7, abs=0.05)
        p.view_pixels("sideways")
        # the step slider: the bricks first, then the details
        assert p.state()["maxStep"] == 2
        p.page.locator("#step").fill("1")
        p.settle()
        assert p.state()["visibleCount"] == 4
        assert {b["face"] for b in p.inspect()["bodies"]} == {"top"}
        p.page.locator("#all").click()
        p.settle()
        assert p.state()["visibleCount"] == 8
        p.assert_clean()


# ---- versions and looking inside ----------------------------------------------------------


def test_project_files_lists_the_versions(running: Running, project: Project) -> None:
    from bricksnap import versions

    (project.path / "versions").mkdir()
    (project.path / "versions" / "index.json").write_text("{not json")
    assert json.loads(running.request("/project-files.json")[2])["versions"] == []
    entry = {"n": 1, "kind": "converted", "label": "First", "note": "", "created": "x",
             "parts": 2, "valid": True, "design_id": "abc", "brief": None}  # fmt: skip
    (project.path / "versions" / "0001").mkdir()
    (project.path / "versions" / "0001" / "build.json").write_text("{}")
    (project.path / "versions" / "index.json").write_text(
        json.dumps({"current": 1, "last": 1, "versions": [entry]})
    )
    listed = json.loads(running.request("/project-files.json")[2])
    assert listed["current"] == 1 and versions.current(project) == 1
    assert listed["versions"] == [{**entry, "build": "versions/0001/build.json", "card": None}]
    status, _, body = running.request("/project/versions/0001/build.json")
    assert status == 200 and body == b"{}"


@pytest.mark.browser
def test_versions_side_by_side_and_looking_inside(
    browser: Any, tmp_path: Path, pawn_path: Path, catalog: Catalog
) -> None:
    """``bricksnap view`` on a hollow model with two versions and no plain conversion: the
    choosers start on the version before the current one beside the current one, follow a
    choice, and the "look inside" control cuts both views open."""
    from bricksnap import versions
    from bricksnap.design import apply_ops
    from bricksnap.pipeline import create_project, rebuild

    proj = create_project(pawn_path, studs=10, directory=tmp_path, name="Hollow", hollow=True)
    rebuild(proj)
    versions.record(proj, "converted", "Converted from pawn.stl")
    design = proj.load_design()
    paint = {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [20, 20, 4]}}
    assert all(r.applied for r in apply_ops(design, [{**paint, "color": RED}], catalog))
    proj.save_design(design)
    proj.meta["brief"] = {"object": "A hollow pawn.", "plan": "A red base."}
    proj.save_meta()
    rebuild(proj)
    versions.record(proj, "pass", "Pass 1: the main shapes")
    r = Running(proj.path)
    p = Page(browser, r.url, width=1100, height=900)
    try:
        p.open()
        page = p.page
        assert page.locator("#choose").is_visible()
        got = page.evaluate("() => window.__bricksnap.choice")
        assert got == {"left": 1, "right": 2}
        assert p.text("#roughTag .pane-title") == "Converted from pawn.stl"
        assert p.text("#designedTag .pane-title") == "Pass 1: the main shapes"
        assert p.text("#designedTag .pane-what") == "Version 2 (in use) · "
        assert p.text('#compare button[data-show="designed"]') == "Right"
        assert p.text("#stepsFor") == "The steps are for version 2."
        assert page.locator("#brief").is_visible() and "A red base." in p.text("#brief")
        options = page.locator("#pickRight option").all_text_contents()
        assert options == ["2 · Pass 1: the main shapes (in use)", "1 · Converted from pawn.stl"]
        assert page.locator('#pickLeft option[value="rough"]').count() == 0  # none kept
        views = p.inspect()["views"]
        assert views["rough"]["shown"] and views["designed"]["shown"]
        assert p.state()["partCount"] == views["designed"]["partCount"]
        p.settle()
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / "versions-view.png"), full_page=True)

        # the right view follows the chooser, and so do the steps and the brief
        page.select_option("#pickRight", "1")
        page.wait_for_function("window.__bricksnap.choice.right === 1")
        p.settle()
        assert page.locator("#brief").is_hidden()  # version 1 had no brief
        assert p.text("#designedTag .pane-title") == "Converted from pawn.stl"
        assert p.inspect()["compare"]["active"] is False  # the same build on both sides
        page.select_option("#pickRight", "2")
        page.wait_for_function("window.__bricksnap.choice.right === 2")

        # look inside: off at first, then a cut from the front through both views
        assert page.evaluate("() => window.__bricksnap.cut") == {
            "axis": "y", "amount": 0, "plane": None, "clipped": 0
        }  # fmt: skip
        whole = p.view_pixels()
        page.eval_on_selector(
            "#cut", "e => { e.value = '50'; e.dispatchEvent(new Event('input')); }"
        )
        cut = page.evaluate("() => window.__bricksnap.cut")
        assert cut["amount"] == 0.5 and cut["clipped"] >= 4 and cut["plane"][:3] == [0, 1, 0]
        assert "50% of the way, from the front" in p.text("#cutSays")
        opened = p.view_pixels()
        page.screenshot(path=str(ARTIFACTS / "versions-look-inside.png"))
        assert np.abs(opened - whole).sum(axis=2).astype(bool).mean() > 0.02
        page.select_option("#cutAxis", "z")
        assert page.evaluate("() => window.__bricksnap.cut.plane")[:3] == [0, 0, -1]
        page.eval_on_selector(
            "#cut", "e => { e.value = '0'; e.dispatchEvent(new Event('input')); }"
        )
        assert page.evaluate("() => window.__bricksnap.cut.clipped") == 0
        p.assert_clean()
    finally:
        p.close()
        r.close()
