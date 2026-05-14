"""Compare endpoint — the killer feature for educational use.

Run several optimization models on the same data and return a unified
side-by-side comparison. Optionally include full backtests for each.
"""

from fastapi import APIRouter, HTTPException

from portopt.api import schemas as S
from portopt.api import services
from portopt.api.settings import settings

router = APIRouter(tags=["compare"])


@router.post("/compare", response_model=S.CompareResponse)
def compare(req: S.CompareRequest):
    """Compare multiple optimization models on the same dataset.

    Returns:
    - `optimizations`: per-model OptimizationResponse
    - `backtests`: per-model BacktestResponse (if with_backtest=True)
    - `summary_table`: flat rows for tabular rendering
    - `weights_table`: by-asset weights for each model (matrix)

    Use cases:
    - "How does HRP compare to Markowitz on this universe?"
    - "Show me Tier 0 vs Tier 3 side-by-side for educational purposes"
    - "Which model produces less turnover for this BR portfolio?"
    """
    if len(req.models) > settings.max_compare_models:
        raise HTTPException(
            400,
            f"max {settings.max_compare_models} models per comparison, got {len(req.models)}",
        )
    try:
        return services.run_compare(req)
    except NotImplementedError as e:
        raise HTTPException(501, f"Model not yet implemented: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Internal compare error: {type(e).__name__}: {e}")
