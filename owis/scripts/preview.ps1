param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

function Get-PythonCmd {
  if (Get-Command py -ErrorAction SilentlyContinue) { return @("py", "-3") }
  if (Get-Command python -ErrorAction SilentlyContinue) { return @("python") }
  throw "Fant ikke Python i PATH. Installer Python 3.11+ eller åpne terminal med Python tilgjengelig."
}

$pythonCmd = Get-PythonCmd
$url = "http://$Host`:$Port/news"

Write-Host "Starter OWIS preview på $url"
Start-Process $url | Out-Null

$exe = $pythonCmd[0]
$prefix = @()
if ($pythonCmd.Length -gt 1) { $prefix = $pythonCmd[1..($pythonCmd.Length - 1)] }
$args = @($prefix + "-m", "uvicorn", "owis.apps.api.main:app", "--host", $Host, "--port", "$Port", "--reload")
& $exe @args
