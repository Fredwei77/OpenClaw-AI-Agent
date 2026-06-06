$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is required to start PostgreSQL."
}

Push-Location $ProjectRoot
try {
    $existingState = docker inspect -f "{{.State.Status}}" openclaw-postgres 2>$null
    if ($LASTEXITCODE -eq 0 -and $existingState -eq "running") {
        Write-Host "Using existing PostgreSQL container: openclaw-postgres"
        exit 0
    }

    docker compose up -d postgres
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
