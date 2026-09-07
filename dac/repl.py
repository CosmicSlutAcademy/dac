"""Interactive REPL — the core interactive loop for DAC."""
import sys
import time
from dac.config import load_config
from dac.core.session import Session
from dac.core.llm import complete, LLMError

PROMPT = "\033[96m≈dac\033[0m \033[90m>\033[0m "

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
            from dac.core.executor import run_cmd
            for c in ["termux-device-info", "termux-battery-status"]:
                _, out, _ = run_cmd(c)
                print(out.strip())
            continue

        session.add_user(user_input)
        messages = session.get_full_messages()

        try:
            print("\033[90mthinking...\033[0m", end="", flush=True)
            t0 = time.time()
            text, usage = complete(cfg, messages)
            elapsed = time.time() - t0
            sys.stdout.write("\r" + " " * 20 + "\r")
            print(text)
            session.add_assistant(text)
            tok = usage.get("total_tokens", "?")
            print(f"\033[90m  [{elapsed:.1f}s | {tok} tokens]\033[0m\n")
        except LLMError as e:
            print(f"\n  \033[91mError:\033[0m {e}\n")

def main():
    repl()
