"""GCIA mind-layer evidence core — encrypted contact log.

The contact log is the investigative branch's structured record of subjective
mind-layer experiences: awake perception, dreams, hypnagogia, meditation, and
reported "contact"-type phenomena. Entries are stored AES-256-CBC encrypted
with a locally generated key (mode 0600) plus a plaintext SHA-256 so tampering
or corruption is detectable on read-back.

Epistemic discipline (GCIAu rule 1): content is an honest report of subjective
experience, never presented as physically verified fact. The `label` field is
the recorder's own honesty check (speculative | insight | distress | dream...).
"""

import datetime
import hashlib
import json
import os
import secrets
import subprocess
from pathlib import Path

LOGDIR = Path(os.path.expanduser("~/.gcia"))
LOG_ENC = LOGDIR / "contact-log.enc"
LOG_KEY = LOGDIR / "contact-log.key"
LOG_META = LOGDIR / "contact-log.meta"

MODES = ["awake", "dream", "hypnagogic", "meditation", "other"]
MOODS = ["calm", "neutral", "focused", "anxious", "overwhelmed", "euphoric", "other"]
LABELS = ["speculative", "insight", "dream", "distress", "memory", "other"]
DISTRESS_WORDS = [
    "self harm", "self-harm", "kill myself", "end my life", "suicid",
    "hurt myself", "can't tell what's real", "cant tell what's real",
    "losing my mind", "panicked", "panic attack", "paranoid", "being watched",
    "accessed against my will", "control my mind", "afraid to sleep",
]

_GALACTIC_NOTE = (
    "GCIA mind-layer protocol: the mind is treated as a real, private "
    "subjective dimension that current instruments cannot measure directly. "
    "Entries document experience honestly; they are evidence about the "
    "experience, not proof of external agents."
)


def _ensure_key():
    LOGDIR.mkdir(parents=True, exist_ok=True)
    if not LOG_KEY.exists():
        key = secrets.token_hex(32)
        LOG_KEY.write_text(key + "\n")
        os.chmod(LOG_KEY, 0o600)
    if LOG_KEY.stat().st_mode & 0o777 != 0o600:
        os.chmod(LOG_KEY, 0o600)
    return str(LOG_KEY)


def _sha256(b):
    return hashlib.sha256(b).hexdigest()


def _read_entries():
    if not LOG_ENC.exists():
        return []
    key_path = _ensure_key()
    meta = None
    if LOG_META.exists():
        meta = json.loads(LOG_META.read_text())
    iv = meta["iv"] if meta else None
    if not iv:
        raise RuntimeError("contact log is corrupt: missing IV metadata")
    try:
        out = subprocess.run(
            ["openssl", "enc", "-d", "-aes-256-cbc",
             "-K", open(key_path).read().strip().encode().hex(), "-iv", iv,
             "-in", str(LOG_ENC)],
            capture_output=True, check=True,
        ).stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError("contact log is corrupt — decryption failed (tampered or wrong key): "
                           + (e.stderr or b"").decode("utf-8", "replace")[:160]) from e
    if meta and meta.get("sha256") and _sha256(out) != meta["sha256"]:
        raise RuntimeError("contact log integrity check FAILED — file tampered or corrupt")
    if not out.strip():
        return []
    return [json.loads(line) for line in out.decode("utf-8", "replace").splitlines() if line.strip()]


def _write_entries(entries):
    _ensure_key()
    iv = secrets.token_hex(16)
    plain = ("\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n").encode("utf-8")
    out = subprocess.run(
        ["openssl", "enc", "-aes-256-cbc",
         "-K", open(LOG_KEY).read().strip().encode().hex(), "-iv", iv,
         "-in", "-"],
        input=plain, capture_output=True, check=True,
    ).stdout
    LOG_ENC.write_bytes(out)
    LOG_META.write_text(json.dumps({"iv": iv, "sha256": _sha256(plain),
                                    "cipher": "aes-256-cbc", "entries": len(entries)}))
    LOG_ENC.chmod(0o600)


def add_entry(content, mode="awake", mood="calm", sleep_h=None, stress=None,
              context="", label="speculative", tags=None):
    """Append one encrypted entry. Returns the entry dict with its id."""
    if not content or not content.strip():
        raise ValueError("content required")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mood not in MOODS:
        raise ValueError(f"mood must be one of {MOODS}")
    if label not in LABELS:
        raise ValueError(f"label must be one of {LABELS}")
    if stress is not None:
        stress = int(stress)
        if not 1 <= stress <= 10:
            raise ValueError("stress must be 1-10")
    if sleep_h is not None:
        sleep_h = float(sleep_h)
        if sleep_h < 0 or sleep_h > 24:
            raise ValueError("sleep_h must be 0-24")
    now = datetime.datetime.now(datetime.timezone.utc)
    entry = {
        "id": f"cl_{now.strftime('%Y%m%dT%H%M%S')}_{secrets.token_hex(3)}",
        "ts": now.isoformat(),
        "mode": mode,
        "mood": mood,
        "sleep_h": sleep_h,
        "stress": stress,
        "context": (context or "").strip()[:200],
        "content": content.strip(),
        "label": label,
        "tags": [t.strip() for t in (tags or []) if t.strip()][:8],
        "hash": _sha256(content.strip().encode("utf-8")),
    }
    entries = _read_entries()
    entries.append(entry)
    _write_entries(entries)
    return entry


def list_entries(limit=None):
    entries = _read_entries()
    entries = sorted(entries, key=lambda e: e.get("ts", ""), reverse=True)
    if limit:
        entries = entries[:limit]
    return entries


def drop_entry(entry_id):
    """Remove one entry by id (e.g. mislabel correction). Returns True if removed."""
    entries = _read_entries()
    kept = [e for e in entries if e.get("id") != entry_id]
    if len(kept) == len(entries):
        return False
    _write_entries(kept)
    return True


def stats():
    entries = _read_entries()
    n = len(entries)
    labels = {}
    modes = {}
    sleeps, stresses = [], []
    for e in entries:
        labels[e.get("label", "other")] = labels.get(e.get("label", "other"), 0) + 1
        modes[e.get("mode", "other")] = modes.get(e.get("mode", "other"), 0) + 1
        if e.get("sleep_h") is not None:
            sleeps.append(float(e["sleep_h"]))
        if e.get("stress") is not None:
            stresses.append(int(e["stress"]))
    newest = entries[-1].get("ts") if entries else None
    oldest = entries[0].get("ts") if entries else None
    return {
        "entries": n,
        "first": oldest,
        "latest": newest,
        "labels": labels,
        "modes": modes,
        "avg_sleep_h": round(sum(sleeps) / len(sleeps), 2) if sleeps else None,
        "avg_stress": round(sum(stresses) / len(stresses), 2) if stresses else None,
    }


def backup(dst_dir=None):
    """Copy current encrypted journal + key to a timestamped backup."""
    import shutil
    if not LOG_ENC.exists():
        return None
    bdir = Path(dst_dir or (LOGDIR / "backups"))
    bdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    pair = []
    for src, ext in ((LOG_ENC, ".enc"), (LOG_META, ".meta"), (LOG_KEY, ".key")):
        if src.exists():
            dst = bdir / f"contact-log-{ts}{ext}"
            shutil.copy2(src, dst)
            dst.chmod(0o600)
            pair.append(str(dst))
    return pair


def rotate_key():
    """Re-encrypt the journal under a fresh key; old material is backed up."""
    entries = _read_entries()
    kept = backup()
    for f in (LOG_KEY, LOG_ENC, LOG_META):
        if f.exists():
            f.unlink()
    _write_entries(entries)
    return {"entries": len(entries), "backup": kept}


def export_plain(dst):
    """Export decrypted journal to a plaintext file (explicit, owner-intended)."""
    entries = list_entries()
    lines = [_GALACTIC_NOTE, ""]
    for e in entries:
        lines.append(f"-- {e['ts']} [{e.get('mode','')}/{e.get('label','')}] "
                     f"sleep={e.get('sleep_h')} stress={e.get('stress')}")
        if e.get("context"):
            lines.append(f"   context: {e['context']}")
        lines.append(f"   {e['content']}")
    out = Path(dst)
    out.write_text("\n".join(lines) + "\n")
    out.chmod(0o600)
    return str(out)
