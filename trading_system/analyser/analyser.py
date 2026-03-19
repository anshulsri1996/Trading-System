# analyser/analyser.py

import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class StrategyAnalyser:
    """
    M3 — Strategy Analyser

    Takes backtest results and does three things:
    1. Identifies specific weaknesses in the strategy
    2. Scores the strategy on key dimensions
    3. Suggests concrete improvements with new parameters to try
    """

    # Thresholds for what we consider acceptable performance
    MIN_WIN_RATE      = 45.0   # below this → signal quality problem
    MIN_PROFIT_FACTOR = 1.5    # below this → risk/reward problem
    MAX_DRAWDOWN      = -15.0  # worse than this → position sizing problem
    MIN_TRADES        = 10     # below this → not enough data to trust results
    MAX_TRADES        = 100    # above this → overtrading problem
    MIN_RETURN        = 10.0   # below this → underperforming vs buy-and-hold

    def analyse(self, metrics: dict, df: pd.DataFrame = None) -> dict:
        """
        Main entry point. Pass in the metrics dict from Backtester.run()

        Parameters:
            metrics : output of Backtester.run()
            df      : original OHLCV dataframe (used to calculate
                      buy-and-hold benchmark)

        Returns:
            analysis dict with weaknesses, score, and suggestions
        """
        if not metrics:
            print("[Analyser] No metrics to analyse.")
            return {}

        print(f"\n[Analyser] Analysing: {metrics['strategy_name']} ...")

        weaknesses   = self._find_weaknesses(metrics, df)
        score        = self._score_strategy(metrics)
        suggestions  = self._generate_suggestions(metrics, weaknesses)
        benchmark    = self._calculate_benchmark(df) if df is not None else None

        analysis = {
            'strategy_name' : metrics['strategy_name'],
            'score'         : score,
            'weaknesses'    : weaknesses,
            'suggestions'   : suggestions,
            'benchmark'     : benchmark
        }

        self._print_analysis(analysis, metrics)
        return analysis

    # ──────────────────────────────────────────────────────────────────────────
    # WEAKNESS DETECTOR
    # ──────────────────────────────────────────────────────────────────────────
    def _find_weaknesses(self, m: dict, df: pd.DataFrame) -> list:
        weaknesses = []
        trades     = m.get('trades', pd.DataFrame())

        # ── 1. Low win rate ────────────────────────────────────────────────
        if m['win_rate'] < self.MIN_WIN_RATE:
            weaknesses.append({
                'type'   : 'LOW_WIN_RATE',
                'value'  : m['win_rate'],
                'detail' : f"Win rate of {m['win_rate']}% means the strategy "
                           f"is wrong more often than right. Signals may be "
                           f"triggering too early or in choppy markets."
            })

        # ── 2. Poor profit factor ──────────────────────────────────────────
        if m['profit_factor'] < self.MIN_PROFIT_FACTOR:
            weaknesses.append({
                'type'   : 'POOR_RISK_REWARD',
                'value'  : m['profit_factor'],
                'detail' : f"Profit factor of {m['profit_factor']} is too low. "
                           f"Avg win ₹{m['avg_win']:,.0f} vs "
                           f"avg loss ₹{abs(m['avg_loss']):,.0f}. "
                           f"Losses are eating into profits."
            })

        # ── 3. Excessive drawdown ──────────────────────────────────────────
        if m['max_drawdown'] < self.MAX_DRAWDOWN:
            weaknesses.append({
                'type'   : 'HIGH_DRAWDOWN',
                'value'  : m['max_drawdown'],
                'detail' : f"Max drawdown of {m['max_drawdown']}% is too large. "
                           f"This means at some point your ₹"
                           f"{m['initial_capital']:,.0f} dropped by "
                           f"₹{abs(m['max_drawdown']/100 * m['initial_capital']):,.0f}. "
                           f"Psychologically very hard to hold through."
            })

        # ── 4. Too few trades ──────────────────────────────────────────────
        if m['total_trades'] < self.MIN_TRADES:
            weaknesses.append({
                'type'   : 'TOO_FEW_TRADES',
                'value'  : m['total_trades'],
                'detail' : f"Only {m['total_trades']} trades over the entire "
                           f"period. Results are not statistically reliable — "
                           f"a few lucky/unlucky trades are distorting the metrics."
            })

        # ── 5. Overtrading ─────────────────────────────────────────────────
        if m['total_trades'] > self.MAX_TRADES:
            weaknesses.append({
                'type'   : 'OVERTRADING',
                'value'  : m['total_trades'],
                'detail' : f"{m['total_trades']} trades means the strategy is "
                           f"firing signals too often. Brokerage costs will "
                           f"destroy profits in live trading."
            })

        # ── 6. Underperforming buy-and-hold ───────────────────────────────
        if df is not None:
            bh_return = self._calculate_benchmark(df)
            if bh_return and m['total_return'] < bh_return:
                weaknesses.append({
                    'type'   : 'UNDERPERFORMS_BENCHMARK',
                    'value'  : m['total_return'],
                    'detail' : f"Strategy returned {m['total_return']}% but "
                               f"simply holding the stock returned {bh_return:.1f}%. "
                               f"The strategy adds no value over doing nothing."
                })

        # ── 7. Consecutive losses analysis ────────────────────────────────
        if not trades.empty:
            results         = trades['result'].tolist()
            max_consec_loss = self._max_consecutive(results, 'LOSS')
            if max_consec_loss >= 4:
                weaknesses.append({
                    'type'   : 'CONSECUTIVE_LOSSES',
                    'value'  : max_consec_loss,
                    'detail' : f"{max_consec_loss} consecutive losses detected. "
                               f"This suggests the strategy struggles badly "
                               f"during certain market conditions."
                })

        # ── 8. Avg loss > Avg win (broken risk/reward) ─────────────────────
        if abs(m['avg_loss']) > m['avg_win']:
            weaknesses.append({
                'type'   : 'INVERTED_RR',
                'value'  : round(abs(m['avg_loss']) / m['avg_win'], 2),
                'detail' : f"Average loss (₹{abs(m['avg_loss']):,.0f}) is larger "
                           f"than average win (₹{m['avg_win']:,.0f}). "
                           f"You need a win rate above "
                           f"{100 * abs(m['avg_loss']) / (m['avg_win'] + abs(m['avg_loss'])):.0f}% "
                           f"just to break even."
            })

        return weaknesses

    # ──────────────────────────────────────────────────────────────────────────
    # STRATEGY SCORER (0-100)
    # ──────────────────────────────────────────────────────────────────────────
    def _score_strategy(self, m: dict) -> dict:
        scores = {}

        # Win rate score (0-25 points)
        scores['win_rate'] = min(25, max(0,
            (m['win_rate'] - 30) / (70 - 30) * 25
        ))

        # Profit factor score (0-25 points)
        scores['profit_factor'] = min(25, max(0,
            (m['profit_factor'] - 1.0) / (3.0 - 1.0) * 25
        ))

        # Drawdown score (0-25 points) — less drawdown = higher score
        scores['drawdown'] = min(25, max(0,
            (m['max_drawdown'] + 30) / 30 * 25
        ))

        # Return score (0-25 points)
        scores['returns'] = min(25, max(0,
            m['total_return'] / 50 * 25
        ))

        total = sum(scores.values())
        scores['total'] = round(total, 1)

        # Letter grade
        if total >= 75:   scores['grade'] = 'A'
        elif total >= 60: scores['grade'] = 'B'
        elif total >= 45: scores['grade'] = 'C'
        elif total >= 30: scores['grade'] = 'D'
        else:             scores['grade'] = 'F'

        return scores

    # ──────────────────────────────────────────────────────────────────────────
    # SUGGESTION ENGINE
    # ──────────────────────────────────────────────────────────────────────────
    def _generate_suggestions(self, m: dict, weaknesses: list) -> list:
        suggestions  = []
        weak_types   = [w['type'] for w in weaknesses]

        if 'LOW_WIN_RATE' in weak_types:
            suggestions.append({
                'priority' : 'HIGH',
                'action'   : 'Add a trend filter',
                'detail'   : "Only take BUY signals when price is above the "
                             "200-day moving average. This avoids buying in "
                             "downtrends and will significantly improve win rate.",
                'code_hint': "df['above_200ma'] = df['close'] > "
                             "df['close'].rolling(200).mean()\n"
                             "# Only buy when above_200ma is True"
            })

        if 'POOR_RISK_REWARD' in weak_types or 'INVERTED_RR' in weak_types:
            suggestions.append({
                'priority' : 'HIGH',
                'action'   : 'Add a stop-loss at 2%',
                'detail'   : "Exit any trade that moves more than 2% against "
                             "you. This caps your average loss and dramatically "
                             "improves the profit factor.",
                'code_hint': "stop_loss = entry_price * 0.98  # 2% stop\n"
                             "if current_price < stop_loss: exit trade"
            })

        if 'HIGH_DRAWDOWN' in weak_types:
            suggestions.append({
                'priority' : 'HIGH',
                'action'   : 'Reduce position size to 50%',
                'detail'   : "Instead of deploying 100% of capital per trade, "
                             "use only 50%. This halves your drawdown while "
                             "keeping the same win/loss ratio.",
                'code_hint': "position = int((capital * 0.5) / cost)  "
                             "# use 50% of capital"
            })

        if 'TOO_FEW_TRADES' in weak_types:
            suggestions.append({
                'priority' : 'MEDIUM',
                'action'   : 'Switch to a shorter timeframe',
                'detail'   : "Try 1-hour or 4-hour candles instead of daily. "
                             "This generates more trades and makes the backtest "
                             "results statistically more reliable.",
                'code_hint': "interval='1h'  # instead of '1d'"
            })

        if 'OVERTRADING' in weak_types:
            suggestions.append({
                'priority' : 'HIGH',
                'action'   : 'Tighten signal conditions',
                'detail'   : "Add a confirmation filter — only trade when two "
                             "indicators agree. For RSI, require RSI < 30 AND "
                             "price below lower Bollinger Band to enter.",
                'code_hint': "signal = (rsi < 30) & (close < bb_lower)"
            })

        if 'UNDERPERFORMS_BENCHMARK' in weak_types:
            suggestions.append({
                'priority' : 'MEDIUM',
                'action'   : 'Optimise entry parameters',
                'detail'   : "Try different parameter combinations. For EMA, "
                             "test fast=10/slow=30 for more signals, or "
                             "fast=50/slow=200 (Golden Cross) for fewer but "
                             "higher quality signals.",
                'code_hint': "# Test: fast=10,slow=30 | fast=20,slow=100 "
                             "| fast=50,slow=200"
            })

        if 'CONSECUTIVE_LOSSES' in weak_types:
            suggestions.append({
                'priority' : 'MEDIUM',
                'action'   : 'Add a daily loss circuit breaker',
                'detail'   : "Stop trading for the day after 3 consecutive "
                             "losses. This protects you during periods when "
                             "the market conditions don't suit the strategy.",
                'code_hint': "if consecutive_losses >= 3: skip signals today"
            })

        # Always suggest this regardless of weaknesses
        suggestions.append({
            'priority' : 'LOW',
            'action'   : 'Test on multiple symbols',
            'detail'   : "Backtest on at least 5 different stocks. A strategy "
                         "that only works on one stock is likely curve-fitted "
                         "to that stock's history.",
            'code_hint': "symbols = ['RELIANCE.NS','TCS.NS','INFY.NS',"
                         "'HDFCBANK.NS','ITC.NS']"
        })

        return suggestions

    # ──────────────────────────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _calculate_benchmark(self, df: pd.DataFrame) -> float:
        """Buy-and-hold return for the same period."""
        if df is None or df.empty:
            return None
        start_price = df.iloc[0]['close']
        end_price   = df.iloc[-1]['close']
        return round(((end_price - start_price) / start_price) * 100, 2)

    def _max_consecutive(self, results: list, target: str) -> int:
        """Find the longest streak of a given result (WIN or LOSS)."""
        max_streak = current = 0
        for r in results:
            if r == target:
                current   += 1
                max_streak = max(max_streak, current)
            else:
                current = 0
        return max_streak

    # ──────────────────────────────────────────────────────────────────────────
    # REPORT PRINTER
    # ──────────────────────────────────────────────────────────────────────────
    def _print_analysis(self, analysis: dict, metrics: dict) -> None:
        m = metrics
        s = analysis['score']

        print("\n" + "★"*55)
        print(f"  STRATEGY ANALYSIS — {analysis['strategy_name']}")
        print("★"*55)

        # Score
        print(f"\n  OVERALL SCORE : {s['total']:.1f}/100  "
              f"[Grade: {s['grade']}]")
        print(f"  Win Rate Score    : {s['win_rate']:.1f}/25")
        print(f"  Profit Factor     : {s['profit_factor']:.1f}/25")
        print(f"  Drawdown Score    : {s['drawdown']:.1f}/25")
        print(f"  Returns Score     : {s['returns']:.1f}/25")

        # Benchmark
        if analysis['benchmark']:
            print(f"\n  Buy-and-Hold Return : {analysis['benchmark']:.1f}%")
            print(f"  Strategy Return     : {m['total_return']:.1f}%")
            diff = m['total_return'] - analysis['benchmark']
            print(f"  Alpha               : {diff:+.1f}%")

        # Weaknesses
        print(f"\n  WEAKNESSES FOUND : {len(analysis['weaknesses'])}")
        print("-"*55)
        for i, w in enumerate(analysis['weaknesses'], 1):
            print(f"\n  {i}. [{w['type']}]")
            print(f"     {w['detail']}")

        # Suggestions
        high = [s for s in analysis['suggestions'] if s['priority']=='HIGH']
        med  = [s for s in analysis['suggestions'] if s['priority']=='MEDIUM']
        low  = [s for s in analysis['suggestions'] if s['priority']=='LOW']

        print(f"\n  IMPROVEMENT SUGGESTIONS ({len(analysis['suggestions'])} total)")
        print("-"*55)
        for group, label in [(high,'🔴 HIGH'), (med,'🟡 MEDIUM'), (low,'🟢 LOW')]:
            for sug in group:
                print(f"\n  {label} priority — {sug['action']}")
                print(f"  {sug['detail']}")
                print(f"  Hint: {sug['code_hint']}")

        print("\n" + "★"*55 + "\n")