param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$url = "http://$Host`:$Port/news"
Write-Host "Starting OWIS API on $Host:$Port ..."
Start-Process $url | Out-Null

uvicorn owis.apps.api.main:app --host $Host --port $Port --reload
