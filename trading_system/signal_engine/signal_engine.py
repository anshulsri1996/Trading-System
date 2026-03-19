# signal_engine/signal_engine.py

import time
import pandas as pd
from datetime import datetime
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from data.data_manager import DataManager
from strategies.base_strategy import BaseStrategy


class SignalEngine:
    """
    M5 — Signal Engine (Paper Trading Mode)

    Runs a strategy on live-ish data by fetching the latest
    candles from yfinance every N seconds and checking for
    new BUY/SELL signals on the most recent candle.

    Paper trading mode:
        - No real orders are placed
        - Signals are printed and logged to a list
        - Tracks a virtual portfolio to show simulated PnL
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        symbol:   str   = None,
        interval: str   = "1d",
        lookback: int   = 100,    # how many candles to load each refresh
        refresh:  int   = 60,     # seconds between each data refresh
    ):
        self.strategy  = strategy
        self.symbol    = symbol or config.DEFAULT_SYMBOL
        self.interval  = interval
        self.lookback  = lookback
        self.refresh   = refresh
        self.dm        = DataManager(symbol=self.symbol)

        # Paper trading state
        self.capital        = float(config.CAPITAL)
        self.position       = 0        # shares held
        self.entry_price    = 0.0
        self.trade_log      = []       # all completed trades
        self.signal_log     = []       # all signals seen
        self.is_running     = False

        print(f"\n[SignalEngine] Initialised")
        print(f"  Strategy : {self.strategy.name}")
        print(f"  Symbol   : {self.symbol}")
        print(f"  Interval : {self.interval}")
        print(f"  Refresh  : every {self.refresh}s")
        print(f"  Capital  : ₹{self.capital:,.0f}")

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN LOOP — start the engine
    # ──────────────────────────────────────────────────────────────────────────
    def start(self, max_cycles: int = None):
        """
        Starts the live signal loop.

        Parameters:
            max_cycles : stop after N cycles (useful for testing).
                         None = run forever until Ctrl+C
        """
        self.is_running = True
        cycle           = 0

        print(f"\n{'='*55}")
        print(f"  SIGNAL ENGINE STARTED — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Press Ctrl+C to stop")
        print(f"{'='*55}\n")

        try:
            while self.is_running:
                cycle += 1
                print(f"--- Cycle {cycle} | "
                      f"{datetime.now().strftime('%H:%M:%S')} ---")

                # 1. Fetch latest data
                df = self._fetch_latest_data()

                if df is None or len(df) < 20:
                    print("[SignalEngine] Not enough data yet. Waiting...")
                    time.sleep(self.refresh)
                    continue

                # 2. Run strategy on latest data
                df_signals = self.strategy.generate_signals(df)

                # 3. Get the signal from the LAST completed candle
                #    (second-to-last row — last row may be incomplete)
                last_candle = df_signals.iloc[-2]
                signal      = int(last_candle['signal'])
                price       = float(last_candle['close'])
                candle_time = df_signals.index[-2]

                # 4. Process the signal
                self._process_signal(signal, price, candle_time)

                # 5. Print current portfolio status
                self._print_status(price)

                # 6. Check if max cycles reached
                if max_cycles and cycle >= max_cycles:
                    print(f"\n[SignalEngine] Reached {max_cycles} cycles. Stopping.")
                    break

                # 7. Wait for next refresh
                print(f"  Next refresh in {self.refresh}s ...\n")
                time.sleep(self.refresh)

        except KeyboardInterrupt:
            print("\n[SignalEngine] Stopped by user (Ctrl+C)")

        finally:
            self._print_final_report()

    # ──────────────────────────────────────────────────────────────────────────
    # FETCH LATEST DATA
    # ──────────────────────────────────────────────────────────────────────────
    def _fetch_latest_data(self) -> pd.DataFrame:
        """
        Fetches the most recent N candles.
        In paper mode this uses yfinance — refreshes every cycle.
        """
        try:
            df = self.dm.get_recent_data(
                days     = self.lookback,
                interval = self.interval
            )
            return df
        except Exception as e:
            print(f"[SignalEngine] Data fetch error: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # PROCESS SIGNAL
    # ──────────────────────────────────────────────────────────────────────────
    def _process_signal(
        self,
        signal: int,
        price:  float,
        candle_time
    ) -> None:
        """
        Decides what to do based on the signal and current position.
        In paper mode: simulates the trade without placing real orders.
        """
        signal_name = {1: 'BUY', -1: 'SELL', 0: 'HOLD'}.get(signal, 'HOLD')

        # Log every signal
        self.signal_log.append({
            'time'   : candle_time,
            'signal' : signal_name,
            'price'  : price
        })

        # ── BUY ───────────────────────────────────────────────────────────
        if signal == 1 and self.position == 0:
            cost          = price * 1.001          # include 0.1% brokerage
            self.position = int(self.capital / cost)
            self.entry_price = price
            self.capital  -= self.position * cost

            print(f"  ✅ BUY  SIGNAL → Bought {self.position} shares "
                  f"@ ₹{price:,.2f}")
            print(f"     Capital remaining: ₹{self.capital:,.2f}")

        # ── SELL ──────────────────────────────────────────────────────────
        elif signal == -1 and self.position > 0:
            proceeds      = price * 0.999          # include 0.1% brokerage
            self.capital += self.position * proceeds

            pnl     = (proceeds - self.entry_price) * self.position
            pnl_pct = ((proceeds - self.entry_price)
                       / self.entry_price * 100)

            self.trade_log.append({
                'entry_price' : self.entry_price,
                'exit_price'  : proceeds,
                'shares'      : self.position,
                'pnl'         : round(pnl, 2),
                'pnl_pct'     : round(pnl_pct, 2),
                'result'      : 'WIN' if pnl > 0 else 'LOSS'
            })

            print(f"  🔴 SELL SIGNAL → Sold {self.position} shares "
                  f"@ ₹{price:,.2f}")
            print(f"     Trade PnL: ₹{pnl:+,.2f} ({pnl_pct:+.2f}%)")

            self.position    = 0
            self.entry_price = 0.0

        # ── HOLD ──────────────────────────────────────────────────────────
        else:
            hold_reason = ("already in position" if self.position > 0
                           else "no position")
            print(f"  ⏸  {signal_name} — {hold_reason}")

    # ──────────────────────────────────────────────────────────────────────────
    # STATUS PRINTER
    # ──────────────────────────────────────────────────────────────────────────
    def _print_status(self, current_price: float) -> None:
        market_value = (self.capital
                        + self.position * current_price)
        pnl          = market_value - config.CAPITAL
        pnl_pct      = (pnl / config.CAPITAL) * 100

        print(f"  Portfolio  : ₹{market_value:>12,.2f}  "
              f"({pnl:+,.2f} | {pnl_pct:+.2f}%)")

        if self.position > 0:
            unrealised     = ((current_price - self.entry_price)
                              / self.entry_price * 100)
            print(f"  Position   : {self.position} shares @ "
                  f"₹{self.entry_price:,.2f} "
                  f"(unrealised: {unrealised:+.2f}%)")

    # ──────────────────────────────────────────────────────────────────────────
    # FINAL REPORT
    # ──────────────────────────────────────────────────────────────────────────
    def _print_final_report(self) -> None:
        print(f"\n{'='*55}")
        print(f"  PAPER TRADING SESSION SUMMARY")
        print(f"{'='*55}")
        print(f"  Total signals seen : {len(self.signal_log)}")
        print(f"  Total trades       : {len(self.trade_log)}")

        if self.trade_log:
            trades_df  = pd.DataFrame(self.trade_log)
            total_pnl  = trades_df['pnl'].sum()
            wins       = (trades_df['pnl'] > 0).sum()
            win_rate   = wins / len(trades_df) * 100
            print(f"  Total PnL          : ₹{total_pnl:+,.2f}")
            print(f"  Win Rate           : {win_rate:.1f}%")
            print(f"\n  Trade breakdown:")
            print(trades_df[['entry_price','exit_price',
                              'pnl','result']].to_string())

        print(f"{'='*55}\n")