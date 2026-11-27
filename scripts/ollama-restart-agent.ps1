<#
.SYNOPSIS
  Wartet auf Neustart-Anfragen des Model-Managers (management.oryn) und startet Ollama neu.

.DESCRIPTION
  Der Model-Manager läuft im Container und kann Ollama (nativ unter Windows) nicht selbst neu starten.
  Er legt deshalb die Datei restart.request in %LOCALAPPDATA%\Oryn\model-manager an (Bind-Mount).
  Dieses Skript prüft alle 2 Sekunden, ruft dann "ollama-gpu.ps1 -Mode restart" auf und schreibt
  das Ergebnis nach status.json (wird im UI angezeigt).

  Als Aufgabe beim Anmelden registrieren: scripts\install-ollama-restart-agent.ps1
  Log: %LOCALAPPDATA%\Oryn\ollama-restart-agent.log
#>
$ErrorActionPreference = 'Continue'
$dir = Join-Path $env:LOCALAPPDATA 'Oryn\model-manager'
$request = Join-Path $dir 'restart.request'
$status = Join-Path $dir 'status.json'
$log = Join-Path $env:LOCALAPPDATA 'Oryn\ollama-restart-agent.log'
$gpu = Join-Path $PSScriptRoot 'ollama-gpu.ps1'
New-Item -ItemType Directory -Force $dir | Out-Null

function Log($m) { "{0:yyyy-MM-ddTHH:mm:ss.fffzzz};Information;{1}" -f (Get-Date), $m | Add-Content -Path $log -Encoding UTF8 }
function Set-Status($state, $message) {
  @{ state = $state; message = $message; at = (Get-Date).ToString('o') } | ConvertTo-Json |
    Set-Content -Path $status -Encoding UTF8
}

Log 'command=agent;event=start'
if (-not (Test-Path $status)) { Set-Status 'idle' '' }

while ($true) {
  if (Test-Path $request) {
    $id = (Get-Content $request -Raw -ErrorAction SilentlyContinue)
    $id = if ($id) { $id.Trim() } else { '' }
    Remove-Item $request -Force -ErrorAction SilentlyContinue
    Log "command=restart;id=$id;event=start"
    Set-Status 'running' 'Ollama wird neu gestartet'
    try {
      $out = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $gpu -Mode restart 2>&1 | Out-String
      $ok = $LASTEXITCODE -eq 0
      $last = ($out -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
      if ($ok) { Set-Status 'done' 'Ollama neu gestartet'; Log "command=restart;id=$id;event=done" }
      else { Set-Status 'failed' "Fehler: $last"; Log "command=restart;id=$id;event=failed;exit=$LASTEXITCODE" }
    } catch {
      Set-Status 'failed' "Fehler: $($_.Exception.Message)"
      Log "command=restart;id=$id;event=failed;error=$($_.Exception.Message)"
    }
  }
  Start-Sleep -Seconds 2
}
