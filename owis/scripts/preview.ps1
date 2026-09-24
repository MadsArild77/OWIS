param(
  [string]$BindAddress = "127.0.0.1",
  [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonExe)) {
  throw "Create .venv and install owis/requirements.txt first. See README.md."
}
Push-Location $projectRoot
try {
  Write-Host "OWIS: http://${BindAddress}:$Port/news"
  & $pythonExe -m uvicorn owis.apps.api.main:app --host $BindAddress --port $Port --reload
  if ($LASTEXITCODE -ne 0) { throw "OWIS exited with code $LASTEXITCODE" }
} finally {
  Pop-Location
}
