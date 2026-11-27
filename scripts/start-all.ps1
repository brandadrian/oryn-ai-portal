<#
.SYNOPSIS
  Startet den kompletten Oryn-Stack in Docker: Gateway, Website, Monitoring, API, Gmail-MCP,
  Open WebUI (chat.oryn) und waeb-operations.

.DESCRIPTION
  - startet Docker Desktop, falls die Engine nicht läuft, und wartet bis zu 5 Minuten
  - legt das Netz "proxy" und das externe Volume "openwebui_data" an, falls sie fehlen
    (z.B. nach einem Reset von Docker Desktop)
  - "docker compose up -d" für jeden Stack in der richtigen Reihenfolge (idempotent)
  - war openwebui_data neu, wird danach das Open-WebUI-Setup (config.json) eingespielt
  Log: %LOCALAPPDATA%\Oryn\start-all.log

  Als Aufgabe beim Anmelden registrieren: scripts\install-start-all.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\start-all.ps1
#>
$ErrorActionPreference = 'Continue'
$portal  = Split-Path $PSScriptRoot -Parent                 # ...\oryn-ai-portal
$github  = Split-Path $portal -Parent                       # ...\github
$gateway = Join-Path $github 'oryn-gateway'

# Reihenfolge zählt: Traefik zuerst, Monitoring vor der API (schreibt nach Loki), gmail-mcp vor Open WebUI.
$stacks = @(
  $gateway,
  (Join-Path $gateway 'website'),
  (Join-Path $portal 'monitoring'),
  (Join-Path $portal 'api'),
  (Join-Path $gateway 'gmail-mcp'),
  (Join-Path $portal 'openwebui'),
  (Join-Path $portal 'waeb-operations')
)

$logDir = Join-Path $env:LOCALAPPDATA 'Oryn'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'start-all.log'
function Log($m) { $l = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m; $l | Tee-Object -FilePath $log -Append }

function Test-Docker { docker info --format '{{.ServerVersion}}' *> $null; return $LASTEXITCODE -eq 0 }

Log '--- start-all ---'
if (-not (Test-Docker)) {
  $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
  Log "Docker-Engine nicht erreichbar, starte $exe"
  Start-Process $exe
  $deadline = (Get-Date).AddMinutes(5)
  while (-not (Test-Docker)) {
    if ((Get-Date) -gt $deadline) { Log 'FEHLER: Docker nach 5 Minuten nicht bereit, Abbruch'; exit 1 }
    Start-Sleep -Seconds 5
  }
}
Log 'Docker bereit'

docker network inspect proxy *> $null
if ($LASTEXITCODE -ne 0) { docker network create proxy | Out-Null; Log 'Netz proxy angelegt' }

$newOpenWebUI = $false
docker volume inspect openwebui_data *> $null
if ($LASTEXITCODE -ne 0) {
  docker volume create openwebui_data | Out-Null
  $newOpenWebUI = $true
  Log 'WARNUNG: Volume openwebui_data fehlte und wurde LEER angelegt (Chats/Benutzer ggf. aus Backup zurückspielen)'
}

$failed = @()
foreach ($dir in $stacks) {
  if (-not (Test-Path (Join-Path $dir 'docker-compose.yml'))) { Log "übersprungen (kein Compose): $dir"; continue }
  Push-Location $dir
  $out = docker compose up -d 2>&1
  $code = $LASTEXITCODE
  Pop-Location
  if ($code -eq 0) { Log "ok: $dir" } else { Log "FEHLER ($code): $dir"; $out | ForEach-Object { Log "  $_" }; $failed += $dir }
}

if ($newOpenWebUI) {
  Log 'warte auf Open WebUI (healthy) für das Setup'
  $deadline = (Get-Date).AddMinutes(5)
  while ((docker inspect -f '{{.State.Health.Status}}' openwebui-openwebui-1 2>$null) -ne 'healthy') {
    if ((Get-Date) -gt $deadline) { Log 'WARNUNG: Open WebUI nicht healthy, Setup übersprungen'; break }
    Start-Sleep -Seconds 5
  }
  Push-Location (Join-Path $portal 'openwebui')
  docker compose run --rm --no-deps setup 2>&1 | ForEach-Object { Log "  setup: $_" }
  Pop-Location
}

if ($failed.Count) { Log "fertig mit Fehlern: $($failed -join ', ')"; exit 1 }
Log 'fertig, alle Stacks laufen'
