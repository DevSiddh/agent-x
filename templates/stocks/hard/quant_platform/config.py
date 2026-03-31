# Template source: microsoft/qlib | Difficulty: hard | Niche: stocks
MARKET = "{{MARKET}}"  # e.g. us_stock, cn_stock
START_TIME = "{{START_TIME}}"
END_TIME = "{{END_TIME}}"
BENCHMARK = "{{BENCHMARK}}"  # e.g. SPY
MODEL = "{{MODEL}}"  # LightGBM, LSTM, Transformer
ALPHA_FACTORS = ["{{FACTOR_1}}", "{{FACTOR_2}}"]
MLFLOW_URI = "{{MLFLOW_URI}}"
BACKTEST_FREQ = "day"
TOP_K = {{TOP_K}}  # number of stocks to hold
N_DROP = {{N_DROP}}  # stocks to drop per rebalance
