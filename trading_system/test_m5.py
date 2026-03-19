# test_m5.py

from strategies.strategy_generator import EMACrossoverStrategy
from signal_engine.signal_engine import SignalEngine

# Use EMA Crossover — our best performing strategy from M3
strategy = EMACrossoverStrategy(fast_period=20, slow_period=50)

engine = SignalEngine(
    strategy = strategy,
    symbol   = "RELIANCE.NS",
    interval = "1d",       # daily candles
    lookback = 120,        # load last 120 days each cycle
    refresh  = 30,         # refresh every 30 seconds for testing
                           # (use 300 for 5 mins in real use)
)

# Run for 3 cycles so you can see it working without waiting forever
# Remove max_cycles=3 to run continuously
engine.start(max_cycles=3)