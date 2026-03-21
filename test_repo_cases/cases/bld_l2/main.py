# BuildError Level 2 — pip build isolation failure
# Classifier: BuildError | build_isolation | affected_file: main.py
# Fix: add --no-build-isolation flag or fix setup.cfg

import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pip", "install", ".",
     "--no-build-isolation", "--quiet"],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(result.stderr)
    raise RuntimeError(f"build isolation error during install: {result.stderr[:200]}")

print("Package installed successfully")
