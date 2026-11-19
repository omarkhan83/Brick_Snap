"""Versions of a project: every state worth comparing is kept, and any can be brought back.

A model changes in steps: the plain conversion, an AI design, each pass of the studio, each
typed change. Each step is kept as a numbered version so a person can put any two side by
side and go back to one they liked better.

CONTRACT (tests go in tests/test_versions.py)

Files, inside the project folder:
    versions/index.json    {"current": n or null, "last": highest number ever given,
                           "versions": [entry, ...]}, oldest first
    versions/0001/         design.npz, design.json: the Design as it was
                           build.json: its checked Build
                           card.png: one clean picture (``pipeline.render_card``), when it
                           could be drawn
An entry: ``{"n", "kind", "label", "note", "created" (UTC, ISO 8601), "parts", "valid",
"design_id", "brief"}``. ``brief`` is the designer's brief as it stood (None before any AI
design); ``design_id`` is ``Design.fingerprint()``.

``KINDS``: "converted" (the conversion, finished by the software alone), "designed" (an AI
designer's design), "edit" (one typed change), "pass" (one pass of the studio; the label
names it), "manual" (edit operations applied by hand).

``record(project, kind, label, note="") -> int``
    Keep the project's current Design and Build as a new version and make it the current
    one. The brief is read from project.json as it is on disk at that moment, not from the
    ``project`` object, which may have been opened before the designer's tools wrote it.
    The Build must be the one made from the Design (``Project.build_is_current``),
    otherwise ``ProjectError`` says to build first. If nothing differs from the current
    version (same Design fingerprint, same parts, same brief) no version is added and that
    version's number is returned, so building again does not pile up copies. Numbers start
    at 1 and are never reused. The version's folder is written under a temporary name and
    moved into place, and the index is written last, so a reader never sees half a version.
``versions(project) -> list[Version]``, oldest first; ``current(project) -> int | None``.
    A missing or damaged index is an empty list, not an error (the project simply has no
    versions yet); entries whose folder is gone are left out.
``version_dir(project, n) -> Path``; ``ProjectError`` when there is no such version.
``restore(project, n) -> Build``
    Make version ``n`` the project's current state: its Design and Build are copied back,
    build.ldr is written again from the Build, the brief in project.json is set to the
    version's brief (removed when it had none, so the next AI run is a first design again),
    renders/card.png is replaced, and ``current`` becomes ``n``. No version is added and no
    other version, the base design or the seed is touched. Files made from the old build
    (the parts list, the wanted list, the booklet, the comparison picture) are the caller's
    to refresh.
``adopt(project) -> int | None``
    A project made before versions were kept gets its present state as its first version:
    when it has no version yet and its Build is the one made from its Design, that state is
    recorded, as "designed" ("The design as it was") when project.json has a brief and as
    "converted" ("The model as it was") otherwise, and its number returned. A project that
    already has versions, or whose Build is missing or older than its Design, is left alone
    (None). The web app and the command line call it before a job or command changes the
    model, so the state the person had is never lost.

This module holds no modelling logic: it copies files and reads ``Project``.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bricksnap.catalog import load_catalog
from bricksnap.ldraw import to_ldraw
from bricksnap.project import Project, ProjectError
from bricksnap.types import Build, Design, write_text_atomic

KINDS = ("converted", "designed", "edit", "pass", "manual")
VERSIONS_DIR = "versions"
INDEX = "index.json"


@dataclass(frozen=True)
class Version:
    n: int
    kind: str
    label: str
    note: str
    created: str
    parts: int
    valid: bool
    design_id: str
    brief: dict[str, Any] | None


def _root(project: Project) -> Path:
    return project.path / VERSIONS_DIR


def _folder(project: Project, n: int) -> Path:
    return _root(project) / f"{n:04d}"


def _read_index(project: Project) -> tuple[int | None, list[Version]]:
    try:
        data = json.loads((_root(project) / INDEX).read_text(encoding="utf-8"))
        found = []
        for entry in data["versions"]:
            brief = entry.get("brief")
            version = Version(
                n=int(entry["n"]),
                kind=str(entry["kind"]),
                label=str(entry["label"]),
                note=str(entry.get("note", "")),
                created=str(entry.get("created", "")),
                parts=int(entry.get("parts", 0)),
                valid=bool(entry.get("valid", False)),
                design_id=str(entry.get("design_id", "")),
                brief=brief if isinstance(brief, dict) else None,
            )
            if (_folder(project, version.n) / "build.json").is_file():
                found.append(version)
        now = data.get("current")
        now = now if isinstance(now, int) and any(v.n == now for v in found) else None
        return now, found
    except (OSError, ValueError, KeyError, TypeError):
        return None, []


def _last(project: Project) -> int:
    """The highest number ever given out, as far as the index remembers."""
    try:
        last = json.loads((_root(project) / INDEX).read_text(encoding="utf-8")).get("last")
        return last if isinstance(last, int) else 0
    except (OSError, ValueError, AttributeError):
        return 0


def _write_index(project: Project, now: int | None, found: list[Version]) -> None:
    last = max([_last(project)] + [v.n for v in found])
    data = {"current": now, "last": last, "versions": [asdict(v) for v in found]}
    write_text_atomic(_root(project) / INDEX, json.dumps(data, indent=1) + "\n")


def versions(project: Project) -> list[Version]:
    return _read_index(project)[1]


def current(project: Project) -> int | None:
    return _read_index(project)[0]


def version_dir(project: Project, n: int) -> Path:
    if not any(v.n == n for v in versions(project)):
        raise ProjectError(f"This project has no version {n}.")
    return _folder(project, n)


def _meta(project: Project) -> dict[str, Any]:
    """The project's notes as they are on disk now. ``project`` may have been opened before
    another process (the designer's tools) wrote the brief, so its own copy is not trusted."""
    try:
        data = json.loads((project.path / "project.json").read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return dict(project.meta)


def _brief(project: Project) -> dict[str, Any] | None:
    brief = _meta(project).get("brief")
    return brief if isinstance(brief, dict) else None


def record(project: Project, kind: str, label: str, note: str = "") -> int:
    if kind not in KINDS:
        raise ValueError(f"unknown kind of version {kind!r}; use one of {', '.join(KINDS)}")
    if not project.has_design() or not project.has_build():
        raise ProjectError("There is nothing to keep as a version yet: build the project first.")
    design, build = project.load_design(), project.load_build()
    if not project.build_is_current(design, build):
        raise ProjectError(
            "The build is older than the design, so it cannot be kept as a version: "
            "build the project first."
        )
    now, found = _read_index(project)
    brief = _brief(project)
    latest = next((v for v in found if v.n == now), None)
    if latest is not None and latest.design_id == build.design_id and latest.brief == brief:
        with contextlib.suppress(OSError):
            if (_folder(project, latest.n) / "build.json").read_bytes() == (
                project.build_path.read_bytes()
            ):
                return latest.n
    root = _root(project)
    root.mkdir(exist_ok=True)
    taken = [int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit()]
    n = max([_last(project)] + [v.n for v in found] + taken) + 1
    staging = root / f".new-{os.getpid()}-{n}"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        design.save(staging / "design.npz", staging / "design.json")
        shutil.copyfile(project.build_path, staging / "build.json")
        card = project.renders_dir / "card.png"
        if card.is_file():
            shutil.copyfile(card, staging / "card.png")
        os.rename(staging, _folder(project, n))
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    report = build.report
    entry = Version(
        n=n,
        kind=kind,
        label=label,
        note=note,
        created=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        parts=len(build.parts),
        valid=bool(report is not None and report.ok),
        design_id=build.design_id,
        brief=brief,
    )
    _write_index(project, n, [*found, entry])
    return n


def adopt(project: Project) -> int | None:
    if versions(project) or not project.has_design() or not project.has_build():
        return None
    if not project.build_is_current():
        return None
    if _brief(project) is not None:
        return record(project, "designed", "The design as it was")
    return record(project, "converted", "The model as it was")


def restore(project: Project, n: int) -> Build:
    folder = version_dir(project, n)
    now, found = _read_index(project)
    version = next(v for v in found if v.n == n)
    design = Design.load(folder / "design.npz", folder / "design.json")
    build = Build.load(folder / "build.json")
    project.save_design(design)
    project.save_build(build)
    write_text_atomic(project.ldraw_path, to_ldraw(build, load_catalog(), title=project.name))
    meta = _meta(project)  # as on disk now, so nothing another process wrote is lost
    if version.brief is None:
        meta.pop("brief", None)
    else:
        meta["brief"] = version.brief
    project.meta = meta
    project.save_meta()
    card = project.renders_dir / "card.png"
    if (folder / "card.png").is_file():
        card.parent.mkdir(exist_ok=True)
        shutil.copyfile(folder / "card.png", card)
    else:
        card.unlink(missing_ok=True)
    _write_index(project, n, found)
    return build
