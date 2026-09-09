"""Personal assistant — speak, notify, remind. Zero dependencies (Termux API)."""
import re
import subprocess
import threading
import time

from dac.config import load_config
from dac.core.llm import complete, LLMError
from dac.core.session import Session

REMINDER_RE = re.compile(r"^remind\s+(.+?)\s+in\s+(\d+)\s*(s|m|h)?$", re.IGNORECASE)


def termux_binary(name):
    import shutil
    return shutil.which(name)


def speak(text):
    """Speak via Termux TTS if available, else just print."""
    print(text)
    tts = termux_binary("termux-tts-speak")
    if tts:
        subprocess.run([tts, text], capture_output=True)
    return tts is not None


def notify(title, content, notif_id="dac_assistant"):
    n = termux_binary("termux-notification")
    if n:
        subprocess.run([n, "--title", title, "-c", content, "--id", notif_id],
                       capture_output=True)
    return n is not None


def parse_delay(spec):
    """'30m' -> 1800, '2h' -> 7200, '90s' -> 90, '15' -> 900 (minutes)."""
    m = re.match(r"^(\d+)\s*(s|m|h)?$", str(spec).strip().lower())
    if not m:
        raise ValueError(f"Bad delay: {spec!r} (use e.g. 30m, 2h, 90s)")
    n = int(m.group(1))
    unit = m.group(2) or "m"
    return n * {"s": 1, "m": 60, "h": 3600}[unit]


def schedule_reminder(text, delay):
    def fire():
        time.sleep(delay)
        speak(f"Reminder: {text}")
        notify("DAC Reminder", text)
    t = threading.Thread(target=fire, daemon=True)
    t.start()
    return t


def assistant_say(text):
    spoke = speak(text)
    notify("DAC Assistant", text[:300])
    return spoke


def assistant_remind(text, delay_spec):
    delay = parse_delay(delay_spec)
    print(f"Reminder set for {delay_spec} ({delay}s): {text}")
    schedule_reminder(text, delay)
    notify("DAC Assistant", f"Reminder scheduled in {delay_spec}")
    return delay


def assistant_talk(once=None):
    """Interactive loop. Voice out, convenience in."""
    cfg = load_config()
    session = Session(session_id="assistant")
    print("DAC Assistant — Ctrl+C to exit")
    print("Commands: remind <text> in <30m|2h|90s> | /q to quit")
    speak("DAC assistant online.")

    while once is not None:
        q = once
        once = None
        try:
            _handle_query(cfg, session, q)
        except (KeyboardInterrupt, EOFError):
            break

    while True:
        try:
            q = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            break
        if not q:
            continue
        if q.lower() in ("/q", "/quit", "/exit", "exit", "quit"):
            print("Bye.")
            break
        try:
            _handle_query(cfg, session, q)
        except (KeyboardInterrupt, EOFError):
            break


def _handle_query(cfg, session, q):
    m = REMINDER_RE.match(q)
    if m:
        assistant_remind(m.group(1), f'{m.group(2)}{m.group(3) or "m"}')
        return
    session.add_user(q)
    try:
        from dac.core.session import SYSTEM_PROMPT  # noqa: F401  (assistant persona)
        text, usage = complete(cfg, session.get_full_messages())
        session.add_assistant(text)
        spoke = speak(text)
        notify("DAC Assistant", text[:300])
        if usage:
            print(f"  [tokens: {usage.get('total_tokens', '?')}]")
        return spoke
    except (LLMError, ImportError) as e:
        print(f"Error: {e}")
        return None


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="dac assistant", description="Personal assistant")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--say", help="Speak one message and exit")
    g.add_argument("--remind", help="Schedule a reminder")
    g.add_argument("--in", dest="in_", help="Delay for --remind (30m, 2h, 90s)")
    args = p.parse_args(argv)

    if args.say:
        return assistant_say(args.say)
    if args.remind:
        return assistant_remind(args.remind, args.in_ or "30m")
    assistant_talk()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
