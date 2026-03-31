# Template source: freqtrade/freqtrade | Difficulty: hard | Niche: crypto
EXCHANGE = "{{EXCHANGE}}"
API_KEY = "{{API_KEY}}"
API_SECRET = "{{API_SECRET}}"
PAIRS = ["{{PAIR_1}}", "{{PAIR_2}}"]
STRATEGY = "{{STRATEGY_CLASS}}"
TIMEFRAME = "{{TIMEFRAME}}"  # e.g. 5m, 1h
MAX_OPEN_TRADES = {{MAX_OPEN_TRADES}}
STAKE_AMOUNT = {{STAKE_AMOUNT}}
DRY_RUN = True  # {{SET_FALSE_FOR_LIVE}}
TELEGRAM_TOKEN = "{{TELEGRAM_TOKEN}}"
TELEGRAM_CHAT_ID = "{{TELEGRAM_CHAT_ID}}"
DB_URL = "sqlite:///tradesv3.sqlite"
