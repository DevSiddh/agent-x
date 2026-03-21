# BuildError Level 1 — Docker build fails (simulated)
# Classifier: BuildError | docker_failure | affected_file: main.py
# Fix: correct the base image name in Dockerfile

import subprocess
import sys

result = subprocess.run(
    ["docker", "build", "-t", "myapp:latest", "."],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(result.stderr)
    raise RuntimeError(f"docker build failed: {result.stderr[:200]}")

print("Build successful")
