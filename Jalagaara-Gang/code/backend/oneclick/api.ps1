# One-click: start the FastAPI server on http://localhost:8000
#   .\backend\oneclick\api.ps1
$backend = Split-Path $PSScriptRoot -Parent
Push-Location $backend
try { & ".\.venv\Scripts\python.exe" -m uvicorn api.main:app --reload --port 8000 }
finally { Pop-Location }
