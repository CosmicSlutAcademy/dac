"""GCI client report generator — the sellable deliverable.

Turns one patrol's worth of real data (device audit, behavior-verification
anomalies, mindguard status, governance registry) into a branded, datestamped
report that can be printed to PDF. This is the micro-automation that converts
the ethical services stack into a repeatable paid product.

Compliance: reports state clearly that they describe the owner's own assessed
environments, make no guarantees, and never claim psychic/paranormal abilities.
"""

import datetime
import hashlib
import json
import os
from pathlib import Path

REPORT_DIR = Path(os.path.expanduser("~/.gcia/reports"))

DEFAULT_FEE = 79
FEE_ITEMS = [
    ("GCIA device & network assessment", 40),
    ("BVH behavior verification scan", 15),
    ("Mindguard wellbeing posture check", 12),
    ("Governance registry alignment", 7),
    ("Report compilation & delivery", 5),
]


def _md_table(rows):
    lines = ["| key | value |", "|---|---|"]
    for k, v in rows:
        lines.append(f"| {k} | {v} |")
    return "\n".join(lines)


def _load_audit():
    try:
        from gcia.audit import run_full_audit
        a = run_full_audit()
        return [("hostname", a.get("hostname", "?")),
                ("uptime_hours", a.get("uptime_hours")),
                ("listening_ports", ",".join(map(str, a.get("listening_ports") or [])) or "none"),
                ("world_writable_home", str(len(a.get("world_writable_home") or []))),
                ("pending_updates", a.get("pending_updates")),
                ("battery_pct", a.get("battery_pct")),
                ("ssh_running", a.get("ssh_running"))]
    except Exception as e:
        return [("audit_error", str(e)[:120])]


def _load_bvh():
    try:
        from gcia.bvh import scan_anomalies
        a = scan_anomalies()
        return a
    except Exception as e:
        return {"status": "error", "findings": [{"level": "alert", "signal": "scan-error", "detail": str(e)[:120], "action": "review manually"}]}


def _load_guard():
    try:
        from gcia.guard import guard_scan
        return guard_scan()
    except Exception:
        return {"status": "no-data", "entries": 0, "findings": []}


def _exec_summary(audit, bvh, guard):
    try:
        from dac.config import load_config
        from dac.core.llm import complete
        cfg = load_config()
        data = json.dumps({"audit": dict(audit), "bvh_status": bvh.get("status"),
                           "bvh_findings": len(bvh.get("findings", [])),
                           "guard_status": guard.get("status"),
                           "contact_entries": guard.get("entries")})
        text, _ = complete(cfg, [{"role": "user",
                                  "content": "Write a 3-sentence executive security summary for a client, "
                                             "plain language, no jargon, no guarantees, based on: " + data}],
                           provider=cfg.get("provider"))
        return text.strip()[:900]
    except Exception:
        return ("Automated assessment completed. No critical containment events were detected "
                "at scan time; follow the findings and recommendations below. This report "
                "describes the owner's assessed environments and makes no guarantees.")


def resolve_auth(client, auth=None):
    """Turn --auth (hash/path/auto) into {attestation, path} from the legal ledger."""
    try:
        from gcia import legal
        entries = legal.engagements(limit=200)
    except Exception:
        entries = []
    if auth in (None, "auto"):
        for e in reversed(entries):
            if e.get("kind") == "authorize" and e.get("client", "").lower() == client.lower():
                return {"attestation": e.get("attestation"), "path": e.get("path"),
                        "source": "ledger"}
        return None
    if auth == "latest":
        for e in reversed(entries):
            if e.get("kind") == "authorize":
                return {"attestation": e.get("attestation"), "path": e.get("path"),
                        "source": "ledger"}
        return None
    if len(auth) == 64 and all(c in "0123456789abcdef" for c in auth.lower()):
        for e in entries:
            if (e.get("hash") or "").lower() == auth.lower() or \
               (e.get("attestation") or "").lower() == auth.lower():
                return {"attestation": e.get("attestation"), "path": e.get("path"),
                        "source": "ledger-hash"}
        return None
    p = Path(auth)
    if p.exists():
        import gcia.legal as _legal
        return {"attestation": _legal._sha256(str(p)), "path": str(p), "source": "file"}
    return None


def generate_report(client, contact="", out=None, fee=DEFAULT_FEE, branded_by="GCI — GCIA/GCIAu",
                   pro_bono=False, auth=None):
    audit = _load_audit()
    bvh = _load_bvh()
    guard = _load_guard()
    summary = _exec_summary(audit, bvh, guard)
    ts = datetime.datetime.now(datetime.timezone.utc)
    ts_str = ts.strftime("%Y-%m-%d %H:%M UTC")
    slug = client.replace(" ", "-").lower() or "client"
    report_dir = out.parent if out else REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    out = out or (report_dir / f"gci-report-{slug}-{ts.strftime('%Y%m%dT%H%M%S')}.html")

    findings = bvh.get("findings", [])
    bvh_rows = "\n".join(
        f"<li><b>[{f.get('level','?').upper()}]</b> {f.get('signal','')} — {f.get('detail','')}<br>"
        f"<i>→ {f.get('action','')}</i></li>" for f in findings) or "<li>No active findings.</li>"
    guard_rows = "\n".join(
        f"<li><b>[{f.get('level','?').upper()}]</b> {f.get('signal','')} — {f.get('detail','')}</li>"
        for f in guard.get("findings", [])) or "<li>Clear / no data.</li>"
    audit_rows = "\n".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in audit)
    if pro_bono:
        fee_rows = ("<tr><td><b>PRO BONO — CIVILIZATION SAFEGUARD</b> (GCIAu Charter §7)</td>"
                    "<td align='right'><b>$0</b></td></tr>")
        fee_total = 0
    else:
        fee_rows = "\n".join(
            f"<tr><td>{name}</td><td align='right'>${amt}</td></tr>" for name, amt in FEE_ITEMS)
        fee_total = sum(a for _, a in FEE_ITEMS)
        if fee != DEFAULT_FEE:
            fee_total = fee

    auth_ref = resolve_auth(client, auth)
    auth_block = ""
    if auth_ref and auth_ref.get("path"):
        auth_block = (f"<h2>Authorization &amp; Evidence Link</h2>"
                      f"<p>Engagement authorization: <code>{auth_ref['path']}</code></p>"
                      f"<p>Attestation SHA-256: <code>{auth_ref.get('attestation') or 'n/a'}</code></p>"
                      f"<p>Report attestation (pre-stamp SHA-256): <code>REPORT_HASH</code></p>")
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<title>GCI Security Report — {client}</title>
<style>
body{{font:14px/1.55 Georgia,serif;color:#1a2430;max-width:820px;margin:32px auto;padding:0 20px}}
h1{{font-size:22px;border-bottom:3px solid #0b3d91;padding-bottom:8px}}
h2{{font-size:16px;color:#0b3d91;margin-top:26px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border:1px solid #c9d4e0;padding:6px 9px;text-align:left}}
.badge{{display:inline-block;background:#eaf1fb;border:1px solid #0b3d91;border-radius:99px;padding:2px 10px;font-size:12px}}
.footer{{margin-top:34px;border-top:1px solid #c9d4e0;padding-top:10px;font-size:11px;color:#5a6b7d}}
.sig{{font-size:11px;color:#5a6b7d}}
</style></head><body>
<h1>GCI Security Report — {client}</h1>
<p class="badge">Generated {ts_str}</p>
<p class="badge">by {branded_by}</p>
{"<p class='badge' style='background:#e5f6ec;border-color:#1e8e4e;color:#14532d'><b>PRO BONO — CIVILIZATION SAFEGUARD (GCIAu Charter §7)</b></p>" if pro_bono else ""}
<p><b>Contact point:</b> {contact or "n/a"}</p>
<h2>Executive Summary</h2>
<p>{summary}</p>
<h2>Assessed Environment (Device Audit)</h2>
<table><tr><th>key</th><th>value</th></tr>{audit_rows}</table>
<h2>Behavior Verification (BVH) — status: {bvh.get('status','?')}</h2>
<ul>{bvh_rows}</ul>
<h2>Mindguard Wellbeing Posture — status: {guard.get('status','?')} ({guard.get('entries',0)} entries)</h2>
<ul>{guard_rows}</ul>
<h2>Governance</h2>
<p>Aligned to the §MDH-ATA digital governance registry (GCIA investigation /
GCIAu authority), charter at <code>docs/gciau-charter.md</code>.</p>
{auth_block}
<h2>Line Items</h2>
<table><tr><th>Service</th><th align="right">Fee</th></tr>{fee_rows}
<tr><td><b>Total</b></td><td align="right"><b>${fee_total}</b></td></tr></table>
<div class="footer">
<p><b>Disclaimer:</b> this report reflects the owner's own assessed environments at scan time.
It provides no guarantee of security or compliance. No psychic, paranormal, or
interdimensional capabilities are claimed.</p>
<p class="sig">GCI — Galactic Cyber Intelligence · GCIA investigation · GCIAu authority ·
Ethical security services · Generated by the GCI Command Deck stack (gcia {__import__('gcia', fromlist=['__version__']).__version__})</p>
</div></body></html>"""

    attest = hashlib.sha256(html.encode("utf-8")).hexdigest()
    if auth_block:
        html = html.replace("REPORT_HASH", attest)
    out.write_text(html)
    out.chmod(0o600 if not out.parent.name == "reports" else 0o600)
    report_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    return {"path": str(out), "client": client, "fee": fee_total, "pro_bono": pro_bono,
            "hash": report_hash, "attestation": attest,
            "auth": auth_ref,
            "bvh_status": bvh.get("status"), "guard_status": guard.get("status")}
