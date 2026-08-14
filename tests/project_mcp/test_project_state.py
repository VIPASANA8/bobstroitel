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
    with pytest.raises(ProjectStateError):
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
    with pytest.raises(ProjectStateError):
        repository.read_spec(name)
