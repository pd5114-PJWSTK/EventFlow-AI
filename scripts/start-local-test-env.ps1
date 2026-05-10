param(
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("compose", "up", "-d")
if (-not $SkipBuild) {
  $composeArgs += "--build"
}

Write-Host "[start] Starting the full app through docker compose..." -ForegroundColor Cyan
docker @composeArgs

$healthUrl = "http://127.0.0.1:8000/health"
$readyUrl = "http://127.0.0.1:8000/ready"
$maxAttempts = 45
$ready = $false

for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
  try {
    $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 3
    $readyCheck = Invoke-RestMethod -Uri $readyUrl -Method Get -TimeoutSec 3
    if ($health.status -eq "ok" -and $readyCheck.status -eq "ok") {
      $ready = $true
      break
    }
  } catch {
    Start-Sleep -Seconds 2
  }
  Start-Sleep -Seconds 1
}

if (-not $ready) {
  throw "Backend did not reach readiness at $readyUrl."
}

$patchPath = Join-Path $repoRoot "scripts\sql\production_upgrade.sql"
if (Test-Path $patchPath) {
  Write-Host "[start] Applying DB patch: scripts\sql\production_upgrade.sql" -ForegroundColor Cyan
  $dbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "eventflow" }
  $dbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "eventflow" }
  $containerPatchPath = "/tmp/production_upgrade.sql"
  docker cp $patchPath "eventflow-postgres:$containerPatchPath"
  docker compose exec -T postgres psql -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -f $containerPatchPath
}

Write-Host "[ok] Backend: $healthUrl" -ForegroundColor Green
Write-Host "[ok] Frontend: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "[info] Canonical local runtime uses Docker Compose only; no local Python, venv or npm is required." -ForegroundColor Yellow
Write-Host "[info] LLM works only when AI_AZURE_LLM_ENABLED=true and Azure credentials are set in .env." -ForegroundColor Yellow
