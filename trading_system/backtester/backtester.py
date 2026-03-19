# backtester/backtester.py

import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class Backtester:
    """
    M2 — Backtesting Engine

    Walks through historical data candle by candle and simulates
    trades based on signals from any strategy.

    Assumptions (keeping it simple and realistic):
        - We trade ONE position at a time (no overlapping trades)
        - We buy/sell at the NEXT candle's open price after a signal
          (realistic — you can't trade at the exact signal candle's close)
        - No leverage
        - Brokerage cost of 0.1% per trade (buy + sell = 0.2% round trip)
    """

    BROKERAGE = 0.001  # 0.1% per trade

    def __init__(self, capital: float = None):
        self.initial_capital = capital or config.CAPITAL
        print(f"[Backtester] Initialised with capital: "
              f"₹{self.initial_capital:,.0f}")

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN METHOD — run the backtest
    # ──────────────────────────────────────────────────────────────────────────
    def run(self, df: pd.DataFrame, strategy_name: str = "Strategy") -> dict:
        """
        Runs the backtest on a DataFrame that already has a 'signal' column.

        Parameters:
            df            : output of strategy.generate_signals()
            strategy_name : just a label for the report

        Returns:
            A dict with all performance metrics + trade log + equity curve
        """
        if 'signal' not in df.columns:
            print("[Backtester] ERROR: DataFrame has no 'signal' column. "
                  "Run strategy.generate_signals() first.")
            return {}

        print(f"\n[Backtester] Running backtest for: {strategy_name}")
        print(f"[Backtester] Candles: {len(df)} | "
              f"Capital: ₹{self.initial_capital:,.0f}")

        # ── Initialise tracking variables ──────────────────────────────────
        capital       = self.initial_capital
        position      = 0          # shares currently held
        entry_price   = 0.0        # price we bought at
        entry_date    = None
        trades        = []         # list of completed trades
        equity_curve  = []         # capital value at each candle

        # ── Walk through every candle ───────────────────────────────────────
        for i in range(len(df) - 1):
            current   = df.iloc[i]
            next_open = df.iloc[i + 1]['open']  # execute at next candle open
            signal    = current['signal']
            date      = df.index[i]

            # ── BUY signal and we are flat (no position) ───────────────────
            if signal == 1 and position == 0:
                # How many shares can we buy with all our capital?
                cost         = next_open * (1 + self.BROKERAGE)
                position     = int(capital / cost)  # whole shares only
                entry_price  = next_open
                entry_date   = df.index[i + 1]
                capital     -= position * cost

            # ── SELL signal and we are holding a position ──────────────────
            elif signal == -1 and position > 0:
                proceeds     = next_open * (1 - self.BROKERAGE)
                capital     += position * proceeds

                # Record the completed trade
                pnl          = (proceeds - entry_price) * position
                pnl_pct      = ((proceeds - entry_price) / entry_price) * 100
                trades.append({
                    'entry_date'  : entry_date,
                    'exit_date'   : df.index[i + 1],
                    'entry_price' : round(entry_price, 2),
                    'exit_price'  : round(proceeds, 2),
                    'shares'      : position,
                    'pnl'         : round(pnl, 2),
                    'pnl_pct'     : round(pnl_pct, 2),
                    'result'      : 'WIN' if pnl > 0 else 'LOSS'
                })
                position = 0

            # ── Track equity at this candle ────────────────────────────────
            # If holding, mark-to-market using current close
            market_value = capital + (position * current['close'])
            equity_curve.append({
                'date'   : date,
                'equity' : round(market_value, 2)
            })

        # ── Close any open position at end of data ─────────────────────────
        if position > 0:
            last_close   = df.iloc[-1]['close']
            proceeds     = last_close * (1 - self.BROKERAGE)
            capital     += position * proceeds
            pnl          = (proceeds - entry_price) * position
            pnl_pct      = ((proceeds - entry_price) / entry_price) * 100
            trades.append({
                'entry_date'  : entry_date,
                'exit_date'   : df.index[-1],
                'entry_price' : round(entry_price, 2),
                'exit_price'  : round(proceeds, 2),
                'shares'      : position,
                'pnl'         : round(pnl, 2),
                'pnl_pct'     : round(pnl_pct, 2),
                'result'      : 'WIN' if pnl > 0 else 'LOSS'
            })

        # ── Calculate performance metrics ──────────────────────────────────
        metrics = self._calculate_metrics(
            trades       = trades,
            equity_curve = equity_curve,
            final_capital= capital,
            strategy_name= strategy_name
        )

        return metrics

    # ──────────────────────────────────────────────────────────────────────────
    # METRICS CALCULATOR
    # ──────────────────────────────────────────────────────────────────────────
    def _calculate_metrics(
        self,
        trades: list,
        equity_curve: list,
        final_capital: float,
        strategy_name: str
    ) -> dict:

        if not trades:
            print("[Backtester] No trades were executed.")
            return {}

        trades_df = pd.DataFrame(trades)
        equity_df = pd.DataFrame(equity_curve)

        # Basic metrics
        total_trades  = len(trades_df)
        wins          = (trades_df['pnl'] > 0).sum()
        losses        = (trades_df['pnl'] <= 0).sum()
        win_rate      = (wins / total_trades) * 100
        total_pnl     = trades_df['pnl'].sum()
        total_return  = ((final_capital - self.initial_capital)
                         / self.initial_capital) * 100

        # Average win and loss
        avg_win  = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if wins  > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] <= 0]['pnl'].mean() if losses > 0 else 0

        # Max drawdown
        eq = equity_df['equity']
        rolling_max  = eq.cummax()
        drawdown     = (eq - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()

        # Profit factor (total wins / total losses — higher is better)
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss   = abs(trades_df[trades_df['pnl'] <= 0]['pnl'].sum())
        profit_factor = (gross_profit / gross_loss
                         if gross_loss > 0 else float('inf'))

        metrics = {
            'strategy_name' : strategy_name,
            'total_trades'  : total_trades,
            'wins'          : int(wins),
            'losses'        : int(losses),
            'win_rate'      : round(win_rate, 2),
            'total_pnl'     : round(total_pnl, 2),
            'total_return'  : round(total_return, 2),
            'max_drawdown'  : round(max_drawdown, 2),
            'profit_factor' : round(profit_factor, 2),
            'avg_win'       : round(avg_win, 2),
            'avg_loss'      : round(avg_loss, 2),
            'initial_capital': self.initial_capital,
            'final_capital' : round(final_capital, 2),
            'trades'        : trades_df,
            'equity_curve'  : equity_df
        }

        self._print_report(metrics)
        return metrics

    # ──────────────────────────────────────────────────────────────────────────
    # PRETTY REPORT PRINTER
    # ──────────────────────────────────────────────────────────────────────────
    def _print_report(self, m: dict) -> None:
        print("\n" + "="*55)
        print(f"  BACKTEST RESULTS — {m['strategy_name']}")
        print("="*55)
        print(f"  Initial Capital  : ₹{m['initial_capital']:>12,.2f}")
        print(f"  Final Capital    : ₹{m['final_capital']:>12,.2f}")
        print(f"  Total PnL        : ₹{m['total_pnl']:>12,.2f}")
        print(f"  Total Return     : {m['total_return']:>11.2f}%")
        print("-"*55)
        print(f"  Total Trades     : {m['total_trades']:>12}")
        print(f"  Wins             : {m['wins']:>12}")
        print(f"  Losses           : {m['losses']:>12}")
        print(f"  Win Rate         : {m['win_rate']:>11.2f}%")
        print("-"*55)
        print(f"  Avg Win          : ₹{m['avg_win']:>12,.2f}")
        print(f"  Avg Loss         : ₹{m['avg_loss']:>12,.2f}")
        print(f"  Profit Factor    : {m['profit_factor']:>12.2f}")
        print(f"  Max Drawdown     : {m['max_drawdown']:>11.2f}%")
        print("="*55 + "\n")