from pathlib import Path
import os

import pytest

from tools.project_mcp.project_state import ProjectRepository, ProjectStateError
from tests.project_mcp.test_project_state import git


def make_project(tmp_path: Path) -> Path:
    git("init", cwd=tmp_path)
    git("config", "user.email", "tests@example.invalid", cwd=tmp_path)
    git("config", "user.name", "Poker8 Tests", cwd=tmp_path)
    specs = tmp_path / "docs" / "superpowers" / "specs"
    plans = tmp_path / "docs" / "superpowers" / "plans"
    specs.mkdir(parents=True)
    plans.mkdir(parents=True)
    for name in (
        "2026-08-14-online-network-mvp-design.md",
        "2026-08-14-poker8-product-vision.md",
    ):
        (specs / name).write_text("# Anchor\n", encoding="utf-8")
    (plans / "active.md").write_text(
        "### Task 1: Safe\n\n**Files:**\n- Create: `safe.py`\n\n"
        "- [ ] **Step 1: Work safely**\n",
        encoding="utf-8",
    )
    git("add", ".", cwd=tmp_path)
    git("commit", "-m", "fixture", cwd=tmp_path)
    return tmp_path


def test_symlinked_approved_document_is_rejected(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    target = root / "outside.md"
    target.write_text("outside", encoding="utf-8")
    link = root / "docs" / "superpowers" / "specs" / "linked.md"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    repository = ProjectRepository(root)
    with pytest.raises(ProjectStateError) as error:
        repository.spec_catalogue()
    assert error.value.code == "unsafe_path"


def test_write_boundary_rejects_source_and_preserves_atomic_original(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    repository = ProjectRepository(root)
    with pytest.raises(ProjectStateError) as forbidden:
        repository._atomic_write("app/main.py", "changed")
    assert forbidden.value.code == "write_failed"

    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    status = project_dir / "status.md"
    status.write_text("original", encoding="utf-8")

    def fail_replace(source: str | os.PathLike[str], target: str | os.PathLike[str]) -> None:
        raise OSError("forced")

    failing = ProjectRepository(root, replace=fail_replace)
    with pytest.raises(ProjectStateError) as failed:
        failing._atomic_write("docs/project/status.md", "replacement")
    assert failed.value.code == "write_failed"
    assert status.read_text(encoding="utf-8") == "original"


def test_no_public_api_reads_env_or_sqlite(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
    data = root / "data"
    data.mkdir()
    (data / "poker.sqlite3").write_bytes(b"database-secret")
    repository = ProjectRepository(root)
    assert all(".env" not in name for name in repository.spec_catalogue())
    assert all("sqlite" not in name for name in repository.plan_catalogue())


def test_corrupt_status_and_decision_ids_fail_closed(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    status = project_dir / "status.md"
    status.write_text("<!-- poker8-project-state\n{}\n-->\n", encoding="utf-8")
    decisions = project_dir / "decisions.md"
    decisions.write_text("## P8-DEC-0002 — Gap\n", encoding="utf-8")
    repository = ProjectRepository(root)
    with pytest.raises(ProjectStateError) as bad_status:
        repository.read_status()
    assert bad_status.value.code == "invalid_status"
    status.write_text(
        "<!-- poker8-project-state\n{}\n-->\n<!-- poker8-project-state\n{}\n-->\n",
        encoding="utf-8",
    )
    with pytest.raises(ProjectStateError) as duplicate_status:
        repository.read_status()
    assert duplicate_status.value.code == "invalid_status"
    with pytest.raises(ProjectStateError) as bad_log:
        repository.record_decision("Title", "Decision", "Rationale")
    assert bad_log.value.code == "invalid_decision_log"


def test_symlinked_manager_target_is_rejected(tmp_path: Path) -> None:
    root = make_project(tmp_path)
    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    outside = root / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    link = project_dir / "status.md"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    repository = ProjectRepository(root)
    with pytest.raises(ProjectStateError) as error:
        repository._atomic_write("docs/project/status.md", "replacement")
    assert error.value.code == "write_failed"
    assert outside.read_text(encoding="utf-8") == "outside"
