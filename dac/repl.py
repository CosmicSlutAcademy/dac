"""Interactive REPL — the core interactive loop for DAC."""
import sys
import time
import os

from dac.config import load_config
from dac.core.session import Session
from dac.core.llm import complete, LLMError, extract_code_blocks_with_lang
from dac.core.autonomous import should_execute, _open_generation
from dac.core.executor import execute_block, run_cmd

PROMPT = "\033[96m≈dac\033[0m \033[90m>\033[0m "

ACTION_KEYWORDS = (
    "build", "create", "automate", "generate", "make ", "make a", "make an",
    "install ", "set up", "setup", "develop", "scaffold", "write a script",
    "write script", "write a tool", "new script",
)

ACTION_WRAP = "\n[ACTION REQUEST: respond ONLY with fenced code blocks (```python or ```bash). End with exactly AUTONOMY_READY. No prose, no numbered lists, no explanation.]\n"


def _is_action_request(text):
    lowered = text.lower()
    return any(kw in lowered for kw in ACTION_KEYWORDS)


def _action_messages(messages, user_input):
    """Append the action-mode wrapper to the last user message."""
    if not _is_action_request(user_input):
        return messages
    out = list(messages)
    for i in range(len(out) - 1, -1, -1):
        if out[i]["role"] == "user":
            out[i] = dict(out[i], content=out[i]["content"] + ACTION_WRAP)
            break
    return out


def _maybe_run_direct(user_input):
    """Run `dac ...` / `!...` lines directly as shell commands. Returns True if handled."""
    if not (user_input.startswith("dac ") or user_input.startswith("!")):
        return False
    cmd = user_input[1:].strip() if user_input.startswith("!") else user_input
    print(f"\033[90m$ {cmd}\033[0m")
    rc, out, err = run_cmd(cmd)
    if out.strip():
        print(out.rstrip())
    if err.strip():
        print(err.rstrip())
    if rc != 0:
        print(f"\033[91m(exit {rc})\033[0m")
    return True


def repl(session=None):
    cfg = load_config()
    session = session or Session()
    print("╔══════════════════════════════════════════════════════╗")
    print("║  DAC — Decentralized Autonomous Coder              ║")
    print("║  Session:", session.session_id.ljust(41), "║")
    print("║  Ctrl+C to exit, /help for commands                ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    while True:
        try:
            user_input = input(PROMPT).strip()
        except (KeyboardInterrupt, EOFError):
            print("\nSession saved. Goodbye.")
            break
        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "/q"):
            print("Session saved.")
            break
        if user_input.lower() == "/clear":
            session.clear()
            print("Context cleared.")
            continue
        if user_input.lower() == "/history":
            for m in session.messages:
                role = m["role"]
                content = m["content"][:200]
                print(f"  [{role}] {content}")
            continue
        if user_input.lower() == "/help":
            print("/clear     - reset conversation")
            print("/history   - show messages")
            print("/new       - start new session")
            print("/device    - show device info")
            print("/exit      - quit")
            continue
        if user_input.lower() == "/new":
            session = Session()
            print(f"New session: {session.session_id}")
            continue
        if user_input.lower() == "/device":
            for c in ["termux-device-info", "termux-battery-status"]:
                _, out, _ = run_cmd(c)
                print(out.strip())
            continue

        # Direct execution: `dac ...` runs DAC CLI, `!...` runs any shell command.
        if _maybe_run_direct(user_input):
            continue

        session.add_user(user_input)
        messages = _action_messages(session.get_full_messages(), user_input)

        try:
            if _is_action_request(user_input):
                print("\033[90m[action mode]\033[0m ", end="", flush=True)
            print("\033[90mthinking...\033[0m", end="", flush=True)
            t0 = time.time()
            text, usage = complete(cfg, messages)
            elapsed = time.time() - t0
            sys.stdout.write("\r" + " " * 20 + "\r")
            print(text)
            session.add_assistant(text)
            tok = usage.get("total_tokens", "?")
            print(f"\033[90m  [{elapsed:.1f}s | {tok} tokens]\033[0m\n")
            
            # Check for AUTONOMY_READY marker and auto-execute
            if should_execute(text):
                print("\033[90mAutonomy triggered — executing...\033[0m")
                project_dir = os.path.expanduser(cfg.get("projects_dir", "~/.dac/projects"))
                results = _execute_code_blocks(text, project_dir, cfg, session)
                if results.get("files_written"):
                    print("\nFiles:")
                    for f in results["files_written"]:
                        print(f"  ✓ {f}")
                if results.get("commands_run"):
                    print("\nOutput:")
                    for c in results["commands_run"]:
                        print(c.get("output", "")[:500])
                if results.get("errors"):
                    print("\nErrors:")
                    for e in results["errors"]:
                        print(f"  ✗ {e}")
        except LLMError as e:
            print(f"\n  \033[91mError:\033[0m {e}\n")


def _execute_code_blocks(text, project_dir, cfg, session):
    """Extract code blocks from LLM text and execute them."""
    from dac.core.llm import complete
    
    results = {"files_written": [], "commands_run": [], "errors": [], "text": text}
    blocks = extract_code_blocks_with_lang(text)
    
    if blocks:
        for lang, block in blocks:
            ext = "py" if lang == "python" else "sh"
            p = os.path.join(project_dir, f"auto_{int(time.time())}.{ext}")
            try:
                from dac.core.executor import write_file
                write_file(p, block)
                results["files_written"].append(p)
                rc, out, _ = execute_block(block, cwd=project_dir, lang=lang)
                results["commands_run"].append({"cmd": f"python3 {p}" if lang == "python" else f"bash {p}", "rc": rc, "output": out[:500]})
                if rc != 0:
                    results["errors"].append(f"Execution failed ({rc}): {p}")
            except Exception as e:
                results["errors"].append(str(e))
    return results

def main():
    repl()
