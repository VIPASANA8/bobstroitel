# Poker8 Project Navigator MCP

Local stdio MCP for the approved Poker8 plans, project status, decision journal,
and read-only Git alignment. It is a navigator and an explicit project-state
manager; it is not a coding agent or a game server.

## Install

From the repository root, run:

```powershell
.\tools\project_mcp\install.ps1
```

The installer resolves absolute paths, uses the existing `.venv`, installs only
`tools/project_mcp/requirements.txt` (`mcp>=2,<3`), refuses to overwrite an
existing `poker8_project` registration, and verifies the registration with
`codex mcp get`. It does not create a virtual environment or modify the game's
root requirements.

If an existing registration is found, remove it deliberately and rerun the
installer:

```powershell
codex mcp remove poker8_project
```

## Verify

```powershell
codex mcp get poker8_project
.\.venv\Scripts\python.exe -m pytest tests/project_mcp -q
```

Open a new Codex task after registration. A running task does not acquire a new
MCP tool inventory dynamically. In that new task, call `get_project_overview`,
`get_next_step`, and `check_current_diff` to confirm the active Foundation task
and the ignored user-owned database artifacts.

## Resources

The server exposes only validated documents from the repository catalogue:

| URI | Contents |
| --- | --- |
| `poker8://project/overview` | Current objective, active task, state, Git summary, and next step (JSON) |
| `poker8://project/status` | Full `docs/project/status.md` Markdown |
| `poker8://project/decisions` | Full `docs/project/decisions.md` Markdown |
| `poker8://specs/{name}` | One discovered Markdown specification |
| `poker8://plans/{name}` | One discovered Markdown plan |

Names are selected from the server's startup catalogue; traversal and unknown
names return a structured `invalid_resource` diagnostic. `.env`, SQLite, and
other secret-looking documents are never opened.

## Tools

Read-only navigation:

- `get_project_overview()` — objective, exclusions, active plan/task, state,
  evidence, branch, Git counts, ignored user changes, and next recommendation.
- `get_next_step()` — exact active task, declared files, current unchecked step,
  plan commands, and blocking status conditions.
- `check_current_diff()` — fixed Git status/diff inspection aligned with the
  active task; returns `aligned`, `warning`, or deterministic `blocked` evidence.

Explicit manager operations:

- `set_active_task(plan, task_number, step_number=1, state="planned", note="")`
  — updates only `docs/project/status.md` and never edits plan checkboxes.
- `confirm_task_completed(evidence, commit=None)` — requires human evidence,
  optionally validates a local commit, and marks the active task completed.
- `record_decision(title, decision, rationale, supersedes=None)` — appends one
  monotonic entry to `docs/project/decisions.md`.

Successful calls return `{ "ok": true, "data": ... }`. Expected domain errors
return `{ "ok": false, "error": { "code": ..., "message": ... } }` without
exposing unapproved file contents.

## Authority and safety

The repository must be a Git worktree containing both approved anchor
specifications. The MCP uses fixed Git argument arrays with `shell=False` and a
short timeout. It never runs tests, servers, migrations, arbitrary commands, or
LLM calls; it cannot stage, commit, switch, merge, push, or otherwise mutate Git.

Source code, tests, specs, plans, `.env`, databases, credentials, and product
files are read-only or outside the readable boundary. The only writable paths
are the two manager documents:

- `docs/project/status.md` — complete validated state document;
- `docs/project/decisions.md` — append-only decision journal.

Manager writes are explicit, fail closed on malformed state, protected by a
process-local lock, and performed through a temporary sibling file followed by
flush, `fsync`, and atomic replace. Existing user-owned `data/*.sqlite3`, WAL/
SHM files, and `.superpowers/` changes are reported separately and do not affect
alignment.

## Remove

```powershell
codex mcp remove poker8_project
```

Removing the registration does not change project files or the isolated virtual
environment. Reinstall only after checking the absolute paths reported by
`codex mcp get poker8_project`.
