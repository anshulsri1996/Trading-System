# execution/execution_engine.py

import time
import pandas as pd
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from data.data_manager import DataManager
from strategies.base_strategy import BaseStrategy
from risk_engine.risk_engine import RiskEngine


class ExecutionEngine:
    """
    M6 — Execution Engine (Paper Trading Mode)

    The master controller that connects all modules:
        Data → Strategy → Risk Check → Execute → Log

    Paper mode: all trades are simulated, no real orders placed.
    Live mode (later): swap _paper_buy/_paper_sell with Kite API calls.
    """

    def __init__(
        self,
        strategy:    BaseStrategy,
        risk_engine: RiskEngine,
        symbol:      str  = None,
        interval:    str  = "1d",
        lookback:    int  = 120,
        refresh:     int  = 60,
    ):
        self.strategy    = strategy
        self.risk        = risk_engine
        self.symbol      = symbol or config.DEFAULT_SYMBOL
        self.interval    = interval
        self.lookback    = lookback
        self.refresh     = refresh
        self.dm          = DataManager(symbol=self.symbol)

        # Portfolio state
        self.capital         = float(config.CAPITAL)
        self.position        = 0
        self.entry_price     = 0.0
        self.stop_loss_price = 0.0
        self.trade_log       = []
        self.equity_curve    = []

        print(f"\n[ExecutionEngine] Ready")
        print(f"  Strategy : {self.strategy.name}")
        print(f"  Symbol   : {self.symbol}")
        print(f"  Mode     : PAPER TRADING")

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN LOOP
    # ──────────────────────────────────────────────────────────────────────────
    def start(self, max_cycles: int = None) -> None:
        cycle = 0

        print(f"\n{'='*55}")
        print(f"  PAPER TRADING STARTED")
        print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*55}\n")

        try:
            while True:
                cycle += 1
                now    = datetime.now().strftime('%H:%M:%S')
                print(f"\n{'─'*45}")
                print(f"Cycle {cycle} | {now}")
                print(f"{'─'*45}")

                # 1. Fetch data
                df = self._fetch_data()
                if df is None:
                    time.sleep(self.refresh)
                    continue

                # 2. Generate signals
                df = self.strategy.generate_signals(df)

                # 3. Get last completed candle
                last         = df.iloc[-2]
                signal       = int(last['signal'])
                close_price  = float(last['close'])

                # 4. Check stop loss if in a position
                if self.position > 0:
                    if self.risk.check_stop_loss(
                            close_price, self.stop_loss_price):
                        self._paper_sell(close_price, reason="STOP_LOSS")

                # 5. Process strategy signal through risk engine
                risk_check = self.risk.can_trade(
                    signal             = signal,
                    current_positions  = 1 if self.position > 0 else 0
                )

                if risk_check['allowed']:
                    if signal == 1 and self.position == 0:
                        sizing = self.risk.calculate_position_size(
                            price   = close_price,
                            capital = self.capital
                        )
                        self._paper_buy(close_price, sizing)

                    elif signal == -1 and self.position > 0:
                        self._paper_sell(close_price, reason="SIGNAL")

                    else:
                        hold = ("holding" if self.position > 0
                                else "flat — no signal")
                        print(f"  ⏸  HOLD ({hold})")
                else:
                    print(f"  ⛔ Signal blocked: {risk_check['reason']}")

                # 6. Track equity
                market_val = self.capital + self.position * close_price
                self.equity_curve.append({
                    'time'   : datetime.now(),
                    'equity' : round(market_val, 2)
                })

                # 7. Print portfolio snapshot
                self._print_snapshot(close_price)

                # 8. Check cycle limit
                if max_cycles and cycle >= max_cycles:
                    print(f"\n[Engine] Reached {max_cycles} cycles. Stopping.")
                    break

                print(f"\n  Next check in {self.refresh}s ...")
                time.sleep(self.refresh)

        except KeyboardInterrupt:
            print("\n[Engine] Stopped by user.")

        finally:
            self._print_session_report()

    # ──────────────────────────────────────────────────────────────────────────
    # PAPER TRADE EXECUTION
    # ──────────────────────────────────────────────────────────────────────────
    def _paper_buy(self, price: float, sizing: dict) -> None:
        shares            = sizing['shares']
        cost              = shares * price * 1.001
        self.capital     -= cost
        self.position     = shares
        self.entry_price  = price
        self.stop_loss_price = sizing['stop_loss_price']

        print(f"\n  ✅ PAPER BUY EXECUTED")
        print(f"     Shares     : {shares}")
        print(f"     Price      : ₹{price:,.2f}")
        print(f"     Cost       : ₹{cost:,.2f}")
        print(f"     Stop loss  : ₹{self.stop_loss_price:,.2f}")
        print(f"     Capital    : ₹{self.capital:,.2f} remaining")

    def _paper_sell(self, price: float, reason: str = "SIGNAL") -> None:
        proceeds      = self.position * price * 0.999
        self.capital += proceeds
        pnl           = (price - self.entry_price) * self.position
        pnl_pct       = (price - self.entry_price) / self.entry_price * 100

        self.trade_log.append({
            'entry'  : self.entry_price,
            'exit'   : price,
            'shares' : self.position,
            'pnl'    : round(pnl, 2),
            'pct'    : round(pnl_pct, 2),
            'reason' : reason,
            'result' : 'WIN' if pnl > 0 else 'LOSS'
        })

        self.risk.update_pnl(pnl)

        icon = "🟢" if pnl > 0 else "🔴"
        print(f"\n  {icon} PAPER SELL EXECUTED ({reason})")
        print(f"     Shares  : {self.position}")
        print(f"     Price   : ₹{price:,.2f}")
        print(f"     PnL     : ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")
        print(f"     Capital : ₹{self.capital:,.2f}")

        self.position        = 0
        self.entry_price     = 0.0
        self.stop_loss_price = 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _fetch_data(self) -> pd.DataFrame:
        try:
            return self.dm.get_recent_data(
                days     = self.lookback,
                interval = self.interval
            )
        except Exception as e:
            print(f"[Engine] Data error: {e}")
            return None

    def _print_snapshot(self, price: float) -> None:
        market_val = self.capital + self.position * price
        pnl        = market_val - config.CAPITAL
        pnl_pct    = pnl / config.CAPITAL * 100
        print(f"\n  Portfolio : ₹{market_val:,.2f} "
              f"({pnl:+,.2f} | {pnl_pct:+.2f}%)")
        if self.position > 0:
            unreal = (price - self.entry_price) / self.entry_price * 100
            print(f"  Position  : {self.position} shares "
                  f"@ ₹{self.entry_price:,.2f} "
                  f"(unrealised: {unreal:+.2f}%)")
            print(f"  Stop loss : ₹{self.stop_loss_price:,.2f}")

    def _print_session_report(self) -> None:
        print(f"\n{'='*55}")
        print(f"  SESSION REPORT — {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*55}")
        print(f"  Trades completed : {len(self.trade_log)}")

        if self.trade_log:
            df       = pd.DataFrame(self.trade_log)
            total    = df['pnl'].sum()
            wins     = (df['pnl'] > 0).sum()
            wr       = wins / len(df) * 100
            print(f"  Total PnL        : ₹{total:+,.2f}")
            print(f"  Win rate         : {wr:.1f}%")
            print(f"\n  Trade log:")
            print(df[['entry','exit','pnl','reason','result']].to_string())

        rs = self.risk.daily_summary()
        print(f"\n  Risk summary:")
        print(f"    Daily PnL    : ₹{rs['daily_pnl']:+,.2f}")
        print(f"    Trades today : {rs['daily_trades']}")
        print(f"    Kill switch  : {rs['kill_switch']}")
        print(f"{'='*55}\n")