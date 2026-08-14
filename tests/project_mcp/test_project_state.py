import subprocess
from pathlib import Path

import pytest

from tools.project_mcp.project_state import ProjectRepository, ProjectStateError


ANCHORS = (
    "2026-08-14-online-network-mvp-design.md",
    "2026-08-14-poker8-product-vision.md",
)


def git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    git("init", cwd=tmp_path)
    specs = tmp_path / "docs" / "superpowers" / "specs"
    plans = tmp_path / "docs" / "superpowers" / "plans"
    specs.mkdir(parents=True)
    plans.mkdir(parents=True)
    for name in ANCHORS:
        (specs / name).write_text(f"# {name}\n", encoding="utf-8")
    (specs / "approved.md").write_text("approved\n", encoding="utf-8")
    (plans / "active.md").write_text("active plan\n", encoding="utf-8")
    return tmp_path


def test_non_git_root_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ProjectStateError, match="Git worktree"):
        ProjectRepository(tmp_path)


def test_symlinked_document_parent_is_rejected(project_root: Path, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-specs"
    outside.mkdir()
    specs = project_root / "docs" / "superpowers" / "specs"
    original = project_root / "docs" / "superpowers" / "specs-real"
    specs.rename(original)
    try:
        specs.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        original.rename(specs)
        pytest.skip(f"symlinks unavailable: {exc}")
    with pytest.raises(ProjectStateError):
        ProjectRepository(project_root)


def test_catalogue_and_reads(project_root: Path) -> None:
    repository = ProjectRepository(project_root)
    assert repository.spec_catalogue() == sorted([*ANCHORS, "approved.md"])
    assert repository.plan_catalogue() == ["active.md"]
    assert repository.read_spec("approved.md") == "approved\n"
    assert repository.read_plan("active.md") == "active plan\n"


@pytest.mark.parametrize("name", ["../../.env", "../spec.md", "/tmp/spec.md", "unknown.md", "active.txt"])
def test_unknown_and_traversal_names_are_rejected(project_root: Path, name: str) -> None:
    repository = ProjectRepository(project_root)
    with pytest.raises(ProjectStateError) as error:
        repository.read_spec(name)
    assert error.value.code == "invalid_resource"


def test_selection_unknown_plan_is_invalid_plan(project_root: Path) -> None:
    repository = ProjectRepository(project_root)
    with pytest.raises(ProjectStateError) as error:
        repository.set_active_task("missing.md", 1)
    assert error.value.code == "invalid_plan"


def test_set_active_task_fails_closed_without_status(project_root: Path) -> None:
    repository = ProjectRepository(project_root)
    (project_root / "docs" / "superpowers" / "plans" / "active.md").write_text(
        "### Task 1: Work\n\n- [ ] **Step 1: Start**\n", encoding="utf-8"
    )
    (project_root / "docs" / "project").mkdir()
    with pytest.raises(ProjectStateError) as error:
        repository.set_active_task("active.md", 1)
    assert error.value.code == "invalid_status"


def test_completed_status_has_no_next_task_recommendation(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text("### Task 1: Done\n\n**Files:**\n- Modify: `x.py`\n\n- [x] **Step 1: Finish**\n", encoding="utf-8")
    repository = ProjectRepository(project_root)
    repository.initialize_status("active.md", 1, 1, "abc")
    status = repository.read_status(); status["state"] = "completed"
    repository._atomic_write("docs/project/status.md", repository._render_status(status))
    assert repository.get_next_step()["recommendation"] == "no next task"


def test_completed_state_cannot_be_activated(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text("### Task 1: Done\n\n- [ ] **Step 1: Finish**\n", encoding="utf-8")
    repository = ProjectRepository(project_root)
    repository.initialize_status("active.md", 1, 1, "abc")
    with pytest.raises(ProjectStateError) as error:
        repository.set_active_task("active.md", 1, state="completed")
    assert error.value.code == "invalid_state"


def test_status_schema_version_requires_exact_integer(project_root: Path) -> None:
    repository = ProjectRepository(project_root)
    (project_root / "docs" / "superpowers" / "plans" / "active.md").write_text("### Task 1: Work\n\n- [ ] **Step 1: Start**\n", encoding="utf-8")
    repository.initialize_status("active.md", 1, 1, "abc")
    for value in (True, 1.0):
        repository.initialize_status("active.md", 1, 1, "abc")
        status = repository.read_status(); status["schema_version"] = value
        repository._atomic_write("docs/project/status.md", repository._render_status(status))
        with pytest.raises(ProjectStateError) as error:
            repository.read_status()
        assert error.value.code == "invalid_status"


def test_plan_files_preserve_declaration_order(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text("### Task 1: Config\n\n**Files:**\n- Create: `online/config.py`\n- Test: `tests/online/test_config.py`\n\n- [ ] **Step 1: Build**\n", encoding="utf-8")
    task = ProjectRepository(project_root).parse_plan("active.md")[0]
    assert task.files == ("online/config.py", "tests/online/test_config.py")
