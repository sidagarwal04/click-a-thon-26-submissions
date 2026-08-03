# One-click: load ALL data into ClickHouse via the CLI (reliable path for the 9M-row job).
# Runs data.load directly, no server involved. Use this instead of the dashboard's Load button
# when you want the full load to run without any --reload interruptions.
#   .\backend\oneclick\load.ps1
$backend = Split-Path $PSScriptRoot -Parent
Push-Location $backend
try { & ".\.venv\Scripts\python.exe" -m data.load }
finally { Pop-Location }
