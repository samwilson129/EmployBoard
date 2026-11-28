from __future__ import annotations

import json
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_ASYNC_DRIVER = "postgresql+asyncpg"
_SYNC_DRIVER = "postgresql+psycopg"

# libpq-only parameters that asyncpg's DSN parser does not understand.
_LIBPQ_ONLY_PARAMS = {
    "sslmode",
    "channel_binding",
    "connect_timeout",
    "target_session_attrs",
    "options",
}


def _as_asyncpg_url(url: str) -> str:
    """Return a SQLAlchemy async URL using asyncpg.

    Neon and Render commonly provide ``postgres://`` or ``postgresql://`` URLs.
    SQLAlchemy needs an explicit driver. libpq-only query parameters are moved
    to connect_args by :attr:`Settings.asyncpg_connect_args`.
    """
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = _ASYNC_DRIVER + "://" + url[len(prefix) :]
            break
    if url.startswith("postgresql+psycopg://"):
        url = _ASYNC_DRIVER + "://" + url[len("postgresql+psycopg://") :]

    parts = urlsplit(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in _LIBPQ_ONLY_PARAMS
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _as_psycopg_url(url: str) -> str:
    """Alembic uses the synchronous psycopg driver, which accepts sslmode."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return _SYNC_DRIVER + "://" + url[len(prefix) :]
    if url.startswith("postgresql+asyncpg://"):
        return _SYNC_DRIVER + "://" + url[len("postgresql+asyncpg://") :]
    if url.startswith("postgresql+psycopg://"):
        return url
    return url


def _without_password(url: str) -> str:
    """Redact credentials for logs and health responses."""
    try:
        parts = urlsplit(url)
        if parts.password is None:
            return url
        netloc = parts.netloc.replace(f":{parts.password}@", ":***@")
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except ValueError:
        return "<unparseable database url>"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "EmployBoard API"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/employboard"

    admin_secret: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    enable_scheduler: bool = True
    sync_interval_hours: int = Field(default=6, ge=1, le=168)
    seed_on_startup: bool = False

    http_timeout_seconds: float = Field(default=30.0, gt=0)
    http_max_retries: int = Field(default=3, ge=0, le=8)
    ats_request_config_json: str = "{}"
    ats_default_requests_per_minute: int = Field(default=120, ge=1)
    ats_default_max_concurrency: int = Field(default=8, ge=1)
    ats_default_retry_delay_seconds: float = Field(default=0.5, ge=0)
    ats_default_max_retry_delay_seconds: float = Field(default=20.0, gt=0)
    ats_default_backoff_multiplier: float = Field(default=2.0, ge=1)
    user_agent: str = (
        "EmployBoard/1.0 (public job aggregation; contact: admin@employboard.example)"
    )
    smartrecruiters_detail_limit: int = Field(default=100, ge=0, le=1000)

    job_description_cache_max_entries: int = Field(default=10_000, ge=1)
    job_description_cache_ttl_hours: int = Field(default=24, ge=1)
    job_description_negative_ttl_minutes: int = Field(default=15, ge=1)
    cache_maintenance_interval_hours: int = Field(default=1, ge=1, le=168)

    deactivation_miss_threshold: int = Field(default=2, ge=1, le=10)
    deactivation_min_fetch_ratio: float = Field(default=0.25, ge=0.0, le=1.0)

    @property
    def async_database_url(self) -> str:
        return _as_asyncpg_url(self.database_url)

    @property
    def sync_database_url(self) -> str:
        """Alembic uses the synchronous psycopg driver."""
        return _as_psycopg_url(self.database_url)

    @property
    def asyncpg_connect_args(self) -> dict[str, object]:
        """Translate libpq SSL options into asyncpg connect arguments."""
        parts = urlsplit(self.database_url.strip())
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        sslmode = query.get("sslmode", "").lower()
        if sslmode in {"require", "prefer", "verify-ca", "verify-full"}:
            return {"ssl": True}
        return {}

    @property
    def cors_origin_list(self) -> list[str]:
        values = [value.strip() for value in self.cors_origins.split(",")]
        return [value for value in values if value]

    @property
    def ats_request_config(self) -> dict[str, dict[str, object]]:
        try:
            value = json.loads(self.ats_request_config_json)
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}

    @property
    def redacted_database_url(self) -> str:
        return _without_password(self.async_database_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()
