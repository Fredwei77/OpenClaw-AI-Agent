$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Migration = Join-Path $ProjectRoot "database\migrations\init.sql"

if (Get-Command psql -ErrorAction SilentlyContinue) {
    $databaseUrl = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "postgresql://postgres:openclaw@localhost:5432/openclaw_db" }
    & psql $databaseUrl -f $Migration
    exit $LASTEXITCODE
}

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Push-Location $ProjectRoot
    try {
        $container = $null
        $existingState = docker inspect -f "{{.State.Status}}" openclaw-postgres 2>$null
        if ($LASTEXITCODE -eq 0 -and $existingState -eq "running") {
            $container = "openclaw-postgres"
        } else {
            $container = docker compose ps -q postgres
        }

        if (-not $container) {
            throw "PostgreSQL container is not running. Run: powershell -ExecutionPolicy Bypass -File scripts/start-postgres.ps1"
        }

        $databaseExists = docker exec $container psql -U postgres -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'openclaw_db'"
        if ($databaseExists -ne "1") {
            docker exec $container createdb -U postgres openclaw_db
        }

        Get-Content -Raw $Migration | docker exec -i $container psql -v ON_ERROR_STOP=1 -U postgres -d openclaw_db
        exit $LASTEXITCODE
    } finally {
        Pop-Location
    }
}

throw "Neither psql nor Docker is available. Install PostgreSQL client tools or Docker Desktop."
