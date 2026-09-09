"""Master launcher — the single entry point for all DAC operations."""
import argparse
import sys
import os
import json
import time
import signal
from pathlib import Path

DAC_ROOT = str(Path(__file__).resolve().parent.parent)

DAEMON_CMD = f'cd {DAC_ROOT} && "{sys.executable}" -c "from dac.daemon import run_daemon; run_daemon()"'

def cmd_init(args):
    from dac.config import load_config, save_config, CONFIG_DIR, PROJECTS_DIR, SESSIONS_DIR
    cfg = load_config()
    if args.api_key:
        cfg["api_key"] = args.api_key
        save_config(cfg)
        print("API key set.")
    if args.model:
        cfg["model"] = args.model
        save_config(cfg)
        print(f"Model: {args.model}")
    for d in [CONFIG_DIR, PROJECTS_DIR, SESSIONS_DIR]:
        Path(d).mkdir(parents=True, exist_ok=True)
    print("DAC initialized.")
    print(f"Config: {CONFIG_DIR}")
    print(f"Projects: {PROJECTS_DIR}")
    return 0

def cmd_daemon(args):
    from dac.daemon import daemon_status
    if args.action == "start":
        running, pid = daemon_status()
        if running:
            print(f"Already running (PID={pid})")
            return 0
        import subprocess
        session_name = "dac-daemon"
        subprocess.run(["tmux", "kill-session", "-t", session_name], capture_output=True)
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, DAEMON_CMD],
            check=False, capture_output=True,
        )
        time.sleep(2)
        running, pid = daemon_status()
        if running:
            print(f"DAC daemon started (PID={pid})")
        else:
            from dac.config import LOG_FILE
            log_f = LOG_FILE
            if log_f.exists():
                print(log_f.read_text()[-500:])
            print("Failed to start daemon.")
        return 0
    elif args.action == "stop":
        running, pid = daemon_status()
        if running:
            os.kill(pid, signal.SIGTERM)
            print(f"Stopped daemon (PID={pid})")
        else:
            print("Daemon not running.")
        return 0
    elif args.action == "status":
        running, pid = daemon_status()
        print(f"Running: {running} (PID={pid})")
        return 0
    return 0

def cmd_trigger(args):
    from dac.daemon import trigger
    task_name = trigger(args.prompt, args.name)
    print(f"Task queued: {task_name}")
    return 0

def cmd_tasks(args):
    from dac.orchestrator import list_tasks, execute_task
    if args.run and not getattr(args, "list", False):
        task = execute_task(args.run)
        if task and task.get("results"):
            r = task["results"]
            for f in r.get("files_written", []):
                print(f"  ✓ {f}")
            for c in r.get("commands_run", []):
                print(f"  → {c['cmd'][:80]} (rc={c['rc']})")
            for e in r.get("errors", []):
                print(f"  ✗ {e}")
        return 0
    tasks = list_tasks()
    if not tasks:
        print("No tasks.")
        return 0
    for t in tasks[:10]:
        status = t.get("status", "?")
        icon = {"done": "✓", "pending": "○", "failed": "✗", "partial": "~"}.get(status, "?")
        print(f"  {icon} {t['name']:30s} [{status}]")
    return 0

def cmd_send(args):
    from dac.daemon import trigger
    import subprocess
    task_name = trigger(args.prompt)
    print(f"Queued: {task_name}")
    subprocess.run([
        "termux-notification", "-t", "DAC", "-c", f"Task: {task_name}",
        "--id", "dac_task"
    ], capture_output=True)
    print("Notification sent.")
    return 0

def cmd_quick(args):
    from dac.orchestrator import create_task, execute_task
    from dac.config import load_config
    cfg = load_config()
    task_name = f"quick_{int(time.time())}"
    create_task(args.prompt, task_name)
    print(f"[dac] Processing: {args.prompt[:100]}")
    result = execute_task(task_name, cfg=cfg)
    if result and result.get("results"):
        r = result["results"]
        if r.get("files_written"):
            print("\nFiles:")
            for f in r["files_written"]:
                print(f"  ✓ {f}")
        if r.get("commands_run"):
            print("\nOutput:")
            for c in r["commands_run"]:
                print(c.get("output", "")[:1000])
        if r.get("errors"):
            print("\nErrors:")
            for e in r["errors"]:
                print(f"  ✗ {e}")
    return 0

def main(argv=None):
    from dac import __version__
    parser = argparse.ArgumentParser(
        prog="dac",
        description="DAC — Decentralized Autonomous Coder",
    )
    parser.add_argument("-V", "--version", action="version", version=f"dac {__version__}")
    sub = parser.add_subparsers(dest="command")
    p_init = sub.add_parser("init", help="Initialize DAC")
    p_init.add_argument("--api-key", help="OpenAI API key")
    p_init.add_argument("--model", help="LLM model (default: gpt-4o)")
    p_trig = sub.add_parser("trigger", help="Send a task prompt to the daemon")
    p_trig.add_argument("prompt")
    p_trig.add_argument("--name")
    p_daemon = sub.add_parser("daemon", help="Control the DAC daemon")
    p_daemon.add_argument("action", choices=["start", "stop", "status"])
    p_tasks = sub.add_parser("tasks", help="List and manage tasks")
    p_tasks.add_argument("--list", action="store_true", help="List tasks")
    p_tasks.add_argument("--run", help="Execute a specific task")
    p_send = sub.add_parser("send", help="Quick: send prompt + notify")
    p_send.add_argument("prompt")
    p_quick = sub.add_parser("quick", help="One-shot: generate + execute")
    p_quick.add_argument("prompt")
    p_repl = sub.add_parser("repl", help="Interactive REPL")
    p_chat = sub.add_parser("chat", help="One-shot chat")
    p_chat.add_argument("prompt")
    p_cfg = sub.add_parser("config", help="View/set config")
    p_cfg.add_argument("--show", action="store_true")
    p_cfg.add_argument("--set", help="key=value")
    p_dev = sub.add_parser("device", help="Device info")
    p_dev.add_argument("--all", action="store_true")
    p_dev.add_argument("--files", action="store_true")
    p_proj = sub.add_parser("project", help="Manage projects")
    p_proj.add_argument("--list", action="store_true")
    p_proj.add_argument("--new")
    p_proj.add_argument("--info")
    p_run = sub.add_parser("run", help="Execute code directly")
    p_run.add_argument("code")
    p_run.add_argument("--language", "-l", default="python")
    p_doctor = sub.add_parser("doctor", help="System health check")
    p_sess = sub.add_parser("sessions", help="List past sessions")
    p_assistant = sub.add_parser("assistant", help="Personal assistant (TTS + notifications)")
    p_assistant.add_argument("--say", help="Speak one message and exit")
    p_assistant.add_argument("--remind", help="Schedule a reminder")
    p_assistant.add_argument("--in", dest="in_", help="Delay for --remind (30m, 2h, 90s)")
    p_monitor = sub.add_parser("monitor", help="Price/API monitor with alerts")
    p_monitor.add_argument("name", nargs="?")
    p_monitor.add_argument("--add", metavar="NAME")
    p_monitor.add_argument("--url", help="JSON endpoint for --add")
    p_monitor.add_argument("--path", help="Dot path to value, e.g. bitcoin.usd")
    p_monitor.add_argument("--threshold", type=float, default=5.0)
    p_monitor.add_argument("--interval", type=int, default=300)
    p_monitor.add_argument("--list", action="store_true")
    p_monitor.add_argument("--remove", metavar="NAME")
    p_telegram = sub.add_parser("telegram", help="Telegram bot backend (long polling)")
    p_telegram.add_argument("--oneshot", action="store_true", help="Process pending updates once")
    p_demo = sub.add_parser("demo", help="Scripted on-device demo (no LLM needed)")
    p_demo.add_argument("--project-dir", help="Where to write the demo project")
    p_site = sub.add_parser("site", help="GCI site generator (landing page + 2h protection feed)")
    p_site.add_argument("--build", action="store_true", help="Generate site once")
    p_site.add_argument("--update", action="store_true", help="Rotate protection and regenerate")
    p_site.add_argument("--serve", action="store_true", help="Serve over HTTP")
    p_site.add_argument("--auto-loop", dest="auto_loop", action="store_true", help="Rotate forever every --interval hours")
    p_site.add_argument("--port", type=int, default=8080)
    p_site.add_argument("--interval", type=float, default=2.0, help="Hours between rotations")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    if args.command == "init":
        return cmd_init(args)
    elif args.command == "trigger":
        return cmd_trigger(args)
    elif args.command == "daemon":
        return cmd_daemon(args)
    elif args.command == "tasks":
        return cmd_tasks(args)
    elif args.command == "send":
        return cmd_send(args)
    elif args.command == "quick":
        return cmd_quick(args)
    elif args.command == "repl":
        from dac.repl import repl
        repl()
    elif args.command == "chat":
        from dac.cli import cmd_chat
        return cmd_chat(args)
    elif args.command == "config":
        from dac.cli import cmd_config
        return cmd_config(args)
    elif args.command == "device":
        from dac.cli import cmd_device
        return cmd_device(args)
    elif args.command == "project":
        from dac.cli import cmd_project
        return cmd_project(args)
    elif args.command == "run":
        from dac.cli import cmd_run
        return cmd_run(args)
    elif args.command == "doctor":
        from dac.cli import cmd_doctor
        return cmd_doctor()
    elif args.command == "sessions":
        from dac.cli import cmd_session
        return cmd_session(args)
    elif args.command == "assistant":
        from dac.assistant import main as assistant_main
        argv = []
        if args.say:
            argv = ["--say", args.say]
        elif args.remind:
            argv = ["--remind", args.remind, "--in", args.in_ or "30m"]
        return assistant_main(argv)
    elif args.command == "monitor":
        from dac.monitor import main as monitor_main
        argv = []
        if args.list:
            argv = ["--list"]
        elif args.remove:
            argv = ["--remove", args.remove]
        elif args.add:
            argv = ["--add", args.add]
            if args.url:
                argv += ["--url", args.url]
            if args.path:
                argv += ["--path", args.path]
            argv += ["--threshold", str(args.threshold), "--interval", str(args.interval)]
        elif args.name:
            argv = [args.name]
        return monitor_main(argv)
    elif args.command == "telegram":
        from dac.telegram_bot import main as telegram_main
        return telegram_main(["--oneshot"] if args.oneshot else [])
    elif args.command == "demo":
        from dac.demo import main as demo_main
        return demo_main(["--project-dir", args.project_dir] if args.project_dir else [])
    elif args.command == "site":
        from dac.site import main as site_main
        argv = []
        if args.serve:
            argv = ["--serve", "--port", str(args.port)]
        elif args.update:
            argv = ["--update"]
        elif args.auto_loop:
            argv = ["--auto-loop", "--interval", str(args.interval)]
        elif args.build:
            argv = ["--build"]
        return site_main(argv)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # Handle pipe closures (e.g., dac config --show | grep)
        sys.exit(0)
