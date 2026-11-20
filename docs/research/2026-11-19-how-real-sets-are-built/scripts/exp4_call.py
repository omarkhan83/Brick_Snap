"""Experiment 4: call one of the AI builder's tools by hand, as the AI builder would.

    uv run python exp4_call.py prepare WORK START.ldr [REFERENCE.png ...]
        make the work folder WORK from START.ldr (moved to x = 0, checked as attempt 0),
        exactly as ``bricksnap.lab.run`` does for ``--start``, with the guide switched on
    uv run python exp4_call.py WORK TOOL 'JSON ARGUMENTS'
        one call of ``bricksnap.lab.tools.call_tool``; prints the text it returns and saves
        each picture it returns as WORK/shown/NNN-TOOL.png (the path is printed)

Every call is logged by the tools themselves in WORK/calls.jsonl, which is how the tool calls
per face are counted.
"""

import base64
import json
import sys
from pathlib import Path

from bricksnap.lab.run import prepare
from bricksnap.lab.tools import call_tool


def main() -> None:
    if sys.argv[1] == "prepare":
        work, start = Path(sys.argv[2]), Path(sys.argv[3])
        refs = [Path(p) for p in sys.argv[4:]]
        prepare(work, "tools", 99, refs, start=start, guide=True)
        print(f"prepared {work}")
        return
    work, tool = Path(sys.argv[1]), sys.argv[2]
    args = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
    shown = work / "shown"
    shown.mkdir(exist_ok=True)
    n = len(list(shown.glob("*.png")))
    for block in call_tool(work, tool, args):
        if block.get("type") == "text":
            print(block["text"])
        elif block.get("type") == "image":
            out = shown / f"{n:03d}-{tool}.png"
            out.write_bytes(base64.b64decode(block["data"]))
            print(f"[picture: {out}]")
            n += 1


if __name__ == "__main__":
    main()
