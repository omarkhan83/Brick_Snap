"""Serve the judge's two tools over MCP (stdio) for one candidates folder.

    python -m bricksnap.designer.judge_server /path/to/project/candidates

The judge is the second, separate AI session of ``bricksnap.designer.judge``: it looks at
several brick builds of the same object and ranks them. Its contract is in judge.py ("The
judge"); this module holds the two tools and the server that offers them.

Implementation notes
--------------------
- ``JUDGE_TOOLS`` holds the two tool definitions (``look`` and ``choose``) as plain JSON, in
  the same shape as ``bricksnap.designer.tools.TOOLS``, so they move to the API unchanged.
  The server is named "bricksnap", like the designer's, so the runner's command line
  (``--allowedTools mcp__bricksnap``) and its check that the server started are the same;
  the model sees ``mcp__bricksnap__look`` and ``mcp__bricksnap__choose``.
- Everything the judge may see is prepared beforehand by judge.py in
  ``<candidates>/judging/``: ``judging.json`` (the letters, in order, and one line of facts
  per letter), ``<letter>.png`` (the seed above that candidate's build, the designer's
  ``render`` picture) and ``all.png`` (the seed and every candidate side by side). Nothing
  there names a candidate's number, folder, run or brief. The tools read only that folder,
  so the judge cannot learn more than it is shown.
- ``Judging(folder).call(name, args)`` answers one call with content blocks (``{"type":
  "text"}`` and ``{"type": "image", "media_type": "image/png", "data": base64}``). It never
  raises: an unknown tool, bad arguments, an unknown letter or a damaged folder come back as
  one text block starting "ERROR:" that says what to fix. The server sends such a result
  with ``isError`` set.
- ``choose`` refuses until every candidate has been looked at on its own with ``look``
  (the prompt asks for that; the refusal makes sure of it), and lists every problem in one
  reply so one retry can fix them all. A good verdict is written to
  ``judging/verdict.json`` (``ranking``, ``reasons``, ``summary``); a later ``choose``
  replaces it. A refused one changes nothing on disk.
- Texts are limited in length (``REASON_LIMIT``, ``SUMMARY_LIMIT``) and anything the model
  sent that an error repeats is cut short, so a reply stays small whatever was sent.
- Every text sent has the candidates folder's path, e-mail addresses and the home folder
  removed (``tools._scrub``), as for the designer's tools. The verdict's reasons and summary
  are cleaned before they are written (``clean``: ``runner.redact``, and control characters
  such as terminal escapes removed), because they are later printed and saved for a person.
- A look counts towards "looked at every candidate" only when its picture was read and
  sent; a look that came back as an ERROR does not.
- Pictures larger than ``tools.MAX_IMAGE_BYTES`` are reduced the same way the designer's
  ``render`` reduces them.
- Calls run one at a time (one lock per server) in a worker thread, as in mcp_server.py.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "bricksnap"
JUDGING_DIR = "judging"
JUDGING_FILE = "judging.json"
VERDICT_FILE = "verdict.json"
ALL = "all"
LETTERS = "ABCDE"
REASON_LIMIT = 800
SUMMARY_LIMIT = 1500

log = logging.getLogger("bricksnap.designer.judge_server")

JUDGE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "look",
        "description": (
            "Look at the candidates. Each candidate is a brick build of the same object, "
            'named by a letter. {"candidate": "all"} returns one sheet with the original 3D '
            "model (the seed) and every candidate side by side, each under its letter, from "
            "the front and from a three-quarter view: use it to compare them directly. "
            '{"candidate": "A"} returns one picture of candidate A: the seed\'s views in the '
            "top row and the candidate's build in the bottom row, from the same viewpoints "
            "(front, right side, top, three-quarter) at the same scale, with stud and plate "
            "numbers along the edges; and one line of facts about it: how many parts it has, "
            "how many weak spots (places where a group of parts hangs on a single part or a "
            "single stud), and the largest group that hangs on one part. Look at every "
            "candidate this way before you choose."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "candidate": {
                    "type": "string",
                    "enum": [ALL, *LETTERS],
                    "description": 'A candidate\'s letter, such as "A", or "all" for the sheet '
                    "with every candidate.",
                }
            },
            "required": ["candidate"],
            "additionalProperties": False,
        },
    },
    {
        "name": "choose",
        "description": (
            "Give your verdict, once you have looked at every candidate: the ranking, best "
            "first, with every candidate's letter exactly once; a reason for every candidate, "
            "one or two sentences on what makes it better or worse than the others, as you "
            "saw it in the pictures; and a short summary of how you decided, saying so "
            "honestly if two were hard to separate. The build ranked first is kept. Returns "
            'the verdict as recorded, or "ERROR:" with everything to fix (then nothing is '
            "recorded). Calling it again replaces the verdict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ranking": {
                    "type": "array",
                    "items": {"type": "string", "enum": list(LETTERS)},
                    "minItems": 1,
                    "maxItems": len(LETTERS),
                    "uniqueItems": True,
                    "description": 'Every candidate\'s letter once, best first, e.g. ["B", "A", '
                    '"C"].',
                },
                "reasons": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": REASON_LIMIT,
                    },
                    "description": "For every candidate's letter, one or two sentences: why it "
                    "is ranked where it is, compared with the others.",
                },
                "summary": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": SUMMARY_LIMIT,
                    "description": "A few sentences: how you decided, and how close it was.",
                },
            },
            "required": ["ranking", "reasons", "summary"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = tuple(t["name"] for t in JUDGE_TOOLS)


# ---- helpers ------------------------------------------------------------------------------


def _text(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def _error(text: str) -> list[dict[str, Any]]:
    return [_text("ERROR: " + text)]


def _clip(text: str, limit: int = 40) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _show(value: Any) -> str:
    """A short, safe rendering of something the model sent."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return '"' + _clip(value) + '"'
    if isinstance(value, int | float):
        return _clip(repr(value))
    if isinstance(value, list | tuple):
        return "a list"
    if isinstance(value, dict):
        return "an object"
    return "a value of an unexpected kind"


def _names(values: Any, limit: int = 5) -> str:
    shown = [_show(v) for v in values]
    text = ", ".join(shown[:limit])
    if len(shown) > limit:
        text += f" and {len(shown) - limit} more"
    return text


def _list_words(letters: list[str]) -> str:
    if len(letters) <= 1:
        return "".join(letters)
    return ", ".join(letters[:-1]) + " and " + letters[-1]


_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def clean(text: str) -> str:
    """The judge's words as a person may see them: e-mail addresses and the home folder
    hidden (``runner.redact``) and control characters (terminal escapes) removed."""
    from bricksnap.designer.runner import redact

    return redact(_CONTROL.sub("", text)).strip()


class _NotPrepared(Exception):
    """The judging folder is missing or damaged; the model cannot fix that."""


_CANNOT_FIX = (
    " This is a problem with the program, and none of your tools can fix it. Stop and say so "
    "in your reply."
)


# ---- the tools ----------------------------------------------------------------------------


class Judging:
    """The judge's two tools for one candidates folder. Holds which candidates the judge
    has looked at during this session."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        self.looked: set[str] = set()

    @property
    def judging_dir(self) -> Path:
        return self.folder / JUDGING_DIR

    def _setup(self) -> tuple[list[str], dict[str, str]]:
        """(letters, facts by letter), from judging.json."""
        try:
            data = json.loads((self.judging_dir / JUDGING_FILE).read_text(encoding="utf-8"))
        except FileNotFoundError as e:
            raise _NotPrepared("there are no candidates to judge here.") from e
        except (OSError, ValueError) as e:
            raise _NotPrepared("the list of candidates could not be read.") from e
        letters = data.get("letters") if isinstance(data, dict) else None
        facts = data.get("facts") if isinstance(data, dict) else None
        if (
            not isinstance(letters, list)
            or not letters
            or not all(isinstance(x, str) and x in LETTERS for x in letters)
            or len(set(letters)) != len(letters)
        ):
            raise _NotPrepared("the list of candidates is damaged.")
        if not isinstance(facts, dict):
            facts = {}
        return letters, {k: str(v) for k, v in facts.items() if isinstance(k, str)}

    # ---- entry point ----

    def call(self, name: Any, args: Any) -> list[dict[str, Any]]:
        from bricksnap.designer.tools import _scrub

        try:
            blocks = self._call(name, args)
        except _NotPrepared as e:
            blocks = _error(str(e) + _CANNOT_FIX)
        except OSError as e:
            blocks = _error(f"a picture or file could not be read ({e.strerror or 'unknown'}).")
        except Exception as e:  # never hand a traceback to the model
            blocks = _error(f"the tool could not finish: {_clip(str(e) or type(e).__name__, 200)}")
        return [
            {**b, "text": _scrub(str(b.get("text", "")), self.folder)}
            if b.get("type") == "text"
            else b
            for b in blocks
        ]

    def _call(self, name: Any, args: Any) -> list[dict[str, Any]]:
        if name not in TOOL_NAMES:
            return _error(f"there is no tool called {_show(name)}. The tools are look and choose.")
        if args is None:
            args = {}
        if not isinstance(args, dict):
            return _error(f"the arguments to {name} must be a JSON object.")
        if name == "look":
            return self._look(args)
        return self._choose(args)

    # ---- look ----

    def _look(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        letters, facts = self._setup()
        choices = f'"all" or one of {_list_words(letters)}'
        unknown = [k for k in args if k != "candidate"]
        if unknown:
            return _error(
                f'look takes only "candidate" ({choices}), not {_names(unknown)}. For example: '
                '{"candidate": "all"}.'
            )
        which = args.get("candidate")
        if not isinstance(which, str):
            return _error(f'look needs "candidate": {choices}, as text, not {_show(which)}.')
        if which.strip().lower() == ALL:
            return self._look_all(letters)
        letter = which.strip()
        if letter not in letters:
            return _error(f"there is no candidate {_show(which)}. Choose {choices}.")
        picture = self._picture(f"{letter}.png")
        self.looked.add(letter)  # only a look that showed the picture counts
        fact = facts.get(letter, "No facts were recorded for this candidate.")
        others = [x for x in letters if x not in self.looked]
        still = (
            f"Still to look at on their own: {_list_words(others)}."
            if others
            else "You have now looked at every candidate on its own."
        )
        text = "\n".join(
            [
                f"Candidate {letter}.",
                "- Top row: the seed, the original 3D model. Bottom row: candidate "
                f"{letter}'s build, part by part (each part has a thin dark outline). Both rows "
                "are drawn from the same viewpoints at the same scale, so they line up.",
                "- Columns: front; right side (picture right is towards the back); top (seen "
                "from above, the front at the bottom); three-quarter view from the front "
                "right. The numbers along the edges count studs across and plates up; a "
                "brick is three plates tall.",
                f"- Facts about {letter}: {fact}",
                still,
            ]
        )
        return [picture, _text(text)]

    def _look_all(self, letters: list[str]) -> list[dict[str, Any]]:
        picture = self._picture("all.png")
        text = "\n".join(
            [
                f"All {len(letters)} candidates: {_list_words(letters)}.",
                "- The first column is the seed, the original 3D model; each further column is "
                "one candidate's build, captioned with its letter.",
                "- Top row: seen from the front. Bottom row: a three-quarter view from the front "
                "right and above. Every picture in a row is drawn at the same scale.",
                "- To see a candidate from more sides, with its facts, call look with its "
                "letter. Look at each one that way before you choose.",
            ]
        )
        return [picture, _text(text)]

    def _picture(self, name: str) -> dict[str, Any]:
        from PIL import Image

        from bricksnap.designer.tools import _png_bytes

        path = self.judging_dir / name
        if not path.is_file():
            raise _NotPrepared(f"the picture {name} is missing.")
        with Image.open(path) as im:
            im.load()
            data = _png_bytes(im)
        return {"type": "image", "media_type": "image/png", "data": base64.b64encode(data).decode()}

    # ---- choose ----

    def _choose(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        letters, _ = self._setup()
        problems: list[str] = []
        unknown = [k for k in args if k not in ("ranking", "reasons", "summary")]
        if unknown:
            problems.append(
                f"{_names(unknown)} {'is' if len(unknown) == 1 else 'are'} not part of the "
                'verdict; send only "ranking", "reasons" and "summary".'
            )
        missing = [k for k in ("ranking", "reasons", "summary") if k not in args]
        if missing:
            problems.append("missing: " + ", ".join(f'"{k}"' for k in missing) + ".")
        every = f"every candidate's letter ({_list_words(letters)}) exactly once"

        ranking: list[str] = []
        if "ranking" in args:
            raw = args["ranking"]
            if not isinstance(raw, list):
                problems.append(
                    f'"ranking" must be a list of {every}, best first, not {_show(raw)}.'
                )
            else:
                bad = [x for x in raw if not isinstance(x, str) or x not in letters]
                if bad:
                    problems.append(
                        f'"ranking" has {_names(bad)}, which '
                        + ("is not a candidate" if len(bad) == 1 else "are not candidates")
                        + f"; the candidates are {_list_words(letters)}."
                    )
                ranking = [x for x in raw if isinstance(x, str) and x in letters]
                twice = sorted({x for x in ranking if ranking.count(x) > 1})
                if twice:
                    problems.append(f'"ranking" lists {_list_words(twice)} more than once.')
                left_out = [x for x in letters if x not in ranking]
                if left_out:
                    problems.append(f'"ranking" leaves out {_list_words(left_out)}; give {every}.')

        reasons: dict[str, str] = {}
        if "reasons" in args:
            raw = args["reasons"]
            if not isinstance(raw, dict):
                problems.append(
                    '"reasons" must be an object with a sentence or two for every candidate, '
                    f'such as {{"{letters[0]}": "..."}}, not {_show(raw)}.'
                )
            else:
                stray = [k for k in raw if k not in letters]
                if stray:
                    problems.append(
                        f'"reasons" has {_names(stray)}, which '
                        + ("is not a candidate" if len(stray) == 1 else "are not candidates")
                        + f"; the candidates are {_list_words(letters)}."
                    )
                for letter in letters:
                    value = raw.get(letter)
                    if letter not in raw:
                        problems.append(f'"reasons" has no reason for {letter}.')
                    elif not isinstance(value, str) or not value.strip():
                        problems.append(
                            f"the reason for {letter} must be a sentence or two of text."
                        )
                    elif len(value.strip()) > REASON_LIMIT:
                        problems.append(
                            f"the reason for {letter} has {len(value.strip())} characters; keep it "
                            f"to {REASON_LIMIT} or fewer."
                        )
                    else:
                        reasons[letter] = value.strip()

        summary = ""
        if "summary" in args:
            raw = args["summary"]
            if not isinstance(raw, str) or not raw.strip():
                problems.append('"summary" must be a few sentences of text: how you decided.')
            elif len(raw.strip()) > SUMMARY_LIMIT:
                problems.append(
                    f'"summary" has {len(raw.strip())} characters; keep it to {SUMMARY_LIMIT} '
                    "or fewer."
                )
            else:
                summary = raw.strip()

        not_seen = [x for x in letters if x not in self.looked]
        if not_seen:
            problems.append(
                f"you have not looked at {_list_words(not_seen)} on "
                f"{'its' if len(not_seen) == 1 else 'their'} own yet. Call look with "
                + " and ".join(f'{{"candidate": "{x}"}}' for x in not_seen)
                + ", then choose."
            )
        if problems:
            return _error(
                "the verdict was not recorded. Fix these and call choose again:\n"
                + "\n".join(f"- {p}" for p in problems)
            )

        from bricksnap.types import write_text_atomic

        reasons = {x: clean(reasons[x]) for x in ranking}
        summary = clean(summary)
        verdict = {"ranking": ranking, "reasons": reasons, "summary": summary}
        write_text_atomic(self.judging_dir / VERDICT_FILE, json.dumps(verdict, indent=1) + "\n")
        lines = [
            "Verdict recorded. " + ", then ".join(ranking) + f". {ranking[0]} will be kept.",
            *(f"- {x}: {reasons[x]}" for x in ranking),
            f"Summary: {summary}",
            "You are done; reply with one sentence.",
        ]
        return [_text("\n".join(lines))]


def call_tool(folder: str | Path, name: str, args: dict[str, Any]) -> list[dict[str, Any]]:
    """One call on a fresh ``Judging`` (which remembers nothing between calls)."""
    return Judging(folder).call(name, args)


# ---- the server ---------------------------------------------------------------------------


def make_server(folder: Path) -> Any:
    """The MCP server for one candidates folder (not yet running)."""
    import anyio
    import anyio.to_thread
    import mcp.types as types
    from mcp.server.lowlevel import Server

    from bricksnap.designer.mcp_server import _to_mcp_content

    tools = [
        types.Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
        for t in JUDGE_TOOLS
    ]
    judging = Judging(folder)

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    one_at_a_time = anyio.Lock()

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        log.info("tool call: %s", name)
        async with one_at_a_time:
            blocks = await anyio.to_thread.run_sync(judging.call, name, args)
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
        stream=sys.stderr, level=logging.INFO, format="bricksnap-judge: %(levelname)s %(message)s"
    )
    if len(argv) != 1:
        sys.stderr.write("Usage: python -m bricksnap.designer.judge_server <candidates folder>\n")
        raise SystemExit(2)
    folder = Path(argv[0]).resolve()
    if not (folder / JUDGING_DIR / JUDGING_FILE).exists():
        sys.stderr.write(f"{folder} holds no candidates prepared for judging.\n")
        raise SystemExit(2)
    anyio.run(serve, folder)


if __name__ == "__main__":
    main()
