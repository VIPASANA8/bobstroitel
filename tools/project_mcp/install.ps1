$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptRoot "..\..")).Path
$python = (Join-Path $repoRoot ".venv\Scripts\python.exe")
$server = (Join-Path $scriptRoot "server.py")
$requirements = (Join-Path $scriptRoot "requirements.txt")

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Poker8 virtual environment is missing: $python"
}
if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
    throw "Project MCP server is missing: $server"
}
if (-not (Test-Path -LiteralPath $requirements -PathType Leaf)) {
    throw "Project MCP requirements are missing: $requirements"
}

# A successful lookup means the operator has an existing registration.  Do
# not overwrite it: removal is an explicit, reversible operator action.
if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Codex CLI is not available on PATH."
}

# This lookup is expected to return non-zero when installing for the first
# time.  Temporarily relax PowerShell's native-command error promotion so that
# stderr cannot terminate the script before LASTEXITCODE is captured.
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $null = & codex mcp get poker8_project 2>$null
    $existingExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}
if ($existingExitCode -eq 0) {
    throw "MCP registration 'poker8_project' already exists; remove it explicitly before reinstalling."
}

# Some checked-in Poker8 environments intentionally omit pip from the venv.
# Prefer that interpreter's pip, then use the Python launcher to target the
# same venv without silently installing into a global interpreter.
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    $null = & $python -c "import pip" 2>$null
    $hasPip = ($LASTEXITCODE -eq 0)
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($hasPip) {
    & $python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "MCP dependency installation failed."
    }
}
else {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "The project virtual environment has no pip and the 'py' launcher is unavailable."
    }
    & py -m pip --python $python install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        throw "MCP dependency installation via 'py --python' failed."
    }
}

& codex mcp add poker8_project -- $python $server --root $repoRoot
if ($LASTEXITCODE -ne 0) {
    throw "Codex MCP registration failed."
}

& codex mcp get poker8_project
if ($LASTEXITCODE -ne 0) {
    throw "Codex could not verify the new MCP registration."
}
