<#
.SYNOPSIS
  Kurzer, reproduzierbarer Ollama-Benchmark (ca. 5-8 min) für eine Instanz, z. B. R9700 auf Port 11434.

.DESCRIPTION
  Misst pro Modell über die Ollama-API (/api/generate, Felder load_duration, prompt_eval_*, eval_*):
    load   Modell-Ladezeit (Modell vorher entladen; ein Vorlauf füllt den Windows-Dateicache,
           damit beide Läufe aus dem RAM laden und nur PCIe/VRAM-Upload gemessen wird)
    short  kurzer Prompt (~60 Tokens), 256 Tokens Generierung, 3 Wiederholungen (Median)
    long   langer Prompt (~24k Tokens), 128 Tokens Generierung, 1 Wiederholung
  Jeder Prompt beginnt mit einer Zufalls-Kennung, damit Ollama keinen Prefix-Cache wiederverwendet.
  temperature 0, fester Seed, think=false -> identische Arbeit in beiden Läufen.
  Ergebnis: bench\results\<Label>.json (+ Tabelle). Mit -Compare zwei Läufe vergleichen.

  Vorher: nichts anderes auf der Instanz laufen lassen (Open WebUI/API-Clients ruhig).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\bench-gpu.ps1 -Label slot1-x16
  powershell -ExecutionPolicy Bypass -File scripts\bench-gpu.ps1 -Label slot2-x4
  powershell -ExecutionPolicy Bypass -File scripts\bench-gpu.ps1 -Compare slot1-x16,slot2-x4
#>
param(
  [string]$Label = ('run-' + (Get-Date -Format 'yyyyMMdd-HHmm')),
  [string]$Endpoint = 'http://127.0.0.1:11434',
  [string[]]$Models = @('qwen3.5:35b-a3b-q4-256k', 'qwen3.8:27b-q4-128k'),
  [int]$LongLines = 850,       # ~28 Tokens/Zeile -> ~24k Tokens
  [int]$ShortReps = 3,
  [int]$NumCtx = 0,           # >0 überschreibt num_ctx (z. B. 16384 für 70B auf 48 GB)
  [string[]]$Compare
)

$ErrorActionPreference = 'Stop'
# mit -File kommen Listen als ein String "a,b" an
$Models = @($Models | ForEach-Object { $_ -split ',' } | Where-Object { $_ })
if ($Compare) { $Compare = @($Compare | ForEach-Object { $_ -split ',' } | Where-Object { $_ }) }
$resDir = Join-Path $PSScriptRoot '..\bench\results'
New-Item -ItemType Directory -Force $resDir | Out-Null

function Get-Median([double[]]$x) { $s = $x | Sort-Object; if (-not $s) { return $null }; $n = $s.Count; if ($n % 2) { $s[[int](($n - 1) / 2)] } else { ($s[$n / 2 - 1] + $s[$n / 2]) / 2 } }

if ($Compare) {
  if ($Compare.Count -ne 2) { throw '-Compare braucht genau zwei Labels, z. B. -Compare slot1-x16,slot2-x4' }
  $a = Get-Content (Join-Path $resDir "$($Compare[0]).json") -Raw | ConvertFrom-Json
  $b = Get-Content (Join-Path $resDir "$($Compare[1]).json") -Raw | ConvertFrom-Json
  Write-Host ("A = {0} ({1})`nB = {2} ({3})" -f $a.label, $a.pcie, $b.label, $b.pcie)
  $rows = foreach ($r in $a.results) {
    $o = $b.results | Where-Object { $_.model -eq $r.model -and $_.test -eq $r.test }
    if (-not $o) { continue }
    foreach ($m in 'load_s', 'wall_s', 'pp_tps', 'tg_tps') {
      if ($null -eq $r.$m -or $null -eq $o.$m) { continue }
      [pscustomobject]@{ Modell = $r.model; Test = $r.test; Wert = $m; A = $r.$m; B = $o.$m
        'Diff %' = if ($r.$m) { [math]::Round(($o.$m - $r.$m) / $r.$m * 100, 1) } else { $null } }
    }
  }
  $rows | Format-Table -AutoSize
  return
}

function Invoke-Gen([hashtable]$body) {
  $json = $body | ConvertTo-Json -Depth 5 -Compress
  Invoke-RestMethod "$Endpoint/api/generate" -Method Post -ContentType 'application/json; charset=utf-8' `
    -Body ([Text.Encoding]::UTF8.GetBytes($json)) -TimeoutSec 900
}
function Unload([string]$m) {
  Invoke-Gen @{ model = $m; keep_alive = 0 } | Out-Null
  for ($i = 0; $i -lt 30; $i++) {
    $ps = Invoke-RestMethod "$Endpoint/api/ps"
    if (-not ($ps.models | Where-Object name -eq $m)) { return }
    Start-Sleep -Milliseconds 500
  }
}
function Nonce { [guid]::NewGuid().ToString('N').Substring(0, 12) }

# langer Kontext: deterministischer Messprotokoll-Text
$sb = [Text.StringBuilder]::new()
for ($i = 1; $i -le $LongLines; $i++) {
  $st = @('ok', 'warn', 'fehler')[$i % 3]; $deg = (($i * 7919) % 1000) / 10
  [void]$sb.AppendLine("Eintrag ${i}: Sensor S$($i % 97) in Halle $($i % 13) meldete $deg Grad und Status $st.")
}
$longText = $sb.ToString()
$shortQ = 'Erkläre in einem Absatz, wie ein Wärmetauscher funktioniert, und nenne drei typische Einsatzgebiete.'
$longQ = 'Welche Halle hat die meisten Einträge mit Status fehler? Antworte kurz mit Begründung.'
$opts = @{ temperature = 0; seed = 42 }
if ($NumCtx -gt 0) { $opts.num_ctx = $NumCtx }

# PCIe-Link der Karten (Hinweis: AMD-Karten haben eine interne PCIe-Bridge; Windows zeigt teils deren Link)
$pcie = (Get-PnpDevice -Class Display -PresentOnly | Where-Object FriendlyName -match 'Radeon' | ForEach-Object {
  $w = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_PciDevice_CurrentLinkWidth -ErrorAction SilentlyContinue).Data
  $s = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName DEVPKEY_PciDevice_CurrentLinkSpeed -ErrorAction SilentlyContinue).Data
  '{0} Gen{1} x{2}' -f ($_.FriendlyName -replace 'AMD Radeon ', ''), $s, $w } | Sort-Object -Unique) -join '; '
$ver = (Invoke-RestMethod "$Endpoint/api/version").version
Write-Host "Benchmark '$Label' gegen $Endpoint (Ollama $ver)`nPCIe: $pcie"

$results = [Collections.Generic.List[object]]::new()
$t0 = Get-Date
foreach ($m in $Models) {
  Write-Host "`n== $m =="
  # andere Modelle auf dieser Instanz entladen
  (Invoke-RestMethod "$Endpoint/api/ps").models | ForEach-Object { Unload $_.name }

  # Vorlauf: Dateicache füllen, dann entladen und Ladezeit messen
  Write-Host '  Vorlauf (Dateicache) ...'
  Invoke-Gen @{ model = $m; keep_alive = '10m'; options = $opts } | Out-Null
  Unload $m
  # 2x laden (Median); load_duration aus einer Mini-Generierung, Wall = Gesamtzeit der Anfrage
  $ld = @(); $wl = @()
  for ($k = 1; $k -le 2; $k++) {
    if ($k -gt 1) { Unload $m }
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $r = Invoke-Gen @{ model = $m; prompt = "[$(Nonce)] Hi"; stream = $false; think = $false; keep_alive = '10m'; options = $opts + @{ num_predict = 1 } }
    $sw.Stop(); $ld += $r.load_duration / 1e9; $wl += $sw.Elapsed.TotalSeconds
  }
  $load = [math]::Round((Get-Median $ld), 2); $wall = [math]::Round((Get-Median $wl), 2)
  $vram = [math]::Round((((Invoke-RestMethod "$Endpoint/api/ps").models | Where-Object name -eq $m).size_vram) / 1GB, 1)
  Write-Host ("  load: {0} s (Wall {1} s; Einzelwerte {2}; VRAM laut Ollama {3} GB)" -f $load, $wall, (($ld | % { [math]::Round($_, 1) }) -join '/'), $vram)
  $results.Add([pscustomobject]@{ model = $m; test = 'load'; load_s = $load; wall_s = $wall; vram_gb = $vram })

  # Warm-up (Shader/Graph), nicht gewertet
  Invoke-Gen @{ model = $m; prompt = "[$(Nonce)] Hallo"; stream = $false; think = $false; options = $opts + @{ num_predict = 16 } } | Out-Null

  foreach ($t in @(@{ name = 'short'; reps = $ShortReps; predict = 256; prompt = { "[$(Nonce)] $shortQ" } },
                   @{ name = 'long'; reps = 1; predict = 128; prompt = { "[$(Nonce)] Messprotokoll:`n$longText`n$longQ" } })) {
    $pp = @(); $tg = @(); $np = @(); $ng = @()
    for ($k = 1; $k -le $t.reps; $k++) {
      $r = Invoke-Gen @{ model = $m; prompt = (& $t.prompt); stream = $false; think = $false; keep_alive = '10m'; options = $opts + @{ num_predict = $t.predict } }
      $pp += $r.prompt_eval_count / ($r.prompt_eval_duration / 1e9); $tg += $r.eval_count / ($r.eval_duration / 1e9)
      $np += $r.prompt_eval_count; $ng += $r.eval_count
      Write-Host ("  {0} #{1}: Prompt {2} Tok @ {3:N0} t/s | Gen {4} Tok @ {5:N1} t/s" -f $t.name, $k, $r.prompt_eval_count, $pp[-1], $r.eval_count, $tg[-1])
    }
    $results.Add([pscustomobject]@{ model = $m; test = $t.name; prompt_tokens = [int](Get-Median $np); gen_tokens = [int](Get-Median $ng)
      pp_tps = [math]::Round((Get-Median $pp), 1); tg_tps = [math]::Round((Get-Median $tg), 1) })
  }
}

$out = [pscustomobject]@{ label = $Label; date = (Get-Date).ToString('s'); endpoint = $Endpoint; ollama = $ver; pcie = $pcie
  duration_s = [math]::Round(((Get-Date) - $t0).TotalSeconds); results = $results }
$file = Join-Path $resDir "$Label.json"
$out | ConvertTo-Json -Depth 5 | Set-Content $file -Encoding UTF8
Write-Host "`nErgebnis ($($out.duration_s) s) -> $file"
$results | Format-Table model, test, load_s, vram_gb, prompt_tokens, pp_tps, gen_tokens, tg_tps -AutoSize
