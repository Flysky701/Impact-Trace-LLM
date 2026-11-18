param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $workspace '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Python environment is missing. Follow docs/local-development.md first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $workspace 'frontend/dist/index.html'))) {
    throw 'Frontend build is missing. Run npm run build in frontend first.'
}
if (-not $env:IMPACT_REPOSITORY_ROOTS -and -not (Test-Path -LiteralPath (Join-Path $workspace '.env'))) {
    $roots = @((Join-Path $workspace 'data/local'))
    if (Test-Path -LiteralPath 'D:\Project') {
        $roots += 'D:\Project'
    }
    $env:IMPACT_REPOSITORY_ROOTS = ($roots -join ';')
}
Push-Location (Join-Path $workspace 'backend')
try {
    & $pythonExecutable -m app.bootstrap
    if ($LASTEXITCODE -ne 0) { throw 'Account initialization failed.' }
    Write-Host "Open http://127.0.0.1:$Port in your browser. Press Ctrl+C to stop."
    & $pythonExecutable -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
