"""Telegram bot backend — stdlib-only long polling. Bridging the daemon to Telegram."""
import json
import time
import urllib.parse
import urllib.request

from dac.config import load_config
from dac.core.llm import complete, LLMError
from dac.core.session import Session
from dac.orchestrator import create_task, execute_task, list_tasks

API = "https://api.telegram.org/bot{token}/"

HELP = """Commands:
/chat <message>   — ask the AI
/quick <task>     — autonomous: generate + execute
/tasks            — list tasks
/monitor          — show price monitors
/device           — phone status
/help             — this message"""


def api(method, token, params=None, timeout=60):
    import urllib.error
    url = API.format(token=token) + method
    data = json.dumps(params or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:200]
        raise RuntimeError(f"Telegram API HTTP {e.code}: {detail}")


def send(token, chat_id, text):
    return api("sendMessage", token, {
        "chat_id": chat_id,
        "text": text[:4000],
        "disable_web_page_preview": True,
    })


def sessions_for(chat_id):
    return Session(session_id=f"tg_{chat_id}")


def handle_update(token, update, cfg):
    msg = update.get("message") or {}
    text = (msg.get("text") or "").strip()
    chat_id = msg.get("chat", {}).get("id")
    if not chat_id or not text:
        return

    if text in ("/start", "/help"):
        send(token, chat_id, "DAC — Decentralized Autonomous Coder on your phone.\n\n" + HELP)
        return
    if text.startswith("/chat "):
        _cmd_chat(token, chat_id, text[6:].strip(), cfg)
        return
    if text.startswith("/quick "):
        _cmd_quick(token, chat_id, text[7:].strip(), cfg)
        return
    if text == "/tasks":
        send(token, chat_id, _tasks_text())
        return
    if text == "/monitor":
        from dac.monitor import list_monitors, load_monitors
        from dac.monitor import run_all
        monitors = load_monitors()
        if not monitors:
            send(token, chat_id, "No monitors. Add one with: dac monitor --add BTC")
            return
        run_all(names=[m["name"] for m in monitors][:5])
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            list_monitors()
        send(token, chat_id, "Monitors:\n" + buf.getvalue())
        return
    if text == "/device":
        from dac.core.executor import run_cmd
        lines = []
        for c in ["termux-battery-status", "termux-wifi-connectioninfo"]:
            rc, out, err = run_cmd(c)
            lines.append(out.strip()[:300] or err.strip()[:300])
        send(token, chat_id, "\n\n".join(lines) or "Device info unavailable.")
        return
    send(token, chat_id, "Unknown command.\n" + HELP)


def _cmd_chat(token, chat_id, prompt, cfg):
    s = sessions_for(chat_id)
    s.add_user(prompt)
    try:
        text, usage = complete(cfg, s.get_full_messages())
        s.add_assistant(text)
        tail = f"\n[tokens: {usage.get('total_tokens', '?')}]" if usage else ""
        send(token, chat_id, text + tail)
    except LLMError as e:
        send(token, chat_id, f"Error: {e}")


def _cmd_quick(token, chat_id, task, cfg):
    send(token, chat_id, f"⚙ Running: {task[:120]}")
    try:
        name = f"tg_{int(time.time())}"
        create_task(task, task_name=name)
        result = execute_task(name, cfg=cfg)
        if not result or not result.get("results"):
            send(token, chat_id, f"Task {name}: no results (status: {result.get('status') if result else '?'})")
            return
        r = result["results"]
        parts = [f"✓ {result['status']}"]
        if r.get("files_written"):
            parts.append("Files:\n" + "\n".join(f"  {f}" for f in r["files_written"][:10]))
        if r.get("commands_run"):
            parts.append("Output:\n" + "\n".join(c.get("output", "")[:200] for c in r["commands_run"][:5]))
        if r.get("errors"):
            parts.append("Errors:\n" + "\n".join(f"  ✗ {e[:200]}" for e in r["errors"][:5]))
        send(token, chat_id, "\n\n".join(parts))
    except Exception as e:
        send(token, chat_id, f"Task failed: {e}")


def _tasks_text():
    tasks = list_tasks()
    if not tasks:
        return "No tasks."
    lines = []
    for t in tasks[:10]:
        icon = {"done": "✓", "pending": "○", "failed": "✗", "partial": "~"}.get(t.get("status"), "?")
        lines.append(f"{icon} {t['name']} [{t.get('status')}]")
    return "Tasks:\n" + "\n".join(lines)


def run_bot(token=None, one_shot=False, cfg=None):
    cfg = cfg or load_config()
    token = token or cfg.get("telegram_token", "")
    if not token:
        raise RuntimeError(
            "No Telegram token. Set it in ~/.dac/config.json:\n"
            "  dac config --set telegram_token 123456:YOUR-BOT-TOKEN"
        )
    offset = 0
    while True:
        try:
            resp = api("getUpdates", token, {"timeout": 10, "offset": offset})
            for u in resp.get("result", []):
                try:
                    handle_update(token, u, cfg)
                except Exception as e:
                    print(f"[telegram] update error: {e}")
                offset = max(offset, u["update_id"] + 1)
        except Exception as e:
            print(f"[telegram] poll error: {e}")
        if one_shot:
            return 0
        time.sleep(1)


def main(argv=None):
    if argv is None:
        import sys
        argv = sys.argv[1:]
    import argparse
    p = argparse.ArgumentParser(prog="dac telegram", description="Telegram bot backend")
    p.add_argument("--oneshot", action="store_true", help="Process pending updates once and exit")
    args = p.parse_args(argv)
    try:
        return run_bot(one_shot=args.oneshot)
    except RuntimeError as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
