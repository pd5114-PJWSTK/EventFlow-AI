param(
  [switch]$SkipBuild,
  [switch]$SkipNpmInstall
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$composeArgs = @("compose", "up", "-d")
if (-not $SkipBuild) {
  $composeArgs += "--build"
}

Write-Host "[start] Uruchamianie backend stack przez docker compose..." -ForegroundColor Cyan
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
  throw "Backend nie osiagnal statusu gotowosci pod $readyUrl."
}

$patches = @(
  "scripts\sql\cp04_production_readiness.sql",
  "scripts\sql\cp05_operational_training_seed.sql",
  "scripts\sql\cp06_operational_company_seed.sql"
)
foreach ($relativePatch in $patches) {
  $patchPath = Join-Path $repoRoot $relativePatch
  if (-not (Test-Path $patchPath)) {
    continue
  }
  Write-Host "[start] Aplikacja patcha DB: $relativePatch" -ForegroundColor Cyan
  $dbUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "eventflow" }
  $dbName = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "eventflow" }
  $containerPatchPath = "/tmp/" + (Split-Path -Leaf $patchPath)
  docker cp $patchPath "eventflow-postgres:$containerPatchPath"
  docker compose exec -T postgres psql -U $dbUser -d $dbName -v ON_ERROR_STOP=1 -f $containerPatchPath
}

Set-Location (Join-Path $repoRoot "frontend")

if (-not $SkipNpmInstall -or -not (Test-Path "node_modules")) {
  Write-Host "[start] Instalacja zaleznosci frontend..." -ForegroundColor Cyan
  npm install
}

Write-Host "[ok] Backend gotowy: $healthUrl" -ForegroundColor Green
Write-Host "[ok] Frontend dev: http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "[info] Logowanie domyslne: admin / Adm1nVPS_2026!Secure" -ForegroundColor Yellow
Write-Host "[info] LLM lokalnie dziala tylko gdy AI_AZURE_LLM_ENABLED=true oraz Azure credentials sa ustawione w .env." -ForegroundColor Yellow

npm run dev
