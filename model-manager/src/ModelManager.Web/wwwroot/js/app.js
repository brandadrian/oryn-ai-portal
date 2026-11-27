'use strict';

const $ = id => document.getElementById(id);
let models = [], busy = false, restartRunning = false, lastActive;

const ctx = n => n ? (n >= 1024 ? Math.round(n / 1024) + 'k' : n) + ' Kontext' : '';
const gb = b => (b / 1024 ** 3).toFixed(1) + ' GB';
const time = t => new Date(t).toLocaleString('de-CH', { weekday:'short', hour:'2-digit', minute:'2-digit' });
const opt = m => `<option value="${m.name.replace(/"/g,'&quot;')}">${m.name}${m.loaded ? ' (aktiv)' : ''}</option>`;

function render() {
  const active = models.find(m => m.loaded);
  $('dot').className = 'dot' + (active ? ' on' : '');
  $('activeName').textContent = active ? active.name : 'Kein Modell geladen';
  const where = active ? (active.gpuPercent >= 100 ? 'ganz auf der GPU' : `${active.gpuPercent}% GPU / ${100 - active.gpuPercent}% CPU`) : '';
  $('activeSub').textContent = active
    ? [ctx(active.contextLength), `${gb(active.sizeVram)} VRAM, ${where}`, `bis ${time(active.expiresAt)}`].filter(Boolean).join(' · ')
    : '';

  // aktives Modell vorauswählen (beim Start und wenn ein anderes geladen wurde), sonst Auswahl behalten
  const activeChanged = active?.name !== lastActive;
  lastActive = active?.name;
  const selected = (activeChanged && active) ? active.name : ($('model').value || active?.name);
  const mine = models.filter(m => m.configured && m.installed);
  const other = models.filter(m => !m.configured && m.installed);
  $('model').innerHTML = `<optgroup label="Meine Modelle">${mine.map(opt).join('')}</optgroup>`
    + (other.length ? `<optgroup label="Weitere">${other.map(opt).join('')}</optgroup>` : '');
  if (models.some(m => m.name === selected && m.installed)) $('model').value = selected;
  update();
}

function update() {
  const m = models.find(x => x.name === $('model').value);
  $('desc').textContent = [ctx(m?.contextLength), m?.description].filter(Boolean).join(' · ');
  $('load').disabled = busy || !m || m.loaded;
  $('unload').disabled = busy || !models.some(x => x.loaded);
  $('restart').disabled = busy || restartRunning;
}

async function refreshRestart() {
  try {
    const s = await (await fetch('api/restart')).json();
    $('restart').hidden = !s.available;
    const running = s.state === 'pending' || s.state === 'running';
    if (running || restartRunning) {
      $('msg').className = 'msg ' + (s.state === 'failed' ? 'err' : 'sub');
      $('msg').textContent = s.message || '';
    }
    restartRunning = running;
    update();
  } catch { }
}

async function refresh() {
  if (busy) return;
  try {
    const r = await fetch('api/models');
    if (!r.ok) throw new Error('HTTP ' + r.status);
    models = await r.json();
    render();
  } catch (e) { $('activeName').textContent = 'Ollama nicht erreichbar'; $('activeSub').textContent = e.message; }
}

async function act(action, name, label) {
  busy = true; update();
  $('msg').className = 'msg sub'; $('msg').textContent = `${label} ${name} …`;
  try {
    const r = await fetch('api/' + action, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ name }) });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || 'HTTP ' + r.status);
    $('msg').textContent = '';
  } catch (e) { $('msg').className = 'msg err'; $('msg').textContent = e.message; }
  busy = false; refresh();
}

$('model').onchange = update;
$('refresh').onclick = () => {
  const b = $('refresh'); b.classList.remove('spin'); void b.offsetWidth; b.classList.add('spin');
  refresh(); refreshRestart();
};
$('load').onclick = () => act('load', $('model').value, 'Lade');
$('unload').onclick = () => act('unload', models.find(m => m.loaded).name, 'Entlade');
$('restart').onclick = async () => {
  if (!confirm('Ollama neu starten? Alle Modelle werden entladen, laufende Anfragen brechen ab.')) return;
  const r = await fetch('api/restart', { method:'POST' });
  if (!r.ok) { $('msg').className = 'msg err'; $('msg').textContent = (await r.json().catch(() => ({}))).error || 'HTTP ' + r.status; return; }
  restartRunning = true; refreshRestart();
};

refresh(); refreshRestart();
setInterval(refresh, 5000);
setInterval(refreshRestart, 2000);
