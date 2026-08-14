# Poker8 Project Navigator MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and register a project-local `poker8_project` MCP that navigates approved Poker8 documents and Git state while writing only the explicitly managed project status and decision journal.

**Architecture:** Keep the implementation to one standard-library domain module plus one thin MCP SDK adapter. The domain module validates the repository, catalogs approved Markdown, parses the active plan, performs fixed read-only Git inspection, and owns fail-closed atomic manager writes; the adapter exposes five resource families and six typed tools over stdio. Install the SDK only into the existing project virtual environment and register absolute paths with Codex.

**Tech Stack:** Python 3.12, standard library, MCP Python SDK v2 (`mcp>=2,<3`), pytest, AnyIO, Git CLI, PowerShell, Codex CLI.

**Approved spec:** [`docs/superpowers/specs/2026-08-14-project-mcp-design.md`](../specs/2026-08-14-project-mcp-design.md)

---

## Locked file map

- `tools/project_mcp/project_state.py` — all project-root validation, document discovery, plan/status parsing, safe writes, decision allocation, Git reads, and alignment rules.
- `tools/project_mcp/server.py` — CLI parsing, `MCPServer` construction, five resource families, six tool handlers, structured error conversion, and stdio entrypoint.
- `tools/project_mcp/requirements.txt` — isolated MCP dependency; the game's root requirements stay unchanged.
- `tools/project_mcp/install.ps1` — idempotence-safe dependency installation and Codex registration using absolute paths.
- `tools/project_mcp/README.md` — operator contract, install/verify/remove commands, capabilities, safety boundaries, and new-task verification.
- `docs/project/status.md` — one canonical machine state embedded in human-readable Markdown.
- `docs/project/decisions.md` — append-only, monotonic project decision journal.
- `tests/project_mcp/test_project_state.py` — catalog, plan, status, next-step, decision, and Git-alignment behavior.
- `tests/project_mcp/test_safety.py` — containment, symlink, secret/database, write-boundary, and atomic-failure tests.
- `tests/project_mcp/test_server.py` — official SDK v2 in-memory MCP contract tests.
- `tests/project_mcp/test_stdio.py` — actual child-process stdio smoke test.

Do not add package marker files, a second configuration format, a database, an HTTP listener, or a dependency to the game's root `requirements.txt`.

### Task 1: Establish the validated repository and document catalogue

**Files:**
- Create: `tools/project_mcp/requirements.txt`
- Create: `tools/project_mcp/project_state.py`
- Create: `tests/project_mcp/test_project_state.py`

- [ ] **Step 1: Add the isolated SDK pin**

Create `tools/project_mcp/requirements.txt` with exactly:

```text
mcp>=2,<3
```

- [ ] **Step 2: Write failing repository and catalogue tests**

Create `tests/project_mcp/test_project_state.py` with helpers that make a real temporary Git worktree and both required anchor specifications:

```python
from pathlib import Path
import subprocess

import pytest

from tools.project_mcp.project_state import ProjectRepository, ProjectStateError


ANCHORS = (
    "2026-08-14-online-network-mvp-design.md",
    "2026-08-14-poker8-product-vision.md",
)


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "tests@example.invalid")
    git(tmp_path, "config", "user.name", "Poker8 Tests")
    specs = tmp_path / "docs" / "superpowers" / "specs"
    plans = tmp_path / "docs" / "superpowers" / "plans"
    specs.mkdir(parents=True)
    plans.mkdir(parents=True)
    for name in ANCHORS:
        (specs / name).write_text(f"# {name}\n", encoding="utf-8")
    (specs / "approved.md").write_text("# Approved\n", encoding="utf-8")
    (plans / "active.md").write_text(
        "# Active Plan\n\n"
        "### Task 1: First task\n\n"
        "**Files:**\n"
        "- Create: `online/config.py`\n"
        "- Test: `tests/online/test_config.py`\n\n"
        "- [ ] **Step 1: Write the failing test**\n\n"
        "Run: `pytest tests/online/test_config.py -q`\n\n"
        "- [ ] **Step 2: Implement the setting**\n",
        encoding="utf-8",
    )
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "fixture")
    return tmp_path


def test_repository_requires_git_and_anchor_documents(tmp_path: Path):
    with pytest.raises(ProjectStateError, match="Git worktree"):
        ProjectRepository(tmp_path)


def test_catalogue_contains_only_markdown_below_approved_roots(project_root: Path):
    (project_root / "docs" / "superpowers" / "specs" / "ignored.txt").write_text(
        "secret", encoding="utf-8"
    )
    repository = ProjectRepository(project_root)
    assert sorted(repository.spec_catalogue()) == [*ANCHORS, "approved.md"]
    assert repository.plan_catalogue() == ["active.md"]


def test_read_catalogued_document_rejects_unknown_name(project_root: Path):
    repository = ProjectRepository(project_root)
    with pytest.raises(ProjectStateError) as error:
        repository.read_spec("../../.env")
    assert error.value.code == "invalid_resource"
```

- [ ] **Step 3: Run the new tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py -q
```

Expected: collection fails because `tools.project_mcp.project_state` does not exist.

- [ ] **Step 4: Implement the repository boundary and catalogue**

Create `tools/project_mcp/project_state.py` with these concrete foundations:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
from typing import Callable, Literal, Sequence


ANCHOR_SPECS = (
    "2026-08-14-online-network-mvp-design.md",
    "2026-08-14-poker8-product-vision.md",
)
STATE_PATTERN = re.compile(
    r"<!-- poker8-project-state\s*\n(?P<json>\{.*?\})\s*\n-->", re.DOTALL
)
TASK_PATTERN = re.compile(r"^### Task (?P<number>\d+): (?P<title>.+)$", re.MULTILINE)
STEP_PATTERN = re.compile(
    r"^- \[(?P<checked>[ xX])\] \*\*Step (?P<number>\d+): (?P<title>.+?)\*\*$",
    re.MULTILINE,
)
FILE_PATTERN = re.compile(r"^- (?:Create|Modify|Test): `(?P<path>[^`]+)`$", re.MULTILINE)
DECISION_PATTERN = re.compile(r"^## P8-DEC-(?P<number>\d{4})\b", re.MULTILINE)
INLINE_COMMAND_PATTERN = re.compile(r"(?:Run|Command):\s*`(?P<command>[^`\n]+)`")
COMMAND_BLOCK_PATTERN = re.compile(r"```(?:powershell|bash|sh)\s*\n(?P<body>.*?)```", re.DOTALL)
ALLOWED_STATES = {"planned", "in_progress", "awaiting_confirmation", "completed"}
WRITABLE_RELATIVE_PATHS = {
    Path("docs/project/status.md"),
    Path("docs/project/decisions.md"),
}


class ProjectStateError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PlanStep:
    number: int
    title: str
    checked: bool
    body: str


@dataclass(frozen=True)
class PlanTask:
    number: int
    title: str
    files: Sequence[str]
    steps: Sequence[PlanStep]


Clock = Callable[[], datetime]
Replace = Callable[[str | os.PathLike[str], str | os.PathLike[str]], None]


class ProjectRepository:
    def __init__(
        self,
        root: Path,
        *,
        clock: Clock | None = None,
        replace: Replace = os.replace,
    ):
        self.root = root.resolve(strict=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.replace = replace
        self._write_lock = threading.Lock()
        self._validate_root()

    def _validate_root(self) -> None:
        result = self._git("rev-parse", "--is-inside-work-tree", check=False)
        if result.returncode != 0 or result.stdout.strip() != "true":
            raise ProjectStateError("invalid_root", "Root must be a Git worktree")
        for name in ANCHOR_SPECS:
            self._safe_regular_file(Path("docs/superpowers/specs") / name)

    def _git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.root,
                shell=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ProjectStateError("git_unavailable", "Git is unavailable or timed out") from exc
        if check and result.returncode != 0:
            raise ProjectStateError("git_unavailable", "Git command failed")
        return result

    def _safe_regular_file(self, relative: Path) -> Path:
        if relative.is_absolute() or ".." in relative.parts:
            raise ProjectStateError("invalid_resource", "Path is outside the approved catalogue")
        candidate = self.root / relative
        if candidate.is_symlink():
            raise ProjectStateError("unsafe_path", "Symbolic links are not allowed")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(self.root) or not resolved.is_file():
            raise ProjectStateError("unsafe_path", "Approved path must be a regular project file")
        return resolved

    def _catalogue(self, relative: Path) -> dict[str, Path]:
        directory = (self.root / relative).resolve(strict=True)
        result: dict[str, Path] = {}
        for candidate in sorted(directory.glob("*.md")):
            safe = self._safe_regular_file(relative / candidate.name)
            result[candidate.name] = safe
        return result

    def spec_catalogue(self) -> list[str]:
        return list(self._catalogue(Path("docs/superpowers/specs")))

    def plan_catalogue(self) -> list[str]:
        return list(self._catalogue(Path("docs/superpowers/plans")))

    def _read_catalogued(self, kind: str, name: str) -> str:
        base = Path("docs/superpowers/specs" if kind == "spec" else "docs/superpowers/plans")
        catalogue = self._catalogue(base)
        if name not in catalogue:
            raise ProjectStateError("invalid_resource", f"Unknown {kind}: {name}")
        return catalogue[name].read_text(encoding="utf-8")

    def read_spec(self, name: str) -> str:
        return self._read_catalogued("spec", name)

    def read_plan(self, name: str) -> str:
        return self._read_catalogued("plan", name)
```

- [ ] **Step 5: Run the catalogue tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py -q
```

Expected: `3 passed`.

- [ ] **Step 6: Commit the validated read boundary**

```powershell
git add tools/project_mcp/requirements.txt tools/project_mcp/project_state.py tests/project_mcp/test_project_state.py
git commit -m "feat: add project MCP document boundary"
```

### Task 2: Parse plans and create the canonical project status

**Files:**
- Modify: `tools/project_mcp/project_state.py`
- Modify: `tests/project_mcp/test_project_state.py`
- Create: `docs/project/status.md`

- [ ] **Step 1: Add failing plan and status tests**

Append these tests to `tests/project_mcp/test_project_state.py`:

```python
def test_parse_plan_returns_exact_files_and_numbered_steps(project_root: Path):
    repository = ProjectRepository(project_root)
    tasks = repository.parse_plan("active.md")
    assert tasks[0].title == "First task"
    assert tasks[0].files == ("online/config.py", "tests/online/test_config.py")
    assert [step.number for step in tasks[0].steps] == [1, 2]
    assert "pytest tests/online/test_config.py -q" in tasks[0].steps[0].body


def test_status_round_trip_and_next_step(project_root: Path):
    status_dir = project_root / "docs" / "project"
    status_dir.mkdir()
    repository = ProjectRepository(project_root)
    repository.initialize_status(
        active_plan="active.md",
        active_task=1,
        active_step=1,
        last_confirmed_commit=git(project_root, "rev-parse", "--short", "HEAD"),
    )
    status = repository.read_status()
    assert status["state"] == "planned"
    assert repository.get_next_step()["step_title"] == "Write the failing test"
    assert repository.get_next_step()["commands"] == [
        "pytest tests/online/test_config.py -q"
    ]


def test_set_active_task_validates_task_step_and_state(project_root: Path):
    (project_root / "docs" / "project").mkdir()
    repository = ProjectRepository(project_root)
    repository.initialize_status("active.md", 1, 1, "abc1234")
    result = repository.set_active_task("active.md", 1, 2, "in_progress", "Implementing")
    assert result["active_step"] == 2
    assert result["note"] == "Implementing"
    with pytest.raises(ProjectStateError) as error:
        repository.set_active_task("active.md", 1, 99, "in_progress", "")
    assert error.value.code == "invalid_step"
    with pytest.raises(ProjectStateError) as completed:
        repository.set_active_task("active.md", 1, 1, "completed", "")
    assert completed.value.code == "invalid_state"
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py -q
```

Expected: the three new tests fail because plan and status methods are absent.

- [ ] **Step 3: Implement task parsing, state validation, rendering, and next-step lookup**

Add these methods to `ProjectRepository`; `_atomic_write` is the only filesystem write primitive and rejects every non-manager target:

```python
    def parse_plan(self, name: str) -> Sequence[PlanTask]:
        text = self.read_plan(name)
        task_matches = list(TASK_PATTERN.finditer(text))
        tasks: list[PlanTask] = []
        for index, match in enumerate(task_matches):
            end = task_matches[index + 1].start() if index + 1 < len(task_matches) else len(text)
            section = text[match.end():end]
            files_match = re.search(r"\*\*Files:\*\*\s*\n(?P<body>(?:- .+\n)+)", section)
            files = tuple(FILE_PATTERN.findall(files_match.group("body"))) if files_match else ()
            step_matches = list(STEP_PATTERN.finditer(section))
            steps: list[PlanStep] = []
            for step_index, step_match in enumerate(step_matches):
                step_end = (
                    step_matches[step_index + 1].start()
                    if step_index + 1 < len(step_matches)
                    else len(section)
                )
                steps.append(
                    PlanStep(
                        number=int(step_match.group("number")),
                        title=step_match.group("title"),
                        checked=step_match.group("checked").lower() == "x",
                        body=section[step_match.end():step_end].strip(),
                    )
                )
            tasks.append(
                PlanTask(
                    number=int(match.group("number")),
                    title=match.group("title"),
                    files=files,
                    steps=tuple(steps),
                )
            )
        return tuple(tasks)

    def _status_path(self) -> Path:
        return self.root / "docs" / "project" / "status.md"

    def _status_json(self, text: str) -> dict[str, object]:
        matches = list(STATE_PATTERN.finditer(text))
        if len(matches) != 1:
            raise ProjectStateError("invalid_status", "Status must contain one project-state block")
        try:
            state = json.loads(matches[0].group("json"))
        except json.JSONDecodeError as exc:
            raise ProjectStateError("invalid_status", "Status state is malformed") from exc
        required = {
            "schema_version", "active_plan", "active_task", "active_step", "state",
            "last_confirmed_commit", "evidence", "note", "updated_at",
        }
        if set(state) != required or state["schema_version"] != 1 or state["state"] not in ALLOWED_STATES:
            raise ProjectStateError("invalid_status", "Status schema is unsupported")
        if not isinstance(state["evidence"], list):
            raise ProjectStateError("invalid_status", "Status evidence must be a list")
        return state

    def read_status(self) -> dict[str, object]:
        return self._status_json(self._safe_regular_file(Path("docs/project/status.md")).read_text(encoding="utf-8"))

    def _render_status(self, state: dict[str, object]) -> str:
        task = self._task(str(state["active_plan"]), int(state["active_task"]))
        evidence = "\n".join(f"- {item}" for item in state["evidence"]) or "- None confirmed"
        machine = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        return (
            f"<!-- poker8-project-state\n{machine}\n-->\n\n"
            "# Poker8 Project Status\n\n## Current focus\n\n"
            f"- Plan: `{state['active_plan']}`\n- Task: {task.number} — {task.title}\n"
            f"- Step: {state['active_step']}\n- State: `{state['state']}`\n"
            f"- Last confirmed commit: `{state['last_confirmed_commit']}`\n"
            f"- Note: {state['note'] or 'None'}\n\n## Evidence\n\n{evidence}\n"
        )

    def _atomic_write(self, relative: Path, content: str) -> None:
        if relative not in WRITABLE_RELATIVE_PATHS:
            raise ProjectStateError("write_forbidden", "MCP may write only status and decisions")
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and (target.is_symlink() or not target.is_file()):
            raise ProjectStateError("unsafe_path", "Writable target must be a regular file")
        if target.parent.is_symlink() or not target.parent.resolve(strict=True).is_relative_to(self.root):
            raise ProjectStateError("unsafe_path", "Writable directory escaped the project root")
        temporary_name: str | None = None
        with self._write_lock:
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=target.parent, delete=False
                ) as temporary:
                    temporary_name = temporary.name
                    temporary.write(content)
                    temporary.flush()
                    os.fsync(temporary.fileno())
                self.replace(temporary_name, target)
            except OSError as exc:
                if temporary_name:
                    Path(temporary_name).unlink(missing_ok=True)
                raise ProjectStateError("write_failed", "Atomic project-state write failed") from exc

    def _task(self, plan: str, number: int) -> PlanTask:
        if plan not in self.plan_catalogue():
            raise ProjectStateError("invalid_plan", f"Unknown plan: {plan}")
        for task in self.parse_plan(plan):
            if task.number == number:
                return task
        raise ProjectStateError("invalid_task", f"Unknown task: {number}")

    def initialize_status(
        self, active_plan: str, active_task: int, active_step: int, last_confirmed_commit: str
    ) -> dict[str, object]:
        task = self._task(active_plan, active_task)
        if active_step not in {step.number for step in task.steps}:
            raise ProjectStateError("invalid_step", f"Unknown step: {active_step}")
        state: dict[str, object] = {
            "schema_version": 1,
            "active_plan": active_plan,
            "active_task": active_task,
            "active_step": active_step,
            "state": "planned",
            "last_confirmed_commit": last_confirmed_commit,
            "evidence": [],
            "note": "",
            "updated_at": self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        self._atomic_write(Path("docs/project/status.md"), self._render_status(state))
        return state

    def set_active_task(
        self, plan: str, task_number: int, step_number: int = 1,
        state: Literal["planned", "in_progress", "awaiting_confirmation"] = "planned",
        note: str = "",
    ) -> dict[str, object]:
        if state not in {"planned", "in_progress", "awaiting_confirmation"}:
            raise ProjectStateError("invalid_state", f"State cannot be selected explicitly: {state}")
        task = self._task(plan, task_number)
        if step_number not in {step.number for step in task.steps}:
            raise ProjectStateError("invalid_step", f"Unknown step: {step_number}")
        current = self.read_status()
        switching = current["active_plan"] != plan or current["active_task"] != task_number
        current.update({
            "active_plan": plan, "active_task": task_number, "active_step": step_number,
            "state": state, "note": note.strip(),
            "evidence": [] if switching else current["evidence"],
            "updated_at": self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        })
        self._atomic_write(Path("docs/project/status.md"), self._render_status(current))
        return current

    def get_next_step(self) -> dict[str, object]:
        status = self.read_status()
        task = self._task(str(status["active_plan"]), int(status["active_task"]))
        if status["state"] == "completed":
            tasks = self.parse_plan(str(status["active_plan"]))
            next_task = next((item for item in tasks if item.number > task.number), None)
            return {
                "state": "completed", "task_number": task.number,
                "recommendation": (
                    f"Switch explicitly to Task {next_task.number}: {next_task.title}"
                    if next_task else "The active plan has no later task"
                ),
            }
        step = next((item for item in task.steps if item.number == int(status["active_step"])), None)
        if step is None:
            raise ProjectStateError("invalid_step", "Active step is absent from the active plan")
        commands = [match.group("command") for match in INLINE_COMMAND_PATTERN.finditer(step.body)]
        for match in COMMAND_BLOCK_PATTERN.finditer(step.body):
            commands.extend(line.strip() for line in match.group("body").splitlines() if line.strip())
        return {
            "state": status["state"], "plan": status["active_plan"],
            "task_number": task.number, "task_title": task.title,
            "step_number": step.number, "step_title": step.title,
            "files": list(task.files), "commands": commands, "body": step.body,
        }
```

- [ ] **Step 4: Create the initial canonical status**

Create `docs/project/status.md` with this exact initial state and human summary; use the current UTC timestamp when executing the plan:

```markdown
<!-- poker8-project-state
{"schema_version":1,"active_plan":"2026-08-14-online-mvp-foundation.md","active_task":1,"active_step":1,"state":"planned","last_confirmed_commit":"8d20207","evidence":[],"note":"","updated_at":"2026-08-14T00:00:00Z"}
-->

# Poker8 Project Status

## Current focus

- Plan: `2026-08-14-online-mvp-foundation.md`
- Task: 1 — Restore a green 6-max baseline
- Step: 1
- State: `planned`
- Last confirmed commit: `8d20207`
- Note: None

## Evidence

- None confirmed
```

- [ ] **Step 5: Run the domain tests and verify GREEN**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py -q
```

Expected: `6 passed`.

- [ ] **Step 6: Commit plan parsing and status management**

```powershell
git add tools/project_mcp/project_state.py tests/project_mcp/test_project_state.py docs/project/status.md
git commit -m "feat: track project MCP active work"
```

### Task 3: Add append-only decisions and explicit completion

**Files:**
- Modify: `tools/project_mcp/project_state.py`
- Modify: `tests/project_mcp/test_project_state.py`
- Create: `docs/project/decisions.md`

- [ ] **Step 1: Write failing decision and completion tests**

Append:

```python
def test_record_decision_allocates_monotonic_id(project_root: Path):
    project_dir = project_root / "docs" / "project"
    project_dir.mkdir()
    (project_dir / "decisions.md").write_text(
        "# Poker8 Project Decisions\n\nEntries are append-only.\n\n"
        "## P8-DEC-0001 — First\n\n- Date: 2026-08-14T00:00:00Z\n"
        "- Supersedes: none\n\n### Decision\n\nA\n\n### Rationale\n\nB\n",
        encoding="utf-8",
    )
    repository = ProjectRepository(project_root)
    result = repository.record_decision("Second", "Choose B", "It is bounded", "P8-DEC-0001")
    assert result["id"] == "P8-DEC-0002"
    assert "## P8-DEC-0002 — Second" in (project_dir / "decisions.md").read_text(encoding="utf-8")


def test_completion_requires_evidence_and_resolvable_hex_commit(project_root: Path):
    (project_root / "docs" / "project").mkdir()
    repository = ProjectRepository(project_root)
    head = git(project_root, "rev-parse", "HEAD")
    repository.initialize_status("active.md", 1, 1, head[:7])
    with pytest.raises(ProjectStateError) as missing:
        repository.confirm_task_completed("", None)
    assert missing.value.code == "invalid_evidence"
    with pytest.raises(ProjectStateError) as invalid:
        repository.confirm_task_completed("tests passed", "main^{tree}")
    assert invalid.value.code == "invalid_commit"
    status = repository.confirm_task_completed("3 focused tests passed", head)
    assert status["state"] == "completed"
    assert status["evidence"] == ["3 focused tests passed"]
```

- [ ] **Step 2: Run the two tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py -q
```

Expected: failures identify missing `record_decision` and `confirm_task_completed`.

- [ ] **Step 3: Implement append-only decisions and confirmation**

Add these methods:

```python
    def _utc_text(self) -> str:
        return self.clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def record_decision(
        self, title: str, decision: str, rationale: str, supersedes: str | None = None
    ) -> dict[str, str]:
        values = {"title": title.strip(), "decision": decision.strip(), "rationale": rationale.strip()}
        if not all(values.values()):
            raise ProjectStateError("invalid_decision", "Title, decision, and rationale are required")
        path = self._safe_regular_file(Path("docs/project/decisions.md"))
        original = path.read_text(encoding="utf-8")
        raw_ids = re.findall(r"^## P8-DEC-([^\s]+)", original, re.MULTILINE)
        matches = list(DECISION_PATTERN.finditer(original))
        if len(raw_ids) != len(matches):
            raise ProjectStateError("invalid_decision_log", "Decision IDs are malformed")
        numbers = [int(match.group("number")) for match in matches]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ProjectStateError("invalid_decision_log", "Decision IDs must be unique and sequential")
        known = {f"P8-DEC-{number:04d}" for number in numbers}
        if supersedes is not None and supersedes not in known:
            raise ProjectStateError("invalid_decision", "Superseded decision does not exist")
        identifier = f"P8-DEC-{len(numbers) + 1:04d}"
        entry = (
            f"\n## {identifier} — {values['title']}\n\n- Date: {self._utc_text()}\n"
            f"- Supersedes: {supersedes or 'none'}\n\n### Decision\n\n{values['decision']}\n\n"
            f"### Rationale\n\n{values['rationale']}\n"
        )
        self._atomic_write(Path("docs/project/decisions.md"), original.rstrip() + "\n" + entry)
        return {"id": identifier, **values, "supersedes": supersedes or "none"}

    def confirm_task_completed(self, evidence: str, commit: str | None = None) -> dict[str, object]:
        clean_evidence = evidence.strip()
        if not clean_evidence:
            raise ProjectStateError("invalid_evidence", "Completion evidence is required")
        if commit is not None:
            if re.fullmatch(r"[0-9a-fA-F]{7,40}", commit) is None:
                raise ProjectStateError("invalid_commit", "Commit must be a hexadecimal object ID")
            resolved = self._git("rev-parse", "--verify", f"{commit}^{{commit}}", check=False)
            if resolved.returncode != 0:
                raise ProjectStateError("invalid_commit", "Commit does not resolve locally")
            confirmed_commit = resolved.stdout.strip()
        else:
            confirmed_commit = str(self.read_status()["last_confirmed_commit"])
        status = self.read_status()
        status.update({
            "state": "completed", "last_confirmed_commit": confirmed_commit,
            "evidence": [clean_evidence], "updated_at": self._utc_text(),
        })
        self._atomic_write(Path("docs/project/status.md"), self._render_status(status))
        return status
```

- [ ] **Step 4: Create the initial decision journal**

Create `docs/project/decisions.md`:

```markdown
# Poker8 Project Decisions

This journal is append-only. Existing entries are never edited or deleted; a later decision may supersede an earlier ID.

## P8-DEC-0001 — Project MCP authority boundary

- Date: 2026-08-14T00:00:00Z
- Supersedes: none

### Decision

The MCP combines read-only navigation with explicit status and decision management.

### Rationale

Poker8 needs durable project guidance without giving an auxiliary tool authority over product code or Git.
```

- [ ] **Step 5: Run all domain tests and commit**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py -q
git diff --check
```

Expected: `8 passed`; `git diff --check` exits `0`.

```powershell
git add tools/project_mcp/project_state.py tests/project_mcp/test_project_state.py docs/project/decisions.md
git commit -m "feat: add explicit project decisions and completion"
```

### Task 4: Implement deterministic Git alignment and safety gates

**Files:**
- Modify: `tools/project_mcp/project_state.py`
- Modify: `tests/project_mcp/test_project_state.py`
- Create: `tests/project_mcp/test_safety.py`

- [ ] **Step 1: Write failing alignment tests in temporary repositories**

Append tests which initialize status, then exercise unstaged, staged, extra, blocked, untracked, and ignored changes:

```python
def initialize_active_status(repository: ProjectRepository, root: Path) -> None:
    (root / "docs" / "project").mkdir(exist_ok=True)
    repository.initialize_status("active.md", 1, 1, git(root, "rev-parse", "--short", "HEAD"))
    git(root, "add", "docs/project/status.md")
    git(root, "commit", "-m", "status fixture")


def test_alignment_covers_staged_unstaged_blocked_and_ignored(project_root: Path):
    repository = ProjectRepository(project_root)
    initialize_active_status(repository, project_root)
    (project_root / "online").mkdir()
    (project_root / "online" / "config.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(project_root, "add", "online/config.py")
    assert repository.check_current_diff()["result"] == "aligned"

    (project_root / "README.md").write_text("outside task\n", encoding="utf-8")
    assert repository.check_current_diff()["result"] == "warning"

    git(project_root, "add", "README.md")
    git(project_root, "commit", "-m", "tracked fixture")
    (project_root / "online" / "config.py").write_text(
        "def deposit_endpoint():\n    return 'USDT'\n", encoding="utf-8"
    )
    assert repository.check_current_diff()["result"] == "blocked"

    (project_root / "data").mkdir()
    (project_root / "data" / "poker_trainer.sqlite3").write_bytes(b"do not inspect")
    (project_root / ".superpowers").mkdir()
    (project_root / ".superpowers" / "marker").write_text("browser", encoding="utf-8")
    result = repository.check_current_diff()
    assert sorted(result["ignored_user_changes"]) == [
        ".superpowers/", "data/poker_trainer.sqlite3"
    ]


def test_untracked_forbidden_text_is_reported_but_never_opened(project_root: Path):
    repository = ProjectRepository(project_root)
    initialize_active_status(repository, project_root)
    untracked = project_root / "online" / "config.py"
    untracked.parent.mkdir()
    untracked.write_text("deposit_endpoint = 'must not be inspected'\n", encoding="utf-8")
    result = repository.check_current_diff()
    assert result["result"] == "warning"
    assert result["blocked_evidence"] == []
```

- [ ] **Step 2: Write fail-closed filesystem tests**

Create `tests/project_mcp/test_safety.py` using the fixture helpers from `test_project_state.py`:

```python
from pathlib import Path
import os

import pytest

from tools.project_mcp.project_state import ProjectRepository, ProjectStateError
from tests.project_mcp.test_project_state import git


def make_project(tmp_path: Path) -> Path:
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "tests@example.invalid")
    git(tmp_path, "config", "user.name", "Poker8 Tests")
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
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "fixture")
    return tmp_path


def test_symlinked_approved_document_is_rejected(tmp_path: Path):
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


def test_write_boundary_rejects_source_and_preserves_atomic_original(tmp_path: Path):
    root = make_project(tmp_path)
    repository = ProjectRepository(root)
    with pytest.raises(ProjectStateError) as forbidden:
        repository._atomic_write(Path("app/main.py"), "changed")
    assert forbidden.value.code == "write_forbidden"

    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    status = project_dir / "status.md"
    status.write_text("original", encoding="utf-8")

    def fail_replace(source, target):
        raise OSError("forced")

    failing = ProjectRepository(root, replace=fail_replace)
    with pytest.raises(ProjectStateError) as failed:
        failing._atomic_write(Path("docs/project/status.md"), "replacement")
    assert failed.value.code == "write_failed"
    assert status.read_text(encoding="utf-8") == "original"


def test_no_public_api_reads_env_or_sqlite(tmp_path: Path):
    root = make_project(tmp_path)
    (root / ".env").write_text("TOKEN=secret", encoding="utf-8")
    (root / "data").mkdir()
    (root / "data" / "poker.sqlite3").write_bytes(b"database-secret")
    repository = ProjectRepository(root)
    assert all(".env" not in name for name in repository.spec_catalogue())
    assert all("sqlite" not in name for name in repository.plan_catalogue())


def test_corrupt_status_and_decision_ids_fail_closed(tmp_path: Path):
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


def test_symlinked_manager_target_is_rejected(tmp_path: Path):
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
        repository._atomic_write(Path("docs/project/status.md"), "replacement")
    assert error.value.code == "unsafe_path"
    assert outside.read_text(encoding="utf-8") == "outside"
```

- [ ] **Step 3: Run alignment and safety tests and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py tests/project_mcp/test_safety.py -q
```

Expected: alignment tests fail because `check_current_diff` is absent; safety tests expose any incomplete fail-closed path handling.

- [ ] **Step 4: Implement the fixed Git reader, ignored paths, and direct blocker evidence**

Add constants and methods:

```python
IGNORED_USER_PATTERNS = (
    re.compile(r"^data/.*\.sqlite3(?:-wal|-shm)?$"),
    re.compile(r"^\.superpowers(?:/|$)"),
)
RUNTIME_PREFIXES = ("app/", "online/", "static/")
FORBIDDEN_ADDITION = re.compile(
    r"(?i)\b(CASH_USDT|deposit|withdraw(?:al)?|KYC|blockchain|play[-_ ]to[-_ ]cash)\b"
)


    def _normal_path(self, raw: str) -> str:
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
        return {self._normal_path(line) for line in self._git(*args).stdout.splitlines() if line.strip()}

    def _untracked(self) -> set[str]:
        paths: set[str] = set()
        for line in self._git("status", "--porcelain=v1").stdout.splitlines():
            if line.startswith("?? "):
                paths.add(self._normal_path(line[3:]))
        return paths

    def _ignored_user_path(self, path: str) -> bool:
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
        status = self.read_status()
        task = self._task(str(status["active_plan"]), int(status["active_task"]))
        unstaged = self._name_only(False)
        staged = self._name_only(True)
        untracked = self._untracked()
        all_paths = unstaged | staged | untracked
        ignored = sorted(path for path in all_paths if self._ignored_user_path(path))
        relevant = all_paths - set(ignored)
        expected = set(task.files)
        extra = sorted(relevant - expected)
        missing = sorted(expected - relevant)
        evidence: list[dict[str, str]] = []
        for patch in (self._patch(unstaged - set(ignored), False), self._patch(staged - set(ignored), True)):
            current_path = ""
            for line in patch.splitlines():
                if line.startswith("+++ b/"):
                    current_path = self._normal_path(line[6:])
                elif (
                    current_path.startswith(RUNTIME_PREFIXES)
                    and line.startswith("+") and not line.startswith("+++")
                    and (match := FORBIDDEN_ADDITION.search(line[1:]))
                ):
                    evidence.append({"path": current_path, "term": match.group(0), "line": line[1:]})
        if evidence:
            result = "blocked"
        elif extra or missing or untracked - set(ignored):
            result = "warning"
        else:
            result = "aligned"
        return {
            "result": result, "active_task_files": sorted(expected),
            "staged": sorted(staged - set(ignored)), "unstaged": sorted(unstaged - set(ignored)),
            "untracked": sorted(untracked - set(ignored)), "extra": extra, "missing": missing,
            "blocked_evidence": evidence, "ignored_user_changes": ignored,
            "limitations": "Deterministic path and added-line checks; semantic review remains required.",
        }

    def get_project_overview(self) -> dict[str, object]:
        status = self.read_status()
        task = self._task(str(status["active_plan"]), int(status["active_task"]))
        alignment = self.check_current_diff()
        return {
            "objective": "Deliver the approved multiplayer play-money Poker8 MVP.",
            "excluded": ["real-money runtime", "USDT payments", "KYC", "blockchain"],
            "active_plan": status["active_plan"], "active_task": status["active_task"],
            "task_title": task.title, "state": status["state"],
            "last_confirmed_commit": status["last_confirmed_commit"],
            "evidence": status["evidence"],
            "branch": self._git("branch", "--show-current").stdout.strip(),
            "git": {
                "result": alignment["result"], "staged_count": len(alignment["staged"]),
                "unstaged_count": len(alignment["unstaged"]),
                "untracked_count": len(alignment["untracked"]),
                "ignored_user_changes": alignment["ignored_user_changes"],
            },
            "next": self.get_next_step(),
        }
```

- [ ] **Step 5: Run the safety gate and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_project_state.py tests/project_mcp/test_safety.py -q
git diff --check
git add tools/project_mcp/project_state.py tests/project_mcp/test_project_state.py tests/project_mcp/test_safety.py
git commit -m "feat: check project MCP scope safely"
```

Expected: all project-state and safety tests pass; formatting check exits `0`.

### Task 5: Expose the approved MCP resources and tools

**Files:**
- Create: `tools/project_mcp/server.py`
- Create: `tests/project_mcp/test_server.py`

- [ ] **Step 1: Install the isolated SDK for development**

Run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r tools/project_mcp/requirements.txt
```

Expected: an MCP `2.x` version installs successfully; the root `requirements.txt` and Git worktree remain unchanged.

- [ ] **Step 2: Write the failing in-memory MCP contract test**

Create `tests/project_mcp/test_server.py`:

```python
from pathlib import Path

import pytest
from mcp import Client

from tools.project_mcp.server import build_server
from tools.project_mcp.project_state import ProjectRepository
from tests.project_mcp.test_project_state import git
from tests.project_mcp.test_safety import make_project


@pytest.fixture
def anyio_backend():
    return "asyncio"


def ready_project(tmp_path: Path) -> Path:
    root = make_project(tmp_path)
    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    repository = ProjectRepository(root)
    repository.initialize_status("active.md", 1, 1, git(root, "rev-parse", "--short", "HEAD"))
    (project_dir / "decisions.md").write_text(
        "# Poker8 Project Decisions\n\nEntries are append-only.\n", encoding="utf-8"
    )
    git(root, "add", "docs/project")
    git(root, "commit", "-m", "manager fixture")
    return root


@pytest.mark.anyio
async def test_server_lists_exact_tools_and_reads_resources(tmp_path: Path):
    root = ready_project(tmp_path)
    async with Client(build_server(root), raise_exceptions=True) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "get_project_overview", "get_next_step", "check_current_diff",
            "set_active_task", "confirm_task_completed", "record_decision",
        }
        resources = await client.list_resources()
        assert {str(resource.uri) for resource in resources.resources} == {
            "poker8://project/overview", "poker8://project/status",
            "poker8://project/decisions",
        }
        templates = await client.list_resource_templates()
        assert {template.uri_template for template in templates.resource_templates} == {
            "poker8://specs/{name}", "poker8://plans/{name}",
        }
        overview = await client.call_tool("get_project_overview", {})
        assert overview.structured_content["ok"] is True
        assert overview.structured_content["data"]["active_task"] == 1
        plan = await client.read_resource("poker8://plans/active.md")
        assert "### Task 1: Safe" in plan.contents[0].text


@pytest.mark.anyio
async def test_manager_tool_errors_are_structured_and_do_not_write_source(tmp_path: Path):
    root = ready_project(tmp_path)
    before = git(root, "status", "--porcelain=v1")
    async with Client(build_server(root), raise_exceptions=True) as client:
        result = await client.call_tool(
            "set_active_task",
            {"plan": "../../.env", "task_number": 1, "step_number": 1, "state": "planned"},
        )
        assert result.structured_content == {
            "ok": False,
            "error": {"code": "invalid_plan", "message": "Unknown plan: ../../.env"},
        }
    assert git(root, "status", "--porcelain=v1") == before


@pytest.mark.anyio
async def test_valid_manager_tool_changes_only_status(tmp_path: Path):
    root = ready_project(tmp_path)
    async with Client(build_server(root), raise_exceptions=True) as client:
        result = await client.call_tool(
            "set_active_task",
            {"plan": "active.md", "task_number": 1, "step_number": 1, "state": "in_progress"},
        )
        assert result.structured_content["ok"] is True
    assert git(root, "diff", "--name-only") == "docs/project/status.md"
```

- [ ] **Step 3: Run the MCP contract test and verify RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_server.py -q
```

Expected: collection fails because `tools.project_mcp.server` does not exist.

- [ ] **Step 4: Implement the thin SDK v2 adapter**

Create `tools/project_mcp/server.py`. Keep `mcp.run()` behind the main guard, return Python dictionaries for structured output, and send diagnostics only through `logging` on stderr. Read-only resource failures are serialized as diagnostic JSON so a corrupt status file does not hide the remaining resources:

```python
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
else:
    from project_state import ProjectRepository, ProjectStateError


LOGGER = logging.getLogger("poker8_project")


def _result(call: Callable[[], object]) -> dict[str, object]:
    try:
        return {"ok": True, "data": call()}
    except ProjectStateError as exc:
        return {"ok": False, "error": {"code": exc.code, "message": str(exc)}}


def _resource_result(call: Callable[[], object]) -> str:
    try:
        return json.dumps({"ok": True, "data": call()}, ensure_ascii=False, default=str)
    except ProjectStateError as exc:
        return json.dumps(
            {"ok": False, "error": {"code": exc.code, "message": str(exc)}},
            ensure_ascii=False,
        )


def build_server(root: Path) -> MCPServer:
    repository = ProjectRepository(root)
    mcp = MCPServer("poker8_project")

    @mcp.resource("poker8://project/overview")
    def project_overview_resource() -> str:
        return _resource_result(repository.get_project_overview)

    @mcp.resource("poker8://project/status")
    def project_status_resource() -> str:
        return repository._safe_regular_file(Path("docs/project/status.md")).read_text(encoding="utf-8")

    @mcp.resource("poker8://project/decisions")
    def project_decisions_resource() -> str:
        return repository._safe_regular_file(Path("docs/project/decisions.md")).read_text(encoding="utf-8")

    @mcp.resource("poker8://specs/{name}")
    def approved_spec(name: str) -> str:
        return repository.read_spec(name)

    @mcp.resource("poker8://plans/{name}")
    def approved_plan(name: str) -> str:
        return repository.read_plan(name)

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

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
    def set_active_task(
        plan: str,
        task_number: int,
        step_number: int = 1,
        state: Literal["planned", "in_progress", "awaiting_confirmation"] = "planned",
        note: str = "",
    ) -> dict[str, object]:
        """Explicitly update only the canonical project status pointer."""
        return _result(lambda: repository.set_active_task(plan, task_number, step_number, state, note))

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False))
    def confirm_task_completed(evidence: str, commit: str | None = None) -> dict[str, object]:
        """Explicitly mark the active task complete with human-provided evidence."""
        return _result(lambda: repository.confirm_task_completed(evidence, commit))

    @mcp.tool(annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False))
    def record_decision(
        title: str, decision: str, rationale: str, supersedes: str | None = None
    ) -> dict[str, object]:
        """Append one immutable numbered decision to the project journal."""
        return _result(lambda: repository.record_decision(title, decision, rationale, supersedes))

    return mcp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poker8 project navigator MCP")
    parser.add_argument("--root", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = parse_args()
    build_server(args.root).run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run MCP and safety tests and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_server.py tests/project_mcp/test_safety.py -q
git diff --check
git add tools/project_mcp/server.py tests/project_mcp/test_server.py
git commit -m "feat: expose Poker8 project MCP"
```

Expected: all selected tests pass; no output-format errors.

### Task 6: Prove the real stdio process and document installation

**Files:**
- Create: `tests/project_mcp/test_stdio.py`
- Create: `tools/project_mcp/install.ps1`
- Create: `tools/project_mcp/README.md`

- [ ] **Step 1: Write the failing child-process smoke test**

Create `tests/project_mcp/test_stdio.py`:

```python
from pathlib import Path
import sys

import pytest
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

from tools.project_mcp.project_state import ProjectRepository
from tests.project_mcp.test_project_state import git
from tests.project_mcp.test_safety import make_project


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_actual_stdio_server_lists_and_calls_tools(tmp_path: Path):
    root = make_project(tmp_path)
    project_dir = root / "docs" / "project"
    project_dir.mkdir()
    repository = ProjectRepository(root)
    repository.initialize_status("active.md", 1, 1, git(root, "rev-parse", "--short", "HEAD"))
    (project_dir / "decisions.md").write_text(
        "# Poker8 Project Decisions\n\nEntries are append-only.\n", encoding="utf-8"
    )
    server_path = Path(__file__).parents[2] / "tools" / "project_mcp" / "server.py"
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path.resolve()), "--root", str(root.resolve())],
    )
    async with Client(stdio_client(parameters)) as client:
        tools = await client.list_tools()
        assert "get_project_overview" in {tool.name for tool in tools.tools}
        result = await client.call_tool("get_project_overview", {})
        assert result.structured_content["ok"] is True
```

- [ ] **Step 2: Run the stdio smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_stdio.py -q
```

Expected: `1 passed`; any import-time stdout noise instead causes a protocol failure.

- [ ] **Step 3: Create the refusal-safe Codex installer**

Create `tools/project_mcp/install.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..\..")).Path
$python = (Join-Path $repoRoot ".venv\Scripts\python.exe")
$server = (Join-Path $scriptRoot "server.py")
$requirements = (Join-Path $scriptRoot "requirements.txt")

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Poker8 virtual environment is missing: $python"
}

$existing = & codex mcp get poker8_project 2>$null
if ($LASTEXITCODE -eq 0) {
    throw "MCP registration 'poker8_project' already exists; remove it explicitly before reinstalling."
}

& $python -m pip install -r $requirements
if ($LASTEXITCODE -ne 0) {
    throw "MCP dependency installation failed."
}

& codex mcp add poker8_project -- $python $server --root $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Codex MCP registration failed."
}

& codex mcp get poker8_project
if ($LASTEXITCODE -ne 0) {
    throw "Codex could not verify the new MCP registration."
}
```

- [ ] **Step 4: Document the exact operator contract**

Create `tools/project_mcp/README.md` with these sections and commands:

```markdown
# Poker8 Project Navigator MCP

Local stdio MCP for approved Poker8 plans, project status, decisions, and read-only Git alignment.

## Install

From the repository root:

```powershell
.\tools\project_mcp\install.ps1
```

The installer uses the existing `.venv`, installs only `tools/project_mcp/requirements.txt`, refuses to replace an existing `poker8_project` entry, and registers absolute paths.

## Verify

```powershell
codex mcp get poker8_project
.\.venv\Scripts\python.exe -m pytest tests/project_mcp -q
```

Open a new Codex task after registration. A running task does not acquire a new MCP tool inventory dynamically.

## Authority

The server reads approved Markdown and fixed Git status/diff commands. It may write only `docs/project/status.md` and `docs/project/decisions.md` after an explicit manager-tool call. It cannot edit product code, run tests or servers, read `.env` or SQLite content, or mutate Git.

## Remove

```powershell
codex mcp remove poker8_project
```
```

- [ ] **Step 5: Run stdio and documentation checks and commit**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp/test_stdio.py -q
git diff --check
git add tests/project_mcp/test_stdio.py tools/project_mcp/install.ps1 tools/project_mcp/README.md
git commit -m "docs: add project MCP installation workflow"
```

Expected: stdio smoke passes and the formatting check exits `0`.

### Task 7: Run the release gate and register the MCP

**Files:**
- Verify: `tools/project_mcp/project_state.py`
- Verify: `tools/project_mcp/server.py`
- Verify: `tools/project_mcp/install.ps1`
- Verify: `tools/project_mcp/README.md`
- Verify: `docs/project/status.md`
- Verify: `docs/project/decisions.md`
- Verify: `tests/project_mcp/test_project_state.py`
- Verify: `tests/project_mcp/test_safety.py`
- Verify: `tests/project_mcp/test_server.py`
- Verify: `tests/project_mcp/test_stdio.py`

- [ ] **Step 1: Run the full Project MCP suite**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/project_mcp -q
```

Expected: every Project MCP test passes with no skip except a Windows symlink test when the host denies symlink creation.

- [ ] **Step 2: Run repository regression evidence without touching unrelated failures**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Expected before Online Foundation Task 1: Project MCP tests pass and the only legacy failure remains `tests/test_table_store.py::test_six_bot_seats_can_be_activated`. If any other test fails, stop and fix only an MCP-caused regression.

- [ ] **Step 3: Audit the authority boundary**

Run:

```powershell
rg -n "shell=True|\.env|sqlite3|git (add|commit|checkout|switch|merge|push)|uvicorn|subprocess\.Popen" tools/project_mcp tests/project_mcp
git diff --check
git status --short
```

Expected: no `shell=True`, Git mutation, server launch, secret read, or SQLite content read in `tools/project_mcp`; any `.env` and `sqlite3` matches occur only in ignore classification, refusal tests, or documented boundaries. `git status` still shows the user-owned `data/poker_trainer.sqlite3` and `.superpowers/` changes unstaged.

- [ ] **Step 4: Install and verify the Codex registration**

Run:

```powershell
.\tools\project_mcp\install.ps1
codex mcp get poker8_project
```

Expected: an enabled stdio registration named `poker8_project` whose command is the absolute `.venv\Scripts\python.exe` and whose arguments contain the absolute `server.py` and repository `--root` paths.

- [ ] **Step 5: Verify from a new Codex task**

Open a new task and call `get_project_overview`, `get_next_step`, and `check_current_diff`. Expected: Foundation Task 1 Step 1 is active, the last confirmed commit is `8d20207`, and `data/poker_trainer.sqlite3` plus `.superpowers/` appear only under `ignored_user_changes`.

- [ ] **Step 6: Commit any verification-only corrections**

If Step 1–5 required source corrections, rerun all of them and commit only the listed MCP files:

```powershell
git add tools/project_mcp docs/project tests/project_mcp
git commit -m "fix: harden Poker8 project MCP"
```

If no correction was required, do not create an empty commit.

## Completion gate

The implementation is complete only when the Project MCP suite and real stdio smoke pass, Codex reports the expected absolute registration, a new task can call the tools, initial navigation points to Online Foundation Task 1 Step 1, and the authority audit proves that only the two manager documents are writable.
