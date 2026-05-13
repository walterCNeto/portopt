"""portopt API — FastAPI module for serving the portopt toolkit over HTTP.

Run locally:
    pip install -e ".[api]"
    uvicorn portopt.api.main:app --reload --port 8000

Deploy to Fly.io (region gru, mesmo padrão do chassiro-api):
    fly launch
    fly deploy

OpenAPI docs available at: http://localhost:8000/docs
"""

from portopt.api.main import app

__all__ = ["app"]
