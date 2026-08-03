# One-click: run BOTH detectors side by side.
#   .\backend\oneclick\compare.ps1
#   .\backend\oneclick\compare.ps1 --metric fill_rate --at 2026-06-29T10:00
$backend = Split-Path $PSScriptRoot -Parent
Push-Location $backend
try { & ".\.venv\Scripts\python.exe" -m oneclick.compare @args }
finally { Pop-Location }
