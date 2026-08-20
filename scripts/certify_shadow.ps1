$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Repo = Split-Path -Parent $PSScriptRoot
$ExpectedBranch = "feat/p0-skills-mcp"
$Hub = Join-Path (Split-Path -Parent $Repo) "CLEMENT_STUDIO_SKILLS_HUB"
$Python = Join-Path $Repo ".venv\Scripts\python.exe"
$Certifier = Join-Path $PSScriptRoot "certify_shadow.py"

Write-Host "============================================================"
Write-Host "CLEMENT — P0-02 SHADOW CERTIFICATION"
Write-Host "MODE=REPOSITORY_SCRIPT"
Write-Host "============================================================"

if (-not (Test-Path -LiteralPath $Repo)) {
    throw "REPOSITORY_NOT_FOUND=$Repo"
}
if (-not (Test-Path -LiteralPath $Hub)) {
    throw "SKILLS_HUB_NOT_FOUND=$Hub"
}
if (-not (Test-Path -LiteralPath $Certifier)) {
    throw "CERTIFIER_NOT_FOUND=$Certifier"
}

Push-Location $Repo
try {
    $Branch = (& git branch --show-current).Trim()
    if ($Branch -ne $ExpectedBranch) {
        throw "BRANCH_MISMATCH=$Branch"
    }

    $Before = @(& git status --porcelain)
    if ($Before.Count -gt 0) {
        $Before | ForEach-Object { Write-Host $_ }
        throw "WORKTREE_NOT_CLEAN_BEFORE"
    }

    & git fetch origin --prune
    if ($LASTEXITCODE -ne 0) {
        throw "GIT_FETCH_FAILED"
    }

    & git pull --ff-only origin $ExpectedBranch
    if ($LASTEXITCODE -ne 0) {
        throw "GIT_PULL_FF_ONLY_FAILED"
    }

    $LocalHead = (& git rev-parse HEAD).Trim()
    $RemoteHead = (& git rev-parse "origin/$ExpectedBranch").Trim()

    Write-Host "BRANCH=$Branch"
    Write-Host "LOCAL_HEAD=$LocalHead"
    Write-Host "REMOTE_HEAD=$RemoteHead"

    if ($LocalHead -ne $RemoteHead) {
        throw "LOCAL_REMOTE_HEAD_MISMATCH"
    }

    if (-not (Test-Path -LiteralPath $Python)) {
        throw "VENV_PYTHON_NOT_FOUND=$Python"
    }

    $PythonVersion = (& $Python -c "import sys; print(sys.version)").Trim()
    Write-Host "VENV_PYTHON=$Python"
    Write-Host "PYTHON_VERSION=$PythonVersion"

    Write-Host "============================================================"
    Write-Host "PHASE=PYTHON_CERTIFIER"
    Write-Host "============================================================"

    & $Python $Certifier --hub-root $Hub
    if ($LASTEXITCODE -ne 0) {
        throw "PYTHON_CERTIFIER_FAILED"
    }

    $After = @(& git status --porcelain)
    if ($After.Count -gt 0) {
        $After | ForEach-Object { Write-Host $_ }
        throw "WORKTREE_NOT_CLEAN_AFTER"
    }

    $FinalHead = (& git rev-parse HEAD).Trim()
    if ($FinalHead -ne $RemoteHead) {
        throw "FINAL_HEAD_MISMATCH=$FinalHead"
    }

    Write-Host "============================================================"
    Write-Host "RESULT=PASS"
    Write-Host "P0_02_GIT_SYNC=PASS"
    Write-Host "P0_02_REAL_HUB=PASS"
    Write-Host "P0_02_REAL_SEARCH=PASS"
    Write-Host "P0_02_MCP_V2_CONTRACT=PASS"
    Write-Host "HEAD=$FinalHead"
    Write-Host "WORKTREE=CLEAN"
    Write-Host "GIT_ADD_EXECUTED=NO"
    Write-Host "COMMIT_CREATED=NO"
    Write-Host "PUSH_EXECUTED=NO"
    Write-Host "MERGE_EXECUTED=NO"
    Write-Host "TAG_CREATED=NO"
    Write-Host "RELEASE_CREATED=NO"
    Write-Host "NEXT=ODYSSEUS_MCP_REGISTRY_E2E"
    Write-Host "============================================================"
}
finally {
    Pop-Location
}
