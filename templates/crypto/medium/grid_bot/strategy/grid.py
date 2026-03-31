# Template source: jordantete/grid_trading_bot | Difficulty: medium | Niche: crypto
from config import GRID_LEVELS, GRID_SPACING, TOTAL_CAPITAL

class GridStrategy:
    def __init__(self, client, state):
        self.client = client
        self.state = state

    def compute_grid(self, current_price: float) -> list[dict]:
        levels = []
        for i in range(1, GRID_LEVELS + 1):
            buy_price = current_price * (1 - i * GRID_SPACING / 100)
            sell_price = current_price * (1 + i * GRID_SPACING / 100)
            amount = (TOTAL_CAPITAL / GRID_LEVELS) / buy_price
            levels.append({"buy": buy_price, "sell": sell_price, "amount": amount})
        return levels

    async def place_grid(self, pair: str, current_price: float):
        levels = self.compute_grid(current_price)
        for level in levels:
            buy_order = await self.client.place_order(pair, "buy", level["amount"], level["buy"])
            sell_order = await self.client.place_order(pair, "sell", level["amount"], level["sell"])
            self.state.track_order(buy_order, sell_order, level)

    async def on_fill(self, filled_order: dict):
        if filled_order["side"] == "buy":
            await self.client.place_order(
                filled_order["symbol"], "sell",
                filled_order["amount"],
                filled_order["price"] * (1 + GRID_SPACING / 100)
            )
        else:
            await self.client.place_order(
                filled_order["symbol"], "buy",
                filled_order["amount"],
                filled_order["price"] * (1 - GRID_SPACING / 100)
            )
        self.state.update_pnl(filled_order)
