# OpenClaw AI Agent - Windows 开发环境启动脚本
# Usage: powershell -ExecutionPolicy Bypass -File scripts/dev.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "Starting OpenClaw AI Agent..." -ForegroundColor Cyan

# 1. Start backend
Write-Host "[1/3] Backend (http://localhost:8000)..." -ForegroundColor Yellow
$backend = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory "$ProjectRoot\backend" -PassThru -WindowStyle Hidden

# 2. Start frontend
Write-Host "[2/3] Frontend (http://localhost:5173)..." -ForegroundColor Yellow
$frontend = Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory "$ProjectRoot\frontend" -PassThru -WindowStyle Hidden

# 3. Wait for frontend dev server to be ready
Write-Host "    Waiting for frontend server..." -ForegroundColor DarkGray
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}

# 4. Launch Chrome with remote debugging
Write-Host "[3/3] Chrome (remote-debugging-port=9222)..." -ForegroundColor Yellow
$chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$chromeArgs = @(
    "--remote-debugging-port=9222",
    "--user-data-dir=C:\chrome-debug-profile",
    "http://localhost:5173"
)
$chrome = Start-Process -FilePath $chromePath -ArgumentList $chromeArgs -PassThru

Write-Host ""
Write-Host "All services started!" -ForegroundColor Green
Write-Host "  Backend : http://localhost:8000" -ForegroundColor White
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "  Chrome  : debug port 9222" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor DarkGray

# Cleanup on exit
$cleanup = {
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    if ($backend -and !$backend.HasExited)  { Stop-Process -Id $backend.Id  -Force -ErrorAction SilentlyContinue }
    if ($frontend -and !$frontend.HasExited) { Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue }
    if ($chrome -and !$chrome.HasExited)     { Stop-Process -Id $chrome.Id   -Force -ErrorAction SilentlyContinue }
    Write-Host "Done." -ForegroundColor Green
}

# Register cleanup for Ctrl+C
[Console]::TreatControlCAsInput = $false
try {
    # Wait until any child process exits
    while ($true) {
        if ($backend.HasExited -or $frontend.HasExited -or $chrome.HasExited) { break }
        Start-Sleep -Seconds 2
    }
} finally {
    & $cleanup
}
