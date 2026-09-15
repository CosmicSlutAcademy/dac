"""Auth-granted remote modes — the two Wardencliffe Towers (phone + laptop).

Access is only possible for peers explicitly granted by the owner. Each granted
key is locked to the `gcia-agent` forced command: allowlisted subcommands only,
no PTY, no port forwarding, no arbitrary shell.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

PEERS_FILE = Path(os.path.expanduser("~/.gcia/peers.json"))
AUTH_KEYS = Path(os.path.expanduser("~/.ssh/authorized_keys"))
AGENT_BIN = "/usr/local/bin/gcia-agent"

ALLOWED = {"audit", "status", "brief", "recon", "scan"}

FORCE_PREFIX = (
    f'command="{AGENT_BIN}",no-port-forwarding,no-agent-forwarding,'
    "no-pty,no-user-rc"
)


def _load_peers():
    if PEERS_FILE.exists():
        try:
            return json.loads(PEERS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_peers(peers):
    PEERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PEERS_FILE.write_text(json.dumps(peers, indent=2))


def _touch_auth_keys():
    AUTH_KEYS.parent.mkdir(parents=True, exist_ok=True)
    if not AUTH_KEYS.exists():
        AUTH_KEYS.touch()
        AUTH_KEYS.chmod(0o600)


def grant(name, pubkey_path, allowed=None):
    """Authorize a peer (e.g. the laptop) to run GCIA commands on this host."""
    pk = Path(pubkey_path).read_text().strip()
    if not pk.startswith(("ssh-ed25519", "ssh-rsa", "ecdsa-", "sk-")):
        raise ValueError("not an SSH public key")
    allowed = allowed or list(ALLOWED)
    peers = _load_peers()
    key_id = pk.split()[-1] if len(pk.split()) > 1 else pk[:24]
    peers[name] = {
        "key_id": key_id,
        "allowed": [a for a in allowed if a in ALLOWED],
        "granted_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_peers(peers)
    _touch_auth_keys()
    line = f"{FORCE_PREFIX} {pk}"
    lines = AUTH_KEYS.read_text().splitlines() if AUTH_KEYS.exists() else []
    lines = [l for l in lines if key_id not in l]
    lines.append(line)
    AUTH_KEYS.write_text("\n".join(lines) + "\n")
    AUTH_KEYS.chmod(0o600)
    return peers[name]


def revoke(name):
    peers = _load_peers()
    if name not in peers:
        raise KeyError(f"no peer named {name!r}")
    key_id = peers.pop(name)["key_id"]
    _save_peers(peers)
    if AUTH_KEYS.exists():
        lines = [l for l in AUTH_KEYS.read_text().splitlines() if key_id not in l]
        AUTH_KEYS.write_text("\n".join(lines) + "\n")
    return True


def peers():
    return _load_peers()


def _run_remote(user, host, port, key, command):
    if command not in ALLOWED:
        raise ValueError(f"not an allowed GCIA command: {command}")
    ssh = ["ssh", "-p", str(port), "-i", key, "-o", "BatchMode=yes",
           "-o", "StrictHostKeyChecking=no", f"{user}@{host}", "gcia-agent", command]
    r = subprocess.run(ssh, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"remote failed ({r.returncode}): {r.stderr[:300]}")
    return r.stdout


def remote_audit(user, host, port=2222, key=None, remote_user=None):
    key = key or str(Path.home() / ".ssh" / "id_storm_key")
    return _run_remote(user or "", host, port, key, "audit")


def remote_scan(user, host, target, port=2222, key=None, remote_user=None):
    key = key or str(Path.home() / ".ssh" / "id_storm_key")
    # target must be an IP or hostname — prevent option injection via ssh/scp
    if not target.replace(".", "").replace("-", "").isalnum():
        raise ValueError(f"suspicious target: {target!r}")
    return _run_remote(user or "", host, port, key, f"scan {target}")
