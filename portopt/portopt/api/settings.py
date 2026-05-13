"""API settings — read from environment variables.

Pattern follows SafraRisk and ChassiRO conventions: 12-factor app with
sensible defaults for local dev and override via env in production.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """API runtime configuration."""

    # App identity
    app_name: str = "portopt API"
    app_version: str = "0.1.0"
    environment: str = field(
        default_factory=lambda: os.getenv("PORTOPT_ENV", "development")
    )

    # CORS — frontend origins allowed to call the API
    cors_origins: list[str] = field(default_factory=lambda: (
        os.getenv("PORTOPT_CORS", "http://localhost:5173,http://localhost:3000").split(",")
    ))

    # Cache (Redis) — optional, defaults to in-memory
    redis_url: str | None = field(
        default_factory=lambda: os.getenv("REDIS_URL")
    )
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("PORTOPT_CACHE_TTL", "86400"))
    )

    # Rate limiting (calls per IP per minute) — disabled by default for educational use
    rate_limit_per_minute: int = field(
        default_factory=lambda: int(os.getenv("PORTOPT_RATE_LIMIT", "0"))
    )

    # Auth — Firebase by default (matches WCN stack), optional in dev
    firebase_project_id: str | None = field(
        default_factory=lambda: os.getenv("FIREBASE_PROJECT_ID")
    )
    require_auth: bool = field(
        default_factory=lambda: os.getenv("PORTOPT_REQUIRE_AUTH", "false").lower() == "true"
    )

    # Yfinance / data — optional API keys for premium sources
    brapi_token: str | None = field(default_factory=lambda: os.getenv("BRAPI_TOKEN"))

    # Limits to prevent abuse on free public endpoints
    max_tickers_per_request: int = 30
    max_backtest_years: int = 25
    max_compare_models: int = 8

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


# Module-level singleton
settings = Settings()
