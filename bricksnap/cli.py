"""The ``bricksnap`` command.

CONTRACT (tests go in tests/test_cli.py)

``main(argv=None) -> int`` parses arguments with argparse and returns the exit code.
Everything goes through ``bricksnap.pipeline`` and ``bricksnap.project`` so the command
line, the AI designer's tools and the tests run the same code. Output is plain language for
a non-programmer. SeedError and ProjectError are printed as "Error: <message>" and return 2;
there are no tracebacks for mistakes a user can make.

    bricksnap new MODEL --studs N [--name NAME] [--dir projects] [--up x|y|z] [--hollow]
        Create a project from a model file, then do everything ``build`` does. Print where
        the project is.
    bricksnap build PROJECT
        Design -> Build -> checks. Writes build.json, build.ldr and renders/compare.png, and
        prints the report text. Returns 0 when the report is ok, 1 when it is not.
    bricksnap check PROJECT
        Re-run the checks on the saved build and print the report. 0 if ok, else 1.
    bricksnap render PROJECT [--out FILE]
        Write the comparison picture (default renders/compare.png) and print its path.
    bricksnap export PROJECT
        Write build.ldr from the saved build and print its path.
    bricksnap ops PROJECT OPS_JSON [--build]
        Apply edit operations (a JSON list in a file, or "-" for standard input) to the
        design, save it, and print one line per operation saying what happened. With
        --build, rebuild afterwards.
    bricksnap design PROJECT [--instruction TEXT] [--model ID] [--effort LEVEL]
        Start an AI design run (``bricksnap.designer.runner.run_designer``). This is the
        only command that sends data off the computer; say so before starting.
    bricksnap view PROJECT [--port 8765] [--no-open]
        Serve the 3D viewer for this project (``bricksnap.viewserver.serve``) and print the
        address.

PROJECT is a path to a project folder; a bare name is looked up under ./projects/.

STAGE 2 ADDITIONS TO THE CONTRACT
(Stage 2 is being built by the lead's agent; until this line is removed, what follows is
not in the code yet.)

- ``export PROJECT``: also writes ``parts.csv`` and ``wanted_list.xml`` through
  ``bricksnap.export.write_exports`` and prints where they are, how many parts and how many
  different parts there are, how to upload the wanted list on BrickLink (Wanted, then
  Upload, paste the file's contents), and any parts that could not be listed.
- ``bench [--studs N] [--out DIR] [--models DIR] [--save] [NAME ...]``: runs
  ``bricksnap.bench.run_bench`` on ``samples/models`` (default out: ``bench/``), prints the
  table, and, when ``samples/scorecard.json`` exists, what changed against it
  (``bench.compare``). ``--save`` writes the new rows to ``samples/scorecard.json``. Exit
  code 0 when every model built with no loose parts, 1 otherwise.
- ``render PROJECT --rough``: the three-row picture (seed, rough, build) through
  ``pipeline.render_compare(project, rough=True)``, saved as ``renders/compare-rough.png``
  unless ``--out`` is given.
- ``new`` and ``build`` print the build's notes under "What the software changed by itself:"
  when there are any, and show only the three most serious weak spots, followed by how many
  more there are and that ``check`` lists them all. ``check`` prints everything.
- ``design`` shows the brief the designer wrote (from ``project.meta["brief"]``) before its
  closing text.

Implementation notes
--------------------
- Exit codes: 0 everything worked and the build (if one was made or checked) is ok; 1 the
  command ran but the result is not good (the build fails its checks, an edit operation was
  not applied, or the AI design run failed); 2 a mistake the user can fix (bad arguments, a
  missing or unusable model file, a folder that is not a project, unreadable operations).
  argparse's own errors are turned into "Error: ..." lines and also return 2.
- Finding a project: PROJECT is used as given when it holds a project.json. Otherwise a bare
  name (one path component) is tried as ./projects/<name> and then ./projects/<slug(name)>,
  so ``--name "My Cat"`` can be reopened as "My Cat" or "my-cat".
- ``ops`` also accepts the JSON written directly on the command line (an argument starting
  with "[" or "{" that is not a file; any length), a single operation object, and
  ``{"ops": [...]}``. A byte-order mark at the start of a file or of standard input is
  ignored. The design is saved only when at least one operation was applied.
- ``check`` saves the fresh report into build.json so the viewer shows the same verdict, and
  then puts back the file's previous modification time: the parts did not change, so the
  build must not look newer than a design edited after it.
- ``render --out`` must name a .png file; the picture is drawn by
  ``pipeline.render_compare`` into renders/ under a temporary name and then moved there.
  The temporary file is removed even when the move fails.
- ``design`` always rebuilds afterwards when the project has a design, so the build it
  reports on, build.ldr and the picture match the final design. File times are not used to
  decide (``check`` and a clock that is set back both make them unreliable), and the saved
  build may be out of date even when the run changed nothing. A hash of design.npz and
  design.json taken before and after the run only chooses the wording. Tool names are shown
  without the runner's ``TOOL_PREFIX``; the run's record is mentioned only if it exists.
- Damaged project files (project.json that is not a JSON object, a design.npz, design.json
  or build.json that cannot be read) are reported as "Error: ... is damaged" with exit code
  2. So is any OSError (a folder that is really a file, no permission, a name too long for
  the system), as "Error: Cannot read or write <path>: <reason>." ``--port`` must be 0 to
  65535.
- The designer runner and the viewer server are imported inside their commands, so the rest
  of the command line works even while those modules are unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import shutil
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn
from zipfile import BadZipFile

from bricksnap.project import Project, ProjectError, slug
from bricksnap.types import Build, Design, SeedError

PROG = "bricksnap"
RUN = "uv run bricksnap"  # how the README tells people to run the command


class UserError(Exception):
    """A mistake the user can fix. The message is written for a non-programmer."""


class _ArgumentError(Exception):
    """argparse found a problem with the command line."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise _ArgumentError(f"{message}\n{self.format_usage().rstrip()}")


# ---- helpers ------------------------------------------------------------------------------


def _show(path: Path) -> str:
    """A path as a person would type it: relative to the current folder when inside it."""
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _ref(project: Project) -> str:
    """How to name this project in a later command (a bare name when it is in ./projects)."""
    try:
        if project.path.resolve().parent == (Path.cwd() / "projects").resolve():
            return shlex.quote(project.path.name)
    except OSError:
        pass
    return shlex.quote(_show(project.path))


def _is_file(path: Path) -> bool:
    """``path.is_file()``, but False for names the system cannot even look up (too long...)."""
    try:
        return path.is_file()
    except (OSError, ValueError):
        return False


def _is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except (OSError, ValueError):
        return False


# What reading a damaged design or build file can raise (numpy, zipfile, json, dataclasses).
_DAMAGED = (ValueError, KeyError, TypeError, AttributeError, IndexError, EOFError, BadZipFile)


def open_project(ref: str) -> Project:
    """Open PROJECT: a path to a project folder, or a bare name looked up under ./projects."""
    given = Path(ref)
    candidates = [given]
    if not given.is_absolute() and len(given.parts) == 1:
        candidates += [Path("projects") / ref, Path("projects") / slug(ref)]
    for candidate in candidates:
        if _is_file(candidate / "project.json"):
            damaged = ProjectError(
                f"The project file {_show(candidate / 'project.json')} is damaged and cannot "
                f"be read. Make the project again with '{RUN} new'."
            )
            try:
                project = Project(candidate)
            except ValueError as e:  # not JSON, or not text at all
                raise damaged from e
            if not isinstance(project.meta, dict):
                raise damaged
            return project
    if _is_dir(given):
        raise ProjectError(
            f"The folder {_show(given)} is not a BrickSnap project (there is no project.json "
            f"in it). Make one with: {RUN} new MODEL --studs 16"
        )
    where = f"{ref}" if len(candidates) == 1 else f"{ref} or projects/{ref}"
    raise ProjectError(
        f"Cannot find a project called '{ref}' (looked for {where}). Check the name, or make "
        f"a new project with: {RUN} new MODEL --studs 16"
    )


def load_design(project: Project) -> Design:
    """The project's design, with a plain message when its files are damaged."""
    try:
        return project.load_design()
    except ProjectError:
        raise
    except _DAMAGED as e:
        raise ProjectError(
            f"The design files of this project ({_show(project.path / 'design.npz')} and "
            f"design.json) are damaged and cannot be read. Make the project again with "
            f"'{RUN} new'."
        ) from e


def load_build(project: Project) -> Build:
    """The project's saved build, with a plain message when build.json is damaged."""
    try:
        return project.load_build()
    except ProjectError:
        raise
    except _DAMAGED as e:
        raise ProjectError(
            f"The build file {_show(project.build_path)} is damaged and cannot be read. "
            f"Make it again with: {RUN} build {_ref(project)}"
        ) from e


def _print_report(build: Build) -> bool:
    report = build.report
    if report is None:
        print(f"This build has no check report. Run '{RUN} check' to make one.")
        return False
    print(report.text.rstrip())
    return report.ok


def _verdict(build: Build) -> str:
    """One plain sentence saying whether the build is good."""
    report = build.report
    if report is not None and report.ok:
        return f"{report.part_count} parts in one connected piece that stands up on its own."
    return (
        "the bricks do NOT hold together as one standing model yet. The check report below "
        "says what is wrong and where."
    )


def _build_and_render(project: Project) -> tuple[Build, Path]:
    from bricksnap.pipeline import rebuild, render_compare

    load_design(project)  # a plain message, not a traceback, when the design is damaged
    build = rebuild(project)
    picture = render_compare(project)
    return build, picture


def _render(project: Project, name: str = "compare.png") -> Path:
    from bricksnap.pipeline import render_compare

    load_design(project)  # the picture uses both; check they can be read first
    if project.has_build():
        load_build(project)
    return render_compare(project, name=name)


def _print_outputs(project: Project, picture: Path) -> None:
    print()
    print("Files:")
    print(f"  {_show(picture)}")
    print("      a picture: your model on the top row, the brick version below it")
    print(f"  {_show(project.ldraw_path)}")
    print("      the brick model, which opens in BrickLink Studio, LeoCAD or LDView")


def _print_next(project: Project, ok: bool) -> None:
    ref = _ref(project)
    print()
    print("What to do next:")
    print(f"  {RUN} view {ref}")
    print("      look at it in 3D in your web browser")
    if ok:
        print(f"  {RUN} design {ref}")
        print("      let the AI designer improve how it looks (this sends pictures to the AI)")
    else:
        print(f"  {RUN} design {ref}")
        print("      let the AI designer fix and improve it (this sends pictures to the AI)")
        print(f"  {RUN} ops {ref} edits.json --build")
        print("      or change the design yourself with edit operations, then rebuild")


# ---- commands -----------------------------------------------------------------------------


def cmd_new(args: argparse.Namespace) -> int:
    from bricksnap.pipeline import create_project

    model = Path(args.model)
    folder = Path(args.dir)
    if _is_file(folder) or (folder.exists() and not _is_dir(folder)):
        raise UserError(f"{folder} is a file, not a folder. Give a folder to put the project in.")
    print(f"Reading {model.name} and turning it into bricks...")
    project = create_project(
        model,
        studs=args.studs,
        name=args.name,
        directory=args.dir,
        up=args.up,
        hollow=args.hollow,
    )
    build, picture = _build_and_render(project)
    inside = "hollow inside, to save parts" if args.hollow else "solid inside"
    print()
    print(f'Made the project "{project.name}".')
    print(f"  Folder: {_show(project.path)}")
    print(f"  Size:   {args.studs} studs ({args.studs * 8} mm) along its longest side, {inside}.")
    print(f"  Result: {_verdict(build)}")
    print()
    print("Check report:")
    ok = _print_report(build)
    _print_outputs(project, picture)
    _print_next(project, ok)
    return 0 if ok else 1


def cmd_build(args: argparse.Namespace) -> int:
    project = open_project(args.project)
    build, picture = _build_and_render(project)
    print(f'Rebuilt "{project.name}" from its current design.')
    print(f"Result: {_verdict(build)}")
    print()
    print("Check report:")
    ok = _print_report(build)
    _print_outputs(project, picture)
    return 0 if ok else 1


def cmd_check(args: argparse.Namespace) -> int:
    from bricksnap.catalog import load_catalog
    from bricksnap.checks import check

    project = open_project(args.project)
    build = load_build(project)
    build.report = check(build, load_catalog())
    project.save_build(build)  # the parts and the design they came from are unchanged
    ok = _print_report(build)
    if project.has_design() and not project.build_is_current(load_design(project), build):
        print()
        print(
            "Note: the design has been edited since these bricks were built, so this report "
            f"is about the earlier version. To rebuild: {RUN} build {_ref(project)}"
        )
    return 0 if ok else 1


def cmd_render(args: argparse.Namespace) -> int:
    project = open_project(args.project)
    if args.out is None:
        picture = _render(project)
    else:
        out = Path(args.out)
        if out.suffix.lower() != ".png":
            raise UserError(f"The picture can only be saved as a .png file (you gave {out}).")
        if _is_dir(out):
            raise UserError(f"{out} is a folder. Give a file name ending in .png.")
        drawn = _render(project, name=".render-out.png")
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(drawn, out)
        finally:
            if drawn.resolve() != out.resolve():
                drawn.unlink(missing_ok=True)  # never leave the temporary picture behind
        picture = out
    print(f"Wrote the comparison picture: {_show(picture)}")
    print("Top row: your model. Bottom row: the brick version, at the same scale.")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from bricksnap.catalog import load_catalog
    from bricksnap.ldraw import to_ldraw

    project = open_project(args.project)
    build = load_build(project)
    text = to_ldraw(build, load_catalog(), title=project.name)
    project.ldraw_path.write_text(text, encoding="utf-8")
    print(f"Wrote the LDraw file: {_show(project.ldraw_path)}")
    print("It opens in BrickLink Studio, LeoCAD or LDView.")
    return 0


def read_ops(source: str) -> list[Any]:
    """The edit operations from a file, from standard input ("-"), or written inline."""
    if source == "-":
        where = "standard input"
        text = sys.stdin.read().removeprefix("﻿")  # a byte-order mark some editors add
    else:
        path = Path(source)
        if _is_file(path):  # a file wins, even when its name starts with "["
            where = _show(path)
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError as e:
                raise UserError(f"{where} is not a text file of operations.") from e
            except OSError as e:
                raise UserError(f"Cannot read {where}: {e.strerror or e}.") from e
        elif source.lstrip().startswith(("[", "{")):
            where = "the text you typed"
            text = source
        elif _is_dir(path):
            raise UserError(f"{source} is a folder. Give the file that holds the operations.")
        else:
            raise UserError(
                f"Cannot find the file {source}. Give a file of edit operations, or '-' to "
                "read them from standard input."
            )
    if not text.strip():
        raise UserError(f"There are no operations in {where}: it is empty.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise UserError(
            f"The operations in {where} are not valid JSON ({e.msg}, line {e.lineno}, column "
            f'{e.colno}). They should be a list such as [{{"op": "paint", "shape": {{"type": '
            '"box", "min": [0, 0, 0], "max": [2, 2, 2]}, "color": 4}].'
        ) from e
    if isinstance(data, dict):
        data = data["ops"] if set(data) == {"ops"} else [data]
    if not isinstance(data, list):
        raise UserError(
            f"The operations in {where} should be a list of operations in square brackets "
            f"[...], not a single {type(data).__name__}."
        )
    if not data:
        raise UserError(f"The list of operations in {where} is empty.")
    return data


def cmd_ops(args: argparse.Namespace) -> int:
    from bricksnap.catalog import load_catalog
    from bricksnap.design import apply_ops

    project = open_project(args.project)
    ops = read_ops(args.ops)
    design = load_design(project)
    results = apply_ops(design, ops, load_catalog())
    applied = sum(r.applied for r in results)
    for r in results:
        if r.applied:
            print(f"{r.index + 1}. Done. {r.message}")
        elif r.message.lower().startswith("rejected"):
            print(f"{r.index + 1}. {r.message}")
        else:
            print(f"{r.index + 1}. Not done. {r.message}")
    print()
    if applied:
        project.save_design(design)
        print(f"Saved the design ({applied} of {len(results)} operations applied).")
    else:
        print("Nothing was changed, so the design was not saved.")
    all_applied = applied == len(results)
    if not args.build:
        if applied:
            print(f"The bricks are not rebuilt yet. To see the change: {RUN} build {_ref(project)}")
        return 0 if all_applied else 1
    build, picture = _build_and_render(project)
    print("Rebuilt the bricks:")
    ok = _print_report(build)
    _print_outputs(project, picture)
    return 0 if ok and all_applied else 1


def _design_fingerprint(project: Project) -> bytes:
    """A hash of the saved design files, to tell whether a run changed the design."""
    digest = hashlib.sha256()
    for name in ("design.npz", "design.json"):
        try:
            digest.update((project.path / name).read_bytes())
        except OSError:
            digest.update(b"missing")
        digest.update(b"\0")
    return digest.digest()


def cmd_design(args: argparse.Namespace) -> int:
    from bricksnap.designer.runner import TOOL_PREFIX, run_designer

    project = open_project(args.project)
    load_design(project)  # fail now, with a clear message, if there is nothing to design
    before = _design_fingerprint(project)
    print(f'Starting the AI designer for "{project.name}".')
    print(
        "This step sends pictures of the model and a description of it (its size, colours "
        "and parts) to the AI provider, Anthropic, through Claude Code. Nothing else in "
        "BrickSnap sends anything off your computer."
    )
    print("It usually takes several minutes. Press Ctrl+C to stop it; edits made so far stay.")
    print()
    sys.stdout.flush()
    options: dict[str, Any] = {}
    if args.instruction is not None:
        options["instruction"] = args.instruction
    if args.model is not None:
        options["model"] = args.model
    if args.effort is not None:
        options["effort"] = args.effort
    run = run_designer(project, **options)

    if run.ok:
        print(f"The AI designer finished after {run.turns} turns.")
    else:
        print(f"The AI designer did not finish: {run.error or 'it stopped without saying why.'}")
    if run.tools_called:
        counts = Counter(name.removeprefix(TOOL_PREFIX) for name in run.tools_called)
        used = ", ".join(f"{name} ({n})" for name, n in counts.items())
        print(f"It used its tools {len(run.tools_called)} times: {used}.")
    else:
        print("It did not use any of its tools, so the design was not changed.")
    if run.final_text.strip():
        print()
        print("What the designer said at the end:")
        for line in run.final_text.strip().splitlines():
            print(f"  {line}")

    print()
    ok = False
    if project.has_design():
        # Always rebuild: a few seconds against a run of minutes, and the saved build may
        # not match the design even when the run changed nothing (ops without --build).
        if _design_fingerprint(project) != before:
            print("Rebuilding from the final design...")
        else:
            print("Making sure the build matches the design...")
        build, picture = _build_and_render(project)
        _print_verdict(build)
        ok = bool(build.report and build.report.ok)
        _print_outputs(project, picture)
    elif project.has_build():
        build = load_build(project)
        _print_verdict(build)
        ok = bool(build.report and build.report.ok)
    if run.transcript is not None and _is_file(run.transcript):
        print()
        print(f"A full record of the run is in {_show(run.transcript)}")
    _print_next(project, ok)
    return 0 if run.ok and ok else 1


def _print_verdict(build: Build) -> None:
    if build.report is not None and build.report.ok:
        print("The build is valid afterwards:")
    else:
        print("The build is NOT valid afterwards:")
    _print_report(build)


def cmd_view(args: argparse.Namespace) -> int:
    from bricksnap.viewserver import serve

    project = open_project(args.project)
    if not project.has_build():
        print(f"Note: this project has not been built yet. Run '{RUN} build {_ref(project)}'.")
    serve(project.path, port=args.port, open_browser=not args.no_open)
    return 0


# ---- argument parsing ---------------------------------------------------------------------


def _port(text: str) -> int:
    try:
        number = int(text)
    except ValueError:
        number = -1
    if not 0 <= number <= 65535:
        raise argparse.ArgumentTypeError(
            f"the port must be a whole number from 1 to 65535 (or 0 to pick a free one), "
            f"not {text!r}"
        )
    return number


def _system_error(e: OSError) -> str:
    """An OSError (a path that cannot be read or written...) as one plain sentence."""
    reason = e.strerror or str(e) or type(e).__name__
    if e.filename is not None:
        return f"Cannot read or write {e.filename}: {reason}."
    return f"{reason}."


def _parser() -> _Parser:
    parser = _Parser(
        prog=PROG,
        description="Turn a 3D model into a set of real LEGO-compatible bricks.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", parser_class=_Parser)
    project_help = "the project folder, or just its name if it is in ./projects"

    p = sub.add_parser(
        "new",
        help="make a project from a 3D model file and build it",
        description=(
            "Make a project from a 3D model file (STL, OBJ, GLB, GLTF, 3MF or PLY), then "
            "build it from bricks and check it."
        ),
    )
    p.add_argument("model", metavar="MODEL", help="the 3D model file")
    p.add_argument(
        "--studs",
        type=int,
        required=True,
        metavar="N",
        help="size along the longest side, in studs (4 to 96; one stud is 8 mm)",
    )
    p.add_argument("--name", help="a name for the project (default: the file name)")
    p.add_argument(
        "--dir",
        default="projects",
        metavar="FOLDER",
        help="the folder to put the project in (default: projects)",
    )
    p.add_argument(
        "--up",
        choices=["x", "y", "z"],
        help="which axis of the file points up, if the model comes out lying down",
    )
    p.add_argument("--hollow", action="store_true", help="keep only a shell, to use fewer parts")
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("build", help="rebuild the bricks from the current design and check them")
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("check", help="check the saved build again and print the report")
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("render", help="draw the comparison picture")
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.add_argument("--out", metavar="FILE", help="where to save it (default: renders/compare.png)")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("export", help="write the LDraw file (build.ldr) from the saved build")
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser(
        "ops",
        help="change the design with edit operations",
        description=(
            "Apply edit operations to the design. OPS_JSON is a file holding a JSON list of "
            "operations, or '-' to read them from standard input."
        ),
    )
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.add_argument("ops", metavar="OPS_JSON", help="a file of operations, or '-'")
    p.add_argument("--build", action="store_true", help="rebuild the bricks afterwards")
    p.set_defaults(func=cmd_ops)

    p = sub.add_parser(
        "design",
        help="let the AI designer improve the model (sends data to the AI)",
        description=(
            "Start an AI design run. This is the only BrickSnap command that sends anything "
            "off your computer: pictures and a description of the model go to the AI provider."
        ),
    )
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.add_argument("--instruction", metavar="TEXT", help="what you want the designer to do")
    p.add_argument("--model", metavar="ID", help="which AI model to use")
    p.add_argument("--effort", metavar="LEVEL", help="how hard the AI should think")
    p.set_defaults(func=cmd_design)

    p = sub.add_parser("view", help="look at the project in 3D in your web browser")
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.add_argument(
        "--port",
        type=_port,
        default=8765,
        help="the port to use, 1 to 65535, or 0 to pick a free one (default: 8765)",
    )
    p.add_argument("--no-open", action="store_true", help="do not open the browser")
    p.set_defaults(func=cmd_view)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except _ArgumentError as e:
        print(f"Error: {e}", file=sys.stderr)
        print(f"For help, run: {RUN} --help", file=sys.stderr)
        return 2
    except SystemExit as e:  # --help
        return e.code if isinstance(e.code, int) else 0
    if getattr(args, "func", None) is None:
        parser.print_help()
        return 2
    try:
        return args.func(args)
    except (SeedError, ProjectError, UserError) as e:
        sys.stdout.flush()
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except OSError as e:  # a folder or file the user named cannot be used
        sys.stdout.flush()
        print(f"Error: {_system_error(e)}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        sys.stdout.flush()
        print("\nStopped.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
