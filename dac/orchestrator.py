"""Orchestrator — runs DAC tasks, chains actions, manages automations."""
import json
import os
import time
import subprocess
from pathlib import Path
from dac.config import load_config, CONFIG_DIR
from dac.core.executor import run_cmd, write_file, run_script_python, run_script_bash
from dac.core.llm import complete, extract_code_blocks, LLMError

TASKS_DIR = CONFIG_DIR / "tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

def create_task(prompt, task_name=None):
    """Register a new task to be executed."""
    task_name = task_name or f"task_{int(time.time())}"
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
    print(f"Task created: {task_name}")
    return task

def execute_task(task_name, cfg=None, project_dir=None):
    """Execute a registered task."""
    cfg = cfg or load_config()
    project_dir = project_dir or os.path.expanduser(cfg.get("projects_dir", "~/.dac/projects"))
    task_file = TASKS_DIR / f"{task_name}.json"
    if not task_file.exists():
        print(f"Task not found: {task_name}")
        return None
    with open(task_file) as f:
        task = json.load(f)
    if task.get("status") == "done":
        print(f"Task already completed: {task_name}")
        return task
    prompt = task["prompt"]
    print(f"[dac] Executing: {task_name}")
    print(f"[dac] Prompt: {prompt[:200]}")
    # Generate plan + actions via LLM
    messages = [
        {"role": "system", "content": "You are an autonomous coding agent. Given a task, provide concrete actions."},
        {"role": "user", "content": (
            f"TASK: {prompt}\n\n"
            f"Directory: {project_dir}\n"
            "Return JSON:\n"
            '{"steps": ["..."], "files": [{"path":"...", "content":"..."}], "commands": ["..."], "summary":"..."}'
        )},
    ]
    try:
        text, usage = complete(cfg, messages)
    except LLMError as e:
        task["status"] = "failed"
        task["error"] = str(e)
        with open(task_file, "w") as f:
            json.dump(task, f, indent=2)
        return task
    # Parse plan
    try:
        from dac.core.autonomous import parse_json
        plan = parse_json(text)
    except Exception:
        plan = {"steps": [], "files": [], "commands": [], "summary": text}
    results = {"steps": plan.get("steps", []), "files_written": [], "commands_run": [], "errors": []}
    # Write files
    for f in plan.get("files", []):
        path = f.get("path", "")
        content = f.get("content", "")
        if not path or not content:
            continue
        full = path if os.path.isabs(path) else os.path.join(project_dir, path)
        try:
            write_file(full, content)
            results["files_written"].append(full)
        except Exception as e:
            results["errors"].append(f"Write failed {path}: {e}")
    # Run commands
    for cmd in plan.get("commands", []):
        try:
            rc, out, err = run_cmd(cmd, cwd=project_dir)
            results["commands_run"].append({"cmd": cmd, "rc": rc, "output": (out + err)[:500]})
            if rc != 0:
                results["errors"].append(f"Command failed ({rc}): {cmd}")
        except Exception as e:
            results["errors"].append(f"Command error {cmd}: {e}")
    task["status"] = "done" if not results["errors"] else "partial"
    task["results"] = results
    task["completed"] = int(time.time())
    with open(task_file, "w") as f:
        json.dump(task, f, indent=2)
    return task

def list_tasks():
    tasks = []
    for f in sorted(TASKS_DIR.glob("*.json"), reverse=True):
        with open(f) as fh:
            tasks.append(json.load(fh))
    return tasks

def auto_watch(poll_interval=5):
    """Watch for new task files and execute them automatically."""
    print(f"[dac] Watching for tasks in {TASKS_DIR} (poll={poll_interval}s)")
    seen = set()
    while True:
        current = set(f.name for f in TASKS_DIR.glob("*.json"))
        new_tasks = current - seen
        for fname in new_tasks:
            task_name = fname.replace(".json", "")
            print(f"[dac] New task detected: {task_name}")
            try:
                execute_task(task_name)
            except Exception as e:
                print(f"[dac] Error executing {task_name}: {e}")
        seen = current
        time.sleep(poll_interval)
