# strategies/strategy_generator.py

import pandas as pd
import numpy as np
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from strategies.base_strategy import BaseStrategy


# ══════════════════════════════════════════════════════════════════════════════
# READY-MADE STRATEGY 1 — EMA Crossover
# ══════════════════════════════════════════════════════════════════════════════
class EMACrossoverStrategy(BaseStrategy):
    """
    Logic:
        BUY  when fast EMA crosses ABOVE slow EMA
        SELL when fast EMA crosses BELOW slow EMA

    Default params:
        fast_period = 20  (faster moving average)
        slow_period = 50  (slower moving average)

    Intuition:
        When the short-term average price rises above the long-term average,
        momentum is bullish → BUY.
        When it falls below → SELL.
    """

    def __init__(self, fast_period=20, slow_period=50):
        super().__init__(
            name   = "EMA Crossover",
            params = {"fast": fast_period, "slow": slow_period}
        )
        self.fast = fast_period
        self.slow = slow_period

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.validate_data(df):
            return df

        df = df.copy()

        # Calculate the two EMAs
        df['ema_fast'] = df['close'].ewm(span=self.fast, adjust=False).mean()
        df['ema_slow'] = df['close'].ewm(span=self.slow, adjust=False).mean()

        # Detect crossovers
        # prev_diff: was fast above or below slow on the previous candle?
        prev_diff = df['ema_fast'].shift(1) - df['ema_slow'].shift(1)
        curr_diff = df['ema_fast'] - df['ema_slow']

        df['signal'] = 0
        df.loc[(prev_diff < 0) & (curr_diff > 0), 'signal'] =  1  # BUY
        df.loc[(prev_diff > 0) & (curr_diff < 0), 'signal'] = -1  # SELL

        # Drop rows where EMAs aren't ready yet
        df = df.dropna(subset=['ema_fast', 'ema_slow'])

        buys  = (df['signal'] ==  1).sum()
        sells = (df['signal'] == -1).sum()
        print(f"[{self.name}] Generated {buys} BUY and {sells} SELL signals "
              f"from {len(df)} candles.")
        return df


# ══════════════════════════════════════════════════════════════════════════════
# READY-MADE STRATEGY 2 — Bollinger Bands
# ══════════════════════════════════════════════════════════════════════════════
class BollingerBandsStrategy(BaseStrategy):
    """
    Logic:
        BUY  when price touches or goes BELOW the lower band
        SELL when price touches or goes ABOVE the upper band

    Default params:
        period = 20   (rolling window for mean and std)
        std_dev = 2.0 (number of standard deviations for bands)

    Intuition:
        Price tends to revert to its mean. When it stretches too far
        in one direction (beyond 2 std devs), it's likely to snap back.
    """

    def __init__(self, period=20, std_dev=2.0):
        super().__init__(
            name   = "Bollinger Bands",
            params = {"period": period, "std_dev": std_dev}
        )
        self.period  = period
        self.std_dev = std_dev

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.validate_data(df):
            return df

        df = df.copy()

        # Calculate bands
        df['bb_mid']   = df['close'].rolling(self.period).mean()
        df['bb_std']   = df['close'].rolling(self.period).std()
        df['bb_upper'] = df['bb_mid'] + (self.std_dev * df['bb_std'])
        df['bb_lower'] = df['bb_mid'] - (self.std_dev * df['bb_std'])

        # Generate signals
        df['signal'] = 0
        df.loc[df['close'] <= df['bb_lower'], 'signal'] =  1  # BUY
        df.loc[df['close'] >= df['bb_upper'], 'signal'] = -1  # SELL

        df = df.dropna(subset=['bb_mid'])

        buys  = (df['signal'] ==  1).sum()
        sells = (df['signal'] == -1).sum()
        print(f"[{self.name}] Generated {buys} BUY and {sells} SELL signals "
              f"from {len(df)} candles.")
        return df


# ══════════════════════════════════════════════════════════════════════════════
# READY-MADE STRATEGY 3 — RSI Mean Reversion
# ══════════════════════════════════════════════════════════════════════════════
class RSIStrategy(BaseStrategy):
    """
    Logic:
        BUY  when RSI drops BELOW oversold level (default 30)
        SELL when RSI rises ABOVE overbought level (default 70)

    Default params:
        period     = 14
        oversold   = 30
        overbought = 70

    Intuition:
        RSI measures momentum. Below 30 = the asset has been sold too
        aggressively and may bounce. Above 70 = overbought, may pull back.
    """

    def __init__(self, period=14, oversold=30, overbought=70):
        super().__init__(
            name   = "RSI Mean Reversion",
            params = {"period": period,
                      "oversold": oversold,
                      "overbought": overbought}
        )
        self.period     = period
        self.oversold   = oversold
        self.overbought = overbought

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self.validate_data(df):
            return df

        df = df.copy()

        # Calculate RSI
        delta     = df['close'].diff()
        gain      = delta.clip(lower=0)
        loss      = -delta.clip(upper=0)
        avg_gain  = gain.ewm(span=self.period, adjust=False).mean()
        avg_loss  = loss.ewm(span=self.period, adjust=False).mean()
        rs        = avg_gain / avg_loss.replace(0, np.nan)
        df['rsi'] = 100 - (100 / (1 + rs))

        # Generate signals
        df['signal'] = 0
        df.loc[df['rsi'] < self.oversold,   'signal'] =  1  # BUY
        df.loc[df['rsi'] > self.overbought, 'signal'] = -1  # SELL

        df = df.dropna(subset=['rsi'])

        buys  = (df['signal'] ==  1).sum()
        sells = (df['signal'] == -1).sum()
        print(f"[{self.name}] Generated {buys} BUY and {sells} SELL signals "
              f"from {len(df)} candles.")
        return df


# ══════════════════════════════════════════════════════════════════════════════
# AI STRATEGY GENERATOR
# Converts plain English → Python strategy class using Claude API
# ══════════════════════════════════════════════════════════════════════════════
class StrategyGenerator:
    """
    Takes a plain English description of a trading strategy and
    returns a ready-to-use strategy object.

    Two modes:
    1. PRESET  — picks from the 3 built-in strategies automatically
    2. AI MODE — calls Claude API to generate a brand new strategy
                 (requires ANTHROPIC_API_KEY in config.py)
    """

    PRESETS = {
        "ema"        : EMACrossoverStrategy,
        "crossover"  : EMACrossoverStrategy,
        "bollinger"  : BollingerBandsStrategy,
        "bb"         : BollingerBandsStrategy,
        "bands"      : BollingerBandsStrategy,
        "rsi"        : RSIStrategy,
        "momentum"   : RSIStrategy,
    }

    def from_text(self, description: str) -> BaseStrategy:
        """
        Main entry point. Pass any plain English description.
        
        Only uses presets for VERY short simple inputs like
        "ema" or "rsi". For anything longer or more complex,
        always uses the AI generator.
        """
        print(f"\n[StrategyGenerator] Input: '{description}'")
        desc_lower = description.lower().strip()

        # Only match preset if input is very short AND is just
        # a keyword — not a full strategy description
        # A full description will have more than 5 words
        word_count = len(desc_lower.split())

        if word_count <= 5:
            for keyword, strategy_class in self.PRESETS.items():
                if keyword in desc_lower:
                    print(f"[StrategyGenerator] Matched preset: "
                        f"{strategy_class.__name__}")
                    return strategy_class()

        # For any full description — always use AI
        print("[StrategyGenerator] Full description detected. "
            "Sending to Claude API...")
        return self._generate_with_ai(description)

    def _generate_with_ai(self, description: str) -> BaseStrategy:
        """
        Calls Claude API to generate a brand new strategy
        from a plain English description.
        """
        try:
            import config
            api_key = getattr(config, 'ANTHROPIC_API_KEY', '')

            if not api_key:
                print("[StrategyGenerator] No ANTHROPIC_API_KEY found in config.py")
                print("[StrategyGenerator] Falling back to EMA Crossover.")
                return EMACrossoverStrategy()

            import anthropic
            client = anthropic.Anthropic(api_key=api_key)

            print("[StrategyGenerator] Sending idea to Claude API...")

            prompt = f"""
    You are an expert quantitative developer. Convert this trading idea into a
    complete Python strategy class.

    Trading idea: {description}

    STRICT RULES:
    1. Class must be named CustomStrategy
    2. Must inherit from BaseStrategy
    3. Must implement generate_signals(self, df) method
    4. df already has columns: open, high, low, close, volume (all lowercase)
    5. You must ADD a 'signal' column to df:
    - 1  = BUY
    - -1 = SELL
    - 0  = HOLD
    6. Use only pandas and numpy (already imported as pd and np)
    7. Call super().__init__(name="Custom Strategy", params={{}}) in __init__
    8. At the end, print how many BUY and SELL signals were generated
    9. Return df with the signal column added
    10. Output ONLY the Python class code — no explanation, no markdown fences

    Example structure:
    class CustomStrategy(BaseStrategy):
        def __init__(self):
            super().__init__(name="Custom Strategy", params={{}})

        def generate_signals(self, df):
            if not self.validate_data(df):
                return df
            df = df.copy()
            # YOUR LOGIC HERE
            df['signal'] = 0
            # set signal = 1 for BUY conditions
            # set signal = -1 for SELL conditions
            buys  = (df['signal'] ==  1).sum()
            sells = (df['signal'] == -1).sum()
            print(f"[Custom Strategy] {{buys}} BUY and {{sells}} SELL signals")
            return df
    """

            message = client.messages.create(
                model      = "claude-sonnet-4-20250514",
                max_tokens = 2000,
                messages   = [{"role": "user", "content": prompt}]
            )

            # Get the generated code
            code = message.content[0].text

            # Clean markdown fences if Claude added them
            code = code.replace("```python", "").replace("```", "").strip()

            print("[StrategyGenerator] Code received from Claude. Compiling...")
            print("\n--- Generated Strategy Code ---")
            print(code)
            print("--- End of Generated Code ---\n")

            # Execute the generated code in a safe namespace
            namespace = {
                'pd'           : pd,
                'np'           : np,
                'BaseStrategy' : BaseStrategy
            }
            exec(code, namespace)

            # Find the new class in the namespace
            for name, obj in namespace.items():
                if (isinstance(obj, type)
                        and issubclass(obj, BaseStrategy)
                        and obj is not BaseStrategy):
                    print(f"[StrategyGenerator] ✅ Strategy '{name}' "
                        f"compiled successfully!")
                    return obj()

            print("[StrategyGenerator] Could not find strategy class. "
                "Falling back to EMA Crossover.")
            return EMACrossoverStrategy()

        except Exception as e:
            print(f"[StrategyGenerator] AI generation failed: {e}")
            print("[StrategyGenerator] Falling back to EMA Crossover.")
            return EMACrossoverStrategy()