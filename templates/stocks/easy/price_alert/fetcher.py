# Template source: yfinance-pattern | Difficulty: easy | Niche: stocks
import yfinance as yf
import time
from config import TICKERS, THRESHOLDS, POLL_INTERVAL

def fetch_prices() -> dict:
    prices = {}
    for ticker in TICKERS:
        data = yf.Ticker(ticker)
        info = data.fast_info
        prices[ticker] = info.last_price
    return prices

def check_alerts(prices: dict) -> list[dict]:
    alerts = []
    for ticker, price in prices.items():
        if ticker in THRESHOLDS:
            t = THRESHOLDS[ticker]
            if "above" in t and price > t["above"]:
                alerts.append({"ticker": ticker, "price": price, "trigger": "above", "threshold": t["above"]})
            if "below" in t and price < t["below"]:
                alerts.append({"ticker": ticker, "price": price, "trigger": "below", "threshold": t["below"]})
    return alerts

def run():
    while True:
        prices = fetch_prices()
        alerts = check_alerts(prices)
        for alert in alerts:
            emit_alert(alert)
        time.sleep(POLL_INTERVAL)

def emit_alert(alert: dict):
    # {{IMPLEMENT_ALERT_CHANNELS}}
    print(f"[ALERT] {alert}")
