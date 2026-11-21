# Stop both demo stacks.
# Usage: powershell -ExecutionPolicy Bypass -File .\stop-demos.ps1

foreach ($port in 8000, 8001, 5173, 5174, 8080, 8081) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
}
Write-Host "Demo ports closed."
