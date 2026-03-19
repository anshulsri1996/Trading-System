# logger/logger.py

import os
import json
import logging
import pandas as pd
from datetime import datetime, date
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class TradingLogger:
    """
    M7 — Logger & Reporter

    Handles two things:
        1. LOGGING  — writes every trade, signal, error and
                      PnL update to structured log files in /logs
        2. REPORTING — generates a plain-English end-of-day report
                       explaining what worked, what failed, and
                       what to improve tomorrow
    """

    def __init__(self, strategy_name: str = "Strategy"):
        self.strategy_name = strategy_name
        self.session_start = datetime.now()
        self.log_dir       = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "logs"
        )
        self.report_dir    = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "reports"
        )

        # Create directories if they don't exist
        os.makedirs(self.log_dir,    exist_ok=True)
        os.makedirs(self.report_dir, exist_ok=True)

        # In-memory stores (also written to disk)
        self.trades  = []
        self.signals = []
        self.errors  = []
        self.pnl_snapshots = []

        # Set up file logger
        self._setup_file_logger()
        print(f"[Logger] Initialised — logs at: {self.log_dir}")

    # ──────────────────────────────────────────────────────────────────────────
    # LOGGING METHODS — call these from ExecutionEngine
    # ──────────────────────────────────────────────────────────────────────────
    def log_signal(
        self,
        signal:    str,
        price:     float,
        symbol:    str,
        reason:    str = ""
    ) -> None:
        """Log every BUY / SELL / HOLD signal."""
        entry = {
            'timestamp' : datetime.now().isoformat(),
            'symbol'    : symbol,
            'signal'    : signal,
            'price'     : price,
            'reason'    : reason
        }
        self.signals.append(entry)
        self.file_logger.info(f"SIGNAL | {signal:4s} | "
                              f"{symbol} @ ₹{price:,.2f} | {reason}")
        self._append_json("signals.json", entry)

    def log_trade(
        self,
        action:      str,
        symbol:      str,
        shares:      int,
        price:       float,
        pnl:         float = None,
        stop_loss:   float = None,
        reason:      str   = ""
    ) -> None:
        """Log every executed trade (buy or sell)."""
        entry = {
            'timestamp'  : datetime.now().isoformat(),
            'action'     : action,
            'symbol'     : symbol,
            'shares'     : shares,
            'price'      : price,
            'pnl'        : pnl,
            'stop_loss'  : stop_loss,
            'reason'     : reason
        }
        self.trades.append(entry)

        pnl_str = f" | PnL: ₹{pnl:+,.2f}" if pnl is not None else ""
        self.file_logger.info(f"TRADE  | {action:4s} | "
                              f"{symbol} × {shares} @ ₹{price:,.2f}"
                              f"{pnl_str}")
        self._append_json("trades.json", entry)

    def log_pnl(
        self,
        capital:    float,
        position:   int,
        price:      float,
        daily_pnl:  float
    ) -> None:
        """Log a PnL snapshot — called every cycle."""
        market_value = capital + position * price
        total_pnl    = market_value - config.CAPITAL
        entry = {
            'timestamp'   : datetime.now().isoformat(),
            'market_value': market_value,
            'total_pnl'   : round(total_pnl, 2),
            'daily_pnl'   : round(daily_pnl, 2),
            'position'    : position,
            'price'       : price
        }
        self.pnl_snapshots.append(entry)
        self.file_logger.info(f"PNL    | Portfolio: ₹{market_value:,.2f} | "
                              f"Total: {total_pnl:+,.2f} | "
                              f"Daily: {daily_pnl:+,.2f}")
        self._append_json("pnl.json", entry)

    def log_error(self, source: str, message: str) -> None:
        """Log any error — data fetch failures, API errors, etc."""
        entry = {
            'timestamp' : datetime.now().isoformat(),
            'source'    : source,
            'message'   : message
        }
        self.errors.append(entry)
        self.file_logger.error(f"ERROR  | {source} | {message}")
        self._append_json("errors.json", entry)

    def log_risk_event(self, event: str, detail: str) -> None:
        """Log risk engine events — kill switch, blocked trades, etc."""
        self.file_logger.warning(f"RISK   | {event} | {detail}")

    # ──────────────────────────────────────────────────────────────────────────
    # END OF DAY REPORT
    # ──────────────────────────────────────────────────────────────────────────
    def generate_eod_report(
        self,
        final_capital:  float,
        equity_curve:   list,
        risk_summary:   dict
    ) -> str:
        """
        Generates a plain-English end-of-day report.
        Saves it to /reports/YYYY-MM-DD.txt
        Returns the report as a string.
        """
        today     = date.today().isoformat()
        duration  = datetime.now() - self.session_start
        report    = []

        report.append("=" * 60)
        report.append(f"  END OF DAY REPORT — {today}")
        report.append(f"  Strategy: {self.strategy_name}")
        report.append("=" * 60)

        # ── Session info ───────────────────────────────────────────────────
        report.append(f"\n  SESSION")
        report.append(f"  Started  : {self.session_start.strftime('%H:%M:%S')}")
        report.append(f"  Duration : {str(duration).split('.')[0]}")
        report.append(f"  Cycles   : {len(self.pnl_snapshots)}")

        # ── PnL summary ────────────────────────────────────────────────────
        total_pnl    = final_capital - config.CAPITAL
        total_return = (total_pnl / config.CAPITAL) * 100

        report.append(f"\n  PNL SUMMARY")
        report.append(f"  Starting capital : ₹{config.CAPITAL:>12,.2f}")
        report.append(f"  Final capital    : ₹{final_capital:>12,.2f}")
        report.append(f"  Total PnL        : ₹{total_pnl:>+12,.2f}")
        report.append(f"  Total return     : {total_return:>+11.2f}%")

        # ── Trade summary ──────────────────────────────────────────────────
        report.append(f"\n  TRADE SUMMARY")
        report.append(f"  Total signals : {len(self.signals)}")
        report.append(f"  Total trades  : {len(self.trades)}")
        report.append(f"  Errors        : {len(self.errors)}")

        if self.trades:
            trades_df  = pd.DataFrame(self.trades)
            sells      = trades_df[trades_df['action'] == 'SELL']

            if not sells.empty and sells['pnl'].notna().any():
                wins     = (sells['pnl'] > 0).sum()
                losses   = (sells['pnl'] <= 0).sum()
                win_rate = wins / len(sells) * 100
                report.append(f"  Wins          : {wins}")
                report.append(f"  Losses        : {losses}")
                report.append(f"  Win rate      : {win_rate:.1f}%")

        # ── Risk summary ───────────────────────────────────────────────────
        report.append(f"\n  RISK SUMMARY")
        report.append(f"  Daily PnL    : ₹{risk_summary.get('daily_pnl', 0):+,.2f}")
        report.append(f"  Kill switch  : {risk_summary.get('kill_switch', False)}")

        # ── What worked ───────────────────────────────────────────────────
        report.append(f"\n  WHAT WORKED")
        report.append(self._analyse_what_worked(total_pnl))

        # ── What failed ───────────────────────────────────────────────────
        report.append(f"\n  WHAT FAILED")
        report.append(self._analyse_what_failed())

        # ── Improvements ──────────────────────────────────────────────────
        report.append(f"\n  IMPROVEMENTS FOR TOMORROW")
        report.append(self._suggest_improvements(total_pnl))

        report.append("\n" + "=" * 60)
        report_text = "\n".join(report)

        # Save to file
        filename = os.path.join(
            self.report_dir, f"report_{today}.txt"
        )
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_text)

        print(f"\n[Logger] Report saved: {filename}")
        print(report_text)
        return report_text

    # ──────────────────────────────────────────────────────────────────────────
    # REPORT ANALYSIS HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _analyse_what_worked(self, total_pnl: float) -> str:
        lines = []

        if total_pnl > 0:
            lines.append(f"  ✅ Strategy was profitable today "
                         f"(+₹{total_pnl:,.2f})")

        if self.trades:
            sells = [t for t in self.trades if t['action'] == 'SELL'
                     and t.get('pnl')]
            wins  = [t for t in sells if t['pnl'] > 0]
            if wins:
                best = max(wins, key=lambda x: x['pnl'])
                lines.append(f"  ✅ Best trade: +₹{best['pnl']:,.2f} "
                             f"on {best['symbol']}")

        if not self.errors:
            lines.append("  ✅ No errors — system ran cleanly all day")

        if len(self.signals) > 0:
            lines.append(f"  ✅ Signal engine fired {len(self.signals)} "
                         f"signals without interruption")

        return "\n".join(lines) if lines else "  No notable positives today."

    def _analyse_what_failed(self) -> str:
        lines = []

        if self.errors:
            lines.append(f"  ❌ {len(self.errors)} errors occurred:")
            for e in self.errors[:3]:  # show first 3
                lines.append(f"     - {e['source']}: {e['message']}")

        sells = [t for t in self.trades
                 if t['action'] == 'SELL' and t.get('pnl')]
        losses = [t for t in sells if t['pnl'] < 0]
        if losses:
            worst = min(losses, key=lambda x: x['pnl'])
            lines.append(f"  ❌ Worst trade: ₹{worst['pnl']:,.2f} "
                         f"({worst.get('reason','')}) on "
                         f"{worst['symbol']}")

        stop_hits = [t for t in sells
                     if t.get('reason') == 'STOP_LOSS']
        if stop_hits:
            lines.append(f"  ❌ Stop loss triggered "
                         f"{len(stop_hits)} time(s) — "
                         f"strategy may be entering too early")

        return "\n".join(lines) if lines else "  No major failures today."

    def _suggest_improvements(self, total_pnl: float) -> str:
        lines = []

        if total_pnl < 0:
            lines.append("  → Review entry conditions — "
                         "consider adding a trend filter")
            lines.append("  → Check if stop loss is too tight")

        stop_hits = [t for t in self.trades
                     if t.get('reason') == 'STOP_LOSS']
        if len(stop_hits) > 2:
            lines.append("  → Stop loss triggered too often — "
                         "widen from 2% to 3%")

        if len(self.trades) == 0:
            lines.append("  → No trades today — consider "
                         "loosening entry conditions or "
                         "switching to a shorter timeframe")

        if len(self.errors) > 0:
            lines.append("  → Fix data fetch errors before "
                         "tomorrow's session")

        lines.append("  → Run backtest on last 30 days to "
                     "verify strategy still valid")

        return "\n".join(lines)

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _setup_file_logger(self) -> None:
        today    = date.today().isoformat()
        log_file = os.path.join(self.log_dir, f"trading_{today}.log")

        self.file_logger = logging.getLogger(f"trading_{today}")
        self.file_logger.setLevel(logging.DEBUG)

        if not self.file_logger.handlers:
            # File handler — writes everything
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            fmt = logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s',
                datefmt='%H:%M:%S'
            )
            fh.setFormatter(fmt)
            self.file_logger.addHandler(fh)

        print(f"[Logger] Log file: {log_file}")

    def _append_json(self, filename: str, entry: dict) -> None:
        """Appends a single entry to a JSON lines file."""
        path = os.path.join(self.log_dir, filename)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + "\n")