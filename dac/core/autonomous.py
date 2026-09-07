"""Autonomy engine — interprets LLM code blocks and executes them on demand."""
import re
import json
import os
import time
from pathlib import Path

from dac.core.llm import extract_code_blocks, parse_json
from dac.core.executor import execute_block, write_file, run_cmd
from dac.config import load_config

AUTONOMY_MARKER = "AUTONOMY_READY"

class AutonomousError(Exception):
    pass

def should_execute(text):
    """Check if the assistant output declares an action should be auto-executed."""
    return AUTONOMY_MARKER in text.upper()

def plan_and_execute(prompt, project_dir, cfg, session, auto_confirm=False):
    """Given a prompt, generate a plan via LLM, then execute or present to user."""
    from dac.core.llm import complete

    # First pass: planning
    plan_messages = session.get_full_messages() + [
        {
            "role": "user",
            "content": (
                f"TASK: {prompt}\n\n"
                f"Project directory: {project_dir}\n"
                "Please provide a concrete execution plan as a JSON object with format:\n"
                '{"plan": ["step1", "step2", ...], "files": [{"path": "...", "content": "..."}], '
                '"commands": ["cmd1", "cmd2"]}\n'
                "If the task requires creating code, put the full code in files[].\n"
                'If it requires running things, put the shell commands in commands[].'
            ),
        }
    ]
    try:
        plan_text, _ = complete(cfg, plan_messages)
        plan = parse_json(plan_text)
    except Exception as e:
        # Fall back to open-ended generation
        return _open_generation(prompt, project_dir, cfg, session)

    results = {"plan": plan.get("plan", []), "files_written": [], "commands_run": [], "errors": []}

    # Write files
    for f in plan.get("files", []):
        path = f.get("path", "")
        content = f.get("content", "")
        if not path:
            continue
        full = path if os.path.isabs(path) else os.path.join(project_dir, path)
        try:
            p = write_file(full, content)
            results["files_written"].append(p)
        except Exception as e:
            results["errors"].append(f"File write failed {path}: {e}")

    # Run commands
    for cmd in plan.get("commands", []):
        try:
            rc, out, err = run_cmd(cmd, cwd=project_dir)
            results["commands_run"].append({"cmd": cmd, "rc": rc, "output": (out + err)[:500]})
            if rc != 0:
                results["errors"].append(f"Command failed ({rc}): {cmd}")
        except Exception as e:
            results["errors"].append(f"Command error {cmd}: {e}")

    return results

def _open_generation(prompt, project_dir, cfg, session):
    """Fallback: send the prompt to the LLM, show output, and look for code blocks."""
    from dac.core.llm import complete

    messages = session.get_full_messages() + [{"role": "user", "content": prompt}]
    text, _ = complete(cfg, messages)

    results = {"files_written": [], "commands_run": [], "errors": [], "text": text}
    blocks = extract_code_blocks(text)

    if blocks:
        # Heuristic: python blocks with file-writing intent
        for i, block in enumerate(blocks):
            # If it's a python script, save it
            p = os.path.join(project_dir, f"generated_{int(time.time())}_{i}.py")
            try:
                write_file(p, block)
                results["files_written"].append(p)
            except Exception as e:
                results["errors"].append(str(e))
    return results

def verify_success(results, expected=None):
    """Check if execution succeeded and deta new errors."""
    if results.get("errors"):
        return False
    if expected and not os.path.exists(expected):
        return False
    return True
