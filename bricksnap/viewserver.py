"""A tiny local web server for the 3D viewer page. Python standard library only.

CONTRACT (tests go in tests/test_viewer.py)

``make_server(project_path, port=8765) -> http.server.ThreadingHTTPServer`` bound to
127.0.0.1 only (``port=0`` picks a free port). Routes, all GET and read-only:

    /                      -> viewer/index.html
    /viewer/<file>         -> files under the repository's viewer/ folder
    /project/<file>        -> files under the project folder (build.json, project.json, renders/...)
    /catalog/parts.json    -> bricksnap/catalog/parts.json
    /catalog/colours.json  -> bricksnap/catalog/colours.json
    /project-files.json    -> {"files": [...]}: which of project.json, build.json and
                              build.rough.json exist in the project folder, in that order

A requested path is resolved and must stay inside its root folder, including when it uses
"..", percent-encoding, backslashes or an absolute path; anything else is 404. (The
prototype's server had no such check.) Content types are set for html, js, css, json, png
and svg. Responses carry "Cache-Control: no-store" so a rebuilt project shows immediately.

``serve(project_path, port=8765, open_browser=True) -> None`` starts the server, prints the
address, optionally opens the browser, and runs until interrupted.

STAGE 2 ADDITION TO THE CONTRACT: real part shapes in the 3D viewer

The page draws each part by its catalogue ``kind`` (parts.json already carries ``kind``,
``studs_top`` and, for slopes, ``slope.low_side``):
- "slope", "curved_slope": a wedge, full height over the stud cells and running down to a
  low lip over the slanted cells, towards the part's low side as turned by ``rot`` (the
  rotation table in bricksnap/catalog/__init__.py; ``Catalog.low_side`` is the reference).
- "slope_inverted": the wedge upside down.
- "tile": flat, no studs.
- "round_brick", "round_plate", "round_tile", "dish", "cone": round (a cylinder; a cone
  tapers). Studs as the catalogue says.
- every other kind: a box with studs, as before.
``window.__bricksnap.inspect()`` reports, for each drawn part, its kind and, for wedges, the
world direction its face runs down, so the tests can compare with ``Catalog.low_side``.
The page also shows ``build.json``'s ``notes`` (what the make-buildable and finishing passes
did) as a short list under the verdict, written with ``textContent``.

STAGE 3 ADDITION TO THE CONTRACT: the plain conversion and the designed build side by side
- ``/project/build.rough.json`` is the plain conversion, when the project kept one. When it
  exists and differs from ``build.json``, the page shows two views side by side (one above
  the other on a narrow screen): "Plain conversion" and "Designed", each with its part
  count, turning and zooming together as one camera. A control shows both, or either one
  alone; the choice survives a rebuild. The step slider acts on the designed build. With no
  rough build, or one equal to the build, the page is exactly as before.
- The brief. When ``project.json`` has a "brief" (object, features, plan, colours, finish),
  the page shows it in a panel: the object sentence, the features as a list, the plan and
  the finish, and the colours as small swatches with their names from colours.json. All
  written with ``textContent``. No brief, no panel.
- ``window.__bricksnap.inspect()`` reports each view (its parts, as now) and that they share
  one camera, so the tests can check both without reading pixels.
- Tests, with screenshots in tests/artifacts/: a project with both builds; with only one;
  with and without a brief; at phone width; and that turning one view turns the other.

Implementation notes
--------------------
- The query string and fragment are ignored (the page adds ``?t=...`` to defeat caches).
- The path is percent-decoded once. After decoding, a path containing a backslash, a NUL
  byte, an empty, "." or ".." segment, or a segment that looks like a Windows drive ("C:")
  is refused outright; the remaining path is then resolved (following symlinks) and must
  still lie inside its root folder and be a regular file. Every refusal is a plain 404.
- HEAD is answered like GET without the body. Other methods get 405.
- Only requests whose Host header names this computer (127.0.0.1, localhost or [::1], with
  any port) are answered; any other Host, or none, gets 404. This stops a web page open in
  another tab from reading the project through DNS rebinding (pointing its own host name at
  127.0.0.1).
- A browser tab closed or reloaded while a file is being sent breaks the connection; the
  server ignores that quietly instead of printing a traceback. Other errors still print.
- Errors the user can cause (missing folder, a port that is not a whole number from 0 to
  65535, port already in use) raise ``ProjectError`` with a plain-language message, which the
  command line prints without a traceback.

Implementation notes: part shapes and notes (viewer/viewer.js)
--------------------------------------------------------------
- Each shape is one shared unit geometry (box, wedge, curved wedge, inverted wedge, cylinder,
  cone, dish) drawn with one instanced mesh per colour and shape, scaled to the part's cells
  less the small gap, turned about z and moved into place. A 3,000-part build is about 50
  meshes. A wedge's geometry runs down towards its own +x; the instance turns that to the
  grid direction given by ``slope.low_side`` and ``rot`` through the same table as
  ``Catalog.low_side``. A turn outside 0/90/180/270 falls back to a box.
- Wedge profile: full height over the rows (along the slope) that have studs, slanted over
  the others, ending in a 1.6 mm (4 LDU) lip, as real slope bricks do. A slope without studs
  (the 1 x 1 and 1 x 2 31-degree slopes, the curved slope) slants over its whole length. An
  inverted slope stands on the rows its ``bottom_cells`` name and is cut away over the rest,
  its thin edge at the top on the side away from ``low_side``. Without that data the slanted
  length comes from ``slope.angle_deg``. The curved slope's top is a curve, gentle near
  the top and steeper towards the lip.
- Round kinds are 32-sided cylinders as wide as their cells. A cone's top is 0.68 of its
  base (a stud fits on it). The dish widens upwards from a foot 0.55 of its rim. Studs are
  only those in ``studs_top``: the dish's off-grid centre stud is not drawn, and the corner
  studs of a 2 x 2 round brick stick out of its sides a little, as the cells say.
- Edge lines come from each shape's own outline (three.js EdgesGeometry), so a wedge shows its
  slope edge and a cylinder its rims. The current step's highlight is the part's own shape,
  grown by 0.7 mm and drawn inside-out.
- ``inspect()`` gives each body ``part``, ``entry`` (its index in build.json's "parts"),
  ``kind``, ``shape``, ``top`` and ``bottom`` (the x-y extent of the flat top and bottom
  faces, or null when that face is only an edge), and ``downhill`` for wedges. ``downhill``
  is worked out from the drawn faces, not copied from the catalogue: the sum of the slanted
  faces' normals is taken into the world, and a face that looks down (an inverted slope's
  underside) counts the other way. ``meshCount`` is the number of objects drawing the model.
  So the tests measure the drawn shapes rather than trust a label, each body also gives
  ``topRim`` and ``bottomRim`` (how many corners the face's rim has, and how far it reaches
  from its centre along the grid diagonal: a radius for a round face, 1.41 times the
  half-width for a square one) and ``edges`` (how many line ends its edge lines have);
  each highlight outline gives its box, ``topRim`` and ``downhill``, measured on the geometry
  that outline really draws. ``inspect({detail: true})`` adds slower measurements:
  ``edgeBox`` and ``edgeGap`` (the box the part's edge lines cover, and how far any line end
  lies from the drawn body), and for upright wedges ``slope``, the heights of the drawn
  slanted face near its top, half way down and near its lip, found by casting a ray down
  onto the part. ``camera`` gives the camera's position and the point it looks at.
- Notes: only non-empty strings are shown. Up to three appear as a list under the heading
  "What the software changed"; more are folded into a ``<details>`` whose summary reads
  "What the software changed (N)". A rebuild keeps it open if the person opened it.
  ``window.__bricksnap.notes`` holds the notes shown.
- Framing: the camera looks from the front-right and above. It moves as close as it can while
  the parts' own corners stay within 88% of the way to the view's edges and the corners of
  the box around the model (at least 4 x 4 x 3 cells) stay inside the view. The point it
  looks at is shifted so the picture sits in the middle. A 16 x 16 stud model now fills
  about 85% of the view's height, where it used to fill about 40%. Resizing the window
  frames the model again until the person turns or zooms it; after that, only turning a
  phone between portrait and landscape does. A rebuild frames it again only when the box
  round the parts changes; once the person has turned the view, framing again (after a
  rebuild or turning a phone) keeps their viewing direction and changes only the distance
  and the point looked at, so live reload during design edits does not snap the view back.

Implementation notes: before and after, and the brief (viewer/viewer.js)
------------------------------------------------------------------------
- Each poll the page reads build.json, project.json and ``/project-files.json``, and asks for
  build.rough.json only when that list names it, so a project without one causes no failed
  requests (a 404 shows as an error in the browser's console). What changed is drawn again;
  a change to project.json alone (a new brief) shows without a rebuild. A build.rough.json
  that cannot be read or drawn, or has no part in it to draw, counts as none: the page shows
  one view, and says nothing, since the plain conversion is extra. "Equal to the build"
  means the same "parts" list.
- One canvas, one renderer, one camera, one set of lights, ground and grid. Each build is
  drawn into its own group by the same code; when both are shown, the canvas draws each
  view's group in turn inside its pane's frame (scissor), with the camera's aspect set to
  that pane. Turning, zooming or moving either view therefore moves both, and the camera is
  framed (as above) on the box round both builds, so they sit at the same scale whichever is
  shown. The part shapes, the stud, and one material per colour (plus the edge, highlight
  and outline materials) are shared by both views and every rebuild; a rebuild frees only
  the instanced meshes and edge lines of the view it replaces. Two views cost exactly what
  the two builds cost drawn alone, added up: one pass each, the same draw calls and
  triangles. A build is drawn with one body mesh and one stud mesh per colour, two edge-line
  objects and one highlight outline per shape: 600 bricks of one shape in three colours
  beside 600 of another in two take 9 + 7 = 16 meshes.
- Camera: picking what to show (Both, or one build alone) never moves a view the person has
  turned, zoomed or moved, though one view alone is wide and two side by side are tall;
  until they have, the model is framed again for the new shape.
- Layout: the panes are flex boxes inside the view (a row; a column at 700 px wide or less,
  where the view grows to 88% of the screen's height). Each pane's sky is under the canvas,
  its frame and name tag above it and let the mouse through. The name tags read "Plain
  conversion" / "What a plain converter makes" and "Designed" / "What BrickSnap made of it",
  each with its part count; on a narrow screen only the name and the count, on one line.
  The control above the views reads "Show: Both, Plain conversion, Designed". Under the step
  slider, "The steps are for the designed build." is shown while the plain conversion is.
  The hint under the views reads "Drag either view to turn both ..." while both are shown.
  The header's part count, verdict and notes are the designed build's. With one view, the
  page is as before: no control, no tags, no frames, no note.
- The brief panel: "The designer's brief", the object sentence, "What makes it
  recognisable" (the features), "The plan", "Colours" (a swatch and the colour's name from
  colours.json, underscores as spaces; a code the catalogue lacks shows as "Colour N" with
  a dashed grey swatch) and "Finish". Empty or wrongly typed fields are left out; an older
  brief written as one string is shown as one paragraph. On screens 1280 px wide or more it
  stands beside the views (the page widens to 1560 px); narrower, it comes after the steps.
- ``inspect()`` keeps its old fields for the designed build and adds ``views`` (per view:
  label, shown, partCount, bodies, studs, outlines, ndc, meshCount, rect in page pixels,
  the camera it was last drawn with, and the ids of the materials and geometries its parts
  use), ``sharedCamera`` (every shown view was last drawn with the one camera, from the same
  place) and ``compare`` ({active, show}). ``frame`` lists the renderer's passes in the
  last frame drawn, each recorded by the scene as the pass ended (so a pass from anywhere
  counts): ``groups`` (the views whose build was visible), ``viewport`` and ``scissor`` (the
  canvas area drawn and the scissor box, [x, y, width, height] in page pixels; scissor null
  when off), ``aspect`` (the camera's shape, read from its projection), ``camera`` (its id),
  and ``calls`` and ``triangles`` (what that pass drew, shadows included; the renderer's
  counts are reset once per frame). The tests compare these with the panes, and colours in
  the picture with the panes, so a view drawn in the wrong place, stretched, or showing the
  other build is caught. ``window.__bricksnap.brief`` holds the brief shown and
  ``roughVersion`` goes up whenever build.rough.json changes.
  ``timeFrames(n)`` draws every shown view n times, waiting for each frame, and returns the
  milliseconds per frame. In the headless test browser, which draws in software, two
  600-part builds take about 0.45 s a frame, the designed one alone 0.3 s and the plain one
  alone 0.17 s; a graphics card is far faster.

STAGE 4 ADDITION TO THE CONTRACT: versions, and looking inside
- ``/project-files.json`` also gives ``versions`` (``bricksnap.versions``, oldest first: each
  ``{"n", "kind", "label", "note", "created", "parts", "valid", "design_id", "brief",
  "build", "card"}``, where ``build`` and ``card`` are the version's files relative to the
  project folder, ``card`` null when it has none) and ``current`` (the current version's
  number, or null). A project without versions, or whose index cannot be read, gives an
  empty list and null. ``version_entries(folder)`` makes both.
- With versions, the page gets two choosers above the views. The left view shows the plain
  conversion (when the project has one) or any version; the right view any version, the
  current one by default, which is drawn from build.json itself so it follows a rebuild as
  before. When there is no plain conversion the left view starts on the version before the
  current one. A chooser left on its default follows the model (a new current version is
  shown on the right); one the person set keeps their choice while that version exists.
  The titles and what is under them, the Show buttons, the part counts, the header (count,
  verdict, notes), the step slider and the brief panel (the brief the right-hand version
  had; hidden when it had none) follow the right view. When the right view shows build.json
  but that build is not the current version's (a run that is still changing it), its title
  says it is the model now, not kept as a version yet. Two views appear whenever the two
  choices draw different builds. Without versions the page is exactly as before.
- "Look inside": a slider under the steps cuts both views away along one axis (from the
  front by default; from the side or from the top), with three.js clipping planes on the
  model's materials only (the ground and grid stay whole), cut parts drawn from both sides.
  At 0 nothing is cut, which is how the page starts.
- ``window.__bricksnap`` adds ``versions`` and ``current`` (as listed), ``choice``
  (``{left, right}``: "rough", a version number, or null for none), ``choose(side, value)``
  (pick a version for "left" or "right", or "rough"/"default"; resolves once it is drawn),
  ``cut`` ({axis, amount (0 to 1), plane: [nx, ny, nz, constant] or null, clipped: how many
  model materials carry it}) and ``setCut(amount, axis)``.
"""

from __future__ import annotations

import errno
import json
import socket
import sys
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from bricksnap.project import ProjectError

REPO_ROOT = Path(__file__).resolve().parent.parent
VIEWER_DIR = REPO_ROOT / "viewer"
CATALOG_DIR = REPO_ROOT / "bricksnap" / "catalog"
CATALOG_FILES = ("parts.json", "colours.json")
PROJECT_FILES = ("project.json", "build.json", "build.rough.json")
"""The project files the page reads; ``/project-files.json`` says which of them exist."""
FILES_ROUTE = "/project-files.json"
LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]"})

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".md": "text/plain; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
    ".ldr": "text/plain; charset=utf-8",
}


def content_type(path: Path) -> str:
    """The Content-Type header for a file, by its extension."""
    return CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")


def safe_join(root: Path, relative: str) -> Path | None:
    """The file ``relative`` (already percent-decoded, "/"-separated) inside ``root``.

    Returns None when the path is unsafe or does not name an existing regular file inside
    ``root`` after resolving symlinks.
    """
    if not relative or "\\" in relative or "\x00" in relative or relative.startswith("/"):
        return None
    parts = relative.split("/")
    for part in parts:
        if part in ("", ".", ".."):
            return None
        if len(part) >= 2 and part[1] == ":":  # a Windows drive such as "C:"
            return None
    try:
        base = root.resolve()
        target = base.joinpath(*parts).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    if not target.is_relative_to(base) or not target.is_file():
        return None
    return target


def is_local_host(host: str | None) -> bool:
    """True when a Host header value names this computer, with or without a port."""
    if not host:
        return False
    host = host.strip().lower()
    if host.startswith("["):  # an IPv6 address such as [::1]:8765
        name, _, rest = host.partition("]")
        name += "]"
        if rest and not (rest.startswith(":") and rest[1:].isdigit()):
            return False
    else:
        name, colon, port = host.partition(":")
        if colon and not port.isdigit():
            return False
    return name in LOCAL_HOSTS


def version_entries(project_root: Path) -> tuple[list[dict[str, Any]], int | None]:
    """The project's versions as ``/project-files.json`` lists them, and the current one."""
    from dataclasses import asdict

    from bricksnap import versions
    from bricksnap.project import Project

    try:
        project = Project(project_root)
        found, now = versions.versions(project), versions.current(project)
    except (OSError, ValueError, TypeError, AttributeError):
        return [], None
    entries = []
    for v in found:
        folder = f"{versions.VERSIONS_DIR}/{v.n:04d}"
        card = f"{folder}/card.png"
        entries.append(
            {
                **asdict(v),
                "build": f"{folder}/build.json",
                "card": card if safe_join(project_root, card) is not None else None,
            }
        )
    return entries, now


def project_files(project_root: Path) -> bytes:
    """The body of ``/project-files.json``: which of ``PROJECT_FILES`` exist as files, and
    the project's versions."""
    found = [name for name in PROJECT_FILES if safe_join(project_root, name) is not None]
    entries, now = version_entries(project_root)
    return json.dumps({"files": found, "versions": entries, "current": now}).encode("utf-8")


def resolve_route(url_path: str, project_root: Path) -> Path | None:
    """The file a request path maps to, or None for 404. ``url_path`` may carry a query."""
    raw = urlsplit(url_path).path
    if "\\" in raw:
        return None
    path = unquote(raw, errors="strict") if "%" in raw else raw
    if path in ("", "/", "/index.html"):
        return safe_join(VIEWER_DIR, "index.html")
    for prefix, root in (("/viewer/", VIEWER_DIR), ("/project/", project_root)):
        if path.startswith(prefix):
            return safe_join(root, path[len(prefix) :])
    if path.startswith("/catalog/"):
        name = path[len("/catalog/") :]
        if name in CATALOG_FILES:
            return safe_join(CATALOG_DIR, name)
    return None


def _make_handler(project_root: Path) -> type[BaseHTTPRequestHandler]:
    class ViewerHandler(BaseHTTPRequestHandler):
        server_version = "BrickSnapViewer/1"
        sys_version = ""

        def _send_headers(self, status: int, ctype: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()

        def _not_found(self, body: bool) -> None:
            data = b"Not found\n"
            self._send_headers(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", len(data))
            if body:
                self.wfile.write(data)

        def _serve(self, body: bool) -> None:
            target = None
            local = is_local_host(self.headers.get("Host"))
            if local and urlsplit(self.path).path == FILES_ROUTE:
                data = project_files(project_root)
                self._send_headers(HTTPStatus.OK, CONTENT_TYPES[".json"], len(data))
                if body:
                    self.wfile.write(data)
                return
            if local:
                try:
                    target = resolve_route(self.path, project_root)
                except (UnicodeDecodeError, ValueError):
                    target = None
            if target is None:
                self._not_found(body)
                return
            try:
                data = target.read_bytes()
            except OSError:
                self._not_found(body)
                return
            self._send_headers(HTTPStatus.OK, content_type(target), len(data))
            if body:
                self.wfile.write(data)

        def do_GET(self) -> None:  # name fixed by http.server
            self._serve(body=True)

        def do_HEAD(self) -> None:
            self._serve(body=False)

        def _refuse(self) -> None:
            data = b"Method not allowed\n"
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "GET, HEAD")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse

        def log_message(self, format: str, *args: object) -> None:
            pass  # keep the terminal quiet; the page polls every two seconds

    return ViewerHandler


class ViewerServer(ThreadingHTTPServer):
    """The viewer's server: one thread per request, quiet about closed browser tabs."""

    daemon_threads = True

    def handle_error(
        self, request: socket.socket | tuple[bytes, socket.socket], client_address: Any
    ) -> None:
        if isinstance(sys.exc_info()[1], ConnectionError):
            return  # BrokenPipe, ConnectionReset, ConnectionAborted: the tab went away
        super().handle_error(request, client_address)


def _port_number(port: object) -> int:
    """``port`` as an int from 0 to 65535 (a string of digits is accepted too)."""
    if isinstance(port, int) and not isinstance(port, bool):
        number = port
    elif isinstance(port, str) and port.strip().isdigit():
        number = int(port.strip())
    else:
        number = -1
    if not 0 <= number <= 65535:
        raise ProjectError(
            f"The port must be a whole number from 0 to 65535, not {port!r}. "
            "Choose another one with --port."
        )
    return number


def make_server(project_path: str | Path, port: int = 8765) -> ThreadingHTTPServer:
    project_root = Path(project_path)
    if not project_root.is_dir():
        raise ProjectError(f"Cannot find the project folder {project_root}.")
    number = _port_number(port)
    handler = _make_handler(project_root.resolve())
    try:
        server = ViewerServer(("127.0.0.1", number), handler)
    except (OverflowError, ValueError):
        raise ProjectError(
            f"The port must be a whole number from 0 to 65535, not {port!r}."
        ) from None
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise ProjectError(
                f"Port {port} is already in use, perhaps by another viewer. "
                "Close it or choose another port with --port."
            ) from None
        raise ProjectError(f"Could not start the viewer on port {port}: {exc.strerror}.") from None
    return server


def serve(project_path: str | Path, port: int = 8765, open_browser: bool = True) -> None:
    server = make_server(project_path, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"BrickSnap viewer for {Path(project_path)} is running at {url}")
    print("Press Ctrl+C to stop it.")
    sys.stdout.flush()
    if open_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nViewer stopped.")
    finally:
        server.server_close()
