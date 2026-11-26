"""Run one free-build session with the AI (research prototype).

    python -m bricksnap.lab.run "TASK" --out DIR [--model claude-fable-5-2] [--effort high]
        [--max-turns 60] [--max-checks 25] [--timeout 3600] [--reference PICTURE ...]
        [--start MODEL.ldr] [--guide]
    python -m bricksnap.lab.blind "TASK" --out DIR [...]      (no tools but a final submit)

CONTRACT (tests in tests/test_lab.py; no test starts a real session)

- One clean-room session through ``bricksnap.designer.runner.run_session``, unchanged: its
  command, flags, scrubbed environment and refusals (no API key, the tool server started,
  the model asked for answered). The system prompt is ``prompt.md`` (``blind_prompt.md`` for
  blind runs); the tool server is ``bricksnap.lab.mcp_server`` for the work folder ``--out``.
- ``--out`` must be a new or empty folder. It gets ``config.json`` (mode, check limit),
  ``reference/`` (copies of ``--reference`` pictures, shown to the AI by the ``reference``
  tool, which the message tells it to call first), the transcript (``transcript/<UTC>.jsonl``,
  rewritten through ``runner.redact`` when the session ends, so it holds no e-mail address
  or home folder), everything the tools save (see ``tools``), and at the end:
  ``final.ldr`` (the model as it was left; in a blind run, what it handed in),
  ``final-report.txt`` and ``final.png`` (the checker's report and the three views, made
  after the session, for the person), and ``session.json`` (ok, error, mode, model, effort,
  turns, seconds, the usage and cost Claude Code reported, the tools called and how often,
  tool errors, how many checks, the final summary line, and the session's closing words,
  redacted; and ``usage_limit``, ``limit_resets`` and ``limit_resets_at``, the runner's:
  Claude Code's line and when the limit resets, in words and in seconds since 1970, when
  the subscription's usage limit stopped the session, else "", "" and null).
- The user message is the task, the number of checks allowed, and (with references) the
  instruction to look at them first: build what they show (a photo, a drawing, or a sheet
  of views) as a brick model of the size asked for, its outline, proportions, colours and
  recognisable features, not a background; the words say what it is, and win where the
  two differ. In a change (below) it says instead that the model was built from them and
  that reference shows them again when the change is about how it should look. The task
  is the person's text, sent as the message and never put in the prompt or on a command
  line.
- ``--start FILE.ldr``: the session begins with that model (``tools.start_model``): moved
  along x so its middle is at x = 0 (the shift is in config.json), checked as attempt 0 (not
  counted), and, in a blind run, given to the AI in the message since it has no tools to
  read it. ``prompt.md`` has a paragraph for this case.
- The parts index is built before the session starts, so no tool call waits minutes for it.
- It prints where everything is.
- ``build(task, out, ...)`` is the same session for other code (the free-build projects of
  ``bricksnap.lab.freebuild``): it takes the options as keywords, passes every stream-json
  event to ``on_event``, prints only the starting model's summary, and returns the
  session record. With ``change_of`` (the words the model was first built from) and
  ``start``, the message says the model in the work area is one the AI built earlier from
  those words and the task is one change to it; ``prompt.md`` has a paragraph for that
  case too.
- ``guide`` (``--guide``; ``build(..., guide=False)``; EXPERIMENTAL): build the way set
  designers do (``bricksnap.lab.guide``). It is recorded as ``"guide"`` in config.json and
  session.json, which also has ``"playbook"``: the title of the last playbook the
  ``playbook`` tool returned (from ``playbook.json``), or null. With it on, the system
  prompt is ``guide.system_prompt(prompt.md)``, written to ``system-prompt.md`` in the work
  folder and given from there, and the tools gain ``playbook`` and ``brief`` (``tools``,
  ``art``); config.json then has ``"subject"`` (the words the model is built from) and
  session.json the brief and the critique (``art.record``). With it off,
  everything the builder is given (the prompt file, the message, the tool list) is exactly
  what it was before the switch existed. A blind run refuses it.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bricksnap.designer import runner

LAB = Path(__file__).parent
PROMPT_FILE = LAB / "prompt.md"
BLIND_PROMPT_FILE = LAB / "blind_prompt.md"
SERVER_MODULE = "bricksnap.lab.mcp_server"
DEFAULT_MODEL = "claude-fable-5-2"
GUIDE_PROMPT_NAME = "system-prompt.md"

LAB_ROLE = runner.Role(
    tools="free-build tools",
    stopped_kept=" The model built so far is saved in the work folder.",
    timeout="The session did not finish within {duration} and was stopped. The model built so "
    "far is saved in the work folder.",
    max_turns="The session used all its turns ({max_turns}) before it finished. The model built "
    "so far is saved in the work folder.",
    switched_kept=" The model it built is saved.",
)


def message(
    task: str,
    mode: str,
    max_checks: int,
    references: int,
    start: str | None = None,
    change_of: str | None = None,
    guide: bool = False,
    brief: str | None = None,
) -> str:
    task = task.strip()
    parts = ["Build this model:", "", f'"{task}"', ""]
    if start is not None and change_of is not None and mode != "blind":
        parts = [
            "You built this model earlier, from these words:",
            "",
            f'"{change_of.strip()}"',
            "",
            "Now make this change to it:",
            "",
            f'"{task}"',
            "",
            "The model is already in the work area. Call check first to see it (it is attempt "
            "0; that check does not count), then make the change as your instructions say for "
            "a change, and keep the rest of the model as it is.",
        ]
    elif start is not None:
        if mode == "blind":
            parts.append(
                "You start from a model that software made from the reference (it is below, "
                "as LDraw). Hand in the whole improved model as one file with submit."
            )
            parts.extend(["", "```ldraw", start.rstrip(), "```", ""])
        else:
            parts.append(
                "You start from a model that software made from the reference: it is already "
                "in the work area. Call check first to see it (it is attempt 0; that check "
                "does not count), then improve it as your instructions say for this case."
            )
    one = references == 1
    if references and start is not None and change_of is not None and mode != "blind":
        parts.append(
            f"The model was built from {'a reference picture' if one else 'reference pictures'}"
            f" of what to build. Call reference to see {'it' if one else 'them'} again when the "
            "change is about how the model should look."
        )
    elif references:
        parts.append(
            f"There {'is' if one else 'are'} {references} reference picture"
            f"{'' if one else 's'} of what to build: call reference first and study "
            f"{'it' if one else 'them'}. Build what {'it shows' if one else 'they show'} as a "
            "brick model of the size asked for: the outline, the proportions, the colours and "
            "the features that make it recognisable, not a background or the lighting. The "
            f"words say what it is; where the words and the picture{'' if one else 's'} "
            "differ, follow the words."
        )
    if guide and brief and start is not None and change_of is not None and mode != "blind":
        parts.append(
            "The model's art direction (its brief), as it was written when it was built:\n"
            + brief
            + "\nBuild the change to it. If the change alters how the model looks, first call "
            "brief with the new version and your reason."
        )
    if mode == "blind":
        parts.append("Write the whole model as an LDraw file and hand it in once with submit.")
    elif guide:
        parts.append(
            f"You have {max_checks} checks (check and submit with ldraw each use one; handing "
            "in does not). Work as your instructions say: the subject and its features, "
            "playbook, the parts for its signature shapes, the brief, then build to it, "
            "checking early and often and fixing every problem. When the check is clean and "
            "the model looks right, hand in with submit {}: it shows the model beside your "
            "brief with what can be counted and ten questions. Answer them with submit's "
            "critique, rebuild what you answer no to when you are asked, then write your "
            "closing words."
        )
    else:
        parts.append(
            f"You have {max_checks} checks (check and submit each use one). Follow your way of "
            "working: find the parts, build the structure, check early and often, fix every "
            "problem, look at the pictures, and stop when the check is clean and the model "
            "looks right. Then write your closing words."
        )
    return "\n".join(parts)


def prompt_file(out: Path, mode: str, guide: bool, session: str = "first") -> Path:
    """The system prompt's file: ``prompt.md`` (``blind_prompt.md``), or with the guide the
    guide-mode instructions for this kind of session ("first", "start", "change") written
    to ``out/system-prompt.md``."""
    if mode == "blind":
        return BLIND_PROMPT_FILE
    if not guide:
        return PROMPT_FILE
    from bricksnap.lab.guide import system_prompt

    path = out / GUIDE_PROMPT_NAME
    text = system_prompt(PROMPT_FILE.read_text(encoding="utf-8"), session)
    path.write_text(text, encoding="utf-8")
    return path


def prepare(
    out: Path,
    mode: str,
    max_checks: int,
    references: list[Path],
    start: Path | None = None,
    guide: bool = False,
    subject: str | None = None,
    parts: int | None = None,
) -> str | None:
    """Make the work folder. With ``start``, the model is that file, moved along x so its
    middle is at x = 0 (``edit.centre_x``), and checked as attempt 0; the moved text is
    returned."""
    if guide and mode == "blind":
        raise SystemExit("A blind run has no tools, so it cannot use the guide.")
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; give a new folder for each session.")
    out.mkdir(parents=True, exist_ok=True)
    config: dict[str, Any] = {"mode": mode, "max_checks": max_checks, "guide": guide}
    if guide and subject:  # the playbook's style section is chosen by the subject's words
        config["subject"] = subject
    if guide and parts:  # the hand-in sheet and the halfway reminder count against it
        config["parts"] = parts
    text = None
    if start is not None:
        from bricksnap.lab.edit import centre_x

        if not start.is_file():
            raise SystemExit(f"The starting model {start} was not found.")
        text, shift = centre_x(start.read_text(encoding="utf-8", errors="replace"))
        config["start"] = {"file": start.name, "moved_x_by": shift}
    (out / "config.json").write_text(json.dumps(config, indent=1) + "\n", encoding="utf-8")
    if references:
        ref = out / "reference"
        ref.mkdir()
        for i, pic in enumerate(references, 1):
            if not pic.is_file():
                raise SystemExit(f"Reference picture {pic} was not found.")
            shutil.copyfile(pic, ref / f"reference-{i}{pic.suffix.lower()}")
    if text is not None:
        from bricksnap.lab.tools import _model, start_model

        summary = start_model(out, text)
        print(f"starting model: {summary}", flush=True)
        return _model(out)
    return None


def _redact_file(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    tmp = path.with_suffix(".tmp")
    tmp.write_text(runner.redact(text), encoding="utf-8")
    tmp.replace(path)


def finish(
    out: Path,
    mode: str,
    run: runner.DesignerRun,
    result_event: dict[str, Any] | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    """After the session: redact the transcript, write the final model, report, picture and
    session.json. Returns the session record."""
    from bricksnap.lab import picture
    from bricksnap.lab.validate import check

    for t in (out / "transcript").glob("*.jsonl"):
        _redact_file(t)
    final = out / "final.ldr"
    if mode != "blind":  # a blind run's result is only what it handed in
        model = out / "model.ldr"
        if model.exists():
            shutil.copyfile(model, final)
    summary = "no model was made"
    if final.exists():
        text = final.read_text(encoding="utf-8")
        report = check(text)
        summary = report.summary()
        (out / "final-report.txt").write_text(report.text() + "\n", encoding="utf-8")
        if report.placed:
            try:
                picture.model_sheet(text, out / "final.png", title="Final: " + summary)
            except picture.PictureError as e:
                (out / "final-report.txt").open("a", encoding="utf-8").write(
                    f"\n(No picture: {e})\n"
                )
    calls: dict[str, int] = {}
    for name in run.tools_called:
        short = name.removeprefix(runner.TOOL_PREFIX)
        calls[short] = calls.get(short, 0) + 1
    usage = None
    if result_event:
        usage = {
            k: result_event.get(k)
            for k in (
                "usage",
                "modelUsage",
                "num_turns",
                "total_cost_usd",
                "duration_ms",
                "duration_api_ms",
            )
        }
    record = {
        **extra,
        "mode": mode,
        "ok": run.ok,
        "error": run.error,
        "usage_limit": run.usage_limit,
        "limit_resets": run.limit_resets,
        "limit_resets_at": run.limit_resets_at,
        "turns": run.turns,
        "seconds": round(run.duration_s, 1),
        "cost_usd_reported": run.cost_usd,
        "usage_reported": usage,
        "models_used": run.models_used,
        "tools_called": calls,
        "tool_errors": run.tool_errors,
        "checks": len(
            [a for a in (out / "attempts").glob("attempt-*.ldr") if a.stem != "attempt-000"]
        ),
        "final_summary": summary,
        "closing_words": run.final_text,
        "playbook": _playbook_used(out),
        "replies": _replies(out),
        **_art_record(out, extra),
    }
    text = runner.redact(json.dumps(record, indent=1))
    (out / "session.json").write_text(text + "\n", encoding="utf-8")
    return record


def _playbook_used(out: Path) -> str | None:
    try:
        data = json.loads((out / "playbook.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    title = data.get("playbook") if isinstance(data, dict) else None
    return str(title) if isinstance(title, str) else None


def _replies(out: Path) -> int:
    """How many replies the model gave (distinct assistant messages in the transcript):
    what Claude Code's --max-turns limits. Its own "turns" (num_turns) counts tool calls
    and the final answer, so a session can report more turns than its limit."""
    seen: set[str] = set()
    for t in (out / "transcript").glob("*.jsonl"):
        with contextlib.suppress(OSError):
            for line in t.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if isinstance(event, dict) and event.get("type") == "assistant":
                    msg = event.get("message")
                    mid = msg.get("id") if isinstance(msg, dict) else None
                    if isinstance(mid, str):
                        seen.add(mid)
    return len(seen)


def _art_record(out: Path, extra: dict[str, Any]) -> dict[str, Any]:
    """Guide mode only: the brief and the critique (``art.record``)."""
    if extra.get("guide") is not True:
        return {}
    from bricksnap.lab import art

    return art.record(out)


def _progress(event: dict[str, Any]) -> None:
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        tools = ", ".join(str(t).removeprefix(runner.TOOL_PREFIX) for t in event.get("tools") or [])
        print(f"started; tools: {tools or 'none'}", flush=True)
    elif kind == "assistant":
        for item in runner.StreamParser._content(event):
            if item.get("type") == "tool_use":
                name = str(item.get("name", "")).removeprefix(runner.TOOL_PREFIX)
                args = item.get("input") or {}
                detail = ""
                if name in ("search_parts", "part_info"):
                    detail = " " + str(args.get("query") or args.get("part") or "")[:60]
                elif name == "place":
                    detail = f" {args.get('part')} on line {args.get('line')}"
                print(f"-> {name}{detail}", flush=True)
            elif item.get("type") == "text" and item.get("text"):
                print(runner.redact(str(item["text"])).strip() + "\n", flush=True)


def build(
    task: str,
    out: Path,
    *,
    mode: str = "tools",
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    max_turns: int = 60,
    max_checks: int = 25,
    timeout: int = 3600,
    references: list[Path] | None = None,
    start: Path | None = None,
    change_of: str | None = None,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    guide: bool = False,
    parts: int | None = None,
    brief: dict[str, Any] | None = None,
    brief_run: int | None = None,
) -> dict[str, Any]:
    """Run one session into the new or empty folder ``out`` and return its record (what
    session.json holds). ``on_event`` gets every stream-json event as it arrives (from the
    runner's reader thread). With ``change_of`` (the words the model was first built from)
    the session starts from ``start`` and the task is a change to it."""
    from bricksnap.lab.search import load_index

    if not task.strip():
        raise SystemExit("Say what to build.")
    refs = list(references or [])
    load_index()
    start_text = prepare(
        out, mode, max_checks, refs, start, guide=guide, subject=change_of or task, parts=parts
    )
    brief_text = None
    if guide and brief and change_of is not None and start is not None:
        from bricksnap.lab import art

        art.seed(out, brief, brief_run)  # a change builds to the model's brief
        brief_text = art.brief_lines(brief)
    session = "change" if change_of is not None else "start" if start is not None else "first"
    result_event: dict[str, Any] = {}

    def hear(event: dict[str, Any]) -> None:
        if event.get("type") == "result":
            result_event.update(event)
        if on_event is not None:
            on_event(event)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run = runner.run_session(
        prompt_file=prompt_file(out, mode, guide, session),
        mcp=runner.mcp_config(out, module=SERVER_MODULE),
        message=message(
            task,
            mode,
            max_checks,
            len(refs),
            start_text,
            change_of=change_of,
            guide=guide,
            brief=brief_text,
        ),
        transcript=out / "transcript" / f"{stamp}.jsonl",
        model=model,
        effort=effort,
        max_turns=max_turns,
        timeout_s=timeout,
        on_event=hear,
        role=LAB_ROLE,
    )
    extra = {
        "start": start and start.name,
        "task": task,
        "change_of": change_of,
        "model": model,
        "effort": effort,
        "max_turns": max_turns,
        "max_checks": max_checks,
        "started": stamp,
        "guide": guide,
    }
    return finish(out, mode, run, result_event or None, extra)


def main(argv: list[str] | None = None, mode: str = "tools") -> None:
    prog = "python -m bricksnap.lab.blind" if mode == "blind" else "python -m bricksnap.lab.run"
    ap = argparse.ArgumentParser(
        prog=prog,
        description="Run one free-build session with the AI (uses your Claude subscription)."
        + (" Blind: no tools but one final submit." if mode == "blind" else ""),
    )
    ap.add_argument("task", help="what to build, in plain words")
    ap.add_argument("--out", required=True, help="a new folder for this session's results")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-turns", type=int, default=60)
    ap.add_argument("--max-checks", type=int, default=25)
    ap.add_argument("--timeout", type=int, default=3600, help="seconds")
    ap.add_argument("--reference", nargs="*", default=[], help="pictures of what to build")
    ap.add_argument("--start", default=None, help="an LDraw file to start from (attempt 0)")
    if mode != "blind":
        ap.add_argument(
            "--guide",
            action="store_true",
            help="build the way set designers do (experimental): the guide's rules and playbooks",
        )
    args = ap.parse_args(argv)
    if not args.task.strip():
        raise SystemExit("Say what to build.")
    out = Path(args.out).expanduser().resolve()
    refs = [Path(p).expanduser().resolve() for p in args.reference]
    from bricksnap.lab import picture

    print("preparing the parts index (the first time takes a little while)...", flush=True)
    if not picture.available():
        print(
            "warning: LeoCAD or xvfb-run was not found, so there will be no pictures.", flush=True
        )
    start = Path(args.start).expanduser().resolve() if args.start else None
    record = build(
        args.task,
        out,
        mode=mode,
        model=args.model,
        effort=args.effort,
        max_turns=args.max_turns,
        max_checks=args.max_checks,
        timeout=args.timeout,
        references=refs,
        start=start,
        on_event=_progress,
        guide=bool(getattr(args, "guide", False)),
    )
    ok = bool(record["ok"])
    print("finished" if ok else "FAILED: " + str(record["error"]))
    print(f"turns: {record['turns']}; time: {record['seconds']:.0f} s; checks: {record['checks']}")
    print(
        "tool calls: "
        + (", ".join(f"{k} x{v}" for k, v in record["tools_called"].items()) or "none")
    )
    print("final model: " + record["final_summary"])
    print(f"results in {out}:")
    for name in (
        "final.ldr",
        "final-report.txt",
        "final.png",
        "session.json",
        "attempts",
        "calls.jsonl",
        "transcript",
    ):
        if (out / name).exists():
            print(f"  {name}")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1:])
