"""Data loaders for portfolio optimization.

Sources supported:
- yfinance (offshore + BR via .SA suffix)
- brapi.dev (BR equities/FIIs)
- BACEN SGS (Brazilian risk-free rates and macro)
- Excel files (for reproducing example exercises)

All loaders return aligned, cleaned `pd.DataFrame` of adjusted close prices,
indexed by `pd.DatetimeIndex` in business day frequency.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Base loader
# ---------------------------------------------------------------------------

class PriceLoader(ABC):
    """Abstract price loader. Subclasses fetch from different sources."""

    @abstractmethod
    def load(
        self,
        tickers: Iterable[str],
        start: str | pd.Timestamp,
        end: str | pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        """Return DataFrame of adjusted close prices, columns = tickers."""
        ...


# ---------------------------------------------------------------------------
# YFinance loader (works for offshore + B3 via .SA suffix)
# ---------------------------------------------------------------------------

class YFinanceLoader(PriceLoader):
    """Loader using yfinance. Works for US, BR (.SA), commodities (=F), FX, indices.

    Notes
    -----
    - Uses 'Adj Close' which already accounts for dividends and splits.
    - Forward-fills missing values up to `ffill_limit` business days.
    - Drops rows where *any* ticker is still NaN after ffill (alignment).
    """

    def __init__(self, ffill_limit: int = 3, auto_adjust: bool = True):
        self.ffill_limit = ffill_limit
        self.auto_adjust = auto_adjust

    def load(self, tickers, start, end=None):
        try:
            import yfinance as yf  # lazy import
        except ImportError as e:
            raise ImportError("Install yfinance: pip install yfinance") from e

        tickers = list(tickers)
        raw = yf.download(
            tickers,
            start=start,
            end=end,
            auto_adjust=self.auto_adjust,
            progress=False,
            group_by="ticker",
        )

        # Flatten multi-index columns
        if len(tickers) == 1:
            prices = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            prices = pd.DataFrame(
                {t: raw[t]["Close"] for t in tickers if t in raw.columns.get_level_values(0)}
            )

        prices.index = pd.to_datetime(prices.index)
        prices = prices.sort_index()
        prices = prices.ffill(limit=self.ffill_limit).dropna()
        return prices


# ---------------------------------------------------------------------------
# Excel loader (for example exercises and custom uploads)
# ---------------------------------------------------------------------------

class ExcelLoader(PriceLoader):
    """Loader for Excel files in standard notebook format.

    Expected format:
    - First column: date (will be set as index)
    - Other columns: prices per ticker
    """

    def __init__(self, path: str | Path, sheet_name: str | int = 0, date_col: str = "Dates"):
        self.path = Path(path)
        self.sheet_name = sheet_name
        self.date_col = date_col

    def load(self, tickers=None, start=None, end=None):
        df = pd.read_excel(self.path, sheet_name=self.sheet_name)
        if self.date_col in df.columns:
            df = df.set_index(self.date_col)
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        if tickers is not None:
            df = df[list(tickers)]
        if start is not None:
            df = df.loc[pd.to_datetime(start):]
        if end is not None:
            df = df.loc[:pd.to_datetime(end)]
        return df.ffill().dropna()


# ---------------------------------------------------------------------------
# BACEN SGS loader (Brazilian risk-free / macro)
# ---------------------------------------------------------------------------

# Common BACEN SGS codes
BACEN_SGS_CODES = {
    "CDI": 4389,           # CDI anualizado
    "SELIC": 11,           # Selic diária (overnight)
    "IPCA": 433,           # IPCA mensal
    "IGP-M": 189,          # IGP-M mensal
    "USD_PTAX": 1,         # USD/BRL PTAX
    "EUR_PTAX": 21619,     # EUR/BRL PTAX
}


class BACENLoader(PriceLoader):
    """Loader for Brazilian Central Bank SGS series.

    Notes
    -----
    Returns are converted to "price-like" cumulative series for compatibility
    with the rest of the pipeline. For CDI (annualized rate), the daily price
    is built from (1 + rate/100/252) cumulative product.
    """

    def __init__(self, mode: str = "cumulative"):
        """
        Parameters
        ----------
        mode : "cumulative" or "raw"
            "cumulative" builds price-like series from rates; "raw" returns rates.
        """
        self.mode = mode

    def load(self, series_codes, start, end=None):
        try:
            from bcb import sgs  # lazy import
        except ImportError as e:
            raise ImportError("Install python-bcb: pip install python-bcb") from e

        # Convert string names to codes if needed
        codes = []
        names = []
        for s in series_codes:
            if isinstance(s, str) and s in BACEN_SGS_CODES:
                codes.append(BACEN_SGS_CODES[s])
                names.append(s)
            else:
                codes.append(int(s))
                names.append(str(s))

        df = sgs.get(dict(zip(names, codes)), start=start, end=end)
        df.index = pd.to_datetime(df.index)

        if self.mode == "cumulative":
            # Assume annualized rates in %; convert to daily and compound
            daily = (1.0 + df / 100.0 / 252.0)
            return daily.cumprod()
        else:
            return df


# ---------------------------------------------------------------------------
# Brapi loader (BR equities/FIIs without Yahoo's quirks)
# ---------------------------------------------------------------------------

class BrapiLoader(PriceLoader):
    """Loader using brapi.dev API. Requires API token (free tier available).

    TODO: implement when integrating production data sources.
    """

    def __init__(self, token: str | None = None):
        self.token = token

    def load(self, tickers, start, end=None):
        raise NotImplementedError(
            "BrapiLoader is a stub. Implement when ready to integrate brapi.dev API."
        )


# ---------------------------------------------------------------------------
# Universe — facade
# ---------------------------------------------------------------------------

@dataclass
class Universe:
    """Convenience wrapper combining loader + tickers + date range.

    Example
    -------
    >>> u = Universe(
    ...     tickers=["PETR4.SA", "VALE3.SA"],
    ...     loader=YFinanceLoader(),
    ...     start="2020-01-01",
    ... )
    >>> prices = u.prices
    """

    tickers: list[str]
    loader: PriceLoader
    start: str | pd.Timestamp
    end: str | pd.Timestamp | None = None
    _cache: pd.DataFrame | None = None

    @property
    def prices(self) -> pd.DataFrame:
        if self._cache is None:
            self._cache = self.loader.load(self.tickers, self.start, self.end)
        return self._cache

    def __len__(self) -> int:
        return len(self.tickers)


# ---------------------------------------------------------------------------
# Top-level convenience function
# ---------------------------------------------------------------------------

def load_prices(
    tickers: Iterable[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp | None = None,
    source: str = "yfinance",
    **kwargs,
) -> pd.DataFrame:
    """One-call convenience function for the common case.

    Parameters
    ----------
    tickers : list of str
    start : date string or Timestamp
    end : date string or Timestamp, optional
    source : "yfinance" | "excel" | "bacen" | "brapi"
    **kwargs : passed to the loader constructor

    Returns
    -------
    pd.DataFrame of adjusted close prices.
    """
    loaders = {
        "yfinance": YFinanceLoader,
        "excel": ExcelLoader,
        "bacen": BACENLoader,
        "brapi": BrapiLoader,
    }
    if source not in loaders:
        raise ValueError(f"Unknown source: {source!r}. Options: {list(loaders)}")
    loader = loaders[source](**kwargs)
    return loader.load(tickers, start, end)
