# BuildError Level 3 — Docker image build fails with missing dependency in image
# Classifier: BuildError | docker_failure | affected_file: Dockerfile
# Fix: correct base image + add missing apt-get install step

import subprocess

result = subprocess.run(
    ["docker", "build", "--no-cache", "-t", "myapp-prod:latest", "-f", "Dockerfile.prod", "."],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    print(result.stderr)
    raise RuntimeError(f"failed to build image: {result.stderr[:300]}")

print("Production image built successfully")
