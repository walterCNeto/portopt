"""Curated datasets from Prof. Guido Chagas' course (2024).

Three files distributed with the package as reference datasets for testing
and education. Each dataset corresponds to an exercise in the original
notebooks:

| Dataset       | Universe                          | Period                | Notebook | Exercise |
|---------------|-----------------------------------|-----------------------|----------|----------|
| `ex1`         | 24 BR stocks + CDI index          | 2003-12 to 2023-12    | nb1      | MV/EW backtest |
| `mdr`         | 24 commodity futures              | 2012-12 to 2023-12    | nb2      | Downside Risk  |
| `mcvar`       | 24 commodity futures (same)       | 2012-12 to 2023-12    | nb2      | CVaR           |

Usage
-----
    >>> import portopt as po
    >>> prices = po.datasets.load("ex1")
    >>> br_stocks = po.datasets.subset("ex1", "br_stocks")
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import pandas as pd

from portopt.data import ExcelLoader


# Package-shipped data directory
_DATA_DIR = Path(__file__).parent / "data_files" / "chagas_2024"

# Dataset metadata
DATASETS = {
    "ex1": {
        "file": "Ex1.xlsx",
        "sheet": "Sheet1",
        "description": "24 Brazilian stocks + CDI index (BZACCETP)",
        "period": "2003-12-30 to 2023-12-29",
        "exercise": "nb1 — MV/EW/BH backtest comparison",
        "subsets": {
            "br_stocks": "All Brazilian stocks (24, ticker contains 'BS Equity')",
            "cdi": "CDI cumulative index (BZACCETP Index column only)",
            "all": "Full universe including CDI",
        },
    },
    "mdr": {
        "file": "MDR_Example.xlsx",
        "sheet": "Prices",
        "description": "24 commodity futures (MDR exercise dataset)",
        "period": "2012-12-28 to 2023-12-29",
        "exercise": "nb2 — Mean-Downside-Risk optimization",
        "subsets": {
            "all": "All 24 commodity futures",
            "metals": "Aluminum, Copper, Gold, Nickel, Platinum, Silver, Zinc",
            "energy": "Brent Crude Oil, WTI Oil, Gas Oil, Gasoline, Heating Oil, Natural Gas",
            "agri": "Cocoa, Coffee, Corn, Cotton, Soybean, Soymeal, Soy Oil, Sugar, Wheat",
            "livestock": "Cattle, Hogs",
        },
    },
    "mcvar": {
        "file": "MCVaR_Example.xls",
        "sheet": "Prices",
        "description": "24 commodity futures (CVaR exercise dataset, same universe as mdr)",
        "period": "2012-12-28 to 2023-12-29",
        "exercise": "nb2 — Mean-CVaR optimization",
        "subsets": {
            "all": "All 24 commodity futures",
            "metals": "Aluminum, Copper, Gold, Nickel, Platinum, Silver, Zinc",
            "energy": "Brent Crude Oil, WTI Oil, Gas Oil, Gasoline, Heating Oil, Natural Gas",
            "agri": "Cocoa, Coffee, Corn, Cotton, Soybean, Soymeal, Soy Oil, Sugar, Wheat",
            "livestock": "Cattle, Hogs",
        },
    },
}

# Asset group definitions for each dataset
ASSET_GROUPS = {
    "mdr": {
        "metals": ["Aluminum", "Copper", "Gold", "Nickel", "Platinum", "Silver", "Zinc"],
        "energy": ["Brent Crude Oil", "WTI Oil", "Gas Oil", "Gasoline", "Heating Oil", "Natural Gas"],
        "agri": ["Cocoa", "Coffee", "Corn", "Cotton", "Soybean", "Soymeal", "Soy Oil", "Sugar", "Wheat"],
        "livestock": ["Cattle", "Hogs"],
    },
}
# mcvar shares the same groups
ASSET_GROUPS["mcvar"] = ASSET_GROUPS["mdr"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DatasetName = Literal["ex1", "mdr", "mcvar"]


def info(name: str | None = None) -> dict:
    """Return metadata for one or all datasets."""
    if name is None:
        return DATASETS
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset: {name!r}. Available: {list(DATASETS)}")
    return DATASETS[name]


def load(name: DatasetName) -> pd.DataFrame:
    """Load a dataset by name.

    Returns
    -------
    pd.DataFrame
        Price DataFrame indexed by date, columns are asset names.

    Example
    -------
    >>> prices = portopt.datasets.load("ex1")
    >>> log_rets = portopt.returns.to_log_returns(prices)
    """
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset: {name!r}. Available: {list(DATASETS)}")

    meta = DATASETS[name]
    path = _DATA_DIR / meta["file"]
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset file not found: {path}\n"
            f"Make sure the package was installed with the data_files folder."
        )
    return ExcelLoader(path, sheet_name=meta["sheet"]).load()


def subset(name: DatasetName, kind: str) -> pd.DataFrame:
    """Load a named subset of a dataset.

    Examples
    --------
    >>> br = portopt.datasets.subset("ex1", "br_stocks")    # without CDI
    >>> cdi = portopt.datasets.subset("ex1", "cdi")          # only CDI
    >>> metals = portopt.datasets.subset("mdr", "metals")
    """
    prices = load(name)

    if name == "ex1":
        if kind == "br_stocks":
            return prices[[c for c in prices.columns if "BS Equity" in c]].dropna()
        if kind == "cdi":
            return prices[["BZACCETP Index"]].dropna()
        if kind == "all":
            return prices

    if name in ASSET_GROUPS and kind in ASSET_GROUPS[name]:
        cols = ASSET_GROUPS[name][kind]
        existing = [c for c in cols if c in prices.columns]
        return prices[existing].dropna()

    if kind == "all":
        return prices

    raise ValueError(
        f"Unknown subset {kind!r} for dataset {name!r}. "
        f"Available: {list(DATASETS[name]['subsets'])}"
    )


def list_datasets() -> list[str]:
    """List available dataset names."""
    return list(DATASETS)
