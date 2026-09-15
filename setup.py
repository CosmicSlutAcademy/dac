"""DAC installer — install globally on the device."""
from setuptools import setup, find_packages

setup(
    name="dac",
    version="1.3.5",
    description="DAC + GCIA — autonomous coding & ethical investigation CLIs for Android",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "dac=dac.launcher:main",
            "dac-repl=dac.repl:main",
            "gcia=gcia.launcher:main",
            "gciau=gcia.launcher:gciau_main",
        ],
    },
)
