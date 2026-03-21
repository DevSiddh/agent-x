# DependencyError Level 3 — Chained import failure across modules
# Classifier: DependencyError | ModuleNotFoundError | affected_file: utils.py
# Fix: add cryptography to requirements.txt + fix utils.py import path

from utils import encrypt_token

if __name__ == "__main__":
    token = encrypt_token("secret-api-key")
    print(f"Encrypted: {token}")
