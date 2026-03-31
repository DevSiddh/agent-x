# Template source: microsoft/qlib | Difficulty: hard | Niche: stocks
import pandas as pd

def compute_alpha_factors(df: pd.DataFrame) -> pd.DataFrame:
    # Core engine: factor computation pipeline
    df["momentum_20"] = df["close"].pct_change(20)
    df["reversal_5"] = -df["close"].pct_change(5)
    df["vol_20"] = df["close"].pct_change().rolling(20).std()
    df["turnover"] = df["volume"] / df["volume"].rolling(20).mean()
    # {{ADD_CUSTOM_ALPHA_FACTORS}}
    return df

def rank_stocks(df: pd.DataFrame, date: str) -> pd.DataFrame:
    snapshot = df.loc[date].copy()
    snapshot["composite_score"] = (
        snapshot["momentum_20"].rank(pct=True) * 0.4 +
        snapshot["reversal_5"].rank(pct=True) * 0.3 +
        snapshot["turnover"].rank(pct=True) * 0.3
    )
    return snapshot.sort_values("composite_score", ascending=False)
