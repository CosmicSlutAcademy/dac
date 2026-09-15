"""gcia-agent — forced-command SSH handler for auth-granted remote access.

Installed as the `command=` in a granted peer's authorized_keys line. Reads the
original command from SSH_ORIGINAL_COMMAND, validates it against the allowlist,
executes it via GCIA, and writes a journal entry. The SSH_ORIGINAL_COMMAND value
is one token (no spaces) accepted by the server's own allowlist.
"""

import datetime
import json
import os
import subprocess
import sys

from gcia.remote import ALLOWED

JOURNAL = os.path.expanduser("~/.gcia/agent-journal.jsonl")


def _log(user, command, rc):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    entry = {
        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "user": user,
        "command": command,
        "rc": rc,
    }
    with open(JOURNAL, "a") as f:
        f.write(json.dumps(entry) + "\n")


def handle(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    orig = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    args = argv or orig.split()
    if not args:
        print("usage: gcia-agent <audit|status|brief|recon|scan>")
        return 1
    cmd = args[0]
    if cmd not in ALLOWED:
        print(f"denied: {cmd!r} is not in the GCIA allowlist")
        _log(os.environ.get("USER", "?"), cmd, 403)
        return 403
    extra = args[1:]
    if extra:
        target = extra[0]
        if not target.replace(".", "").replace("-", "").isalnum():
            print(f"denied: suspicious extra argument {target!r}")
            _log(os.environ.get("USER", "?"), cmd, 403)
            return 403
    args = ["gcia", cmd] + extra
    r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    _log(os.environ.get("USER", "?"), cmd, r.returncode)
    return r.returncode


def main():
    sys.exit(handle())


if __name__ == "__main__":
    main()
