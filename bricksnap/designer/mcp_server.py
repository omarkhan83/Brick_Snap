"""Serve the designer's tools over MCP (stdio) for one project.

    python -m bricksnap.designer.mcp_server /path/to/project

CONTRACT (tests go in tests/test_designer_mcp.py)

- An MCP server named "bricksnap" using the ``mcp`` Python SDK, speaking stdio. It exposes
  exactly the tools in ``bricksnap.designer.tools.TOOLS`` with their names, descriptions and
  input schemas unchanged, so headless Claude Code sees them as ``mcp__bricksnap__describe``
  and so on.
- A tool call is passed to ``bricksnap.designer.tools.call_tool`` and its content blocks are
  converted to MCP text and image content.
- Nothing is printed to standard output except the protocol (logging goes to standard error).
- The test starts the server as a subprocess with the SDK's stdio client, lists the tools,
  and calls ``describe`` on a small project.

Implementation notes
--------------------
- Uses the SDK's low-level ``Server`` so the input schemas go out exactly as written in
  ``TOOLS`` (the high-level helpers would derive them from Python signatures).
- ``call_tool`` is synchronous and can take a second on a large model, so it runs in a worker
  thread to keep the protocol responsive. Calls run one at a time (one lock per server): two
  calls that overlapped would read and write the same project files, and an edit could be
  lost or a half-written design read. The model often sends several calls in one message.
- The types come from ``mcp.types``; the low-level ``Server(name, on_list_tools=...,
  on_call_tool=...)`` API used here is the one in mcp 2.x.
- A result whose only block starts with "ERROR:" is sent with ``isError`` set, so the model
  sees it as a failed call; the text says what to fix.
- While serving, the SDK points file descriptor 1 at standard error, so a stray print from a
  library cannot corrupt the protocol.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

SERVER_NAME = "bricksnap"

log = logging.getLogger("bricksnap.designer.mcp_server")


def _to_mcp_content(blocks: list[dict[str, Any]]) -> list[Any]:
    import mcp.types as types

    content: list[Any] = []
    for b in blocks:
        if b.get("type") == "image":
            content.append(
                types.ImageContent(
                    type="image", data=b["data"], mime_type=b.get("media_type", "image/png")
                )
            )
        else:
            content.append(types.TextContent(type="text", text=str(b.get("text", ""))))
    return content


def make_server(project_path: Path) -> Any:
    """The MCP server for one project (not yet running)."""
    import anyio
    import anyio.to_thread
    import mcp.types as types
    from mcp.server.lowlevel import Server

    from bricksnap.designer.tools import TOOLS, call_tool

    tools = [
        types.Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
        for t in TOOLS
    ]

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=tools)

    one_at_a_time = anyio.Lock()

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        log.info("tool call: %s", name)
        async with one_at_a_time:
            blocks = await anyio.to_thread.run_sync(call_tool, project_path, name, args)
        is_error = (
            len(blocks) == 1
            and blocks[0].get("type") == "text"
            and str(blocks[0].get("text", "")).startswith("ERROR:")
        )
        return types.CallToolResult(content=_to_mcp_content(blocks), is_error=is_error)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def serve(project_path: Path) -> None:
    from mcp.server.stdio import stdio_server

    server = make_server(project_path)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main(argv: list[str] | None = None) -> None:
    import anyio

    argv = sys.argv[1:] if argv is None else argv
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="bricksnap-mcp: %(levelname)s %(message)s"
    )
    if len(argv) != 1:
        sys.stderr.write("Usage: python -m bricksnap.designer.mcp_server <project folder>\n")
        raise SystemExit(2)
    project_path = Path(argv[0]).resolve()
    if not (project_path / "project.json").exists():
        sys.stderr.write(f"{project_path} is not a BrickSnap project (no project.json in it).\n")
        raise SystemExit(2)
    anyio.run(serve, project_path)


if __name__ == "__main__":
    main()
