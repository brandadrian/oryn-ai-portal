<#
.SYNOPSIS
  Registriert (oder entfernt) die Aufgabe "Oryn Docker-Stack": führt beim Anmelden scripts\start-all.ps1 aus.
  Startet Docker Desktop bei Bedarf selbst und bringt nach einem Docker-Reset alle Stacks wieder hoch.
  Läuft als aktueller Benutzer, keine Admin-Rechte nötig.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\install-start-all.ps1            # registrieren
  powershell -ExecutionPolicy Bypass -File scripts\install-start-all.ps1 -Uninstall # entfernen
#>
param([switch]$Uninstall)

$name = 'Oryn Docker-Stack'
if ($Uninstall) { Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "Aufgabe '$name' entfernt."; return }

$script = Join-Path $PSScriptRoot 'start-all.ps1'
$user = "$env:USERDOMAIN\$env:USERNAME"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$trigger.Delay = 'PT1M'
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description 'Startet Docker Desktop und alle Oryn-Stacks (start-all.ps1). Quelle: oryn-ai-portal\scripts' -Force | Out-Null
Write-Host "Aufgabe '$name' registriert (beim Anmelden, $user)."
