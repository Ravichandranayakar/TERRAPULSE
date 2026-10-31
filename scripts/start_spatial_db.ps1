# Start the TerraPulse spatial database (PostgreSQL 16 + PostGIS 3.6).
#
# The machine's own PostgreSQL service on port 5432 is left alone. This is a
# second, user-space cluster on port 5433 so PostGIS could be added without
# administrator rights over Program Files.

$ErrorActionPreference = "Stop"
$PG   = "C:\Users\Ravichandran\pgsql16"
$DATA = "$PG\data"

if (-not (Test-Path "$DATA\PG_VERSION")) {
    throw "No cluster at $DATA. Re-run the setup before using the spatial layer."
}

& "$PG\bin\pg_ctl.exe" -D $DATA status *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "PostGIS already running on port 5433"
} else {
    & "$PG\bin\pg_ctl.exe" -D $DATA -o "-p 5433 -c listen_addresses=127.0.0.1" -l "$PG\server.log" start
    Start-Sleep -Seconds 4
    Write-Host "PostGIS started on port 5433"
}

& "$PG\bin\psql.exe" -U postgres -h 127.0.0.1 -p 5433 -d terrapulse -c "SELECT PostGIS_Full_Version();"