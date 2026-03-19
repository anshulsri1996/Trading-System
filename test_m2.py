# test_m2.py

from data.data_manager import DataManager
from strategies.strategy_generator import (
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    RSIStrategy
)
from backtester.backtester import Backtester

# ── Get data ───────────────────────────────────────────────────────────────
dm = DataManager(symbol="RELIANCE.NS")
df = dm.get_historical_data(
        start    = "2022-01-01",
        end      = "2024-12-31",
        interval = "1d"
     )

bt = Backtester(capital=100_000)

# ── Test 1: EMA Crossover ──────────────────────────────────────────────────
s1      = EMACrossoverStrategy(fast_period=20, slow_period=50)
df1     = s1.generate_signals(df)
result1 = bt.run(df1, strategy_name="EMA Crossover")

# ── Test 2: Bollinger Bands ────────────────────────────────────────────────
s2      = BollingerBandsStrategy(period=20, std_dev=2.0)
df2     = s2.generate_signals(df)
result2 = bt.run(df2, strategy_name="Bollinger Bands")

# ── Test 3: RSI ────────────────────────────────────────────────────────────
s3      = RSIStrategy(period=14, oversold=30, overbought=70)
df3     = s3.generate_signals(df)
result3 = bt.run(df3, strategy_name="RSI Mean Reversion")

# ── Print trade log for best strategy ─────────────────────────────────────
print("\nTRADE LOG — EMA Crossover:")
print(result1['trades'][['entry_date','exit_date',
                          'entry_price','exit_price',
                          'pnl','result']].to_string())