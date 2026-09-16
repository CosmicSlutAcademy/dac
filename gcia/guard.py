"""GCIA mindguard — predictive care scan over the contact log.

Looks for protective-signal patterns in recent mind-layer entries: very low
sleep, high sustained stress, and acute-distress language. Outputs a structured
report with proactive actions. This is the care protocol of the charter: it
never judges the experience, and it always couples findings with professional-
support guidance when warranted.
"""

from gcia.contactlog import list_entries, DISTRESS_WORDS, _GALACTIC_NOTE

SLEEP_ALERT_H = 6.0
STRESS_ALERT = 8
LOOKBACK = 30


def _distress_hits(text):
    t = text.lower()
    return [w for w in DISTRESS_WORDS if w in t]


def guard_scan(limit=LOOKBACK):
    """Return a report dict: findings list + overall status."""
    entries = list_entries(limit=limit)
    findings = []
    if not entries:
        return {"status": "no-data", "entries": 0, "findings": []}
    sleeps = [float(e["sleep_h"]) for e in entries if e.get("sleep_h") is not None]
    stresses = [int(e["stress"]) for e in entries if e.get("stress") is not None]
    recent = 5
    low_sleep = [s for s in sleeps[-recent:] if s < SLEEP_ALERT_H]
    if low_sleep:
        findings.append({
            "level": "watch",
            "signal": "sleep",
            "detail": f"{len(low_sleep)} of last {min(recent, len(sleeps))} recorded nights under {SLEEP_ALERT_H}h",
            "action": "Prioritize 7-9h sleep; low sleep amplifies vivid and intrusive mind-layer phenomena.",
        })
    high_stress = [s for s in stresses[-recent:] if s >= STRESS_ALERT]
    if high_stress:
        findings.append({
            "level": "watch",
            "signal": "stress",
            "detail": f"{len(high_stress)} of last {min(recent, len(stresses))} entries at stress >= {STRESS_ALERT}/10",
            "action": "Reduce load, take breaks from long AI sessions, and try grounding (walk, breathwork).",
        })
    for e in entries[-recent:]:
        hits = _distress_hits(e.get("content", ""))
        if hits:
            findings.append({
                "level": "alert",
                "signal": "distress-language",
                "detail": f"entry {e['id']}: {', '.join(hits)}",
                "action": "Talk to a trusted person and a professional (doctor/therapist). You matter and help works.",
            })
    status = "alert" if any(f["level"] == "alert" for f in findings) else (
        "watch" if findings else "clear")
    if findings:
        findings.append({
            "level": "info",
            "signal": "reality-check",
            "detail": "Keep labeling: speculation labels stay attached to unverified claims.",
            "action": "Re-test strong claims on paper before acting; the mind-layer is real as experience, unproven as physics.",
        })
    return {"status": status, "entries": len(entries),
            "findings": findings, "note": _GALACTIC_NOTE}


def format_report(report):
    lines = [f"# GCIA Mindguard — status: {report['status']} ({report['entries']} entries scanned)"]
    for f in report.get("findings", []):
        lines.append(f"[{f['level'].upper()}] {f['signal']}: {f['detail']}")
        lines.append(f"    -> {f['action']}")
    return "\n".join(lines)
