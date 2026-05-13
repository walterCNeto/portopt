"""Smoke tests for the FastAPI app.

Validates that every endpoint:
- Returns 200 for a valid request
- Includes pedagogy when applicable
- Validates input properly (400 on bad request)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from portopt.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Health / meta
# ---------------------------------------------------------------------------

def test_root():
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data
    assert "docs" in data


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["n_models"] >= 14
    assert data["n_datasets"] == 3


def test_openapi_schema():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"]
    # All major routes present
    paths = set(schema["paths"].keys())
    assert "/api/models" in paths
    assert "/api/optimize" in paths
    assert "/api/backtest" in paths
    assert "/api/compare" in paths
    assert "/api/datasets" in paths


# ---------------------------------------------------------------------------
# Models catalog (the menu)
# ---------------------------------------------------------------------------

def test_list_models_returns_full_menu_with_pedagogy():
    r = client.get("/api/models")
    assert r.status_code == 200
    models = r.json()
    assert len(models) >= 14

    # Educational positioning: every model has pedagogy
    for m in models:
        assert "pedagogy" in m
        assert m["pedagogy"]["model_name"]
        assert m["pedagogy"]["one_liner"]
        assert m["pedagogy"]["tier"] in (
            "naive", "allocation", "alt_risk", "risk_budget", "robust", "roadmap"
        )

    # Tier ordering: naive first
    tiers = [m["tier"] for m in models]
    naive_idx = tiers.index("naive")
    if "robust" in tiers:
        assert naive_idx < tiers.index("robust")


def test_get_model_info_markowitz():
    r = client.get("/api/models/markowitz")
    assert r.status_code == 200
    m = r.json()
    assert m["name"] == "markowitz"
    assert m["tier"] == "allocation"
    assert "Markowitz" in m["pedagogy"]["model_name"]
    assert "1952" in str(m["pedagogy"]["references"])  # Markowitz 1952


def test_get_unknown_model_404():
    r = client.get("/api/models/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Optimize endpoint with bundled dataset (no network)
# ---------------------------------------------------------------------------

def test_optimize_with_dataset():
    """Use the bundled ex1 dataset to avoid yfinance network calls in CI."""
    req = {
        "model": "markowitz",
        "data": {
            "source": "dataset",
            "dataset": "ex1",
            "subset": "br_stocks",
            "tickers": [],
            "start": "2018-01-01",
            "end": "2023-12-31",
        },
        "constraints": {"bounds": [0.0, 0.4]},
    }
    r = client.post("/api/optimize", json=req)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["converged"]
    assert abs(sum(data["weights"].values()) - 1.0) < 1e-3
    # Pedagogy attached
    assert data["pedagogy"]["model_name"]
    # Diagnostics include solver info
    assert "backend" in data["diagnostics"]


def test_optimize_hrp_with_dataset():
    """HRP uses a different solver path; ensure it works through the API."""
    req = {
        "model": "hrp",
        "data": {
            "source": "dataset",
            "dataset": "mdr",
            "tickers": [],
            "start": "2014-01-01",
        },
    }
    r = client.post("/api/optimize", json=req)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["converged"]
    assert data["pedagogy"]["tier"] == "risk_budget"


def test_optimize_invalid_model_returns_400():
    req = {
        "model": "no_such_model",
        "data": {
            "source": "dataset", "dataset": "ex1", "subset": "br_stocks",
            "tickers": [], "start": "2018-01-01",
        },
    }
    r = client.post("/api/optimize", json=req)
    assert r.status_code == 400


def test_optimize_invalid_constraint_returns_422():
    """bounds[0] > bounds[1] should be rejected by Pydantic."""
    req = {
        "model": "markowitz",
        "data": {
            "source": "dataset", "dataset": "ex1", "subset": "br_stocks",
            "tickers": [], "start": "2018-01-01",
        },
        "constraints": {"bounds": [0.5, 0.2]},  # invalid
    }
    r = client.post("/api/optimize", json=req)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Compare endpoint
# ---------------------------------------------------------------------------

def test_compare_multiple_models():
    req = {
        "models": [
            {"model": "ew"},
            {"model": "markowitz"},
            {"model": "hrp"},
        ],
        "data": {
            "source": "dataset", "dataset": "ex1", "subset": "br_stocks",
            "tickers": [], "start": "2018-01-01",
        },
        "constraints": {"bounds": [0.0, 0.4]},
    }
    r = client.post("/api/compare", json=req)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data["optimizations"].keys()) == {"ew", "markowitz", "hrp"}
    assert len(data["summary_table"]) == 3
    # Weights table: asset → {model → weight}
    assert len(data["weights_table"]) >= 5


def test_compare_too_many_models_returns_400():
    """Pydantic validation enforces max_length=8 at schema level → 422."""
    req = {
        "models": [{"model": "ew"} for _ in range(9)],
        "data": {
            "source": "dataset", "dataset": "ex1", "subset": "br_stocks",
            "tickers": [], "start": "2018-01-01",
        },
    }
    r = client.post("/api/compare", json=req)
    assert r.status_code in (400, 422)


# ---------------------------------------------------------------------------
# Backtest endpoint
# ---------------------------------------------------------------------------

def test_backtest_endpoint():
    req = {
        "model": "ew",
        "data": {
            "source": "dataset", "dataset": "ex1", "subset": "br_stocks",
            "tickers": [], "start": "2018-01-01",
        },
        "config": {"training_window": 252, "rebalance": "monthly"},
    }
    r = client.post("/api/backtest", json=req)
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["points"]) > 0
    assert len(data["rebalance_dates"]) > 0
    assert "sharpe" in data["metrics"]
    assert data["pedagogy"]["model_name"]


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

def test_list_datasets():
    r = client.get("/api/datasets")
    assert r.status_code == 200
    ds = r.json()
    assert len(ds) == 3
    names = {d["name"] for d in ds}
    assert names == {"ex1", "mdr", "mcvar"}
    for d in ds:
        assert d["n_assets"] > 0
        assert d["n_dates"] > 0


def test_get_dataset_info():
    r = client.get("/api/datasets/ex1")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "ex1"
    assert "BR" in d["description"] or "Brazil" in d["description"]


def test_get_dataset_prices_subset():
    r = client.get("/api/datasets/mdr/prices?subset=metals&downsample=20")
    assert r.status_code == 200
    d = r.json()
    assert "Gold" in d["columns"]
    assert len(d["dates"]) > 0
    assert len(d["values"]) == len(d["dates"])


def test_unknown_dataset_404():
    r = client.get("/api/datasets/no_such_dataset")
    assert r.status_code == 404
