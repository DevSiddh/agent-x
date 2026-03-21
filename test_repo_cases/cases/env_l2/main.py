# EnvironmentError Level 2 — Circular import between module_a and module_b
# Classifier: EnvironmentError | stale_pycache | affected_file: module_a.py
# Fix: restructure imports to break circular dependency

from module_a import combined

if __name__ == "__main__":
    print(combined())
