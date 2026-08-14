"""Safe access to the project specifications and plans."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path


class ProjectStateError(Exception):
    """A validation or document-access failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ProjectRepository:
    """Validated, read-only boundary around approved project documents."""

    _ANCHORS = (
        "docs/superpowers/specs/2026-08-14-online-network-mvp-design.md",
        "docs/superpowers/specs/2026-08-14-poker8-product-vision.md",
    )

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        if not self.root.is_dir():
            raise ProjectStateError("invalid_root", "project root is not a directory")
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=self.root,
                shell=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectStateError("not_git_repository", "project root is not a Git work tree") from exc
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise ProjectStateError("not_git_repository", "project root is not a Git work tree")
        for relative in self._ANCHORS:
            path = self.root / relative
            if not self._is_regular_file(path):
                raise ProjectStateError("missing_anchor", f"required anchor is missing or unsafe: {relative}")

    @staticmethod
    def _is_regular_file(path: Path) -> bool:
        try:
            return not path.is_symlink() and stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
        except OSError:
            return False

    def _catalogue(self, relative_dir: str) -> list[str]:
        directory = self.root / relative_dir
        if not directory.is_dir() or directory.is_symlink():
            raise ProjectStateError("invalid_document_directory", f"document directory is unavailable: {relative_dir}")
        names: list[str] = []
        try:
            entries = list(directory.iterdir())
        except OSError as exc:
            raise ProjectStateError("document_catalogue_failed", f"cannot inspect {relative_dir}") from exc
        for entry in entries:
            if entry.suffix != ".md":
                continue
            if not self._is_regular_file(entry):
                raise ProjectStateError("unsafe_document", f"document is not a regular file: {entry.name}")
            names.append(entry.name)
        return sorted(names)

    def spec_catalogue(self) -> list[str]:
        return self._catalogue("docs/superpowers/specs")

    def plan_catalogue(self) -> list[str]:
        return self._catalogue("docs/superpowers/plans")

    def _read(self, relative_dir: str, name: str) -> str:
        if not isinstance(name, str) or not name or name != Path(name).name or Path(name).suffix != ".md":
            raise ProjectStateError("invalid_document_name", f"invalid document name: {name!r}")
        directory = self.root / relative_dir
        candidate = directory / name
        try:
            candidate_resolved = candidate.resolve(strict=False)
            if candidate_resolved.parent != directory.resolve() or not self._is_regular_file(candidate):
                raise ProjectStateError("unsafe_document", f"document is not an approved regular file: {name}")
            return candidate.read_text(encoding="utf-8")
        except ProjectStateError:
            raise
        except (OSError, UnicodeError) as exc:
            raise ProjectStateError("document_not_found", f"document is unavailable: {name}") from exc

    def read_spec(self, name: str) -> str:
        return self._read("docs/superpowers/specs", name)

    def read_plan(self, name: str) -> str:
        return self._read("docs/superpowers/plans", name)
