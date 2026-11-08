<#
.SYNOPSIS
  Stellt ein, welche Grafikkarte(n) Ollama (Vulkan) nutzt, und startet Ollama neu.

.DESCRIPTION
  -Mode both    Vulkan, R9700 + RX 7800 XT (Standard, nötig für qwen3.6:27b-abx-rca)
  -Mode r9700   Vulkan, nur AI PRO R9700 (32 GB)
  -Mode rx      Vulkan, nur RX 7800 XT (16 GB)
  -Mode rocm    zurück auf ROCm (Ollama-Standard). Achtung: 35B-A3B stürzt mit ROCm ab, wenn er auf beide Karten verteilt wird.
  -Mode restart Ollama nur neu starten, Einstellungen bleiben
  -Mode status  nur anzeigen (Standard ohne Parameter)

  Setzt die Windows-Benutzervariablen OLLAMA_VULKAN, HIP_VISIBLE_DEVICES und GGML_VK_VISIBLE_DEVICES,
  beendet Ollama (Taskleisten-App und Server), startet es neu und zeigt laut server.log die aktiven Karten.
  Die Vulkan-Indizes werden aus dem server.log über den Gerätenamen ermittelt (letzter Start mit beiden Karten).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\ollama-gpu.ps1 -Mode r9700
#>
param([ValidateSet('both', 'r9700', 'rx', 'rocm', 'restart', 'status')][string]$Mode = 'status')

$log = Join-Path $env:LOCALAPPDATA 'Ollama\server.log'
$app = Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama app.exe'
$vars = 'OLLAMA_VULKAN', 'HIP_VISIBLE_DEVICES', 'GGML_VK_VISIBLE_DEVICES'

function Get-Devices([int]$FromLine = 0) {
  # "inference compute" Zeilen: library, name=Vulkan0, description, total
  if (-not (Test-Path $log)) { return @() }
  @(Select-String $log -Pattern 'msg="inference compute"' | Where-Object { $_.LineNumber -gt $FromLine } | ForEach-Object {
    [pscustomobject]@{
      Line = $_.LineNumber
      Library = [regex]::Match($_.Line, 'library=(\w+)').Groups[1].Value
      Name = [regex]::Match($_.Line, ' name=(\w+)').Groups[1].Value
      Description = [regex]::Match($_.Line, 'description="([^"]+)"').Groups[1].Value
      Total = [regex]::Match($_.Line, 'total="([^"]+)"').Groups[1].Value
    } })
}

function Get-VulkanIndex([string]$Pattern) {
  # letzter Start, bei dem beide Karten unter Vulkan sichtbar waren -> Index aus "VulkanN"
  $all = Get-Devices | Where-Object Library -eq 'Vulkan'
  $hit = $all | Where-Object { $_.Description -match $Pattern -and $_.Name -match '^Vulkan\d+$' } |
    Where-Object { $l = $_.Line; @($all | Where-Object { [math]::Abs($_.Line - $l) -le 2 }).Count -ge 2 } | Select-Object -Last 1
  if (-not $hit) { throw "Index für '$Pattern' nicht im server.log gefunden. Zuerst einmal '-Mode both' ausführen." }
  [int]($hit.Name -replace 'Vulkan', '')
}

function Show-Status([int]$FromLine = 0) {
  Write-Host 'Benutzervariablen:'
  foreach ($k in $vars) { $v = [Environment]::GetEnvironmentVariable($k, 'User'); Write-Host ('  {0,-24} {1}' -f $k, $(if ($null -eq $v) { '(nicht gesetzt)' } else { $v })) }
  $devs = Get-Devices $FromLine
  if ($devs) { $last = ($devs | Select-Object -Last 1).Line; $devs = $devs | Where-Object { $last - $_.Line -le 2 } }
  Write-Host 'Aktive Karten (letzter Ollama-Start):'
  if (-not $devs) { Write-Host '  (keine Einträge gefunden)' }
  $devs | ForEach-Object { Write-Host ('  {0,-7} {1,-8} {2} ({3})' -f $_.Library, $_.Name, $_.Description, $_.Total) }
}

if ($Mode -eq 'status') { Get-Help $MyInvocation.MyCommand.Path -Examples | Out-Null; Show-Status; return }

$target = if ($Mode -eq 'restart') { $null } else { switch ($Mode) {
  'both'  { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = $null } }
  'r9700' { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = [string](Get-VulkanIndex 'R9700') } }
  'rx'    { @{ OLLAMA_VULKAN = '1'; HIP_VISIBLE_DEVICES = '-1'; GGML_VK_VISIBLE_DEVICES = [string](Get-VulkanIndex '7800') } }
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
Show-Status $fromLine
Write-Host 'Hinweis: Modelle sind entladen; die erste Anfrage lädt das Modell neu (27B ~35 s).'
