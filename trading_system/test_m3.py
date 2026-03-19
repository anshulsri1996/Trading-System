# test_m3.py

from data.data_manager import DataManager
from strategies.strategy_generator import (
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    RSIStrategy
)
from backtester.backtester import Backtester
from analyser.analyser import StrategyAnalyser

# ── Get data ───────────────────────────────────────────────────────────────
dm = DataManager(symbol="RELIANCE.NS")
df = dm.get_historical_data(
        start    = "2022-01-01",
        end      = "2024-12-31",
        interval = "1d"
     )

bt  = Backtester(capital=100_000)
ana = StrategyAnalyser()

# ── Analyse all 3 strategies ───────────────────────────────────────────────
for Strategy, name in [
    (EMACrossoverStrategy,  "EMA Crossover"),
    (BollingerBandsStrategy,"Bollinger Bands"),
    (RSIStrategy,           "RSI Mean Reversion")
]:
    s       = Strategy()
    signals = s.generate_signals(df)
    results = bt.run(signals, strategy_name=name)
    ana.analyse(results, df=df)