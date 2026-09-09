"""DAC Daemon — runs in background via tmux, executes tasks on demand."""
import os
import sys
import time
import signal
import json
import threading
from pathlib import Path
from dac.config import load_config, CONFIG_DIR, LOG_FILE, PID_FILE, TASKS_DIR

FLAG_FILE = Path("/tmp/dac_trigger.flag")


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def signal_handler(sig, frame):
    log("Shutting down DAC daemon.")
    if PID_FILE.exists():
        PID_FILE.unlink()
    sys.exit(0)


def trigger(prompt, task_name=None):
    task_name = task_name or f"dac_{int(time.time())}"
    task_file = TASKS_DIR / f"{task_name}.json"
    task = {
        "name": task_name,
        "prompt": prompt,
        "status": "pending",
        "created": int(time.time()),
        "results": None,
    }
    with open(task_file, "w") as f:
        json.dump(task, f, indent=2)
    with open(FLAG_FILE, "w") as f:
        f.write(task_name)
    log(f"Triggered task: {task_name}")
    return task_name


def run_daemon(interval=5):
    """Main daemon loop."""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGPIPE, signal_handler)
    PID_FILE.write_text(str(os.getpid()))
    log(f"DAC daemon started (PID={os.getpid()})")
    cfg = load_config()
    processed = set()

    # Optional background services
    if cfg.get("telegram_token"):
        def _tg():
            while True:
                try:
                    from dac.telegram_bot import run_bot
                    run_bot(cfg=cfg)
                except Exception as e:
                    log(f"[telegram] {e}")
                    time.sleep(10)

        threading.Thread(target=_tg, daemon=True, name="dac-telegram").start()
        log("Telegram bot service started.")

    def _monitors_loop():
        while True:
            try:
                from dac.monitor import run_all
                run_all(cfg=cfg)
            except Exception as e:
                log(f"[monitor] {e}")
            time.sleep(60)

    threading.Thread(target=_monitors_loop, daemon=True, name="dac-monitors").start()

    # Process any pending tasks on startup
    for f in TASKS_DIR.glob("*.json"):
        with open(f) as fh:
            task = json.load(fh)
        if task.get("status") == "pending" and task["name"] not in processed:
            log(f"Processing queued task: {task['name']}")
            try:
                from dac.orchestrator import execute_task
                execute_task(task["name"], cfg=cfg)
                processed.add(task["name"])
            except Exception as e:
                log(f"Error: {e}")

    while True:
        if FLAG_FILE.exists():
            task_name = FLAG_FILE.read_text().strip()
            FLAG_FILE.unlink()
            if task_name not in processed:
                log(f"Processing triggered task: {task_name}")
                try:
                    from dac.orchestrator import execute_task
                    execute_task(task_name, cfg=cfg)
                    processed.add(task_name)
                except Exception as e:
                    log(f"Error processing {task_name}: {e}")
        time.sleep(interval)


def daemon_status():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
        except ValueError:
            PID_FILE.unlink()
            return False, None
        try:
            os.kill(pid, 0)
            return True, pid
        except (ProcessLookupError, PermissionError):
            PID_FILE.unlink()
            return False, None
    return False, None
