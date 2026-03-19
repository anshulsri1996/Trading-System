# test_ai_strategy.py

from data.data_manager import DataManager
from strategies.strategy_generator import StrategyGenerator
from backtester.backtester import Backtester
from analyser.analyser import StrategyAnalyser

print("="*60)
print("  AI STRATEGY GENERATOR TEST")
print("="*60)
print("\nExamples of what you can type:")
print("  - Buy when RSI drops below 30, sell when it crosses above 70")
print("  - Buy when 20 EMA crosses above 50 EMA and volume is above average")
print("  - Buy when price touches lower Bollinger Band, sell at middle band")
print("  - Buy when RSI below 40 and price above 200 day moving average")
print()

# Get strategy idea from user
idea = input("Describe your strategy in plain English:\n> ").strip()

if not idea:
    idea = "Buy when RSI drops below 35 and sell when RSI rises above 65"
    print(f"Using default: {idea}")

# Generate strategy using AI
print("\n[System] Generating strategy...")
gen      = StrategyGenerator()
strategy = gen.from_text(idea)

# Get historical data
print("\n[System] Fetching historical data...")
dm = DataManager(symbol="RELIANCE.NS")
df = dm.get_historical_data(
    start    = "2022-01-01",
    end      = "2024-12-31",
    interval = "1d"
)

# Generate signals
print("\n[System] Running strategy on historical data...")
df_signals = strategy.generate_signals(df)

# Backtest
print("\n[System] Backtesting...")
bt      = Backtester(capital=100_000)
results = bt.run(df_signals, strategy_name=strategy.name)

# Analyse
print("\n[System] Analysing results...")
ana = StrategyAnalyser()
ana.analyse(results, df=df)

print("\n✅ Done! Your AI-generated strategy has been backtested.")