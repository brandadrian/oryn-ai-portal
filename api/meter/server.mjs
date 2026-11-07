// Mess-Proxy zwischen nginx und Ollama. Reicht alles unverändert durch und schreibt
// pro Inferenz-Anfrage eine JSON-Zeile nach Loki (Client, Modell, Tokens, Zeiten, Status).
// Keine Abhängigkeiten, Node 22. Prompt-Inhalte werden NICHT gespeichert.
import http from 'node:http';

const OLLAMA = new URL(process.env.OLLAMA_URL || 'http://host.docker.internal:11434');
const LOKI = process.env.LOKI_URL || '';               // z.B. http://host.docker.internal:3100
const PORT = Number(process.env.PORT || 8080);
const INFERENCE = /^\/(api\/(chat|generate|embed|embeddings)|v1\/(chat\/completions|completions|embeddings))$/;

// ---------- Loki ----------
let queue = [];
async function flush() {
  if (!LOKI || queue.length === 0) return;
  const batch = queue; queue = [];
  const streams = new Map();
  for (const e of batch) {
    const labels = { job: 'ollama-api', model: e.model || 'unbekannt', client: e.client, endpoint: e.endpoint };
    const key = JSON.stringify(labels);
    if (!streams.has(key)) streams.set(key, { stream: labels, values: [] });
    streams.get(key).values.push([String(e.ts * 1e6), JSON.stringify(e)]);
  }
  try {
    const r = await fetch(`${LOKI.replace(/\/$/, '')}/loki/api/v1/push`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ streams: [...streams.values()] }),
    });
    if (!r.ok) console.error(`loki ${r.status}: ${(await r.text()).slice(0, 200)}`);
  } catch (err) {
    console.error(`loki nicht erreichbar: ${err.message}`);
    if (queue.length < 5000) queue = batch.concat(queue);   // später nochmal
  }
}
setInterval(flush, 5000).unref();

// ---------- Client erkennen ----------
function clientName(ua = '') {
  const u = ua.toLowerCase();
  if (u.includes('copilot') || u.includes('vscode')) return 'copilot';
  if (u.includes('open-webui') || u.includes('openwebui')) return 'open-webui';
  if (u.startsWith('curl')) return 'curl';
  if (u.includes('python')) return 'python';
  if (u.includes('powershell')) return 'powershell';
  if (u.includes('openai/')) return 'openai-sdk';
  if (u.includes('node') || u.includes('undici')) return 'node';
  return ua ? 'andere' : 'unbekannt';
}

// ---------- Antwort auswerten ----------
// Ollama-API: letztes Objekt (done:true) hat prompt_eval_count, eval_count, *_duration (ns).
// OpenAI-API: "usage" (bei Stream nur mit stream_options.include_usage, das setzen wir).
function readStats(obj, s) {
  if (!obj || typeof obj !== 'object') return;
  if (obj.prompt_eval_count != null) s.prompt_tokens = obj.prompt_eval_count;
  if (obj.eval_count != null) s.output_tokens = obj.eval_count;
  if (obj.prompt_eval_duration != null) s.prompt_ms = Math.round(obj.prompt_eval_duration / 1e6);
  if (obj.eval_duration != null) s.output_ms = Math.round(obj.eval_duration / 1e6);
  if (obj.load_duration != null) s.load_ms = Math.round(obj.load_duration / 1e6);
  if (obj.total_duration != null) s.ollama_ms = Math.round(obj.total_duration / 1e6);
  if (obj.prompt_eval_cached_count != null) s.cached_tokens = obj.prompt_eval_cached_count;
  if (obj.done_reason) s.done_reason = obj.done_reason;
  // OpenAI-API von Ollama liefert zusätzlich "timings" (llama.cpp)
  if (obj.timings) {
    if (obj.timings.prompt_ms != null) s.prompt_ms = Math.round(obj.timings.prompt_ms);
    if (obj.timings.predicted_ms != null) s.output_ms = Math.round(obj.timings.predicted_ms);
  }
  if (obj.usage) {
    s.prompt_tokens = obj.usage.prompt_tokens ?? s.prompt_tokens;
    s.output_tokens = obj.usage.completion_tokens ?? s.output_tokens;
    const cached = obj.usage.prompt_tokens_details?.cached_tokens;
    if (cached != null) s.cached_tokens = cached;
  }
  const fr = obj.choices?.[0]?.finish_reason;
  if (fr) s.done_reason = fr;
  if (obj.error) s.error = String(obj.error.message ?? obj.error).slice(0, 300);
}

function makeParser(contentType, s) {
  let buf = '';
  const isSse = contentType.includes('text/event-stream');
  const handle = (line) => {
    line = line.trim();
    if (!line) return;
    if (isSse) {
      if (!line.startsWith('data:')) return;
      line = line.slice(5).trim();
      if (line === '[DONE]') return;
    }
    try { readStats(JSON.parse(line), s); } catch { /* unvollständig/kein JSON */ }
  };
  return {
    push(chunk) {
      buf += chunk.toString('utf8');
      let i;
      while ((i = buf.indexOf('\n')) >= 0) { handle(buf.slice(0, i)); buf = buf.slice(i + 1); }
      if (buf.length > 4_000_000) buf = buf.slice(-100_000);  // Schutz bei riesigen Antworten ohne Zeilenumbruch
    },
    end() { handle(buf); buf = ''; },
  };
}

// ---------- Proxy ----------
const server = http.createServer((req, res) => {
  const t0 = Date.now();
  const path = (req.url || '/').split('?')[0];
  const measure = req.method === 'POST' && INFERENCE.test(path);
  const chunks = [];

  req.on('data', (c) => chunks.push(c));
  req.on('end', () => {
    let body = Buffer.concat(chunks);
    const s = {
      ts: t0, endpoint: path, client: clientName(req.headers['user-agent']),
      user: String(req.headers['x-gateway-user'] || '') || undefined,   // E-Mail aus dem Token-Portal
      user_agent: (req.headers['user-agent'] || '').slice(0, 200),
      ip: String(req.headers['x-forwarded-for'] || req.socket.remoteAddress || '').split(',')[0].trim(),
      request_bytes: body.length,
    };

    if (measure) {
      try {
        const j = JSON.parse(body.toString('utf8'));
        s.model = j.model;
        // Ollama-API streamt standardmässig, OpenAI-API nur mit stream:true, Embeddings nie
        s.stream = path.includes('embed') ? false : path.startsWith('/v1/') ? j.stream === true : j.stream !== false;
        if (Array.isArray(j.messages)) s.messages = j.messages.length;
        if (Array.isArray(j.tools)) s.tools = j.tools.length;
        if (j.options?.num_ctx) s.num_ctx = j.options.num_ctx;
        // Bei OpenAI-Streams Token-Zahlen anfordern (zusätzlicher letzter Chunk, OpenAI-Standard)
        if (path.startsWith('/v1/') && j.stream === true && !j.stream_options?.include_usage) {
          j.stream_options = { ...(j.stream_options || {}), include_usage: true };
          body = Buffer.from(JSON.stringify(j));
        }
      } catch { /* kein JSON: unverändert durchreichen */ }
    }

    // Host-Header bleibt "localhost" (setzt nginx), sonst lehnt Ollama ab
    const headers = { ...req.headers, 'content-length': String(body.length) };
    delete headers['transfer-encoding'];
    delete headers['x-gateway-user'];
    const up = http.request({
      hostname: OLLAMA.hostname, port: OLLAMA.port || 80, path: req.url, method: req.method, headers,
    }, (upRes) => {
      res.writeHead(upRes.statusCode || 502, upRes.headers);
      s.status = upRes.statusCode;
      const parser = measure ? makeParser(String(upRes.headers['content-type'] || ''), s) : null;
      let first = true, bytes = 0;
      upRes.on('data', (c) => {
        if (first) { s.first_byte_ms = Date.now() - t0; first = false; }
        bytes += c.length;
        parser?.push(c);
        res.write(c);
      });
      upRes.on('end', () => {
        res.end();
        if (!measure) return;
        parser.end();
        s.response_bytes = bytes;
        s.duration_ms = Date.now() - t0;
        // Zeit, die nicht Rechnen/Laden war: vor allem Warteschlange (Ollama rechnet eine Anfrage nach der anderen)
        if (s.ollama_ms != null) s.wait_ms = Math.max(0, s.duration_ms - s.ollama_ms);
        if (s.output_tokens && s.output_ms) s.output_tps = Math.round(s.output_tokens / (s.output_ms / 1000) * 10) / 10;
        if (s.prompt_tokens && s.prompt_ms) s.prompt_tps = Math.round(s.prompt_tokens / (s.prompt_ms / 1000));
        if (s.prompt_tokens && s.cached_tokens != null) s.cache_pct = Math.round(100 * s.cached_tokens / s.prompt_tokens);
        if (s.ollama_ms == null && s.prompt_ms != null && s.output_ms != null) s.wait_ms = Math.max(0, s.duration_ms - s.prompt_ms - s.output_ms);
        queue.push(s);
        console.log(`${s.status} ${s.client} ${s.model} ${path} prompt=${s.prompt_tokens ?? '?'} out=${s.output_tokens ?? '?'} ${s.duration_ms}ms`);
      });
      upRes.on('error', () => res.destroy());
    });

    up.on('error', (err) => {
      if (!res.headersSent) { res.writeHead(502, { 'Content-Type': 'application/json' }); }
      res.end(JSON.stringify({ error: `ollama nicht erreichbar: ${err.message}` }));
      if (measure) { s.status = 502; s.error = err.message; s.duration_ms = Date.now() - t0; queue.push(s); }
    });
    // Client bricht ab -> Anfrage an Ollama abbrechen und als abgebrochen erfassen
    res.on('close', () => {
      if (!res.writableEnded) {
        up.destroy();
        if (measure) { s.status = s.status ?? 499; s.aborted = true; s.duration_ms = Date.now() - t0; queue.push(s); }
      }
    });
    up.end(body);
  });
});

server.requestTimeout = 0;      // lange Generierungen nicht abbrechen
server.headersTimeout = 0;
server.listen(PORT, () => console.log(`ollama-meter :${PORT} -> ${OLLAMA.href}, loki=${LOKI || 'aus'}`));
for (const sig of ['SIGTERM', 'SIGINT']) process.on(sig, async () => { await flush(); process.exit(0); });
