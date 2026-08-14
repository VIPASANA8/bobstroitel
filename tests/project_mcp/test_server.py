from pathlib import Path
import subprocess

import pytest
from mcp import Client

from tests.project_mcp.test_project_state import git
from tests.project_mcp.test_safety import make_project
from tools.project_mcp.project_state import ProjectRepository
from tools.project_mcp.server import build_server


@pytest.fixture
def anyio_backend():
    return "asyncio"


def ready_project(tmp_path: Path) -> Path:
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
    git("add", "docs/project", cwd=root)
    git("commit", "-m", "manager fixture", cwd=root)
    return root


@pytest.mark.anyio
async def test_server_lists_exact_tools_and_reads_resources(tmp_path: Path):
    root = ready_project(tmp_path)
    async with Client(build_server(root), raise_exceptions=True) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "get_project_overview",
            "get_next_step",
            "check_current_diff",
            "set_active_task",
            "confirm_task_completed",
            "record_decision",
        }
        resources = await client.list_resources()
        assert {str(resource.uri) for resource in resources.resources} == {
            "poker8://project/overview",
            "poker8://project/status",
            "poker8://project/decisions",
        }
        templates = await client.list_resource_templates()
        assert {template.uri_template for template in templates.resource_templates} == {
            "poker8://specs/{name}",
            "poker8://plans/{name}",
        }
        overview = await client.call_tool("get_project_overview", {})
        assert overview.structured_content["ok"] is True
        assert overview.structured_content["data"]["active_task"] == 1
        plan = await client.read_resource("poker8://plans/active.md")
        assert "### Task 1: Safe" in plan.contents[0].text


@pytest.mark.anyio
async def test_manager_tool_errors_are_structured_and_do_not_write_source(
    tmp_path: Path,
):
    root = ready_project(tmp_path)
    before = git("status", "--porcelain=v1", cwd=root)
    async with Client(build_server(root), raise_exceptions=True) as client:
        result = await client.call_tool(
            "set_active_task",
            {
                "plan": "../../.env",
                "task_number": 1,
                "step_number": 1,
                "state": "planned",
            },
        )
        assert result.structured_content == {
            "ok": False,
            "error": {"code": "invalid_plan", "message": "Unknown plan: ../../.env"},
        }
    assert git("status", "--porcelain=v1", cwd=root) == before


@pytest.mark.anyio
async def test_valid_manager_tool_changes_only_status(tmp_path: Path):
    root = ready_project(tmp_path)
    async with Client(build_server(root), raise_exceptions=True) as client:
        result = await client.call_tool(
            "set_active_task",
            {
                "plan": "active.md",
                "task_number": 1,
                "step_number": 1,
                "state": "in_progress",
            },
        )
        assert result.structured_content["ok"] is True
    changed = subprocess.run(
        ["git", "diff", "--name-only"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert changed == "docs/project/status.md"


@pytest.mark.anyio
async def test_resource_catalogue_is_frozen_and_never_reads_new_markdown(
    tmp_path: Path,
):
    root = ready_project(tmp_path)
    (root / "docs" / "superpowers" / "specs" / "secret.md").write_text(
        "TOKEN=must-not-be-read", encoding="utf-8"
    )
    server = build_server(root)
    async with Client(server, raise_exceptions=True) as client:
        result = await client.read_resource("poker8://specs/secret.md")
    payload = result.contents[0].text
    assert "TOKEN=must-not-be-read" not in payload
    assert '"code": "invalid_resource"' in payload
