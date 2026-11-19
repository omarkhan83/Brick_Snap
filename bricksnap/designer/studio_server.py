"""Serve one studio pass's tools over MCP (stdio) for one project.

    python -m bricksnap.designer.studio_server /path/to/project --tools describe,render \
        --ops add,remove,paint

CONTRACT (tests go in tests/test_studio.py)

- An MCP server named "bricksnap" (as the designer's, so the runner's ``--allowedTools
  mcp__bricksnap`` and its check that the server started are unchanged) offering exactly the
  tools named by ``--tools``, as ``studio_tools.tool_definitions`` defines them, with
  apply_ops limited to the operations named by ``--ops``. A pass's tools are therefore
  enforced by the server: a tool it was not given is neither listed nor answered.
- Calls go to one ``studio_tools.Session`` for the life of the server (one session of the
  model), one at a time, in a worker thread, as in ``mcp_server``; a result whose only block
  starts with "ERROR:" is sent with ``isError`` set.
- Nothing is printed to standard output except the protocol.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from bricksnap.designer.mcp_server import SERVER_NAME, _to_mcp_content

log = logging.getLogger("bricksnap.designer.studio_server")


def make_server(project_path: Path, tools: tuple[str, ...], ops: tuple[str, ...]) -> Any:
    """The MCP server for one pass on one project (not yet running)."""
    import anyio
    import anyio.to_thread
    import mcp.types as types
    from mcp.server.lowlevel import Server

    from bricksnap.designer.studio_tools import Session, tool_definitions

    listed = [
        types.Tool(name=t["name"], description=t["description"], input_schema=t["input_schema"])
        for t in tool_definitions(tools, ops)
    ]
    session = Session(project_path, tools, ops)

    async def on_list_tools(ctx: Any, params: Any) -> types.ListToolsResult:
        return types.ListToolsResult(tools=listed)

    one_at_a_time = anyio.Lock()

    async def on_call_tool(ctx: Any, params: types.CallToolRequestParams) -> types.CallToolResult:
        name = params.name
        args = dict(params.arguments or {})
        log.info("tool call: %s", name)
        async with one_at_a_time:
            blocks = await anyio.to_thread.run_sync(session.call, name, args)
        is_error = (
            len(blocks) == 1
            and blocks[0].get("type") == "text"
            and str(blocks[0].get("text", "")).startswith("ERROR:")
        )
        return types.CallToolResult(content=_to_mcp_content(blocks), is_error=is_error)

    return Server(SERVER_NAME, on_list_tools=on_list_tools, on_call_tool=on_call_tool)


async def serve(project_path: Path, tools: tuple[str, ...], ops: tuple[str, ...]) -> None:
    from mcp.server.stdio import stdio_server

    server = make_server(project_path, tools, ops)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def _names(text: str) -> tuple[str, ...]:
    return tuple(n for n in (p.strip() for p in text.split(",")) if n)


def main(argv: list[str] | None = None) -> None:
    import anyio

    from bricksnap.design import OPS
    from bricksnap.designer.studio_tools import STUDIO_TOOL_NAMES

    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="bricksnap-studio: %(levelname)s %(message)s"
    )
    ap = argparse.ArgumentParser(prog="python -m bricksnap.designer.studio_server")
    ap.add_argument("project")
    ap.add_argument("--tools", required=True)
    ap.add_argument("--ops", default="")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    tools, ops = _names(args.tools), _names(args.ops)
    bad = [t for t in tools if t not in STUDIO_TOOL_NAMES] + [o for o in ops if o not in OPS]
    if bad or not tools or ("apply_ops" in tools and not ops):
        sys.stderr.write(f"Unknown or missing tools or operations: {', '.join(bad) or 'none'}\n")
        raise SystemExit(2)
    project_path = Path(args.project).resolve()
    if not (project_path / "project.json").exists():
        sys.stderr.write(f"{project_path} is not a BrickSnap project (no project.json in it).\n")
        raise SystemExit(2)
    anyio.run(serve, project_path, tools, ops or OPS)


if __name__ == "__main__":
    main()
