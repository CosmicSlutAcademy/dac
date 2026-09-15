"""Device security posture audit."""

import os
import shutil
import socket
import subprocess
import json


def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def listening_ports():
    """Parse /proc/net/tcp (and tcp6) for local listening ports."""
    ports = []
    for path in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(path) as f:
                lines = f.readlines()[1:]
        except Exception:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            try:
                local_port = int(parts[1].split(":")[1], 16)
            except Exception:
                continue
            state = parts[3]
            if state == "0A" and local_port:  # LISTEN
                ports.append(local_port)
    return sorted(set(ports))


def world_writable_home():
    """Spot unsafe perms in $HOME."""
    home = os.path.expanduser("~")
    bad = []
    for name in os.listdir(home):
        p = os.path.join(home, name)
        try:
            mode = os.stat(p).st_mode & 0o777
            if mode & 0o002:
                bad.append((name, oct(mode)))
        except Exception:
            continue
    return bad


def package_updates():
    """Return count of available updates via apt (best-effort)."""
    out = _run(["apt-get", "-s", "upgrade", "-o", "APT::Get::List-Cleanup=0"])
    if not out:
        return -1
    n = 0
    for line in out.splitlines():
        if line.startswith("Inst "):
            n += 1
    return n


def uptime():
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


def battery_pct():
    try:
        out = _run(["termux-battery-status"])
        if out:
            return json.loads(out).get("percentage", None)
    except Exception:
        pass
    return None


def run_full_audit():
    return {
        "hostname": socket.gethostname(),
        "uptime_hours": round(uptime() / 3600, 1),
        "listening_ports": listening_ports(),
        "world_writable_home": world_writable_home(),
        "pending_updates": package_updates(),
        "battery_pct": battery_pct(),
        "has_git": bool(shutil.which("git")),
        "has_python": bool(shutil.which("python3")),
        "ssh_running": bool(shutil.which("sshd")),
    }
