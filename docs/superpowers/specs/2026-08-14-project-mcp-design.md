# Poker8 Project Navigator MCP Design

**Date:** 2026-08-14
**Status:** Approved design
**Scope:** Local project guidance and explicitly confirmed project-status management

## 1. Objective

Build a project-local MCP server that helps Codex follow Poker8's approved Product Vision, Online MVP specification, implementation roadmap, and current task without giving the server authority to modify product code or Git.

The MCP combines two roles:

1. **Navigator:** reads specifications, plans, project status, decision history, and Git state; identifies the next approved step; and reports divergence from the active task.
2. **Project manager:** updates only the dedicated status and decision-log files after explicit tool calls.

Analysis never changes project status automatically. Completion always requires an explicit confirmation call with evidence.

## 2. Product boundaries

### Included

- Local stdio MCP server registered in Codex as `poker8_project`.
- Read-only access to approved specifications and implementation plans.
- Read-only inspection of fixed Git status and diff commands.
- A concise project overview and deterministic next-step recommendation.
- Active-task scope checking against the task's declared file list.
- Detection of explicit Online MVP boundary violations.
- Explicit updates to `docs/project/status.md`.
- Append-only decisions in `docs/project/decisions.md`.
- Installation, registration, unit, integration, in-memory MCP, and stdio smoke tests.

### Excluded

- Editing source code, tests, specifications, implementation plans, or Git metadata.
- Running tests, application servers, migrations, formatters, or arbitrary commands.
- Staging, committing, switching branches, merging, pushing, or opening pull requests.
- Reading `.env`, Telegram bot tokens, credentials, database content, or other secrets.
- Semantic code review or LLM calls inside the MCP server.
- Replacing the existing `senior_reviewer` MCP.
- Automatically declaring tasks complete based on Git or test output.
- Remote HTTP transport, authentication, hosting, telemetry, or multi-project support.

## 3. Architecture

The implementation lives inside the Poker8 repository:

```text
tools/project_mcp/
├── server.py
├── project_state.py
├── install.ps1
├── README.md
└── requirements.txt

docs/project/
├── status.md
└── decisions.md

tests/project_mcp/
├── test_project_state.py
├── test_safety.py
├── test_server.py
└── test_stdio.py
```

Responsibilities:

- `server.py` creates the MCP server and registers resource and tool handlers.
- `project_state.py` owns project-root validation, approved-document discovery, plan parsing, Git reads, alignment checks, status serialization, decision IDs, and the two allowed write operations.
- `install.ps1` installs the isolated tool dependency into the existing project virtual environment and registers the absolute stdio command with Codex.
- `README.md` documents installation, verification, available capabilities, write boundaries, and removal.
- `status.md` is the canonical current-project pointer.
- `decisions.md` is the append-only decision log.

The server uses the official MCP Python SDK v2 and the local stdio transport. Its dependency is isolated in `tools/project_mcp/requirements.txt` as:

```text
mcp>=2,<3
```

The game application's production `requirements.txt` remains unchanged.

## 4. Project root and source documents

`install.ps1` resolves the repository root and registers the server with an explicit absolute `--root` argument. `server.py` refuses to start when the root is not a Git worktree or does not contain the two approved anchor documents:

- `docs/superpowers/specs/2026-08-14-online-network-mvp-design.md`
- `docs/superpowers/specs/2026-08-14-poker8-product-vision.md`

The roadmap and child plans are discovered only under `docs/superpowers/plans/`. Arbitrary client paths are never accepted. Resource identifiers use validated document names returned by the server's own catalogue.

The MCP treats specifications and plans as immutable source material. Changes to them can be observed in Git and reported, but the MCP has no tool that writes them.

## 5. MCP resources

The server exposes:

| Resource | Purpose |
|---|---|
| `poker8://project/overview` | Current objective, active plan/task, task state, latest confirmed commit, and concise Git summary |
| `poker8://project/status` | Full human-readable status document |
| `poker8://project/decisions` | Full decision journal |
| `poker8://specs/{name}` | One approved specification selected from the discovered catalogue |
| `poker8://plans/{name}` | One approved roadmap or implementation plan selected from the discovered catalogue |

Resource templates validate `{name}` against the catalogue. They do not convert names into unchecked filesystem paths.

## 6. MCP tools

### `get_project_overview()`

Returns:

- Online MVP objective and explicit exclusions;
- active plan path and task number;
- task title and state;
- latest confirmed commit and evidence summary;
- current branch;
- staged, unstaged, and untracked path counts;
- next recommended action.

It performs no writes.

### `get_next_step()`

Reads the active plan and returns the exact active task title, its declared files, the checklist step identified by `active_step`, relevant commands as quoted plan text, and blocking status conditions. If the active task is completed, it recommends the next numbered task in the same plan. It never advances status itself.

### `check_current_diff()`

Runs fixed Git commands without a shell:

```text
git status --porcelain=v1
git diff --name-only
git diff --cached --name-only
```

After validating the tracked paths returned by those commands, it invokes `git diff --no-ext-diff --unified=0 --` and its cached equivalent with the validated paths as separate subprocess arguments.

It compares changed paths with the active task's declared `Files` section and returns one result:

- `aligned`: all relevant project changes are within the active task's declared files;
- `warning`: additional files, plan/spec changes, missing expected files, or an ambiguity require review;
- `blocked`: deterministic evidence shows an explicit MVP boundary violation.

Blockers require direct patch evidence of a runtime deposit, withdrawal, KYC, blockchain, cash-wallet, PLAY-to-cash conversion, or payment endpoint, or a write outside the two manager files attempted through MCP. Broader semantic concerns, including possible client authority over game results, are reported as `warning` with context for agent review rather than being presented as deterministic proof.

The tool returns evidence and relevant requirements rather than claiming a full semantic code review. Patch content is requested only for tracked, validated, non-secret paths returned by Git. Untracked project files produce `warning` and are never opened by the checker. Existing user-owned `data/*.sqlite3`, `*.sqlite3-wal`, `*.sqlite3-shm`, and `.superpowers/` paths appear in an `ignored_user_changes` field and do not affect the alignment result.

### `set_active_task(plan, task_number, step_number, state, note)`

Validates `plan` against the discovered plan catalogue and verifies that both `### Task {task_number}` and the numbered checklist step exist. It updates only `docs/project/status.md`, stores the optional note, and clears task-completion evidence when switching tasks. `step_number` defaults to `1`; `state` accepts `planned`, `in_progress`, or `awaiting_confirmation`, but never `completed`. It does not edit plan checkboxes.

### `confirm_task_completed(evidence, commit)`

Requires non-empty human-provided evidence. When `commit` is supplied, it must resolve in the current repository. The tool records the active task as `completed`, stores evidence and the confirmed commit, and calculates the next recommendation without switching tasks automatically.

The tool does not infer test success, inspect remote CI, or modify Git.

### `record_decision(title, decision, rationale, supersedes)`

Requires non-empty title, decision, and rationale. It appends one numbered entry to `docs/project/decisions.md`. When `supersedes` is supplied, the referenced decision ID must exist. Existing entries are never edited or deleted.

## 7. Status document format

`docs/project/status.md` remains readable in Markdown and contains one machine-managed JSON comment:

```markdown
<!-- poker8-project-state
{"schema_version":1,"active_plan":"2026-08-14-online-mvp-foundation.md","active_task":1,"active_step":1,"state":"planned","last_confirmed_commit":"8d20207","evidence":[],"note":"","updated_at":"2026-08-14T00:00:00Z"}
-->

# Poker8 Project Status

## Current focus

Human-readable summary generated from the state above.
```

Allowed task states are:

- `planned`;
- `in_progress`;
- `awaiting_confirmation`;
- `completed`.

The MCP rewrites the complete status document from validated state. If the JSON block is missing, duplicated, malformed, or uses an unsupported schema version, write tools fail closed and leave the file unchanged.

The initial status points to Foundation Task 1, Step 1 as `planned`, because the approved planning work is complete and the known legacy 7-player fixture is the first implementation step.

## 8. Decision log format

`docs/project/decisions.md` begins with a short write-policy notice. Entries use monotonic identifiers:

```markdown
## P8-DEC-0001 — Project MCP authority boundary

- Date: 2026-08-14T00:00:00Z
- Supersedes: none

### Decision

The MCP combines read-only navigation with explicit status and decision management.

### Rationale

The project needs durable guidance without giving an auxiliary tool authority over product code or Git.
```

The next ID is calculated from valid existing headings. Duplicate or malformed IDs cause the append operation to fail without changing the file.

## 9. Safety model

The MCP is fail-closed:

- The repository root is resolved once at startup.
- Approved readable paths are constructed by the server, resolved, and checked for containment.
- Readable and writable targets must be regular files and not symbolic links.
- No tool accepts an arbitrary path, command, Git ref expression, or environment-variable name.
- Git commands use `subprocess.run` with fixed argument arrays, `shell=False`, a short timeout, and the validated repository root as `cwd`.
- `.env`, secret-looking files, and SQLite contents are never read. Direct filesystem reads are limited to approved documents; tracked source patches are read only through filtered Git diff commands.
- Writes are restricted to the two exact manager paths.
- Writes use a temporary sibling file, flush, `fsync`, and `os.replace`.
- A process-local lock serializes manager writes.
- stdout is reserved for MCP protocol messages; diagnostic logs go to stderr.
- Exceptions return structured, non-secret errors and do not include file contents outside the approved scope.

The stdio server exposes no network listener and requires no authentication because Codex launches it locally as a child process.

## 10. Installation and lifecycle

`install.ps1`:

1. resolves the repository root;
2. verifies `.venv/Scripts/python.exe` exists;
3. installs `tools/project_mcp/requirements.txt` with that interpreter;
4. refuses to overwrite an existing `poker8_project` registration;
5. registers the server through `codex mcp add poker8_project -- <python> <server.py> --root <repo>`;
6. verifies the result with `codex mcp get poker8_project`.

The script does not create a Python environment, alter the game requirements, or modify another MCP registration. Removal is documented as:

```powershell
codex mcp remove poker8_project
```

A newly registered MCP is verified from a new Codex task because an already running task does not dynamically gain a new tool inventory.

## 11. Error handling

- Missing anchor documents: startup fails with an actionable stderr message.
- Unknown plan or task: tool returns `invalid_plan` or `invalid_task`; no write occurs.
- Corrupt status: manager tools return `invalid_status`; read-only resources still expose a diagnostic overview where possible.
- Corrupt decision IDs: `record_decision` returns `invalid_decision_log`; no append occurs.
- Git unavailable or timed out: overview and diff tools return `git_unavailable`; document resources remain usable.
- Commit cannot be resolved: completion returns `invalid_commit`; status remains unchanged.
- Atomic replace fails: the original file remains authoritative and the tool returns `write_failed`.

## 12. Verification strategy

### Unit tests

- Discover only approved spec and plan Markdown files.
- Parse exact numbered tasks and their `Files` sections.
- Return the first unconfirmed step and next numbered task.
- Parse and render the status state without losing fields.
- Allocate sequential decision IDs.
- Reject unsupported state values and malformed manager files.

### Safety tests

- Reject path traversal and unlisted resource names.
- Reject symlinked readable or writable targets.
- Never read `.env` or SQLite contents.
- Refuse every write target except the two exact manager files.
- Leave the original file intact when an atomic write is forced to fail.

### Git integration tests

Use temporary Git repositories to prove:

- active-task files produce `aligned`;
- extra files produce `warning`;
- explicit forbidden runtime surfaces produce `blocked` with evidence;
- staged and unstaged paths are both considered;
- user-owned SQLite and `.superpowers/` paths are reported separately and ignored for alignment;
- completion accepts a real local commit and rejects an unknown commit.

### MCP contract tests

Use the official SDK's in-memory client to assert:

- the five resource families are discoverable and readable;
- all six tools are discoverable;
- `get_project_overview` and `get_next_step` return structured content;
- manager tools update only their allowed temporary-repository files.

Launch the actual server as a stdio child process for one smoke test that initializes MCP, lists tools, calls `get_project_overview`, and closes cleanly without non-protocol stdout.

### Installation verification

- `pytest tests/project_mcp -q` passes.
- `codex mcp get poker8_project` reports an enabled stdio server with the expected Python executable, server path, and root.
- A new Codex task can list and call `poker8_project` tools.

## 13. Completion criterion

The Project Navigator MCP is complete when:

1. all project-MCP tests pass;
2. the server is registered and callable from a new Codex task;
3. overview and next-step tools point to Foundation Task 1 initially;
4. alignment checking reports existing user database artifacts separately;
5. explicit status and decision calls update only their approved files;
6. the server has no execution, source-editing, secret-reading, or Git-mutation capability.

## 14. References

- MCP Python SDK v2: <https://github.com/modelcontextprotocol/python-sdk>
- Codex MCP management uses `codex mcp add`, `codex mcp get`, `codex mcp list`, and `codex mcp remove` as verified by the installed Codex CLI.
