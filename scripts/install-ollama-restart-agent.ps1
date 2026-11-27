<#
.SYNOPSIS
  Registriert (oder entfernt) die Aufgabe "Oryn Ollama Restart-Agent": startet beim Anmelden
  scripts\ollama-restart-agent.ps1, damit der Model-Manager (management.oryn) Ollama neu starten kann.

.DESCRIPTION
  Läuft als aktueller Benutzer (interaktiv, wie die Ollama-Taskleisten-App), keine Admin-Rechte nötig.
  Startet die Aufgabe nach dem Registrieren sofort.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install-ollama-restart-agent.ps1            # registrieren + starten
  powershell -ExecutionPolicy Bypass -File scripts\install-ollama-restart-agent.ps1 -Uninstall # entfernen
#>
param([switch]$Uninstall)

$name = 'Oryn Ollama Restart-Agent'
if ($Uninstall) {
  Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Aufgabe '$name' entfernt."; return
}

$script = Join-Path $PSScriptRoot 'ollama-restart-agent.ps1'
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description 'Startet Ollama neu, wenn der Model-Manager es anfordert. Quelle: oryn-ai-portal\scripts' -Force | Out-Null
Start-ScheduledTask -TaskName $name
Write-Host "Aufgabe '$name' registriert und gestartet ($user)."
