"""The web app: use BrickSnap from a browser, with no terminal.

``uv run bricksnap serve`` starts a small server on this computer and opens a page where a
person can choose a model file, watch it become a brick build, see the plain conversion next
to the designed build, start the AI designer, ask for a change in words, and download the
files. Everything it does goes through ``bricksnap.pipeline`` and the same functions the
command line uses: this module holds no modelling logic of its own.

CONTRACT (tests go in tests/test_webapp.py; browser tests there too, marked ``browser``)

``make_app_server(projects_dir="projects", port=8765) -> ThreadingHTTPServer`` and
``serve_app(projects_dir="projects", port=8765, open_browser=True) -> None``, in the manner
of ``bricksnap.viewserver`` (Python's standard library only; bound to 127.0.0.1 only;
``port=0`` picks a free port).

Pages (GET)
    /                         the home page: the projects in ``projects_dir`` as cards (name,
                              picture, part count, valid or not), newest first, and a form to
                              start a new one
    /p/<project>              one project: the 3D viewer page as ``bricksnap view`` shows it
                              (plain conversion beside the designed build, the brief, what the
                              software changed, the step slider), with the actions below added
    /viewer/..., /catalog/... as in ``bricksnap.viewserver``
    /p/<project>/files/<file> the project's files, read-only, as ``/project/<file>`` there

Actions (POST, JSON in and out unless said otherwise). Each returns at once; anything that
takes more than a moment returns ``{"job": id}``.
    /api/projects                    multipart form: ``model`` (the file), ``studs`` (4 to 96,
                                     default 16), ``name`` (optional), ``hollow`` (optional).
                                     Converts and builds. Job result: ``{"project": slug}``.
    /api/p/<project>/build           rebuild from the current design
    /api/p/<project>/design          ``{"request": "add a red collar"}`` or ``{}`` for a
                                     first design; ``{"best_of": 3}`` optional (2 to 5).
                                     Starts the AI designer (``runner.run_designer`` or
                                     ``judge.design_best_of``). Refused with a plain message
                                     unless the body also has ``"understood": true``: the page
                                     sets it only after the person has read and accepted that
                                     this step sends pictures and a description of the model to
                                     the AI provider, how many AI runs it starts, and that it
                                     uses their own Claude Code login.
    /api/p/<project>/export          writes build.ldr, parts.csv and wanted_list.xml
    /api/p/<project>/instructions    writes instructions.pdf and instructions.html
    /api/p/<project>/delete          moves the project folder into ``projects_dir/.trash``
                                     (nothing is ever deleted outright)
GET /api/projects                    the list the home page shows
GET /api/p/<project>                 name, studs, part count, verdict, notes, brief, which
                                     files exist, whether the build is current, running job
GET /api/jobs/<id>                   ``{"state": "waiting" | "running" | "done" | "failed",
                                     "kind", "project", "started", "progress": [plain
                                     sentences, newest last], "result", "error"}``

Jobs
- One job runs at a time per project; a second request for the same project while one runs
  is refused with a plain message naming what is running. Different projects may run side
  by side, but only one AI job at a time for the whole server.
- A job's progress lines are plain sentences a person can read ("Reading cat.glb", "Laying
  out the bricks", "The designer is looking at the model", "The designer changed the design
  (3 edits)", "Judging the three designs"). For AI jobs they come from the runner's
  ``on_event`` hook; no model text is shown before it has passed ``runner.redact``.
- A failed job says why in plain words (the same messages the command line prints for the
  same mistakes), never a traceback. The server never dies because a job did.
- Jobs live in memory; when the server stops they are gone, and whatever a job had already
  written to the project folder stays, as with the command line.

Safety. This server acts for whoever can reach it, so:
- It listens on 127.0.0.1 only and answers only requests whose Host header names this
  computer, exactly as ``viewserver`` does.
- Every POST must carry the header ``X-BrickSnap-Token`` with the token the server made at
  start-up and put into the pages it serves, and must not carry an ``Origin`` header naming
  another site. A web page on another site therefore cannot start anything, even though it
  can reach this address. A POST without the token is refused and changes nothing.
- An uploaded file is untrusted. At most 60 MB (larger is refused with a plain message
  before it is read to the end); only .stl, .obj, .glb, .gltf, .3mf and .ply; saved under a
  name the server chooses; the project's folder name is ``project.slug`` of the given name
  (or of the file's stem) made unique with a number, never a path from the browser.
- ``<project>`` in an address is one path component matching the slug pattern, resolved
  inside ``projects_dir`` and nowhere else; ``.trash`` and anything starting with a dot is
  never served.
- Text from files, from the person and from the AI goes into pages with ``textContent``.
- Nothing is fetched from the internet by the pages. Only the design action sends anything
  off this computer, and only through the clean-room runner.

The pages
- Plain JavaScript modules and CSS in ``viewer/`` beside the viewer's own (no build step, no
  framework): ``home.html`` with ``home.js``, and the project page, which is the viewer page
  with an action bar (``app.js``) when it is served by this server.
- Written for people who do not program: one clear next step on every screen, plain words,
  what is happening while a job runs (the progress lines, newest first, and that it is safe
  to leave the page), and what to do when something fails.
- The home page works at phone width. The LEGO trademark line is on every page.

The command line gains ``bricksnap serve [--port N] [--dir FOLDER] [--no-open]`` (the lead
wires it in; ``serve_app`` is all it needs).
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
from pathlib import Path

MAX_UPLOAD_BYTES = 60 * 1024 * 1024
MODEL_SUFFIXES = (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply")


def make_app_server(projects_dir: str | Path = "projects", port: int = 8765) -> ThreadingHTTPServer:
    raise NotImplementedError


def serve_app(
    projects_dir: str | Path = "projects", port: int = 8765, open_browser: bool = True
) -> None:
    raise NotImplementedError
