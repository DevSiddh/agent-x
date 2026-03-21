# ConfigError Level 2 — SQLite query on nonexistent table
# Classifier: ConfigError | no_such_table | affected_file: main.py
# Fix: CREATE TABLE users before querying (add migration)

import sqlite3

conn = sqlite3.connect(":memory:")
# Table 'users' was never created — migration missing
cursor = conn.execute("SELECT id, name, email FROM users WHERE active=1")
rows = cursor.fetchall()
print(f"Found {len(rows)} active users")
conn.close()
