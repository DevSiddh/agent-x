# Template source: jordantete/grid_trading_bot | Difficulty: medium | Niche: crypto
import asyncio
from config import EXCHANGE, API_KEY, API_SECRET, PAIR
from exchange.client import ExchangeClient
from strategy.grid import GridStrategy
from strategy.state import GridState

async def main():
    client = ExchangeClient(EXCHANGE, API_KEY, API_SECRET)
    state = GridState()
    strategy = GridStrategy(client, state)
    balance = await client.get_balance()
    # {{GET_CURRENT_PRICE}}
    current_price = 0.0  # replace with live fetch
    await strategy.place_grid(PAIR, current_price)
    async for orders in client.watch_orders(PAIR):
        for order in orders:
            if order["status"] == "closed":
                await strategy.on_fill(order)

if __name__ == "__main__":
    asyncio.run(main())
