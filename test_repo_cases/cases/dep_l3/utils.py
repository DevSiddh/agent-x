# DependencyError Level 3 — Import chain across files
# utils.py imports cryptography which is not installed
# Classifier sees: ModuleNotFoundError in utils.py (not main.py)

from cryptography.fernet import Fernet


def encrypt_token(data: str) -> bytes:
    key = Fernet.generate_key()
    f = Fernet(key)
    return f.encrypt(data.encode())
