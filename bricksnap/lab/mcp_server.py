"""Serve the free-build lab's tools over MCP (stdio) for one work folder (research prototype).

    python -m bricksnap.lab.mcp_server /path/to/work-folder

Like ``bricksnap.designer.mcp_server``: the low-level SDK ``Server`` named "bricksnap" (so the
runner's ``--allowedTools mcp__bricksnap`` and its started-server check apply unchanged), the
tools of ``bricksnap.lab.tools.tools_for(folder)`` with their descriptions and schemas exactly
as written, one call at a time in a worker thread, a result whose only block starts with
"ERROR:" sent with ``isError`` set, and nothing on standard output but the protocol.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "bricksnap"

log = logging.getLogger("bricksnap.lab.mcp_server")


def make_server(folder: Path) -> Any:
    import anyio
    import anyio.to_thread
    import mcp.types as types
    from mcp.server.lowlevel import Server

    from bricksnap.designer.mcp_server import _to_mcp_content
    from bricksnap.lab.tools import call_tool, tools_for

    tools = [
        types.Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
        for t in tools_for(folder)
    ]

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    one_at_a_time = anyio.Lock()

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        log.info("tool call: %s", name)
        async with one_at_a_time:
            blocks = await anyio.to_thread.run_sync(call_tool, folder, name, args)
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
        stream=sys.stderr, level=logging.INFO, format="bricksnap-lab: %(levelname)s %(message)s"
    )
    if len(argv) != 1:
        sys.stderr.write("Usage: python -m bricksnap.lab.mcp_server <work folder>\n")
        raise SystemExit(2)
    folder = Path(argv[0]).resolve()
    if not folder.is_dir():
        sys.stderr.write(f"{folder} is not a folder.\n")
        raise SystemExit(2)
    anyio.run(serve, folder)


if __name__ == "__main__":
    main()
