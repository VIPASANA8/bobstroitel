"""Smoke-test the real stdio transport, not only the in-memory SDK adapter."""

from pathlib import Path
import subprocess
import sys

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from tests.project_mcp.test_project_state import git
from tests.project_mcp.test_safety import make_project
from tools.project_mcp.project_state import ProjectRepository


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_actual_stdio_server_lists_and_calls_tools(tmp_path: Path):
    root = make_project(tmp_path)
    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    repository = ProjectRepository(root)
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    repository.initialize_status("active.md", 1, 1, commit)
    (project_dir / "decisions.md").write_text(
        "# Poker8 Project Decisions\n\nEntries are append-only.\n",
        encoding="utf-8",
    )

    server_path = (
        Path(__file__).parents[2] / "tools" / "project_mcp" / "server.py"
    ).resolve()
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path), "--root", str(root.resolve())],
    )

    # stdio_client owns the child process and the Client owns the MCP
    # initialize/close handshake.  Any accidental stdout from the server is
    # therefore a framing error and fails this test.
    async with Client(stdio_client(parameters), raise_exceptions=True) as client:
        tools = await client.list_tools()
        assert "get_project_overview" in {tool.name for tool in tools.tools}
        result = await client.call_tool("get_project_overview", {})
        assert result.structured_content["ok"] is True
