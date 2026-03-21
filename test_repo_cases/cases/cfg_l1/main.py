# ConfigError Level 1 — Missing key in config dict
# Classifier: ConfigError | missing_key | affected_file: main.py
# Fix: add "database" key to config dict (1 line)

config = {
    "host": "localhost",
    "port": 5432,
    # "database" key intentionally missing
}

db_name = config["database"]
print(f"Connecting to {config['host']}:{config['port']}/{db_name}")
