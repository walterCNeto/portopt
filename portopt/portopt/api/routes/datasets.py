"""Dataset endpoints — expose the Chagas (2024) bundled datasets via HTTP."""

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from portopt import datasets as ds
from portopt.api.schemas import DatasetInfo, DatasetPrices

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("", response_model=list[DatasetInfo])
def list_datasets():
    """List all curated datasets bundled with the package."""
    out = []
    for name in ds.list_datasets():
        info = ds.info(name)
        prices = ds.load(name)
        out.append(DatasetInfo(
            name=name,
            description=info["description"],
            period=info["period"],
            exercise=info["exercise"],
            subsets=info["subsets"],
            n_assets=prices.shape[1],
            n_dates=prices.shape[0],
        ))
    return out


@router.get("/{name}", response_model=DatasetInfo)
def get_dataset_info(name: str):
    """Get metadata for a specific dataset."""
    try:
        info = ds.info(name)
    except ValueError as e:
        raise HTTPException(404, str(e))
    prices = ds.load(name)
    return DatasetInfo(
        name=name,
        description=info["description"],
        period=info["period"],
        exercise=info["exercise"],
        subsets=info["subsets"],
        n_assets=prices.shape[1],
        n_dates=prices.shape[0],
    )


@router.get("/{name}/prices", response_model=DatasetPrices)
def get_dataset_prices(
    name: str,
    subset: str | None = Query(None, description="Named subset (br_stocks, metals, etc)"),
    start: str | None = Query(None, description="ISO date filter"),
    end: str | None = Query(None, description="ISO date filter"),
    downsample: int = Query(0, ge=0, description="Keep 1 every N rows; 0 = no downsample"),
):
    """Return the price matrix of a dataset (full or by subset).

    For large datasets, pass `downsample` to reduce transfer size
    (useful for charts; preserve full granularity for optimization).
    """
    try:
        if subset:
            prices = ds.subset(name, subset)
        else:
            prices = ds.load(name)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(404, str(e))

    if start:
        prices = prices.loc[pd.to_datetime(start):]
    if end:
        prices = prices.loc[:pd.to_datetime(end)]
    if downsample > 1:
        prices = prices.iloc[::downsample]

    return DatasetPrices(
        name=name,
        subset=subset,
        columns=list(prices.columns),
        dates=[d.date() for d in prices.index],
        values=[
            [float(v) if pd.notna(v) else None for v in row]
            for row in prices.values
        ],
    )
