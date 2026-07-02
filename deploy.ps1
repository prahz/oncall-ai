$ErrorActionPreference = "Stop"

Write-Host "Starting deployment to Lemma cloud..." -ForegroundColor Cyan

# 1. Deploy backend components
$dirs = @("agents", "functions", "schedules", "surfaces", "tables", "workflows")
foreach ($dir in $dirs) {
    if (Test-Path $dir) {
        Write-Host "Importing $dir..." -ForegroundColor Green
        lemma pod import $dir
    }
}

# 2. Deploy dashboard app
$appDir = "apps\oncall-dashboard"
$sourceDir = "$appDir\source"
$packageJson = "$sourceDir\package.json"
$packageJsonBak = "$sourceDir\package.json.bak"

if (Test-Path $appDir) {
    Write-Host "Deploying oncall-dashboard app..." -ForegroundColor Green
    
    # Temporarily rename package.json to avoid WinError 2 (NPM build issue)
    if (Test-Path $packageJson) {
        Move-Item -Force $packageJson $packageJsonBak
    }
    
    try {
        lemma apps deploy oncall-dashboard $sourceDir -y
    }
    finally {
        # Restore package.json
        if (Test-Path $packageJsonBak) {
            Move-Item -Force $packageJsonBak $packageJson
        }
    }
}

Write-Host "Deployment completed successfully!" -ForegroundColor Cyan
