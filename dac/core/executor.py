"""Command / script executor with logging."""
import os
import shlex
import subprocess
import time
import json
from pathlib import Path

class ExecError(Exception):
    def __init__(self, cmd, returncode, stdout, stderr):
        self.cmd = cmd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        super().__init__(f"Command failed ({returncode}): {cmd[:200]}")

def run_cmd(cmd, cwd=None, timeout=60, capture=True):
    """Run a shell command. Returns (returncode, stdout, stderr)."""
    proc = subprocess.run(
        cmd, shell=True, cwd=cwd, capture_output=capture, text=True, timeout=timeout
    )
    return proc.returncode, proc.stdout, proc.stderr

def run_script_python(code, cwd=None, timeout=60):
    """Execute a Python code block. Returns (returncode, combined_output)."""
    start = time.time()
    proc = subprocess.run(
        ["python3", "-c", code],
        cwd=cwd or os.getcwd(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    combined = proc.stdout + (proc.stderr if proc.stderr else "")
    return proc.returncode, combined, round(time.time() - start, 2)

def run_script_bash(code, cwd=None, timeout=60):
    start = time.time()
    proc = subprocess.run(
        ["bash", "-c", code],
        cwd=cwd or os.getcwd(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    combined = proc.stdout + (proc.stderr if proc.stderr else "")
    return proc.returncode, combined, round(time.time() - start, 2)

def execute_block(block, cwd=None, timeout=60, lang="python"):
    if lang == "python":
        return run_script_python(block, cwd=cwd, timeout=timeout)
    elif lang == "bash":
        return run_script_bash(block, cwd=cwd, timeout=timeout)
    else:
        return run_script_bash(block, cwd=cwd, timeout=timeout)

def write_file(path, content):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return str(p)
