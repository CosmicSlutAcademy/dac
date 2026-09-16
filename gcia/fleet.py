"""GCI Fleet — principal coder + specialist captain/pilot bots.

Captains plan and review; pilots execute within their tool allowlist.
`fleet brief` runs a mission: the principal (local DAC LLM) assigns roles,
pilots execute, the principal synthesizes a mission report. If the LLM is
offline, a deterministic dispatcher runs instead — the fleet degrades, never
fails.

Architecture mirrors the GCI ethos: specialists are scoped (allowlist per
role), every action is bounded by timeouts, and results are journaled.
"""

import datetime
import json
import os
import re
import subprocess
from pathlib import Path

MISSION_DIR = Path(os.path.expanduser("~/.gcia/fleet"))

ROLES = [
    {"rank": "captain", "name": "captain-core",
     "mission": "Principal Coder — plan, review, decide next iteration.",
     "tools": ["dac chat", "dac quick", "fleet brief", "contact-log"]},
    {"rank": "captain", "name": "captain-defense",
     "mission": "Cyber defense lead — command recon, scan, audit, patrol.",
     "tools": ["recon", "scan", "audit", "patrol"]},
    {"rank": "captain", "name": "captain-mindguard",
     "mission": "Cognitive-sovereignty lead — mindguard, journal, care protocol.",
     "tools": ["guard", "contact-log", "telegram"]},
    {"rank": "pilot", "name": "pilot-recon",
     "mission": "Sweep the local network for live hosts.",
     "tools": ["gcia recon"]},
    {"rank": "pilot", "name": "pilot-scan",
     "mission": "Port-scan one host (target authorizes).",
     "tools": ["gcia scan <host> [ports]"]},
    {"rank": "pilot", "name": "pilot-audit",
     "mission": "Run the full device security audit.",
     "tools": ["gcia audit"]},
    {"rank": "pilot", "name": "pilot-patrol",
     "mission": "Run one patrol cycle (audit + mindguard + alerts).",
     "tools": ["gcia patrol --once"]},
    {"rank": "pilot", "name": "pilot-guard",
     "mission": "Mindguard predictive care scan over the contact-log.",
     "tools": ["gcia guard"]},
    {"rank": "pilot", "name": "pilot-brief",
     "mission": "Generate a GCIAu policy briefing + checklist.",
     "tools": ["gcia brief --theme <...>"]},
    {"rank": "pilot", "name": "pilot-contact",
     "mission": "Mind-layer evidence journaling (add/list/stats).",
     "tools": ["gcia contact-log add|list|stats"]},
    {"rank": "pilot", "name": "pilot-code",
     "mission": "Autonomous coding executor via DAC (fenced deliverables).",
     "tools": ["dac quick <task>"]},
    {"rank": "pilot", "name": "pilot-telegram",
     "mission": "Off-device alert channel check.",
     "tools": ["gcia telegram test"]},
]

ROLE_CMDS = {
    "captain-core": None,
    "captain-defense": None,
    "captain-mindguard": None,
    "pilot-recon": ["gcia", "recon"],
    "pilot-scan": ["gcia", "scan", "{host}", "--ports", "{ports}"],
    "pilot-audit": ["gcia", "audit"],
    "pilot-patrol": ["gcia", "patrol", "--once"],
    "pilot-guard": ["gcia", "guard"],
    "pilot-brief": ["gcia", "brief", "--theme", "{theme}"],
    "pilot-contact": ["gcia", "contact-log", "{action}"],
    "pilot-code": ["dac", "quick", "{task}"],
    "pilot-telegram": ["gcia", "telegram", "test"],
}

TIMEOUTS = {"pilot-code": 300, "pilot-recon": 120, "pilot-scan": 60,
            "pilot-patrol": 120, "pilot-brief": 30, "pilot-contact": 30,
            "pilot-guard": 20, "pilot-audit": 30, "pilot-telegram": 30}


def roster():
    return [dict(r) for r in ROLES]


def _role(name):
    for r in ROLES:
        if r["name"] == name:
            return r
    return None


def _expand(cmd_template, args):
    out = []
    if isinstance(args, list):
        args = dict(zip([t[1:-1] for t in cmd_template if t.startswith("{")],
                        list(args)))
    if not isinstance(args, dict):
        args = {}
    for tok in cmd_template:
        if tok.startswith("{"):
            key = tok[1:-1]
            val = args.get(key, "")
            if not val:
                return None
            out.append(val)
        else:
            out.append(tok)
    return out


def run_role(name, args=None, timeout=None, approve=False):
    """Execute a specialist's scoped command through the BVH gate.

    Every pilot action is previewed by the Behavior Verification Harness
    (gcia/bvh.py). `warn` verdicts (mutations) require `approve=True`; `deny`
    verdicts fail closed unless the operator escalates via `gcia bvh run --force`.
    """
    import shlex
    from gcia.bvh import run as _bvh_run
    role = _role(name)
    if not role:
        return {"role": name, "ok": False, "error": f"unknown role {name!r}"}
    if role["rank"] == "captain":
        return {"role": name, "ok": True, "output": f"{role['mission']} (captain — no direct tool)"}
    tmpl = ROLE_CMDS.get(name)
    if not tmpl:
        return {"role": name, "ok": False, "error": "no tool mapping"}
    cmd = _expand(tmpl, args or {})
    if cmd is None:
        return {"role": name, "ok": False, "error": "missing required arguments"}
    command = shlex.join(cmd)
    res = _bvh_run(command, approve=approve, timeout=timeout or TIMEOUTS.get(name, 60))
    if res.get("verdict") in ("deny", "require-approval"):
        return {"role": name, "ok": False, "verdict": res.get("verdict"),
                "rule": res.get("rule"), "registry": res.get("registry"),
                "error": res.get("why", res.get("output", ""))[:400]}
    return {"role": name, "ok": res.get("ok", False), "rc": res.get("rc"),
            "verdict": res.get("verdict"), "rule": res.get("rule"),
            "registry": res.get("registry"),
            "output": res.get("output", "") or "(no output)"}


def _llm_assign(task):
    """Ask the principal (local DAC LLM) for a JSON mission plan. Returns None on failure."""
    try:
        from dac.config import load_config
        from dac.core.llm import complete
        cfg = load_config()
        roles = ", ".join(r["name"] for r in ROLES)
        prompt = (
            f"You are captain-core, principal coder of the GCI fleet. "
            f"Available specialists: {roles}. "
            f"Task: {task}. "
            f"Reply ONLY with JSON: {{\"roles\": [\"pilot-...\", ...], "
            f"\"args\": {{\"pilot-...\": {{\"host\": \"...\"}}}}, "
            f"\"note\": \"one-line plan\"}}. Pick 2-5 pilots. "
            f"Never use captains for execution; never invent roles.")
        text, _ = complete(cfg, [{"role": "user", "content": prompt}], provider=cfg.get("provider"))
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            return None
        return json.loads(m.group(0))
    except Exception:
        return None


def _dispatch_fallback(task):
    """Deterministic dispatch when the principal LLM is unavailable."""
    t = task.lower()
    roles = ["pilot-audit"]  # always audit first
    for role, keys in [("pilot-guard", ["mind", "guard", "wellbeing", "sleep", "stress"]),
                       ("pilot-recon", ["network", "lan", "recon", "sweep", "scan"]),
                       ("pilot-brief", ["brief", "policy", "phishing", "deepfake"]),
                       ("pilot-contact", ["contact", "journal", "log", "entry"]),
                       ("pilot-code", ["code", "build", "create", "automate", "script"]),
                       ("pilot-patrol", ["patrol", "security", "protect", "defense"]),
                       ("pilot-telegram", ["telegram", "alert", "alerts"])]:
        if any(k in t for k in keys):
            roles.append(role)
    return {"roles": list(dict.fromkeys(roles)), "args": {}, "note": "deterministic fallback (principal LLM offline)"}


def _synthesize(task, results):
    try:
        from dac.config import load_config
        from dac.core.llm import complete
        cfg = load_config()
        summary = "\n".join(f"## {r['role']}\n{r.get('output', r.get('error', ''))[:800]}"
                            for r in results[:5])
        text, _ = complete(cfg, [{"role": "user",
                                  "content": f"Mission: {task}\n\n{summary}\n\n"
                                              "Write a 4-6 line mission report: findings, "
                                              "risks, recommended next action. Keep it direct."}])
        return text[:2000]
    except Exception:
        parts = ["# Mission report (fallback)", f"task: {task}", ""]
        for r in results:
            parts.append(f"- {r['role']}: {'ok' if r['ok'] else 'FAILED'} — "
                         f"{(r.get('output') or r.get('error') or '')[:200]}")
        return "\n".join(parts)


def fleet_brief(task):
    """Run a mission: assign to specialists, execute, synthesize, journal."""
    MISSION_DIR.mkdir(parents=True, exist_ok=True)
    plan = _llm_assign(task) or _dispatch_fallback(task)
    roles = [r for r in plan.get("roles", []) if _role(r)]
    args_map = plan.get("args", {}) or {}
    results = []
    for role in roles:
        args = args_map.get(role, {})
        results.append(run_role(role, args=args, approve=False))
    report = _synthesize(task, results)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = MISSION_DIR / f"mission-{ts}.md"
    out_path.write_text(f"# GCI Fleet mission — {ts}\n\ntask: {task}\nnote: {plan.get('note','')}\n\n"
                        + report + "\n")
    out_path.chmod(0o600)
    return {"mission": str(out_path), "plan": plan, "results": results, "report": report}


def fleet_status():
    import shutil
    s = {}
    s["deck"] = _http_ok("http://127.0.0.1:8890/api/status")
    s["llm"] = _http_ok("http://127.0.0.1:8080/health")
    from gcia.notify import telegram_config
    s["telegram"] = bool(telegram_config().get("chat_id"))
    s["sshd"] = bool(shutil.which("sshd"))
    return s


def _http_ok(url):
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False
