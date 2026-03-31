# Template source: pathwaycom/pathway | Difficulty: hard | Niche: data
import pathway as pw
from config import KAFKA_BROKERS, KAFKA_TOPIC_INPUT, KAFKA_TOPIC_OUTPUT, WINDOW_SIZE_SECONDS

def build_pipeline():
    # Core engine: Pathway streaming pipeline
    rdkafka_settings = {
        "bootstrap.servers": ",".join(KAFKA_BROKERS),
        "group.id": "{{CONSUMER_GROUP}}",
        "auto.offset.reset": "latest",
    }
    input_table = pw.io.kafka.read(
        rdkafka_settings,
        topic=KAFKA_TOPIC_INPUT,
        format="json",
        schema=pw.schema_from_dict({
            "timestamp": pw.column_definition(dtype=float),
            "value": pw.column_definition(dtype=float),
            # {{ADD_SCHEMA_FIELDS}}
        })
    )
    # Windowed aggregation
    windowed = input_table.windowby(
        input_table.timestamp,
        window=pw.temporal.sliding(duration=WINDOW_SIZE_SECONDS, hop=WINDOW_SIZE_SECONDS // 2)
    ).reduce(
        avg_value=pw.reducers.mean(input_table.value),
        count=pw.reducers.count(),
        # {{ADD_MORE_AGGREGATIONS}}
    )
    pw.io.kafka.write(windowed, rdkafka_settings, topic=KAFKA_TOPIC_OUTPUT, format="json")
    return windowed

if __name__ == "__main__":
    build_pipeline()
    pw.run()
