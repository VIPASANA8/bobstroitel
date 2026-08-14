"""Safe access to the project specifications and plans."""

from __future__ import annotations

import stat
import subprocess
import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class ProjectStateError(RuntimeError):
    """A validation or document-access failure."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

@dataclass(frozen=True)
class PlanStep:
    number: int
    title: str
    body: str
    checked: bool = False
    commands: tuple[str, ...] = ()

@dataclass(frozen=True)
class PlanTask:
    number: int
    title: str
    files: dict[str, tuple[str, ...]]
    steps: tuple[PlanStep, ...]

    @property
    def declared_files(self) -> list[str]:
        return [p for values in self.files.values() for p in values]


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
            raise ProjectStateError("not_git_repository", "project root is not a Git worktree") from exc
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise ProjectStateError("not_git_repository", "project root is not a Git worktree")
        for relative in self._ANCHORS:
            path = self._safe_path(relative)
            if not self._is_regular_file(path):
                raise ProjectStateError("missing_anchor", f"required anchor is missing or unsafe: {relative}")
        self._write_lock = threading.Lock()

    def parse_plan(self, name: str) -> tuple[PlanTask, ...]:
        text = self.read_plan(name)
        matches = list(re.finditer(r"^### Task\s+(\d+):\s*(.+?)\s*$", text, re.M))
        tasks = []
        for i, match in enumerate(matches):
            section = text[match.end(): matches[i+1].start() if i + 1 < len(matches) else len(text)]
            files: dict[str, list[str]] = {"Create": [], "Modify": [], "Test": []}
            fm = re.search(r"\*\*Files:\*\*(.*?)(?=\n###|\n\*\*|\Z)", section, re.S)
            if fm:
                for kind, path in re.findall(r"[-*]\s*(Create|Modify|Test):\s*`([^`]+)`", fm.group(1)):
                    files[kind].append(path)
            sm = list(re.finditer(r"^\s*- \[([ xX])\] \*\*Step\s+(\d+):\s*(.+?)\*\*\s*$", section, re.M))
            steps = []
            for j, s in enumerate(sm):
                body = section[s.end(): sm[j+1].start() if j + 1 < len(sm) else len(section)].strip()
                commands = []
                commands += re.findall(r"(?:Run|Command):\s*`([^`]+)`", body, re.I)
                for block in re.findall(r"```(?:powershell|bash|sh)\s*\n(.*?)```", body, re.I | re.S):
                    commands.extend(line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("#"))
                steps.append(PlanStep(int(s.group(2)), s.group(3).strip(), body, s.group(1).lower() == "x", tuple(commands)))
            tasks.append(PlanTask(int(match.group(1)), match.group(2).strip(), {k: tuple(v) for k,v in files.items()}, tuple(steps)))
        return tuple(tasks)

    _STATUS_RE = re.compile(r"<!-- poker8-project-state\s+(.*?)\s*-->", re.S)
    _STATUS_KEYS = {"schema_version","active_plan","active_task","active_step","state","last_confirmed_commit","evidence","note","updated_at"}
    _STATES = {"planned", "in_progress", "awaiting_confirmation", "completed"}

    def _status_path(self) -> Path:
        return self._safe_path("docs/project/status.md")

    def read_status(self) -> dict:
        path = self._status_path()
        try: text = path.read_text(encoding="utf-8") if self._is_regular_file(path) else ""
        except (OSError, UnicodeError) as exc: raise ProjectStateError("invalid_status", "status unavailable") from exc
        blocks = self._STATUS_RE.findall(text)
        if len(blocks) != 1: raise ProjectStateError("invalid_status", "status block missing or duplicated")
        try: data = json.loads(blocks[0])
        except json.JSONDecodeError as exc: raise ProjectStateError("invalid_status", "malformed status") from exc
        valid_types = (isinstance(data, dict) and isinstance(data.get("active_plan"), str)
            and isinstance(data.get("active_task"), int) and not isinstance(data.get("active_task"), bool)
            and isinstance(data.get("active_step"), int) and not isinstance(data.get("active_step"), bool)
            and isinstance(data.get("state"), str) and data.get("state") in self._STATES
            and isinstance(data.get("last_confirmed_commit"), str)
            and isinstance(data.get("note"), str) and isinstance(data.get("updated_at"), str)
            and isinstance(data.get("evidence"), list) and all(isinstance(item, str) for item in data.get("evidence", [])))
        if not isinstance(data, dict) or data.get("schema_version") != 1 or set(data) != self._STATUS_KEYS or not valid_types:
            raise ProjectStateError("invalid_status", "unsupported status schema")
        return data

    def _atomic_write(self, relative: str, content: str) -> None:
        if relative not in {"docs/project/status.md", "docs/project/decisions.md"}:
            raise ProjectStateError("write_failed", "write target is not approved")
        try:
            path = self._safe_path(relative)
        except ProjectStateError as exc:
            raise ProjectStateError("write_failed", "target is unsafe") from exc
        parent = path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and not self._is_regular_file(path): raise ProjectStateError("write_failed", "target is unsafe")
            if self._is_link(parent): raise ProjectStateError("write_failed", "parent is unsafe")
            with self._write_lock:
                fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
                try:
                    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                        handle.write(content); handle.flush(); os.fsync(handle.fileno())
                    os.replace(temp, path)
                except OSError as exc:
                    try: os.unlink(temp)
                    except OSError: pass
                    raise ProjectStateError("write_failed", "atomic write failed") from exc
        except ProjectStateError: raise
        except OSError as exc: raise ProjectStateError("write_failed", "atomic write failed") from exc

    def _render_status(self, data: dict) -> str:
        machine = json.dumps(data, sort_keys=True, separators=(",", ":"))
        evidence = "\n".join(f"- {e}" for e in data["evidence"]) or "- (none)"
        return (f"# Project Status\n\nPlan: `{data['active_plan']}`\nTask: {data['active_task']}\nStep: {data['active_step']}\nState: `{data['state']}`\nCommit: `{data['last_confirmed_commit']}`\nNote: {data['note']}\nEvidence:\n{evidence}\n\n<!-- poker8-project-state {machine} -->\n")

    def initialize_status(self, active_plan: str, active_task: int, active_step: int, last_confirmed_commit: str) -> dict:
        data = {"schema_version":1,"active_plan":active_plan,"active_task":active_task,"active_step":active_step,"state":"planned","last_confirmed_commit":last_confirmed_commit,"evidence":[],"note":"","updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
        self._validate_selection(active_plan, active_task, active_step)
        self._atomic_write("docs/project/status.md", self._render_status(data)); return data

    def _validate_selection(self, plan: str, task: int, step: int) -> tuple[PlanTask, PlanStep]:
        try:
            tasks = self.parse_plan(plan)
        except ProjectStateError as exc:
            raise ProjectStateError("invalid_plan", "plan not found or cannot be parsed") from exc
        if not tasks:
            raise ProjectStateError("invalid_plan", "plan has no tasks")
        t = next((x for x in tasks if x.number == task), None)
        if t is None: raise ProjectStateError("invalid_task", "task not found")
        s = next((x for x in t.steps if x.number == step), None)
        if s is None: raise ProjectStateError("invalid_step", "step not found")
        return t, s

    def set_active_task(self, plan: str, task_number: int, step_number: int = 1, state: str = "planned", note: str = "") -> dict:
        if state not in {"planned","in_progress","awaiting_confirmation"}: raise ProjectStateError("invalid_state", "completed state cannot be activated")
        self._validate_selection(plan, task_number, step_number)
        old = self.read_status()
        switched = old.get("active_plan") != plan or old.get("active_task") != task_number
        data = {"schema_version":1,"active_plan":plan,"active_task":task_number,"active_step":step_number,"state":state,"last_confirmed_commit":old.get("last_confirmed_commit",""),"evidence":[] if switched else old.get("evidence",[]),"note":note,"updated_at":datetime.now(timezone.utc).isoformat().replace("+00:00","Z")}
        self._atomic_write("docs/project/status.md", self._render_status(data)); return data

    def get_next_step(self) -> dict:
        status = self.read_status(); tasks = self.parse_plan(status["active_plan"]); task = next(t for t in tasks if t.number == status["active_task"])
        if status["state"] == "completed":
            task = next((t for t in tasks if t.number > task.number), None)
            if task is None:
                return {"plan": status["active_plan"], "task": None, "task_title": None,
                        "step": None, "step_title": None, "files": [], "body": "",
                        "commands": [], "recommendation": "no next task"}
            step = task.steps[0]
            recommendation = f"Switch explicitly to Task {task.number}: {task.title}"
        else:
            step = next((s for s in task.steps if not s.checked), None)
            if step is None:
                return {"plan": status["active_plan"], "task": task.number, "task_title": task.title,
                        "step": None, "step_title": None, "files": task.declared_files, "body": "",
                        "commands": [], "recommendation": "no unconfirmed steps"}
        result = {"plan":status["active_plan"],"task":task.number,"task_title":task.title,"step":step.number,"step_title":step.title,"files":task.declared_files,"body":step.body,"commands":list(step.commands)}
        if status["state"] == "completed": result["recommendation"] = recommendation
        return result

    @staticmethod
    def _is_link(path: Path) -> bool:
        is_junction = getattr(path, "is_junction", None)
        if path.is_symlink() or (is_junction is not None and is_junction()):
            return True
        # Python versions without Path.is_junction still expose the Windows
        # reparse-point bit through stat_result.file_attributes.
        try:
            return bool(getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400)
        except OSError:
            return False

    def _safe_path(self, relative: str) -> Path:
        """Resolve a repository-relative path without traversing links."""
        candidate = self.root / relative
        try:
            current = self.root
            for part in Path(relative).parts:
                current = current / part
                if self._is_link(current):
                    raise ProjectStateError("unsafe_path", f"symlink or junction in approved path: {relative}")
            resolved = candidate.resolve(strict=False)
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ProjectStateError("unsafe_path", f"path escapes project root: {relative}") from exc
        return candidate

    @staticmethod
    def _is_regular_file(path: Path) -> bool:
        try:
            return not ProjectRepository._is_link(path) and stat.S_ISREG(path.stat(follow_symlinks=False).st_mode)
        except OSError:
            return False

    def _catalogue(self, relative_dir: str) -> list[str]:
        directory = self._safe_path(relative_dir)
        if not directory.is_dir():
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
                raise ProjectStateError("unsafe_path", f"document is not a regular file: {entry.name}")
            names.append(entry.name)
        return sorted(names)

    def spec_catalogue(self) -> list[str]:
        return self._catalogue("docs/superpowers/specs")

    def plan_catalogue(self) -> list[str]:
        return self._catalogue("docs/superpowers/plans")

    def _read(self, relative_dir: str, name: str) -> str:
        if not isinstance(name, str) or not name or name != Path(name).name or Path(name).suffix != ".md":
            raise ProjectStateError("invalid_resource", f"invalid document name: {name!r}")
        try:
            try:
                directory = self._safe_path(relative_dir)
            except ProjectStateError as exc:
                raise ProjectStateError("invalid_resource", f"invalid document resource: {name}") from exc
            candidate = directory / name
            try:
                self._safe_path(f"{relative_dir}/{name}")
            except ProjectStateError as exc:
                raise ProjectStateError("invalid_resource", f"invalid document resource: {name}") from exc
            candidate_resolved = candidate.resolve(strict=False)
            if candidate_resolved.parent != directory.resolve() or not self._is_regular_file(candidate):
                raise ProjectStateError("invalid_resource", f"document is not an approved regular file: {name}")
            return candidate.read_text(encoding="utf-8")
        except ProjectStateError:
            raise
        except (OSError, UnicodeError) as exc:
            raise ProjectStateError("invalid_resource", f"document is unavailable: {name}") from exc

    def read_spec(self, name: str) -> str:
        return self._read("docs/superpowers/specs", name)

    def read_plan(self, name: str) -> str:
        return self._read("docs/superpowers/plans", name)
