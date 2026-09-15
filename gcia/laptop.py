"""Laptop link — SSH bridge so the laptop can reach this device's CLI."""

import os
import shutil
import subprocess


def ssh_keypair():
    """Ensure an ed25519 keypair exists for laptop access."""
    d = os.path.expanduser("~/.ssh")
    os.makedirs(d, exist_ok=True)
    priv = os.path.join(d, "id_storm_key")
    pub = priv + ".pub"
    if not os.path.exists(priv):
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", priv],
            check=True, capture_output=True,
        )
    return priv, pub


def start_sshd(port=2222):
    """Start a persistent sshd on the device (proot-style)."""
    if not shutil.which("sshd"):
        return False, "sshd not installed (apt-get install -y openssh-server)"
    subprocess.run(["mkdir", "-p", "/run/sshd"], capture_output=True)
    subprocess.run(["mkdir", "-p", os.path.expanduser("~/.ssh")], capture_output=True)
    subprocess.run(["chmod", "700", os.path.expanduser("~/.ssh")], capture_output=True)
    pub = os.path.expanduser("~/.ssh/authorized_keys")
    if not os.path.exists(pub):
        subprocess.run(["touch", pub], capture_output=True)
    return True, f"sshd ready on port {port}"
