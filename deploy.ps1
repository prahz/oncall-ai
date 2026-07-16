$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Canonical cloud target. The live dashboard (oncall-dashboard-harsh-dev) is
# served by the pod named "Oncall-AI" in the "harshdumpss-s-space" org. We pin
# both explicitly so a deploy can NEVER land in the wrong pod (there are several
# look-alike pods on this account).
# ---------------------------------------------------------------------------
$ORG = "019eff2e-a06b-7647-b98a-605385ee80aa"   # harshdumpss-s-space
$POD = "019f1e93-f5f6-766f-b9c0-1606bc2809be"   # Oncall-AI (live)
$L   = "lemma", "--timeout", "300", "--org", $ORG, "--pod", $POD

Write-Host "Deploying to Oncall-AI ($POD)..." -ForegroundColor Cyan

# 1. Backend resources (tables first so new columns/tables exist before code uses them)
$dirs = @("tables", "functions", "agents", "workflows", "schedules", "surfaces")
foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "Importing $dir..." -ForegroundColor Green
        & $L pod import $dir
    }
}

# 2. Seed the runbooks + monitored_services tables (idempotent).
#    NOTE: runbooks live in the `runbooks` TABLE, not in /files — the hosted
#    file API rejects writes from this CLI/runtime, so we store docs in tables.
#    Regenerate the embedded runbooks after editing files/runbooks/*.md with:
#      scripts\build_bootstrap.py   (see repo)
Write-Host "Seeding runbooks + services (running _bootstrap)..." -ForegroundColor Green
& $L function run _bootstrap

# 3. Dashboard app (rename package.json to dodge the Windows npm-build WinError 2)
$appDir = "apps\oncall-dashboard"
$sourceDir = "$appDir\source"
$packageJson = "$sourceDir\package.json"
$packageJsonBak = "$sourceDir\package.json.bak"
if (Test-Path $appDir) {
    Write-Host "Deploying oncall-dashboard app..." -ForegroundColor Green
    if (Test-Path $packageJson) { Move-Item -Force $packageJson $packageJsonBak }
    try {
        & $L apps deploy oncall-dashboard $sourceDir -y
    }
    finally {
        if (Test-Path $packageJsonBak) { Move-Item -Force $packageJsonBak $packageJson }
    }
}

Write-Host "Deployment completed successfully!" -ForegroundColor Cyan
