"""The studio: design a model in passes, each a clean-room AI session with one job.

The first way of designing (``runner.run_designer``) touches up the conversion in one
session. The studio is the second way: a fixed order of sessions, each with its own
instructions and only the tools its job needs. The conversion is what the passes measure
against, not what they start from. The AI still only edits the Design; the solver still
places every part; every result is still checked; and every pass that changes the model is
kept as a version (``bricksnap.versions``), so any two can be put side by side.

CONTRACT (tests go in tests/test_studio.py; no test starts a real AI session)

Passes (``Pass``: name, job in words, version label, tools, operations, turn and time limits,
the message it is sent). ``PASSES`` holds the six, by name:
    plan     looks at the seed and the conversion from all sides; records the brief and a
             construction plan (scale, named regions with boxes, shapes, colours, finish,
             and the interior or none). Tools: describe, render, brief, plan.
    outline  starts from an EMPTY design and lays out the main masses of the plan in their
             main colours. Tools: describe, render, measure, apply_ops (add, remove, paint),
             rebuild.
    refine   corrects proportions, shapes the regions, adds the features and colours that
             make the object recognisable, hollows and furnishes a planned interior. Same
             tools and operations as outline.
    surface  chooses finish on purpose and places details, also on side faces. Tools as
             above; operations paint, set_finish, place_detail, remove_detail.
    critic   a fresh session that has seen none of the work: the pictures (also cut-through
             views and zooms) and the measurements, and reports "good" or at most five
             concrete problems through critique. Tools: render, measure, critique. It
             edits nothing.
    fix      applies the critic's list, and only that. Tools as outline; every operation.
The tools are enforced by the tool server (``studio_server``), not only by the prompt.
Each pass's system prompt is its own ``prompts/<name>.md`` followed by ``prompts/common.md``
(the grid, the tools' conventions and what can be built, written once).

``run_studio(project, *, model=DEFAULT_MODEL, effort="high", on_event=None, passes=None,
rounds=1, wish=None) -> StudioRun``
- The sessions are ``passes`` (default ``DEFAULT_PASSES``: plan, outline, refine, surface;
  names or ``Pass`` objects) followed by ``rounds`` rounds of critic and fix. A critic that
  says "good" ends the rounds without a fix. ``ValueError`` before anything runs for an
  unknown pass, a fix with no critic before it, rounds outside 0 to 3, or no plan pass when
  the project has no plan and brief to build from.
- Before the first session: the project is built if its build is not made from its design,
  its card drawn, and its state kept as a version (``versions.record``: "converted" when the
  design has no edits, "designed" when it has a brief, "manual" otherwise; an unchanged
  state is not kept twice). With a plan pass the old brief and plan are removed (the plan
  pass writes new ones). With an outline pass the design is emptied
  (``design.cleared``, which the edit log records) and the old build removed, so every
  pass from the plan on sees the seed and the conversion, not an earlier design.
- After each session: the plan pass must have saved a brief and a plan; the critic a
  report (moved to ``studio/critique-<round>.json``); a pass that changes the model is
  rebuilt when its last edits were not, its card drawn, and it is kept as a version
  ("pass", labelled with what it did), whose build must hold (``report.ok``). A pass that
  changed nothing makes no new version (its ``version`` is None).
- If a session fails (``DesignerRun.ok`` false) or a check above fails, the studio stops.
  What the failed pass made is kept as a version too when it can be built (labelled as
  stopped), and then the last other version whose build held is put back
  (``versions.restore``);
  ``StudioRun.error`` says so in plain words. The pictures in renders/ are redrawn for the
  project's final state.
- ``on_event`` receives every stream-json event of every session (as ``run_designer``
  gives them), and the studio's own events, each with an "event" key:
  ``{"event": "pass_started", "pass", "index", "of", "job", "words"}`` (``words``: "Pass 2 of
  6: laying out the main shapes"), ``{"event": "pass_ended", "pass", "index", "of", "ok",
  "skipped", "version", "error"}``, ``{"event": "restored", "version", "why"}`` and last
  ``{"event": "studio_done", "ok", "version", "sessions"}``. An ``on_event`` that raises
  never stops the work.
- ``StudioRun``: ``ok``, ``passes`` (a ``PassResult`` each: name, ok, skipped, error, turns,
  version, closing words, duration, cost, the ``DesignerRun``), ``start_version``,
  ``version`` (the project's version at the end), ``restored`` (the version put back, or
  None), ``sessions`` (AI sessions started), ``error``. ``studio/run.json`` records the same
  after every pass.

Implementation notes
--------------------
- Each session is ``run_pass(project, pass_, message, ...)``: one ``runner.run_session``
  with the composed prompt (written to ``studio/prompts/<pass>.md``), the MCP config of
  ``runner.mcp_config`` pointed at ``studio_server`` with ``--tools`` and ``--ops``, the
  transcript in the project's ``designer/`` folder (``<UTC time>-<pass>.jsonl``) and the
  runner's flags, environment and refusals unchanged. The studio looks ``run_pass`` up on
  this module at call time, so tests replace it with a fake that plays the pass through the
  real tools.
- ``python -m bricksnap.designer.studio PROJECT [--passes ...] [--rounds N] [--wish TEXT]``
  runs the studio and prints each pass and each tool call; ``--judge A B ...`` instead
  compares versions with ``judge.judge_versions``.
- The plan pass's message carries the person's ``wish``, quoted exactly, as
  ``runner.WISH_MESSAGE`` does. The fix pass's message carries the critic's report in plain
  words (``studio_tools.critique_words``).
"""

from __future__ import annotations

import contextlib
import json
import shutil
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bricksnap import versions
from bricksnap.design import OPS
from bricksnap.designer import runner
from bricksnap.designer.runner import DEFAULT_MODEL, DesignerRun, Role
from bricksnap.designer.studio_tools import (
    CRITIQUE_FILE,
    PLAN_FILE,
    STUDIO_DIR,
    critique_words,
    load_critique,
    load_plan,
)
from bricksnap.project import Project, ProjectError
from bricksnap.types import write_text_atomic

PROMPTS_DIR = Path(__file__).parent / "prompts"
COMMON_PROMPT = "common.md"
SERVER_MODULE = "bricksnap.designer.studio_server"
RUN_FILE = "run.json"
MAX_ROUNDS = 3

_LOOK = ("describe", "render", "measure")
_EDIT = (*_LOOK, "apply_ops", "rebuild")
_SHAPE_OPS = ("add", "remove", "paint")


@dataclass(frozen=True)
class Pass:
    name: str
    job: str  # what it does, in a few words, for progress: "laying out the main shapes"
    label: str  # the version's label: "Outline: the main shapes laid out"
    tools: tuple[str, ...]
    ops: tuple[str, ...] = ()
    max_turns: int = 40
    timeout_s: int = 1800
    message: str = ""
    changes_model: bool = True


PLAN = Pass(
    name="plan",
    job="studying the model and planning it",
    label="Plan",
    tools=("describe", "render", "brief", "plan"),
    max_turns=30,
    timeout_s=1200,
    message="Study this model and record the brief and the construction plan for it.",
    changes_model=False,
)
OUTLINE = Pass(
    name="outline",
    job="laying out the main shapes",
    label="Outline: the main shapes laid out",
    tools=_EDIT,
    ops=_SHAPE_OPS,
    max_turns=40,
    timeout_s=1800,
    message="The design is empty. Lay out the main shapes of the plan.",
)
REFINE = Pass(
    name="refine",
    job="shaping and colouring the regions",
    label="Refine: shapes and colours",
    tools=_EDIT,
    ops=_SHAPE_OPS,
    max_turns=50,
    timeout_s=2400,
    message="Refine the outline into the model the plan describes.",
)
SURFACE = Pass(
    name="surface",
    job="choosing the surface and placing details",
    label="Surface: finish and details",
    tools=_EDIT,
    ops=("paint", "set_finish", "place_detail", "remove_detail"),
    max_turns=40,
    timeout_s=1800,
    message="Choose the surface finish and place the details.",
)
CRITIC = Pass(
    name="critic",
    job="a critic looking at it with fresh eyes",
    label="Critic",
    tools=("render", "measure", "critique"),
    max_turns=20,
    timeout_s=900,
    message=(
        "Here is a brick build and the 3D model it was made from. Look at both and give "
        "your report."
    ),
    changes_model=False,
)
FIX = Pass(
    name="fix",
    job="fixing what the critic found",
    label="Fix: the critic's points",
    tools=_EDIT,
    ops=OPS,
    max_turns=40,
    timeout_s=1800,
    message=(
        "A critic who has not seen how this model was made compared the build with the "
        "original model and found these problems, most important first:\n\n{critique}\n\n"
        "Fix these, and only these."
    ),
)
PASSES = {p.name: p for p in (PLAN, OUTLINE, REFINE, SURFACE, CRITIC, FIX)}
DEFAULT_PASSES = ("plan", "outline", "refine", "surface")
DEFAULT_ROUNDS = 1

STUDIO = Role(
    tools="studio tools",
    stopped_kept=" The edits made so far are saved.",
    timeout="The pass did not finish within {duration} and was stopped.",
    max_turns="The pass used all its turns ({max_turns}) before it finished.",
    switched_kept=" The edits it made are saved.",
)


@dataclass
class PassResult:
    name: str
    ok: bool = False
    skipped: bool = False
    error: str = ""
    turns: int = 0
    version: int | None = None
    closing: str = ""
    duration_s: float = 0.0
    cost_usd: float | None = None
    run: DesignerRun | None = None

    def record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "skipped": self.skipped,
            "error": self.error,
            "turns": self.turns,
            "version": self.version,
            "closing": self.closing,
            "duration_s": round(self.duration_s, 1),
            "cost_usd": self.cost_usd,
        }


@dataclass
class StudioRun:
    ok: bool = False
    passes: list[PassResult] = field(default_factory=list)
    start_version: int | None = None
    version: int | None = None
    restored: int | None = None
    sessions: int = 0
    error: str = ""


# ---- one session --------------------------------------------------------------------------


def prompt_text(pass_: Pass) -> str:
    """The pass's system prompt: the common part, then its own."""
    common = (PROMPTS_DIR / COMMON_PROMPT).read_text(encoding="utf-8").rstrip()
    own = (PROMPTS_DIR / f"{pass_.name}.md").read_text(encoding="utf-8").rstrip()
    return own + "\n\n" + common + "\n"


def studio_mcp(project: Project, pass_: Pass) -> dict[str, Any]:
    """The MCP config of one pass: the studio's server with this pass's tools."""
    config = runner.mcp_config(project.path.resolve(), module=SERVER_MODULE)
    server = config["mcpServers"][runner.SERVER_NAME]
    server["args"] += ["--tools", ",".join(pass_.tools), "--ops", ",".join(pass_.ops or OPS)]
    return config


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


RETRY_WAITS_S = (30, 90, 240)
"""How long to wait before trying a session again when the AI service was busy."""
_BUSY_SIGNS = ("529", "overloaded", "503", "service unavailable", "rate limit", "try again in")
_sleep = time.sleep  # replaced in tests


def service_was_busy(run: DesignerRun) -> bool:
    """True when a session failed because the AI service was busy, not because of the work:
    the kind of failure that goes away by itself and is worth trying again."""
    text = run.error.lower()
    return not run.ok and any(sign in text for sign in _BUSY_SIGNS)


def run_pass(
    project: Project,
    pass_: Pass,
    message: str,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> DesignerRun:
    """One clean-room session for one pass (see the implementation notes).

    When the AI service is busy (``service_was_busy``) the session is started again after
    each wait in ``RETRY_WAITS_S``, with a ``{"event": "retry", "pass", "attempt", "wait_s",
    "why"}`` event before each wait. A new session sees the design as the failed one left
    it, which for a session that never got to work is as it was. Any other failure is
    returned as it is.
    """
    folder = project.path / STUDIO_DIR / "prompts"
    folder.mkdir(parents=True, exist_ok=True)
    prompt_file = folder / f"{pass_.name}.md"
    prompt_file.write_text(prompt_text(pass_), encoding="utf-8")
    for attempt, wait_s in enumerate((*RETRY_WAITS_S, None), start=1):
        run = runner.run_session(
            prompt_file=prompt_file,
            mcp=studio_mcp(project, pass_),
            message=message,
            transcript=project.designer_dir / f"{_stamp()}-{pass_.name}.jsonl",
            model=model,
            effort=effort,
            max_turns=pass_.max_turns,
            timeout_s=pass_.timeout_s,
            on_event=on_event,
            role=STUDIO,
        )
        if wait_s is None or not service_was_busy(run):
            break
        _tell(
            on_event,
            event="retry",
            **{"pass": pass_.name},
            attempt=attempt,
            wait_s=wait_s,
            why=runner.redact(run.error),
        )
        _sleep(wait_s)
    run.kind = pass_.name
    return run


# ---- the run ------------------------------------------------------------------------------


def _tell(on_event: Callable[[dict[str, Any]], None] | None, **event: Any) -> None:
    if on_event is not None:
        with contextlib.suppress(Exception):  # progress output must never stop the work
            on_event(event)


def _resolve(passes: Sequence[str | Pass] | None, rounds: int) -> list[Pass]:
    if not isinstance(rounds, int) or not 0 <= rounds <= MAX_ROUNDS:
        raise ValueError(f"Choose 0 to {MAX_ROUNDS} rounds of critic and fix, not {rounds}.")
    chosen: list[Pass] = []
    for p in DEFAULT_PASSES if passes is None else passes:
        if isinstance(p, Pass):
            chosen.append(p)
        elif p in PASSES:
            chosen.append(PASSES[p])
        else:
            raise ValueError(f"There is no pass called {p!r}; the passes are {', '.join(PASSES)}.")
    chosen += [CRITIC, FIX] * rounds
    for i, p in enumerate(chosen):
        if p.name == "fix" and not any(q.name == "critic" for q in chosen[:i]):
            raise ValueError("A fix pass needs a critic pass before it.")
    if not chosen:
        raise ValueError("There are no passes to run.")
    return chosen


def _kind_now(project: Project) -> str:
    if runner.has_brief(project):
        return "designed"
    return "manual" if project.load_design().log else "converted"


def _settle(project: Project, catalog: Any) -> Any:
    """Build the project when its build is not made from its design; draw its card."""
    from bricksnap import pipeline

    design = project.load_design()
    build = None
    if not project.build_is_current(design):
        build = pipeline.rebuild(project, catalog=catalog)
    pipeline.render_card(project, catalog=catalog)
    return build if build is not None else project.load_build()


def _last_valid(project: Project, exclude: int | None = None) -> int | None:
    for v in reversed(versions.versions(project)):
        if v.valid and v.n != exclude:
            return v.n
    return None


def _short(text: str, limit: int = 600) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _write_run(project: Project, result: StudioRun, sequence: list[Pass], status: str) -> None:
    data = {
        "status": status,
        "ok": result.ok,
        "error": result.error,
        "start_version": result.start_version,
        "version": result.version,
        "restored": result.restored,
        "sessions": result.sessions,
        "planned": [p.name for p in sequence],
        "passes": [r.record() for r in result.passes],
    }
    folder = project.path / STUDIO_DIR
    folder.mkdir(exist_ok=True)
    write_text_atomic(folder / RUN_FILE, json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def _start_empty(project: Project) -> None:
    from bricksnap.design import cleared

    project.save_design(cleared(project.load_design()))
    project.build_path.unlink(missing_ok=True)
    project.ldraw_path.unlink(missing_ok=True)


def run_studio(
    project: Project,
    *,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
    passes: Sequence[str | Pass] | None = None,
    rounds: int = DEFAULT_ROUNDS,
    wish: str | None = None,
) -> StudioRun:
    """Design ``project`` in passes (see the contract). Never raises for a pass that fails;
    the result says what happened."""
    from bricksnap import pipeline
    from bricksnap.catalog import load_catalog

    sequence = _resolve(passes, rounds)
    names = [p.name for p in sequence]
    project.load_design()  # a project with nothing to design fails here
    if "plan" not in names and (load_plan(project) is None or not runner.has_brief(project)):
        raise ValueError(
            "This project has no construction plan and brief to build from, so the passes "
            "must start with the plan pass."
        )
    catalog = load_catalog()
    result = StudioRun()
    _settle(project, catalog)
    result.start_version = versions.record(
        project, _kind_now(project), "Before the studio", "The model as it was before the studio."
    )
    result.version = result.start_version
    folder = project.path / STUDIO_DIR
    folder.mkdir(exist_ok=True)
    (folder / CRITIQUE_FILE).unlink(missing_ok=True)
    if "plan" in names:
        (folder / PLAN_FILE).unlink(missing_ok=True)
        project.meta.pop("brief", None)
        project.save_meta()
    if "outline" in names:
        _start_empty(project)
    _write_run(project, result, sequence, "running")

    total = len(sequence)
    critiques = 0
    report: dict[str, Any] | None = None
    stop = False
    for index, p in enumerate(sequence, start=1):
        outcome = PassResult(name=p.name)
        result.passes.append(outcome)
        if stop or (p.name == "fix" and (report is None or report.get("verdict") == "good")):
            outcome.ok, outcome.skipped = True, True
            _tell(on_event, event="pass_ended", **_where(p, index, total), ok=True, skipped=True,
                  version=None, error="")  # fmt: skip
            continue
        _tell(
            on_event,
            event="pass_started",
            **_where(p, index, total),
            job=p.job,
            words=f"Pass {index} of {total}: {p.job}",
        )
        message = p.message
        if p.name == "plan" and wish and wish.strip():
            message += (
                "\n\nThe person who made this model also has a wish for the design, in their "
                f'own words:\n\n"{wish.strip()}"\n\nMake the wish part of your brief and plan.'
            )
        if p.name == "fix" and report is not None:
            message = message.replace("{critique}", critique_words(report))
        started = time.monotonic()
        result.sessions += 1
        try:
            run = run_pass(project, p, message, model=model, effort=effort, on_event=on_event)
        except Exception as e:  # a fault in one session stops the studio, never loses work
            run = DesignerRun(ok=False, error=runner.redact(str(e) or type(e).__name__))
        project = Project(project.path)  # the session changed project.json (the brief)
        outcome.run = run
        outcome.turns, outcome.cost_usd = run.turns, run.cost_usd
        outcome.closing = _short(run.final_text)
        problem = run.error if not run.ok else ""

        if (
            not problem
            and p.name == "plan"
            and (not runner.has_brief(project) or load_plan(project) is None)
        ):
            problem = "The plan pass ended without recording both the brief and the plan."
        if not problem and p.name == "critic":
            report = load_critique(project)
            if report is None:
                problem = "The critic ended without giving its report."
            else:
                critiques += 1
                shutil.move(folder / CRITIQUE_FILE, folder / f"critique-{critiques}.json")
                outcome.closing = _short(critique_words(report))
                stop = report.get("verdict") == "good"
        if p.changes_model:
            problem = _keep_pass(project, p, outcome, result, catalog, problem)
        outcome.duration_s = time.monotonic() - started
        outcome.ok = not problem
        outcome.error = problem
        _tell(on_event, event="pass_ended", **_where(p, index, total), ok=outcome.ok,
              skipped=False, version=outcome.version, error=problem)  # fmt: skip
        if problem:
            result.error = f"The {p.name} pass did not succeed: {problem}"
            _put_back(project, result, on_event, exclude=outcome.version)
            break
        _write_run(project, result, sequence, "running")
    else:
        result.ok = True

    project = Project(project.path)
    with contextlib.suppress(Exception):  # pictures are a convenience; the versions are kept
        if project.has_build() and project.build_is_current():
            pipeline.render_compare(project, catalog=catalog)
            pipeline.render_card(project, catalog=catalog)
    result.version = versions.current(project)
    _write_run(project, result, sequence, "done")
    _tell(on_event, event="studio_done", ok=result.ok, version=result.version,
          sessions=result.sessions)  # fmt: skip
    return result


def _where(p: Pass, index: int, total: int) -> dict[str, Any]:
    return {"pass": p.name, "index": index, "of": total}


def _keep_pass(
    project: Project,
    p: Pass,
    outcome: PassResult,
    result: StudioRun,
    catalog: Any,
    problem: str,
) -> str:
    """Build and keep what a pass made as a version. Returns the problem, if any: the one the
    session already had, or one found here (an empty design, a build that does not hold)."""
    design = project.load_design()
    if not design.filled.any():
        return problem or "The pass left the design empty."
    try:
        build = _settle(project, catalog)
    except Exception as e:
        why = str(e) or type(e).__name__
        return problem or runner.redact(f"its design could not be built ({why})")
    label = p.label if not problem else f"{p.label} (stopped part way)"
    note = problem or outcome.closing
    before = versions.current(project)
    try:
        n = versions.record(project, "pass", label, note)
    except ProjectError as e:
        return problem or str(e)
    outcome.version = n if n != before else None  # None: the pass changed nothing
    result.version = n
    if not problem and not (build.report is not None and build.report.ok):
        first = build.report.text.splitlines()[0] if build.report and build.report.text else ""
        return (
            "its build does not hold together as one standing model"
            + (f" ({first.strip()})" if first.strip() else "")
            + "."
        )
    return problem


def _put_back(
    project: Project,
    result: StudioRun,
    on_event: Callable[[dict[str, Any]], None] | None,
    exclude: int | None = None,
) -> None:
    """Restore the last version that held, other than ``exclude`` (the failed pass's own)."""
    n = _last_valid(project, exclude)
    if n is None:
        result.error += " No earlier version holds together, so nothing was put back."
        return
    try:
        versions.restore(project, n)
    except Exception as e:
        result.error += f" Putting back version {n} failed too ({runner.redact(str(e))})."
        return
    result.restored = n
    result.error += f" The project was put back to version {n}, the last one that held together."
    _tell(on_event, event="restored", version=n, why=result.error)


__all__ = [
    "DEFAULT_PASSES",
    "DEFAULT_ROUNDS",
    "PASSES",
    "Pass",
    "PassResult",
    "StudioRun",
    "prompt_text",
    "run_pass",
    "run_studio",
]


# ---- command line ---------------------------------------------------------------------------


def _progress(event: dict[str, Any]) -> None:
    if event.get("event") == "pass_started":
        print(f"\n== {event['words']}", flush=True)
    elif event.get("event") == "pass_ended":
        if event.get("skipped"):
            print(f"== {event['pass']}: skipped", flush=True)
        else:
            state = "ok" if event.get("ok") else "FAILED: " + str(event.get("error", ""))
            kept = f"; kept as version {event['version']}" if event.get("version") else ""
            print(f"== {event['pass']}: {state}{kept}", flush=True)
    elif event.get("event") == "restored":
        print(f"== put back version {event['version']}", flush=True)
    elif "type" in event:
        runner._progress(event)


def main(argv: list[str] | None = None) -> None:
    """``python -m bricksnap.designer.studio PROJECT [--passes plan,outline] [--rounds 1]
    [--wish TEXT] [--judge 3 7]``: run the studio (or, with --judge, only compare versions)
    and print what happens. Uses the Claude subscription, never an API key."""
    import argparse
    import sys

    ap = argparse.ArgumentParser(prog="python -m bricksnap.designer.studio")
    ap.add_argument("project")
    ap.add_argument("--passes", default=",".join(DEFAULT_PASSES))
    ap.add_argument("--rounds", type=int, default=DEFAULT_ROUNDS)
    ap.add_argument("--wish", default=None)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--judge", type=int, nargs="+", default=None, help="version numbers")
    args = ap.parse_args(argv)
    try:
        project = Project(args.project)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2) from None
    if args.judge:
        from bricksnap.designer.judge import judge_versions

        verdict = judge_versions(project, args.judge, model=args.model, effort=args.effort)
        print("ranking (best first): " + ", ".join(f"version {n}" for n in verdict.ranking))
        for n in verdict.ranking:
            print(f"  version {n}: {verdict.reasons.get(n, '')}")
        print(verdict.summary or verdict.error)
        return
    result = run_studio(
        project,
        model=args.model,
        effort=args.effort,
        on_event=_progress,
        passes=[p for p in args.passes.split(",") if p],
        rounds=args.rounds,
        wish=args.wish,
    )
    print("\nfinished" if result.ok else "\nSTOPPED: " + result.error)
    print(f"AI sessions: {result.sessions}; the project is now version {result.version}")
    raise SystemExit(0 if result.ok else 1)


if __name__ == "__main__":
    main()
