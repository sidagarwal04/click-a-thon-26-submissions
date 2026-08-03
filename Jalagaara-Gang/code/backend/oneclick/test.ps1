# One-click: run the whole test suite.
#   .\backend\oneclick\test.ps1
$backend = Split-Path $PSScriptRoot -Parent
Push-Location $backend
try { & ".\.venv\Scripts\python.exe" -m pytest -q @args }
finally { Pop-Location }
