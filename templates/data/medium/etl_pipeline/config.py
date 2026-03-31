# Template source: prefecthq/prefect | Difficulty: medium | Niche: data
SOURCE_DB_URL = "{{SOURCE_DB_URL}}"  # e.g. postgresql://user:pass@host/db
TARGET_DB_URL = "{{TARGET_DB_URL}}"
S3_BUCKET = "{{S3_BUCKET}}"
S3_PREFIX = "{{S3_PREFIX}}"
SCHEDULE_CRON = "{{SCHEDULE_CRON}}"  # e.g. 0 2 * * *
BATCH_SIZE = {{BATCH_SIZE}}  # e.g. 10000
TRANSFORMS = ["{{TRANSFORM_1}}", "{{TRANSFORM_2}}"]
