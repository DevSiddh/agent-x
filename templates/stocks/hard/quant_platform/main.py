# Template source: microsoft/qlib | Difficulty: hard | Niche: stocks
from config import MARKET, START_TIME, END_TIME, TOP_K
from alpha import compute_alpha_factors, rank_stocks
# {{IMPORT_QLIB_COMPONENTS}}

if __name__ == "__main__":
    print(f"Quant platform | market={MARKET} | {START_TIME} -> {END_TIME} | top_k={TOP_K}")
    # {{INITIALIZE_QLIB}}
    # {{RUN_WORKFLOW}}
