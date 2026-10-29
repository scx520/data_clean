param(
    [int]$Port = 8000,
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment creation failed.' }
}
& $pythonPath -m pip install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
if (-not $SkipBuild -or -not (Test-Path -LiteralPath 'frontend\dist\index.html')) {
    Push-Location frontend
    try {
        npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    }
    finally { Pop-Location }
}
Write-Host "Data cleaning platform: http://127.0.0.1:$Port" -ForegroundColor Green
Write-Host 'Press Ctrl+C to stop.'
& $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $Port
