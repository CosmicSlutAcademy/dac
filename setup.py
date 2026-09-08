"""DAC installer — install globally on the device."""
from setuptools import setup, find_packages

setup(
    name="dac",
    version="1.3.0",
    description="Decentralized Autonomous Coder — LLM-driven coding agent on Android",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "dac=dac.launcher:main",
            "dac-repl=dac.repl:main",
        ],
    },
)
