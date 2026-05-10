param(
  [Parameter(Mandatory = $true)]
  [string]$InputFile,

  [Parameter(Mandatory = $true)]
  [string]$OutputFile
)

$lines = Get-Content -Path $InputFile
$start = ($lines | Select-String -Pattern '^BEGIN;' | Select-Object -First 1).LineNumber
$end = ($lines | Select-String -Pattern '^COMMIT;' | Select-Object -Last 1).LineNumber

if (-not $start -or -not $end -or $end -lt $start) {
  throw "Could not detect SQL BEGIN/COMMIT block in $InputFile"
}

$sql = $lines[($start - 1)..($end - 1)]
$outDir = Split-Path -Path $OutputFile -Parent
if ($outDir -and -not (Test-Path $outDir)) {
  New-Item -ItemType Directory -Path $outDir | Out-Null
}

Set-Content -Path $OutputFile -Value ($sql -join "`n") -Encoding utf8
Write-Output "Wrote SQL block: $OutputFile"
