# Mixed Level 1 — Dependency + missing config key (two errors, first wins)
# Classifier: DependencyError | ModuleNotFoundError | affected_file: main.py
# Fix: add redis to requirements.txt AND add "host" key to config

import redis

config = {"port": 6379}  # missing "host" key

client = redis.Redis(host=config["host"], port=config["port"])
client.ping()
print("Redis connected")
