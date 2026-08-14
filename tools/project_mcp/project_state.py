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


IGNORED_USER_PATTERNS = (
    re.compile(r"^data/.*\.sqlite3(?:-wal|-shm)?$"),
    re.compile(r"^\.superpowers(?:/|$)"),
)
RUNTIME_PREFIXES = ("app/", "online/", "static/")
FORBIDDEN_ADDITION = re.compile(
    r"(?i)(?<![a-z0-9])(?:CASH_USDT|deposit(?:[-_ ]endpoint)?|"
    r"withdraw(?:al)?(?:[-_ ]endpoint)?|KYC|blockchain|play[-_ ]to[-_ ]cash|"
    r"cash[-_ ]wallet|payment[-_ ]endpoint)(?![a-z0-9])"
)
# Document resources are approved project Markdown only.  Secret-looking
# names are excluded even when they happen to live below an approved folder.
SECRET_DOCUMENT_NAME = re.compile(
    r"(?i)(?:^|[._-])(?:env|secret|secrets|password|passwd|token|credential|credentials|private)(?:[._-]|$)"
)


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
    files: tuple[str, ...]
    steps: tuple[PlanStep, ...]

    @property
    def declared_files(self) -> list[str]:
        return list(self.files)


class ProjectRepository:
    """Validated, read-only boundary around approved project documents."""

    _ANCHORS = (
        "docs/superpowers/specs/2026-08-14-online-network-mvp-design.md",
        "docs/superpowers/specs/2026-08-14-poker8-product-vision.md",
    )

    def __init__(self, root: Path, *, replace=os.replace) -> None:
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
        self._replace = replace

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run one fixed, read-only Git command in the validated worktree."""
        if any(not isinstance(arg, str) or not arg for arg in args):
            raise ProjectStateError("git_unavailable", "invalid Git command")
        try:
            result = subprocess.run(
                ["git", *args], cwd=self.root, shell=False, capture_output=True,
                text=True, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectStateError("git_unavailable", "Git is unavailable or timed out") from exc
        if check and result.returncode != 0:
            raise ProjectStateError("git_unavailable", "Git command failed")
        return result

    def _task(self, plan: str, number: int) -> PlanTask:
        if plan not in self.plan_catalogue():
            raise ProjectStateError("invalid_plan", f"Unknown plan: {plan}")
        for task in self.parse_plan(plan):
            if task.number == number:
                return task
        raise ProjectStateError("invalid_task", f"Unknown task: {number}")

    def parse_plan(self, name: str) -> tuple[PlanTask, ...]:
        text = self.read_plan(name)
        matches = list(re.finditer(r"^### Task\s+(\d+):\s*(.+?)\s*$", text, re.M))
        tasks = []
        for i, match in enumerate(matches):
            section = text[match.end(): matches[i+1].start() if i + 1 < len(matches) else len(text)]
            files: list[str] = []
            fm = re.search(r"\*\*Files:\*\*(.*?)(?=\n###|\n\*\*|\Z)", section, re.S)
            if fm:
                for kind, path in re.findall(r"[-*]\s*(Create|Modify|Test):\s*`([^`]+)`", fm.group(1)):
                    files.append(path)
            sm = list(re.finditer(r"^\s*- \[([ xX])\] \*\*Step\s+(\d+):\s*(.+?)\*\*\s*$", section, re.M))
            steps = []
            for j, s in enumerate(sm):
                body = section[s.end(): sm[j+1].start() if j + 1 < len(sm) else len(section)].strip()
                commands = []
                commands += re.findall(r"(?:Run|Command):\s*`([^`]+)`", body, re.I)
                for block in re.findall(r"```(?:powershell|bash|sh)\s*\n(.*?)```", body, re.I | re.S):
                    commands.extend(line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith("#"))
                steps.append(PlanStep(int(s.group(2)), s.group(3).strip(), body, s.group(1).lower() == "x", tuple(commands)))
            tasks.append(PlanTask(int(match.group(1)), match.group(2).strip(), tuple(files), tuple(steps)))
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
        schema_ok = isinstance(data, dict) and isinstance(data.get("schema_version"), int) and not isinstance(data.get("schema_version"), bool) and data.get("schema_version") == 1
        if not schema_ok or not isinstance(data, dict) or set(data) != self._STATUS_KEYS or not valid_types:
            raise ProjectStateError("invalid_status", "unsupported status schema")
        try:
            self._validate_selection(data["active_plan"], data["active_task"], data["active_step"])
        except ProjectStateError as exc:
            raise ProjectStateError("invalid_status", "status selection is stale or invalid") from exc
        return data

    def _atomic_write(self, relative: str, content: str) -> None:
        if relative not in {"docs/project/status.md", "docs/project/decisions.md"}:
            raise ProjectStateError("write_forbidden", "MCP may write only status and decisions")
        try:
            path = self._safe_path(relative)
        except ProjectStateError:
            raise
        parent = path.parent
        try:
            parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and not self._is_regular_file(path): raise ProjectStateError("unsafe_path", "target is unsafe")
            if self._is_link(parent): raise ProjectStateError("unsafe_path", "parent is unsafe")
            with self._write_lock:
                fd, temp = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(parent))
                try:
                    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                        handle.write(content); handle.flush(); os.fsync(handle.fileno())
                    self._replace(temp, path)
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

    _DECISION_ID_RE = re.compile(r"^P8-DEC-(\d{4})$")

    @staticmethod
    def _initial_decisions() -> str:
        return ("# Project Decisions\n\n"
                "Policy: append-only; decisions are never edited or deleted.\n\n"
                "## P8-DEC-0001 — Project boundary\n\n"
                "- Date: 2026-08-14T00:00:00Z\n- Supersedes: none\n\n"
                "### Decision\n\nProject state writes are limited to approved status and decision documents.\n\n"
                "### Rationale\n\nKeep the MCP write boundary explicit and auditable.\n")

    def _read_decisions(self) -> tuple[str, list[dict]]:
        path = self._safe_path("docs/project/decisions.md")
        if not self._is_regular_file(path):
            return self._initial_decisions(), [{"id": "P8-DEC-0001", "title": "Project boundary",
                "decision": "Project state writes are limited to approved status and decision documents.",
                "rationale": "Keep the MCP write boundary explicit and auditable.", "supersedes": None}]
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                text = handle.read()
        except (OSError, UnicodeError) as exc:
            raise ProjectStateError("invalid_decision_log", "decision log unavailable") from exc
        raw_headings = list(re.finditer(r"^##\s+P8-DEC-(\S+).*?$", text, re.M))
        matches = list(re.finditer(r"^## (P8-DEC-\d{4})\s*(?::|—)\s*(.+?)\s*$", text, re.M))
        if len(raw_headings) != len(matches):
            raise ProjectStateError("invalid_decision_log", "malformed decision log")
        entries = []
        for i, match in enumerate(matches):
            section = text[match.end(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
            dm = re.search(r"^Decision:\s*(.+?)\s*$", section, re.M) or re.search(r"### Decision\s*\n\s*(.+?)(?=\n\s*### Rationale|\Z)", section, re.S)
            rm = re.search(r"^Rationale:\s*(.+?)\s*$", section, re.M) or re.search(r"### Rationale\s*\n\s*(.+?)(?=\n\s*## |\Z)", section, re.S)
            any_sm = re.search(r"^-?\s*Supersedes:\s*(\S+)\s*$", section, re.M)
            if any_sm and any_sm.group(1) != "none" and self._DECISION_ID_RE.fullmatch(any_sm.group(1)) is None:
                raise ProjectStateError("invalid_decision_log", "malformed decision supersedes reference")
            sm = re.search(r"^-?\s*Supersedes:\s*(P8-DEC-\d{4}|none)\s*$", section, re.M)
            entries.append({"id": match.group(1), "title": match.group(2).strip(),
                            "decision": dm.group(1).strip() if dm else "",
                            "rationale": rm.group(1).strip() if rm else "",
                            "supersedes": (None if not sm or sm.group(1) == "none" else sm.group(1))})
        if not entries or any(self._DECISION_ID_RE.fullmatch(e["id"]) is None for e in entries):
            raise ProjectStateError("invalid_decision_log", "malformed decision log")
        for index, entry in enumerate(entries, 1):
            if entry["id"] != f"P8-DEC-{index:04d}" or not entry["title"] or not entry["decision"] or not entry["rationale"]:
                raise ProjectStateError("invalid_decision_log", "gapped or malformed decision log")
            if entry["supersedes"] and entry["supersedes"] not in {x["id"] for x in entries[:index - 1]}:
                raise ProjectStateError("invalid_decision_log", "invalid decision supersedes reference")
        return text, entries

    def record_decision(self, title: str, decision: str, rationale: str, supersedes: str | None = None) -> dict:
        values = (title, decision, rationale)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ProjectStateError("invalid_decision", "title, decision, and rationale are required")
        text, entries = self._read_decisions()
        if supersedes is not None and supersedes not in {entry["id"] for entry in entries}:
            raise ProjectStateError("invalid_decision", "supersedes must reference an existing decision")
        entry = {"id": f"P8-DEC-{len(entries) + 1:04d}", "title": title.strip(), "decision": decision.strip(),
                 "rationale": rationale.strip(), "supersedes": supersedes}
        newline = "\r\n" if "\r\n" in text else "\n"
        suffix = (f"{newline}## {entry['id']} — {entry['title']}{newline}{newline}"
                  f"- Date: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}{newline}"
                  f"- Supersedes: {supersedes or 'none'}{newline}{newline}"
                  f"### Decision{newline}{newline}{entry['decision']}{newline}{newline}"
                  f"### Rationale{newline}{newline}{entry['rationale']}{newline}")
        separator = "" if text.endswith(("\n", "\r")) else newline
        self._atomic_write("docs/project/decisions.md", text + separator + suffix.lstrip("\r\n"))
        entry["supersedes"] = supersedes or "none"
        return entry

    def confirm_task_completed(self, evidence: str, commit: str | None = None) -> dict:
        if not isinstance(evidence, str) or not evidence.strip():
            raise ProjectStateError("invalid_evidence", "evidence must be non-empty")
        evidence = evidence.strip()
        if commit is not None:
            if not isinstance(commit, str) or re.fullmatch(r"[0-9a-fA-F]{7,40}", commit) is None:
                raise ProjectStateError("invalid_commit", "commit must be a hexadecimal local revision")
            try:
                result = subprocess.run(["git", "rev-parse", "--verify", f"{commit}^{{commit}}"], cwd=self.root,
                                        shell=False, capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise ProjectStateError("invalid_commit", "commit cannot be verified") from exc
            if result.returncode != 0:
                raise ProjectStateError("invalid_commit", "commit cannot be verified")
            commit = result.stdout.strip()
        status = self.read_status()
        status["state"] = "completed"
        status["evidence"] = [evidence]
        if commit is not None:
            status["last_confirmed_commit"] = commit
        status["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self._atomic_write("docs/project/status.md", self._render_status(status))
        return status

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
            step = task.steps[0] if task.steps else None
            recommendation = f"Switch explicitly to Task {task.number}: {task.title}"
            if step is None:
                return {"plan": status["active_plan"], "task": task.number, "task_title": task.title,
                        "step": None, "step_title": None, "files": task.declared_files, "body": "",
                        "commands": [], "recommendation": recommendation}
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
    def _normal_path(raw: str) -> str:
        value = raw.strip().strip('"').replace("\\", "/")
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        path = Path(value)
        if path.is_absolute() or ".." in path.parts:
            raise ProjectStateError("unsafe_git_path", "Git returned an unsafe path")
        return path.as_posix()

    def _name_only(self, cached: bool) -> set[str]:
        args = ["diff"]
        if cached:
            args.append("--cached")
        args.append("--name-only")
        return {
            self._normal_path(line)
            for line in self._git(*args).stdout.splitlines()
            if line.strip()
        }

    def _untracked(self) -> set[str]:
        paths: set[str] = set()
        for line in self._git("status", "--porcelain=v1").stdout.splitlines():
            if line.startswith("?? "):
                paths.add(self._normal_path(line[3:]))
        return paths

    def _expand_untracked(self, paths: set[str]) -> set[str]:
        """Expand Git's directory marker using names only, never file contents."""
        expanded: set[str] = set()
        for path in paths:
            if path != "data":
                expanded.add(path)
                continue
            directory = self.root / "data"
            if self._is_link(directory):
                expanded.add(path)
                continue
            try:
                entries = directory.iterdir()
            except OSError:
                expanded.add(path)
                continue
            found = False
            for entry in entries:
                found = True
                expanded.add(f"data/{entry.name}")
            if not found:
                expanded.add(path)
        return expanded

    @staticmethod
    def _ignored_user_path(path: str) -> bool:
        return any(pattern.match(path) for pattern in IGNORED_USER_PATTERNS)

    def _patch(self, paths: set[str], cached: bool) -> str:
        if not paths:
            return ""
        args = ["diff"]
        if cached:
            args.append("--cached")
        args.extend(["--no-ext-diff", "--unified=0", "--", *sorted(paths)])
        return self._git(*args).stdout

    def check_current_diff(self) -> dict[str, object]:
        """Compare fixed Git path/diff output with the active task scope."""
        status = self.read_status()
        task = self._task(str(status["active_plan"]), int(status["active_task"]))
        unstaged = self._name_only(False)
        staged = self._name_only(True)
        untracked = self._expand_untracked(self._untracked())
        all_paths = unstaged | staged | untracked
        ignored_raw = {path for path in all_paths if self._ignored_user_path(path)}
        ignored_display = {
            ".superpowers/" if path == ".superpowers" or path.startswith(".superpowers/") else path
            for path in ignored_raw
        }
        relevant = all_paths - ignored_raw
        expected = set(task.files)
        extra = sorted(relevant - expected)
        missing = sorted(expected - relevant)
        evidence: list[dict[str, str]] = []
        for patch in (
            self._patch(unstaged - ignored_raw, False),
            self._patch(staged - ignored_raw, True),
        ):
            current_path = ""
            for line in patch.splitlines():
                if line.startswith("+++ b/"):
                    current_path = self._normal_path(line[6:])
                elif (
                    current_path.startswith(RUNTIME_PREFIXES)
                    and line.startswith("+")
                    and not line.startswith("+++")
                    and (match := FORBIDDEN_ADDITION.search(line[1:]))
                ):
                    evidence.append({
                        "path": current_path,
                        "term": match.group(0),
                        "line": line[1:],
                    })
        if evidence:
            result = "blocked"
        elif extra or missing or relevant & untracked:
            result = "warning"
        else:
            result = "aligned"
        return {
            "result": result,
            "active_task_files": sorted(expected),
            "staged": sorted(staged - ignored_raw),
            "unstaged": sorted(unstaged - ignored_raw),
            "untracked": sorted(untracked - ignored_raw),
            "extra": extra,
            "missing": missing,
            "blocked_evidence": evidence,
            "ignored_user_changes": sorted(ignored_display),
            "limitations": "Deterministic path and added-line checks; semantic review remains required.",
        }

    def get_project_overview(self) -> dict[str, object]:
        status = self.read_status()
        task = self._task(str(status["active_plan"]), int(status["active_task"]))
        alignment = self.check_current_diff()
        return {
            "objective": "Deliver the approved multiplayer play-money Poker8 MVP.",
            "excluded": ["real-money runtime", "USDT payments", "KYC", "blockchain"],
            "active_plan": status["active_plan"],
            "active_task": status["active_task"],
            "task_title": task.title,
            "state": status["state"],
            "last_confirmed_commit": status["last_confirmed_commit"],
            "evidence": status["evidence"],
            "branch": self._git("branch", "--show-current").stdout.strip(),
            "git": {
                "result": alignment["result"],
                "staged_count": len(alignment["staged"]),
                "unstaged_count": len(alignment["unstaged"]),
                "untracked_count": len(alignment["untracked"]),
                "ignored_user_changes": alignment["ignored_user_changes"],
            },
            "next": self.get_next_step(),
        }

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

    def _safe_regular_file(self, relative: Path) -> Path:
        relative = Path(relative)
        if relative.is_absolute() or ".." in relative.parts:
            raise ProjectStateError("invalid_resource", "Path is outside the approved catalogue")
        candidate = self._safe_path(relative.as_posix())
        if not self._is_regular_file(candidate):
            raise ProjectStateError("invalid_resource", "Approved path is not a regular file")
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
            if SECRET_DOCUMENT_NAME.search(entry.name.removesuffix(".md")):
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
            if SECRET_DOCUMENT_NAME.search(Path(name).stem):
                raise ProjectStateError("invalid_resource", f"document name is not approved: {name}")
            if name not in self._catalogue(relative_dir):
                raise ProjectStateError("invalid_resource", f"unknown document: {name}")
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
