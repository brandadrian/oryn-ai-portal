<#
.SYNOPSIS
  Registriert (oder entfernt) die Aufgabe "Oryn Ollama Scout (11435)": startet beim Anmelden die zweite
  Ollama-Instanz (RX 7800 XT, Port 11435) über "ollama-gpu.ps1 -Mode second".

.DESCRIPTION
  Instanz A (11434) startet die Ollama-Taskleisten-App selbst. Die Aufgabe wartet auf A, startet nur B
  und tut nichts, wenn B schon läuft. Läuft als aktueller Benutzer, keine Admin-Rechte nötig.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install-ollama-autostart.ps1            # registrieren + testen
  powershell -ExecutionPolicy Bypass -File scripts\install-ollama-autostart.ps1 -Uninstall # entfernen
#>
param([switch]$Uninstall)

$name = 'Oryn Ollama Scout (11435)'
if ($Uninstall) { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "Aufgabe '$name' entfernt."; return }

$script = Join-Path $PSScriptRoot 'ollama-gpu.ps1'
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`" -Mode second"
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = 'PT30S'   # Taskleisten-App zuerst starten lassen
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description 'Startet die zweite Ollama-Instanz (RX 7800 XT, Port 11435). Quelle: oryn-ai-portal\scripts' -Force | Out-Null
Write-Host "Aufgabe '$name' registriert (beim Anmelden, $user)."
