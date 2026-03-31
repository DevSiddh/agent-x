# Template source: CryptoSignal/Crypto-Signal | Difficulty: easy | Niche: crypto
import ccxt
import pandas as pd
import ta
from config import EXCHANGE, PAIRS, INTERVAL, RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD

def fetch_ohlcv(pair: str) -> pd.DataFrame:
    exchange = getattr(ccxt, EXCHANGE)()
    ohlcv = exchange.fetch_ohlcv(pair, INTERVAL, limit=100)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df

def compute_signals(df: pd.DataFrame) -> dict:
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=RSI_PERIOD).rsi()
    df["macd"] = ta.trend.MACD(df["close"]).macd()
    latest = df.iloc[-1]
    return {
        "rsi": latest["rsi"],
        "macd": latest["macd"],
        "signal": "BUY" if latest["rsi"] < RSI_OVERSOLD else "SELL" if latest["rsi"] > RSI_OVERBOUGHT else "HOLD"
    }

def run_feed():
    while True:
        for pair in PAIRS:
            df = fetch_ohlcv(pair)
            signals = compute_signals(df)
            if signals["signal"] != "HOLD":
                emit_alert(pair, signals)
        # {{ADD_SLEEP_INTERVAL}}

def emit_alert(pair: str, signals: dict):
    # {{IMPLEMENT_ALERT_CHANNELS}}
    print(f"[ALERT] {pair}: {signals}")
