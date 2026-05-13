"""Optimization endpoint."""

from fastapi import APIRouter, HTTPException

from portopt.api import schemas as S
from portopt.api import services

router = APIRouter(tags=["optimization"])


@router.post("/optimize", response_model=S.OptimizationResponse)
def optimize(req: S.OptimizeRequest):
    """Run a single-model optimization on the requested data.

    The response includes:
    - `weights`: optimal allocation
    - `pedagogy`: educational metadata (formula, references, drawbacks)
    - `diagnostics`: solver-specific output

    For comparing multiple models on the same data, use POST /compare instead.
    """
    try:
        return services.run_optimization(req)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Internal optimization error: {type(e).__name__}: {e}")
