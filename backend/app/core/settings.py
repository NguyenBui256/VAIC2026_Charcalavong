"""Application settings — pydantic-settings, env-prefixed `VAIC_`.

Env vars follow the form `VAIC_<UPPER_FIELD>` (e.g. `VAIC_DATABASE_URL`).
A root `.env` is auto-loaded; never commit it (NFR-6).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Field names map to `VAIC_<NAME>` env vars."""

    model_config = SettingsConfigDict(
        env_prefix="VAIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Allows constructing `Settings(llm_api_key=...)` by field name in
        # tests, in addition to the `ANTHROPIC_API_KEY` validation_alias used
        # for env/`.env` resolution below.
        populate_by_name=True,
    )

    # Sync SQLAlchemy URL (architecture mandates sync mode)
    database_url: str = Field(
        default="postgresql+psycopg://vaic:changeme@localhost:5432/vaic",
        description="Sync SQLAlchemy DSN",
    )

    # Postgres superuser / migration role DSN (used by Alembic and tests that
    # need to BYPASSRLS for fixture setup). Defaults to the same DB, same user.
    database_admin_url: str = Field(
        default="postgresql+psycopg://vaic:changeme@localhost:5432/vaic",
        description="DSN for migrations + fixtures (BYPASSRLS-capable role)",
    )

    # The Postgres role used by the FastAPI app at runtime. RLS policies apply
    # to this role; it MUST NOT have BYPASSRLS. If empty, the role logged into
    # via `database_url` is used (tests use the same role with `SET LOCAL`).
    app_db_role: str = Field(default="", description="Postgres role for the app")

    redis_url: str = Field(default="redis://localhost:6379/0")

    # Auth — used starting in Story 1.3
    jwt_secret: str = Field(default="replace-with-32-byte-hex-from-openssl-rand-hex-32")
    jwt_algorithm: str = Field(default="HS256")
    jwt_ttl_minutes: int = Field(default=480)

    # LLM provider keys — Story 1.6 (AD-7). Loaded at runtime; a missing key
    # surfaces as a clear error when the adapter is *called*, not at import
    # time (FR-5 consequence).
    anthropic_api_key: str = Field(default="", description="Anthropic API key")
    openai_api_key: str = Field(default="", description="OpenAI API key")
    google_api_key: str = Field(default="", description="Google Gemini API key")
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama HTTP base URL for local models",
    )

    # OpenAI-compatible Model Layer endpoint (AD-7, FR-26 provider-agnostic).
    # Defaults to the FPT AI Marketplace "OpenAI Wrapper" root. Override with
    # `VAIC_LLM_BASE_URL` to point the `openai` adapter at any other
    # Chat-Completions-compatible endpoint (self-hosted, OpenAI proper, etc.).
    llm_base_url: str = Field(
        default="https://mkp-api.fptcloud.com/v1",
        description="Base URL for the OpenAI-compatible LLM adapter",
    )
    # The deployment's Model Layer key is stored under the bare `ANTHROPIC_API_KEY`
    # env var (not `VAIC_`-prefixed) by operator convention -- `validation_alias`
    # bypasses `env_prefix` for this field only so it reads that exact var.
    llm_api_key: str = Field(
        default="",
        validation_alias="ANTHROPIC_API_KEY",
        description="API key for the OpenAI-compatible LLM adapter (from ANTHROPIC_API_KEY)",
    )

    # Story 2.7 (AR-14 stored credentials / NFR-6) — Fernet key for
    # encrypting stored Integration auth headers at rest. A missing/blank
    # key surfaces as a clear error only when encrypt/decrypt is CALLED
    # (app.core.crypto), not at import time.
    encryption_key: str = Field(
        default="", description="Fernet key (urlsafe base64, 32 bytes) for stored credentials"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — import once per process."""
    return Settings()
