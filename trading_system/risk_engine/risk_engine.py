# risk_engine/risk_engine.py

import sys, os
from datetime import datetime, date

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class RiskEngine:
    """
    M6 — Risk Engine

    Every single trade must pass through this engine before
    being executed. If any rule is violated, the trade is
    blocked and the reason is logged.

    Rules enforced:
        1. Max capital per trade
        2. Daily loss limit
        3. Max positions at once
        4. Stop-loss per trade
        5. Kill switch (manual or automatic)
    """

    def __init__(
        self,
        capital:           float = None,
        max_risk_per_trade: float = None,
        daily_loss_limit:  float = None,
        stop_loss_pct:     float = 0.02,   # 2% stop loss per trade
        max_positions:     int   = 1,      # only 1 trade at a time
    ):
        self.capital            = capital or float(config.CAPITAL)
        self.initial_capital    = self.capital
        self.max_risk_per_trade = max_risk_per_trade or config.MAX_RISK_PER_TRADE
        self.daily_loss_limit   = daily_loss_limit or config.DAILY_LOSS_LIMIT
        self.stop_loss_pct      = stop_loss_pct
        self.max_positions      = max_positions

        # State tracking
        self.daily_pnl          = 0.0
        self.daily_trades       = 0
        self.last_reset_date    = date.today()
        self.kill_switch        = False
        self.risk_log           = []       # every decision logged here

        print(f"\n[RiskEngine] Initialised")
        print(f"  Capital          : ₹{self.capital:,.0f}")
        print(f"  Max risk/trade   : {self.max_risk_per_trade*100:.0f}%")
        print(f"  Daily loss limit : {self.daily_loss_limit*100:.0f}%")
        print(f"  Stop loss        : {self.stop_loss_pct*100:.0f}% per trade")

    # ──────────────────────────────────────────────────────────────────────────
    # MAIN CHECK — call this before every trade
    # ──────────────────────────────────────────────────────────────────────────
    def can_trade(self, signal: int, current_positions: int = 0) -> dict:
        """
        Master check. Call this before placing any trade.

        Returns:
            {
                'allowed' : True/False,
                'reason'  : explanation string
            }
        """
        # Reset daily counters if it's a new day
        self._reset_if_new_day()

        # ── Rule 1: Kill switch ────────────────────────────────────────────
        if self.kill_switch:
            return self._block("KILL_SWITCH",
                               "Kill switch is active. All trading halted.")

        # ── Rule 2: Only check BUY signals for entry rules ─────────────────
        if signal == 1:

            # Rule 3: Max positions
            if current_positions >= self.max_positions:
                return self._block("MAX_POSITIONS",
                                   f"Already holding {current_positions} "
                                   f"position(s). Max allowed: "
                                   f"{self.max_positions}.")

            # Rule 4: Daily loss limit
            daily_loss_pct = abs(self.daily_pnl) / self.initial_capital
            if self.daily_pnl < 0 and daily_loss_pct >= self.daily_loss_limit:
                self._activate_kill_switch(
                    f"Daily loss limit hit: "
                    f"₹{abs(self.daily_pnl):,.0f} "
                    f"({daily_loss_pct*100:.1f}%)"
                )
                return self._block("DAILY_LOSS_LIMIT",
                                   f"Daily loss of {daily_loss_pct*100:.1f}% "
                                   f"exceeds limit of "
                                   f"{self.daily_loss_limit*100:.0f}%.")

        return self._allow()

    # ──────────────────────────────────────────────────────────────────────────
    # POSITION SIZING — how many shares to buy
    # ──────────────────────────────────────────────────────────────────────────
    def calculate_position_size(
        self,
        price:   float,
        capital: float
    ) -> dict:
        """
        Calculates how many shares to buy based on risk rules.

        Uses fixed fractional position sizing:
            Risk amount = capital × max_risk_per_trade
            Stop loss   = price × stop_loss_pct
            Shares      = risk_amount / (price × stop_loss_pct)

        This ensures a single losing trade never loses more than
        max_risk_per_trade % of capital.
        """
        # Max amount we're willing to lose on this trade
        risk_amount = capital * self.max_risk_per_trade

        # How much price must move against us to hit stop loss
        risk_per_share = price * self.stop_loss_pct

        # How many shares we can buy within our risk limit
        shares = int(risk_amount / risk_per_share)

        # Make sure we have enough capital to buy those shares
        cost         = shares * price * 1.001   # include brokerage
        if cost > capital:
            shares   = int(capital * 0.95 / (price * 1.001))  # use 95% of capital

        stop_loss_price = round(price * (1 - self.stop_loss_pct), 2)

        result = {
            'shares'          : shares,
            'entry_price'     : price,
            'stop_loss_price' : stop_loss_price,
            'risk_amount'     : round(risk_amount, 2),
            'total_cost'      : round(shares * price, 2)
        }

        print(f"  [RiskEngine] Position size: {shares} shares @ ₹{price:,.2f}")
        print(f"  [RiskEngine] Stop loss    : ₹{stop_loss_price:,.2f} "
              f"(-{self.stop_loss_pct*100:.0f}%)")
        print(f"  [RiskEngine] Max risk     : ₹{risk_amount:,.2f}")

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # STOP LOSS CHECK — call this on every candle while in a position
    # ──────────────────────────────────────────────────────────────────────────
    def check_stop_loss(
        self,
        current_price: float,
        stop_loss_price: float
    ) -> bool:
        """
        Returns True if stop loss has been hit and we should exit.
        """
        if current_price <= stop_loss_price:
            print(f"  [RiskEngine] ⛔ STOP LOSS HIT — "
                  f"Price ₹{current_price:,.2f} ≤ "
                  f"Stop ₹{stop_loss_price:,.2f}")
            return True
        return False

    # ──────────────────────────────────────────────────────────────────────────
    # UPDATE DAILY PNL — call after every closed trade
    # ──────────────────────────────────────────────────────────────────────────
    def update_pnl(self, pnl: float) -> None:
        """
        Updates the daily PnL tracker.
        Automatically activates kill switch if daily limit is breached.
        """
        self.daily_pnl    += pnl
        self.daily_trades += 1

        print(f"  [RiskEngine] Daily PnL: ₹{self.daily_pnl:+,.2f} "
              f"({self.daily_trades} trades today)")

        # Auto kill switch
        daily_loss_pct = abs(self.daily_pnl) / self.initial_capital
        if self.daily_pnl < 0 and daily_loss_pct >= self.daily_loss_limit:
            self._activate_kill_switch(
                f"Daily loss limit breached: "
                f"{daily_loss_pct*100:.1f}%"
            )

    # ──────────────────────────────────────────────────────────────────────────
    # KILL SWITCH — manual activation
    # ──────────────────────────────────────────────────────────────────────────
    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        self._activate_kill_switch(reason)

    def deactivate_kill_switch(self) -> None:
        self.kill_switch = False
        print("[RiskEngine] ✅ Kill switch deactivated. Trading resumed.")

    # ──────────────────────────────────────────────────────────────────────────
    # DAILY SUMMARY
    # ──────────────────────────────────────────────────────────────────────────
    def daily_summary(self) -> dict:
        return {
            'date'         : self.last_reset_date,
            'daily_pnl'    : round(self.daily_pnl, 2),
            'daily_trades' : self.daily_trades,
            'kill_switch'  : self.kill_switch
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PRIVATE HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _allow(self) -> dict:
        return {'allowed': True, 'reason': 'All checks passed'}

    def _block(self, rule: str, reason: str) -> dict:
        self.risk_log.append({
            'time'   : datetime.now(),
            'rule'   : rule,
            'reason' : reason
        })
        print(f"  [RiskEngine] ❌ TRADE BLOCKED — {rule}: {reason}")
        return {'allowed': False, 'reason': reason}

    def _activate_kill_switch(self, reason: str) -> None:
        self.kill_switch = True
        print(f"\n  [RiskEngine] 🚨 KILL SWITCH ACTIVATED")
        print(f"  Reason: {reason}")
        print(f"  All trading halted for today.\n")

    def _reset_if_new_day(self) -> None:
        today = date.today()
        if today != self.last_reset_date:
            print(f"[RiskEngine] New trading day — resetting daily counters.")
            self.daily_pnl       = 0.0
            self.daily_trades    = 0
            self.kill_switch     = False
            self.last_reset_date = today