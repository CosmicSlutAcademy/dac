"""DAC configuration management."""
import os
import json
import shutil
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("DAC_HOME", Path.home() / ".dac"))
CONFIG_FILE = CONFIG_DIR / "config.json"
CONFIG_BACKUP = CONFIG_DIR / "config.json.bak"
PROJECTS_DIR = CONFIG_DIR / "projects"
SESSIONS_DIR = CONFIG_DIR / "sessions"
TASKS_DIR = CONFIG_DIR / "tasks"
LOG_FILE = CONFIG_DIR / "dac.log"
PID_FILE = CONFIG_DIR / "dac.pid"

DEFAULTS = {
    "provider": "openai",
    "fallback_provider": "",
    "model": "gpt-4o",
    "api_key": "",
    "telegram_token": "",
    "max_tokens": 4096,
    "temperature": 0.2,
    "max_retries": 3,
    "projects_dir": str(PROJECTS_DIR),
    "auto_execute": False,
    "sandbox": True,
    "log_commands": True,
}

def ensure_dirs():
    for d in [CONFIG_DIR, PROJECTS_DIR, SESSIONS_DIR, TASKS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def _read_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _try_backup():
    """Restore config from .bak if present and valid."""
    if not CONFIG_BACKUP.exists():
        return None
    try:
        saved = _read_json(CONFIG_BACKUP)
        if isinstance(saved, dict):
            return {**DEFAULTS, **saved}
    except (json.JSONDecodeError, ValueError, OSError):
        pass
    return None

def load_config():
    ensure_dirs()
    cfg = None
    if CONFIG_FILE.exists():
        try:
            saved = _read_json(CONFIG_FILE)
            if isinstance(saved, dict):
                cfg = {**DEFAULTS, **saved}
            else:
                raise ValueError("config root must be an object")
        except (json.JSONDecodeError, ValueError, OSError):
            cfg = None
    if cfg is None:
        restored = _try_backup()
        if restored is not None:
            cfg = restored
            print("Warning: config.json was corrupt; restored from backup.")
            # Write the restored config back so the corrupt copy is replaced.
            try:
                save_config(cfg, backup=False)
            except OSError:
                pass
        else:
            cfg = DEFAULTS.copy()
            print("Warning: config.json is corrupt, resetting to defaults.")
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("OPENAI_API_KEY", "")
    return cfg

def save_config(cfg: dict, backup=True):
    ensure_dirs()
    # Atomic write: temp file then rename, so a crash never leaves a 0-byte config.
    tmp = CONFIG_DIR / "config.json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, CONFIG_FILE)
    # Always mirror the latest valid config into the backup, so a later
    # clipboard/truncation accident can be auto-restored.
    if backup:
        try:
            shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)
        except OSError:
            pass
    return cfg

def get(key=None, cfg=None):
    if cfg is None:
        cfg = load_config()
    if key is None:
        return cfg
    return cfg.get(key, DEFAULTS.get(key))
