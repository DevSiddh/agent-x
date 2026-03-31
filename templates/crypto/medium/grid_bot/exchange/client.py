# Template source: jordantete/grid_trading_bot | Difficulty: medium | Niche: crypto
import ccxt.pro as ccxtpro

class ExchangeClient:
    def __init__(self, exchange_id: str, api_key: str, api_secret: str):
        self.exchange = getattr(ccxtpro, exchange_id)({"apiKey": api_key, "secret": api_secret})

    async def place_order(self, pair: str, side: str, amount: float, price: float) -> dict:
        return await self.exchange.create_limit_order(pair, side, amount, price)

    async def cancel_order(self, order_id: str, pair: str) -> dict:
        return await self.exchange.cancel_order(order_id, pair)

    async def get_balance(self) -> dict:
        return await self.exchange.fetch_balance()

    async def watch_orders(self, pair: str):
        while True:
            orders = await self.exchange.watch_orders(pair)
            yield orders
