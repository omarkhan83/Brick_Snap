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
                                     unless the body also has ``"understood": true`` and
                                     ``"understood_runs"``, the number of AI runs the person was
                                     shown (1, or ``best_of`` + 1 with a judge): the page sets
                                     them only after the person has read and accepted that
                                     this step sends pictures and a description of the model to
                                     the AI provider, how many AI runs it starts, and that it
                                     uses their own Claude Code login. Changing the number of
                                     designs on the page takes the agreement back.
    /api/p/<project>/export          writes build.ldr, parts.csv and wanted_list.xml
    /api/p/<project>/instructions    writes instructions.pdf and instructions.html
    /api/p/<project>/delete          moves the project folder into ``projects_dir/.trash``
                                     (nothing is ever deleted outright)
    /api/p/<project>/restore         ``{"version": n}``: brings version n back
                                     (``versions.restore``), after keeping the model as it
                                     is now in the list. Job result: ``{"project", "parts",
                                     "valid", "version"}``.
GET /api/projects                    the list the home page shows
GET /api/p/<project>                 name, studs, part count, verdict, notes, brief, which
                                     files exist, whether the build is current, running job,
                                     and the model's versions
GET /api/jobs/<id>                   ``{"state": "waiting" | "running" | "choosing" |
                                     "done" | "failed", "kind", "project", "started",
                                     "progress": [plain sentences, newest last], "result",
                                     "error"}`` ("choosing": see the pieces, below)

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
- Any other user account on the same computer can reach the server too, and act through it
  with the files and the Claude Code login of the person who started it: run it only on a
  computer you do not share with other people while it runs.
- An uploaded file is untrusted. At most 60 MB (larger is refused with a plain message
  before it is read to the end); only .stl, .obj, .glb, .gltf, .3mf and .ply; saved under a
  name the server chooses; the project's folder name is ``project.slug`` of the given name
  (or of the file's stem) made unique with a number, never a path from the browser.
- ``<project>`` in an address is one path component matching the slug pattern, resolved
  inside ``projects_dir`` and nowhere else; ``.trash`` and anything starting with a dot is
  never served.
- Text from files, from the person and from the AI goes into pages with ``textContent``.
- Nothing is fetched from the internet by the pages. Only the design action (and the
  experimental AI builder below) sends anything off this computer, and only through the
  clean-room runner.

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

Implementation notes
--------------------
- ``make_app_server`` returns an ``AppServer`` (a ``ThreadingHTTPServer``, quiet about closed
  tabs like the viewer's) whose ``app`` holds the projects folder, the token and the jobs.
  A missing ``projects_dir`` is made; one that is a file, a bad port or a port in use is a
  ``ProjectError`` with a plain message, as for ``bricksnap view``.
- Routes besides those above: ``/p/<project>/project-files.json`` is the viewer's list of
  which of project.json, build.json and build.rough.json exist, as ``/project-files.json``
  is for ``bricksnap view``. The project page is ``viewer/index.html`` with the project's
  addresses put on ``<body>`` (``data-project-files``, ``data-project-list``; viewer.js falls
  back to ``/project/`` and ``/project-files.json`` without them, so ``bricksnap view`` is
  unchanged), the token in a ``<meta name="bricksnap-token">`` and ``app.css``/``app.js``
  added. The home page is ``viewer/home.html`` with the token put into its meta tag.
- ``GET /api/projects`` gives ``{"projects": [...], "jobs": [...]}``: the cards, and the jobs
  that are waiting or running, so a page opened again still shows a new model being made.
  A card has ``project`` (the folder name), ``name``, ``studs``, ``parts``, ``valid``,
  ``picture`` (an address, or null), ``updated`` (seconds since 1970: the newest of
  project.json and build.json, which orders the cards), ``job`` (the running job's id, or
  null) and ``problem`` (a plain sentence when project.json or build.json cannot be read).
  Folders whose names do not match the slug pattern, or with no project.json, are not listed.
- ``GET /api/p/<project>`` adds ``verdict`` (a plain sentence), ``notes``, ``brief``,
  ``files`` (which of build.ldr, parts.csv, wanted_list.xml, instructions.pdf,
  instructions.html and renders/compare.png exist), ``current`` and ``job`` (the running
  job, as ``/api/jobs/<id>`` gives it, or null).
- Every job, ``build`` included, also makes the plain conversion (``pipeline.rough_build``,
  reused while the base design is unchanged), so the project page shows "Plain conversion"
  beside "Designed" from the start; ``new`` and ``build`` also draw renders/compare.png, as
  the command line does. ``design`` rebuilds afterwards as ``bricksnap design`` does (an edit
  rebuilds before the run too); a best-of run keeps the winner's build. ``delete`` is quick
  and answers at once with ``{"deleted": slug, "moved_to": ".trash/<folder>"}``; a project
  whose job is running cannot be moved. ``best_of`` 1 is accepted and means one design.
- A job's id is random. Finished jobs are kept in memory (the newest 200). A refused action
  answers 400 (409 for a busy project or a running AI job, 404 for a project that is not
  there, 413 for a file that is too large) with ``{"error": "<plain message>"}``.
- A new project is made in ``projects_dir/.incoming/<job id>/`` from the upload, saved there
  as ``slug(file stem)`` plus its suffix, and moved into place once it has been read; the
  folder name is chosen when the request arrives (and again if a folder of that name
  appeared meanwhile) and is held by the job, so two uploads of cat.stl become ``cat`` and
  ``cat-2``. The project's name is the given name, or the file's name without its suffix, cut
  to 80 characters with control characters removed: it is only ever shown as text.
- Upload limits: a body whose Content-Length is more than 60 MB plus 1 MB for the form's
  other fields is refused before any of it is read; a body with no Content-Length is refused
  (411); the file is written to disk as it arrives and the upload is stopped as soon as it
  passes 60 MB; a file whose name does not end in an allowed suffix is refused as soon as its
  part's headers are read. The form's other fields may be at most 4 KB each. The multipart
  body is read by this module's own small parser (the ``cgi`` module is gone from Python
  3.13); its part headers are read with ``email``.
- POST checks, in order: the Host header (404), the Origin header (403), the token (403,
  compared in constant time). Every response carries ``X-Frame-Options: DENY`` and
  ``Content-Security-Policy: frame-ancestors 'none'``, so no other site can show a page in a
  frame and trick a click on its buttons; files under ``/p/<project>/files/`` also carry
  ``sandbox``, so an HTML file there cannot run scripts as this site. Under ``files/`` only
  what the pages use is served, judged on the file the address resolves to (after
  symlinks), case and all: project.json, build.json, build.rough.json, the downloads
  (build.ldr, parts.csv, wanted_list.xml, instructions.pdf, instructions.html) and
  ``renders/<name>.png``. Nothing else, so no AI transcript (``.jsonl``, which holds the
  account's e-mail address), no candidates and no seed. Raw paths holding ``%2F``, ``%5C``
  or ``%00`` are refused before decoding; the rest follows ``viewserver.safe_join``. An
  address for a project that is not there (moved to the bin, or mistyped) gets a short page
  that says so, with a link back to all the models.
- A refused request never touches the project: whether a project exists and whether it is
  busy is checked on its folder name alone, and only the job opens it (opening puts back an
  interrupted best-of run, which must not happen under a running one).
- Each connection waits at most 30 seconds (``REQUEST_TIMEOUT_S``) for the browser to send
  something, so an idle connection cannot hold a thread for ever.
- Plain messages: SeedError, ProjectError and the command line's own errors are shown as the
  command line prints them (without "Error: "), and an OSError through the command line's
  ``_system_error``, except that a sentence giving command-line advice ("Make it again
  with: uv run bricksnap build ...") is replaced by which button to press
  (``for_the_page``). A job that is refused (its project moved to the bin meanwhile) gives
  its plain message. Anything else is written with its traceback to standard error and the
  page gets a plain sentence saying that something went wrong inside BrickSnap; a job that
  stops in any other way is still marked failed.
- A .gltf file whose data is kept in separate files (a buffer ``uri`` that is not a
  ``data:`` address) is refused at upload with a message saying to export it as .glb.
- Downloads stay in step with the build: every job that changes the build writes the parts
  list and the wanted list again, and the instruction booklet too when the project had one
  (``App._refresh_downloads``), so a new model has them from the start and nobody orders
  the parts of an older build. One that cannot be written again is removed, and the
  progress says so. (Rebuilding with the command line does not do this.)
- Pictures: every job that changes the build also writes renders/card.png
  (``pipeline.render_card``), the picture on the project's card; a project without one
  shows renders/compare.png. ``serve_app`` draws the missing cards in the background when
  it starts (``App.make_missing_cards``), so models made with the command line get one too;
  ``make_app_server`` draws no cards (it only clears stale uploads, below).
  ``GET /api/p/<project>`` also gives ``bin``, the folder the project would be moved to,
  as the person would find it.
- Progress from the designer: the run starting, each tool call in words (``describe``,
  ``render``, ``brief``, ``rebuild``, and ``apply_ops`` with its number of edits), and what
  the designer writes, shortened to 240 characters after ``runner.redact``.

STAGE 4 ADDITION TO THE CONTRACT: versions (``bricksnap.versions``)
- Every job that changes the model keeps the result as a version, labelled as the command
  line labels it (``cli.keep_version`` and its label helpers): ``new`` "converted"
  ("Converted from cat.glb"); ``build`` "manual" ("Changed by hand", or "Built again" when
  only the bricks changed; nothing new when nothing changed); ``design`` "designed", or
  "edit" with the request as the note, a best-of run saying it was the best of N, a run
  that stopped saying so. Before a job changes anything, a project made before versions
  were kept gets its present state as its first version (``versions.adopt``). Keeping a
  version never fails a job: when it cannot be done the progress says so and the job
  carries on.
- ``restore`` is a job like the others (token, one job per project, refused while another
  runs; a version number that is not a whole number of at least 1 is refused at once, one
  the project does not have fails the job plainly). It keeps the present state first
  (building it when the design was changed after its build, so nothing is lost), brings
  the version back, then draws renders/compare.png and the card again, makes sure the plain
  conversion is there, and refreshes the downloads as after any build.
- ``GET /api/p/<project>`` also gives ``versions``, oldest first, each ``{"n", "kind",
  "label", "note", "created", "parts", "valid", "picture"}`` (``picture`` is the address of
  the version's card, or null), and ``current_version``, the number of the current one
  (null when there are none). (``current`` already says whether the build is up to date.)
- ``project-files.json`` lists the versions too (``viewserver.project_files``), which the
  viewer's two choosers use.
- Under ``files/``, ``versions/<NNNN>/build.json`` and ``versions/<NNNN>/card.png`` are
  served for a version the project's index lists, judged on the resolved path like the
  other files; nothing else in a version's folder (never its design files).

STAGE 4 ADDITION TO THE CONTRACT: designing in passes (``bricksnap.designer.studio``)
- ``/api/p/<project>/design`` with ``{"mode": "passes"}`` (and optional ``"rounds"``, 0 to
  ``MAX_STUDIO_ROUNDS`` = 2, default the studio's 1) starts ``studio.run_studio`` with the
  default passes, for a first design or to design a model again. ``"mode"`` may also be
  ``"one"`` or left out (the one-designer way, as above); anything else is refused. A
  ``request`` or a ``best_of`` other than 1 is refused with this mode. ``understood_runs``
  must be ``studio_runs(rounds)``, the most AI runs it can start (4 passes plus 2 per round:
  6 by default, 4 for 0 rounds, 8 for 2), otherwise it is refused as above.
- It is a ``design`` job like the others (one AI job at a time, the project busy). The job
  also gives ``passes``, the studio's passes in order, each ``{"pass", "job" (its words),
  "state": "waiting" | "running" | "done" | "skipped" | "failed", "version"}`` (``passes``
  is null for every other job). Progress lines come from ``cli.StudioProgress`` (the pass
  starting, "Pass 2 kept as version 3", "The critic found 3 things to fix", "Put back
  version 4 because ...") and, within a pass, the designer's own lines as above, all through
  ``runner.redact``.
- The studio keeps its own versions; the job keeps none. Afterwards the plain conversion is
  made sure of and the downloads refreshed, when the project has a build made from its
  design. A studio that stops fails the job with its own plain words and which versions the
  passes made. While the studio runs the project may have no build at all (the outline
  pass starts from an empty design): ``GET /api/p/<project>`` then says it is not built,
  as for any project without a build.

STAGE 4 ADDITION TO THE CONTRACT: a file of several separate pieces (``bricksnap.pieces``)
- A new model's job reads the upload with ``pieces.find_pieces`` (named as the person's
  file was) before making anything. When the file looks like several pieces and the form
  did not say which to build, the job stops in a fourth state, ``"choosing"``, and gives
  ``pieces`` (``Pieces.to_json`` at the chosen size: how many are offered, how many more
  and how many small bits there are, each offered piece's number, colour and size in studs
  within the whole layout and alone, and ``wait_minutes``) and ``picture``, the address of
  the numbered picture from above (``GET /api/jobs/<id>/pieces.png``, served only while
  that job is waiting; it lives in the upload's folder under ``.incoming`` and goes with
  it). Every other job and state has ``pieces`` and ``picture`` null. A choosing job is
  listed with the running ones in ``GET /api/projects``, so a page opened again still
  shows the question, and its project name stays held.
- ``POST /api/jobs/<id>/choose`` (token, Origin and Host as for every POST) with
  ``{"piece": "largest" | "all" | n}`` answers it and the job goes on: the largest piece
  alone, everything together, or piece n alone (``pipeline.create_project(piece=...)``;
  the project keeps the piece). ``{"cancel": true}`` ends the job "done" with result
  ``{"project": null, "cancelled": true}`` and nothing made. A choice that is not one of
  those, or a number the file does not have, is refused (400) with a plain message and
  the job keeps waiting; a job that is not waiting for a choice answers 409, an unknown
  one 404. Of two answers that race, one is taken and the other gets 409. Once answered
  (or given up), ``pieces`` and ``picture`` are null again. Nobody choosing within
  ``CHOICE_WAIT_S`` (an hour, which the page says: ``pieces.wait_minutes``) fails the job
  plainly. While it waits, the job keeps only the summary and the picture, never the mesh.
- A job may give ``todo``: what to do after its failure, when the page's usual hint for
  that kind of job would be wrong (nobody chose in time; a piece number the file does not
  offer). Null otherwise.
- ``make_app_server`` removes uploads left in ``.incoming`` by a server that stopped while
  it waited for an answer (``App.clear_stale_uploads``): nothing at all when ``.incoming``
  is a link or not a real folder directly inside the projects folder; inside it only real
  folders named like a job id (16 hexadecimal characters), never following links, and
  only those untouched for longer than ``CHOICE_WAIT_S`` plus ``STALE_MARGIN_S`` (ten
  minutes), so a second server on the same folder is not disturbed. When a waiting job's
  upload is gone by the time the answer comes, the job fails plainly with the "choose the
  file again" hint.
- The upload form may carry ``up`` ("x", "y" or "z"; empty for what the file says, as
  ``--up`` on the command line): the pieces are looked for, and the model built, with that
  axis up. Anything else is refused before anything starts. The page offers it under
  "More choices" as "Which way is up in the file", and the question about pieces says to
  use it when the picture shows the pieces from the side.
- A file with too many separate parts seen from above, or too many small bits, is not
  asked about: the job says so in one progress line (``Pieces.note``) and builds it whole.
- The upload form may also carry ``piece`` (the same three choices) to choose in advance;
  a value that is not one of them is refused before anything starts. A file that is one
  object never asks, and is built as before.
- ``GET /api/p/<project>`` gives ``piece``: the piece the project builds, or null.
- The home page shows the question in the new model's job box: what was found and why it
  matters, as a question and with the numbers, the picture, one choice per offered piece
  ("Piece 2 alone", its size built alone, with its colour from the picture), any smaller
  pieces and small bits, "Everything together, as it is", a "Build it" button, "Cancel,
  build nothing", and how long the question waits.

EXPERIMENTAL ADDITION TO THE CONTRACT: models the AI builds from parts (``bricksnap.lab``)
- A second kind of project, a free build (``bricksnap.lab.freebuild``, whose contract says
  what one is on disk): an AI session builds the model itself, part by part, from the whole
  LDraw parts library. It lives in the same projects folder; ``kind`` tells the two apart
  ("model" for one made from a 3D file, "free" for a free build). The pages call it "Built
  by the AI, part by part" and mark it experimental wherever it appears.
- ``POST /api/free`` (JSON): ``{"words", "name"?, "parts"? (20 to 300, default 80),
  "reference"? (the folder name of an ordinary project with a 3D model, whose pictures from
  five sides the AI is shown), "understood": true, "understood_runs": 1}``. Answers
  ``{"job", "project"}`` (202). ``POST /api/p/<project>/change`` for a free build:
  ``{"words", "understood": true, "understood_runs": 1}``: one AI session starting from the
  current model. Both are AI jobs (kinds "free" and "change") under the rules above: token,
  Origin and Host; one AI job for the whole server; one job per project; refused without
  the agreement (the same refusal for a wrong ``understood_runs``). The words are untrusted
  text: at most ``MAX_REQUEST_CHARS``, control characters removed, only ever shown as text.
  A name is cut to ``MAX_NAME_CHARS``; the folder name is chosen by the server as for an
  upload. When LeoCAD, xvfb-run or the parts library is missing, the request is refused
  with ``freebuild.missing``'s plain message and nothing starts.
- Progress lines come from ``freebuild.Progress`` (the builder looking for parts, placing
  parts with the count so far, each check and what it found, what it says, through
  ``runner.redact``). A failed run says why in plain words and keeps what it made as a run
  (``freebuild.build``).
- ``POST /api/p/<project>/use`` ``{"run": n}``: a job ("use") that makes run n the current
  model again (``freebuild.restore``); the other runs stay. ``delete`` moves a free build
  to the bin as any other project.
- Actions that make no sense for a free build (build, design, export, instructions,
  restore) refuse it with a plain message (``NOT_FOR_FREE``), before anything starts; change
  and use refuse an ordinary project (``FREE_ONLY``).
- ``GET /api/projects``: a free build's card has ``kind`` "free", ``name``, ``parts``,
  ``valid`` (the checker found no problems), ``problems``, ``unchecked`` (joints it could
  not confirm), ``checked`` (its one-line summary), ``picture`` (pictures/card.png),
  ``updated`` (project.json's time), ``job`` and ``problem``; ``studs`` is null. Ordinary
  cards gain ``kind`` "model".
- ``GET /api/p/<project>`` for a free build: the card, plus ``words``, ``parts_wanted``,
  ``reference``, ``kinds``, ``summary``, ``report`` (the checker's full report), ``notes``
  (the AI's closing words, redacted when kept), ``current_run``, ``runs`` (oldest first,
  each ``{"n", "kind", "words", "created", "ok", "error", "has_model", "parts", "kinds",
  "summary", "clean", "problems", "unchecked", "seconds", "picture"}``), ``turntable`` (the
  addresses of the twelve views round the model), ``sheet``, ``picture_problem``, ``files``
  (``{file: address}`` for model.ldr, parts.csv and report.txt), ``bin`` and ``job``.
- The page ``/p/<project>`` of a free build is ``viewer/free.html`` (with ``free.js``), not
  the 3D viewer, which cannot draw these parts; ``project-files.json`` is not found for it.
- Files: for a free build, ``files/`` serves only model.ldr, parts.csv, report.txt,
  ``pictures/card.png``, ``pictures/sheet.png``, ``pictures/turn-NN.png`` and
  ``runs/<NNNN>/pictures/card.png`` for a run its project.json lists, judged on the
  resolved path as above. Never the runs' work folders, transcripts, calls.jsonl or
  anything ending ``.jsonl``.
"""

from __future__ import annotations

import contextlib
import errno
import hmac
import json
import os
import re
import secrets
import shutil
import stat
import sys
import threading
import time
import traceback
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from email.message import Message
from email.parser import HeaderParser
from email.utils import collapse_rfc2231_value
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import unquote, urlsplit

from bricksnap.cli import (
    StudioProgress,
    UserError,
    _system_error,
    adopt_versions,
    converted_label,
    design_label,
    keep_present,
    keep_version,
    load_build,
    load_design,
    open_project,
    rebuild_label,
)
from bricksnap.lab import freebuild
from bricksnap.project import Project, ProjectError, slug
from bricksnap.types import SeedError
from bricksnap.versions import VERSIONS_DIR
from bricksnap.viewserver import (
    CATALOG_DIR,
    CATALOG_FILES,
    CONTENT_TYPES,
    VIEWER_DIR,
    ViewerServer,
    _port_number,
    is_local_host,
    project_files,
    safe_join,
    version_entries,
)

MAX_UPLOAD_BYTES = 60 * 1024 * 1024
MODEL_SUFFIXES = (".stl", ".obj", ".glb", ".gltf", ".3mf", ".ply")
FORM_OVERHEAD = 1024 * 1024
"""Room in an upload's Content-Length for the form's other fields and its boundaries."""
MAX_FIELD_BYTES = 4096
MAX_JSON_BYTES = 64 * 1024
MAX_NAME_CHARS = 80
MAX_REQUEST_CHARS = 2000
DEFAULT_STUDS = 16
MIN_STUDS, MAX_STUDS = 4, 96
MAX_BEST_OF = 5
MAX_STUDIO_ROUNDS = 2
KEPT_JOBS = 200
SAID_CHARS = 240

TOKEN_HEADER = "X-BrickSnap-Token"
TOKEN_PLACEHOLDER = "BRICKSNAP_TOKEN"
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
TRASH_DIR = ".trash"
INCOMING_DIR = ".incoming"
REQUEST_TIMEOUT_S = 30
"""How long a connection may wait for the browser to send something."""
CHOICE_WAIT_S = 3600
"""How long a new model waits for the person to choose a piece before it gives up."""
PIECES_PICTURE = "pieces.png"
STALE_MARGIN_S = 600
"""Extra time before an upload left in .incoming is taken to be abandoned."""
_JOB_ID = re.compile(r"[0-9a-f]{16}")
CHOOSE_AGAIN = (
    "Choose the file again on this page; when BrickSnap asks which piece to build, pick one "
    "of the pieces it offers, or everything together."
)
DOWNLOADS = (
    "build.ldr",
    "parts.csv",
    "wanted_list.xml",
    "instructions.pdf",
    "instructions.html",
    "renders/compare.png",
)
SERVED_FILES = frozenset({"project.json", "build.json", "build.rough.json", *DOWNLOADS})
"""The files of a project the pages may fetch; ``renders/<name>.png`` too, and nothing else."""
_SERVED_PICTURE = re.compile(r"renders/[A-Za-z0-9][A-Za-z0-9._-]*\.png")
_SERVED_VERSION = re.compile(r"versions/([0-9]{4,})/(?:build\.json|card\.png)")
_COMMAND_ADVICE = re.compile(
    r"\buv run\b|'bricksnap\b|\s--[a-z]"
    r"|\bbricksnap (?:new|build|check|design|view|export|render|ops|instructions|serve)\b"
)
GLTF_SEPARATE = (
    "{name} keeps its data in separate files, which cannot be uploaded together. Open the "
    "model in your 3D program and export it as .glb (one file), then choose that file."
)
NOT_FOUND_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Not here - BrickSnap</title>
<link rel="icon" href="data:,">
<link rel="stylesheet" href="/viewer/style.css">
<link rel="stylesheet" href="/viewer/app.css">
</head>
<body class="home">
<header class="top">
  <div class="bar">
    <div class="titles">
      <span class="kicker">BrickSnap</span>
      <h1>This model is not here</h1>
    </div>
  </div>
</header>
<main>
  <section class="card notfound">
    <p class="lead">There is no model at this address. It may have been moved to the bin, or
    the address may be mistyped. A model moved to the bin is kept in the .trash folder inside
    your projects folder, so nothing is lost.</p>
    <p><a id="allModels" class="button primary" href="/">See all your models</a></p>
  </section>
</main>
<footer class="foot">
  <p id="trademark">LEGO® is a trademark of the LEGO Group, which does not sponsor,
  authorize, or endorse this project.</p>
</footer>
</body>
</html>
"""
ACTIONS = ("build", "design", "export", "instructions", "delete", "restore", "change", "use")
FREE_JOBS = ("free", "change")
FREE_FILES = frozenset({"model.ldr", "parts.csv", "report.txt"})
"""The files of a free-build project the pages may fetch, besides its pictures."""
_FREE_PICTURE = re.compile(r"pictures/(?:card|sheet|turn-[0-9]{2})\.png")
_FREE_RUN_CARD = re.compile(r"runs/([0-9]{4,})/pictures/card\.png")
NOT_FOR_FREE = (
    "This model was built by the AI from parts (an experimental kind of model), so {what} "
    'does not apply to it. Use "Ask for a change" on its page instead.'
)
FREE_ONLY = (
    "This model was made from a 3D file, so it cannot be changed this way. Use the AI "
    "designer on its page instead."
)
NOT_FOR_FREE_WORDS = {
    "build": "building the bricks again",
    "design": "the AI designer",
    "export": "making the parts list this way",
    "instructions": "making building instructions",
    "restore": "going back to a version",
}
APP_TYPES = {
    **CONTENT_TYPES,
    ".pdf": "application/pdf",
    ".csv": "text/csv; charset=utf-8",
    ".xml": "application/xml; charset=utf-8",
}
_ENCODED_SEPARATOR = re.compile(r"%(2f|5c|00)", re.IGNORECASE)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")

JOB_LABELS = {
    "new": "turning a new model into bricks",
    "build": "rebuilding the bricks",
    "design": "the AI designer is working on it",
    "export": "writing the parts list and the LDraw file",
    "instructions": "making the building instructions",
    "restore": "going back to an earlier version",
    "free": "the AI is building a new model from parts",
    "change": "the AI is changing the model it built",
    "use": "bringing back an earlier run",
}
TOOL_WORDS = {
    "describe": "The designer is looking at the model",
    "render": "The designer is looking at pictures of the model",
    "brief": "The designer is writing down its plan (the brief)",
    "rebuild": "The designer is rebuilding the bricks to check its work",
    "measure": "The designer is measuring the bricks against the model",
    "plan": "The designer is writing down its construction plan",
    "critique": "The critic is writing down what it found",
}
NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five"}
SOMETHING_WENT_WRONG = (
    "Something went wrong inside BrickSnap while {what}. It is not something you did. The "
    "details were written in the window where BrickSnap is running. Try again; if it happens "
    "again, tell the BrickSnap team what you were doing."
)


class Refused(Exception):
    """An action the app turns down, with a plain message and the HTTP status to answer."""

    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class JobFailed(Exception):
    """A job that ran but did not get where it should; the message is for a person, and
    ``todo`` (optional) says what to do instead of the page's usual hint for the job."""

    def __init__(self, message: str, todo: str | None = None) -> None:
        super().__init__(message)
        self.todo = todo


def _wait_words() -> str:
    minutes = round(CHOICE_WAIT_S / 60)
    return "an hour" if minutes == 60 else f"{minutes} minutes" if minutes != 1 else "a minute"


def plain_message(error: BaseException) -> str | None:
    """The message for a mistake a person can fix, as the page shows it, or None for a fault."""
    if isinstance(error, Refused):
        return error.message
    if isinstance(error, freebuild.FreeBuildError):
        return str(error)
    if isinstance(error, (SeedError, ProjectError, UserError, JobFailed)):
        return for_the_page(str(error))
    if isinstance(error, OSError):
        return _system_error(error)
    return None


def for_the_page(message: str) -> str:
    """A command-line message with its command-line advice replaced by which button to press.

    The command line's messages end with what to type ("Make it again with: uv run bricksnap
    build cat"); a person using the pages has buttons instead. Sentences that name a command
    are left out and one sentence of advice for the pages takes their place.
    """
    sentences = re.split(r"(?<=[.!?])\s+", message.strip())
    kept = [s for s in sentences if not _COMMAND_ADVICE.search(s)]
    dropped = " ".join(s for s in sentences if _COMMAND_ADVICE.search(s))
    if not dropped:
        return message
    if re.search(r"\bnew\b", dropped):
        advice = 'Make the model again from its file on the home page ("Make a new model").'
    elif re.search(r"\bcheck\b", dropped):
        advice = (
            'Ask the AI designer to fix the model, or press "Build the bricks again" on the '
            "model's page."
        )
    else:
        advice = 'Press "Build the bricks again" on the model\'s page.'
    return " ".join([*kept, advice])


def gltf_needs_other_files(path: Path) -> bool:
    """True when a .gltf file keeps its data in separate files (a buffer not inside it)."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False  # not readable as glTF: loading it says what is wrong
    buffers = data.get("buffers") if isinstance(data, dict) else None
    for buffer in buffers if isinstance(buffers, list) else []:
        uri = buffer.get("uri") if isinstance(buffer, dict) else None
        if isinstance(uri, str) and not uri.startswith("data:"):
            return True
    return False


def served_file(folder: Path, inner: str) -> Path | None:
    """The file ``inner`` of a project's folder when the pages may fetch it, else None.

    Judged on the file the address resolves to, so a symlink cannot reach anything else."""
    target = safe_join(folder, inner)
    if target is None:
        return None
    try:
        rel = target.relative_to(folder.resolve()).as_posix()
    except (OSError, ValueError):
        return None
    if rel.lower().endswith(".jsonl"):
        return None
    if freebuild.is_free(folder):
        return served_free_file(folder, target, rel)
    if rel in SERVED_FILES or _SERVED_PICTURE.fullmatch(rel):
        return target
    kept = _SERVED_VERSION.fullmatch(rel)
    if kept is None or kept.group(1) != f"{int(kept.group(1)):04d}":
        return None
    return target if int(kept.group(1)) in {v["n"] for v in version_list(folder)} else None


def served_free_file(folder: Path, target: Path, rel: str) -> Path | None:
    """For a free-build project: the model, the parts list, the report and the pictures, and
    the card of a run its project.json lists. Nothing else (never a run's work folder)."""
    if rel in FREE_FILES or _FREE_PICTURE.fullmatch(rel):
        return target
    kept = _FREE_RUN_CARD.fullmatch(rel)
    if kept is None or kept.group(1) != f"{int(kept.group(1)):04d}":
        return None
    try:
        runs = freebuild.read_meta(folder).get("runs") or []
    except freebuild.FreeBuildError:
        return None
    listed = {r.get("n") for r in runs if isinstance(r, dict)}
    return target if int(kept.group(1)) in listed else None


def version_list(folder: Path) -> list[dict[str, Any]]:
    """The versions of the project in ``folder``, oldest first, as ``viewserver.project_files``
    lists them; an empty list when there are none or they cannot be read."""
    return version_entries(folder)[0]


def clean_text(text: str, limit: int) -> str:
    """Text from the browser as one line: control characters gone, at most ``limit`` long."""
    return _CONTROL.sub(" ", text).strip()[:limit].strip()


def _plural(n: int, word: str) -> str:
    return f"{n:,} {word if n == 1 else word + 's'}"


def _short(text: str, limit: int = SAID_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ---- jobs ---------------------------------------------------------------------------------


@dataclass
class Job:
    id: str
    kind: str
    project: str
    ai: bool = False
    state: str = "waiting"  # waiting, running, choosing, done, failed
    started: float = field(default_factory=time.time)
    finished: float | None = None
    progress: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    passes: list[dict[str, Any]] | None = None  # a studio job's passes, in order
    pieces: dict[str, Any] | None = None  # a new model's pieces (``Pieces.to_json``)
    picture: Path | None = None  # the picture of those pieces, numbered
    choice: str | int | None = None  # what the person chose ("cancel" to build nothing)
    chosen: threading.Event = field(default_factory=threading.Event)
    todo: str | None = None  # what to do after a failure, when the page's usual hint is wrong

    def say(self, line: str) -> None:
        self.progress.append(line)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "kind": self.kind,
            "project": self.project,
            "what": JOB_LABELS.get(self.kind, self.kind),
            "started": self.started,
            "finished": self.finished,
            "progress": list(self.progress),
            "result": self.result,
            "error": self.error,
            "passes": None if self.passes is None else [dict(p) for p in self.passes],
            "pieces": self.pieces,
            "picture": f"/api/jobs/{self.id}/{PIECES_PICTURE}" if self.picture else None,
            "todo": self.todo,
        }


def studio_runs(rounds: int) -> int:
    """The most AI runs a studio job with ``rounds`` rounds of critic and fix can start."""
    from bricksnap.designer import studio

    return len(studio.DEFAULT_PASSES) + 2 * rounds


def designer_progress(event: dict[str, Any]) -> list[str]:
    """Plain sentences for one stream-json event of an AI design run."""
    from bricksnap.designer.runner import TOOL_PREFIX, StreamParser, redact

    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        return ["The designer has started"]
    if kind != "assistant":
        return []
    lines = []
    for item in StreamParser._content(event):
        if item.get("type") == "tool_use":
            name = str(item.get("name", "")).removeprefix(TOOL_PREFIX)
            if name == "apply_ops":
                ops = (item.get("input") or {}).get("ops")
                count = f" ({_plural(len(ops), 'edit')})" if isinstance(ops, list) else ""
                lines.append(f"The designer changed the design{count}")
            else:
                lines.append(TOOL_WORDS.get(name, f"The designer is using its {name} tool"))
        elif item.get("type") == "text" and str(item.get("text") or "").strip():
            lines.append("The designer says: " + _short(redact(str(item["text"]))))
    return lines


def best_of_progress(event: dict[str, Any]) -> str | None:
    """A plain sentence for one ``judge.design_best_of`` event (as ``bricksnap design``)."""
    from bricksnap.designer.runner import redact

    kind = event.get("event")
    if kind == "designing":
        return f"Designing {event.get('candidate')} of {event.get('of')}"
    if kind == "designed":
        if event.get("valid"):
            return f"Design {event.get('candidate')} is ready"
        return f"Design {event.get('candidate')} cannot be used: {redact(str(event.get('why')))}"
    if kind == "judging":
        count = event.get("candidates")
        return f"Judging the {NUMBER_WORDS.get(count, count)} designs" if count else "Judging"

    if kind == "judged":
        if event.get("ok"):
            return "The judge has finished"
        return f"The judge did not finish: {redact(str(event.get('error')))}"
    if kind == "kept":
        if event.get("winner") is None:
            return "No design could be kept"
        how = " (chosen by measurement)" if event.get("by_measurement") else ""
        return f"Kept design {event.get('winner')}{how}"
    return None


# ---- reading an upload --------------------------------------------------------------------


def _header_param(msg: Message, name: str) -> str | None:
    value = msg.get_param(name, header="content-disposition")
    if value is None:
        return None
    return collapse_rfc2231_value(value)


class _Reader(Protocol):
    def read(self, size: int, /) -> bytes: ...


def read_form(
    rfile: _Reader,
    length: int,
    boundary: bytes,
    save_file: Callable[[str], Path],
    file_field: str = "model",
) -> tuple[dict[str, str], str | None, int]:
    """Read a multipart/form-data body of ``length`` bytes from ``rfile``.

    Returns the text fields, the browser's name of the ``file_field`` file (None when no file
    was sent) and the file's size. ``save_file(browser_name)`` is called when the file's part
    starts; it returns the path to write to, or raises ``Refused`` (a wrong suffix), which
    stops the reading there. The file is written as it arrives and refused once it passes
    ``MAX_UPLOAD_BYTES``. Never reads more than ``length`` bytes.
    """
    chunk = 64 * 1024
    remaining = length
    buf = bytearray()

    def fill() -> None:
        nonlocal remaining
        if remaining <= 0:
            raise Refused("The form that was sent is incomplete. Try again.")
        data = rfile.read(min(chunk, remaining))
        if not data:
            raise Refused("The upload stopped before the whole file arrived. Try again.")
        remaining -= len(data)
        buf.extend(data)

    def need(count: int) -> None:
        while len(buf) < count:
            fill()

    delim = b"--" + boundary
    sep = b"\r\n" + delim
    while (start := buf.find(delim)) < 0:  # the preamble, normally empty
        if len(buf) > chunk:
            raise Refused("The form that was sent could not be read. Try again.")
        fill()
    del buf[: start + len(delim)]

    fields: dict[str, str] = {}
    file_name: str | None = None
    file_size = 0
    while True:
        need(2)
        if buf[:2] == b"--":
            break  # the closing boundary
        if buf[:2] != b"\r\n":
            raise Refused("The form that was sent could not be read. Try again.")
        del buf[:2]
        while (end := buf.find(b"\r\n\r\n")) < 0:
            if len(buf) > 16 * 1024:
                raise Refused("The form that was sent could not be read. Try again.")
            fill()
        msg = HeaderParser().parsestr(bytes(buf[:end]).decode("utf-8", "replace"))
        del buf[: end + 4]
        name = _header_param(msg, "name")
        filename = _header_param(msg, "filename")

        out = None
        text: bytearray | None = None
        if name == file_field and filename and file_name is None:
            file_name = filename
            out = save_file(filename).open("wb")
        elif filename is None and name is not None:
            text = bytearray()
        try:
            while True:
                at = buf.find(sep)
                data = bytes(buf[:at]) if at >= 0 else bytes(buf[: max(0, len(buf) - len(sep))])
                if out is not None:
                    file_size += len(data)
                    if file_size > MAX_UPLOAD_BYTES:
                        raise Refused(too_large_message(), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                    out.write(data)
                elif text is not None:
                    text.extend(data)
                    if len(text) > MAX_FIELD_BYTES:
                        raise Refused("A field of the form is too long.")
                if at >= 0:
                    del buf[: at + len(sep)]
                    break
                del buf[: len(data)]
                fill()
        finally:
            if out is not None:
                out.close()
        if text is not None and name is not None:
            fields[name] = text.decode("utf-8", "replace")
    return fields, file_name, file_size


def too_large_message() -> str:
    mb = MAX_UPLOAD_BYTES // (1024 * 1024)
    return (
        f"The file is too large: BrickSnap takes model files of up to {mb} MB. Save a simpler "
        "version of the model in your 3D program (fewer triangles) and try again."
    )


def wrong_suffix_message(name: str) -> str:
    kinds = ", ".join(s.lstrip(".").upper() for s in MODEL_SUFFIXES)
    return f"BrickSnap cannot open {name}. Please choose a 3D model file: {kinds}."


# ---- the app ------------------------------------------------------------------------------


class App:
    """Everything the request handler acts on: the projects folder, the token and the jobs."""

    def __init__(self, projects_dir: Path) -> None:
        self.shown_root = projects_dir  # as the person gave it, for messages
        self.root = projects_dir.resolve()
        self.threads: list[threading.Thread] = []
        self.token = secrets.token_hex(32)
        self.lock = threading.Lock()
        self.jobs: dict[str, Job] = {}
        self.busy: dict[str, str] = {}  # project folder name -> the id of its running job
        self.ai_job: str | None = None

    # ---- projects ---------------------------------------------------------------------------

    def project_dir(self, name: str) -> Path | None:
        """The folder of project ``name`` inside ``projects_dir``, or None."""
        if not SLUG_RE.fullmatch(name):
            return None
        path = self.root / name
        try:
            if path.resolve().parent != self.root or not (path / "project.json").is_file():
                return None
        except (OSError, RuntimeError, ValueError):
            return None
        return path

    def known(self, name: str) -> Path:
        """The folder of project ``name``, or a plain refusal. Opens nothing: a refused
        request must not touch a project whose job is running."""
        folder = self.project_dir(name)
        if folder is None:
            raise Refused(
                f"There is no project called {name!r} here. It may have been moved to the bin; "
                "go back to the list of models.",
                HTTPStatus.NOT_FOUND,
            )
        return folder

    def ordinary(self, name: str, action: str) -> Path:
        """The folder of ordinary project ``name``; a free build is refused plainly."""
        folder = self.known(name)
        if freebuild.is_free(folder):
            raise Refused(NOT_FOR_FREE.format(what=NOT_FOR_FREE_WORDS.get(action, "that")))
        return folder

    def free(self, name: str) -> Path:
        """The folder of free-build project ``name``; an ordinary project is refused."""
        folder = self.known(name)
        if not freebuild.is_free(folder):
            raise Refused(FREE_ONLY)
        return folder

    def open(self, name: str) -> Project:
        """Open project ``name`` for a job (this puts back an interrupted best-of run)."""
        return open_project(str(self.known(name)))

    def summary(self, folder: Path) -> dict[str, Any]:
        """A project's card for the home page, read without trusting its files."""
        name = folder.name
        if freebuild.is_free(folder):
            return self.free_summary(folder)
        card: dict[str, Any] = {
            "project": name,
            "kind": "model",
            "name": name,
            "studs": None,
            "parts": None,
            "valid": None,
            "picture": None,
            "updated": 0.0,
            "job": self.busy.get(name),
            "problem": None,
        }
        times = []
        try:
            times.append((folder / "project.json").stat().st_mtime)
            meta = json.loads((folder / "project.json").read_text(encoding="utf-8"))
            if not isinstance(meta, dict):
                raise ValueError("not an object")
            card["name"] = str(meta.get("name") or name)
            studs = meta.get("studs")
            card["studs"] = studs if isinstance(studs, int) else None
        except (OSError, ValueError):
            card["problem"] = "This project's file project.json is damaged and cannot be read."
        build_file = folder / "build.json"
        if build_file.is_file():
            try:
                times.append(build_file.stat().st_mtime)
                data = json.loads(build_file.read_text(encoding="utf-8"))
                parts = data.get("parts")
                card["parts"] = len(parts) if isinstance(parts, list) else None
                report = data.get("report")
                card["valid"] = bool(report.get("ok")) if isinstance(report, dict) else False
            except (OSError, ValueError, AttributeError):
                card["problem"] = card["problem"] or (
                    "This project's build file is damaged and cannot be read. Build it again."
                )
        for picture in ("card.png", "compare.png"):
            with contextlib.suppress(OSError):
                path = folder / "renders" / picture
                if path.is_file():
                    version = path.stat().st_mtime_ns
                    card["picture"] = f"/p/{name}/files/renders/{picture}?v={version}"
                    break
        card["updated"] = max(times, default=0.0)
        return card

    def free_summary(self, folder: Path) -> dict[str, Any]:
        """A free-build project's card: as an ordinary one's, with ``kind`` "free", what the
        checker said (``checked``, ``problems``, ``unchecked``) and no studs."""
        name = folder.name
        card: dict[str, Any] = {
            "project": name,
            "kind": "free",
            "name": name,
            "studs": None,
            "parts": None,
            "valid": None,
            "problems": None,
            "unchecked": None,
            "checked": "",
            "picture": None,
            "updated": 0.0,
            "job": self.busy.get(name),
            "problem": None,
        }
        try:
            card["updated"] = (folder / "project.json").stat().st_mtime
            info = freebuild.describe(folder)
        except (OSError, freebuild.FreeBuildError):
            card["problem"] = "This project's file project.json is damaged and cannot be read."
            return card
        card.update(
            name=info["name"],
            parts=info["parts"],
            valid=info["clean"],
            problems=info["problems"],
            unchecked=info["unchecked"],
            checked=info["summary"],
        )
        with contextlib.suppress(OSError):
            path = folder / "pictures" / "card.png"
            if path.is_file():
                card["picture"] = f"/p/{name}/files/pictures/card.png?v={path.stat().st_mtime_ns}"
        return card

    def free_info(self, folder: Path) -> dict[str, Any]:
        """``GET /api/p/<project>`` for a free-build project."""
        name = folder.name
        info = self.free_summary(folder)
        about: dict[str, Any]
        try:
            about = freebuild.describe(folder)
        except freebuild.FreeBuildError as e:
            about = {"runs": [], "turntable": [], "files": []}
            info["problem"] = str(e)

        def url(rel: str | None) -> str | None:
            if not rel:
                return None
            try:
                stamp = (folder / rel).stat().st_mtime_ns
            except OSError:
                return None
            return f"/p/{name}/files/{rel}?v={stamp}"

        runs = []
        for run in about.get("runs", []):
            n = run.get("n")
            if not isinstance(n, int):
                continue
            card = f"runs/{n:04d}/pictures/card.png"
            runs.append(
                {
                    **{
                        k: run.get(k)
                        for k in (
                            "n",
                            "kind",
                            "words",
                            "created",
                            "ok",
                            "error",
                            "has_model",
                            "parts",
                            "kinds",
                            "summary",
                            "clean",
                            "problems",
                            "unchecked",
                            "seconds",
                        )
                    },
                    "picture": url(card),
                }
            )
        info.update(
            words=about.get("words", ""),
            parts_wanted=about.get("parts_wanted"),
            reference=about.get("reference"),
            kinds=about.get("kinds"),
            summary=about.get("summary", ""),
            report=about.get("report", ""),
            notes=about.get("notes", ""),
            current_run=about.get("current_run"),
            runs=runs,
            turntable=[u for u in (url(rel) for rel in about.get("turntable", [])) if u],
            sheet=url(str(about.get("sheet") or "")),
            picture_problem=about.get("picture_problem"),
            files={rel: url(rel) for rel in about.get("files", [])},
            bin=str(self.shown_root / TRASH_DIR),
        )
        job_id = info["job"]
        with self.lock:
            job = self.jobs.get(job_id) if job_id else None
            info["job"] = job.to_json() if job else None
        return info

    def list_projects(self) -> dict[str, Any]:
        cards = []
        with contextlib.suppress(OSError):
            for folder in self.root.iterdir():
                if self.project_dir(folder.name) is not None:
                    cards.append(self.summary(folder))
        cards.sort(key=lambda c: (-c["updated"], c["project"]))
        with self.lock:
            active = [
                j.to_json()
                for j in self.jobs.values()
                if j.state in ("waiting", "running", "choosing")
            ]
        return {"projects": cards, "jobs": active}

    def clear_stale_uploads(self) -> int:
        """Remove uploads left in ``.incoming`` by a server that stopped while a new model
        waited for its answer (or failed to tidy up). Returns how many were removed.

        Nothing at all when ``.incoming`` is a link or not a real folder directly inside the
        projects folder. Inside it, only real folders (not links) named like a job (16
        lower-case hexadecimal characters) and not touched for longer than the waiting limit
        and ``STALE_MARGIN_S``, so another server on the same folder keeps the uploads it is
        still asking about. Links inside them are removed, never followed."""
        incoming = self.root / INCOMING_DIR
        try:
            if incoming.is_symlink() or not incoming.is_dir():
                return 0
            if incoming.resolve().parent != self.root.resolve():
                return 0
            entries = list(incoming.iterdir())
        except OSError:
            return 0
        removed = 0
        now = time.time()
        for folder in entries:
            if not _JOB_ID.fullmatch(folder.name):
                continue
            try:
                info = folder.lstat()
            except OSError:
                continue
            if (
                not stat.S_ISDIR(info.st_mode)
                or now - info.st_mtime <= CHOICE_WAIT_S + STALE_MARGIN_S
            ):
                continue
            shutil.rmtree(folder, ignore_errors=True)  # removes links inside, never follows
            removed += 1
        return removed

    def make_missing_cards(self) -> int:
        """Draw renders/card.png for every project that has a build but no card yet (one made
        with the command line, or before cards existed). Returns how many were drawn. A
        project with a running job is left to its job; one that cannot be drawn is skipped."""
        from bricksnap.pipeline import render_card

        made = 0
        with contextlib.suppress(OSError):
            for folder in sorted(self.root.iterdir()):
                name = folder.name
                if self.project_dir(name) is None or (folder / "renders" / "card.png").exists():
                    continue
                if not (folder / "build.json").is_file() or name in self.busy:
                    continue
                try:
                    render_card(Project(folder))
                    made += 1
                except Exception as e:  # a damaged project must not stop the others
                    print(f"No card picture for {name}: {type(e).__name__}: {e}", file=sys.stderr)
        return made

    def project_info(self, name: str) -> dict[str, Any]:
        folder = self.project_dir(name)
        if folder is None:
            raise Refused(f"There is no project called {name!r} here.", HTTPStatus.NOT_FOUND)
        if freebuild.is_free(folder):
            return self.free_info(folder)
        info = self.summary(folder)
        info["notes"], info["brief"], info["current"], info["verdict"] = [], None, False, ""
        info["piece"] = None
        with contextlib.suppress(OSError, ValueError, AttributeError):
            meta = json.loads((folder / "project.json").read_text(encoding="utf-8"))
            info["brief"] = meta.get("brief") or None
            piece = meta.get("piece")
            if isinstance(piece, int) and not isinstance(piece, bool) and piece >= 1:
                info["piece"] = piece
        with contextlib.suppress(OSError, ValueError, AttributeError):
            data = json.loads((folder / "build.json").read_text(encoding="utf-8"))
            notes = data.get("notes")
            if isinstance(notes, list):
                info["notes"] = [n for n in notes if isinstance(n, str) and n.strip()]
        try:
            project = Project(folder)
            info["current"] = project.build_is_current()
        except Exception:  # damaged files: the card's "problem" already says so
            info["current"] = False
        if info["valid"]:
            info["verdict"] = (
                f"{_plural(info['parts'] or 0, 'part')} in one connected piece that stands up on "
                "its own."
            )
        elif info["valid"] is False:
            info["verdict"] = "The bricks do not hold together as one standing model yet."
        else:
            info["verdict"] = "Not built into bricks yet."
        info["files"] = [f for f in DOWNLOADS if safe_join(folder, f) is not None]
        info["bin"] = str(self.shown_root / TRASH_DIR)
        found, info["current_version"] = version_entries(folder)
        info["versions"] = []
        for v in found:
            card = folder / VERSIONS_DIR / f"{v['n']:04d}" / "card.png"
            picture = f"/p/{name}/files/{VERSIONS_DIR}/{v['n']:04d}/card.png"
            info["versions"].append(
                {
                    **{k: v[k] for k in ("n", "kind", "label", "note", "created", "parts")},
                    "valid": v["valid"],
                    "picture": picture if card.is_file() else None,
                }
            )
        job_id = info["job"]
        with self.lock:
            job = self.jobs.get(job_id) if job_id else None
            info["job"] = job.to_json() if job else None
        return info

    def job_json(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise Refused(
                    "That job is not known. It may have finished before BrickSnap was last "
                    "started; the project list shows how things are now.",
                    HTTPStatus.NOT_FOUND,
                )
            return job.to_json()

    def free_name(self, wanted: str) -> str:
        """A folder name for a new project: ``slug(wanted)``, made unique with a number.
        Call with the lock held."""
        base = slug(wanted)[:60].strip("-") or "model"
        name, n = base, 1
        while name in self.busy or os.path.lexists(self.root / name):
            n += 1
            name = f"{base}-{n}"
        return name

    # ---- running jobs -----------------------------------------------------------------------

    def start(
        self,
        kind: str,
        project: str,
        work: Callable[[Job], dict[str, Any]],
        *,
        ai: bool = False,
        job_id: str | None = None,
        reserved: bool = False,
    ) -> Job:
        """Start ``work`` in a thread as a job on ``project``; refused while one runs there.
        With ``reserved`` the project's name was already taken for this job (a new upload)."""
        with self.lock:
            running = self.jobs.get(self.busy.get(project, ""))
            if running is not None and not (reserved and running.id == job_id):
                raise Refused(self.busy_message(running), HTTPStatus.CONFLICT)
            if ai and self.ai_job is not None and self.jobs[self.ai_job].kind in FREE_JOBS:
                other = self.jobs[self.ai_job]
                raise Refused(
                    f'The AI is already building "{other.project}" from parts. Only one AI job '
                    "runs at a time; wait for it to finish, then try again.",
                    HTTPStatus.CONFLICT,
                )
            if ai and self.ai_job is not None:
                other = self.jobs[self.ai_job]
                raise Refused(
                    f'The AI designer is already working on "{other.project}". Only one design '
                    "runs at a time; wait for it to finish, then try again.",
                    HTTPStatus.CONFLICT,
                )
            job = Job(id=job_id or secrets.token_hex(8), kind=kind, project=project, ai=ai)
            self.jobs[job.id] = job
            self.busy[project] = job.id
            if ai:
                self.ai_job = job.id
            self._forget_old_jobs()
        thread = threading.Thread(target=self._run, args=(job, work), daemon=True)
        with self.lock:
            self.threads = [t for t in self.threads if t.is_alive()] + [thread]
        thread.start()
        return job

    def wait_idle(self, timeout: float) -> bool:
        """Wait until no job thread is running; True when none is left."""
        end = time.time() + timeout
        with self.lock:
            threads = list(self.threads)
        for thread in threads:
            thread.join(max(0.0, end - time.time()))
        return not any(t.is_alive() for t in threads)

    def reserve(self, wanted: str, job_id: str) -> str:
        """Hold a new project's folder name for the upload that is arriving."""
        with self.lock:
            name = self.free_name(wanted)
            self.busy[name] = job_id
            return name

    def release(self, name: str, job_id: str) -> None:
        with self.lock:
            if self.busy.get(name) == job_id:
                del self.busy[name]

    def busy_message(self, job: Job) -> str:
        minutes = int((time.time() - job.started) // 60)
        ago = "just now" if minutes < 1 else f"{_plural(minutes, 'minute')} ago"
        return (
            f'"{job.project}" is busy: {JOB_LABELS.get(job.kind, job.kind)} (started {ago}). '
            "Wait for that to finish, then try again."
        )

    def _forget_old_jobs(self) -> None:
        done = [j for j in self.jobs.values() if j.state in ("done", "failed")]
        for job in done[: max(0, len(done) - KEPT_JOBS)]:
            del self.jobs[job.id]

    def _run(self, job: Job, work: Callable[[Job], dict[str, Any]]) -> None:
        job.state = "running"
        try:
            job.result = work(job)
            job.state = "done"
        except BaseException as e:  # a job's thread ends here, whatever stopped it
            message = plain_message(e)
            if isinstance(e, JobFailed):
                job.todo = e.todo
            if message is None:
                print(f"BrickSnap: the {job.kind} job for {job.project!r} failed:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                message = SOMETHING_WENT_WRONG.format(what=JOB_LABELS.get(job.kind, job.kind))
            job.error = message
            job.state = "failed"
        finally:
            if job.state not in ("done", "failed"):  # stopped by something that is not an error
                job.error = SOMETHING_WENT_WRONG.format(what=JOB_LABELS.get(job.kind, job.kind))
                job.state = "failed"
            job.finished = time.time()
            with self.lock:
                if self.busy.get(job.project) == job.id:
                    del self.busy[job.project]
                if self.ai_job == job.id:
                    self.ai_job = None

    # ---- actions ------------------------------------------------------------------------------

    def new_project(
        self, job_id: str, folder: str, staging: Path, upload: Path, fields: dict[str, str]
    ) -> Job:
        """Start the job that makes project ``folder`` from the file saved at ``upload``."""
        studs = parse_studs(fields.get("studs"))
        browser_name = clean_text(fields.get("_file_name", ""), 200) or upload.name
        name = clean_text(fields.get("name", ""), MAX_NAME_CHARS)
        name = name or clean_text(Path(browser_name.replace("\\", "/")).stem, MAX_NAME_CHARS)
        hollow = fields.get("hollow", "").strip().lower() in ("1", "true", "on", "yes")
        wanted = parse_piece(fields.get("piece"))
        up = parse_up(fields.get("up"))

        def work(job: Job) -> dict[str, Any]:
            from bricksnap.pipeline import create_project

            try:
                job.say(f"Reading {browser_name} and turning it into bricks")
                piece, box = self._which_piece(
                    job, upload, staging, studs, wanted, browser_name, up
                )
                if piece == "cancel":
                    job.say("Stopped before building, as you chose. Nothing was made.")
                    return {"project": None, "cancelled": True}
                if not upload.is_file():  # tidied away meanwhile, e.g. by another server
                    raise JobFailed(
                        f"The file {browser_name} was no longer here when your answer came "
                        "(it is kept only while BrickSnap waits), so nothing was built.",
                        todo=CHOOSE_AGAIN,
                    )
                if piece is not None:
                    job.say(f"Turning piece {piece} of {browser_name} into bricks, on its own")
                made = create_project(
                    upload,
                    studs=studs,
                    name=name or upload.stem,
                    directory=staging / "made",
                    up=up,
                    hollow=hollow,
                    piece=piece if isinstance(piece, int) else None,
                    piece_box=box,
                )
                with self.lock:
                    target = self.root / job.project
                    if os.path.lexists(target):  # a folder of that name appeared meanwhile
                        del self.busy[job.project]
                        job.project = self.free_name(job.project)
                        self.busy[job.project] = job.id
                        target = self.root / job.project
                    os.rename(made.path, target)
                project = Project(target)
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            return self._build(job, project, new=True)

        return self.start("new", folder, work, job_id=job_id, reserved=True)

    def _which_piece(
        self,
        job: Job,
        upload: Path,
        staging: Path,
        studs: int,
        wanted: str | int | None,
        shown_name: str,
        up: str | None = None,
    ) -> tuple[int | str | None, Any]:
        """(the piece of the uploaded file to build, and its box): a number, None for the
        whole file, or "cancel". When the file looks like several pieces and the form did
        not say which, the job waits (state "choosing") until the person chooses on the
        page; only the summary, the picture and the offered pieces' boxes are kept
        meanwhile, never the mesh."""
        from bricksnap.pieces import find_pieces

        found = find_pieces(upload, up=up, name=shown_name)
        several, offered, total = found.several, found.count, len(found.everything)
        boxes = [p.box for p in found.pieces] if several else []
        note = found.note()
        summary = found.to_json(studs)
        picture: Path | None = None
        if several and wanted is None:
            picture = staging / PIECES_PICTURE
            try:
                found.save_picture(picture)
            except OSError:
                picture = None
        del found  # the mesh is not kept while the job waits
        if not several:
            if note:
                job.say(note)
            if isinstance(wanted, int) and wanted > 1:
                raise JobFailed(
                    f"{shown_name} looks like one object, so there is no piece {wanted} to build.",
                    todo=CHOOSE_AGAIN,
                )
            return None, None
        if wanted is None:
            summary["wait_minutes"] = round(CHOICE_WAIT_S / 60)
            with self.lock:
                job.pieces = summary
                job.picture = picture
                job.state = "choosing"
            job.say(
                f"This file looks like {total} separate pieces, not one object. Waiting for "
                "you to choose what to build."
            )
            if not job.chosen.wait(CHOICE_WAIT_S):
                with self.lock:
                    job.state = "running"
                    job.pieces = job.picture = None
                raise JobFailed(
                    f"Nobody chose which piece to build within {_wait_words()}, so nothing "
                    "was built.",
                    todo=CHOOSE_AGAIN,
                )
            wanted = job.choice
        if wanted == "cancel" or wanted is None:
            return "cancel", None
        if wanted == "all":
            job.say(f"Building all {total} pieces together, as you chose")
            return None, None
        number = 1 if wanted == "largest" else int(wanted)
        if not 1 <= number <= offered:
            raise JobFailed(
                f"{shown_name} has {offered} pieces to choose from, numbered 1 to {offered}, "
                f"so there is no piece {number}.",
                todo=CHOOSE_AGAIN,
            )
        return number, boxes[number - 1]

    def choose(self, job_id: str, body: dict[str, Any]) -> dict[str, Any]:
        """The person's answer to "which piece?" for a new model that is waiting for it:
        ``{"piece": "largest" | "all" | n}``, or ``{"cancel": true}`` to build nothing."""
        from bricksnap.pieces import parse_choice

        if body.get("cancel") is True:
            choice: str | int = "cancel"
        else:
            try:
                choice = parse_choice(body.get("piece", ""))
            except SeedError as e:
                raise Refused(str(e)) from e
        with self.lock:
            job = self.jobs.get(job_id) if _JOB_ID.fullmatch(job_id) else None
            if job is None:
                raise Refused("That job is not known.", HTTPStatus.NOT_FOUND)
            if job.state != "choosing" or job.chosen.is_set():
                raise Refused(
                    "This model is not waiting for a choice any more. Reload the page to see "
                    "how it is going.",
                    HTTPStatus.CONFLICT,
                )
            count = int((job.pieces or {}).get("count", 0))
            if isinstance(choice, int) and not 1 <= choice <= count:
                raise Refused(f"There is no piece {choice}: the pieces are numbered 1 to {count}.")
            job.choice = choice
            job.state = "running"
            job.pieces = job.picture = None  # the question is answered
            job.chosen.set()
        return {"job": job_id}

    def pieces_picture(self, job_id: str) -> Path | None:
        """The numbered picture of a new model's pieces, while its job has one."""
        with self.lock:
            job = self.jobs.get(job_id) if _JOB_ID.fullmatch(job_id) else None
            picture = job.picture if job is not None else None
        return picture if picture is not None and picture.is_file() else None

    def _build(self, job: Job, project: Project, new: bool = False) -> dict[str, Any]:
        """Rebuild, draw the picture and make the plain conversion, as ``bricksnap build``."""
        from bricksnap.pipeline import rebuild, render_card, render_compare, rough_build

        job.say("Laying out the bricks and checking that they hold together")
        load_design(project)  # a plain message, not a traceback, when the design is damaged
        if not new:
            adopt_versions(project, say=job.say)
        build = rebuild(project)
        job.say("Drawing a picture of the model beside the bricks")
        render_compare(project)
        render_card(project)
        job.say("Making the plain conversion, to show beside the design")
        rough_build(project)
        self._refresh_downloads(job, project)
        if new:
            self._keep(job, project, "converted", converted_label(project))
        else:
            self._keep(job, project, "manual", rebuild_label(project, build))
        return self._outcome(job, project, build)

    def _keep(self, job: Job, project: Project, kind: str, label: str, note: str = "") -> None:
        """Keep the model as it is now as a version, and say so; never fails the job."""
        n = keep_version(project, kind, label, note, say=job.say)
        if n is not None:
            job.say(f"Kept as version {n}: {label}")

    def _refresh_downloads(self, job: Job, project: Project) -> None:
        """Keep the files a person downloads in step with the build just made.

        The parts list and the wanted list are written again, and so is the instruction
        booklet when the project had one, so nobody orders the parts of an older build. A
        file that cannot be written again is taken away (it would describe another build)
        and the progress says so; the job itself carries on, because the build is fine.
        """
        from bricksnap.catalog import load_catalog
        from bricksnap.export import write_exports
        from bricksnap.instructions import make_instructions

        def renew(files: tuple[str, ...], make: Callable[[], object], what: str) -> None:
            try:
                make()
            except Exception as e:  # these files are extras: never fail the build for them
                print(f"Could not write {what}: {type(e).__name__}: {e}", file=sys.stderr)
                for name in files:
                    with contextlib.suppress(OSError):
                        (project.path / name).unlink()
                job.say(f"Could not write {what} for this build; the older one was removed")

        renew(
            ("parts.csv", "wanted_list.xml"),
            lambda: write_exports(project, load_catalog()),
            "the parts list and the wanted list",
        )
        booklet = ("instructions.pdf", "instructions.html")
        if any((project.path / name).is_file() for name in booklet):
            job.say("Bringing the instruction booklet up to date")
            renew(booklet, lambda: make_instructions(project), "the instruction booklet")

    def _outcome(self, job: Job, project: Project, build: Any) -> dict[str, Any]:
        ok = bool(build.report and build.report.ok)
        if ok:
            job.say(f"Done: {_plural(len(build.parts), 'part')} in one connected piece")
        else:
            job.say(
                f"Done, but the {_plural(len(build.parts), 'part')} do not hold together as one "
                "standing model yet"
            )
        return {"project": project.path.name, "parts": len(build.parts), "valid": ok}

    def build(self, name: str) -> Job:
        self.ordinary(name, "build")  # a plain refusal now if it is not there

        def work(job: Job) -> dict[str, Any]:
            return self._build(job, self.open(name))

        return self.start("build", name, work)

    def design(self, name: str, body: dict[str, Any]) -> Job:
        mode = body.get("mode")
        if mode == "passes":
            return self.design_in_passes(name, body)
        if mode not in (None, "one"):
            raise Refused(
                'Choose how the AI designs the model: "one" (one AI run that touches up the '
                'conversion) or "passes" (it designs the model in passes).'
            )
        request = body.get("request")
        if request is not None:
            if not isinstance(request, str):
                raise Refused("The request must be text, such as: add a red collar.")
            if not request.strip():
                raise Refused(
                    'The request is empty. Type the change you want, for example "add a red '
                    'collar", or leave the box empty for a first design.'
                )
            if len(request) > MAX_REQUEST_CHARS:
                raise Refused(
                    f"The request is too long. Keep it under {MAX_REQUEST_CHARS:,} characters; "
                    "one change at a time works best."
                )
            request = request.strip()
        best_of = body.get("best_of", 1)
        if best_of is None:
            best_of = 1
        if (
            not isinstance(best_of, int)
            or isinstance(best_of, bool)
            or not (1 <= best_of <= MAX_BEST_OF)
        ):
            raise Refused(
                f"Choose how many designs to make, a whole number from 1 to {MAX_BEST_OF}, not "
                f"{best_of!r}."
            )
        self.ordinary(name, "design")
        self._check_agreement(body, 1 if best_of == 1 else best_of + 1)

        def work(job: Job) -> dict[str, Any]:
            return self._design(job, self.open(name), request, best_of)

        return self.start("design", name, work, ai=True)

    @staticmethod
    def _check_agreement(body: dict[str, Any], runs: int) -> None:
        """Refuse an AI job the person has not agreed to, for exactly ``runs`` AI runs."""
        if body.get("understood") is not True:
            raise Refused(
                "The AI designer was not started. It sends pictures and a description of your "
                "model to the AI provider and uses your own Claude Code login, so it starts only "
                "after you have read that and agreed. Use the AI designer button on the project "
                "page and confirm there."
            )
        agreed = body.get("understood_runs")
        if not isinstance(agreed, int) or isinstance(agreed, bool) or agreed != runs:
            raise Refused(
                f"The AI designer was not started: this would start {_plural(runs, 'AI run')}, "
                "which is not the number you agreed to. Open the AI designer again, check how "
                "many designs to try, and confirm."
            )

    def design_in_passes(self, name: str, body: dict[str, Any]) -> Job:
        """``{"mode": "passes", "rounds": 0 to 2}``: the studio designs the model in passes."""
        from bricksnap.designer import studio

        if body.get("request") is not None:
            raise Refused(
                "Designing in passes takes no request: it designs the whole model. Once it is "
                "done, ask for one change in your own words."
            )
        if body.get("best_of") not in (None, 1):
            raise Refused(
                "Designing in passes makes one design, so it cannot be combined with trying "
                "several designs. Every pass is kept as a version to compare instead."
            )
        rounds = body.get("rounds", studio.DEFAULT_ROUNDS)
        if (
            not isinstance(rounds, int)
            or isinstance(rounds, bool)
            or not (0 <= rounds <= MAX_STUDIO_ROUNDS)
        ):
            raise Refused(
                "Choose how many rounds of critic and fix, a whole number from 0 to "
                f"{MAX_STUDIO_ROUNDS}, not {rounds!r}."
            )
        self.ordinary(name, "design")
        self._check_agreement(body, studio_runs(rounds))

        def work(job: Job) -> dict[str, Any]:
            return self._design_in_passes(job, self.open(name), rounds)

        return self.start("design", name, work, ai=True)

    def _design_in_passes(self, job: Job, project: Project, rounds: int) -> dict[str, Any]:
        """Run the studio, with its passes and versions shown as the job's progress. The
        studio keeps its own versions; this keeps none."""
        from bricksnap.designer import runner, studio
        from bricksnap.pipeline import rough_build

        load_design(project)  # fail now, clearly, if there is nothing to design
        load_build(project)
        names = [*studio.DEFAULT_PASSES, *(["critic", "fix"] * rounds)]
        job.passes = [
            {"pass": p, "job": studio.PASSES[p].job, "state": "waiting", "version": None}
            for p in names
        ]
        if runner.has_brief(project):
            job.say(
                "This designs the model again, in passes. The model as it is now stays in the "
                "list of versions"
            )
        else:
            job.say("This is a first design of the model, in passes")
        job.say(f"Starting up to {_plural(len(names), 'AI run')} one after another")
        words = StudioProgress(project)

        def hear(event: dict[str, Any]) -> None:
            line = words.line(event)
            if line is not None:
                job.say(line)
            kind, index = event.get("event"), event.get("index")
            if kind in ("pass_started", "pass_ended") and isinstance(index, int):
                entry = (
                    job.passes[index - 1] if job.passes and 0 < index <= len(job.passes) else None
                )
                if entry is not None:
                    if kind == "pass_started":
                        entry["state"] = "running"
                    elif event.get("skipped"):
                        entry["state"] = "skipped"
                    else:
                        entry["state"] = "done" if event.get("ok") else "failed"
                        entry["version"] = event.get("version")
            if kind is None:
                for said in designer_progress(event):
                    job.say(said)

        try:
            result = studio.run_studio(project, on_event=hear, rounds=rounds)
        except ValueError as e:  # checked before anything ran
            raise JobFailed(str(e)) from e
        project = Project(project.path)
        made = [p.version for p in result.passes if p.version is not None]
        build = None
        if project.has_build() and project.build_is_current():
            rough_build(project)  # the plain conversion stays beside it
            self._refresh_downloads(job, project)
            build = load_build(project)
        if not result.ok:
            if not made:
                kept = "No pass made a new version."
            elif len(made) == 1:
                kept = f"What the passes made is kept as version {made[0]}."
            else:
                listed = ", ".join(str(n) for n in made[:-1]) + f" and {made[-1]}"
                kept = f"What the passes made is kept as versions {listed}."
            raise JobFailed(
                f"{runner.redact(result.error or 'The passes stopped without saying why.')} "
                f"{kept} You can look at every version in the list of versions."
            )
        if build is None:
            raise JobFailed(
                "The passes finished, but the model has no build that matches its design. "
                'Press "Build the bricks again".'
            )
        out = self._outcome(job, project, build)
        out.update(kind="passes", version=result.version, sessions=result.sessions, versions=made)
        return out

    def _design(
        self, job: Job, project: Project, request: str | None, best_of: int
    ) -> dict[str, Any]:
        from bricksnap.designer import judge, runner
        from bricksnap.pipeline import rebuild, render_card, render_compare, rough_build

        design_before = load_design(project)  # fail now, clearly, if there is nothing to design
        kind = runner.run_kind(project, request)
        adopt_versions(project, say=job.say)
        what, label, note = design_label(kind, request, best_of)
        if kind == runner.EDIT:
            job.say(f'This is one change to a model that is already designed: "{request}"')
            job.say("Building the model as it is now, so the change starts from it")
            rebuild(project)
            adopt_versions(project, say=job.say)
        elif runner.has_brief(project):
            job.say("This is another full design pass: the designer may change any part of it")
        elif request:
            job.say(f'This is a first design of the model, with your wish: "{request}"')
        else:
            job.say("This is a first design of the model")
        options: dict[str, Any] = {}
        if request is not None:
            options["instruction"] = request

        if best_of > 1:
            job.say(
                f"Starting {best_of + 1} AI runs one after another: {best_of} designs and one "
                "judging run"
            )

            def tell(event: dict[str, Any]) -> None:
                line = best_of_progress(event)
                if line:
                    job.say(line)

            result = judge.design_best_of(project, best_of, on_event=tell, **options)
            if result.winner is None:
                raise JobFailed(
                    (result.error or "No design could be kept.")
                    + " Your project was left as it was. The designs that were made are in its "
                    "candidates folder, to look at."
                )
            project = Project(project.path)
            rough_build(project)
            render_card(project)
            self._refresh_downloads(job, project)
            self._keep(job, project, what, label, note)
            build = load_build(project)
            out = self._outcome(job, project, build)
            out.update(
                kind=kind,
                winner=result.winner,
                by_measurement=result.by_measurement,
                summary=runner.redact(result.summary or ""),
            )
            return out

        job.say("The designer is getting ready")

        def hear(event: dict[str, Any]) -> None:
            for line in designer_progress(event):
                job.say(line)

        run = runner.run_designer(project, on_event=hear, **options)
        if run.ok:
            job.say(f"The designer finished after {_plural(run.turns, 'turn')}")
        job.say("Rebuilding the bricks from the final design")
        project = Project(project.path)
        build = rebuild(project)
        render_compare(project)
        render_card(project)
        rough_build(project)
        self._refresh_downloads(job, project)
        if not run.ok:
            label += " (stopped before it finished)"
        self._keep(job, project, what, label, note)
        log = load_design(project).log
        out = self._outcome(job, project, build)
        out.update(
            kind=kind,
            edits=max(0, len(log) - len(design_before.log)),
            said=runner.redact(run.final_text.strip()),
        )
        if not run.ok:
            raise JobFailed(
                f"The AI designer did not finish: {run.error or 'it stopped without saying why.'} "
                "The changes it made before it stopped are kept, and the bricks were rebuilt "
                "from them."
            )
        return out

    def export(self, name: str) -> Job:
        self.ordinary(name, "export")

        def work(job: Job) -> dict[str, Any]:
            return self._export(job, self.open(name))

        return self.start("export", name, work)

    def _export(self, job: Job, project: Project) -> dict[str, Any]:
        """What ``bricksnap export`` does and says, in progress lines."""
        from bricksnap.catalog import load_catalog
        from bricksnap.cli import _describe_line, _sentence
        from bricksnap.export import parts_list, unlisted, write_exports
        from bricksnap.ldraw import to_ldraw

        build = load_build(project)
        catalog = load_catalog()
        try:
            lines = parts_list(build, catalog)  # also checks every part and colour value
        except (ValueError, TypeError) as e:
            raise ProjectError(
                f"The build file of this project is damaged and cannot be read: {_sentence(e)} "
                "Build it again."
            ) from e
        try:
            text: str | None = to_ldraw(build, catalog, title=project.name)
            problem = ""
        except ValueError as e:  # a part that is not in the parts table
            text, problem = None, _sentence(e)
        except (TypeError, KeyError):
            text, problem = None, "the build holds a value of the wrong kind, so it may be damaged."
        if text is not None:
            project.ldraw_path.write_text(text, encoding="utf-8")
            job.say(
                "Wrote the LDraw file, build.ldr: it opens in BrickLink Studio, LeoCAD or LDView"
            )
        else:
            job.say(f"Could not write the LDraw file: {problem}")
        write_exports(project, catalog)
        job.say("Wrote the parts list, parts.csv: it opens in any spreadsheet program")
        job.say("Wrote the BrickLink wanted list, wanted_list.xml")
        missing = unlisted(lines)
        total = sum(line.quantity for line in lines)
        if lines:
            job.say(
                f"The model needs {_plural(total, 'part')} of "
                f"{_plural(len(lines), 'different kind')}"
            )
        else:
            job.say("The build has no parts, so there is nothing to buy")
        for line in missing:
            job.say(f"Not on the wanted list, add it by hand: {_describe_line(line)}")
        current = True
        if project.has_design():
            current = project.build_is_current(load_design(project), build)
        files = [
            f for f in ("build.ldr", "parts.csv", "wanted_list.xml") if (project.path / f).is_file()
        ]
        return {
            "project": project.path.name,
            "files": files,
            "parts": total,
            "kinds": len(lines),
            "unlisted": len(missing),
            "wanted_list_usable": bool(lines) and len(missing) < len(lines),
            "ldraw_written": text is not None,
            "current": current,
        }

    def instructions(self, name: str) -> Job:
        self.ordinary(name, "instructions")

        def work(job: Job) -> dict[str, Any]:
            from bricksnap.instructions import make_instructions

            project = self.open(name)
            build = load_build(project)
            job.say("Making the instruction booklet: one picture for each step")
            make_instructions(project)
            steps = len({p.step for p in build.parts})
            job.say(
                f"Wrote the booklet: {_plural(len(build.parts), 'part')} in "
                f"{_plural(steps, 'step')}"
            )
            return {
                "project": project.path.name,
                "files": ["instructions.pdf", "instructions.html"],
                "steps": steps,
            }

        return self.start("instructions", name, work)

    def restore(self, name: str, body: dict[str, Any]) -> Job:
        number = body.get("version")
        if not isinstance(number, int) or isinstance(number, bool) or number < 1:
            raise Refused("Choose which version to go back to, by its number.")
        self.ordinary(name, "restore")

        def work(job: Job) -> dict[str, Any]:
            return self._restore(job, self.open(name), number)

        return self.start("restore", name, work)

    def _restore(self, job: Job, project: Project, n: int) -> dict[str, Any]:
        from bricksnap import versions
        from bricksnap.pipeline import render_card, render_compare, rough_build

        version = next((v for v in versions.versions(project) if v.n == n), None)
        if version is None:
            raise JobFailed(
                f"This model has no version {n}, so nothing was changed. Reload the page to see "
                "the versions it has."
            )
        job.say(f"Going back to version {n}: {version.label}")
        job.say("Keeping the model as it is now in the list of versions")
        keep_present(project, say=job.say)
        build = versions.restore(project, n)
        project = Project(project.path)
        job.say("Drawing a picture of the model beside the bricks")
        render_compare(project)
        render_card(project)
        rough_build(project)  # the plain conversion stays beside it
        self._refresh_downloads(job, project)
        out = self._outcome(job, project, build)
        out["version"] = n
        return out

    # ---- models the AI builds from parts (experimental) --------------------------------------

    @staticmethod
    def _free_agreement(body: dict[str, Any]) -> None:
        """Refuse an AI build the person has not agreed to (one AI run)."""
        agreed = body.get("understood_runs")
        if (
            body.get("understood") is not True
            or not isinstance(agreed, int)
            or isinstance(agreed, bool)
            or agreed != 1
        ):
            raise Refused(
                "The AI builder was not started. It sends the words you typed (and, when you "
                "chose a model to look like, pictures of it) to the AI provider, starts one AI "
                "run and uses your own Claude Code login, so it starts only after you have read "
                "that and agreed. Read the box above the start button and tick it."
            )

    @staticmethod
    def _free_words(body: dict[str, Any], key: str, example: str) -> str:
        words = body.get(key)
        if not isinstance(words, str) or not words.strip():
            raise Refused(f'Say in words what you want, for example "{example}".')
        if len(words) > MAX_REQUEST_CHARS:
            raise Refused(
                f"That is too long. Keep it under {MAX_REQUEST_CHARS:,} characters; a sentence "
                "or two works best."
            )
        return freebuild.clean(words, MAX_REQUEST_CHARS)

    @staticmethod
    def _free_ready() -> None:
        problem = freebuild.missing()
        if problem:
            raise Refused(problem)

    def new_free(self, body: dict[str, Any]) -> Job:
        """``POST /api/free``: a new model the AI builds from parts, from the person's words."""
        words = self._free_words(body, "words", "a small red fire truck")
        name = body.get("name")
        if name is not None and not isinstance(name, str):
            raise Refused("The name must be text.")
        name = clean_text(name or "", MAX_NAME_CHARS)
        parts = body.get("parts", freebuild.DEFAULT_PARTS)
        if (
            not isinstance(parts, int)
            or isinstance(parts, bool)
            or not freebuild.MIN_PARTS <= parts <= freebuild.MAX_PARTS
        ):
            raise Refused(
                f"Choose about how many parts, a whole number from {freebuild.MIN_PARTS} to "
                f"{freebuild.MAX_PARTS}."
            )
        reference = body.get("reference")
        ref_folder = None
        if reference is not None:
            if not isinstance(reference, str):
                raise Refused("Choose the model to look like from the list.")
            ref_folder = self.ordinary(reference, "reference")
            if not (ref_folder / "design.npz").is_file():
                raise Refused(f'"{reference}" has no 3D model to show the AI. Choose another.')
        self._free_agreement(body)
        self._free_ready()
        job_id = secrets.token_hex(8)
        folder = self.reserve(name or freebuild.name_from(words), job_id)

        def work(job: Job) -> dict[str, Any]:
            path = freebuild.create(
                self.root, words, name=name or None, parts=parts, reference=reference, folder=folder
            )
            references = []
            if ref_folder is not None:
                job.say("Drawing the model to look like from five sides, to show the AI")
                references.append(freebuild.reference_sheet(ref_folder, path / "reference.png"))
            return self._free_run(job, path, None, references)

        try:
            return self.start("free", folder, work, ai=True, job_id=job_id, reserved=True)
        except BaseException:
            self.release(folder, job_id)
            raise

    def change(self, name: str, body: dict[str, Any]) -> Job:
        """``POST /api/p/<project>/change``: the AI changes a model it built, in words."""
        words = self._free_words(body, "words", "make the roof blue")
        self.free(name)
        self._free_agreement(body)
        self._free_ready()

        def work(job: Job) -> dict[str, Any]:
            return self._free_run(job, self.free(name), words, [])

        return self.start("change", name, work, ai=True)

    def _free_run(
        self, job: Job, folder: Path, words: str | None, references: list[Path]
    ) -> dict[str, Any]:
        if words is None:
            job.say("This is a new model: the AI builds it part by part from the parts library")
        else:
            job.say(f'This is one change to the model: "{_short(words, 200)}"')
        job.say("One AI run; it usually takes ten to twenty minutes")
        entry = freebuild.build(folder, words, on_say=job.say, references=references)
        verdict = entry.get("summary") or "not checked"
        job.say(f"Done: {verdict}")
        return {
            "project": folder.name,
            "run": entry["n"],
            "parts": entry["parts"],
            "clean": entry["clean"],
            "summary": entry.get("summary") or "",
        }

    def use(self, name: str, body: dict[str, Any]) -> Job:
        """``POST /api/p/<project>/use``: ``{"run": n}`` brings back an earlier run."""
        n = body.get("run")
        if not isinstance(n, int) or isinstance(n, bool) or n < 1:
            raise Refused("Choose which run to bring back, by its number.")
        self.free(name)

        def work(job: Job) -> dict[str, Any]:
            entry = freebuild.restore(self.free(name), n)
            job.say(f"Run {n} is the model shown now; the other runs are still in the list")
            return {"project": name, "run": n, "parts": entry.get("parts")}

        return self.start("use", name, work)

    def delete(self, name: str) -> dict[str, Any]:
        """Move the project's folder into ``.trash``; nothing is deleted outright."""
        with self.lock:
            folder = self.project_dir(name)
            if folder is None:
                raise Refused(f"There is no project called {name!r} here.", HTTPStatus.NOT_FOUND)
            running = self.jobs.get(self.busy.get(name, ""))
            if running is not None:
                raise Refused(self.busy_message(running), HTTPStatus.CONFLICT)
            trash = self.root / TRASH_DIR
            trash.mkdir(exist_ok=True)
            target = trash / name
            if os.path.lexists(target):
                stamp = time.strftime("%Y%m%d-%H%M%S")
                target = trash / f"{name}-{stamp}"
                n = 1
                while os.path.lexists(target):
                    n += 1
                    target = trash / f"{name}-{stamp}-{n}"
            os.rename(folder, target)
        return {
            "deleted": name,
            "moved_to": f"{TRASH_DIR}/{target.name}",
            "folder": str(self.shown_root / TRASH_DIR / target.name),
        }


def parse_up(value: str | None) -> str | None:
    """The optional ``up`` field of the upload form: None (as the file says), "x", "y" or
    "z"; anything else is refused."""
    word = (value or "").strip().lower()
    if not word:
        return None
    if word not in ("x", "y", "z"):
        raise Refused("Which way is up must be x, y or z, or left as the file says.")
    return word


def parse_piece(value: str | None) -> str | int | None:
    """The optional ``piece`` field of the upload form: None when it is empty."""
    from bricksnap.pieces import parse_choice

    if value is None or not value.strip():
        return None
    try:
        return parse_choice(value)
    except SeedError as e:
        raise Refused(str(e)) from e


def parse_studs(value: str | None) -> int:
    """The size field of the form: a whole number of studs from 4 to 96 (16 when empty)."""
    if value is None or not value.strip():
        return DEFAULT_STUDS
    text = value.strip()
    if not text.isdigit() or not MIN_STUDS <= int(text) <= MAX_STUDS:
        raise Refused(
            f"The size must be a whole number of studs between {MIN_STUDS} and {MAX_STUDS} "
            f"(you gave {value.strip()[:20]!r}). One stud is 8 mm."
        )
    return int(text)


# ---- the request handler ------------------------------------------------------------------


def _read_page(name: str) -> str:
    return (VIEWER_DIR / name).read_text(encoding="utf-8")


def home_page(token: str) -> bytes:
    html = _read_page("home.html")
    if html.count(TOKEN_PLACEHOLDER) != 1:
        raise RuntimeError("viewer/home.html must hold the token placeholder exactly once")
    return html.replace(TOKEN_PLACEHOLDER, token).encode("utf-8")


def project_page(name: str, token: str) -> bytes:
    """viewer/index.html for project ``name`` (a slug), with the action bar added."""
    html = _read_page("index.html")
    swaps = (
        (
            "<body>",
            f'<body class="in-app" data-project="{name}" data-project-files="/p/{name}/files" '
            f'data-project-list="/p/{name}/project-files.json">',
        ),
        (
            "</head>",
            f'<meta name="bricksnap-token" content="{token}">\n'
            '<link rel="stylesheet" href="/viewer/app.css">\n</head>',
        ),
        ("</body>", '<script type="module" src="/viewer/app.js"></script>\n</body>'),
    )
    for old, new in swaps:
        if html.count(old) != 1:
            raise RuntimeError(f"viewer/index.html must hold {old} exactly once")
        html = html.replace(old, new)
    return html.encode("utf-8")


def free_page(name: str, token: str, folder: Path) -> bytes:
    """viewer/free.html for free-build project ``name`` (a slug), with the address of the
    turntable's first picture on ``<body>`` so it shows at once."""
    html = _read_page("free.html")
    for old in (TOKEN_PLACEHOLDER, "<body"):
        if html.count(old) != 1:
            raise RuntimeError(f"viewer/free.html must hold {old} exactly once")
    attrs = f'data-project="{name}"'
    frames = freebuild.turn_frames(folder)
    if frames:
        with contextlib.suppress(OSError):
            stamp = (folder / frames[0]).stat().st_mtime_ns
            attrs += f' data-first="/p/{name}/files/{frames[0]}?v={stamp}"'
    html = html.replace(TOKEN_PLACEHOLDER, token).replace("<body", f"<body {attrs}")
    return html.encode("utf-8")


def _make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class AppHandler(BaseHTTPRequestHandler):
        server_version = "BrickSnapApp/1"
        sys_version = ""
        timeout = REQUEST_TIMEOUT_S  # an idle connection must not hold a thread for ever

        # ---- answering ----------------------------------------------------------------

        def _send(
            self, status: int, ctype: str, data: bytes, body: bool = True, sandbox: bool = False
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            policy = "frame-ancestors 'none'" + ("; sandbox" if sandbox else "")
            self.send_header("Content-Security-Policy", policy)
            self.send_header("Referrer-Policy", "no-referrer")
            if self.close_connection:
                self.send_header("Connection", "close")
            self.end_headers()
            if body:
                self.wfile.write(data)

        def _json(self, status: int, value: Any, body: bool = True) -> None:
            data = json.dumps(value).encode("utf-8")
            self._send(status, CONTENT_TYPES[".json"], data, body)

        def _error(self, status: int, message: str, body: bool = True) -> None:
            self._json(status, {"error": message}, body)

        def _not_found(self, body: bool = True) -> None:
            self._send(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", b"Not found\n", body)

        def _fault(self, what: str) -> None:
            print(f"BrickSnap: a request for {self.path!r} failed:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            self.close_connection = True
            with contextlib.suppress(Exception):
                self._error(
                    HTTPStatus.INTERNAL_SERVER_ERROR, SOMETHING_WENT_WRONG.format(what=what)
                )

        # ---- GET ----------------------------------------------------------------------

        def _path(self) -> str | None:
            """The request's path, decoded once, or None when it is not acceptable."""
            raw = urlsplit(self.path).path
            if "\\" in raw or _ENCODED_SEPARATOR.search(raw):
                return None
            try:
                path = unquote(raw, errors="strict")
            except UnicodeDecodeError:
                return None
            if "\x00" in path or "\\" in path or not path.startswith("/"):
                return None
            return path

        def _serve(self, body: bool) -> None:
            if not is_local_host(self.headers.get("Host")):
                self._not_found(body)
                return
            path = self._path()
            if path is None:
                self._not_found(body)
                return
            try:
                self._route_get(path, body)
            except Refused as e:
                self._error(e.status, e.message, body)

        def _file(self, target: Path | None, body: bool, sandbox: bool = False) -> None:
            if target is None:
                self._not_found(body)
                return
            try:
                data = target.read_bytes()
            except OSError:
                self._not_found(body)
                return
            ctype = APP_TYPES.get(target.suffix.lower(), "application/octet-stream")
            self._send(HTTPStatus.OK, ctype, data, body, sandbox)

        def _route_get(self, path: str, body: bool) -> None:
            html = CONTENT_TYPES[".html"]
            if path in ("/", "/index.html"):
                self._send(HTTPStatus.OK, html, home_page(app.token), body)
            elif path.startswith("/viewer/"):
                self._file(safe_join(VIEWER_DIR, path[len("/viewer/") :]), body)
            elif path.startswith("/catalog/"):
                name = path[len("/catalog/") :]
                self._file(safe_join(CATALOG_DIR, name) if name in CATALOG_FILES else None, body)
            elif path == "/api/projects":
                self._json(HTTPStatus.OK, app.list_projects(), body)
            elif path.startswith("/api/jobs/") and path.endswith(f"/{PIECES_PICTURE}"):
                job_id = path[len("/api/jobs/") : -len(PIECES_PICTURE) - 1]
                self._file(app.pieces_picture(job_id), body)
            elif path.startswith("/api/jobs/"):
                self._json(HTTPStatus.OK, app.job_json(path[len("/api/jobs/") :]), body)
            elif path.startswith("/api/p/"):
                self._json(HTTPStatus.OK, app.project_info(path[len("/api/p/") :]), body)
            elif path.startswith("/p/"):
                self._project_get(path[len("/p/") :], body)
            else:
                self._not_found(body)

        def _project_get(self, rest: str, body: bool) -> None:
            name, _, sub = rest.partition("/")
            folder = app.project_dir(name)
            if folder is None and sub == "":
                page = NOT_FOUND_PAGE.encode("utf-8")
                self._send(HTTPStatus.NOT_FOUND, CONTENT_TYPES[".html"], page, body)
            elif folder is None:
                self._not_found(body)
            elif sub == "" and freebuild.is_free(folder):
                page = free_page(name, app.token, folder)
                self._send(HTTPStatus.OK, CONTENT_TYPES[".html"], page, body)
            elif sub == "":
                self._send(
                    HTTPStatus.OK, CONTENT_TYPES[".html"], project_page(name, app.token), body
                )
            elif sub == "project-files.json" and freebuild.is_free(folder):
                self._not_found(body)
            elif sub == "project-files.json":
                self._send(HTTPStatus.OK, CONTENT_TYPES[".json"], project_files(folder), body)
            elif sub.startswith("files/"):
                self._file(served_file(folder, sub[len("files/") :]), body, sandbox=True)
            else:
                self._not_found(body)

        def do_GET(self) -> None:  # name fixed by http.server
            try:
                self._serve(body=True)
            except ConnectionError:
                raise
            except Exception:
                self._fault("showing a page")

        def do_HEAD(self) -> None:
            try:
                self._serve(body=False)
            except ConnectionError:
                raise
            except Exception:
                self._fault("showing a page")

        # ---- POST ---------------------------------------------------------------------

        def _same_site(self, origin: str) -> bool:
            port = getattr(self.server, "server_port", None)
            allowed = {f"http://{host}:{port}" for host in ("127.0.0.1", "localhost", "[::1]")}
            return origin.strip().lower() in allowed

        def _length(self, limit: int, too_big: str) -> int:
            value = self.headers.get("Content-Length")
            if value is None:
                self.close_connection = True
                if self.headers.get("Transfer-Encoding"):
                    raise Refused(
                        "The request did not say how long it is. Try again from the BrickSnap "
                        "page.",
                        HTTPStatus.LENGTH_REQUIRED,
                    )
                return 0
            if not value.strip().isdigit():
                self.close_connection = True
                raise Refused("The request could not be read.")
            length = int(value)
            if length > limit:
                self.close_connection = True  # the rest of the body is never read
                raise Refused(too_big, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return length

        def _read_json(self) -> dict[str, Any]:
            length = self._length(MAX_JSON_BYTES, "The request is too long.")
            data = self.rfile.read(length) if length else b""
            if not data.strip():
                return {}
            try:
                value = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                raise Refused("The request could not be read.") from None
            if not isinstance(value, dict):
                raise Refused("The request could not be read.")
            return value

        def do_POST(self) -> None:
            try:
                self._post()
            except ConnectionError:
                raise
            except Refused as e:
                self._error(e.status, e.message)
            except Exception as e:
                message = plain_message(e)
                if message is None:
                    self._fault("starting that")
                else:
                    self._error(HTTPStatus.BAD_REQUEST, message)

        def _post(self) -> None:
            if not is_local_host(self.headers.get("Host")):
                self.close_connection = True
                self._not_found()
                return
            origin = self.headers.get("Origin")
            if origin is not None and not self._same_site(origin):
                self.close_connection = True
                raise Refused(
                    "This request came from another web site, so BrickSnap refused it.",
                    HTTPStatus.FORBIDDEN,
                )
            token = self.headers.get(TOKEN_HEADER, "")
            if not hmac.compare_digest(token.encode("utf-8", "replace"), app.token.encode()):
                self.close_connection = True
                raise Refused(
                    "This request did not come from a BrickSnap page that is open now, so it "
                    "was refused. Reload the page and try again.",
                    HTTPStatus.FORBIDDEN,
                )
            path = self._path()
            if path == "/api/projects":
                self._json(HTTPStatus.ACCEPTED, {"job": self._upload().id})
                return
            if path is not None and path.startswith("/api/jobs/") and path.endswith("/choose"):
                job_id = path[len("/api/jobs/") : -len("/choose")]
                self._json(HTTPStatus.OK, app.choose(job_id, self._read_json()))
                return
            if path == "/api/free":
                job = app.new_free(self._read_json())
                self._json(HTTPStatus.ACCEPTED, {"job": job.id, "project": job.project})
                return
            if path is not None and path.startswith("/api/p/"):
                name, _, action = path[len("/api/p/") :].partition("/")
                if action in ACTIONS and SLUG_RE.fullmatch(name):
                    body = self._read_json()
                    if action == "delete":
                        self._json(HTTPStatus.OK, app.delete(name))
                        return
                    if action == "design":
                        job = app.design(name, body)
                    elif action == "restore":
                        job = app.restore(name, body)
                    elif action == "change":
                        job = app.change(name, body)
                    elif action == "use":
                        job = app.use(name, body)
                    else:
                        job = getattr(app, action)(name)
                    self._json(HTTPStatus.ACCEPTED, {"job": job.id})
                    return
            self.close_connection = True
            self._error(HTTPStatus.NOT_FOUND, "There is no such action.")

        def _upload(self) -> Job:
            """Read a new model from the form and start the job that builds it."""
            ctype = Message()
            ctype["content-type"] = self.headers.get("Content-Type", "")
            boundary = ctype.get_param("boundary")
            if ctype.get_content_type() != "multipart/form-data" or not isinstance(boundary, str):
                self.close_connection = True
                raise Refused("Send the model with the form on the BrickSnap page.")
            if not 1 <= len(boundary) <= 200:
                self.close_connection = True
                raise Refused("The form that was sent could not be read. Try again.")
            length = self._length(MAX_UPLOAD_BYTES + FORM_OVERHEAD, too_large_message())
            if length == 0:
                self.close_connection = True
                raise Refused(
                    "The request did not say how long it is. Try again from the BrickSnap page.",
                    HTTPStatus.LENGTH_REQUIRED,
                )
            job_id = secrets.token_hex(8)
            staging = app.root / INCOMING_DIR / job_id
            chosen: dict[str, Path] = {}

            def save_file(browser_name: str) -> Path:
                base = browser_name.replace("\\", "/").rsplit("/", 1)[-1]
                suffix = Path(base).suffix.lower()
                if suffix not in MODEL_SUFFIXES:
                    raise Refused(wrong_suffix_message(clean_text(base, 120) or "that file"))
                staging.mkdir(parents=True, exist_ok=True)
                chosen["file"] = staging / (slug(Path(base).stem)[:60].strip("-") + suffix)
                return chosen["file"]

            folder = None
            try:
                fields, browser_name, size = read_form(
                    self.rfile, length, boundary.encode("latin-1"), save_file
                )
                if browser_name is None or "file" not in chosen:
                    raise Refused("Choose a 3D model file first.")
                if size == 0:
                    raise Refused(f"{clean_text(browser_name, 120)} is empty. Choose another file.")
                if chosen["file"].suffix == ".gltf" and gltf_needs_other_files(chosen["file"]):
                    raise Refused(GLTF_SEPARATE.format(name=clean_text(browser_name, 120)))
                fields["_file_name"] = browser_name.replace("\\", "/").rsplit("/", 1)[-1]
                parse_studs(fields.get("studs"))  # refuse a wrong size before anything starts
                parse_piece(fields.get("piece"))  # and a choice of piece that makes no sense
                parse_up(fields.get("up"))
                wanted = clean_text(fields.get("name", ""), MAX_NAME_CHARS)
                folder = app.reserve(wanted or Path(fields["_file_name"]).stem, job_id)
                return app.new_project(job_id, folder, staging, chosen["file"], fields)
            except BaseException:
                self.close_connection = True
                shutil.rmtree(staging, ignore_errors=True)
                if folder is not None:
                    app.release(folder, job_id)
                raise

        def _refuse_method(self) -> None:
            data = b"Method not allowed\n"
            self.close_connection = True
            self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
            self.send_header("Allow", "GET, HEAD, POST")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        do_PUT = do_DELETE = do_PATCH = do_OPTIONS = _refuse_method

        def log_message(self, format: str, *args: object) -> None:
            pass  # keep the terminal quiet; the pages poll every second or two

    return AppHandler


class AppServer(ViewerServer):
    """The app's server; ``app`` holds its projects folder, token and jobs (the tests use it)."""

    app: App


def make_app_server(projects_dir: str | Path = "projects", port: int = 8765) -> AppServer:
    root = Path(projects_dir)
    number = _port_number(port)
    if root.exists() and not root.is_dir():
        raise ProjectError(
            f"{root} is a file, not a folder. Give a folder to keep the projects in."
        )
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise ProjectError(_system_error(e)) from None
    app = App(root)
    try:
        server = AppServer(("127.0.0.1", number), _make_handler(app))
    except (OverflowError, ValueError):
        raise ProjectError(
            f"The port must be a whole number from 0 to 65535, not {port!r}."
        ) from None
    except OSError as exc:
        if exc.errno == errno.EADDRINUSE:
            raise ProjectError(
                f"Port {port} is already in use, perhaps by another BrickSnap window. Close it "
                "or choose another port with --port."
            ) from None
        raise ProjectError(f"Could not start BrickSnap on port {port}: {exc.strerror}.") from None
    server.app = app
    app.clear_stale_uploads()
    return server


def serve_app(
    projects_dir: str | Path = "projects", port: int = 8765, open_browser: bool = True
) -> None:
    server = make_app_server(projects_dir, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"BrickSnap is running at {url}")
    print(f"Your projects are kept in {Path(projects_dir)}.")
    print("Leave this window open while you use BrickSnap. Press Ctrl+C to stop it.")
    sys.stdout.flush()
    if open_browser:
        threading.Timer(0.3, webbrowser.open, args=(url,)).start()
    threading.Thread(target=server.app.make_missing_cards, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBrickSnap stopped.")
    finally:
        server.server_close()
