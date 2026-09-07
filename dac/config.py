"""DAC configuration management."""
import os
import json
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("DAC_HOME", Path.home() / ".dac"))
CONFIG_FILE = CONFIG_DIR / "config.json"
PROJECTS_DIR = CONFIG_DIR / "projects"
SESSIONS_DIR = CONFIG_DIR / "sessions"
TASKS_DIR = CONFIG_DIR / "tasks"
LOG_FILE = CONFIG_DIR / "dac.log"
PID_FILE = CONFIG_DIR / "dac.pid"

DEFAULTS = {
    "provider": "openai",
    "model": "gpt-4o",
    "api_key": "",
    "max_tokens": 4096,
    "temperature": 0.2,
    "projects_dir": str(PROJECTS_DIR),
    "auto_execute": False,
    "sandbox": True,
    "log_commands": True,
}

def ensure_dirs():
    for d in [CONFIG_DIR, PROJECTS_DIR, SESSIONS_DIR, TASKS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def load_config():
    ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
        cfg = {**DEFAULTS, **saved}
    else:
        cfg = DEFAULTS.copy()
    if not cfg.get("api_key"):
        cfg["api_key"] = os.environ.get("OPENAI_API_KEY", "")
    return cfg

def save_config(cfg: dict):
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
    return cfg

def get(key=None, cfg=None):
    if cfg is None:
        cfg = load_config()
    if key is None:
        return cfg
    return cfg.get(key, DEFAULTS.get(key))
