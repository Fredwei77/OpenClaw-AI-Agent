# OpenClaw AI Agent - Windows local development launcher
# Usage: powershell -ExecutionPolicy Bypass -File scripts/dev.ps1 [-Restart]

param(
    [switch] $Restart
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$env:PYTHONUTF8 = "1"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$BackendUrl = "http://127.0.0.1:8000/health"
$FrontendUrl = "http://127.0.0.1:5173"
$backend = $null
$frontend = $null
$chrome = $null
$ChromeDebugUrl = "http://127.0.0.1:9222/json/version"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

function Test-HttpReady([string] $Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-HttpReady([string] $Name, [string] $Url, [int] $TimeoutSeconds, $Process, [string] $ErrorLog) {
    for ($i = 0; $i -lt $TimeoutSeconds; $i++) {
        if (Test-HttpReady $Url) {
            return
        }
        if ($Process -and $Process.HasExited) {
            $details = if (Test-Path $ErrorLog) { Get-Content -Raw $ErrorLog } else { "" }
            throw "$Name exited before becoming ready. See $ErrorLog`n$details"
        }
        Start-Sleep -Seconds 1
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds. See $ErrorLog"
}

function Resolve-PythonPath {
    $projectVenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $projectVenvPython) {
        try {
            & $projectVenvPython -c "import asyncpg, bcrypt, fastapi, uvicorn, browser_harness._ipc, browser_harness.helpers" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $projectVenvPython
            }
            Write-Host "Ignoring project .venv with missing backend requirements." -ForegroundColor Yellow
        } catch {
            Write-Host "Ignoring unusable project .venv (recreate it or install backend requirements)." -ForegroundColor Yellow
        }
    }

    foreach ($name in @("python.exe", "python", "py.exe", "py")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    $pythonRoot = Join-Path $env:LOCALAPPDATA "Programs\Python"
    if (Test-Path $pythonRoot) {
        $candidate = Get-ChildItem -Path $pythonRoot -Filter python.exe -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match "\\Python\d+\\python\.exe$" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }
    throw "Python was not found. Install Python 3.11+ or add python.exe to PATH."
}

function Stop-StartedProcess($Process) {
    if ($Process -and -not $Process.HasExited) {
        Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ChromeDebugProfile {
    try {
        $debugChrome = Get-CimInstance Win32_Process -Filter "name = 'chrome.exe'" -ErrorAction SilentlyContinue |
            Where-Object { $_.CommandLine -like "*C:\chrome-debug-profile*" }
        foreach ($process in $debugChrome) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "Could not inspect Chrome debug-profile processes; continuing." -ForegroundColor DarkYellow
    }
}

function Start-ChromeDebug([string] $ChromePath) {
    if (Test-HttpReady $ChromeDebugUrl) {
        Write-Host "[1/3] Reusing Chrome debug port 9222" -ForegroundColor Green
        return $null
    }

    Stop-ChromeDebugProfile
    Write-Host "[1/3] Starting Chrome debug port 9222" -ForegroundColor Yellow
    $chromeArgs = @(
        "--remote-debugging-port=9222",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
        "--user-data-dir=C:\chrome-debug-profile",
        "--new-window",
        "about:blank"
    )
    $process = Start-Process -FilePath $ChromePath -ArgumentList $chromeArgs -PassThru
    for ($i = 0; $i -lt 30; $i++) {
        if (Test-HttpReady $ChromeDebugUrl) { return $process }
        Start-Sleep -Milliseconds 500
    }
    throw "Chrome remote debugging port 9222 did not become ready."
}

function Open-FrontendInChrome([string] $ChromePath) {
    Start-Process -FilePath $ChromePath -ArgumentList @(
        "--remote-debugging-port=9222",
        "--remote-debugging-address=127.0.0.1",
        "--remote-allow-origins=*",
        "--user-data-dir=C:\chrome-debug-profile",
        $FrontendUrl
    ) | Out-Null
}

try {
    Write-Host "Starting OpenClaw AI Agent..." -ForegroundColor Cyan

    if ($Restart) {
        Write-Host "Restart requested. Stopping listeners on ports 8000, 5173 and Chrome debug profile..." -ForegroundColor Yellow
        $listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
            Where-Object { $_.LocalPort -in @(8000, 5173) } |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($processId in $listeners) {
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
        }
        Stop-ChromeDebugProfile
        Start-Sleep -Seconds 1
    }

    $chromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (-not (Test-Path $chromePath)) {
        Write-Warning "Chrome was not found at $chromePath. Browser harness delivery will be unavailable."
    } else {
        $chrome = Start-ChromeDebug $chromePath
    }

    if (Test-HttpReady $BackendUrl) {
        Write-Host "[2/3] Reusing backend at http://127.0.0.1:8000" -ForegroundColor Green
    } else {
        $python = Resolve-PythonPath
        $backendOut = Join-Path $RuntimeDir "backend.stdout.log"
        $backendErr = Join-Path $RuntimeDir "backend.stderr.log"
        Write-Host "[2/3] Starting backend at http://127.0.0.1:8000" -ForegroundColor Yellow
        $backend = Start-Process -FilePath $python -ArgumentList "main.py" -WorkingDirectory "$ProjectRoot\backend" -RedirectStandardOutput $backendOut -RedirectStandardError $backendErr -PassThru -WindowStyle Hidden
        Wait-HttpReady "Backend" $BackendUrl 45 $backend $backendErr
    }

    if (Test-HttpReady $FrontendUrl) {
        Write-Host "[3/3] Reusing frontend at http://127.0.0.1:5173" -ForegroundColor Green
    } else {
        $node = (Get-Command "node.exe" -ErrorAction Stop).Source
        $vite = Join-Path $ProjectRoot "frontend\node_modules\vite\bin\vite.js"
        if (-not (Test-Path $vite)) {
            throw "Vite is not installed. Run: cd frontend; npm.cmd install"
        }
        $frontendOut = Join-Path $RuntimeDir "frontend.stdout.log"
        $frontendErr = Join-Path $RuntimeDir "frontend.stderr.log"
        Write-Host "[3/3] Starting frontend at http://127.0.0.1:5173" -ForegroundColor Yellow
        $frontend = Start-Process -FilePath $node -ArgumentList "`"$vite`"", "--host", "127.0.0.1", "--port", "5173" -WorkingDirectory "$ProjectRoot\frontend" -RedirectStandardOutput $frontendOut -RedirectStandardError $frontendErr -PassThru -WindowStyle Hidden
        Wait-HttpReady "Frontend" $FrontendUrl 30 $frontend $frontendErr
    }

    if (Test-Path $chromePath) {
        Open-FrontendInChrome $chromePath
    }

    Write-Host ""
    Write-Host "Services are ready." -ForegroundColor Green
    Write-Host "  Backend : http://127.0.0.1:8000" -ForegroundColor White
    Write-Host "  Frontend: http://127.0.0.1:5173" -ForegroundColor White
    Write-Host "  Logs    : $RuntimeDir" -ForegroundColor White
    Write-Host ""
    Write-Host "Press Ctrl+C to stop services started by this script." -ForegroundColor DarkGray

    while ($backend -or $frontend -or $chrome) {
        if (($backend -and $backend.HasExited) -or ($frontend -and $frontend.HasExited)) {
            throw "A service exited unexpectedly. Check logs in $RuntimeDir"
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Stop-StartedProcess $frontend
    Stop-StartedProcess $backend
    Stop-StartedProcess $chrome
}
