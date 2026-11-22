<#
.SYNOPSIS
  Stellt ein, welche Grafikkarte(n) Ollama (Vulkan) nutzt, und startet Ollama neu.

.DESCRIPTION
  -Mode both    Vulkan, R9700 + RX 7800 XT (Standard, nötig für qwen3.6:27b-abx-rca)
  -Mode r9700   Vulkan, nur AI PRO R9700 (32 GB)
  -Mode rx      Vulkan, nur RX 7800 XT (16 GB)
  -Mode split   zwei getrennte Ollama-Instanzen: R9700 auf Port 11434 (Taskleisten-App), RX 7800 XT auf Port 11435
  -Mode split-rx  wie split, aber umgekehrt: RX 7800 XT auf 11434, R9700 auf 11435
                Die zweite Instanz bekommt Kontext 131072 ($ctx2) und loggt nach %LOCALAPPDATA%\Ollama\server-11435.log. Beide nutzen denselben Modell-Ordner.
                Clients wählen die Karte über den Endpoint (http://localhost:11434 bzw. http://localhost:11435).
  -Mode second  nur die zweite Instanz (split-Modus) starten, falls sie nicht läuft. Wartet bis zu 3 Minuten auf
                Instanz A (11434), startet A nie neu. Für den Autostart beim Anmelden (scripts\install-ollama-autostart.ps1).
  -Mode rocm    zurück auf ROCm (Ollama-Standard). Achtung: 35B-A3B stürzt mit ROCm ab, wenn er auf beide Karten verteilt wird.
  -Mode restart Ollama nur neu starten, Einstellungen bleiben
  -Mode status  nur anzeigen (Standard ohne Parameter)

  Setzt die Windows-Benutzervariablen OLLAMA_VULKAN, HIP_VISIBLE_DEVICES und GGML_VK_VISIBLE_DEVICES,
  beendet Ollama (Taskleisten-App und Server), startet es neu und zeigt laut server.log die aktiven Karten.
  Die Vulkan-Indizes werden aus dem server.log über den Gerätenamen ermittelt (letzter Start mit beiden Karten).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode r9700
#>
param([ValidateSet('both', 'r9700', 'rx', 'split', 'split-rx', 'second', 'rocm', 'restart', 'status')][string]$Mode = 'status')

$log = Join-Path $env:LOCALAPPDATA 'Ollama\server.log'
$log2 = Join-Path $env:LOCALAPPDATA 'Ollama\server-11435.log'
$app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
$exe = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe'
$port2 = 11435
$ctx2 = '131072'   # Kontext der zweiten Instanz (RX 7800 XT, 16 GB); qwen3.5:9b mit 128k ca. 8 GB VRAM# OLLAMA_SPLIT_SECOND: Vulkan-Index der Karte für die zweite Instanz (nur in den split-Modi gesetzt)
$vars = 'OLLAMA_VULKAN', 'HIP_VISIBLE_DEVICES', 'GGML_VK_VISIBLE_DEVICES', 'OLLAMA_SPLIT_SECOND'
# Beim Neustart zusätzlich aus den Benutzervariablen übernehmen (sonst erbt Ollama alte Werte aus der aufrufenden Shell)
$keep = 'OLLAMA_NUM_PARALLEL', 'OLLAMA_CONTEXT_LENGTH', 'OLLAMA_KV_CACHE_TYPE', 'OLLAMA_FLASH_ATTENTION'

function Get-Devices([int]$FromLine = 0, [string]$Path = $log) {
  # "inference compute" Zeilen: library, name=Vulkan0, description, total
  if (-not (Test-Path $Path)) { return @() }
  @(Select-String $Path -Pattern 'msg="inference compute"' | Where-Object { $_.LineNumber -gt $FromLine } | ForEach-Object {
    [pscustomobject]@{
      Line = $_.LineNumber
      Library = [regex]::Match($_.Line, 'library=(\w+)').Groups[1].Value
      Name = [regex]::Match($_.Line, ' name=(\w+)').Groups[1].Value
      FilterId = [regex]::Match($_.Line, 'filter_id=(\d+)').Groups[1].Value
      Description = [regex]::Match($_.Line, 'description="([^"]+)"').Groups[1].Value
      Total = [regex]::Match($_.Line, 'total="([^"]+)"').Groups[1].Value
    } })
}

function Get-VulkanIndex([string]$Pattern) {
  # neuester Eintrag der Karte -> filter_id ist der echte Vulkan-Index (auch wenn GGML_VK_VISIBLE_DEVICES gefiltert hat).
  # Ältere Logs ohne filter_id: nur Starts mit beiden Karten, Index aus "VulkanN".
  # sucht in server.log, server-11435.log und den rotierten server-1..5.log (neueste Datei zuerst)
  $files = @($log, $log2) + @(1..5 | ForEach-Object { Join-Path $env:LOCALAPPDATA "Ollama\server-$_.log" }) |
    Where-Object { Test-Path $_ } | Sort-Object { (Get-Item $_).LastWriteTime } -Descending
  foreach ($f in $files) {
    $all = Get-Devices 0 $f | Where-Object Library -eq 'Vulkan'
    $hit = $all | Where-Object { $_.Description -match $Pattern -and $_.FilterId -ne '' } | Select-Object -Last 1
    if ($hit) { return [int]$hit.FilterId }
    $hit = $all | Where-Object { $_.Description -match $Pattern -and $_.Name -match '^Vulkan\d+$' } |
      Where-Object { $l = $_.Line; @($all | Where-Object { [math]::Abs($_.Line - $l) -le 2 }).Count -ge 2 } | Select-Object -Last 1
    if ($hit) { return [int]($hit.Name -replace 'Vulkan', '') }
  }
  throw "Index für '$Pattern' nicht in den server*.log gefunden. Zuerst einmal '-Mode both' ausführen."
}

function Show-Status([int]$FromLine = 0) {
  Write-Host 'Benutzervariablen:'
  foreach ($k in $vars) { $v = [Environment]::GetEnvironmentVariable($k, 'User'); Write-Host ('  {0,-24} {1}' -f $k, $(if ($null -eq $v) { '(nicht gesetzt)' } else { $v })) }
  $devs = Get-Devices $FromLine
  if ($devs) { $last = ($devs | Select-Object -Last 1).Line; $devs = $devs | Where-Object { $last - $_.Line -le 2 } }
  Write-Host 'Aktive Karten (letzter Ollama-Start):'
  if (-not $devs) { Write-Host '  (keine Einträge gefunden)' }
  $devs | ForEach-Object { Write-Host ('  {0,-7} {1,-8} {2} ({3})' -f $_.Library, $_.Name, $_.Description, $_.Total) }
  if ($null -ne [Environment]::GetEnvironmentVariable('OLLAMA_SPLIT_SECOND', 'User')) {
    $d2 = Get-Devices 0 $log2 | Select-Object -Last 1
    $ok = try { [bool](Invoke-RestMethod "http://127.0.0.1:$port2/api/version" -TimeoutSec 3) } catch { $false }
    Write-Host ("Zweite Instanz (Port {0}): {1}{2}" -f $port2, $(if ($ok) { 'läuft' } else { 'NICHT erreichbar' }), $(if ($d2) { ", $($d2.Description) ($($d2.Total))" } else { '' }))
  }
}

function Start-Second {
  # zweite Instanz: eigene Karte, eigener Port, eigenes Log; Variablen nur für diesen Prozess setzen
  $idx = [Environment]::GetEnvironmentVariable('OLLAMA_SPLIT_SECOND', 'User')
  if ($null -eq $idx) { return }
  # Kontext passend zu 16 GB (sonst erbt sie OLLAMA_CONTEXT_LENGTH=131072 von Instanz A)
  $second = @{ GGML_VK_VISIBLE_DEVICES = $idx; OLLAMA_HOST = "127.0.0.1:$port2"; HIP_VISIBLE_DEVICES = '-1'; OLLAMA_VULKAN = '1'
    OLLAMA_CONTEXT_LENGTH = $ctx2; OLLAMA_KEEP_ALIVE = [Environment]::GetEnvironmentVariable('OLLAMA_KEEP_ALIVE', 'User') }
  $saved = @{}; foreach ($k in $second.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process') }
  foreach ($k in $second.Keys) { [Environment]::SetEnvironmentVariable($k, $second[$k], 'Process') }
  Start-Process $exe -ArgumentList 'serve' -WindowStyle Hidden -RedirectStandardError $log2 -RedirectStandardOutput "$log2.out"
  foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') }
  for ($i = 0; $i -lt 30; $i++) { Start-Sleep -Seconds 2; if ((Get-Devices 0 $log2).Count -gt 0) { Start-Sleep -Seconds 1; break } }
}

if ($Mode -eq 'status') { Get-Help $MyInvocation.MyCommand.Path -Examples | Out-Null; Show-Status; return }

if ($Mode -eq 'second') {
  # nur Instanz B; A (Taskleisten-App) startet beim Anmelden selbst
  function Test-Port([int]$p) { try { [bool](Invoke-RestMethod "http://127.0.0.1:$p/api/version" -TimeoutSec 2) } catch { $false } }
  if ($null -eq [Environment]::GetEnvironmentVariable('OLLAMA_SPLIT_SECOND', 'User')) { Write-Host 'Kein split-Modus gesetzt, nichts zu tun.'; return }
  if (Test-Port $port2) { Write-Host "Zweite Instanz läuft schon (Port $port2)."; return }
  for ($i = 0; $i -lt 90 -and -not (Test-Port 11434); $i++) { Start-Sleep -Seconds 2 }
  if (-not (Test-Port 11434)) { Write-Host 'Instanz A (11434) nicht erreichbar, starte B trotzdem.' }
  # User-Variablen laden (Task/Shell können veraltete Werte haben)
  foreach ($k in $keep) { $v = [Environment]::GetEnvironmentVariable($k, 'User'); if ($null -ne $v) { Set-Item "env:$k" $v } }
  Start-Second
  Write-Host ("Zweite Instanz (Port {0}): {1}" -f $port2, $(if (Test-Port $port2) { 'läuft' } else { 'NICHT erreichbar' }))
  return
}

$target = if ($Mode -eq 'restart') { $null } else { switch ($Mode) {
  'both'  { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = $null } }
  'r9700' { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = [string](Get-VulkanIndex 'R9700') } }
  'rx'    { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = [string](Get-VulkanIndex '7800') } }
  'split' { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = [string](Get-VulkanIndex 'R9700'); OLLAMA_SPLIT_SECOND = [string](Get-VulkanIndex '7800') } }
  'split-rx' { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = [string](Get-VulkanIndex '7800'); OLLAMA_SPLIT_SECOND = [string](Get-VulkanIndex 'R9700') } }
  'rocm'  { @{ OLLAMA_VULKAN = $null; HIP_VISIBLE_DEVICES = $null; GGML_VK_VISIBLE_DEVICES = $null } }
} }
if ($target) {
  foreach ($k in $vars) {
    [Environment]::SetEnvironmentVariable($k, $target[$k], 'User')   # $null entfernt die Variable
    if ($null -eq $target[$k]) { Remove-Item "env:$k" -ErrorAction SilentlyContinue } else { Set-Item "env:$k" $target[$k] }
  }
  Write-Host "Modus '$Mode' gesetzt, starte Ollama neu ..."
} else {
  # Neustart mit den gespeicherten Benutzervariablen (nicht mit denen dieser Shell)
  foreach ($k in $vars) { $v = [Environment]::GetEnvironmentVariable($k, 'User'); if ($null -eq $v) { Remove-Item "env:$k" -ErrorAction SilentlyContinue } else { Set-Item "env:$k" $v } }
  Write-Host 'Starte Ollama neu (Einstellungen unverändert) ...'
}

foreach ($k in $keep) { $v = [Environment]::GetEnvironmentVariable($k, 'User'); if ($null -eq $v) { Remove-Item "env:$k" -ErrorAction SilentlyContinue } else { Set-Item "env:$k" $v } }

$fromLine = if (Test-Path $log) { @(Get-Content $log).Count } else { 0 }
Get-Process -Name 'ollama app' -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name 'ollama', 'llama-server' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 3
if ((Test-Path $log) -and @(Get-Content $log).Count -lt $fromLine) { $fromLine = 0 }   # Log wurde beim Neustart rotiert
Start-Process $app
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep -Seconds 2
  if ((Test-Path $log) -and @(Get-Content $log).Count -lt $fromLine) { $fromLine = 0 }   # Ollama rotiert server.log beim Start
  if ((Get-Devices $fromLine).Count -gt 0) { Start-Sleep -Seconds 1; break }
}
Start-Second
Show-Status $fromLine
Write-Host 'Hinweis: Modelle sind entladen; die erste Anfrage lädt das Modell neu (27B ~35 s).'
