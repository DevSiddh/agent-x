# EnvironmentError Level 1 — Single missing env var
# Classifier: EnvironmentError | missing_env_var | affected_file: main.py
# Fix: add API_KEY to workflow env section (1 line)

import os

api_key = os.environ.get("API_KEY")
if not api_key:
    raise EnvironmentError("environment variable API_KEY not set")

print(f"Connected with key: {api_key[:4]}****")
