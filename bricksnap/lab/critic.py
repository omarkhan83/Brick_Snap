"""The outside eye: an independent critic of a free build's looks (research prototype,
EXPERIMENTAL).

    python -m bricksnap.lab.critic /path/to/runs/NNNN/critic      (its tool server)

The builder's own critique (``lab.art``) is lenient: it answers "yes" about its own work
where the numbers say otherwise. A critique written by a reviewer who saw only the pictures,
turned into a change run, improved a finished model clearly (25 November). This module is
that reviewer: one short clean-room AI session that is shown the model and nothing of how it
was made, and answers with up to five concrete fixes. ``freebuild.critique`` gathers what it
is shown and keeps its answer; ``freebuild.polish`` turns the answer into a change.

CONTRACT (tests in tests/test_polish.py; no test starts a real AI session)

What it is shown is prepared in one folder (``prepare``), so its tools can read nothing else:
    shown.json       {"pictures": [{"file", "caption"}...], "references": [{"file",
                     "caption"}...]}: the files, in order, and one line saying what each is
    model-N.png      the model's pictures (the caller's: the three-view sheet and views round it)
    reference-N.png  the pictures the person gave of what to build, when there are any
    answer.json      the answer, once ``critique`` has accepted one
    <UTC>.jsonl      the session's transcript, redacted (``runner.redact``) when it ends
``prepare(folder, pictures, references)`` copies the given ``(path, caption)`` pairs in under
those names, removing the pictures, list and answer of an earlier critique of the same run
(transcripts stay). The message (``message``) holds only the words the model was built from,
the changes the person asked for since, the brief's lines and the HOW IT LOOKS lines, with
how many reference pictures there are: every text the caller gives, and nothing else.

The tools (``CRITIC_TOOLS``, plain JSON like ``designer.tools.TOOLS``; the server is named
"bricksnap" like the others, so the runner's flags and checks apply unchanged):
    look      ``{"what": "model"}`` (the default) gives every model picture with one line per
              picture; ``{"what": "references"}`` the reference pictures (an "ERROR:" when
              there are none). A look counts once its pictures were read and sent.
    critique  ``{"fixes": [{"where", "fix"}, ...], "keep"}``: at most ``MAX_FIXES`` fixes
              (none is allowed: no padding), the most visible first, each naming where on the
              model (at most ``WHERE_CHARS``) and what to do in brick terms (at most
              ``FIX_CHARS``), and what already works and must be kept (at most
              ``KEEP_CHARS``). Refused, with every problem named in one "ERROR:", until the
              model has been looked at (and the references, when there are any), or when a
              field is missing, empty, too long or not text, or a key is unknown. A good answer
              is cleaned (``judge_server.clean``: e-mail addresses and the home folder hidden,
              control characters gone) with its spaces collapsed, written to answer.json and
              read back to the critic; a later call replaces it.
``Critic(folder).call(name, args)`` never raises: unknown tools, bad arguments and a folder
that is missing or damaged come back as one "ERROR:" text block, and every text sent has the
folder's path, e-mail addresses and the home folder removed (``tools._scrub``). Pictures
larger than ``tools.MAX_IMAGE_BYTES`` are reduced as the designer's are.

``run(folder, message, model=..., effort=..., on_event=None)``: one ``runner.run_session``
with ``critic_prompt.md`` (in this folder), this module as the tool server for ``folder``, at
most ``MAX_TURNS`` replies and ``TIMEOUT_S`` seconds, and the critic's own words for its
errors (``ROLE``); its ``kind`` is "critique". ``read_answer(folder)`` is the answer when it
is complete (``{"fixes": [...], "keep"}``), else None. ``progress(event)`` gives plain
sentences for its stream-json events ("The outside eye is looking at the model").
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import shutil
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bricksnap.designer import runner

SERVER_NAME = "bricksnap"
SERVER_MODULE = "bricksnap.lab.critic"
PROMPT_FILE = Path(__file__).parent / "critic_prompt.md"
SHOWN_FILE = "shown.json"
ANSWER_FILE = "answer.json"
MAX_FIXES = 5
WHERE_CHARS = 60
FIX_CHARS = 220
KEEP_CHARS = 200
# A critic looks (one reply, the model and the references together), answers, and closes:
# three replies, four with a reference look of its own. The rest is room for fixing a refused
# answer. Ten minutes is several times what three replies with a handful of pictures take.
MAX_TURNS = 8
TIMEOUT_S = 600

ROLE = runner.Role(
    tools="outside eye's tools",
    stopped_kept="",
    timeout="The outside eye did not finish within {duration} and was stopped.",
    max_turns="The outside eye used all its turns ({max_turns}) before it gave its list.",
    switched_kept="",
)

log = logging.getLogger("bricksnap.lab.critic")

CRITIC_TOOLS: list[dict[str, Any]] = [
    {
        "name": "look",
        "description": (
            'Look at the model. {"what": "model"} returns its pictures: a sheet of three views '
            "(from the front-left above, from the back-right above, straight from the front), "
            "then four views from all round it, each with a line saying where it is seen from. "
            '{"what": "references"} returns the pictures the person gave of what to build, '
            "when there are any (the message says how many). Look at the model, and at the "
            "references when there are any, before you give your critique."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "what": {
                    "type": "string",
                    "enum": ["model", "references"],
                    "description": '"model" (the default) or "references".',
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "critique",
        "description": (
            "Give your critique, once you have looked: up to five fixes, the most visible "
            'first, each with "where" (the place on the model, in a few words a builder can '
            'find) and "fix" (what is wrong there and what to do about it, in brick terms: the '
            'parts and techniques to use); and "keep": one line on what already works and must '
            "be kept. Fewer fixes are better than padding; none is allowed when nothing would "
            'clearly improve the model. Returns the critique as recorded, or "ERROR:" with '
            "everything to fix (then nothing is recorded). Calling it again replaces it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fixes": {
                    "type": "array",
                    "maxItems": MAX_FIXES,
                    "items": {
                        "type": "object",
                        "properties": {
                            "where": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": WHERE_CHARS,
                                "description": 'Where on the model, e.g. "the front corners".',
                            },
                            "fix": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": FIX_CHARS,
                                "description": "What is wrong there and what to do, in brick "
                                'terms, e.g. "they are stacked plates: press 2 x 2 curved '
                                'slopes on side studs instead".',
                            },
                        },
                        "required": ["where", "fix"],
                        "additionalProperties": False,
                    },
                    "description": "The fixes, the most visible first; at most five.",
                },
                "keep": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": KEEP_CHARS,
                    "description": "One line: what already works and must be kept.",
                },
            },
            "required": ["fixes", "keep"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = tuple(t["name"] for t in CRITIC_TOOLS)

_CANNOT_FIX = (
    " This is a problem with the program, and none of your tools can fix it. Stop and say so "
    "in your reply."
)


class _NotPrepared(Exception):
    """The folder is missing or damaged; the model cannot fix that."""


def _text(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _error(text: str) -> list[dict[str, Any]]:
    return [_text("ERROR: " + text)]


def _clean(text: str) -> str:
    from bricksnap.designer.judge_server import clean

    return " ".join(clean(text).split())


# ---- what it is shown ------------------------------------------------------------------------


def prepare(
    folder: Path, pictures: list[tuple[Path, str]], references: list[tuple[Path, str]]
) -> dict[str, Any]:
    """Copy what the critic is shown into ``folder`` (see the contract); returns shown.json."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in [*folder.glob("model-*.png"), *folder.glob("reference-*.png")]:
        old.unlink()
    for name in (SHOWN_FILE, ANSWER_FILE):
        with contextlib.suppress(FileNotFoundError):
            (folder / name).unlink()
    shown: dict[str, Any] = {"pictures": [], "references": []}
    for key, stem, given in (
        ("pictures", "model", pictures),
        ("references", "reference", references),
    ):
        for k, (path, caption) in enumerate(given, 1):
            name = f"{stem}-{k}.png"
            shutil.copyfile(path, folder / name)
            shown[key].append({"file": name, "caption": caption})
    (folder / SHOWN_FILE).write_text(json.dumps(shown, indent=1) + "\n", encoding="utf-8")
    return shown


def message(
    words: str,
    changes: list[str],
    brief: str,
    looks: str,
    references: int,
) -> str:
    """What the critic is told: these texts and the number of reference pictures, nothing
    else. ``brief`` and ``looks`` may be empty."""
    parts = ["Look at this model and write the fixes that would most improve how it looks.", ""]
    if words.strip():
        parts += ["What it is meant to be, in the person's words:", f'"{words.strip()}"', ""]
    else:
        parts += [
            "There were no words: it was built from the reference pictures, so they say what it "
            "is meant to be.",
            "",
        ]
    if changes:
        parts.append("Changes the person asked for since, oldest first:")
        parts += [f'- "{c.strip()}"' for c in changes]
        parts.append("")
    if brief.strip():
        parts += ["Its art direction (the brief):", brief.strip(), ""]
    else:
        parts += ["It has no written art direction.", ""]
    if looks.strip():
        parts += [looks.strip(), ""]
    if references:
        one = references == 1
        parts += [
            f"There {'is' if one else 'are'} {references} reference picture{'' if one else 's'} "
            f'of what to build: look at {"it" if one else "them"} with look {{"what": '
            '"references"}.',
            "",
        ]
    parts.append(
        'Look at the model with look {"what": "model"}, then call critique once with your '
        "fixes, the most visible first, and what to keep."
    )
    return "\n".join(parts)


# ---- the tools -------------------------------------------------------------------------------


class Critic:
    """The critic's two tools for one prepared folder; remembers what it has looked at."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self.looked: set[str] = set()

    def _shown(self) -> dict[str, list[dict[str, str]]]:
        try:
            data = json.loads((self.folder / SHOWN_FILE).read_text(encoding="utf-8"))
        except FileNotFoundError as e:
            raise _NotPrepared("there is no model to look at here.") from e
        except (OSError, ValueError) as e:
            raise _NotPrepared("the list of pictures could not be read.") from e
        out: dict[str, list[dict[str, str]]] = {"pictures": [], "references": []}
        for key in out:
            items = data.get(key) if isinstance(data, dict) else None
            if not isinstance(items, list):
                raise _NotPrepared("the list of pictures is damaged.")
            for item in items:
                name = item.get("file") if isinstance(item, dict) else None
                if not isinstance(name, str) or "/" in name or "\\" in name or name.startswith("."):
                    raise _NotPrepared("the list of pictures is damaged.")
                out[key].append({"file": name, "caption": str(item.get("caption") or "")})
        if not out["pictures"]:
            raise _NotPrepared("there are no pictures of the model.")
        return out

    def call(self, name: Any, args: Any) -> list[dict[str, Any]]:
        from bricksnap.designer.tools import _scrub

        try:
            blocks = self._call(name, args)
        except _NotPrepared as e:
            blocks = _error(str(e) + _CANNOT_FIX)
        except OSError as e:
            blocks = _error(f"a picture could not be read ({e.strerror or 'unknown'}).")
        except Exception as e:  # never hand a traceback to the model
            said = " ".join((str(e) or type(e).__name__).split())[:200]
            blocks = _error(f"the tool could not finish: {said}")
        return [
            {**b, "text": _scrub(str(b.get("text", "")), self.folder)}
            if b.get("type") == "text"
            else b
            for b in blocks
        ]

    def _call(self, name: Any, args: Any) -> list[dict[str, Any]]:
        if name not in TOOL_NAMES:
            return _error("there is no such tool. The tools are look and critique.")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return _error(f"the arguments to {name} must be a JSON object.")
        if name == "look":
            return self._look(args)
        return self._critique(args)

    def _picture(self, name: str) -> dict[str, Any]:
        from PIL import Image

        from bricksnap.designer.tools import _png_bytes

        path = self.folder / name
        if not path.is_file():
            raise _NotPrepared(f"the picture {name} is missing.")
        with Image.open(path) as im:
            im.load()
            data = _png_bytes(im)
        return {"type": "image", "media_type": "image/png", "data": base64.b64encode(data).decode()}

    def _look(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        shown = self._shown()
        unknown = [k for k in args if k != "what"]
        if unknown:
            return _error('look takes only "what": "model" or "references".')
        what = args.get("what", "model")
        if what not in ("model", "references"):
            return _error('look needs "what": "model" or "references".')
        items = shown["pictures"] if what == "model" else shown["references"]
        if not items:
            return _error(
                "there are no reference pictures for this model; look at the model itself, "
                'with {"what": "model"}.'
            )
        blocks = [self._picture(item["file"]) for item in items]
        self.looked.add(what)
        head = (
            f"The model, in {len(items)} pictures:"
            if what == "model"
            else f"What to build, as the person gave it, in {len(items)} picture"
            + ("s:" if len(items) > 1 else ":")
        )
        lines = [head] + [f"- Picture {k}: {item['caption']}" for k, item in enumerate(items, 1)]
        if what == "model" and shown["references"] and "references" not in self.looked:
            lines.append('Now look at the references too, with {"what": "references"}.')
        return [*blocks, _text("\n".join(lines))]

    def _critique(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        shown = self._shown()
        problems: list[str] = []
        unknown = [k for k in args if k not in ("fixes", "keep")]
        if unknown:
            problems.append('send only "fixes" and "keep".')
        fixes: list[dict[str, str]] = []
        raw = args.get("fixes")
        if "fixes" not in args:
            problems.append('"fixes" is missing: a list of up to five {"where", "fix"} (or []).')
        elif not isinstance(raw, list):
            problems.append('"fixes" must be a list of up to five {"where", "fix"}.')
        else:
            if len(raw) > MAX_FIXES:
                problems.append(
                    f'"fixes" has {len(raw)}; give at most {MAX_FIXES}, the most visible first.'
                )
            for k, item in enumerate(raw[:MAX_FIXES], 1):
                if not isinstance(item, dict):
                    problems.append(f'fix {k} must be an object with "where" and "fix".')
                    continue
                if any(key not in ("where", "fix") for key in item):
                    problems.append(f'fix {k} may have only "where" and "fix".')
                kept: dict[str, str] = {}
                for key, limit in (("where", WHERE_CHARS), ("fix", FIX_CHARS)):
                    value = item.get(key)
                    if not isinstance(value, str) or not value.strip():
                        problems.append(f'fix {k} needs "{key}" as text.')
                    elif len(value.strip()) > limit:
                        problems.append(
                            f'fix {k}\'s "{key}" has {len(value.strip())} characters; keep it to '
                            f"{limit} or fewer."
                        )
                    else:
                        kept[key] = _clean(value)
                if len(kept) == 2:
                    fixes.append(kept)
        keep = args.get("keep")
        if not isinstance(keep, str) or not keep.strip():
            problems.append('"keep" must be one line of text: what already works and must be kept.')
        elif len(keep.strip()) > KEEP_CHARS:
            problems.append(
                f'"keep" has {len(keep.strip())} characters; keep it to {KEEP_CHARS} or fewer.'
            )
        if "model" not in self.looked:
            problems.append('you have not looked at the model yet: call look {"what": "model"}.')
        if shown["references"] and "references" not in self.looked:
            problems.append(
                'you have not looked at the references yet: call look {"what": "references"}.'
            )
        if problems:
            return _error(
                "the critique was not recorded. Fix these and call critique again:\n"
                + "\n".join(f"- {p}" for p in problems)
            )
        from bricksnap.types import write_text_atomic

        answer = {"fixes": fixes, "keep": _clean(str(keep))}
        write_text_atomic(self.folder / ANSWER_FILE, json.dumps(answer, indent=1) + "\n")
        lines = [
            f"Critique recorded: {len(fixes)} fix{'' if len(fixes) == 1 else 'es'}.",
            *(f"{k}. {f['where']}: {f['fix']}" for k, f in enumerate(fixes, 1)),
            f"Keep: {answer['keep']}",
            "You are done; reply with one sentence.",
        ]
        return [_text("\n".join(lines))]


def call_tool(folder: str | Path, name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    """One call on a fresh ``Critic`` (which then remembers nothing)."""
    return Critic(folder).call(name, args)


def read_answer(folder: Path) -> dict[str, Any] | None:
    """The critic's answer when it is complete, else None."""
    try:
        data = json.loads((folder / ANSWER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("fixes"), list):
        return None
    keep = data.get("keep")
    fixes = [
        {"where": str(f["where"]), "fix": str(f["fix"])}
        for f in data["fixes"][:MAX_FIXES]
        if isinstance(f, dict) and isinstance(f.get("where"), str) and isinstance(f.get("fix"), str)
    ]
    if len(fixes) != len(data["fixes"]) or not isinstance(keep, str) or not keep.strip():
        return None
    return {"fixes": fixes, "keep": keep}


# ---- the session -----------------------------------------------------------------------------


def run(
    folder: Path,
    text: str,
    *,
    model: str,
    effort: str = "high",
    on_event: Callable[[dict[str, Any]], None] | None = None,
) -> runner.DesignerRun:
    """One clean-room critic session on the prepared ``folder``, told ``text``."""
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    transcript = folder / f"{stamp}.jsonl"
    done = runner.run_session(
        prompt_file=PROMPT_FILE,
        mcp=runner.mcp_config(folder, module=SERVER_MODULE),
        message=text,
        transcript=transcript,
        model=model,
        effort=effort,
        max_turns=MAX_TURNS,
        timeout_s=TIMEOUT_S,
        on_event=on_event,
        role=ROLE,
    )
    done.kind = "critique"
    with contextlib.suppress(OSError):  # it holds the account's e-mail address
        if transcript.is_file():
            raw = transcript.read_text(encoding="utf-8", errors="replace")
            transcript.write_text(runner.redact(raw), encoding="utf-8")
    return done


PROGRESS = {
    "look": "The outside eye is looking at the model's pictures",
    "look references": "The outside eye is looking at the pictures the model was built from",
    "critique": "The outside eye is writing down its fixes",
}


def progress(event: dict[str, Any]) -> list[str]:
    """Plain sentences for one stream-json event of a critic session."""
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        return ["The outside eye has started: it sees only the pictures, the words and the brief"]
    if kind != "assistant":
        return []
    out = []
    for item in runner.StreamParser._content(event):
        if item.get("type") != "tool_use":
            continue
        name = str(item.get("name", "")).removeprefix(runner.TOOL_PREFIX)
        args = item.get("input") if isinstance(item.get("input"), dict) else {}
        if name == "look" and (args or {}).get("what") == "references":
            name = "look references"
        if name in PROGRESS:
            out.append(PROGRESS[name])
    return out


# ---- the server ------------------------------------------------------------------------------


def make_server(folder: Path) -> Any:
    """The MCP server for one prepared folder (not yet running)."""
    import anyio
    import anyio.to_thread
    import mcp.types as types
    from mcp.server.lowlevel import Server

    from bricksnap.designer.mcp_server import _to_mcp_content

    tools = [
        types.Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
        for t in CRITIC_TOOLS
    ]
    critic = Critic(folder)

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    one_at_a_time = anyio.Lock()

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        log.info("tool call: %s", name)
        async with one_at_a_time:
            blocks = await anyio.to_thread.run_sync(critic.call, name, args)
        is_error = (
            len(blocks) == 1
            and blocks[0].get("type") == "text"
            and str(blocks[0].get("text", "")).startswith("ERROR:")
        )
        return types.CallToolResult(content=_to_mcp_content(blocks), is_error=is_error)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def serve(folder: Path) -> None:
    from mcp.server.stdio import stdio_server

    server = make_server(folder)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main(argv: list[str] | None = None) -> None:
    import anyio

    argv = sys.argv[1:] if argv is None else argv
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="bricksnap-critic: %(levelname)s %(message)s"
    )
    if len(argv) != 1:
        sys.stderr.write("Usage: python -m bricksnap.lab.critic <prepared critic folder>\n")
        raise SystemExit(2)
    folder = Path(argv[0]).resolve()
    if not (folder / SHOWN_FILE).is_file():
        sys.stderr.write(f"{folder} holds nothing prepared for the critic.\n")
        raise SystemExit(2)
    anyio.run(serve, folder)


if __name__ == "__main__":
    main()
