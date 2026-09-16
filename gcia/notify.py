"""GCIA alerts — push findings to the phone via Termux API (zero deps)."""

import shutil
import subprocess


def termux_binary(name):
    return shutil.which(name)


def notify(title, content, notif_id="gcia"):
    """Send an Android notification via termux-notification, else print."""
    n = termux_binary("termux-notification")
    if n:
        try:
            subprocess.run([n, "--title", title, "-c", content, "--id", notif_id],
                           capture_output=True, timeout=15)
            return True
        except Exception:
            pass
    print(f"[GCIA ALERT] {title}\n{content}")
    return False


def speak(text):
    """Speak via termux-tts-speak if present, else just print."""
    t = termux_binary("termux-tts-speak")
    if t:
        try:
            subprocess.run([t, text], capture_output=True, timeout=15)
            return True
        except Exception:
            pass
    print(text)
    return False


def push_alert(title, content, sound=False, notif_id="gcia"):
    ok = notify(title, content, notif_id=notif_id)
    if sound:
        speak(f"GCIA alert. {title}")
    return ok


# --- Telegram alert channel (stdlib, via Bot API) ---
import json as _json
import os as _os
import urllib.request as _request
import urllib.error as _error
from pathlib import Path as _Path

TG_CONF = _Path(_os.path.expanduser("~/.gcia/telegram.json"))


def telegram_config():
    """Return {token, chat_id} from telegram.json or env overrides."""
    cfg = {}
    try:
        if TG_CONF.exists():
            cfg = _json.loads(TG_CONF.read_text())
    except Exception:
        cfg = {}
    env_token = _os.environ.get("GCIA_TELEGRAM_TOKEN")
    env_chat = _os.environ.get("GCIA_TELEGRAM_CHAT_ID")
    if env_token:
        cfg["token"] = env_token
    if env_chat:
        cfg["chat_id"] = env_chat
    return cfg


def set_telegram(token, chat_id):
    TG_CONF.parent.mkdir(parents=True, exist_ok=True)
    TG_CONF.write_text(_json.dumps({"token": token.strip(), "chat_id": str(chat_id).strip()}))
    TG_CONF.chmod(0o600)
    return str(TG_CONF)


def clear_telegram():
    if TG_CONF.exists():
        TG_CONF.unlink()
        return True
    return False


def telegram_alert(title, content):
    """Send a patrol/alert message to Telegram. Returns True on success."""
    cfg = telegram_config()
    token, chat = cfg.get("token", ""), cfg.get("chat_id", "")
    if not token or not chat:
        return False
    text = f"⚡ {title}\n{content}"[:4000]
    try:
        req = _request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=_json.dumps({"chat_id": chat, "text": text,
                              "disable_web_page_preview": True}).encode(),
            headers={"Content-Type": "application/json"})
        with _request.urlopen(req, timeout=20) as r:
            r.read()
        return True
    except Exception:
        return False


def push_alert(title, content, sound=False, notif_id="gcia", telegram=True):
    ok = notify(title, content, notif_id=notif_id)
    if telegram:
        tg = telegram_alert(title, content)
        if tg:
            ok = True
    if sound:
        speak(f"GCIA alert. {title}")
    return ok
