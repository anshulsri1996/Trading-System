# main.py
# ══════════════════════════════════════════════════════════════════════════════
# ALGORITHMIC TRADING SYSTEM — MASTER CONTROLLER
# Run this single file to start the entire system
# ══════════════════════════════════════════════════════════════════════════════

import sys
import os
import time
import threading
from datetime import datetime, date

# ── Import all modules ─────────────────────────────────────────────────────
import config
from data.data_manager          import DataManager
from strategies.strategy_generator import (
    StrategyGenerator,
    EMACrossoverStrategy,
    BollingerBandsStrategy,
    RSIStrategy
)
from backtester.backtester      import Backtester
from analyser.analyser          import StrategyAnalyser
from risk_engine.risk_engine    import RiskEngine
from logger.logger              import TradingLogger


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — WELCOME SCREEN
# ══════════════════════════════════════════════════════════════════════════════
def print_banner():
    print("\n" + "█"*60)
    print("█" + " "*58 + "█")
    print("█" + "  ALGORITHMIC TRADING SYSTEM".center(58) + "█")
    print("█" + "  Paper Trading Mode".center(58) + "█")
    print("█" + " "*58 + "█")
    print("█"*60)
    print(f"\n  Started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Capital : ₹{config.CAPITAL:,.0f}")
    print(f"  Symbol  : {config.DEFAULT_SYMBOL}")
    print()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — LET USER PICK A STRATEGY
# ══════════════════════════════════════════════════════════════════════════════
def choose_strategy():
    print("="*60)
    print("  CHOOSE YOUR STRATEGY")
    print("="*60)
    print("  1. EMA Crossover        (trend following)")
    print("  2. Bollinger Bands      (mean reversion)")
    print("  3. RSI Mean Reversion   (momentum)")
    print("  4. Type your own idea   (AI generator)")
    print("-"*60)

    choice = input("  Enter choice (1/2/3/4): ").strip()

    if choice == "1":
        strategy = EMACrossoverStrategy(fast_period=20, slow_period=50)

    elif choice == "2":
        strategy = BollingerBandsStrategy(period=20, std_dev=2.0)

    elif choice == "3":
        strategy = RSIStrategy(period=14, oversold=30, overbought=70)

    elif choice == "4":
        idea     = input("\n  Describe your strategy in plain English:\n  > ")
        gen      = StrategyGenerator()
        strategy = gen.from_text(idea)

    else:
        print("  Invalid choice. Using EMA Crossover.")
        strategy = EMACrossoverStrategy()

    print(f"\n  ✅ Strategy selected: {strategy.name}")
    return strategy


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — RUN BACKTEST BEFORE GOING LIVE
# ══════════════════════════════════════════════════════════════════════════════
def run_backtest(strategy):
    print("\n" + "="*60)
    print("  STEP 1/3 — BACKTESTING STRATEGY")
    print("  Testing on 3 years of historical data first...")
    print("="*60)

    dm = DataManager(symbol=config.DEFAULT_SYMBOL)
    df = dm.get_historical_data(
        start    = "2022-01-01",
        end      = "2024-12-31",
        interval = "1d"
    )

    # Run backtest
    bt      = Backtester(capital=config.CAPITAL)
    signals = strategy.generate_signals(df)
    results = bt.run(signals, strategy_name=strategy.name)

    # Analyse results
    print("\n" + "="*60)
    print("  STEP 2/3 — ANALYSING BACKTEST RESULTS")
    print("="*60)
    ana      = StrategyAnalyser()
    analysis = ana.analyse(results, df=df)

    # Ask user if they want to continue
    print("\n" + "="*60)
    score = analysis['score']['total']
    grade = analysis['score']['grade']
    print(f"  Strategy Score : {score:.1f}/100  [Grade: {grade}]")

    if grade in ['D', 'F']:
        print(f"\n  ⚠️  WARNING: This strategy scored {grade}.")
        print("  It may not perform well in live trading.")

        grade = analysis['score']['grade']
    score = analysis['score']['total']

    # ── Grade A or B — auto approve ───────────────────────────────────
    if grade in ['A', 'B']:
        print(f"\n  ✅ Strategy grade {grade} — approved automatically.")
        print(f"  Proceeding to paper trading...")
        return True, results

    # ── Grade C — warn but allow ───────────────────────────────────────
    elif grade == 'C':
        print(f"\n  ⚠️  Grade C strategy — acceptable but not ideal.")
        proceed = input("  Proceed to paper trading? (yes/no): ").strip().lower()
        return proceed in ['yes', 'y'], results

    # ── Grade D — strong warning ───────────────────────────────────────
    elif grade == 'D':
        print(f"\n  🚨 WARNING: Grade D strategy (score: {score:.1f}/100)")
        print(f"  This strategy has serious weaknesses.")
        print(f"  Type CONFIRM to proceed anyway, or press Enter to cancel: ")
        confirm = input("  > ").strip()
        if confirm == "CONFIRM":
            print("  Proceeding with low-confidence strategy...")
            return True, results
        else:
            print("  Smart choice. Try a different strategy.")
            return False, results

    # ── Grade F — hard block ───────────────────────────────────────────
    elif grade == 'F':
        print(f"\n  ❌ HARD BLOCK — Grade F strategy refused.")
        print(f"  Score: {score:.1f}/100 — too risky to run.")
        print(f"\n  Top suggestions to fix it:")
        suggestions = analysis.get('suggestions', [])
        high = [s for s in suggestions if s['priority'] == 'HIGH']
        for s in high[:3]:
            print(f"  → {s['action']}")
        print(f"\n  Restart and pick a different strategy.")
        return False, results


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — PAPER TRADING LOOP
# ══════════════════════════════════════════════════════════════════════════════
def run_paper_trading(strategy, logger, risk):
    print("\n" + "="*60)
    print("  STEP 3/3 — PAPER TRADING STARTED")
    print("  Press Ctrl+C to stop and generate EOD report")
    print("="*60 + "\n")

    dm       = DataManager(symbol=config.DEFAULT_SYMBOL)
    capital  = float(config.CAPITAL)
    position = 0
    entry_price  = 0.0
    stop_loss_p  = 0.0
    equity_curve = []
    cycle        = 0

    try:
        while True:
            cycle += 1
            now    = datetime.now().strftime('%H:%M:%S')
            print(f"\n{'─'*50}")
            print(f"  Cycle {cycle} | {now} | {config.DEFAULT_SYMBOL}")
            print(f"{'─'*50}")

            # ── Fetch latest data ──────────────────────────────────────────
            try:
                df = dm.get_recent_data(days=120, interval="1d")
            except Exception as e:
                logger.log_error("DataManager", str(e))
                print(f"  ⚠️  Data error: {e}. Retrying in 60s...")
                time.sleep(60)
                continue

            if len(df) < 20:
                print("  ⚠️  Not enough data. Waiting...")
                time.sleep(60)
                continue

            # ── Generate signals ───────────────────────────────────────────
            df_sig  = strategy.generate_signals(df)
            last    = df_sig.iloc[-2]
            signal  = int(last['signal'])
            price   = float(last['close'])
            sig_str = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}.get(signal, 'HOLD')

            print(f"  Signal    : {sig_str}")
            print(f"  Price     : ₹{price:,.2f}")

            logger.log_signal(sig_str, price, config.DEFAULT_SYMBOL)

            # ── Check stop loss ────────────────────────────────────────────
            if position > 0 and price <= stop_loss_p:
                proceeds    = position * price * 0.999
                pnl         = (price - entry_price) * position
                capital    += proceeds

                print(f"\n  ⛔ STOP LOSS HIT @ ₹{price:,.2f}")
                print(f"     PnL : ₹{pnl:+,.2f}")

                logger.log_trade("SELL", config.DEFAULT_SYMBOL,
                                 position, price, pnl, reason="STOP_LOSS")
                risk.update_pnl(pnl)
                position    = 0
                entry_price = 0.0
                stop_loss_p = 0.0

            # ── Risk check ────────────────────────────────────────────────
            check = risk.can_trade(signal, 1 if position > 0 else 0)

            if check['allowed']:

                # BUY
                if signal == 1 and position == 0:
                    sizing      = risk.calculate_position_size(price, capital)
                    shares      = sizing['shares']
                    cost        = shares * price * 1.001
                    capital    -= cost
                    position    = shares
                    entry_price = price
                    stop_loss_p = sizing['stop_loss_price']

                    print(f"\n  ✅ BUY  {shares} shares @ ₹{price:,.2f}")
                    print(f"     Stop loss : ₹{stop_loss_p:,.2f}")
                    print(f"     Capital   : ₹{capital:,.2f} remaining")

                    logger.log_trade("BUY", config.DEFAULT_SYMBOL,
                                     shares, price,
                                     stop_loss=stop_loss_p)

                # SELL
                elif signal == -1 and position > 0:
                    proceeds    = position * price * 0.999
                    pnl         = (price - entry_price) * position
                    pnl_pct     = (price - entry_price) / entry_price * 100
                    capital    += proceeds

                    icon = "🟢" if pnl > 0 else "🔴"
                    print(f"\n  {icon} SELL {position} shares @ ₹{price:,.2f}")
                    print(f"     PnL : ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")

                    logger.log_trade("SELL", config.DEFAULT_SYMBOL,
                                     position, price, pnl, reason="SIGNAL")
                    risk.update_pnl(pnl)
                    position    = 0
                    entry_price = 0.0
                    stop_loss_p = 0.0

                else:
                    hold = "holding" if position > 0 else "flat"
                    print(f"  ⏸  HOLD ({hold})")
            else:
                logger.log_risk_event("BLOCKED", check['reason'])

            # ── Portfolio snapshot ────────────────────────────────────────
            market_val = capital + position * price
            total_pnl  = market_val - config.CAPITAL
            total_ret  = total_pnl / config.CAPITAL * 100

            print(f"\n  Portfolio : ₹{market_val:,.2f} "
                  f"({total_pnl:+,.2f} | {total_ret:+.2f}%)")

            if position > 0:
                unreal = (price - entry_price) / entry_price * 100
                print(f"  Position  : {position} shares "
                      f"@ ₹{entry_price:,.2f} "
                      f"(unrealised: {unreal:+.2f}%)")
                print(f"  Stop loss : ₹{stop_loss_p:,.2f}")

            logger.log_pnl(capital, position, price, risk.daily_pnl)

            equity_curve.append({
                'time'  : now,
                'equity': round(market_val, 2)
            })

            # ── Wait for next candle ───────────────────────────────────────
            refresh = 60   # seconds — change to 3600 for hourly candles
            print(f"\n  Next check in {refresh}s ...")
            time.sleep(refresh)

    except KeyboardInterrupt:
        print("\n\n  ⏹  Trading stopped by user.")
        return capital, equity_curve


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — END OF DAY REPORT
# ══════════════════════════════════════════════════════════════════════════════
def generate_eod(logger, risk, final_capital, equity_curve):
    print("\n" + "="*60)
    print("  GENERATING END OF DAY REPORT...")
    print("="*60)
    logger.generate_eod_report(
        final_capital = final_capital,
        equity_curve  = equity_curve,
        risk_summary  = risk.daily_summary()
    )


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — ties everything together
# ══════════════════════════════════════════════════════════════════════════════
def main():
    # 1. Banner
    print_banner()

    # 2. Pick strategy
    strategy = choose_strategy()

    # 3. Backtest + analyse
    proceed, backtest_results = run_backtest(strategy)
    if not proceed:
        print("\n  Exiting. Adjust your strategy and try again.")
        sys.exit(0)

    # 4. Set up risk engine + logger
    risk   = RiskEngine(
                 capital            = config.CAPITAL,
                 max_risk_per_trade = config.MAX_RISK_PER_TRADE,
                 daily_loss_limit   = config.DAILY_LOSS_LIMIT,
                 stop_loss_pct      = 0.02
             )
    logger = TradingLogger(strategy_name=strategy.name)

    # 5. Run paper trading
    final_capital, equity_curve = run_paper_trading(
        strategy, logger, risk
    )

    # 6. EOD report
    generate_eod(logger, risk, final_capital, equity_curve)

    print("\n  ✅ Session complete. Check /logs and /reports for details.")
    print("  Goodbye!\n")


if __name__ == "__main__":
    main()