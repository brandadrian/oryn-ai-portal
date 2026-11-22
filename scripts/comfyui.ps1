<#
.SYNOPSIS
  Startet ComfyUI (aus Comfy Desktop) ohne Fenster als Bild-Engine für Open WebUI: http://127.0.0.1:8188

.DESCRIPTION
  Nutzt die Installation von Comfy Desktop (ROCm-PyTorch) und deren Modell-Ordner
  (%LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Shared\models). Open WebUI erreicht es über host.docker.internal:8188.

  GPU: HIP-Gerät 1 = RX 7800 XT (ROCm-Reihenfolge: 0 = R9700, 1 = RX 7800 XT, unabhängig von den Vulkan-Indizes von Ollama).
  Auf der R9700 ist kein Platz: qwen3.8:27b-q4-256k belegt dort ca. 28 GB (23 GB + Rest im geteilten Speicher).
  ROCm sieht unter Windows den VRAM nicht, den Ollama (Vulkan) belegt. Läuft ComfyUI darüber, schiebt Windows Teile von Ollama
  in den RAM (gemessen: qwen3.8 fiel von 33 auf 7 t/s, bis das Modell neu geladen wurde). Deshalb:
    --reserve-vram 11     lässt auf der RX 11 GB frei (Scout qwen3.5:9b ca. 8.5 GB + Desktop), ComfyUI nimmt höchstens
                          ca. 5.5 GB und streamt den Rest der Gewichte aus dem RAM
    --disable-smart-memory  schiebt die Modelle nach jedem Bild in den RAM zurück, damit Ollama den VRAM wieder hat
  Qwen-Image 2.1 Turbo (int8): DiT 7.3 GB + Text-Encoder 9.4 GB, nacheinander geladen.

  -Mode start      starten, falls nicht schon aktiv (Standard)
  -Mode stop       beenden
  -Mode restart    neu starten
  -Mode status     läuft es? GPU und freier Speicher laut ComfyUI
  -Mode install    Aufgabe "Oryn ComfyUI (8188)" registrieren: Start beim Anmelden
  -Mode uninstall  Aufgabe entfernen
  Log: %LOCALAPPDATA%\Comfy-Desktop\ComfyUI-Installs\ComfyUI\logs\headless-8188.log
#>
param([ValidateSet('start', 'stop', 'restart', 'status', 'install', 'uninstall')][string]$Mode = 'start')

$port = 8188
$base = Join-Path $env:LOCALAPPDATA 'Comfy-Desktop'
$root = Join-Path $base 'ComfyUI-Installs\ComfyUI'
$py = Join-Path $root 'ComfyUI\.venv\Scripts\python.exe'
$main = Join-Path $root 'ComfyUI\main.py'
$paths = Join-Path $env:APPDATA 'Comfy Desktop\instance-model-paths\inst-1794042434584.yaml'
$out = Join-Path $base 'ComfyUI-Shared\output'
$log = Join-Path $root 'logs\headless-8188.log'
$task = "Oryn ComfyUI ($port)"
# ROCm-Gerät und VRAM, den ComfyUI frei lässt (GB). ROCm sieht den VRAM nicht, den Ollama (Vulkan) belegt.
$device = '1'      # RX 7800 XT
$reserve = '11'    # Scout-Instanz (11435) + Desktop

function Get-Comfy { Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match "main\.py.*--port\W+$port\b" } }
function Test-Comfy { try { Invoke-RestMethod "http://127.0.0.1:$port/system_stats" -TimeoutSec 3 } catch { $null } }

switch ($Mode) {
  'install' {
    $user = "$env:USERDOMAIN\$env:USERNAME"
    $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Mode start"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    $trigger.Delay = 'PT45S'
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
      -Description 'ComfyUI headless (RX 7800 XT, Port 8188) für Open WebUI Bildgenerierung. Quelle: oryn-ai-portal\scripts\comfyui.ps1' -Force | Out-Null
    Write-Host "Aufgabe '$task' registriert (beim Anmelden, $user)."
    return
  }
  'uninstall' { Unregister-ScheduledTask -TaskName $task -Confirm:$false -ErrorAction SilentlyContinue; Write-Host "Aufgabe '$task' entfernt."; return }
  'status' {
    $s = Test-Comfy
    if (-not $s) { Write-Host "ComfyUI ($port) läuft nicht."; return }
    $d = $s.devices[0]
    Write-Host ("ComfyUI {0} läuft: {1}, frei {2:N1} von {3:N1} GB (laut ROCm)" -f $s.system.comfyui_version, $d.name, ($d.vram_free / 1GB), ($d.vram_total / 1GB))
    return
  }
  { $_ -in 'stop', 'restart' } {
    Get-Comfy | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Host "ComfyUI ($port) beendet."
    if ($Mode -eq 'stop') { return }
    Start-Sleep 2
  }
}

if (Test-Comfy) { Write-Host "ComfyUI ($port) läuft bereits."; return }

# Ollama setzt HIP_VISIBLE_DEVICES=-1 (Vulkan-Modus), für ComfyUI nur die gewählte Karte freigeben
$env:HIP_VISIBLE_DEVICES = $device
$env:PYTHONIOENCODING = 'utf-8'
# Avast setzt SSLKEYLOGFILE auf eine Pipe, damit stürzt OpenSSL in Python ab ("no OPENSSL_Applink")
Remove-Item Env:SSLKEYLOGFILE -ErrorAction SilentlyContinue
# hipBLASLt (ROCm 7.14, Windows, gfx1201) stürzt bei fp32-Batch-Matmul (int8-Text-Encoder) mit Zugriffsverletzung ab.
# Nur beide Variablen zusammen umgehen es (PyTorch und rocBLAS ohne hipBLASLt).
$env:TORCH_BLAS_PREFER_HIPBLASLT = '0'
$env:ROCBLAS_USE_HIPBLASLT = '0'
$cmdArgs = @($main, '--listen', '127.0.0.1', '--port', $port, '--disable-auto-launch',
  '--extra-model-paths-config', $paths, '--output-directory', $out,
  '--reserve-vram', $reserve, '--disable-smart-memory')
$quoted = ($cmdArgs | ForEach-Object { '"' + $_ + '"' }) -join ' '
Start-Process -FilePath 'cmd.exe' -ArgumentList "/c `"`"$py`" $quoted > `"$log`" 2>&1`"" -WorkingDirectory (Split-Path $main) -WindowStyle Hidden

for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep 2
  if (Test-Comfy) { Write-Host "ComfyUI läuft: http://127.0.0.1:$port"; return }
}
Write-Host "ComfyUI startet nicht, siehe $log"
exit 1
