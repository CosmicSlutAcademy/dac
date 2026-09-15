"""Quantum-resilient vault — AES-256-CBC encryption via openssl CLI (zero deps)."""

import json
import os
import secrets
import subprocess
import tempfile


def _openssl_path():
    import shutil
    return shutil.which("openssl")


def generate_key(out_path):
    """Generate a 256-bit key (hex) with the OS CSPRNG."""
    key = secrets.token_hex(32)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        os.chmod(out_path, 0o600)
        f.write(key + "\n")
    return out_path


def encrypt_file(key_path, src, dst=None):
    if not _openssl_path():
        raise RuntimeError("openssl not found — cannot encrypt")
    key = open(key_path).read().strip().encode()
    dst = dst or src + ".enc"
    iv = secrets.token_hex(16)  # 16 bytes for CBC
    cmd = [
        "openssl", "enc", "-aes-256-cbc",
        "-K", key.hex(), "-iv", iv,
        "-in", src, "-out", dst,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    with open(dst + ".meta", "w") as f:
        json.dump({"iv": iv, "cipher": "aes-256-cbc"}, f)
    return dst


def decrypt_file(key_path, enc, dst=None):
    if not _openssl_path():
        raise RuntimeError("openssl not found — cannot decrypt")
    key = open(key_path).read().strip().encode()
    dst = dst or enc[:-4] if enc.endswith(".enc") else enc + ".dec"
    meta = enc + ".meta"
    if os.path.exists(meta):
        m = json.load(open(meta))
        iv = m["iv"]
    else:
        raise RuntimeError(f"missing {meta} — IV not stored; cannot decrypt")
    subprocess.run(
        ["openssl", "enc", "-d", "-aes-256-cbc", "-K", key.hex(), "-iv", iv,
         "-in", enc, "-out", dst],
        check=True, capture_output=True,
    )
    return dst


def checksum(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
