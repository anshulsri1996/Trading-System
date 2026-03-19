# data/data_manager.py

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config


class DataManager:

    def __init__(self, symbol: str = None):
        self.symbol = symbol or config.DEFAULT_SYMBOL
        print(f"[DataManager] Initialised for symbol: {self.symbol}")

    def get_historical_data(self, start=None, end=None, interval="1d"):
        start = start or config.HISTORICAL_START
        end   = end   or config.HISTORICAL_END

        print(f"[DataManager] Downloading {interval} data for {self.symbol} "
              f"from {start} to {end} ...")

        raw = yf.download(
            tickers     = self.symbol,
            start       = start,
            end         = end,
            interval    = interval,
            auto_adjust = True,
            progress    = False
        )

        if raw.empty:
            print("[DataManager] WARNING: No data returned. "
                  "Check your symbol or date range.")
            return pd.DataFrame()

        df = self._clean_dataframe(raw)
        print(f"[DataManager] Downloaded {len(df)} candles. "
              f"Date range: {df.index[0]} → {df.index[-1]}")
        return df

    def get_recent_data(self, days=90, interval="1d"):
        end   = datetime.today().strftime("%Y-%m-%d")
        start = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        return self.get_historical_data(start=start, end=end, interval=interval)

    def describe(self, df):
        if df.empty:
            print("[DataManager] DataFrame is empty.")
            return

        print("\n" + "="*55)
        print("  DATA SUMMARY")
        print("="*55)
        print(f"  Symbol       : {self.symbol}")
        print(f"  Candles      : {len(df)}")
        print(f"  From         : {df.index[0]}")
        print(f"  To           : {df.index[-1]}")
        print(f"  Missing rows : {df.isnull().sum().sum()}")
        print(f"  Columns      : {list(df.columns)}")
        print("-"*55)
        print(df[['open','high','low','close','volume']].describe().round(2))
        print("="*55 + "\n")

    def _clean_dataframe(self, raw):
        df = raw.copy()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df.columns = [c.lower() for c in df.columns]

        needed = ['open', 'high', 'low', 'close', 'volume']
        df = df[[c for c in needed if c in df.columns]]

        df = df.dropna(subset=['close'])
        df = df.sort_index()
        df.index = pd.to_datetime(df.index)
        df.index.name = 'datetime'

        return df