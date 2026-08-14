"""Thin MCP SDK adapter for the Poker8 project navigator.

The domain and safety rules live in :mod:`project_state`; this module only
maps those operations to MCP resources and tools.  It intentionally has no
filesystem API beyond the two approved document resources.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Callable, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

if __package__:
    from .project_state import ProjectRepository, ProjectStateError
else:  # pragma: no cover - exercised by the stdio entrypoint
    from project_state import ProjectRepository, ProjectStateError


LOGGER = logging.getLogger("poker8_project")


def _result(call: Callable[[], object]) -> dict[str, object]:
    """Convert domain results and expected failures to stable tool output."""
    try:
        return {"ok": True, "data": call()}
    except ProjectStateError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}


def _resource_result(call: Callable[[], object]) -> str:
    """Serialize a resource result without hiding a diagnostic failure."""
    try:
        return json.dumps(
            {"ok": True, "data": call()}, ensure_ascii=False, default=str
        )
    except ProjectStateError as exc:
        return json.dumps(
            {"ok": False, "error": {"code": exc.code, "message": str(exc)}},
            ensure_ascii=False,
        )


def _document_result(call: Callable[[], str]) -> str:
    """Return approved Markdown verbatim, or a non-secret diagnostic JSON."""
    try:
        return call()
    except ProjectStateError as exc:
        return json.dumps(
            {"ok": False, "error": {"code": exc.code, "message": str(exc)}},
            ensure_ascii=False,
        )


def build_server(root: Path) -> MCPServer:
    """Build an in-memory-capable server rooted at one validated worktree."""
    repository = ProjectRepository(root)
    # Freeze the approved names at startup.  A new untracked Markdown file
    # must not become a readable MCP resource merely by appearing later in
    # an otherwise approved directory.
    approved_specs = frozenset(repository.spec_catalogue())
    approved_plans = frozenset(repository.plan_catalogue())
    mcp = MCPServer("poker8_project")

    @mcp.resource("poker8://project/overview")
    def project_overview_resource() -> str:
        return _resource_result(repository.get_project_overview)

    @mcp.resource("poker8://project/status")
    def project_status_resource() -> str:
        return _document_result(
            lambda: repository._safe_regular_file(
                Path("docs/project/status.md")
            ).read_text(encoding="utf-8")
        )

    @mcp.resource("poker8://project/decisions")
    def project_decisions_resource() -> str:
        return _document_result(
            lambda: repository._safe_regular_file(
                Path("docs/project/decisions.md")
            ).read_text(encoding="utf-8")
        )

    @mcp.resource("poker8://specs/{name}")
    def approved_spec(name: str) -> str:
        def read() -> str:
            if name not in approved_specs:
                raise ProjectStateError("invalid_resource", f"Unknown spec: {name}")
            return repository.read_spec(name)

        return _document_result(read)

    @mcp.resource("poker8://plans/{name}")
    def approved_plan(name: str) -> str:
        def read() -> str:
            if name not in approved_plans:
                raise ProjectStateError("invalid_resource", f"Unknown plan: {name}")
            return repository.read_plan(name)

        return _document_result(read)

    read_only = ToolAnnotations(read_only_hint=True, open_world_hint=False)

    @mcp.tool(annotations=read_only)
    def get_project_overview() -> dict[str, object]:
        """Return the approved MVP focus, active work, Git summary, and next step."""
        return _result(repository.get_project_overview)

    @mcp.tool(annotations=read_only)
    def get_next_step() -> dict[str, object]:
        """Return the exact active task step without changing project status."""
        return _result(repository.get_next_step)

    @mcp.tool(annotations=read_only)
    def check_current_diff() -> dict[str, object]:
        """Compare staged, unstaged, and untracked paths with the active task."""
        return _result(repository.check_current_diff)

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    def set_active_task(
        plan: str,
        task_number: int,
        step_number: int = 1,
        state: Literal["planned", "in_progress", "awaiting_confirmation"] = "planned",
        note: str = "",
    ) -> dict[str, object]:
        """Explicitly update only the canonical project status pointer."""
        def activate() -> object:
            # Preserve the public invalid-plan contract before the domain
            # selection validator reports its lower-level parse failure.
            if plan not in repository.plan_catalogue():
                raise ProjectStateError("invalid_plan", f"Unknown plan: {plan}")
            return repository.set_active_task(
                plan, task_number, step_number, state, note
            )

        return _result(
            activate
        )

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    def confirm_task_completed(
        evidence: str, commit: str | None = None
    ) -> dict[str, object]:
        """Explicitly mark the active task complete with human evidence."""
        return _result(lambda: repository.confirm_task_completed(evidence, commit))

    @mcp.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    def record_decision(
        title: str,
        decision: str,
        rationale: str,
        supersedes: str | None = None,
    ) -> dict[str, object]:
        """Append one immutable numbered decision to the project journal."""
        return _result(
            lambda: repository.record_decision(
                title, decision, rationale, supersedes
            )
        )

    return mcp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poker8 project navigator MCP")
    parser.add_argument("--root", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    # basicConfig writes to stderr; stdout remains reserved for MCP framing.
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    build_server(args.root).run()


if __name__ == "__main__":  # pragma: no cover
    main()
