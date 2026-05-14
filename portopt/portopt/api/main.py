"""FastAPI application — entry point.

Run locally:
    uvicorn portopt.api.main:app --reload --port 8000

Production:
    uvicorn portopt.api.main:app --host 0.0.0.0 --port 8080 --workers 2
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from portopt.api.routes import (
    backtest as r_backtest,
    compare as r_compare,
    data as r_data,
    datasets as r_datasets,
    health as r_health,
    models as r_models,
    optimize as r_optimize,
)
from portopt.api.settings import settings

logger = logging.getLogger("portopt.api")
logging.basicConfig(level=logging.INFO if not settings.is_production else logging.WARNING)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Portfolio Optimization Toolkit — REST API.\n\n"
        "Educational/academic positioning: "
        "every model carries a `pedagogy` block with formula (LaTeX), references and "
        "drawbacks. Use **POST /compare** to evaluate multiple models on the same data — "
        "the killer feature for learning by comparison.\n\n"
        "Bundled datasets: `ex1` (24 BR stocks + CDI), `mdr` and `mcvar` (24 commodity futures)."
    ),
    contact={
        "name": "WCN Softwares",
        "url": "https://github.com/walterCNeto",
    },
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=[
        {"name": "meta", "description": "Health and metadata"},
        {"name": "models", "description": "Model catalog with pedagogy (the menu)"},
        {"name": "optimization", "description": "Single-model optimization"},
        {"name": "backtest", "description": "Rolling backtest with transaction costs"},
        {"name": "compare", "description": "Side-by-side multi-model comparison"},
        {"name": "datasets", "description": "Bundled educational datasets"},
        {"name": "data", "description": "External data fetch (yfinance, BACEN)"},
    ],
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Top-level
app.include_router(r_health.router)

# Functional, under /api
app.include_router(r_models.router, prefix="/api")
app.include_router(r_optimize.router, prefix="/api")
app.include_router(r_backtest.router, prefix="/api")
app.include_router(r_compare.router, prefix="/api")
app.include_router(r_datasets.router, prefix="/api")
app.include_router(r_data.router, prefix="/api")


# ---------------------------------------------------------------------------
# Exception handling — clean JSON errors
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled exception on {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"Internal server error: {type(exc).__name__}",
            "path": str(request.url.path),
        },
    )


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
    }
