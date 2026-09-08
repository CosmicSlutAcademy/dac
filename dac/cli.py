"""DAC CLI command implementations."""
import os
import sys
from pathlib import Path

def cmd_config(args):
    from dac.config import load_config, save_config
    cfg = load_config()
    if args.show:
        def _mask(k, v):
            if not v:
                return v
            if k == "api_key":
                return "sk-***" + str(v)[-4:]
            if k == "telegram_token":
                return "tg-***" + str(v)[-4:]
            if k.endswith("_key") or k.endswith("_token"):
                return "***" + str(v)[-4:]
            return v
        safe = {k: _mask(k, v) for k, v in cfg.items()}
        for k, v in safe.items():
            print(f"{k}: {v}")
        return 0
    if args.set:
        key, _, val = args.set.partition("=")
        if not key:
            print("Format: --set key=value")
            return 1
        cfg[key] = val
        save_config(cfg)
        print(f"Set {key}")
        return 0
    print("Use --show or --set key=value")
    return 0

def cmd_project(args):
    from dac.config import load_config
    cfg = load_config()
    base = os.path.expanduser(cfg.get("projects_dir", "~/.dac/projects"))
    if args.list:
        if not Path(base).exists():
            print("No projects.")
            return 0
        dirs = [p for p in sorted(Path(base).iterdir()) if p.is_dir()]
        if not dirs:
            print("No projects.")
            return 0
        for p in dirs:
            if p.is_dir():
                n_files = sum(1 for _ in p.rglob("*") if _.is_file())
                size = sum(_.stat().st_size for _ in p.rglob("*") if _.is_file())
                print(f"  {p.name:30s} {n_files:4d} files  {size/1024:.0f} KB")
        return 0
    if args.new:
        p = Path(base) / args.new
        p.mkdir(parents=True, exist_ok=True)
        print(f"Created: {p}")
        return 0
    if args.info:
        p = Path(base) / args.info
        if not p.exists():
            print(f"Not found: {p}")
            return 1
        n_files = sum(1 for _ in p.rglob("*") if _.is_file())
        print(f"Project: {args.info}")
        print(f"Path:    {p}")
        print(f"Files:   {n_files}")
        return 0
    print("Use --list, --new NAME, or --info NAME")
    return 0

def cmd_session(args):
    from dac.core.session import list_sessions
    sessions = list_sessions()
    if not sessions:
        print("No sessions yet.")
        return 0
    for s in sessions[:10]:
        print(f"  {s['id']}  ({s['turns']} turns)")
    return 0

def cmd_run(args):
    from dac.core.executor import execute_block
    rc, out, t = execute_block(args.code, lang=getattr(args, 'language', 'python'))
    print(out)
    return rc

def cmd_device(args):
    from dac.core.executor import run_cmd
    if args.all:
        cmds = ["termux-device-info", "termux-battery-status", "termux-wifi-connectioninfo"]
    else:
        cmds = ["termux-device-info", "termux-battery-status"]
    for c in cmds:
        rc, out, err = run_cmd(c)
        print(f"--- {c} ---")
        print((out + err).strip() or "(no output)")
    if getattr(args, 'files', False):
        rc, out, err = run_cmd("ls /sdcard/Download/ | head -10")
        print("--- /sdcard/Download/ ---")
        print(out)
    return 0

def cmd_chat(args):
    from dac.config import load_config
    from dac.core.session import Session
    from dac.core.llm import complete, LLMError
    cfg = load_config()
    session = Session()
    session.add_user(args.prompt)
    messages = session.get_full_messages()
    try:
        text, usage = complete(cfg, messages)
    except LLMError as e:
        print(f"ERROR: {e}")
        return 1
    session.add_assistant(text)
    print(text)
    if usage:
        print(f"\n[tokens: {usage.get('total_tokens','?')}]")
    return 0

def cmd_doctor():
    import shutil, platform
    from dac.config import load_config, ensure_dirs, CONFIG_DIR, PROJECTS_DIR, SESSIONS_DIR, TASKS_DIR
    from dac import __version__
    checks = []
    ok = True

    # Python version
    py_ok = sys.version_info >= (3, 10)
    checks.append(('python >= 3.10', 'ok' if py_ok else 'FAIL', f'{platform.python_version()}'))
    ok &= py_ok

    # git
    git = shutil.which('git')
    checks.append(('git', 'ok' if git else 'WARN', git or 'not found'))

    # tmux
    tmux = shutil.which('tmux')
    checks.append(('tmux', 'ok' if tmux else 'WARN', tmux or 'not found'))

    # API key
    cfg = load_config()
    key = cfg.get('api_key', '')
    key_status = 'ok' if key else 'WARN'
    checks.append(('api_key', key_status, 'sk-***' + key[-4:] if len(key) > 4 else 'not set'))
    if not key:
        ok = False

    # Directories
    ensure_dirs()
    for d in [('config', CONFIG_DIR), ('projects', PROJECTS_DIR), ('sessions', SESSIONS_DIR), ('tasks', TASKS_DIR)]:
        checks.append((d[0] + '_dir', 'ok', str(d[1])))

    # termux
    for cmd in ['termux-info', 'termux-device-info']:
        t = shutil.which(cmd)
        if t:
            checks.append(('termux', 'ok', t))
            break
    else:
        checks.append(('termux', 'WARN', 'not detected'))

    print(f'DAC v{__version__} — Health Check')
    print()
    max_label = max(len(c[0]) for c in checks)
    for label, status, detail in checks:
        icon = '[92mok[0m' if status == 'ok' else ('[93mWARN[0m' if status == 'WARN' else '[91mFAIL[0m')
        print(f'  {icon}  {label:{max_label}}  {detail}')
    print()
    if ok and all(c[1] != 'FAIL' for c in checks):
        print('All checks passed.')
    else:
        print('Some checks failed or have warnings.')
    return 0
