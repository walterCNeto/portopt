"""Backtest endpoint."""

from fastapi import APIRouter, HTTPException

from portopt.api import schemas as S
from portopt.api import services

router = APIRouter(tags=["backtest"])


@router.post("/backtest", response_model=S.BacktestResponse)
def backtest(req: S.BacktestRequest):
    """Run a rolling backtest of a single model.

    The engine is look-ahead-bias-proof: at each rebalancing date, the model
    sees only `[t - training_window : t]` returns.

    Time series points are downsampled to ~800 points for transfer efficiency.
    """
    try:
        return services.run_backtest(req)
    except NotImplementedError as e:
        raise HTTPException(501, f"Model not yet implemented: {e}")
    except ValueError as e:
        raise HTTPException(400, str(e))
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, f"Internal backtest error: {type(e).__name__}: {e}")
