# Mixed Level 3 — Pydantic + env var + missing table (structural — may escalate)
# Classifier: RuntimeError | pydantic_namespace (first match wins)
# This may hit structural escalation (3 interacting issues, patch > 15 lines)

import os
import sqlite3
from pydantic import BaseModel


class ModelMetrics(BaseModel):
    model_version: str     # conflicts with protected namespace "model_"
    model_accuracy: float  # conflicts with protected namespace "model_"
    model_loss: float      # conflicts with protected namespace "model_"


def save_metrics(metrics: ModelMetrics) -> None:
    db_path = os.environ.get("METRICS_DB")
    if not db_path:
        raise EnvironmentError("environment variable METRICS_DB not set")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO model_runs VALUES (?, ?, ?)",
                 (metrics.model_version, metrics.model_accuracy, metrics.model_loss))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    m = ModelMetrics(model_version="v1", model_accuracy=0.95, model_loss=0.05)
    save_metrics(m)
    print("Saved")
