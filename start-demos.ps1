# Start both demo stacks for recording.
# Usage: powershell -ExecutionPolicy Bypass -File .\start-demos.ps1

$ErrorActionPreference = "Stop"
$root = "D:\nexvia"

Write-Host "Resetting fraud demo data..."
Set-Location "$root\AIML-01"
$env:DATABASE_URL = "sqlite:///./data/dev.db"
$env:FEATURE_BACKEND = "feast"
Remove-Item data\dev.db -ErrorAction SilentlyContinue
python scripts/seed.py --limit 600
$env:DRIFT_SHARE_THRESHOLD = "0.3"
python scripts/drift_job.py --once

Write-Host "Starting fraud API and dashboard..."
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "nexvia_fraud.api.app:app", "--host", "127.0.0.1", "--port", "8000" -WorkingDirectory "$root\AIML-01" -WindowStyle Minimized
Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev", "--", "--port", "5173" -WorkingDirectory "$root\AIML-01\dashboard" -WindowStyle Minimized

Write-Host "Resetting imaging demo data..."
Set-Location "$root\AIML-02"
$env:DATABASE_URL = "sqlite:///./data/dev.db"
Remove-Item data\dev.db -ErrorAction SilentlyContinue
python scripts/seed_demo.py

Write-Host "Starting imaging API and dashboard..."
Start-Process -FilePath "python" -ArgumentList "-m", "uvicorn", "nexvia_imaging.api.app:app", "--host", "127.0.0.1", "--port", "8001" -WorkingDirectory "$root\AIML-02" -WindowStyle Minimized
$env:VITE_API_URL = "http://localhost:8001"
Set-Location "$root\AIML-02\dashboard"
npm.cmd run build
Start-Process -FilePath "npm.cmd" -ArgumentList "run", "preview", "--", "--port", "5174" -WorkingDirectory "$root\AIML-02\dashboard" -WindowStyle Minimized

Start-Sleep -Seconds 8
Start-Process "http://localhost:5173"
Start-Process "http://localhost:5174"
Write-Host "Demos running: http://localhost:5173 and http://localhost:5174"
