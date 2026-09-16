"""GCIA patrol — periodic security audit + phone alert every N hours."""

import time

from gcia.audit import run_full_audit
from gcia.notify import push_alert


def _flag_rows(audit):
    rows = []
    ports = audit.get("listening_ports") or []
    if ports:
        rows.append(f"listening ports: {','.join(map(str, ports))}")
    ww = audit.get("world_writable_home") or []
    if ww:
        rows.append(f"world-writable home entries: {len(ww)}")
    updates = audit.get("pending_updates", 0)
    if updates and updates > 0:
        rows.append(f"pending package updates: {updates}")
    return rows


def one_patrol(notify_even_clean=True, sound=False):
    audit = run_full_audit()
    flags = _flag_rows(audit)
    host = audit.get("hostname", "device")
    battery = audit.get("battery_pct")
    bat = f"{battery}%" if battery is not None else "n/a"
    from gcia.guard import guard_scan
    try:
        mind = guard_scan()
        if mind["status"] != "no-data" and mind["status"] != "clear":
            flags.append(f"mindguard:{mind['status']} ({len(mind['findings'])} finding(s))")
    except Exception:
        pass
    from gcia.bvh import scan_anomalies
    try:
        beh = scan_anomalies()
        if beh["status"] != "clear":
            flags.append(f"bvh:{beh['status']} ({len(beh['findings'])} finding(s))")
    except Exception:
        pass
    if flags:
        title = f"GCIA PATROL: {len(flags)} finding(s) on {host}"
        content = " | ".join(flags) + f" | battery {bat}"
    else:
        title = f"GCIA PATROL: {host} clear"
        content = f"No open listening ports, no unsafe perms, no mindguard flags. Battery {bat}."
    push_alert(title, content, sound=sound)
    return audit, flags


def patrol_loop(interval_hours=2, every_hours=None, sound=False):
    """Run audit + alert, then wait interval, forever."""
    interval = (every_hours or interval_hours) * 3600
    while True:
        try:
            one_patrol(sound=sound)
        except Exception as e:
            push_alert("GCIA patrol error", str(e)[:200])
        time.sleep(interval)
