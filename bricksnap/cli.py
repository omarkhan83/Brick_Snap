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

STAGE 3 ADDITION TO THE CONTRACT: a typed edit
(Being built by the lead's agent; until this line is removed, what follows is not in the
code yet.)
- ``design PROJECT "add a red collar"``: the request may be given as a second argument
  (``--instruction`` stays and means the same; giving both is a mistake the command explains).
- Before the run the command says which kind it is: a first design, or one change to a
  model that is already designed (and quotes the request back).
- After an edit it says what changed, from the project itself: how many edit operations
  this run added to the design's log and of which kinds, how many parts before and after,
  and whether the build is valid. If the run added no operation, it says the designer made
  no change and why it said so.

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
  of the command line works even while those modules are unavailable. So are
  ``bricksnap.export`` and ``bricksnap.bench``.
- Short report (``new``, ``build``, and also ``ops --build`` and ``design``, which rebuild
  too): the report text is printed as it is up to the weak-spot heading, so the verdict and
  every problem stay; then the first three entries of ``Report.weak_spots``; then "- and N
  more weak spots; '... check PROJECT' lists them all." The weak-spot list is found by
  looking for the line "- <first weak spot>" in the text, and the total by the number that
  starts the heading line above it (``Report`` keeps at most ten sentences; when the total
  is larger the line says ``check`` lists "the 10 most serious"). If that line is not found,
  or there are three weak spots or fewer, the text is printed whole. The notes come before
  the report, one "  - " line each; no heading when there are none.
- ``export`` makes the parts list first, which also checks every part and colour value: a
  part id that is not text or a colour that is not a whole number makes build.json
  "damaged" (exit code 2, nothing written). Then build.ldr, then the two lists. A part that
  is not in the parts table cannot go into the LDraw file: the lists are still written (so
  the user sees which parts to buy by hand), the output says why build.ldr could not be
  written and that an older one was left as it was, and the exit code is 1. "Kinds" of
  part count the same part in another colour separately (one line of the parts list each),
  because that is what a buyer orders. Parts left off the wanted list are listed with their
  quantity, colour and name; a colour that is not in the parts table is shown by its LDraw
  code ("in unknown colour 999"). When no part can go on the wanted list, or the build has
  no parts, wanted_list.xml holds no ITEM, which BrickLink will not accept, so the upload
  steps are left out and the output says there is nothing to upload. Like ``check``, it
  says when the design was edited after the build, because then the lists are for the
  earlier version. Otherwise the exit code is 0.
- ``render`` says what the bottom row is: the bricks once the project is built, otherwise
  the design (the renderer draws cells then), with the command that builds it. ``--rough``
  reads design.base.npz first, so a damaged one is "Error: ... is damaged" with exit code 2
  (a missing one is ``Project``'s own "has no base design yet" error).
- ``bench``: model names are checked against the files in the models folder first (a wrong
  name lists the models; nothing is built). ``--studs`` must be 4 to 96. The scorecard path
  is ``samples/scorecard.json`` relative to the current folder, written as
  ``{"studs": N, "rows": [...]}`` (``Row`` fields); a bare list of rows is read too, and
  unknown fields are ignored. It is compared only when it was made at the same size, and
  only for the models in this run. A damaged scorecard is a printed note, not an error,
  with one plain reason (not a text file, not valid JSON, no list of rows, a size that is
  not a whole number, a row with no model name, or a field whose value is of the wrong
  kind: each known field must have the type of ``Row``'s default, a whole number being
  accepted where a fraction is expected). Nothing damaged is passed to ``bench.compare``.
  ``--save`` with model names replaces those models' rows and keeps the others (unless the
  saved scorecard was made at another size; then it is replaced and the output says so).
  Models whose ``error`` is set are listed under "Could not be built:". Exit code 0 only
  when there was at least one row and no row has an error or loose parts.
- ``design`` reads the brief from project.json again after the run (the designer's tools
  save it through their own Project object). Each field gets a plain label; features are
  one "- " line each; colour codes are shown by their catalogue names ("colour N" for a code
  not in the catalogue); missing or empty fields are skipped; a brief that is plain text is
  printed as it is.
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


SHOWN_WEAK_SPOTS = 3
"""How many weak spots ``new`` and ``build`` show; ``check`` shows the report in full."""


def _print_report(build: Build, project: Project | None = None) -> bool:
    """Print the check report. Given the project, show only the most serious weak spots.

    The report's text is printed as it is, except that after the third weak spot one line
    says how many more there are and how to see them (``check`` prints everything).
    """
    report = build.report
    if report is None:
        print(f"This build has no check report. Run '{RUN} check' to make one.")
        return False
    lines = report.text.rstrip().splitlines()
    weak = report.weak_spots
    first = f"- {weak[0]}" if weak else None
    if project is None or first not in lines or len(weak) <= SHOWN_WEAK_SPOTS:
        print("\n".join(lines))
        return report.ok
    start = lines.index(first)  # the weak-spot heading is the line before it
    heading = lines[start - 1].split() if start > 0 else []
    total = int(heading[0]) if heading and heading[0].isdigit() else len(weak)
    total = max(total, len(weak))
    for line in lines[:start]:
        print(line)
    for spot in weak[:SHOWN_WEAK_SPOTS]:
        print(f"- {spot}")
    more = total - SHOWN_WEAK_SPOTS
    lists = "lists them all" if total <= len(weak) else f"lists the {len(weak)} most serious"
    print(
        f"- and {more} more weak {'spot' if more == 1 else 'spots'}; "
        f"'{RUN} check {_ref(project)}' {lists}."
    )
    return report.ok


def _print_notes(build: Build) -> bool:
    """What the make-buildable and finishing passes changed or could not do, if anything.
    Returns whether there were any."""
    notes = [note.strip() for note in build.notes if note.strip()]
    if not notes:
        return False
    print()
    print("What the software changed by itself:")
    for note in notes:
        print(f"  - {note}")
    return True


def _plural(n: int, singular: str, plural: str | None = None) -> str:
    """'1 part', '2 parts'; ``plural`` when adding an s is not enough."""
    return f"{n:,} {singular if n == 1 else (plural or singular + 's')}"


def _sentence(e: Exception) -> str:
    """An exception's plain-language message as one sentence ending in a full stop."""
    text = str(e).strip().strip("'\"") or "it holds something unexpected"
    return text if text.endswith((".", "!", "?")) else text + "."


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


def _render(project: Project, name: str = "compare.png", rough: bool = False) -> Path:
    from bricksnap.pipeline import render_compare

    load_design(project)  # the picture uses both; check they can be read first
    if project.has_build():
        load_build(project)
    if rough:  # the middle row is laid out from the untouched base design
        try:
            project.load_design(base=True)
        except ProjectError:
            raise
        except _DAMAGED as e:
            raise ProjectError(
                f"The base design of this project ({_show(project.path / 'design.base.npz')}) "
                f"is damaged and cannot be read, so the plain conversion cannot be drawn. "
                f"Make the project again with '{RUN} new', or draw the picture without --rough."
            ) from e
    return render_compare(project, name=name, rough=rough)


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
    _print_notes(build)
    print()
    print("Check report:")
    ok = _print_report(build, project)
    _print_outputs(project, picture)
    _print_next(project, ok)
    return 0 if ok else 1


def cmd_build(args: argparse.Namespace) -> int:
    project = open_project(args.project)
    build, picture = _build_and_render(project)
    print(f'Rebuilt "{project.name}" from its current design.')
    print(f"Result: {_verdict(build)}")
    _print_notes(build)
    print()
    print("Check report:")
    ok = _print_report(build, project)
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
    rough = bool(args.rough)
    if args.out is None:
        picture = _render(project, "compare-rough.png" if rough else "compare.png", rough)
    else:
        out = Path(args.out)
        if out.suffix.lower() != ".png":
            raise UserError(f"The picture can only be saved as a .png file (you gave {out}).")
        if _is_dir(out):
            raise UserError(f"{out} is a folder. Give a file name ending in .png.")
        drawn = _render(project, ".render-out.png", rough)
        try:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(drawn, out)
        finally:
            if drawn.resolve() != out.resolve():
                drawn.unlink(missing_ok=True)  # never leave the temporary picture behind
        picture = out
    print(f"Wrote the comparison picture: {_show(picture)}")
    built = project.has_build()
    if rough:
        bottom = (
            "the brick version as it is now" if built else "the design, not built into bricks yet"
        )
        print(
            "Top row: your model. Middle row: the plain conversion, before any design work. "
            f"Bottom row: {bottom}. All at the same scale."
        )
    elif built:
        print("Top row: your model. Bottom row: the brick version, at the same scale.")
    else:
        print(
            "Top row: your model. Bottom row: the design, not built into bricks yet. Both at "
            "the same scale."
        )
    if not built:
        print(f"To build it from bricks: {RUN} build {_ref(project)}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from bricksnap.catalog import load_catalog
    from bricksnap.export import parts_list, unlisted, write_exports
    from bricksnap.ldraw import to_ldraw

    project = open_project(args.project)
    build = load_build(project)
    catalog = load_catalog()
    try:
        lines = parts_list(build, catalog)  # also checks every part and colour value
    except (ValueError, TypeError) as e:
        raise ProjectError(
            f"The build file {_show(project.build_path)} is damaged and cannot be read: "
            f"{_sentence(e)} Make it again with: {RUN} build {_ref(project)}"
        ) from e
    try:
        text: str | None = to_ldraw(build, catalog, title=project.name)
        ldraw_problem = ""
    except ValueError as e:  # a part that is not in the parts table
        text, ldraw_problem = None, _sentence(e)
    except (TypeError, KeyError):  # Python's own words, not for a person
        text = None
        ldraw_problem = "the build holds a value of the wrong kind, so it may be damaged."
    if text is not None:
        project.ldraw_path.write_text(text, encoding="utf-8")
    files = write_exports(project, catalog)
    missing = unlisted(lines)
    total = sum(line.quantity for line in lines)
    wanted = files["wanted_list"]

    if text is not None:
        print(f"Wrote the LDraw file: {_show(project.ldraw_path)}")
        print("    It opens in BrickLink Studio, LeoCAD or LDView.")
    else:
        print(f"Could not write the LDraw file: {ldraw_problem}")
        if _is_file(project.ldraw_path):
            print(
                f"    The older {project.ldraw_path.name} was left as it was, so it does not "
                "match the lists below."
            )
    print(f"Wrote the parts list: {_show(files['parts'])}")
    print("    It opens in any spreadsheet program, such as Excel or LibreOffice.")
    print(f"Wrote the BrickLink wanted list: {_show(wanted)}")
    print()
    if not lines:
        print(
            "The build has no parts, so there is nothing to buy and nothing to upload to "
            f"BrickLink. To build it again: {RUN} build {_ref(project)}"
        )
    else:
        print(
            f"The model needs {_plural(total, 'part')} of "
            f"{_plural(len(lines), 'different kind')} "
            "(the same part in another colour counts as another kind)."
        )
        print()
    if lines and len(missing) < len(lines):
        print("To buy the parts on BrickLink (bricklink.com):")
        print("  1. Sign in, then choose Wanted, then Upload.")
        print(f"  2. Open {wanted.name} in a text editor such as Notepad, copy everything in it,")
        print("     and paste it into the box on that page.")
        print(
            "  3. Follow the steps on the page to check the parts and save them as a wanted list."
        )
        print()
    if lines and len(missing) == len(lines):
        print(
            "None of the parts can go on the BrickLink wanted list, because BrickLink's number "
            f"for each part or its colour is not known, so there is nothing to upload. Buy "
            f"{'it' if total == 1 else 'them'} by hand:"
        )
    elif missing:
        count = sum(line.quantity for line in missing)
        print(
            f"{_plural(count, 'part is', 'parts are')} not on the wanted list, because "
            "BrickLink's number for the part or its colour is not known. Add "
            f"{'it' if count == 1 else 'them'} by hand:"
        )
    elif lines:
        print("Every part is on the wanted list.")
    for line in missing:
        print(f"  - {_describe_line(line)}")
    if project.has_design() and not project.build_is_current(load_design(project), build):
        print()
        print(
            "Note: the design has been edited since these bricks were built, so these lists "
            f"are for the earlier version. To rebuild first: {RUN} build {_ref(project)}"
        )
    return 0 if text is not None else 1


def _describe_line(line: Any) -> str:
    """One line of the parts list for a person: '2 x Red Brick 1 x 1 (part 3005)'. A colour
    that is not in the parts table is shown by its LDraw colour code."""
    from bricksnap.export import UNKNOWN_COLOUR

    if line.colour_name == UNKNOWN_COLOUR:
        return f"{line.quantity} x {line.name} (part {line.part}) in unknown colour {line.colour}"
    return f"{line.quantity} x {line.colour_name} {line.name} (part {line.part})"


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
    print(f"Rebuilt the bricks. Result: {_verdict(build)}")
    _print_notes(build)
    print()
    print("Check report:")
    ok = _print_report(build, project)
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
    _print_brief(project)
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
        _print_verdict(build, project)
        ok = bool(build.report and build.report.ok)
        _print_outputs(project, picture)
    elif project.has_build():
        build = load_build(project)
        _print_verdict(build, project)
        ok = bool(build.report and build.report.ok)
    if run.transcript is not None and _is_file(run.transcript):
        print()
        print(f"A full record of the run is in {_show(run.transcript)}")
    _print_next(project, ok)
    return 0 if run.ok and ok else 1


_BRIEF_FIELDS = (
    ("object", "What it is"),
    ("features", "What makes it recognisable"),
    ("plan", "The plan"),
    ("colours", "Colours"),
    ("finish", "Surfaces"),
)


def _colour_names(codes: Any) -> str:
    """LDraw colour codes as the catalogue's names: 'Black, White, colour 999'."""
    from bricksnap.catalog import load_catalog

    colours = load_catalog().colours
    names = []
    for code in codes if isinstance(codes, list) else [codes]:
        try:
            names.append(colours[int(code)].name)
        except (KeyError, TypeError, ValueError):
            names.append(f"colour {code}")
    return ", ".join(names)


def _print_brief(project: Project) -> None:
    """The brief the designer wrote (project.meta["brief"]), read afresh after the run."""
    try:
        meta = json.loads((project.path / "project.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    brief = meta.get("brief") if isinstance(meta, dict) else None
    if not brief:
        return
    print()
    print("The designer's brief:")
    if not isinstance(brief, dict):
        for line in str(brief).strip().splitlines():
            print(f"  {line}")
        return
    for key, label in _BRIEF_FIELDS:
        value = brief.get(key)
        if value in (None, "", []):
            continue
        if key == "colours":
            print(f"  {label}: {_colour_names(value)}")
        elif isinstance(value, list):
            print(f"  {label}:")
            for item in value:
                print(f"    - {item}")
        else:
            print(f"  {label}: {value}")


def _print_verdict(build: Build, project: Project) -> None:
    if _print_notes(build):
        print()
    if build.report is not None and build.report.ok:
        print("The build is valid afterwards:")
    else:
        print("The build is NOT valid afterwards:")
    _print_report(build, project)


SCORECARD = Path("samples") / "scorecard.json"
"""The saved scorecard that ``bench`` compares against and ``bench --save`` replaces."""


def _read_scorecard(path: Path) -> tuple[int | None, list[Any]] | None:
    """(studs, rows) from a saved scorecard, or None when there is none or it is damaged.

    Accepts ``{"studs": N, "rows": [...]}`` (what ``--save`` writes) or a bare list of rows.
    Prints a plain note when the file exists but cannot be used.
    """
    if not _is_file(path):
        return None
    try:
        return _parse_scorecard(path)
    except _DamagedScorecard as e:
        print(f"The saved scorecard {_show(path)} is damaged and cannot be read: {e}")
        print("Run with --save to replace it with this result.")
        return None


class _DamagedScorecard(Exception):
    """Why a saved scorecard cannot be used, as a plain sentence."""


def _is_whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_scorecard(path: Path) -> tuple[int | None, list[Any]]:
    """(studs, rows) from a scorecard file, or _DamagedScorecard saying what is wrong.

    Each row must be an object with a model name; each known field must have the type of
    ``Row``'s default for it (a whole number is accepted where a fraction is expected).
    """
    from dataclasses import MISSING

    from bricksnap.bench import Row

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise _DamagedScorecard("it is not a text file.") from e
    except OSError as e:
        raise _DamagedScorecard(f"{e.strerror or 'the system would not open it'}.") from e
    try:
        data = json.loads(text)
    except ValueError as e:  # a merge conflict left in it, for example
        raise _DamagedScorecard("it is not valid JSON.") from e
    raw = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        raise _DamagedScorecard("it holds no list of rows.")
    studs = data.get("studs") if isinstance(data, dict) else None
    if studs is not None and not _is_whole(studs):
        raise _DamagedScorecard("the size it was made at is not a whole number of studs.")

    types: dict[str, type | None] = {}
    for field in Row.__dataclass_fields__.values():
        default = field.default
        types[field.name] = type(default) if default is not MISSING else None
    rows = []
    for number, item in enumerate(raw, start=1):
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise _DamagedScorecard(f"row {number} has no model name.")
        values = {}
        for key, value in item.items():
            if key not in types:
                continue  # a field this version does not know
            want = types[key]
            if want is float:
                fits = isinstance(value, float) or _is_whole(value)
            elif want is int:
                fits = _is_whole(value)
            elif want in (bool, str):
                fits = isinstance(value, want)
            else:
                fits = True
            if not fits:
                raise _DamagedScorecard(
                    f"row {number} ({name}) has {json.dumps(value)} for {key}, which should be "
                    f"{_KIND_OF.get(want, 'something else')}."
                )
            values[key] = value
        rows.append(Row(**values))
    return studs, rows


_KIND_OF: dict[type | None, str] = {
    bool: "true or false",
    int: "a whole number",
    float: "a number",
    str: "text",
}


def cmd_bench(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from bricksnap.bench import MODEL_SUFFIXES, compare, format_table, run_bench
    from bricksnap.seed import MAX_STUDS, MIN_STUDS
    from bricksnap.types import write_text_atomic

    studs = int(args.studs)
    if not MIN_STUDS <= studs <= MAX_STUDS:
        raise UserError(f"The size must be between {MIN_STUDS} and {MAX_STUDS} studs.")
    models = Path(args.models)
    out = Path(args.out)
    if not _is_dir(models):
        raise UserError(
            f"Cannot find the folder of test models {models}. Run this from the BrickSnap "
            "folder, or give the folder with --models."
        )
    available = sorted(
        p.stem for p in models.iterdir() if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES
    )
    if not available:
        raise UserError(
            f"There are no model files in {models} (STL, OBJ, GLB, GLTF, 3MF or PLY files)."
        )
    names = list(dict.fromkeys(args.names)) or None
    unknown = [n for n in names or [] if n not in available]
    if unknown:
        raise UserError(
            f"There is no model called {', '.join(unknown)} in {models}. The models are: "
            f"{', '.join(available)}."
        )
    if _is_file(out):
        raise UserError(f"{out} is a file, not a folder. Give a folder to put the results in.")

    count = len(names) if names else len(available)
    print(
        f"Building {_plural(count, 'test model')} at {studs} studs and drawing a picture of "
        f"each. This can take a minute or two..."
    )
    sys.stdout.flush()
    rows = run_bench(models, out, studs=studs, names=names)
    print()
    print(format_table(rows).rstrip())

    failed = [r for r in rows if r.error]
    if failed:
        print()
        print("Could not be built:")
        for r in failed:
            print(f"  - {r.name}: {r.error}")
    unpictured = [r for r in rows if not r.error and getattr(r, "picture_error", "")]
    if unpictured:
        print()
        print("Built and measured, but the picture could not be drawn:")
        for r in unpictured:
            print(f"  - {r.name}: {r.picture_error}")

    print()
    saved = _read_scorecard(SCORECARD)
    if saved is None:
        if not _is_file(SCORECARD):
            print("Nothing to compare with yet; run with --save to keep this result.")
    else:
        saved_studs, old_rows = saved
        if saved_studs is not None and saved_studs != studs:
            print(
                f"The saved scorecard ({_show(SCORECARD)}) was made at {saved_studs} studs and "
                f"this run is at {studs}, so they are not compared."
            )
        else:
            here = {r.name for r in rows}
            print(f"Compared with the saved scorecard ({_show(SCORECARD)}):")
            print(compare([r for r in old_rows if r.name in here], rows).rstrip())

    if args.save:
        keep: list[Any] = []
        print()
        if names and saved is not None:
            if saved[0] in (None, studs):
                here = {r.name for r in rows}
                keep = [r for r in saved[1] if r.name not in here]  # the others stay as saved
            else:
                print(
                    f"The old scorecard was made at {saved[0]} studs, so it is replaced, not "
                    "added to."
                )
        merged = sorted(keep + list(rows), key=lambda r: r.name)
        SCORECARD.parent.mkdir(parents=True, exist_ok=True)
        data = {"studs": studs, "rows": [asdict(r) for r in merged]}
        write_text_atomic(SCORECARD, json.dumps(data, indent=1) + "\n")
        print(f"Saved this result as the scorecard to compare with next time: {_show(SCORECARD)}")

    built = [r.name for r in rows if not r.error]
    example = shlex.quote(_show(out / "projects" / slug(built[0] if built else "cat")))
    print()
    print("Files:")
    print(f"  {_show(out / 'scorecard.md')}")
    print("      the table above")
    print(f"  {_show(out)}/<model>.png")
    print("      a picture of each model: your model, the plain conversion, the finished build")
    print(f"  {_show(out / 'projects')}/<model>")
    print(f"      the project of each model, to look at in 3D with: {RUN} view {example}")

    bad = [r.name for r in rows if r.error or r.loose]
    print()
    if rows and not bad:
        print(f"Result: all {_plural(len(rows), 'model')} built with no loose parts.")
        return 0
    print(
        f"Result: {len(bad)} of {_plural(len(rows), 'model')} could not be built or "
        f"{'has' if len(bad) == 1 else 'have'} loose parts: {', '.join(bad)}."
    )
    return 1


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
    p.add_argument(
        "--out",
        metavar="FILE",
        help="where to save it (default: renders/compare.png, or compare-rough.png with --rough)",
    )
    p.add_argument(
        "--rough",
        action="store_true",
        help="add a middle row: the plain conversion, before any design work",
    )
    p.set_defaults(func=cmd_render)

    p = sub.add_parser(
        "export",
        help="write the brick model, the parts list and a BrickLink wanted list",
        description=(
            "Write build.ldr (the brick model), parts.csv (the parts list) and wanted_list.xml "
            "(for buying the parts on BrickLink) from the saved build."
        ),
    )
    p.add_argument("project", metavar="PROJECT", help=project_help)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser(
        "bench",
        help="build every test model and measure the results (the scorecard)",
        description=(
            "Build every test model, draw a picture of each and print a table of measurements, "
            "compared with the saved scorecard (samples/scorecard.json) when there is one."
        ),
    )
    p.add_argument(
        "names",
        metavar="NAME",
        nargs="*",
        help="only these models (file names without the ending, such as cat); default: all",
    )
    p.add_argument("--studs", type=int, default=16, metavar="N", help="size in studs (default: 16)")
    p.add_argument(
        "--out",
        default="bench",
        metavar="FOLDER",
        help="where to put the results (default: bench)",
    )
    p.add_argument(
        "--models",
        default=str(Path("samples") / "models"),
        metavar="FOLDER",
        help="the folder of test models (default: samples/models)",
    )
    p.add_argument(
        "--save",
        action="store_true",
        help="keep this result in samples/scorecard.json to compare with next time",
    )
    p.set_defaults(func=cmd_bench)

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
