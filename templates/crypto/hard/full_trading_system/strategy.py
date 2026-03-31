# Template source: freqtrade/freqtrade | Difficulty: hard | Niche: crypto
import pandas as pd
import ta

class {{STRATEGY_CLASS}}:
    timeframe = "{{TIMEFRAME}}"
    minimal_roi = {"0": {{ROI_0}}, "30": {{ROI_30}}, "60": {{ROI_60}}}
    stoploss = {{STOPLOSS}}
    trailing_stop = {{TRAILING_STOP}}

    def populate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        df["ema_fast"] = ta.trend.EMAIndicator(df["close"], window=9).ema_indicator()
        df["ema_slow"] = ta.trend.EMAIndicator(df["close"], window=21).ema_indicator()
        df["bb_upper"] = ta.volatility.BollingerBands(df["close"]).bollinger_hband()
        df["bb_lower"] = ta.volatility.BollingerBands(df["close"]).bollinger_lband()
        # {{ADD_MORE_INDICATORS}}
        return df

    def populate_entry_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        df["enter_long"] = (
            (df["rsi"] < 35) &
            (df["ema_fast"] > df["ema_slow"]) &
            (df["close"] < df["bb_lower"])
        ).astype(int)
        # {{ADD_ENTRY_CONDITIONS}}
        return df

    def populate_exit_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        df["exit_long"] = (
            (df["rsi"] > 70) |
            (df["close"] > df["bb_upper"])
        ).astype(int)
        # {{ADD_EXIT_CONDITIONS}}
        return df
