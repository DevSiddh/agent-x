# mix_l2 — SQLAlchemy missing table + missing import
import sqlalchemy as sa

engine = sa.create_engine("sqlite:///:memory:")

# Table never created — OperationalError: no such table: orders
with engine.connect() as conn:
    result = conn.execute(sa.text("SELECT * FROM orders"))
    print(result.fetchall())
