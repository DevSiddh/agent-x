# Mixed Level 2 — Missing package + no such table (two-stage failure)
# Classifier: DependencyError (sqlalchemy missing) OR ConfigError (no such table)
# Fix: add sqlalchemy to requirements.txt AND create orders table migration

from db import engine

print(f"Engine: {engine}")
