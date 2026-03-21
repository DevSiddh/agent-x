# ConfigError Level 3 — Malformed YAML config + cascading failure
# Classifier: ConfigError | malformed_yaml | affected_file: main.py
# Fix: fix YAML syntax (close the bracket on line 6)

import yaml

CONFIG = """
database:
  host: localhost
  port: 5432
  tables: [users, orders, products
credentials:
  user: admin
  password: secret
"""

try:
    config = yaml.safe_load(CONFIG)
    print(f"DB host: {config['database']['host']}")
except yaml.YAMLError as exc:
    raise yaml.YAMLError(f"yaml error: malformed YAML in config.yaml — {exc}")
