# Template source: pandas-pattern | Difficulty: easy | Niche: data
import pandas as pd
from config import INPUT_PATH, OUTPUT_PATH, TRANSFORMS, SCHEMA

def load(path: str) -> pd.DataFrame:
    return pd.read_csv(path)

def transform(df: pd.DataFrame) -> pd.DataFrame:
    # Core engine: apply transforms in sequence
    for t in TRANSFORMS:
        if t == "drop_nulls":
            df = df.dropna()
        elif t == "normalize_dates":
            for col in df.select_dtypes(include="object").columns:
                try:
                    df[col] = pd.to_datetime(df[col])
                except Exception:
                    pass
        # {{ADD_CUSTOM_TRANSFORMS}}
    return df

def validate(df: pd.DataFrame) -> pd.DataFrame:
    for col, dtype in SCHEMA.items():
        if col in df.columns:
            df[col] = df[col].astype(dtype)
    return df

def save(df: pd.DataFrame, path: str):
    df.to_csv(path, index=False)

def run():
    df = load(INPUT_PATH)
    df = transform(df)
    df = validate(df)
    save(df, OUTPUT_PATH)
    print(f"Done: {len(df)} rows written to {OUTPUT_PATH}")
