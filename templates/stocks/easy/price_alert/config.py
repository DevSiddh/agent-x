# Template source: yfinance-pattern | Difficulty: easy | Niche: stocks
TICKERS = ["{{TICKER_1}}", "{{TICKER_2}}"]  # e.g. AAPL, TSLA
THRESHOLDS = {
    "{{TICKER_1}}": {"above": {{PRICE_ABOVE}}, "below": {{PRICE_BELOW}}},
}
POLL_INTERVAL = 60  # seconds
ALERT_CHANNELS = ["telegram", "email"]
