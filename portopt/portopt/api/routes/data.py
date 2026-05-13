"""External data endpoint — fetch prices from yfinance/BACEN.

Caches results in Redis (if configured) or in-memory LRU for the session.
Yfinance is slow and rate-limited; caching is essential for educational
demos that re-run the same queries.
"""

from functools import lru_cache
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

import portopt as po
from portopt.api.schemas import BaseSchema
from portopt.api.settings import settings

router = APIRouter(prefix="/data", tags=["data"])


class PriceFetchRequest(BaseSchema):
    tickers: list[str] = Field(min_length=1, max_length=40)
    start: str = Field(description="ISO date YYYY-MM-DD")
    end: str | None = None
    source: Literal["yfinance", "bacen"] = "yfinance"


class PriceFetchResponse(BaseSchema):
    columns: list[str]
    dates: list[str]
    values: list[list[float | None]]
    source: str
    n_rows: int


@lru_cache(maxsize=128)
def _cached_fetch(tickers_tuple: tuple, start: str, end: str | None, source: str) -> pd.DataFrame:
    """In-memory LRU cache; for production deploy add Redis layer."""
    return po.data.load_prices(list(tickers_tuple), start=start, end=end, source=source)


@router.post("/prices", response_model=PriceFetchResponse)
def fetch_prices(req: PriceFetchRequest):
    """Fetch external price series.

    Notes:
    - yfinance: BR equities use the .SA suffix (e.g. PETR4.SA, VALE3.SA)
    - bacen: use SGS names like CDI, SELIC, IPCA, USD_PTAX

    Results are cached for the lifetime of the API process.
    """
    if len(req.tickers) > settings.max_tickers_per_request:
        raise HTTPException(
            400, f"max {settings.max_tickers_per_request} tickers per request"
        )
    try:
        prices = _cached_fetch(tuple(req.tickers), req.start, req.end, req.source)
    except Exception as e:
        raise HTTPException(502, f"Data source error ({req.source}): {e}")

    return PriceFetchResponse(
        columns=list(prices.columns),
        dates=[d.strftime("%Y-%m-%d") for d in prices.index],
        values=[
            [float(v) if pd.notna(v) else None for v in row]
            for row in prices.values
        ],
        source=req.source,
        n_rows=len(prices),
    )
