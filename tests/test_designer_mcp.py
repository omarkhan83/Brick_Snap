"""Tests for the designer's MCP server (bricksnap/designer/mcp_server.py).

The server is started as a real subprocess and spoken to with the mcp SDK's stdio client,
exactly as headless Claude Code would.
"""

from __future__ import annotations

import base64
import io
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from mcp import ClientSession, StdioServerParameters, stdio_client
from PIL import Image

from bricksnap.designer.tools import TOOLS
from bricksnap.pipeline import create_project, rebuild

BRIEF = {
    "object": "A chess pawn, standing upright.",
    "features": ["a round head", "a wide base"],
    "plan": "Keep the head round.",
    "colours": [71, 4],
    "finish": "Studs everywhere.",
}


@pytest.fixture(scope="module")
def project_path(tmp_path_factory, pawn_path: Path, catalog) -> Path:
    root = tmp_path_factory.mktemp("designer-mcp")
    project = create_project(pawn_path, studs=6, directory=root, catalog=catalog)
    rebuild(project, catalog=catalog)
    return project.path


def run_session(project_path: Path, calls: list[tuple[str, dict]]):
    """Start the server, list its tools, make the calls; return (tools, results)."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "bricksnap.designer.mcp_server", str(project_path)],
    )

    async def go():
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            results = [await session.call_tool(name, args) for name, args in calls]
            return listed.tools, results

    return anyio.run(go)


def test_server_lists_tools_and_answers_calls(project_path: Path):
    op = {"op": "paint", "shape": {"type": "box", "min": [0, 0, 0], "max": [20, 20, 0]}, "color": 4}
    tools, results = run_session(
        project_path,
        [
            ("describe", {}),
            ("render", {"views": ["front", "top"]}),
            ("apply_ops", {"ops": [op]}),
            ("brief", BRIEF),
            ("apply_ops", {"ops": [op]}),
            ("explode", {}),
        ],
    )

    # exactly our tools, unchanged
    assert [t.name for t in tools] == [t["name"] for t in TOOLS]
    for listed, ours in zip(tools, TOOLS, strict=True):
        assert listed.description == ours["description"]
        assert listed.input_schema == ours["input_schema"]

    describe, render, refused, brief, apply, unknown = results

    assert not describe.is_error
    assert [c.type for c in describe.content] == ["text"]
    assert "cells" in describe.content[0].text and "COLOURS AVAILABLE" in describe.content[0].text

    assert not render.is_error
    assert [c.type for c in render.content] == ["image", "text"]
    image = render.content[0]
    assert image.mime_type == "image/png"
    img = Image.open(io.BytesIO(base64.b64decode(image.data)))
    assert img.width > 200
    assert "Top row" in render.content[1].text

    # apply_ops refuses until there is a brief, and the refusal is a failed call
    assert refused.is_error
    assert refused.content[0].text.startswith("ERROR: write the brief first")

    assert not brief.is_error
    assert brief.content[0].text.startswith("Brief saved.")

    assert not apply.is_error
    assert "1 of 1 operations applied" in apply.content[0].text

    assert unknown.is_error
    assert unknown.content[0].text.startswith("ERROR:")


def test_server_refuses_a_folder_that_is_not_a_project(tmp_path: Path):
    proc = subprocess.run(
        [sys.executable, "-m", "bricksnap.designer.mcp_server", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "not a BrickSnap project" in proc.stderr


def test_server_needs_one_argument():
    proc = subprocess.run(
        [sys.executable, "-m", "bricksnap.designer.mcp_server"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "Usage" in proc.stderr


def test_overlapping_calls_do_not_corrupt_each_other(project_path: Path, tmp_path: Path):
    # a client may run several calls at once; each edit must land and be counted once
    import shutil

    from bricksnap.project import Project

    copy = tmp_path / "proj"
    shutil.copytree(project_path, copy)
    project = Project(copy)
    project.meta["brief"] = BRIEF
    project.save_meta()
    before = len(Project(copy).load_design().log)
    n = 8
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "bricksnap.designer.mcp_server", str(copy)]
    )

    def op(i: int) -> dict:
        return {
            "op": "add",
            "shape": {"type": "box", "min": [i, 0, 20], "max": [i, 0, 20]},
            "color": 4,
        }

    async def go():
        results: list = [None] * n
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()

            async def call(i: int) -> None:
                results[i] = await session.call_tool("apply_ops", {"ops": [op(i)]})

            async with anyio.create_task_group() as tg:
                for i in range(n):
                    tg.start_soon(call, i)
        return results

    results = anyio.run(go)
    texts = [r.content[0].text for r in results]
    assert not any(r.is_error for r in results), texts
    assert all("1 of 1 operations applied" in t for t in texts), texts
    # every call saw the edits before it, so the reported log sizes are all different
    sizes = sorted(int(t.split(" edit")[0].rsplit(" ", 1)[1]) for t in texts)
    assert sizes == list(range(before + 1, before + n + 1))
    design = Project(copy).load_design()
    assert len(design.log) == before + n
    assert int((design.colors[:n, 0, 20] == 4).sum()) == n
