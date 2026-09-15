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
