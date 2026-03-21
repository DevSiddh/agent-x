# EnvironmentError Level 3 — Config class with 3 missing env vars
# Classifier: EnvironmentError | missing_env_var | affected_file: config.py
# Fix: add DATABASE_URL, SECRET_KEY, EXTERNAL_API_URL to workflow env

from config import AppConfig

if __name__ == "__main__":
    cfg = AppConfig()
    cfg.validate()
    print(f"Connected to {cfg.db_url}")
