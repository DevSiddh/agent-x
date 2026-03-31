# Template source: freqtrade/freqtrade | Difficulty: hard | Niche: crypto
from config import EXCHANGE, API_KEY, API_SECRET, PAIRS, DRY_RUN
# {{IMPORT_TRADING_ENGINE}}

if __name__ == "__main__":
    # {{INITIALIZE_ENGINE_WITH_CONFIG}}
    print(f"Starting trading system | dry_run={DRY_RUN} | pairs={PAIRS}")
