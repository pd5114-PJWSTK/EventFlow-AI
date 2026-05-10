param(
  [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Clear-FrontendCheckContainers {
  $ids = docker ps -aq --filter "label=com.docker.compose.service=frontend-check"
  if ($ids) {
    Write-Host "[quality] Removing stale frontend-check containers..." -ForegroundColor Yellow
    docker rm -f $ids | Out-Null
  }
}

Clear-FrontendCheckContainers

if (-not $SkipBuild) {
  Write-Host "[quality] Building backend and frontend images..." -ForegroundColor Cyan
  docker compose build backend frontend
}

Write-Host "[quality] Validating local Docker Compose config..." -ForegroundColor Cyan
docker compose config | Out-Null

Write-Host "[quality] Validating VPS Docker Compose config..." -ForegroundColor Cyan
docker compose -f docker-compose.vps.yml config | Out-Null

Write-Host "[quality] Running backend tests in Docker..." -ForegroundColor Cyan
docker compose run --rm `
  -e READY_CHECK_EXTERNALS=false `
  -e CELERY_ALWAYS_EAGER=true `
  -e API_TEST_JOBS_ENABLED=true `
  -e API_DOCS_ENABLED=true `
  backend python -m pytest -q

Write-Host "[quality] Running frontend typecheck, lint, tests and build in Docker..." -ForegroundColor Cyan
try {
  docker compose --profile quality run --rm frontend-check
} finally {
  Clear-FrontendCheckContainers
}

Write-Host "[quality] All quality gates passed." -ForegroundColor Green
