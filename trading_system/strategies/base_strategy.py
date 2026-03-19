# strategies/base_strategy.py

import pandas as pd
from abc import ABC, abstractmethod


class BaseStrategy(ABC):
    """
    Every strategy in this system inherits from this class.
    
    Think of this as a contract:
    - Every strategy MUST implement generate_signals()
    - generate_signals() MUST return a DataFrame with a 'signal' column
    
    Signal values:
        1  = BUY
       -1  = SELL
        0  = HOLD (do nothing)
    """

    def __init__(self, name: str, params: dict = None):
        self.name   = name
        self.params = params or {}
        print(f"[Strategy] Loaded: {self.name} | Params: {self.params}")

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Takes an OHLCV DataFrame, returns the same DataFrame
        with these extra columns added:
            signal   : 1 (buy), -1 (sell), 0 (hold)
            + any indicator columns the strategy uses
        """
        pass

    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Checks that the DataFrame has everything the strategy needs.
        Called automatically before generate_signals().
        """
        required = ['open', 'high', 'low', 'close', 'volume']
        missing  = [c for c in required if c not in df.columns]

        if missing:
            print(f"[Strategy] ERROR: Missing columns: {missing}")
            return False

        if len(df) < 50:
            print(f"[Strategy] WARNING: Only {len(df)} candles. "
                  f"Need at least 50 for reliable signals.")

        return True