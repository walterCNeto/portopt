"""Health check / meta endpoints."""

from fastapi import APIRouter

from portopt.api.schemas import HealthResponse
from portopt.api.settings import settings
from portopt.datasets import list_datasets
from portopt.models import MODEL_REGISTRY

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    """Liveness probe + basic API metadata."""
    return HealthResponse(
        version=settings.app_version,
        environment=settings.environment,
        n_models=len(set(MODEL_REGISTRY.values())),
        n_datasets=len(list_datasets()),
    )
