# test_m1.py

from data.data_manager import DataManager
from strategies.strategy_generator import StrategyGenerator

# Get some data
dm  = DataManager(symbol="RELIANCE.NS")
df  = dm.get_historical_data(
        start    = "2024-01-01",
        end      = "2024-12-31",
        interval = "1d"
      )

gen = StrategyGenerator()

# ── Test 1: EMA Crossover ──────────────────────────────────────────────────
print("\n" + "="*50)
print("TEST 1 — EMA Crossover")
print("="*50)
strategy = gen.from_text("ema crossover strategy")
result   = strategy.generate_signals(df)
print(result[result['signal'] != 0][['close','ema_fast','ema_slow','signal']].head(10))

# ── Test 2: Bollinger Bands ────────────────────────────────────────────────
print("\n" + "="*50)
print("TEST 2 — Bollinger Bands")
print("="*50)
strategy = gen.from_text("bollinger bands strategy")
result   = strategy.generate_signals(df)
print(result[result['signal'] != 0][['close','bb_upper','bb_lower','signal']].head(10))

# ── Test 3: RSI ────────────────────────────────────────────────────────────
print("\n" + "="*50)
print("TEST 3 — RSI Mean Reversion")
print("="*50)
strategy = gen.from_text("rsi momentum strategy")
result   = strategy.generate_signals(df)
print(result[result['signal'] != 0][['close','rsi','signal']].head(10))