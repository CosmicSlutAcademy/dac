"""GCI Command Deck — unified GCIA (investigation) + GCIAu (authority) web UI.

One codebase, stdlib only: runs in Termux (Android) and WSL/Ubuntu (Windows 11).
Security: loopback-only by default. To expose over LAN you must set --token.
"""

import datetime
import json
import os
import secrets
import socket
import subprocess
import time
from collections import defaultdict, deque
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VERSION = "0.2.0"

DECK_JOURNAL = Path(os.path.expanduser("~/.gcia/deck-journal.jsonl"))
RATE_LIMITS = {"GET": (90, 60), "POST": (25, 60)}  # (max, window_seconds)
_hits = defaultdict(deque)
_host_ok = ""
_host_token = ""


def _journal(entry):
    try:
        DECK_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with open(DECK_JOURNAL, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def host_allowed(host_header, token):
    """Loopback binding: refuse any non-loopback Host to blunt DNS rebinding.
    Network binding (with --token) accepts any Host."""
    if token:
        return True
    h = (host_header or "").split(":")[0].lower()
    return h in ("127.0.0.1", "localhost", "::1", "0:0:0:0:0:0:0:1") or _host_ok == h


def rate_ok(ip, method):
    """Token-bucket-ish limiter. Returns True if within budget."""
    key = (ip, method)
    max_n, window = RATE_LIMITS.get(method, RATE_LIMITS["GET"])
    now = time.time()
    q = _hits[key]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= max_n:
        return False
    q.append(now)
    return True

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GCI Command Deck</title>
<style>
:root{--bg:#05080f;--panel:#0a1220;--line:#1c2a44;--txt:#cfe3ff;--dim:#7f97b8;
--gcia:#35d6ff;--gciau:#ffd166;--ok:#3ddc84;--warn:#ffb020;--alert:#ff5470}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);
font:14px/1.5 ui-monospace,Menlo,Consolas,monospace}
header{padding:16px 22px;border-bottom:1px solid var(--line);display:flex;gap:18px;
align-items:center;flex-wrap:wrap;background:linear-gradient(180deg,#0b1424,#05080f)}
header h1{font-size:17px;margin:0;letter-spacing:2px}
.gcia{color:var(--gcia)} .gciau{color:var(--gciau)}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:16px 22px;max-width:1400px;margin:auto}
@media(max-width:900px){main{grid-template-columns:1fr}}
.col{border:1px solid var(--line);border-radius:10px;overflow:hidden}
.col>h2{margin:0;padding:10px 14px;font-size:13px;letter-spacing:2px;border-bottom:1px solid var(--line)}
#gcia-col>h2{color:var(--gcia);background:#081627}
#gciau-col>h2{color:var(--gciau);background:#171407}
.card{margin:12px;padding:12px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}
.card h3{margin:0 0 8px;font-size:12px;color:var(--dim);letter-spacing:1px}
button{background:#12243f;color:var(--txt);border:1px solid var(--line);border-radius:6px;
padding:6px 12px;cursor:pointer;font:inherit}button:hover{border-color:var(--gcia)}
button.au:hover{border-color:var(--gciau)}
input,select,textarea{background:#060b14;color:var(--txt);border:1px solid var(--line);
border-radius:6px;padding:6px;font:inherit;width:100%;margin:3px 0}
.row{display:flex;gap:8px;flex-wrap:wrap}.row>*{flex:1;min-width:110px}
.out{margin-top:8px;white-space:pre-wrap;word-break:break-word;font-size:12px;color:#bcd4f2}
table{width:100%;border-collapse:collapse;font-size:12px;margin-top:6px}
td,th{border:1px solid var(--line);padding:4px 6px;text-align:left}
.badge{display:inline-block;padding:1px 8px;border-radius:99px;font-size:11px;border:1px solid var(--line)}
.ok{color:var(--ok)} .warn{color:var(--warn)} .alert{color:var(--alert)}
#toast{position:fixed;right:16px;bottom:16px;background:#12243f;border:1px solid var(--gcia);
padding:10px 14px;border-radius:8px;display:none;max-width:340px}
</style></head><body>
<header>
 <h1><span class="gcia">GCI</span> COMMAND DECK <span class="gciau">· GCIA ⊕ GCIAu</span></h1>
 <span class="badge" id="host">connecting…</span>
 <span class="badge" id="ver">gcia v?</span>
 <button onclick="doAudit()">Audit</button>
 <button onclick="doRecon()">Recon</button>
 <button onclick="doPatrol()">Patrol now</button>
 <button onclick="doGuard()">Mindguard</button>
</header>
<main>
 <div class="col" id="gcia-col"><h2>GCIA — INVESTIGATION</h2>
  <div class="card"><h3>DEVICE AUDIT</h3><div class="out" id="audit">Run audit to load.</div></div>
  <div class="card"><h3>NETWORK</h3>
   <div class="row"><button onclick="doRecon()">Recon LAN</button></div>
   <div class="row"><input id="scanhost" placeholder="host" value="127.0.0.1">
   <input id="scanports" placeholder="ports (e.g. 22,8080)"></div>
   <button onclick="doScan()">Scan host</button><div class="out" id="net"></div></div>
  <div class="card"><h3>CONTACT-LOG — MIND-LAYER EVIDENCE</h3>
   <textarea id="cltext" rows="3" placeholder="Describe the experience honestly…"></textarea>
   <div class="row">
    <select id="clmode"><option>awake</option><option>dream</option><option>hypnagogic</option><option>meditation</option><option>other</option></select>
    <select id="clmood"><option>calm</option><option>neutral</option><option>focused</option><option>anxious</option><option>overwhelmed</option><option>euphoric</option><option>other</option></select>
    <select id="cllabel"><option value="speculative">speculative</option><option value="insight">insight</option><option value="dream">dream</option><option value="distress">distress</option><option value="memory">memory</option><option value="other">other</option></select>
   </div>
   <div class="row">
    <input id="clsleep" type="number" step="0.1" placeholder="sleep h (0-24)">
    <input id="clstress" type="number" min="1" max="10" placeholder="stress 1-10">
    <input id="clcontext" placeholder="context (where/when)">
   </div>
   <button onclick="addContact()">Log entry (encrypted)</button>
   <button onclick="loadStats()">Journal stats</button><div class="out" id="clout"></div></div>
 </div>
 <div class="col" id="gciau-col"><h2>GCIAu — AUTHORITY</h2>
  <div class="card"><h3>MINDGUARD — PREDICTIVE CARE</h3><div class="out" id="guard">Run mindguard to load.</div></div>
  <div class="card"><h3>IMMUNITY — SELF-CHECK</h3><div class="out" id="immunity"><button class="au" onclick="immunity()">Run self-check</button></div></div>
  <div class="card"><h3>BVH — BEHAVIOR VERIFICATION</h3>
   <div class="row"><button class="au" onclick="bvhAnomaly()">Anomaly scan</button>
   <button class="au" onclick="bvhJournal()">Recent actions</button></div>
   <div class="row"><input id="bvhcmd" placeholder="command to preview (e.g. rm -rf /)">
   <button class="au" onclick="bvhPreview()">Preview</button></div>
   <div class="out" id="bvhout"></div></div>
  <div class="card"><h3>CHARTER</h3><div class="out" id="charter">Loading…</div></div>
  <div class="card"><h3>BRIEFINGS</h3>
   <div class="row"><select id="theme">
    <option value="phishing">phishing</option><option value="deepfake">deepfake</option>
    <option value="device">device</option><option value="network">network</option><option value="data">data</option>
   </select><button class="au" onclick="doBrief()">Generate briefing</button></div>
   <div class="out" id="brief"></div></div>
  <div class="card"><h3>REMOTE LINK — TOWER BRIDGE</h3>
   <div class="row"><button class="au" onclick="genKey()">Generate storm key</button>
   <button class="au" onclick="loadRemote()">Refresh peers</button></div>
   <textarea id="mypub" rows="2" readonly placeholder="your public key appears here — copy to the other tower"></textarea>
   <div class="row"><input id="peername" placeholder="peer name"><input id="peerpub" placeholder="paste peer public key"></div>
   <button class="au" onclick="grantPeer()">Import granted peer</button>
   <div class="out" id="remote"></div></div>
 </div>
</main>
<div id="toast"></div>
<script>
const CSRF='__CSRF__';
const $=id=>document.getElementById(id);
function toast(m){const t=$('toast');t.textContent=m;t.style.display='block';
 setTimeout(()=>t.style.display='none',4000)}
async function api(p,opts){opts=opts||{};
 if(opts.method==='POST'){opts.headers=Object.assign({'Content-Type':'application/json','X-GCI-CSRF':CSRF},opts.headers||{})}
 const r=await fetch(p,opts);
 const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||r.status);return j}
function esc(s){return String(s??'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
async function doAudit(){const o=$('audit');o.textContent='…';
 try{const a=await api('/api/audit');o.innerHTML=`<table><tr><th>key</th><th>value</th></tr>`+
 Object.entries(a).map(([k,v])=>`<tr><td>${esc(k)}</td><td>${esc(Array.isArray(v)?v.join(', '):v)}</td></tr>`).join('')+`</table>`}
 catch(e){o.textContent='ERR '+e.message}}
async function doRecon(){const o=$('net');o.textContent='sweeping…';
 try{const r=await api('/api/recon');o.textContent=r.live.map(h=>h.host+' '+h.name+' ports='+h.ports.join(',')).join('\\n')||'no live hosts'}
 catch(e){o.textContent='ERR '+e.message}}
async function doScan(){const o=$('net');o.textContent='scanning…';
 try{const r=await api('/api/scan?host='+encodeURIComponent($('scanhost').value)+'&ports='+encodeURIComponent($('scanports').value));
 o.textContent='open: '+(r.open.join(', ')||'none')}catch(e){o.textContent='ERR '+e.message}}
async function addContact(){const body={text:$('cltext').value,mode:$('clmode').value,mood:$('clmood').value,
 label:$('cllabel').value,sleep_h:$('clsleep').value?parseFloat($('clsleep').value):null,
 stress:$('clstress').value?parseInt($('clstress').value):null,context:$('clcontext').value,
 tags:[]};if(!body.text)return toast('enter text');
 try{await api('/api/contact-log/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 toast('contact logged');$('cltext').value='';$('clsleep').value='';$('clstress').value='';$('clcontext').value='';loadStats()}
 catch(e){toast('ERR '+e.message)}}
async function loadStats(){const o=$('clout');
 try{const s=await api('/api/contact-log/stats');
 o.innerHTML=`<p>entries: <b>${s.entries}</b> · avg sleep <b>${s.avg_sleep_h??'—'}</b>h · avg stress <b>${s.avg_stress??'—'}</b>/10</p>`+
 `<div class="row">${Object.entries(s.labels).map(([k,v])=>`<span class="badge">${esc(k)}:${v}</span>`).join(' ')}</div>`+
 `<div class="out" id="cllist"></div>`;loadEntries();loadGuard()}
 catch(e){o.textContent='ERR '+e.message}}
async function loadEntries(){const o=$('cllist');if(!o)return;
 try{const r=await api('/api/contact-log/list?limit=5');o.textContent=r.entries.map(e=>
 `[${e.ts.slice(0,19)}] ${e.id} ${e.mode}/${e.label} sleep=${e.sleep_h??'—'} stress=${e.stress??'—'}\\n${e.content}`).join('\\n\\n')||'(empty)'}
 catch(e){o.textContent='ERR '+e.message}}
async function doGuard(){const o=$('guard');o.textContent='scanning…';
 try{const r=await api('/api/guard');o.innerHTML=r.findings.length?r.findings.map(f=>
 `<div class="${esc(f.level)}">[${esc(f.level.toUpperCase())}] ${esc(f.signal)}: ${esc(f.detail)}<br>&nbsp;&nbsp;→ ${esc(f.action)}</div>`).join('\\n')
 :`<span class="ok">clear — ${r.entries} entries scanned</span>`}catch(e){o.textContent='ERR '+e.message}}
async function loadCharter(){try{const r=await api('/api/charter');
 const md=r.text.split('\\n').map(l=>{if(l.startsWith('# '))return '<h1>'+esc(l.slice(2))+'</h1>';
 if(l.startsWith('## '))return '<h3>'+esc(l.slice(3))+'</h3>';
 if(l.startsWith('- '))return '• '+esc(l.slice(2));
 if(/^\\d+\\./.test(l))return '<b>'+esc(l.split('. ')[0]+'.</b> '+esc(l.split('. ').slice(1).join('. ')));
 return esc(l)}).join('<br>');$('charter').innerHTML=md}catch(e){$('charter').textContent='ERR '+e.message}}
async function doBrief(){const o=$('brief');o.textContent='…';
 try{const r=await api('/api/brief?theme='+encodeURIComponent($('theme').value));
 o.textContent=r.briefing.guidance}catch(e){o.textContent='ERR '+e.message}}
async function doPatrol(){try{const r=await api('/api/patrol');toast('patrol: '+r.title)}catch(e){toast('ERR '+e.message)}}
async function loadRemote(){const o=$('remote');try{const r=await api('/api/remote');
 let t=`peers: ${r.peers.length?Object.keys(r.peers).join(', '):'none'}\\n\\nAGENT JOURNAL (last 5)\\n`;
 t+=r.journal.slice(0,5).map(j=>`[${j.ts.slice(0,19)}] ${j.user} → ${j.command} rc=${j.rc}`).join('\\n')||'(empty)';
 o.textContent=t}catch(e){o.textContent='ERR '+e.message}}
async function genKey(){try{const r=await api('/api/remote/generate-key',{method:'POST',body:'{}'});
 $('mypub').value=r.public_key;toast('storm key ready — copy it to the other tower')}
 catch(e){toast('ERR '+e.message)}}
async function grantPeer(){const name=$('peername').value.trim(),pub=$('peerpub').value.trim();
 if(!name||!pub)return toast('need name + public key');
 try{const r=await api('/api/remote/grant',{method:'POST',body:JSON.stringify({name:name,pubkey:pub})});
 toast('granted '+r.name);$('peerpub').value='';loadRemote()}catch(e){toast('ERR '+e.message)}}
async function revokePeer(name){try{await api('/api/remote/revoke',{method:'POST',body:JSON.stringify({name:name})});
 toast('revoked '+name);loadRemote()}catch(e){toast('ERR '+e.message)}}
async function bvhAnomaly(){const o=$('bvhout');o.textContent='…';
 try{const r=await api('/api/bvh/anomaly');o.innerHTML=`status: <b>${esc(r.status)}</b> (${r.scanned} actions)\n`+
 r.findings.map(f=>`[${esc(f.level.toUpperCase())}] ${esc(f.registry)} ${esc(f.signal)}: ${esc(f.detail)}\n→ ${esc(f.action)}`).join('\n')||'(clear)'}
 catch(e){o.textContent='ERR '+e.message}}
async function bvhJournal(){const o=$('bvhout');o.textContent='…';
 try{const r=await api('/api/bvh/journal?limit=8');o.textContent=r.entries.map(e=>
 `[${e.ts.slice(0,19)}] ${e.verdict} ${e.cmd} rc=${e.rc}`).join('\n')||'(empty)'}
 catch(e){o.textContent='ERR '+e.message}}
async function bvhPreview(){const o=$('bvhout');const cmd=$('bvhcmd').value.trim();if(!cmd)return;
 try{const r=await api('/api/bvh/preview?command='+encodeURIComponent(cmd));
 o.textContent=`[${r.verdict.toUpperCase()}] ${r.id} ${r.registry}\n${r.why}`}catch(e){o.textContent='ERR '+e.message}}
async function immunity(){const o=$('immunity');o.textContent='…';
 try{const r=await api('/api/immunity');o.innerHTML=r.checks.map(c=>
 `<div class="${esc(c.pass?'ok':'warn')}">${c.pass?'✓':'✗'} ${esc(c.name)}: ${esc(c.detail)}</div>`).join('\n')}
 catch(e){o.textContent='ERR '+e.message}}
(async function init(){try{const s=await api('/api/status');$('host').textContent=s.hostname;
 $('ver').textContent='gcia v'+s.version;loadStats();loadCharter();doAudit()}catch(e){$('host').textContent='offline'}})();
</script></body></html>"""


def _as_dict_entries(entries):
    return [{"id": e.get("id"), "ts": e.get("ts"), "mode": e.get("mode"),
             "label": e.get("label"), "sleep_h": e.get("sleep_h"),
             "stress": e.get("stress"), "content": e.get("content")} for e in entries]


def api_dispatch_get(path, query):
    if path == "/api/status":
        from gcia import __version__
        return {"hostname": socket.gethostname(), "version": __version__}
    if path == "/api/audit":
        from gcia.audit import run_full_audit
        return run_full_audit()
    if path == "/api/recon":
        from gcia.recon import local_ips, sweep, scan_ports, reverse_lookup
        ips = local_ips()
        target = ips[0] if ips else "127.0.0.1"
        live = []
        for h in sweep(target, 24):
            live.append({"host": h, "name": reverse_lookup(h),
                         "ports": scan_ports(h)})
        return {"target": target, "live": live}
    if path == "/api/scan":
        host = (query.get("host") or ["127.0.0.1"])[0]
        ports = None
        if query.get("ports") and query["ports"][0].strip():
            ports = [int(p) for p in query["ports"][0].split(",") if p.strip()]
        from gcia.recon import scan_ports
        return {"host": host, "open": scan_ports(host, ports)}
    if path == "/api/brief":
        from gcia.policy import briefing
        theme = (query.get("theme") or ["device"])[0]
        return {"briefing": briefing(theme)}
    if path == "/api/charter":
        cands = [Path(__file__).resolve().parent.parent / "docs" / "gciau-charter.md",
                 Path.home() / ".gcia" / "gciau-charter.md"]
        for c in cands:
            if c.exists():
                return {"text": c.read_text()}
        return {"text": "# GCIAu Charter\\n(charter file not found — see docs/gciau-charter.md)"}
    if path == "/api/guard":
        from gcia.guard import guard_scan
        return guard_scan()
    if path == "/api/patrol":
        from gcia.patrol import one_patrol
        audit, flags = one_patrol()
        return {"title": f"patrol complete — {len(flags)} finding(s)",
                "flags": flags, "hostname": audit.get("hostname")}
    if path == "/api/contact-log/list":
        from gcia.contactlog import list_entries
        limit = int(query.get("limit", ["10"])[0])
        return {"entries": _as_dict_entries(list_entries(limit))}
    if path == "/api/contact-log/stats":
        from gcia.contactlog import stats
        s = stats()
        s["labels"] = {k: v for k, v in sorted(s["labels"].items())}
        return s
    if path == "/api/registry":
        from gcia import registry
        q = (query.get("q") or [""])[0].strip()
        if q:
            return {"items": registry.search(q)}
        return {"items": registry.list_registry(), "count": registry.count(),
                "infinity": registry.INFINITY}
    if path == "/api/bvh/anomaly":
        from gcia.bvh import scan_anomalies
        return scan_anomalies()
    if path == "/api/bvh/journal":
        from gcia.bvh import journal
        limit = int(query.get("limit", ["10"])[0])
        return {"entries": journal(limit=limit)}
    if path == "/api/bvh/preview":
        from gcia.bvh import preview as _preview
        cmd = (query.get("command") or [""])[0]
        return _preview(cmd)
    if path == "/api/immunity":
        checks = []
        bound = _host_ok
        checks.append({"name": "deck-binding", "pass": (not bound) or bound.startswith(("127.", "localhost")) or bool(_host_token),
                       "detail": f"bound={bound or '?'} token={'set' if _host_token else 'none'}"})
        checks.append({"name": "csrf", "pass": True, "detail": "X-GCI-CSRF enforced on all mutations"})
        checks.append({"name": "rate-limit", "pass": True, "detail": "per-IP budgets: GET 90/min, POST 25/min"})
        try:
            from gcia import contactlog
            _ = contactlog.list_entries()
            checks.append({"name": "contact-log integrity", "pass": True, "detail": "decrypt + sha256 verified"})
        except Exception as e:
            checks.append({"name": "contact-log integrity", "pass": False, "detail": str(e)[:120]})
        try:
            key = contactlog.LOG_KEY
            mode = key.stat().st_mode & 0o777 if key.exists() else None
            checks.append({"name": "log-key perms", "pass": mode == 0o600,
                           "detail": f"mode={oct(mode) if mode else 'n/a'}"})
        except Exception:
            pass
        from gcia.remote import peers
        checks.append({"name": "peer-keys", "pass": True, "detail": f"{len(peers())} granted peer(s)"})
        import shutil
        checks.append({"name": "openssl", "pass": bool(shutil.which("openssl")),
                       "detail": "present" if shutil.which("openssl") else "missing"})
        from gcia.notify import telegram_config
        tc = telegram_config()
        checks.append({"name": "telegram-alerts", "pass": bool(tc.get("token") and tc.get("chat_id")),
                       "detail": "configured" if tc.get("chat_id") else "not configured"})
        return {"checks": checks}
    if path == "/api/remote":
        from gcia.remote import peers
        journal = []
        jp = Path.home() / ".gcia" / "agent-journal.jsonl"
        if jp.exists():
            for line in jp.read_text().splitlines()[-20:]:
                try:
                    journal.append(json.loads(line))
                except Exception:
                    pass
        return {"peers": peers(), "journal": journal}
    return None


def api_dispatch_post(path, body):
    if path == "/api/contact-log/add":
        from gcia.contactlog import add_entry
        t = body.get("text") or ""
        return {"entry": add_entry(t, mode=body.get("mode", "awake"),
                                   mood=body.get("mood", "calm"),
                                   sleep_h=body.get("sleep_h"),
                                   stress=body.get("stress"),
                                   context=body.get("context", ""),
                                   label=body.get("label", "speculative"),
                                   tags=body.get("tags"))}
    if path == "/api/alert":
        from gcia.notify import push_alert
        push_alert("GCI Deck", body.get("message", "deck alert"))
        return {"ok": True}
    if path == "/api/remote/generate-key":
        from gcia.laptop import ssh_keypair
        priv, pub = ssh_keypair()
        return {"private_key": priv, "public_key": Path(pub).read_text().strip()}
    if path == "/api/remote/grant":
        import tempfile
        from gcia.remote import grant as _grant
        name = str(body.get("name") or "").strip()
        pubkey = str(body.get("pubkey") or "").strip()
        if not name or not pubkey:
            return {"error": "name and pubkey required"}
        with tempfile.NamedTemporaryFile("w", suffix=".pub", delete=False) as f:
            f.write(pubkey + "\n")
            tmp = f.name
        try:
            info = _grant(name, tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
        return {"name": name, "key_id": info.get("key_id"), "allowed": info.get("allowed")}
    if path == "/api/remote/revoke":
        from gcia.remote import revoke as _revoke
        name = str(body.get("name") or "").strip()
        _revoke(name)
        return {"name": name, "ok": True}
    return None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _check_token(self):
        token = self.server.token  # type: ignore[attr-defined]
        if not token:
            return True
        q = parse_qs(urlparse(self.path).query)
        got = q.get("token", [""])[0] or self.headers.get("X-GCI-Token", "")
        return got == token

    def _guard(self, method):
        """Immunity gate: host check, rate limit, token. Returns None or error dict."""
        if not host_allowed(self.headers.get("Host", ""), self.server.token):
            _journal({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      "event": "host-rejected", "host": self.headers.get("Host", "")[:80],
                      "path": urlparse(self.path).path})
            return {"code": 403, "error": "untrusted Host header"}
        ip = self.client_address[0] if self.client_address else "?"
        if not rate_ok(ip, method):
            return {"code": 429, "error": "rate limit exceeded — slow down"}
        if not self._check_token():
            _journal({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      "event": "bad-token", "ip": ip, "path": urlparse(self.path).path})
            return {"code": 401, "error": "token required"}
        if method == "POST":
            if not self.headers.get("Content-Type", "").startswith("application/json"):
                return {"code": 415, "error": "JSON content-type required"}
            if self.headers.get("X-GCI-CSRF") != self.server.csrf:  # type: ignore[attr-defined]
                _journal({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          "event": "csrf-rejected", "ip": ip, "path": urlparse(self.path).path})
                return {"code": 403, "error": "CSRF token mismatch"}
        return None

    def do_GET(self):
        g = self._guard("GET")
        if g:
            self._send(g["code"], {"error": g["error"]})
            return
        parsed = urlparse(self.path)
        if parsed.path == "/":
            page = PAGE.replace("__CSRF__", self.server.csrf)  # type: ignore[attr-defined]
            data = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        result = api_dispatch_get(parsed.path, parse_qs(parsed.query))
        if result is None:
            self._send(404, {"error": "not found"})
            return
        self._send(200, result)

    def do_POST(self):
        g = self._guard("POST")
        if g:
            self._send(g["code"], {"error": g["error"]})
            return
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            self._send(400, {"error": "bad json"})
            return
        result = api_dispatch_post(parsed.path, body)
        if result is None:
            self._send(404, {"error": "not found"})
            return
        _journal({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "event": "deck-action", "ip": self.client_address[0] if self.client_address else "?",
                  "path": parsed.path})
        self._send(200, result)


def serve(host="127.0.0.1", port=8890, token=None):
    if not host.startswith(("127.", "localhost")) and not token:
        raise SystemExit("Refusing to expose the deck on the network without --token.")
    if port < 1 or port > 65535:
        raise SystemExit("invalid port")
    global _host_ok, _host_token
    _host_ok = host
    _host_token = token or ""
    server = ThreadingHTTPServer((host, port), Handler)
    server.token = token  # type: ignore[attr-defined]
    server.csrf = secrets.token_hex(16)  # type: ignore[attr-defined]
    _journal({"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "event": "deck-start", "host": host, "port": port,
              "token": bool(token)})
    print(f"GCI Command Deck online: http://{host}:{port}" + (f"  (token required)" if token else ""))
    print("GCIA investigation | GCIAu authority | immunity: CSRF + host-check + rate-limit active")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ndeck stopped")
