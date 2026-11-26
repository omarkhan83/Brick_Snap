"""Start the AI designer so that it sees only our prompt and our tools (the clean-room runner).

For now the model runs through headless Claude Code on the user's subscription. The
requirement (docs/decisions/2026-11-15-ai-designer-runs-clean-and-is-the-only-thing-that-
sends-data.md) is that it behaves as it would through a bare API call.

CONTRACT (tests go in tests/test_designer_runner.py)

``build_command(prompt_file, mcp_config_file, model, effort, max_turns) -> list[str]``
returns exactly:

    claude -p
      --system-prompt-file <prompt_file>        replaces Claude Code's whole default prompt
      --tools ""                                no built-in tools
      --mcp-config <mcp_config_file> --strict-mcp-config
      --setting-sources ""                      no user, project or local settings
      --disable-slash-commands
      --no-session-persistence
      --allowedTools mcp__bricksnap
      --permission-mode dontAsk
      --model <model> --effort <effort> --max-turns <max_turns>
      --output-format stream-json --verbose

(``--bare`` must NOT be used: it disables subscription login. ``--verbose`` is required by
Claude Code for stream-json output in print mode.) The user message is written to the
process's standard input, not put on the command line.

``run_designer(project, instruction=None, model="claude-fable-5-2", effort="high",
max_turns=40, timeout_s=1800) -> DesignerRun``
- Runs from a new, empty temporary directory, so no CLAUDE.md or project file can be picked
  up. Writes the MCP config there: one server, "bricksnap", command ``sys.executable`` with
  args ``-m bricksnap.designer.mcp_server <absolute project path>``.
- Environment: a copy of the current one, changed as follows.
  Removed: ANTHROPIC_API_KEY and ANTHROPIC_AUTH_TOKEN (the API key must not be spent; the
  subscription login is used), and every variable whose name starts with CLAUDE (CLAUDECODE,
  CLAUDE_CODE_*, CLAUDE_EFFORT, CLAUDE_PID and so on) except CLAUDE_CODE_OAUTH_TOKEN and
  CLAUDE_CONFIG_DIR, so a run started from inside another Claude Code session does not
  inherit that session's settings.
  Set (each confirmed to work on Claude Code 2.1.325): CLAUDE_CODE_DISABLE_AUTO_MEMORY=1,
  CLAUDE_CODE_DISABLE_CLAUDE_MDS=1, CLAUDE_CODE_ATTRIBUTION_HEADER=0,
  CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS=1, CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS=1,
  CLAUDE_CODE_DISABLE_BUNDLED_SKILLS=1, CLAUDE_CODE_DISABLE_ATTACHMENTS=1,
  CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1, and MAX_MCP_OUTPUT_TOKENS=200000 (pictures
  returned by our tools count against this limit; the default of 25000 is too small).
- Known leftovers that no documented flag removes (measured 2026-11-15): Claude Code puts the
  line "You are a Claude agent, built on Anthropic's Claude Agent SDK." before our system
  prompt, appends an "# Environment" block (working directory, platform, shell, OS version,
  a note about untrusted downloads, the model name and today's date), and attaches a
  reminder holding the account's email address to the user message. None of it concerns
  the design task and the model has no tool that could act on it. ``parity.py`` reports
  these so we notice if they change.
- The user message is ``instruction`` if given, otherwise a fixed default asking the designer
  to improve the model following its process.
- Standard output is stream-json, one JSON object per line. Every line is appended to
  ``<project>/designer/<UTC timestamp>.jsonl`` as it arrives. From it, collect: the tool
  list announced in the ``system``/``init`` event, the names of the tools called, the final
  result text, the number of turns, and any error.
- Returns a ``DesignerRun``. A missing ``claude`` executable, a timeout, a non-zero exit or
  an error result gives ``ok=False`` with a plain-language ``error``; it does not raise.
- Tests must not start a real model: test ``build_command``, the environment scrubbing and
  the stream parsing (feed it recorded lines). One test marked ``@pytest.mark.designer``
  runs a real session; it is excluded by default.

STAGE 3 ADDITION TO THE CONTRACT: a typed edit
``run_designer(project, instruction=...)`` has two kinds of run.
- A *first pass*: the project has no brief yet. The message is the default instruction;
  if the person gave an instruction it is added as their wish for the design.
- An *edit*: the project already has a brief and the person gave an instruction ("add a
  red collar"). The message says that this model has already been designed, quotes the
  person's request exactly, and asks for that change and nothing else: keep the rest of the
  model, keep the brief unless the request contradicts it (then update the brief), rebuild,
  check the result against the request, and say in a sentence or two what was changed.
  ``DesignerRun`` gains ``kind`` ("first pass" or "edit").
- prompt.md gains a short section, "When the person asks for a change", saying the same from
  the designer's side. Nothing else in the prompt changes.
- The request is the person's own text: it is passed to the model as their message, never
  placed in the system prompt, and never used to build a command line or a file name.

Implementation notes
--------------------
- ``designer_env(base)`` does the environment scrubbing; ``StreamParser`` reads the
  stream-json lines (unknown event types and lines that are not JSON are kept in the
  transcript and otherwise ignored); ``redact(text)`` replaces e-mail addresses with
  "<account email>" and the home directory with "~". Everything the runner hands back for
  display (``final_text``, ``error``, ``tool_errors``) has been redacted. The raw transcript
  is not redacted; it stays inside the project folder, which git ignores.
- ``redact`` also hides the home directory as Python's error messages print a file name
  (``repr``, which doubles every backslash in a Windows path and escapes control
  characters). Its e-mail pattern only starts a match where a run of address characters
  starts, so a long text without an "@" takes linear time instead of seconds.
- The MCP config also sets ``PYTHONPATH`` for the server to the folder that holds the
  ``bricksnap`` package, so the server starts from the empty temporary folder even when
  BrickSnap is not installed into the interpreter.
- If the ``init`` event reports that the "bricksnap" server did not connect, the run is
  stopped at once with a plain error instead of letting the model work without tools.
- If the ``init`` event gives an ``apiKeySource`` other than "none", Claude Code holds an API
  key of its own (a Console login, say) and would spend it; the run is stopped at once.
- Claude Code can switch models in mid-session: when a safety check stops a reply it adds a
  message of its own to the conversation (a ``user`` event with ``isSynthetic``) and carries
  on with another model (an assistant ``fallback`` block and a ``system`` /
  ``model_refusal_fallback`` event), then reports success. That is context we did not supply,
  so the parser records it, with the model named in each assistant message and in the
  result's ``modelUsage``, and ``run_designer`` returns ``ok=False`` with a plain explanation
  (the edits and the reply are still kept). ``DesignerRun.models_used`` lists the models that
  answered. The expected model is the one the ``init`` event names (Claude Code resolves
  aliases such as "opus" there); a dated name of the same model counts as the same.
- A usage limit: when the subscription's usage limit for the model is reached, Claude Code
  answers with a message of its own instead of the model (an assistant event marked
  ``"error": "rate_limit"``, model ``<synthetic>``, text "You've hit your Fable limit ·
  resets 2am (Europe/London)"), often after a ``rate_limit_event`` whose ``rate_limit_info``
  has ``"status": "rejected"`` and ``resetsAt`` (seconds since 1970), and then a result
  with ``is_error`` and the same text. The parser keeps that line (``usage_limit``) and
  when the limit resets (``limit_resets``: the words after "resets", else the ``resetsAt``
  time on this computer's clock, "on 1 December at 02:00", else ""); a result whose text is
  such a line counts too. ``run_session`` then gives ``ok=False``, an ``error`` that says
  the limit was reached and when it resets, and ``DesignerRun.usage_limit``,
  ``limit_resets`` (redacted) and ``limit_resets_at`` (the ``resetsAt``, or None), so
  callers can say what to do. It never retries, and never
  on another model.
- The stdout reader never dies silently: if reading an event or writing the transcript
  fails, the failure becomes the run's error, the process is stopped, and the rest of the
  output is still drained so the child cannot block on a full pipe.
- Text is redacted before it is shortened, so an address cut in half cannot slip through.
- ``DesignerRun`` also carries the names of tools whose calls came back as errors
  (``tool_errors``, with the error text), the wall-clock ``duration_s`` and, when Claude
  Code reports it, ``cost_usd`` (the notional API price; a subscription run is not billed
  per call).
- ``python -m bricksnap.designer.runner <project> [--instruction TEXT]`` runs the designer
  and prints each tool call as it happens, then the redacted summary.
- Typed edit: ``has_brief(project)`` uses the rule the tools use (a non-empty text or a
  non-empty dict in ``project.meta["brief"]``). ``run_kind(project, instruction)`` gives
  ``EDIT`` when there is a brief and a request that is not blank, otherwise ``FIRST_PASS``;
  a project with a brief and no request gets another first pass with the default message.
  ``designer_message(project, instruction)`` builds the message from ``WISH_MESSAGE`` or
  ``EDIT_MESSAGE``. The request is stripped of surrounding blanks and put in by plain
  replacement of "{request}" (not ``str.format``, so the messages may hold other braces
  without escaping them). Braces or quotes in the request are sent exactly as typed,
  between quotation marks on a line of their own.
- When ``prompt_file`` replaces the prompt (the parity probe), the instruction is sent as it
  is: the two kinds of run belong to prompt.md, and the probe's message must reach the model
  unchanged. ``kind`` is still reported.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bricksnap.project import Project

DEFAULT_MODEL = "claude-fable-5-2"
PROMPT_FILE = Path(__file__).parent / "prompt.md"
DEFAULT_INSTRUCTION = (
    "Improve this model so that it looks designed rather than merely converted, "
    "following your process."
)

FIRST_PASS = "first pass"
EDIT = "edit"

# A first pass with a wish: the default instruction, then the person's words, quoted exactly.
WISH_MESSAGE = (
    DEFAULT_INSTRUCTION + "\n\n"
    "The person who made this model also has a wish for the design, in their own words:\n\n"
    '"{request}"\n\n'
    "Make the wish part of your brief and of your design, and say in your summary how you "
    "included it."
)

# An edit: the model is designed and accepted; the person wants this one change.
EDIT_MESSAGE = (
    "This model has already been designed. It has a brief, and the person has looked at the "
    "result and accepted it. Now they want one change, in their own words:\n\n"
    '"{request}"\n\n'
    "Make that change and nothing else. Keep the rest of the model exactly as it is: every "
    "cell outside the part the request is about should stay as it is now. Keep the brief as "
    "it is, unless the request contradicts it: it does when the change brings in a colour "
    "that is not in the brief's colours, or alters something the brief describes. Then call "
    "brief first and update only those parts of it, keeping the rest as written.\n\n"
    "Look before you edit (describe and render), so you know exactly where the change goes. "
    "Make it with as few edits as do it well, rebuild, and look at the result: check that "
    "it does what the person asked and that nothing else changed. Then say in a sentence or "
    "two what you changed."
)

SERVER_NAME = "bricksnap"
TOOL_PREFIX = f"mcp__{SERVER_NAME}__"

REMOVED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
KEPT_CLAUDE_ENV = ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR")
SET_ENV = {
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
    "CLAUDE_CODE_ATTRIBUTION_HEADER": "0",
    "CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS": "1",
    "CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS": "1",
    "CLAUDE_CODE_DISABLE_BUNDLED_SKILLS": "1",
    "CLAUDE_CODE_DISABLE_ATTACHMENTS": "1",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    "MAX_MCP_OUTPUT_TOKENS": "200000",
}

# The look-behind makes a match start only where a run of address characters starts. Without
# it a long run with no "@" is scanned again from every one of its characters, which takes
# seconds on a 200,000-character text; it finds exactly the same addresses.
_EMAIL = re.compile(
    r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}"
)
# Claude Code's own line when the subscription's usage limit is reached: "You've hit your
# Fable limit · resets 2am (Europe/London)" (also "your limit", "your weekly limit").
_USAGE_LIMIT = re.compile(
    r"You(?:'|’)ve hit your (?:(?P<what>[^\n·]*?) )?limit\b(?:\s*·\s*resets\s+(?P<when>[^\n]+))?",
    re.IGNORECASE,
)


@dataclass
class DesignerRun:
    ok: bool
    transcript: Path | None = None
    tools_announced: list[str] = field(default_factory=list)
    tools_called: list[str] = field(default_factory=list)
    turns: int = 0
    final_text: str = ""
    error: str = ""
    tool_errors: list[str] = field(default_factory=list)
    duration_s: float = 0.0
    cost_usd: float | None = None
    models_used: list[str] = field(default_factory=list)
    kind: str = FIRST_PASS  # FIRST_PASS or EDIT
    usage_limit: str = ""  # Claude Code's line when the usage limit stopped the session
    limit_resets: str = ""  # when that limit resets, in words ("" when not known)
    limit_resets_at: float | None = None  # and as seconds since 1970, when Claude Code said


# ---- the message ----------------------------------------------------------------------------


def has_brief(project: Project) -> bool:
    """True when the project has a brief from an earlier run (the rule the tools use: a
    non-empty text, or a non-empty dict, in ``project.meta["brief"]``)."""
    brief = project.meta.get("brief") if isinstance(project.meta, dict) else None
    if isinstance(brief, str):
        return bool(brief.strip())
    return isinstance(brief, dict) and bool(brief)


def _request(instruction: str | None) -> str:
    return instruction.strip() if instruction and instruction.strip() else ""


def run_kind(project: Project, instruction: str | None) -> str:
    """EDIT when the project has a brief and the person typed a request, else FIRST_PASS."""
    return EDIT if _request(instruction) and has_brief(project) else FIRST_PASS


def designer_message(project: Project, instruction: str | None) -> str:
    """The user message for this run (see the contract): the default instruction, the
    default with the person's wish, or a request for one change."""
    request = _request(instruction)
    if not request:
        return DEFAULT_INSTRUCTION
    template = EDIT_MESSAGE if has_brief(project) else WISH_MESSAGE
    return template.replace("{request}", request)


# ---- redaction ------------------------------------------------------------------------------


def redact(text: str, home: str | None = None) -> str:
    """Replace e-mail addresses with "<account email>" and the home directory with "~".

    The home directory is also found as Python's error messages show a file name (repr()
    doubles each backslash, so every Windows path, and escapes control characters).
    """
    text = _EMAIL.sub("<account email>", text)
    home = str(Path.home()) if home is None else home
    home = home.rstrip("/\\")
    if len(home) > 1:
        for form in dict.fromkeys((repr(home)[1:-1], home)):
            text = text.replace(form, "~")
    return text


# ---- command and environment ----------------------------------------------------------------


def build_command(
    prompt_file: Path, mcp_config_file: Path, *, model: str, effort: str, max_turns: int
) -> list[str]:
    return [
        "claude",
        "-p",
        "--system-prompt-file",
        str(prompt_file),
        "--tools",
        "",
        "--mcp-config",
        str(mcp_config_file),
        "--strict-mcp-config",
        "--setting-sources",
        "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--allowedTools",
        "mcp__bricksnap",
        "--permission-mode",
        "dontAsk",
        "--model",
        model,
        "--effort",
        effort,
        "--max-turns",
        str(max_turns),
        "--output-format",
        "stream-json",
        "--verbose",
    ]


def designer_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """The environment for the Claude Code child process (see the contract above)."""
    base = os.environ if base is None else base
    env: dict[str, str] = {}
    for key, value in base.items():
        if key in REMOVED_ENV:
            continue
        if key.startswith("CLAUDE") and key not in KEPT_CLAUDE_ENV:
            continue
        env[key] = value
    env.update(SET_ENV)
    return env


def mcp_config(project_path: Path, module: str = "bricksnap.designer.mcp_server") -> dict[str, Any]:
    """The MCP config: one stdio server, "bricksnap", serving the tools of ``module`` (the
    designer's by default) for one folder."""
    package_root = Path(__file__).resolve().parent.parent.parent
    return {
        "mcpServers": {
            SERVER_NAME: {
                "type": "stdio",
                "command": sys.executable,
                "args": ["-m", module, str(project_path.resolve())],
                "env": {"PYTHONPATH": str(package_root)},
            }
        }
    }


# ---- reading the stream ---------------------------------------------------------------------


def _short(text: str, limit: int = 300) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _tool_result_text(item: dict[str, Any]) -> str:
    content = item.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(c.get("text", ""))
            for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


class StreamParser:
    """Collects what matters from Claude Code's stream-json output, one line at a time."""

    def __init__(self) -> None:
        self.init: dict[str, Any] | None = None
        self.tools_announced: list[str] = []
        self.tools_called: list[str] = []
        self.tool_errors: list[str] = []
        self.texts: list[str] = []
        self.result: dict[str, Any] | None = None
        self.not_json = 0
        self.models_used: list[str] = []  # every model that answered, in order of appearance
        self.switches: list[str] = []  # plain-language notes of Claude Code changing course
        self.usage_limit = ""  # Claude Code's line when the subscription's usage limit was hit
        self.resets_at: float | None = None  # a rejected rate_limit_event's resetsAt
        self._pending: dict[str, str] = {}  # tool_use id -> tool name

    def _model_seen(self, model: object) -> None:
        if isinstance(model, str) and model and model not in self.models_used:
            self.models_used.append(model)

    def _switch(self, note: str) -> None:
        note = _short(redact(note), 400)
        if note not in self.switches:
            self.switches.append(note)

    def feed(self, line: str) -> dict[str, Any] | None:
        """Read one line; return the event if it was a JSON object, otherwise None."""
        line = line.strip()
        if not line:
            return None
        try:
            event = json.loads(line)
        except ValueError:
            self.not_json += 1
            return None
        if not isinstance(event, dict):
            self.not_json += 1
            return None
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            self.init = event
            tools = event.get("tools")
            if isinstance(tools, list):
                self.tools_announced = [str(t) for t in tools]
        elif kind == "system" and event.get("subtype") == "model_refusal_fallback":
            self._switch(
                f"Claude Code switched from {event.get('original_model', 'the requested model')} "
                f"to {event.get('fallback_model', 'another model')} after a safety check stopped "
                f"a reply (scope: {event.get('scope', 'unknown')})."
            )
        elif kind == "rate_limit_event":
            info = event.get("rate_limit_info")
            if isinstance(info, dict) and info.get("status") == "rejected":
                resets = info.get("resetsAt")
                if isinstance(resets, int | float) and not isinstance(resets, bool):
                    self.resets_at = float(resets)
        elif kind == "assistant":
            message = event.get("message")
            if isinstance(message, dict):
                self._model_seen(message.get("model"))
            synthetic = event.get("error") == "rate_limit" or (
                isinstance(message, dict) and message.get("model") == "<synthetic>"
            )
            for item in self._content(event):
                if item.get("type") == "tool_use":
                    name = str(item.get("name", ""))
                    self.tools_called.append(name)
                    if "id" in item:
                        self._pending[str(item["id"])] = name
                elif item.get("type") == "text" and item.get("text"):
                    self.texts.append(str(item["text"]))
                    if synthetic:  # Claude Code speaking for the model: a usage limit?
                        self._limit_seen(item["text"])
                elif item.get("type") == "fallback":
                    self._switch(
                        f"Claude Code fell back from {self._model_name(item.get('from'))} to "
                        f"{self._model_name(item.get('to'))}."
                    )
        elif kind == "user":
            if event.get("isSynthetic"):
                said = " ".join(
                    str(c.get("text", "")) for c in self._content(event) if c.get("type") == "text"
                )
                self._switch(
                    "Claude Code added a message of its own to the conversation (a safety check "
                    f'had stopped a reply): "{_short(said, 160)}"'
                )
            for item in self._content(event):
                if item.get("type") == "tool_result" and item.get("is_error"):
                    name = self._pending.get(str(item.get("tool_use_id", "")), "a tool")
                    self.tool_errors.append(f"{name}: {_short(redact(_tool_result_text(item)))}")
        elif kind == "result":
            self.result = event
            usage = event.get("modelUsage")
            if isinstance(usage, dict):
                for model in usage:
                    self._model_seen(model)
            if event.get("is_error"):
                self._limit_seen(event.get("result"))
        return event

    def _limit_seen(self, text: object) -> None:
        if not self.usage_limit and isinstance(text, str):
            m = _USAGE_LIMIT.search(text)
            if m:
                self.usage_limit = _short(m.group(0), 200)

    def limit_resets(self) -> str:
        """When the usage limit resets, in words: Claude Code's ("2am (Europe/London)"),
        else the rejected ``rate_limit_event``'s time on this computer's clock, else ""."""
        m = _USAGE_LIMIT.search(self.usage_limit) if self.usage_limit else None
        when = (m.group("when") or "") if m else ""
        when = re.sub(r"\s*\(error type\b.*$", "", when).strip().rstrip(".")
        if when:
            return when
        if self.resets_at is not None:
            with contextlib.suppress(OverflowError, OSError, ValueError):
                at = datetime.fromtimestamp(self.resets_at)
                return f"on {at.day} {at:%B} at {at:%H:%M}"
        return ""

    @staticmethod
    def _model_name(side: object) -> str:
        if isinstance(side, dict) and isinstance(side.get("model"), str):
            return side["model"]
        return "another model"

    @staticmethod
    def _content(event: dict[str, Any]) -> list[dict[str, Any]]:
        message = event.get("message")
        if not isinstance(message, dict):
            return []
        content = message.get("content")
        if not isinstance(content, list):
            return []
        return [c for c in content if isinstance(c, dict)]

    # ---- conclusions ----

    def server_status(self) -> str | None:
        """The status the init event gives our MCP server ("connected", "failed", ...)."""
        if not self.init:
            return None
        servers = self.init.get("mcp_servers")
        for server in servers if isinstance(servers, list) else []:
            if isinstance(server, dict) and server.get("name") == SERVER_NAME:
                return str(server.get("status", ""))
        return "missing"

    def api_key_source(self) -> str | None:
        """The init event's ``apiKeySource`` ("none" when the subscription login is used)."""
        source = self.init.get("apiKeySource") if self.init else None
        return None if source is None else str(source)

    def model_switch_note(self, requested: str | None = None) -> str:
        """A plain explanation when a model other than the expected one answered, or ""."""
        expected = self.init.get("model") if self.init else None
        if not isinstance(expected, str) or not expected:
            expected = requested
        others = [m for m in self.models_used if expected and not _same_model(m, expected)]
        if not self.switches and not others:
            return ""
        parts = [f"Claude Code switched models during the run (requested: {expected})."]
        parts.extend(self.switches)
        if self.models_used:
            parts.append("Models that answered: " + ", ".join(self.models_used) + ".")
        parts.append(
            "So the run did not behave like a bare API call; check the result before using it."
        )
        return " ".join(parts)

    @property
    def turns(self) -> int:
        if self.result and isinstance(self.result.get("num_turns"), int):
            return int(self.result["num_turns"])
        return 0

    @property
    def final_text(self) -> str:
        if self.result and isinstance(self.result.get("result"), str):
            return self.result["result"]
        return self.texts[-1] if self.texts else ""

    @property
    def cost_usd(self) -> float | None:
        cost = self.result.get("total_cost_usd") if self.result else None
        return float(cost) if isinstance(cost, int | float) else None

    def result_error(self, max_turns: int | None = None) -> str:
        """A plain-language error from the result event, or "" when it succeeded."""
        if self.result is None:
            return ""
        subtype = str(self.result.get("subtype", ""))
        if subtype == "success" and not self.result.get("is_error"):
            return ""
        if subtype == "error_max_turns":
            limit = f" ({max_turns})" if max_turns else ""
            return (
                f"The designer used all its turns{limit} before it finished. The edits it made "
                "so far are saved; run it again or allow more turns."
            )
        detail = self.result.get("result")
        if not isinstance(detail, str) or not detail.strip():
            errors = self.result.get("errors")
            detail = "; ".join(str(e) for e in errors) if isinstance(errors, list) else ""
        detail = _short(redact(detail or subtype or "unknown problem"))
        return f"Claude Code reported a problem: {detail}"

    def limit_error(self) -> str:
        """The plain error for a session the usage limit stopped (see the contract)."""
        m = _USAGE_LIMIT.search(self.usage_limit)
        what = (m.group("what") or "").strip() if m else ""
        resets = self.limit_resets()
        said = (
            f"Your Claude subscription has reached its {what + ' ' if what else ''}usage limit "
            "(Claude Code said so instead of answering), so the run stopped."
        )
        if resets:
            return redact(f"{said} The limit resets {resets}.")
        return redact(f"{said} Claude Code did not say when it resets.")


def _same_model(used: str, expected: str) -> bool:
    """True when ``used`` is ``expected`` or a dated name of it ("claude-x-20261101")."""
    if used == expected:
        return True
    a, b = sorted((used, expected), key=len)
    return re.fullmatch(re.escape(a) + r"-\d{8}", b) is not None


def _duration_words(seconds: int) -> str:
    if seconds >= 120 and seconds % 60 == 0:
        return f"{seconds // 60} minutes"
    return f"{seconds} second" + ("" if seconds == 1 else "s")


# ---- running --------------------------------------------------------------------------------


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


@dataclass(frozen=True)
class Role:
    """Who a clean-room session is, for the words of its errors."""

    tools: str  # "design tools"
    stopped_kept: str  # added after "...so the run was stopped." when the output was unreadable
    timeout: str  # "The designer did not finish within {duration} and was stopped. ..."
    max_turns: str | None  # "... ({max_turns}) ..."; None: the parser's own (designer) words
    switched_kept: str  # added after the note that the model switched


DESIGNER = Role(
    tools="design tools",
    stopped_kept=" The edits made so far are saved.",
    timeout="The designer did not finish within {duration} and was stopped. The edits it made "
    "so far are saved.",
    max_turns=None,
    switched_kept=" The edits it made are saved.",
)
JUDGE = Role(
    tools="judging tools",
    stopped_kept="",
    timeout="The judge did not finish within {duration} and was stopped.",
    max_turns="The judge used all its turns ({max_turns}) before it gave its verdict.",
    switched_kept="",
)


def run_designer(
    project: Project,
    *,
    instruction: str | None = None,
    model: str = DEFAULT_MODEL,
    effort: str = "high",
    max_turns: int = 40,
    timeout_s: int = 1800,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    prompt_file: Path | None = None,
) -> DesignerRun:
    """Run the AI designer on ``project`` (see the contract above). Never raises for the
    usual failures; they come back as ``ok=False`` with ``error`` in plain words.

    ``on_event`` is called with each stream-json event as it arrives (for progress output).
    ``prompt_file`` replaces the system prompt (the parity check uses it); default prompt.md.
    """
    project_path = project.path.resolve()
    kind = run_kind(project, instruction)  # decided from the project as it is before the run
    if prompt_file is None:
        message = designer_message(project, instruction)
    else:  # another prompt (the parity probe) brings its own message, sent as it is
        message = instruction if instruction and instruction.strip() else DEFAULT_INSTRUCTION
    run = run_session(
        prompt_file=prompt_file or PROMPT_FILE,
        mcp=mcp_config(project_path),
        message=message,
        transcript=project.designer_dir / f"{_timestamp()}.jsonl",
        model=model,
        effort=effort,
        max_turns=max_turns,
        timeout_s=timeout_s,
        on_event=on_event,
        role=DESIGNER,
    )
    run.kind = kind
    return run


def run_session(
    *,
    prompt_file: Path,
    mcp: dict[str, Any],
    message: str,
    transcript: Path,
    model: str,
    effort: str,
    max_turns: int,
    timeout_s: int,
    on_event: Callable[[dict[str, Any]], None] | None = None,
    role: Role = DESIGNER,
) -> DesignerRun:
    """Start one clean-room session and watch it (shared by the designer and the judge).

    The command is ``build_command``, the environment ``designer_env()``, the working folder
    a new empty one; ``mcp`` is written there as the tool config and ``message`` goes to the
    model on standard input. Every output line is appended to ``transcript`` (its folder is
    made if need be). The session is stopped at once if Claude Code would use an API key or
    the tool server did not start, and fails if another model answered. Never raises for the
    usual failures; they come back as ``ok=False`` with ``error`` in plain words.
    """
    started = time.monotonic()
    run = DesignerRun(ok=False, transcript=transcript)
    parser = StreamParser()
    with contextlib.suppress(OSError):  # an unwritable folder is reported by the reader
        transcript.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bricksnap-designer-") as tmp:
        work = Path(tmp)
        config_file = work / "mcp.json"
        config_file.write_text(json.dumps(mcp, indent=1), encoding="utf-8")
        cmd = build_command(
            prompt_file.resolve(),
            config_file,
            model=model,
            effort=effort,
            max_turns=max_turns,
        )
        # an empty folder of its own as the working directory, kept apart from the config
        cwd = work / "cwd"
        cwd.mkdir()
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=designer_env(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except FileNotFoundError:
            run.error = (
                "Claude Code is not installed here: the 'claude' command was not found. "
                "Install Claude Code and sign in with your subscription, then try again."
            )
            run.duration_s = time.monotonic() - started
            return run
        except OSError as e:
            run.error = redact(f"Claude Code could not be started: {e}")
            run.duration_s = time.monotonic() - started
            return run

        stderr_tail: list[str] = []
        server_failed = threading.Event()
        api_key_used = threading.Event()
        reader_problem: list[str] = []

        def stop(problem: str) -> None:
            if not reader_problem:
                reader_problem.append(problem)
            with contextlib.suppress(OSError):
                proc.kill()

        def handle(line: str, out: Any) -> None:
            out.write(line if line.endswith("\n") else line + "\n")
            out.flush()
            event = parser.feed(line)
            if event is None:
                return
            if event.get("type") == "system" and event.get("subtype") == "init":
                if parser.server_status() not in ("connected", None):
                    server_failed.set()
                    proc.kill()
                elif parser.api_key_source() not in ("none", None):
                    api_key_used.set()
                    proc.kill()
            if on_event is not None:
                # progress output must never stop a run
                with contextlib.suppress(Exception):
                    on_event(event)

        def read_stdout() -> None:
            # Whatever goes wrong here, keep draining stdout so the child cannot block on a
            # full pipe, and make the failure the run's error.
            assert proc.stdout is not None
            try:
                out = transcript.open("a", encoding="utf-8")
            except OSError as e:
                stop(f"the transcript could not be written ({e})")
                out = None
            try:
                for line in proc.stdout:
                    if reader_problem or out is None:
                        continue
                    try:
                        handle(line, out)
                    except Exception as e:
                        stop(str(e) or type(e).__name__)
            finally:
                if out is not None:
                    out.close()

        def read_stderr() -> None:
            assert proc.stderr is not None
            for line in proc.stderr:
                stderr_tail.append(line.rstrip("\n"))
                del stderr_tail[:-20]

        readers = [
            threading.Thread(target=read_stdout, daemon=True),
            threading.Thread(target=read_stderr, daemon=True),
        ]
        for t in readers:
            t.start()
        try:
            assert proc.stdin is not None
            proc.stdin.write(message)
            proc.stdin.close()
        except OSError:
            pass  # the process ended early; its exit code and output say why

        timed_out = False
        try:
            proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
        for t in readers:
            t.join(timeout=10)

    run.tools_announced = parser.tools_announced
    run.tools_called = parser.tools_called
    run.tool_errors = parser.tool_errors
    run.turns = parser.turns
    run.final_text = redact(parser.final_text)
    run.cost_usd = parser.cost_usd
    run.models_used = list(parser.models_used)
    run.duration_s = time.monotonic() - started
    run.usage_limit = redact(parser.usage_limit)
    run.limit_resets = redact(parser.limit_resets()) if parser.usage_limit else ""
    run.limit_resets_at = parser.resets_at if parser.usage_limit else None
    switched = parser.model_switch_note(model)

    if server_failed.is_set():
        run.error = (
            f"The {role.tools} could not be started inside Claude Code (the bricksnap tool "
            f"server reported '{parser.server_status()}'), so the run was stopped."
        )
    elif api_key_used.is_set():
        run.error = redact(
            "Claude Code would use an API key, not your Claude subscription (it reported the "
            f"key source as '{parser.api_key_source()}'), so the run was stopped before the "
            "model did any work. Sign in to Claude Code with your subscription instead of a "
            "key, then try again."
        )
    elif reader_problem:
        run.error = _short(
            redact(
                f"BrickSnap could not read Claude Code's output ({reader_problem[0]}), so the "
                "run was stopped." + role.stopped_kept
            ),
            500,
        )
    elif timed_out:
        run.error = role.timeout.format(duration=_duration_words(timeout_s))
    elif parser.usage_limit:
        run.error = parser.limit_error()
    elif parser.result is not None and parser.result_error(max_turns):
        run.error = parser.result_error(max_turns)
        if role.max_turns and parser.result.get("subtype") == "error_max_turns":
            run.error = role.max_turns.format(max_turns=max_turns)
    elif proc.returncode != 0:
        tail = _short(redact(" ".join(stderr_tail[-5:]))) if stderr_tail else "no details given"
        run.error = f"Claude Code stopped with an error (exit code {proc.returncode}): {tail}"
    elif parser.result is None:
        run.error = "Claude Code ended without reporting a result, so the run may be incomplete."
    elif switched:
        run.error = switched + role.switched_kept
    else:
        run.ok = True
    return run


# ---- command line ---------------------------------------------------------------------------


def _progress(event: dict[str, Any]) -> None:
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        tools = ", ".join(str(t) for t in event.get("tools") or [])
        print(f"started; tools: {tools or 'none'}", flush=True)
    elif kind == "assistant":
        for item in StreamParser._content(event):
            if item.get("type") == "tool_use":
                name = str(item.get("name", "")).removeprefix(TOOL_PREFIX)
                detail = ""
                if name == "apply_ops":
                    ops = (item.get("input") or {}).get("ops")
                    detail = f" ({len(ops)} operations)" if isinstance(ops, list) else ""
                print(f"-> {name}{detail}", flush=True)
            elif item.get("type") == "text" and item.get("text"):
                print(redact(str(item["text"])).strip() + "\n", flush=True)


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(
        prog="python -m bricksnap.designer.runner",
        description="Run the AI designer on a project (uses your Claude subscription).",
    )
    ap.add_argument("project", help="the project folder")
    ap.add_argument("--instruction", default=None, help="what to ask the designer")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--effort", default="high")
    ap.add_argument("--max-turns", type=int, default=40)
    ap.add_argument("--timeout", type=int, default=1800, help="seconds")
    args = ap.parse_args(argv)
    try:
        project = Project(args.project)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2) from None
    run = run_designer(
        project,
        instruction=args.instruction,
        model=args.model,
        effort=args.effort,
        max_turns=args.max_turns,
        timeout_s=args.timeout,
        on_event=_progress,
    )
    calls: dict[str, int] = {}
    for name in run.tools_called:
        short = name.removeprefix(TOOL_PREFIX)
        calls[short] = calls.get(short, 0) + 1
    print("finished" if run.ok else "FAILED: " + run.error)
    print(f"turns: {run.turns}; time: {run.duration_s:.0f} s")
    print("tool calls: " + (", ".join(f"{k} x{v}" for k, v in calls.items()) or "none"))
    for err in run.tool_errors:
        print("tool error: " + err)
    if run.transcript:
        print("transcript: " + redact(str(run.transcript)))
    raise SystemExit(0 if run.ok else 1)


if __name__ == "__main__":
    main()
