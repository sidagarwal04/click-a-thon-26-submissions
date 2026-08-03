# One-click: list ClickHouse tables + row counts.
#   .\backend\oneclick\tables.ps1
$backend = Split-Path $PSScriptRoot -Parent
Push-Location $backend
try { & ".\.venv\Scripts\python.exe" -m oneclick.tables @args }
finally { Pop-Location }
