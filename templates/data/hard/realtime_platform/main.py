# Template source: pathwaycom/pathway | Difficulty: hard | Niche: data
import threading
from stream import build_pipeline
import pathway as pw
# {{IMPORT_METRICS_SERVER}}

if __name__ == "__main__":
    # {{START_PROMETHEUS_METRICS_SERVER}}
    build_pipeline()
    pw.run(monitoring_level=pw.MonitoringLevel.ALL)
