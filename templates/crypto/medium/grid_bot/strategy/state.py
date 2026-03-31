# Template source: jordantete/grid_trading_bot | Difficulty: medium | Niche: crypto
class GridState:
    def __init__(self):
        self.open_orders = {}
        self.filled_orders = []
        self.pnl = 0.0

    def track_order(self, buy_order, sell_order, level):
        self.open_orders[buy_order["id"]] = {"type": "buy", "level": level}
        self.open_orders[sell_order["id"]] = {"type": "sell", "level": level}

    def update_pnl(self, filled_order):
        self.filled_orders.append(filled_order)
        # {{CALCULATE_PNL_DELTA}}

    def get_summary(self) -> dict:
        return {"open": len(self.open_orders), "filled": len(self.filled_orders), "pnl": self.pnl}
