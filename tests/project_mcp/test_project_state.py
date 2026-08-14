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


def test_read_status_rejects_stale_selection(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text("### Task 1: Work\n\n- [ ] **Step 1: Start**\n", encoding="utf-8")
    repository = ProjectRepository(project_root)
    repository.initialize_status("active.md", 1, 1, "abc")
    status = repository.read_status(); status["active_step"] = 99
    repository._atomic_write("docs/project/status.md", repository._render_status(status))
    with pytest.raises(ProjectStateError) as error:
        repository.read_status()
    assert error.value.code == "invalid_status"


def test_completed_next_task_without_steps_is_safe(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text("### Task 1: Done\n\n- [ ] **Step 1: Finish**\n\n### Task 2: Placeholder\n", encoding="utf-8")
    repository = ProjectRepository(project_root)
    repository.initialize_status("active.md", 1, 1, "abc")
    status = repository.read_status(); status["state"] = "completed"
    repository._atomic_write("docs/project/status.md", repository._render_status(status))
    result = repository.get_next_step()
    assert result["task"] == 2 and result["step"] is None


def _ready_repository(project_root: Path) -> ProjectRepository:
    (project_root / "docs" / "superpowers" / "plans" / "active.md").write_text(
        "### Task 1: Work\n\n- [ ] **Step 1: Start**\n", encoding="utf-8"
    )
    repository = ProjectRepository(project_root)
    repository.initialize_status("active.md", 1, 1, "")
    return repository


def test_record_decision_assigns_sequential_ids_and_supersedes(project_root: Path) -> None:
    repository = _ready_repository(project_root)
    first = repository.record_decision("Boundary", "Keep writes narrow", "Safety")
    second = repository.record_decision("Refinement", "Use atomic writes", "Integrity", supersedes=first["id"])
    assert first["id"] == "P8-DEC-0002"
    assert second["id"] == "P8-DEC-0003"
    assert second["supersedes"] == first["id"]


@pytest.mark.parametrize("args", [("", "d", "r"), ("t", "", "r"), ("t", "d", "")])
def test_record_decision_rejects_empty_fields(project_root: Path, args: tuple[str, str, str]) -> None:
    with pytest.raises(ProjectStateError) as error:
        _ready_repository(project_root).record_decision(*args)
    assert error.value.code == "invalid_decision"


def test_record_decision_rejects_unknown_supersedes(project_root: Path) -> None:
    with pytest.raises(ProjectStateError) as error:
        _ready_repository(project_root).record_decision("t", "d", "r", supersedes="P8-DEC-9999")
    assert error.value.code == "invalid_decision"


def test_malformed_decision_log_fails_closed_without_write(project_root: Path) -> None:
    repository = _ready_repository(project_root)
    path = project_root / "docs" / "project" / "decisions.md"
    original = "# Decisions\n\nP8-DEC-0002\n"
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ProjectStateError) as error:
        repository.record_decision("t", "d", "r")
    assert error.value.code == "invalid_decision_log"
    assert path.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("original", [
    "# Decisions\n\n## P8-DEC-XYZ: Broken\nDecision: d\nRationale: r\n",
    "# Decisions\n\n## P8-DEC-0001 — Boundary\n- Supersedes: P8-DEC-0099\n### Decision\nD\n### Rationale\nR\n",
    "# Decisions\n\n## P8-DEC-0001: Boundary\n- Supersedes: P8-DEC-XYZ\nDecision: D\nRationale: R\n",
])
def test_decision_log_malformed_heading_or_bullet_reference_fails_closed(project_root: Path, original: str) -> None:
    repository = _ready_repository(project_root)
    path = project_root / "docs" / "project" / "decisions.md"
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ProjectStateError) as error:
        repository.record_decision("t", "d", "r")
    assert error.value.code == "invalid_decision_log"
    assert path.read_text(encoding="utf-8") == original


def test_record_decision_preserves_crlf_existing_bytes(project_root: Path) -> None:
    repository = _ready_repository(project_root)
    path = project_root / "docs" / "project" / "decisions.md"
    original = "# Decisions\r\n\r\n## P8-DEC-0001: Boundary\r\nDecision: D\r\nRationale: R\r\n"
    path.write_bytes(original.encode("utf-8"))
    repository.record_decision("Next", "D2", "R2")
    result = path.read_bytes().decode("utf-8")
    assert result.startswith(original)
    assert "\r\n## P8-DEC-0002 — Next\r\n" in result


def test_completion_requires_evidence(project_root: Path) -> None:
    with pytest.raises(ProjectStateError) as error:
        _ready_repository(project_root).confirm_task_completed(" ")
    assert error.value.code == "invalid_evidence"
    with pytest.raises(ProjectStateError) as error:
        _ready_repository(project_root).confirm_task_completed(["tests"])
    assert error.value.code == "invalid_evidence"


def test_completion_rejects_invalid_commit_ref(project_root: Path) -> None:
    with pytest.raises(ProjectStateError) as error:
        _ready_repository(project_root).confirm_task_completed("tests", commit="not-a-commit")
    assert error.value.code == "invalid_commit"


def test_completion_accepts_local_commit_and_updates_status(project_root: Path) -> None:
    git("config", "user.email", "test@example.com", cwd=project_root)
    git("config", "user.name", "Test", cwd=project_root)
    (project_root / "seed.txt").write_text("seed", encoding="utf-8")
    git("add", ".", cwd=project_root); git("commit", "-m", "seed", cwd=project_root)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, check=True, capture_output=True, text=True).stdout.strip()
    repository = _ready_repository(project_root)
    result = repository.confirm_task_completed("pytest", commit=commit)
    assert result["state"] == "completed" and result["evidence"] == ["pytest"] and result["last_confirmed_commit"] == commit


def test_completion_unknown_commit_leaves_status_unchanged(project_root: Path) -> None:
    repository = _ready_repository(project_root)
    before = repository.read_status()
    with pytest.raises(ProjectStateError) as error:
        repository.confirm_task_completed("tests", commit="0123456")
    assert error.value.code == "invalid_commit"
    assert repository.read_status() == before


def _initialize_active_status(repository: ProjectRepository, root: Path) -> None:
    git("add", "docs/superpowers", cwd=root)
    git("commit", "-m", "plan fixture", cwd=root)
    (root / "docs" / "project").mkdir(exist_ok=True)
    repository.initialize_status("active.md", 1, 1, "")
    git("add", "docs/project/status.md", cwd=root)
    git("commit", "-m", "status fixture", cwd=root)


def test_alignment_covers_staged_unstaged_blocked_and_ignored(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text(
        "### Task 1: Work\n\n**Files:**\n- Create: `online/config.py`\n\n"
        "- [ ] **Step 1: Start**\n",
        encoding="utf-8",
    )
    repository = ProjectRepository(project_root)
    _initialize_active_status(repository, project_root)
    online = project_root / "online"
    online.mkdir()
    config = online / "config.py"
    config.write_text("VALUE = 1\n", encoding="utf-8")
    git("add", "online/config.py", cwd=project_root)
    assert repository.check_current_diff()["result"] == "aligned"

    (project_root / "README.md").write_text("outside task\n", encoding="utf-8")
    assert repository.check_current_diff()["result"] == "warning"

    git("add", "README.md", cwd=project_root)
    git("commit", "-m", "tracked fixture", cwd=project_root)
    config.write_text("def deposit_endpoint():\n    return 'USDT'\n", encoding="utf-8")
    result = repository.check_current_diff()
    assert result["result"] == "blocked"
    assert result["blocked_evidence"]
    assert result["blocked_evidence"][0]["path"] == "online/config.py"

    data = project_root / "data"
    data.mkdir()
    (data / "poker_trainer.sqlite3").write_bytes(b"do not inspect")
    (data / "poker_trainer.sqlite3-wal").write_bytes(b"do not inspect")
    superpowers = project_root / ".superpowers"
    superpowers.mkdir()
    (superpowers / "marker").write_text("browser", encoding="utf-8")
    result = repository.check_current_diff()
    assert sorted(result["ignored_user_changes"]) == [
        ".superpowers/", "data/poker_trainer.sqlite3", "data/poker_trainer.sqlite3-wal",
    ]


def test_untracked_forbidden_text_is_reported_but_never_opened(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text(
        "### Task 1: Work\n\n**Files:**\n- Create: `online/config.py`\n\n"
        "- [ ] **Step 1: Start**\n",
        encoding="utf-8",
    )
    repository = ProjectRepository(project_root)
    _initialize_active_status(repository, project_root)
    untracked = project_root / "online" / "config.py"
    untracked.parent.mkdir()
    untracked.write_text("deposit_endpoint = 'must not be inspected'\n", encoding="utf-8")
    result = repository.check_current_diff()
    assert result["result"] == "warning"
    assert result["blocked_evidence"] == []


def test_project_overview_contains_alignment_and_next_step(project_root: Path) -> None:
    plan = project_root / "docs" / "superpowers" / "plans" / "active.md"
    plan.write_text(
        "### Task 1: Work\n\n**Files:**\n- Create: `online/config.py`\n\n"
        "- [ ] **Step 1: Start**\n",
        encoding="utf-8",
    )
    repository = ProjectRepository(project_root)
    _initialize_active_status(repository, project_root)
    overview = repository.get_project_overview()
    assert overview["active_plan"] == "active.md"
    assert overview["active_task"] == 1
    assert overview["task_title"] == "Work"
    assert overview["git"]["result"] == "warning"
    assert overview["next"]["step"] == 1
