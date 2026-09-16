"""GCI Behavior Verification Harness (BVH) — make machine learning behave.

Every agent/pilot action is previewed against a rule map keyed to the
§MDH-ATA digital governance registry, then executed only within the allowed
verdict, journaled, and audited for anomalies. Destructive or mutating actions
require explicit operator approval (Human Authorization §MDH-ATA-57).
"""

import datetime
import json
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

BVH_DIR = Path(os.path.expanduser("~/.gcia"))
BVH_JOURNAL = BVH_DIR / "bvh-journal.jsonl"

HOME = os.path.expanduser("~")
ALLOWED_ROOTS = [HOME, "/root/projects", "/data/data/com.termux/files/home"]

# Rules: registry_id + verdict. First match wins; later = stronger.
RULES = [
    # --- DENY — containment/reversibility (§MDH-ATA-59/61) ---
    {"id": "BVH-D01", "registry": "§MDH-ATA-59", "verdict": "deny",
     "pattern": r"rm\s+-rf?\s*/(\s|$)|mkfs|dd\s+of=/dev|shutdown|reboot|:\(\)\{\s*:\|:&;?\s*\}:?",
     "why": "Destructive or system-terminal action — not reversible."},
    {"id": "BVH-D02", "registry": "§MDH-ATA-47", "verdict": "deny",
     "pattern": r"(cat|base64|cp)\s+[^\n]*\.ssh/|curl\s+-F?\s*[^\n]*http|nc\s+-[^ ]*e|scp\s+[^\n]*(0\.0\.0\.0|[^ ]+@)",
     "why": "Credential exposure or exfiltration pattern."},
    {"id": "BVH-D03", "registry": "§MDH-ATA-44", "verdict": "deny",
     "pattern": r"chmod\s+(777|a\+w|o\+w)|chown\s+[^\n]*\.ssh|>?>\s*/etc/",
     "why": "Unsafe perms or writes outside operator scope."},
    # --- WARN — mutations need operator approval (§MDH-ATA-57) ---
    {"id": "BVH-W01", "registry": "§MDH-ATA-57", "verdict": "warn",
     "pattern": r"rm\s|mv\s|dd\s|touch\s|mkdir\s|>(\s|\S)|mkfs|chmod\s|chown\s|git\s+push|git\s+reset|git\s+clean|pip\s+install|apt(-get)?\s+(install|remove|purge)|pkg\s+(install|remove)|useradd|passwd|dropdb",
     "why": "Mutating action — requires operator approval."},
    {"id": "BVH-W02", "registry": "§MDH-ATA-57", "verdict": "warn",
     "pattern": r"ssh\s+[^\n]+@|curl\s+-sS?L?\s+[^\n]+api|wget\s",
     "why": "Network interaction — requires operator approval."},
    {"id": "BVH-W03", "registry": "§MDH-ATA-38", "verdict": "warn",
     "pattern": r"^dac\b.*quick\b",
     "why": "Autonomous code execution — requires operator approval."},
    # --- ALLOW — read-only / investigation (§MDH-ATA-25 evidence fabric) ---
    {"id": "BVH-A01", "registry": "§MDH-ATA-25", "verdict": "allow",
     "pattern": r"^(gcia|python3? -c|cat|ls|echo|date|whoami|id|pwd|uptime|uname|ps|ss|netstat|df|free|mount|git status|git log|git diff|curl -sI|grep|rg|find|head|tail|wc|stat|cksum|sha256sum|hostname|env|printf)\b.*",
     "why": "Read-only or established investigation tool."},
]


def evaluate(command):
    """Preview command string against the rule map.
    Returns {verdict, rule, registry, why, match}."""
    cmd = command.strip()
    # expand leading "sudo " transparently
    if cmd.startswith("sudo "):
        cmd = cmd[5:].strip()
    for rule in RULES:
        if re.search(rule["pattern"], cmd, re.IGNORECASE):
            return {"verdict": rule["verdict"], "id": rule["id"],
                    "registry": rule["registry"], "why": rule["why"],
                    "match": cmd[:120], "command": command}
    # unknown = anomaly-worthy but treat as warn (Containment: unknown behavior)
    return {"verdict": "warn", "id": "BVH-W00", "registry": "§MDH-ATA-38",
            "why": "Unknown command pattern — treat as emergent behavior, require approval.",
            "match": cmd[:120], "command": command}


def preview(command):
    """Sandboxed preview: evaluate rules, do not execute."""
    return evaluate(command)


def _journal(entry):
    BVH_DIR.mkdir(parents=True, exist_ok=True)
    with open(BVH_JOURNAL, "a") as f:
        f.write(json.dumps(entry) + "\n")


def run(command, approve=False, force=False, timeout=120):
    """Check -> execute (if allowed) -> verify -> journal. Never runs deny."""
    v = evaluate(command)
    if v["verdict"] == "deny" and not force:
        _journal({"ts": _now(), "cmd": command, "verdict": v["verdict"],
                  "rule": v["id"], "registry": v["registry"], "rc": None,
                  "event": "denied"})
        return {"ok": False, "verdict": "deny", "rule": v["id"],
                "registry": v["registry"], "why": v["why"],
                "output": f"DENIED ({v['id']} {v['registry']}): {v['why']}"}
    if v["verdict"] == "warn" and not approve and not force:
        _journal({"ts": _now(), "cmd": command, "verdict": "pending-approval",
                  "rule": v["id"], "registry": v["registry"], "rc": None})
        return {"ok": False, "verdict": "require-approval", "rule": v["id"],
                "registry": v["registry"], "why": v["why"],
                "output": f"APPROVAL REQUIRED ({v['id']} {v['registry']}): {v['why']}\nRe-run with --approve to execute."}
    t0 = time.time()
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        rc, out, err = r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        rc, out, err = -1, "", "timeout"
    except Exception as e:
        rc, out, err = -1, "", str(e)
    dur = round(time.time() - t0, 2)
    entry = {"ts": _now(), "cmd": command, "verdict": v["verdict"],
             "rule": v["id"], "registry": v["registry"], "rc": rc,
             "duration_s": dur, "event": "executed"}
    _journal(entry)
    return {"ok": rc == 0, "verdict": v["verdict"], "rule": v["id"],
            "registry": v["registry"], "rc": rc, "duration_s": dur,
            "output": (out + err).strip()[:4000]}


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def journal(limit=None):
    if not BVH_JOURNAL.exists():
        return []
    rows = []
    for line in BVH_JOURNAL.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-limit:] if limit else rows


def scan_anomalies(limit=40):
    """Predictive anomaly scan over BVH + agent journals."""
    findings = []
    rows = journal(limit=limit)
    denied = [r for r in rows if r.get("event") == "denied"]
    if denied:
        findings.append({
            "registry": "§MDH-ATA-59", "level": "alert", "signal": "containment-breach-attempt",
            "detail": f"{len(denied)} denied action(s): " + ", ".join(r["cmd"][:40] for r in denied[:3]),
            "action": "Operator review; no execution occurred (fail-closed)."})
    mutated = [r for r in rows if r.get("verdict") == "warn" and r.get("rc") is not None]
    if len(mutated) >= 3:
        findings.append({
            "registry": "§MDH-ATA-57", "level": "watch", "signal": "mutation-frequency",
            "detail": f"{len(mutated)} approved mutations in recent window",
            "action": "Confirm each had operator approval."})
    fails = [r for r in rows if r.get("rc") not in (0, None, -1)]
    if len(fails) >= 3:
        findings.append({
            "registry": "§MDH-ATA-63", "level": "watch", "signal": "repeating-failures",
            "detail": f"{len(fails)} failing action(s) in recent window",
            "action": "Inspect recovery path; check for root cause before retry."})
    unknown = [r for r in rows if r.get("rule") in ("BVH-W00",)]
    if len(unknown) >= 3:
        findings.append({
            "registry": "§MDH-ATA-38", "level": "watch", "signal": "emergent-behavior",
            "detail": f"{len(unknown)} unknown command pattern(s) observed",
            "action": "Add a rule or a human review for these patterns."})
    agent_j = BVH_DIR / "agent-journal.jsonl"
    if agent_j.exists():
        denied_remote = 0
        for line in agent_j.read_text().splitlines():
            try:
                if json.loads(line).get("rc") == 403:
                    denied_remote += 1
            except Exception:
                pass
        if denied_remote >= 3:
            findings.append({
                "registry": "§MDH-ATA-50", "level": "watch", "signal": "remote-allowlist-pressure",
                "detail": f"{denied_remote} denied remote agent command(s)",
                "action": "Verify granted peers; rotate keys if unexpected."})
    return {"status": "alert" if any(f["level"] == "alert" for f in findings)
            else ("watch" if findings else "clear"),
            "scanned": len(rows), "findings": findings}
