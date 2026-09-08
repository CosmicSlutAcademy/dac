"""dac demo — scripted showcase of autonomous coding, no LLM required."""
import os
import time
from pathlib import Path

from dac import __version__
from dac.config import load_config
from dac.core.executor import write_file, run_script_python, run_script_bash


DEMO_FILES = {
    "fib.py": (
        "def fib(n):\n"
        "    a, b = 0, 1\n"
        "    for _ in range(n):\n"
        "        a, b = b, a + b\n"
        "    return a\n"
        "\n"
        "if __name__ == '__main__':\n"
        "    print('Fibonacci(20) =', fib(20))\n"
    ),
    "test_fib.py": (
        "import fib\n"
        "assert fib.fib(0) == 0\n"
        "assert fib.fib(10) == 55\n"
        "assert fib.fib(20) == 6765\n"
        "print('All tests passed.')\n"
    ),
}


def run_demo(project_dir=None):
    cfg = load_config()
    base = Path(project_dir or os.path.expanduser(cfg.get("projects_dir", "~/.dac/projects")))
    proj = base / "demo"
    proj.mkdir(parents=True, exist_ok=True)

    print("=" * 56)
    print(f"  DAC v{__version__} — Autonomous Coder on your phone")
    print(f"  Project: {proj}")
    print("=" * 56)

    # 1. Write files
    t0 = time.time()
    print("\n[1/3] Writing project files...")
    for name, content in DEMO_FILES.items():
        p = write_file(proj / name, content)
        print(f"       ✓ {p}")

    # 2. Run the code
    print("\n[2/3] Executing code...")
    rc, out, dt = run_script_python("import fib; print('Fibonacci(15) =', fib.fib(15))",
                                    cwd=proj)
    print(f"       → {out.strip()}  ({dt}s)")

    # 3. Run the tests
    print("\n[3/3] Running tests...")
    rc2, out2, dt2 = run_script_python("import test_fib", cwd=proj)
    print(f"       → {out2.strip()}  ({dt2}s)")

    elapsed = time.time() - t0
    print("\n" + "-" * 56)
    print(f"  Demo complete in {elapsed:.2f}s — all code ran on-device.")
    print(f"  Files: {proj}")
    print("-" * 56)
    return 0 if (rc == 0 and rc2 == 0) else 1


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="dac demo", description="Run the on-device demo")
    p.add_argument("--project-dir", help="Where to write the demo project")
    args = p.parse_args(argv)
    return run_demo(args.project_dir)


if __name__ == "__main__":
    raise SystemExit(main())
