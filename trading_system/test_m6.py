# test_m6.py

from strategies.strategy_generator import EMACrossoverStrategy
from risk_engine.risk_engine import RiskEngine
from execution.execution_engine import ExecutionEngine

# ── Set up strategy ────────────────────────────────────────────────────────
strategy = EMACrossoverStrategy(fast_period=20, slow_period=50)

# ── Set up risk engine ─────────────────────────────────────────────────────
risk = RiskEngine(
    capital            = 100_000,
    max_risk_per_trade = 0.02,    # risk max 2% per trade
    daily_loss_limit   = 0.05,    # stop if down 5% today
    stop_loss_pct      = 0.02,    # exit if trade moves 2% against us
)

# ── Set up execution engine ────────────────────────────────────────────────
engine = ExecutionEngine(
    strategy  = strategy,
    risk_engine = risk,
    symbol    = "RELIANCE.NS",
    interval  = "1d",
    lookback  = 120,
    refresh   = 30,
)

# Run 2 cycles to confirm everything works
engine.start(max_cycles=2)