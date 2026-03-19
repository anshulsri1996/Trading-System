# test_m7.py

from strategies.strategy_generator import EMACrossoverStrategy
from risk_engine.risk_engine import RiskEngine
from execution.execution_engine import ExecutionEngine
from logger.logger import TradingLogger

# ── Setup ──────────────────────────────────────────────────────────────────
strategy = EMACrossoverStrategy(fast_period=20, slow_period=50)
risk     = RiskEngine(
               capital            = 100_000,
               max_risk_per_trade = 0.02,
               daily_loss_limit   = 0.05,
               stop_loss_pct      = 0.02
           )
logger   = TradingLogger(strategy_name="EMA Crossover")

# ── Log some simulated events to test the logger ───────────────────────────
print("\n--- Testing logger ---")

logger.log_signal("BUY",  1411.50, "RELIANCE.NS", "EMA crossover detected")
logger.log_signal("HOLD", 1415.00, "RELIANCE.NS", "Waiting for confirmation")
logger.log_signal("SELL", 1445.00, "RELIANCE.NS", "EMA crossed below")

logger.log_trade("BUY",  "RELIANCE.NS", 70, 1411.50, stop_loss=1383.27)
logger.log_trade("SELL", "RELIANCE.NS", 70, 1445.00, pnl=2345.00,
                 reason="SIGNAL")

logger.log_pnl(
    capital   = 97_655.00,
    position  = 0,
    price     = 1445.00,
    daily_pnl = 2345.00
)

logger.log_error("DataManager", "Timeout fetching candle — retrying")

# ── Generate end of day report ─────────────────────────────────────────────
print("\n--- Generating EOD report ---")
logger.generate_eod_report(
    final_capital = 102_345.00,
    equity_curve  = [],
    risk_summary  = risk.daily_summary()
)

print("\n--- Check your /logs folder for the files ---")