# Template source: mementum/backtrader | Difficulty: medium | Niche: stocks
import backtrader as bt

class {{STRATEGY_NAME}}(bt.Strategy):
    params = dict(sma_fast={{SMA_FAST}}, sma_slow={{SMA_SLOW}}, rsi_period=14)

    def __init__(self):
        self.sma_fast = bt.indicators.SMA(self.data.close, period=self.p.sma_fast)
        self.sma_slow = bt.indicators.SMA(self.data.close, period=self.p.sma_slow)
        self.rsi = bt.indicators.RSI(self.data.close, period=self.p.rsi_period)
        self.crossover = bt.indicators.CrossOver(self.sma_fast, self.sma_slow)

    def next(self):
        # Core engine: signal-driven order logic
        if not self.position:
            if self.crossover > 0 and self.rsi < 70:
                self.buy(size={{POSITION_SIZE}})
                # {{ADD_ENTRY_FILTERS}}
        elif self.crossover < 0 or self.rsi > 70:
            self.close()
            # {{ADD_EXIT_FILTERS}}

    def notify_trade(self, trade):
        if trade.isclosed:
            print(f"TRADE CLOSED | PnL: {trade.pnl:.2f} | PnL net: {trade.pnlcomm:.2f}")
