"""Check that the clean-room runner really is clean: the model gets our prompt and our tools.

CONTRACT

``check_parity(model=DEFAULT_MODEL) -> ParityReport`` starts a tiny real session with exactly
the flags ``runner.build_command`` produces (a throwaway project is enough for the MCP
server) and a system prompt containing a unique marker sentence. The user message asks the
model to list every tool it can call and to quote the first sentence of its instructions.
From the stream-json ``init`` event and the reply, report:

- ``tools``: every tool the session announced. ``extra_tools``: any that are not our
  ``mcp__bricksnap__*`` tools, one per entry of ``tools.TOOL_NAMES`` (Claude Code's
  documentation says ``EndConversation`` may remain when MCP tools are present; list
  whatever is actually there).
- whether the model quoted the marker (so our prompt is the system prompt) and whether it
  mentioned any instruction, file, skill, memory or environment detail we did not supply.
- the init event's other inventory fields where present (MCP servers, slash commands,
  agents, skills, plugins, output style, cwd, model).
- ``leftovers``: what the model reports having in its context besides our prompt and the
  user message (see "Known leftovers" in runner.py). Ask the model to quote all of it.
- ``ok`` is True when the only tools are ours plus documented leftovers, the marker was
  quoted, and nothing beyond the known leftovers shows up.

``main()`` (``python -m bricksnap.designer.parity``) runs the check, prints the report in
plain language, and writes it to the file given by ``--out`` when present. This uses a small
amount of the user's Claude subscription; it never uses an API key.

Implementation notes
--------------------
- The session is started through ``runner.run_designer`` (same command, same scrubbed
  environment, same empty working folder) with a probe system prompt in place of prompt.md.
  The throwaway project is a small box made on the spot, so the check does not depend on the
  sample models. It lives in a temporary folder that is deleted afterwards, unless
  ``--keep-in DIR`` is given, in which case it is created inside DIR and kept (its raw
  transcript stays in the project's designer/ folder).
- Everything printed or written is redacted first (``runner.redact``): e-mail addresses
  become "<account email>" and the home directory "~".
- The probe asks for four labelled sections: TOOLS, MARKER (the sentence that starts with
  "Parity marker", whose random code appears only in the system prompt, never in the user
  message), FIRST SENTENCE (the very first sentence of the system prompt) and OTHER CONTEXT
  (everything else, word for word). The first sentence and the other context together are
  the ``leftovers``.
- ``KNOWN_LEFTOVERS`` names each leftover measured on Claude Code 2.1.325 with a pattern that
  recognises it; the report says which of them were seen, so a change shows up. Besides the
  three in runner.py's contract, measured on 2026-11-15: a sentence appended to the system
  prompt telling the model to make independent tool calls together ("If you intend to call
  multiple tools and there are no dependencies between the calls, ..."), and three built-in
  plugins listed in the init event (``DOCUMENTED_BUILTIN_PLUGINS``) that bring no tools,
  skills, agents or text the model can see. No documented flag removes them (they stay on
  even under ``--safe-mode``).
- The reply is split by its labels: each label is taken once, in order, written in capitals
  on a line of its own (markdown marks such as ``**`` or ``##`` around it are allowed), and
  everything after "OTHER CONTEXT:" belongs to that section, so a label-like line inside the
  model's quote cannot end it. A reply with sections but no OTHER CONTEXT is not clean.
- The leftover text is known word for word (measured on Claude Code 2.1.325), so the check
  removes each known sentence or ``key: value`` line (``_KNOWN_TEXT``; only the values that
  differ between machines, such as the e-mail address, folder, platform and date, are left
  open) and looks at what remains. A remaining line is accepted only when it is empty, mere
  punctuation, or made up entirely of words from a small vocabulary that describes the parts
  of a context (``_REMARK_WORDS``: "System prompt text after the marker paragraph:",
  "Reminder attached to your message:"), which gives the model room for its own headings
  and remarks but not for an instruction. Everything else is listed as unexpected. Words
  that point at Claude Code features we switched off (CLAUDE.md, skills, memory, hooks,
  plugins, git status) are flagged as well. A model can paraphrase, so a flag is a reason to
  read the quote, not proof.
- The init event's slash commands, agents and skills must be empty, every plugin must be a
  documented built-in one (an entry of any other shape counts as a problem), ``apiKeySource``
  must be "none" (so no API key was spent), the bricksnap server must be "connected", and,
  where present, ``memory_paths`` must be empty, ``output_style`` "default" and
  ``permissionMode`` "dontAsk"; otherwise ``ok`` is False with a note saying which.
- ``evaluate`` also takes the ``StreamParser`` that read the session (``stream``): if Claude
  Code switched models or added a message of its own (see runner.py), the result is NOT
  CLEAN, and the report lists the models that actually answered next to the requested one.
"""

from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bricksnap.designer.runner import DEFAULT_MODEL, TOOL_PREFIX, StreamParser, redact
from bricksnap.designer.tools import TOOL_NAMES

OUR_TOOLS = tuple(f"{TOOL_PREFIX}{n}" for n in TOOL_NAMES)
DOCUMENTED_EXTRA_TOOLS = ("EndConversation",)
DOCUMENTED_BUILTIN_PLUGINS = (
    "cc-plugin-agents-md",
    "cc-plugin-privacy",
    "cc-plugin-plugin-authoring",
)

INVENTORY_FIELDS = (
    "mcp_servers",
    "slash_commands",
    "agents",
    "skills",
    "plugins",
    "output_style",
    "cwd",
    "model",
    "permissionMode",
    "apiKeySource",
    "memory_paths",
    "claude_code_version",
)
MUST_BE_EMPTY = ("slash_commands", "agents", "skills")

# name -> (what it is, a pattern that recognises it in the model's quote)
KNOWN_LEFTOVERS: dict[str, tuple[str, str]] = {
    "identity": (
        'The Agent SDK identity line before our prompt ("You are a Claude agent, built on '
        "Anthropic's Claude Agent SDK.\")",
        r"Claude Agent SDK",
    ),
    "parallel_calls": (
        "A sentence after our prompt asking for independent tool calls to be made together",
        r"independent calls|call multiple tools",
    ),
    "environment": (
        'The "# Environment" block (working folder, platform, shell, OS version, a note about '
        "untrusted downloads, the model name, today's date)",
        r"#\s*Environment|following environment",
    ),
    "email_reminder": (
        "A reminder attached to the user message holding the account's email address",
        r"<account email>|userEmail|email address",
    ),
}

# The known leftover text, word for word as measured on Claude Code 2.1.325 (2026-11-15).
# Each entry is a regex; "{}" in the source text stands for a value that differs between
# machines and sessions (an address, a folder, a date). Matches are cut out of the quote and
# whatever remains is examined line by line.
_VALUE = r"[^\n]{1,80}?"  # a value on one line, as short as possible
_DOT_AFTER_VALUE = r"\.(?=[\s\"'’”]|$)"  # "Opus 5.5." ends at the second dot, not the first


def _words(chunk: str) -> str:
    return r"\s+".join(re.escape(w).replace("`", "`?").replace("'", "['’]") for w in chunk.split())


def _lit(text: str) -> str:
    """``text`` word for word, any whitespace between words, "{}" for a value."""
    pattern = _VALUE.join(_words(c) for c in text.split("{}"))
    return pattern.replace(_VALUE + r"\.", _VALUE + _DOT_AFTER_VALUE)


def _line(text: str, value: str = r"\S+") -> str:
    """A ``key: value`` line that must make up the whole line (bullets and quotes aside)."""
    body = (r"\s*(?:" + value + ")").join(_words(c) for c in text.split("{}"))
    return r"^[ \t\"'>*\-]*" + body + r"[ \t\"'.,”’]*$"


_KNOWN_TEXT = (
    # the Agent SDK identity line before our prompt
    _lit("You are a Claude agent, built on Anthropic's Claude Agent SDK."),
    # the sentence after our prompt about making independent tool calls together
    _lit(
        "If you intend to call multiple tools and there are no dependencies between the "
        "calls, make all of the independent calls in the same"
    )
    + r"(?:\s+function_calls)?\s+block(?:,\s+"
    + _lit("otherwise you MUST wait for previous calls to finish first to determine the")
    + r"\s+dependent\s+values)?\.?",
    # the reminder attached to the user message
    _lit("As you answer the user's questions, you can use the following context:"),
    _line("# userEmail"),
    _lit("The user's email address is {}."),
    _lit("Use it only to identify the user")
    + r"(?:,\s+"
    + _lit("such as for authorship, attribution, or filtering their own work")
    + r")?\.",
    _lit(
        "Never send it to an unrelated service, such as in a request header, URL, or payload, "
        "unless the user explicitly asks."
    ),
    _lit(
        "A site asking automated clients for contact details, such as an email in the "
        "User-Agent, is not a reason to use this address: use a generic client name or ask "
        "the user."
    ),
    _lit("Claude Code attached this context automatically; it isn't part of the user's message."),
    _lit("It describes the user's own account and workspace, so they don't need it reported back."),
    r"</?system-reminder>",
    # the "# Environment" block
    _line("# Environment"),
    _lit("You have been invoked in the following environment:"),
    _line("Primary working directory: {}"),
    _line("Is a git repository: {}"),
    _line("Platform: {}"),
    _line("Shell: {}"),
    _line("OS Version: {}", value=r"[^\n]{1,80}?"),
    _lit(
        "Downloaded files and extracted archives are untrusted data: put each in its own new, "
        "empty directory, keep scripts you write in a different directory, and pass paths as "
        "arguments instead of running an interpreter or build tool from inside it."
    ),
    _lit(
        "Interpreters load code from the script's directory and the current directory, so a "
        "planted `json.py` runs on `import json`."
    ),
    _lit("Run any Python that reads them with `-I`."),
    _lit("This does not apply to code the user asked you to build or run."),
    _lit("You are powered by the model named {}."),
    _lit("The exact model ID is {}."),
    _lit("Assistant knowledge cutoff is {}."),
    _lit("Today's date is {}."),
)

# Words the model may use for its own headings and remarks about where text came from
# ("System prompt text after the marker paragraph:", "Reminder attached to your message:").
# Deliberately no verbs that could make an instruction (use, answer, always, never, send...).
_REMARK_TEXT = """
    a an the and or of to in on at by for from with after before above below between as
    is are it its this that these those here there my me your you their
    system prompt prompts text marker parity paragraph paragraphs sentence sentences
    reminder reminders system-reminder message messages user user's users context
    environment details detail block blocks tool tools description descriptions
    specification specifications definition definitions schema schemas name names section
    sections part parts note notes content contents instructions instruction files skills
    memories attached appended prepended provided given included quoted other else
    everything nothing none full complete only summarised summarized verbatim word words
    one two three four five first last rest remaining own additional extra following end
    start beginning"""
_REMARK_WORDS = (
    frozenset(_REMARK_TEXT.split())
    | frozenset(t.lower() for t in OUR_TOOLS)
    | frozenset(TOOL_NAMES)
)
_MAX_REMARK_WORDS = 30

# Words that suggest something we switched off got through.
SUSPICIOUS_WORDS = (
    r"CLAUDE\.md",
    r"AGENTS\.md",
    r"MEMORY\.md",
    r"\bskills?\b",
    r"\bmemor(y|ies)\b",
    r"\bhooks?\b",
    r"\bplugins?\b",
    r"slash command",
    r"gitStatus",
    r"git status",
    r"Recent commits",
    r"\bsubagents?\b",
    r"output style",
)

BUILTIN_TOOLS = frozenset(
    {
        "Bash",
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "WebFetch",
        "WebSearch",
        "Task",
        "TodoWrite",
        "NotebookEdit",
        "Agent",
        "Skill",
    }
)

SECTION_LABELS = ("TOOLS", "MARKER", "FIRST SENTENCE", "OTHER CONTEXT")

PROBE_INSTRUCTION = "\n".join(
    [
        "This is a configuration check, not a design task. Do not call any tool.",
        "",
        "Answer in exactly four sections, each starting with its label on a line of its own:",
        "",
        "TOOLS:",
        "Every tool you can call, one per line, with its exact name as given to you. Write "
        '"none" if you have no tools.',
        "",
        "MARKER:",
        'The sentence in your instructions that starts with "Parity marker", quoted exactly, '
        'including its code. Write "none" if there is no such sentence.',
        "",
        "FIRST SENTENCE:",
        "The very first sentence of your system prompt, quoted exactly, whatever it is.",
        "",
        "OTHER CONTEXT:",
        'Quote, word for word and complete, everything in your context other than the "Parity '
        'marker" paragraph and this message. That includes any text before or after that '
        "paragraph in your system prompt, any notes, reminders, environment details, dates, "
        "names or addresses attached to this message, and any files, instructions, skills or "
        "memories you were given. Do not summarise and do not leave anything out. Do not repeat "
        'the tool descriptions. If there is nothing else, write "nothing".',
    ]
)


@dataclass
class ParityReport:
    ok: bool
    tools: list[str] = field(default_factory=list)
    extra_tools: list[str] = field(default_factory=list)
    marker_quoted: bool = False
    leftovers: str = ""
    inventory: dict[str, object] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    text: str = ""
    leftovers_seen: dict[str, bool] = field(default_factory=dict)


# ---- pieces that do not need a model --------------------------------------------------------


def make_marker() -> str:
    return f"Parity marker {secrets.token_hex(6).upper()}: this sentence is the BrickSnap prompt."


def probe_prompt(marker: str) -> str:
    return (
        f"{marker} You are being checked to make sure you receive only this prompt and the "
        "tools the program gives you. Answer the user's questions about your own context "
        "truthfully, completely and word for word. Do not call any tool."
    )


def split_sections(reply: str) -> dict[str, str]:
    """The labelled sections of the reply (missing ones are '').

    Each label is taken once, in order, in capitals at the start of a line. Everything after
    "OTHER CONTEXT:" belongs to that section, so a label-like line inside the model's quote
    does not end it.
    """
    sections = dict.fromkeys(SECTION_LABELS, "")
    found = {}
    for label in SECTION_LABELS:
        m = re.search(r"^[ \t#*_]*" + re.escape(label) + r"[ \t*_]*:[ \t*_]*", reply, re.MULTILINE)
        if m:
            found[label] = m
    other = found.get("OTHER CONTEXT")
    limit = other.start() if other else len(reply) + 1
    accepted: list[tuple[str, re.Match[str]]] = []
    last = -1
    for label in SECTION_LABELS:
        m = found.get(label)
        if m is None or m.start() <= last:
            continue
        if label != "OTHER CONTEXT" and m.start() >= limit:
            continue
        accepted.append((label, m))
        last = m.start()
    for i, (label, m) in enumerate(accepted):
        end = accepted[i + 1][1].start() if i + 1 < len(accepted) else len(reply)
        sections[label] = reply[m.end() : end].strip()
    return sections


def _strip_fences(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.strip().startswith("```"))


def _is_nothing(text: str) -> bool:
    return text.strip().strip("\"'.*").lower() in ("", "nothing", "none")


def _is_remark(line: str) -> bool:
    """True for a line that is only the model's own heading or remark, or punctuation."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_'’-]*", line.lower().replace("’", "'"))
    return len(words) <= _MAX_REMARK_WORDS and all(w in _REMARK_WORDS for w in words)


def classify_leftovers(quoted: str) -> tuple[list[str], list[str]]:
    """(unexpected lines, suspicious words) in the model's quote of its other context."""
    text = _strip_fences(quoted).strip()
    if _is_nothing(text):
        return [], []
    rest = text
    for pattern in _KNOWN_TEXT:
        rest = re.sub(pattern, "\n", rest, flags=re.IGNORECASE | re.MULTILINE)
    unexpected: list[str] = []
    for line in rest.splitlines():
        s = line.strip().strip("\"'“”‘’").strip()
        if s and not _is_remark(s):
            unexpected.append(s)
    words = sorted(
        {m.group(0) for pat in SUSPICIOUS_WORDS for m in re.finditer(pat, text, re.IGNORECASE)},
        key=str.lower,
    )
    return unexpected, words


def leftovers_seen(quoted: str) -> dict[str, bool]:
    return {
        name: bool(re.search(pattern, quoted, re.IGNORECASE))
        for name, (_, pattern) in KNOWN_LEFTOVERS.items()
    }


def _check_init(init: dict[str, Any], report: ParityReport) -> None:
    notes = report.notes
    raw_tools = init.get("tools")
    tools = [str(t) for t in raw_tools] if isinstance(raw_tools, list) else []
    report.tools = tools
    report.extra_tools = [t for t in tools if t not in OUR_TOOLS]
    missing = [t for t in OUR_TOOLS if t not in tools]
    if missing:
        notes.append("Our tools missing from the session: " + ", ".join(missing) + ".")
    undocumented = [t for t in report.extra_tools if t not in DOCUMENTED_EXTRA_TOOLS]
    if undocumented:
        notes.append(
            "Tools besides ours that are not documented leftovers: " + ", ".join(undocumented) + "."
        )
    for key in INVENTORY_FIELDS:
        if key in init:
            report.inventory[key] = json.loads(redact(json.dumps(init[key])))
    for key in MUST_BE_EMPTY:
        if init.get(key):
            notes.append(
                f"The session still had {key.replace('_', ' ')}: {redact(str(init[key]))}."
            )
    raw_plugins = init.get("plugins") or []
    plugins = raw_plugins if isinstance(raw_plugins, list) else [raw_plugins]
    odd_plugins = [
        str(p.get("name")) if isinstance(p, dict) else str(p)
        for p in plugins
        if not isinstance(p, dict)
        or p.get("name") not in DOCUMENTED_BUILTIN_PLUGINS
        or p.get("path") != "builtin"
    ]
    if odd_plugins:
        notes.append(
            "Plugins besides the documented built-in ones were loaded: "
            + redact(", ".join(odd_plugins))
            + "."
        )
    source = init.get("apiKeySource")
    if source is not None and source != "none":
        notes.append(
            f"Claude Code reports the API key source as {source!r}: an API key may have been "
            "used instead of the subscription."
        )
    if init.get("memory_paths"):
        notes.append(
            "Claude Code reports memory folders it would read: "
            + redact(json.dumps(init["memory_paths"]))
            + "."
        )
    if "output_style" in init and init["output_style"] != "default":
        notes.append(
            f"The output style is {redact(repr(init['output_style']))}, not the default one, "
            "so Claude Code may add its own instructions to the prompt."
        )
    if "permissionMode" in init and init["permissionMode"] != "dontAsk":
        notes.append(
            f"The permission mode is {redact(repr(init['permissionMode']))}, not 'dontAsk' as "
            "the runner asks for."
        )
    raw_servers = init.get("mcp_servers")
    servers = (
        [s for s in raw_servers if isinstance(s, dict)] if isinstance(raw_servers, list) else []
    )
    status = next((s.get("status") for s in servers if s.get("name") == "bricksnap"), None)
    if status != "connected":
        notes.append(f"The bricksnap tool server was not connected (status: {status}).")
    others = [str(s.get("name")) for s in servers if s.get("name") != "bricksnap"]
    if others:
        notes.append("Other tool servers were present: " + ", ".join(others) + ".")


def evaluate(
    init: dict[str, Any] | None,
    reply: str,
    marker: str,
    *,
    run_error: str = "",
    stream: StreamParser | None = None,
) -> ParityReport:
    """Turn the init event and the model's reply into a report (no model needed).

    ``stream`` is the parser that read the whole session; with it, a model switch or a
    message Claude Code added of its own makes the result NOT CLEAN.
    """
    report = ParityReport(ok=False)
    reply = redact(reply)
    notes = report.notes
    switched = stream.model_switch_note() if stream is not None else ""
    if run_error and not (switched and switched in run_error):
        notes.append(f"The session did not finish cleanly: {redact(run_error)}")
    if init is None:
        notes.append(
            "Claude Code never announced its setup (no init event), so nothing could be checked."
        )
    else:
        _check_init(init, report)
    if stream is not None:
        report.inventory["models_that_answered"] = list(stream.models_used)
    if switched:
        notes.append(switched)

    sections = split_sections(reply)
    report.marker_quoted = marker in reply
    if not report.marker_quoted:
        notes.append(
            "The model did not quote the marker sentence, so our prompt may not be its system "
            "prompt."
        )
    first = sections["FIRST SENTENCE"]
    other = sections["OTHER CONTEXT"]
    if not any(sections.values()):
        other = reply  # the model ignored the format; check everything it said
    elif not other:
        notes.append(
            "The reply has no OTHER CONTEXT section, so the rest of the model's context could "
            "not be checked."
        )
    parts = []
    if first and marker not in first:
        parts.append(first)
    if not _is_nothing(other):
        parts.append(other)
    report.leftovers = "\n\n".join(parts)
    report.leftovers_seen = leftovers_seen(report.leftovers)
    unexpected, words = classify_leftovers(report.leftovers)
    if unexpected:
        notes.append(
            "The model quoted context that is not a known leftover: "
            + " | ".join(u[:200] for u in unexpected)
        )
    if words:
        notes.append(
            "The quoted context mentions things we switched off: " + ", ".join(words) + "."
        )
    if sections["TOOLS"]:
        named = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sections["TOOLS"]))
        stray = sorted(named & BUILTIN_TOOLS)
        if stray:
            notes.append("The model says it can call built-in tools: " + ", ".join(stray) + ".")

    report.ok = init is not None and not notes
    report.text = format_report(report, reply)
    return report


def format_report(report: ParityReport, reply: str, *, remarks: list[str] | None = None) -> str:
    lines = ["# Clean-room parity check", ""]
    lines.append(
        "Result: CLEAN. The model received our prompt and our tools, plus only the known "
        "leftovers listed below."
        if report.ok
        else "Result: NOT CLEAN. See the problems below."
    )
    lines.append("")
    lines.append("## Tools the session announced")
    for t in report.tools or ["(none)"]:
        tag = ""
        if t in OUR_TOOLS:
            tag = " (ours)"
        elif t in DOCUMENTED_EXTRA_TOOLS:
            tag = " (documented leftover: Claude Code may keep it when MCP tools are present)"
        elif t != "(none)":
            tag = " (NOT EXPECTED)"
        lines.append(f"- {t}{tag}")
    lines.append("")
    lines.append("## Our prompt")
    lines.append(
        "The model quoted the marker sentence (with its random code), so our prompt reached it."
        if report.marker_quoted
        else "The model did NOT quote the marker sentence."
    )
    lines.append("")
    lines.append("## Problems")
    lines.extend(f"- {n}" for n in report.notes) if report.notes else lines.append("- none")
    if remarks:
        lines.append("")
        lines.append("## Remarks")
        lines.extend(f"- {r}" for r in remarks)
    lines.append("")
    lines.append("## Known leftovers (no documented flag removes these)")
    for name, (what, _) in KNOWN_LEFTOVERS.items():
        seen = report.leftovers_seen.get(name)
        state = "seen" if seen else "NOT seen (it may have changed, or the model left it out)"
        lines.append(f"- {what}: {state}.")
    plugins = report.inventory.get("plugins")
    if isinstance(plugins, list) and plugins:
        names = ", ".join(str(p.get("name")) for p in plugins if isinstance(p, dict))
        lines.append(
            f"- Built-in plugins listed by Claude Code: {names}. They add no tools, skills or "
            "agents here, and nothing from them appears in the model's quote."
        )
    lines.append("")
    lines.append("## Setup reported by Claude Code (init event)")
    for key, value in report.inventory.items():
        lines.append(f"- {key}: {json.dumps(value)}")
    if not report.inventory:
        lines.append("- (not available)")
    lines.append("")
    lines.append("## What else the model says is in its context (its own quote, redacted)")
    lines.append("")
    lines.append("```text")
    lines.append(report.leftovers.replace("```", "'''") or "(nothing quoted)")
    lines.append("```")
    lines.append("")
    lines.append("## The model's full reply (redacted)")
    lines.append("")
    lines.append("```text")
    lines.append(reply.replace("```", "'''") or "(no reply)")
    lines.append("```")
    return redact("\n".join(lines)) + "\n"


# ---- the real check -------------------------------------------------------------------------


def _box_model(folder: Path) -> Path:
    import trimesh

    path = folder / "box.stl"
    trimesh.creation.box(extents=(32.0, 16.0, 19.2)).export(path)
    return path


def check_parity(*, model: str = DEFAULT_MODEL, keep_in: Path | None = None) -> ParityReport:
    from bricksnap.designer.runner import run_designer
    from bricksnap.pipeline import create_project

    marker = make_marker()
    code = marker.split()[2].rstrip(":").lower()
    with tempfile.TemporaryDirectory(prefix="bricksnap-parity-") as tmp:
        work = Path(tmp)
        prompt_file = work / "probe-prompt.md"
        prompt_file.write_text(probe_prompt(marker) + "\n", encoding="utf-8")
        project = create_project(
            _box_model(work),
            studs=4,
            name=f"parity-{code}",
            directory=keep_in if keep_in is not None else work / "projects",
        )
        run = run_designer(
            project,
            instruction=PROBE_INSTRUCTION,
            model=model,
            effort="low",
            max_turns=3,
            timeout_s=600,
            prompt_file=prompt_file,
        )
        parser = StreamParser()
        if run.transcript is not None and run.transcript.exists():
            for line in run.transcript.read_text(encoding="utf-8").splitlines():
                parser.feed(line)
    reply = parser.final_text
    report = evaluate(parser.init, reply, marker, run_error=run.error, stream=parser)
    if run.tools_called:
        remarks = [
            "The model called tools although it was asked not to: "
            + ", ".join(run.tools_called)
            + ". That says nothing about what it was given."
        ]
        report.text = format_report(report, redact(reply), remarks=remarks)
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m bricksnap.designer.parity",
        description=(
            "Check that the AI designer receives only BrickSnap's prompt and tools. Uses a "
            "small amount of your Claude subscription; never an API key."
        ),
    )
    ap.add_argument("--out", type=Path, default=None, help="also write the report to this file")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--keep-in",
        type=Path,
        default=None,
        help="create the throwaway project inside this folder and keep it (with its transcript)",
    )
    args = ap.parse_args(argv)
    print("Running a short check with Claude Code (about a minute)...", flush=True)
    report = check_parity(model=args.model, keep_in=args.keep_in)
    print(report.text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report.text, encoding="utf-8")
        print(f"Report written to {redact(str(args.out))}")
    sys.exit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
