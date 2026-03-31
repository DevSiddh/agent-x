# Template source: prefecthq/prefect | Difficulty: medium | Niche: data
from prefect import flow, task
import pandas as pd
import sqlalchemy as sa
from config import SOURCE_DB_URL, TARGET_DB_URL, BATCH_SIZE, TRANSFORMS

@task(retries=3, retry_delay_seconds=10)
def extract(query: str) -> pd.DataFrame:
    engine = sa.create_engine(SOURCE_DB_URL)
    return pd.read_sql(query, engine, chunksize=BATCH_SIZE)

@task
def transform(df: pd.DataFrame) -> pd.DataFrame:
    # Core engine: apply transforms in sequence
    for t in TRANSFORMS:
        if t == "drop_nulls":
            df = df.dropna()
        elif t == "deduplicate":
            df = df.drop_duplicates()
        elif t == "normalize_dates":
            for col in df.select_dtypes(include="object").columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                except Exception:
                    pass
        # {{ADD_CUSTOM_TRANSFORMS}}
    return df

@task(retries=2)
def load(df: pd.DataFrame, table: str):
    engine = sa.create_engine(TARGET_DB_URL)
    df.to_sql(table, engine, if_exists="append", index=False)
    print(f"Loaded {len(df)} rows into {table}")

@flow(name="{{FLOW_NAME}}")
def etl_flow(query: str = "{{DEFAULT_QUERY}}", table: str = "{{TARGET_TABLE}}"):
    raw = extract(query)
    clean = transform(raw)
    load(clean, table)

if __name__ == "__main__":
    etl_flow()
