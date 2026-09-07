"""Session/context manager — persists conversation history and project state."""
import json
import os
import time
from pathlib import Path

from dac.config import SESSIONS_DIR

SYSTEM_PROMPT = """You are DAC (Decentralized Autonomous Coder), an elite autonomous coding agent running on an Android device.
You can generate, modify, and execute code. You have access to:
- Python 3.12 execution
- Bash shell commands
- Full filesystem access at /root and /sdcard
- Android device controls (termux commands, intents, shizuku, bsh)

When the user asks you to do something:
1. Think through what needs to be done
2. Write the code or commands needed
3. Present them clearly in fenced code blocks (```python or ```bash)
4. After presenting, say EXACTLY "AUTONOMY_READY" if the action should be executed automatically

Guidelines:
- Be precise and efficient — no unnecessary explanations
- Always use full paths when writing files
- For complex tasks, break into steps
- Use proper error handling
- Store persistent data in /root/projects/
- When creating tools, make them standalone and installable"""

class Session:
    def __init__(self, session_id=None):
        self.session_id = session_id or f"sess_{int(time.time())}"
        self.dir = SESSIONS_DIR / self.session_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.dir / "history.json"
        self.messages = []
        self._load()

    def _load(self):
        if self.history_file.exists():
            with open(self.history_file) as f:
                self.messages = json.load(f)

    def save(self):
        with open(self.history_file, "w") as f:
            json.dump(self.messages, f, indent=1)

    def add_user(self, text):
        self.messages.append({"role": "user", "content": text})
        self.save()

    def add_assistant(self, text):
        self.messages.append({"role": "assistant", "content": text})
        self.save()

    def get_full_messages(self, include_system=True):
        msgs = []
        if include_system:
            msgs.append({"role": "system", "content": SYSTEM_PROMPT})
        # Keep last N messages to avoid token overflow
        history = self.messages[-50:] if len(self.messages) > 50 else self.messages
        msgs.extend(history)
        return msgs

    def clear(self):
        self.messages = []
        self.save()

    def status(self):
        return {
            "session_id": self.session_id,
            "turns": len(self.messages),
            "dir": str(self.dir),
        }

def list_sessions():
    sessions = []
    for d in SESSIONS_DIR.iterdir():
        if d.is_dir() and (d / "history.json").exists():
            with open(d / "history.json") as fh:
                hist = json.load(fh)
            sessions.append({
                "id": d.name,
                "turns": len(hist),
            })
    return sorted(sessions, key=lambda s: s["id"], reverse=True)
