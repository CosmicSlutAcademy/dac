# NEXTGENWORLD — DAC System

## Decentralized Autonomous Coder (DAC)

Your phone is now a self-sufficient AI coding workstation. Every prompt you send generates, manages, and executes code autonomously.

---

### Quick Start

```bash
# Initialize (set your OpenAI API key)
dac init --api-key sk-your-key-here

# Start the daemon (background task runner)
dac daemon start

# One-shot: send a prompt, it auto-generates + executes
dac quick "create a Python script that tracks BTC price every hour and saves to CSV"

# Interactive REPL (chat mode with context)
dac repl

# Check device status
dac device

# View all projects
dac project --list
```

---

### Commands Reference

| Command | Description |
|---------|-------------|
| `dac init` | Initialize + set API key |
| `dac quick "prompt"` | One-shot autonomous execution |
| `dac repl` | Interactive REPL session |
| `dac chat "prompt"` | One-shot chat (no execution) |
| `dac trigger "prompt"` | Queue a task for the daemon |
| `dac daemon start/stop/status` | Background task runner |
| `dac tasks --list` | View all tasks |
| `dac run "code" --language python` | Direct code execution |
| `dac device` | Phone info (model, battery, WiFi) |
| `dac project --list/--new/--info` | Project management |
| `dac config --show/--set key=val` | Configuration |

---

### Architecture

```
/dac/
  __init__.py          — Package root
  __main__.py          — python -m dac entry
  launcher.py          — Master CLI orchestrator
  cli.py               — Command implementations
  repl.py              — Interactive REPL
  config.py            — Config management
  daemon.py            — Background task runner (tmux)
  orchestrator.py      — Task queue + execution engine
  core/
    llm.py             — OpenAI API integration (zero dependencies)
    executor.py        — Code/command execution engine
    session.py         — Conversation memory + context
    autonomous.py      — Plan → execute autonomy engine
```

### Data

- Config: `~/.dac/config.json`
- Projects: `~/.dac/projects/`
- Sessions: `~/.dac/sessions/`
- Tasks: `~/.dac/tasks/`
- Logs: `~/.dac/dac.log`

---

### How It Works

1. **You send a prompt** → `dac quick "build a telegram bot"`
2. **LLM generates a plan** → JSON with steps, files, commands
3. **DAC writes files** → Creates project directory with code
4. **DAC executes commands** → Runs the code on your device
5. **You get the result** → Files created, code running

Everything runs natively on your Pixel 10 Pro XL — no cloud runtime needed.
