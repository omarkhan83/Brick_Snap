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
import socket
import struct
import threading
import time
from collections.abc import Generator, Iterator
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

    def inspect(self) -> dict[str, Any]:
        """What the page draws now, in world millimetres (see state.inspect in viewer.js)."""
        return self.page.evaluate("() => window.__bricksnap.inspect()")

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
