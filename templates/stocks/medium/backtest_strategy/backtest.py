# Template source: mementum/backtrader | Difficulty: medium | Niche: stocks
import backtrader as bt
import yfinance as yf
from config import TICKER, START_DATE, END_DATE, INITIAL_CASH, COMMISSION
from strategy import {{STRATEGY_NAME}}

def run_backtest():
    cerebro = bt.Cerebro()
    cerebro.addstrategy({{STRATEGY_NAME}})
    raw = yf.download(TICKER, start=START_DATE, end=END_DATE)
    data = bt.feeds.PandasData(dataname=raw)
    cerebro.adddata(data)
    cerebro.broker.setcash(INITIAL_CASH)
    cerebro.broker.setcommission(COMMISSION)
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name="sharpe")
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
    cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
    print(f"Starting Portfolio: {cerebro.broker.getvalue():.2f}")
    results = cerebro.run()
    strat = results[0]
    print(f"Final Portfolio:    {cerebro.broker.getvalue():.2f}")
    print(f"Sharpe Ratio:       {strat.analyzers.sharpe.get_analysis()}")
    print(f"Max Drawdown:       {strat.analyzers.drawdown.get_analysis()['max']['drawdown']:.2f}%")
    cerebro.plot(style="candlestick")  # {{DISABLE_PLOT_IN_CI}}
    return results

if __name__ == "__main__":
    run_backtest()
