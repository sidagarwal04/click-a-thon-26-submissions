# One-click anomaly detector. No venv activation needed.
#   .\backend\oneclick\detect.ps1
#   .\backend\oneclick\detect.ps1 --metric fill_rate --at 2026-06-29T10:00 --method seasonal_ml
$backend = Split-Path $PSScriptRoot -Parent
Push-Location $backend
try { & ".\.venv\Scripts\python.exe" -m oneclick.detect @args }
finally { Pop-Location }
