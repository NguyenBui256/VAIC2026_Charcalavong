"""Application settings — pydantic-settings, env-prefixed `VAIC_`.

Env vars follow the form `VAIC_<UPPER_FIELD>` (e.g. `VAIC_DATABASE_URL`).
The env file is chosen by `VAIC_ENV` (see `_resolve_env_file`): `.env` for
dev (default), `.env.production` for production. Never commit either (NFR-6).
Real OS env vars always win over the file, so container/CI overrides still work.
"""

from __future__ import annotations

import os
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Production values (values in {"production", "prod"}) load `.env.production`;
# anything else — including unset — loads the dev `.env`. Read from the raw OS
# environment (not a Settings field) because it must be known BEFORE the file
# is picked. Set it in the shell before launching: `$env:VAIC_ENV="production"`.
_PROD_ENV_VALUES = {"production", "prod"}


def _resolve_env_file() -> str:
    """Return the dotenv filename for the current `VAIC_ENV` (dev vs prod)."""
    return (
        ".env.production"
        if os.getenv("VAIC_ENV", "").strip().lower() in _PROD_ENV_VALUES
        else ".env"
    )


class Settings(BaseSettings):
    """Runtime configuration. Field names map to `VAIC_<NAME>` env vars."""

    model_config = SettingsConfigDict(
        env_prefix="VAIC_",
        env_file=_resolve_env_file(),
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

    # CORS — browser origins allowed to call the API cross-origin (Vite dev
    # server on :5173 by default). Comma-separated in `VAIC_CORS_ORIGINS`.
    # In dev the frontend usually reaches the API via the Vite proxy (same
    # origin, no CORS needed); this covers direct `VITE_API_BASE` calls and
    # production deploys served from a different origin.
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated allowed CORS origins",
    )

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
    # Preferred var is `VAIC_LLM_API_KEY`; falls back to the bare
    # `ANTHROPIC_API_KEY` env var (not `VAIC_`-prefixed, operator convention
    # from earlier deployments) when unset. `validation_alias` bypasses
    # `env_prefix` for this field so both exact var names resolve.
    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("VAIC_LLM_API_KEY", "ANTHROPIC_API_KEY"),
        description="API key for the OpenAI-compatible LLM adapter",
    )
    # Provider id for the OpenAI-compatible Model Layer adapter (AD-7,
    # provider-agnostic per FR-26). Selects the `LlmPort` implementation via
    # `select_llm_adapter`.
    llm_provider: str = Field(
        default="openai", description="Provider id for the default LLM adapter"
    )
    # Model name passed as `ModelRef.model_name` to the adapter's `complete`
    # call. Defaults to the FPT AI Marketplace DeepSeek deployment.
    llm_model: str = Field(
        default="DeepSeek-V4-Flash", description="Default model name for the LLM adapter"
    )
    # Orchestrator-specific model override (Story 3.3 decomposition prompt).
    # Falls back to `llm_model` when unset -- most deployments use one model
    # for both orchestration and Specialist Agents.
    orchestrator_model: str = Field(
        default="", description="Model name for orchestrator decomposition; falls back to llm_model"
    )

    # Hard wall-clock timeout (seconds) enforced on every LLM request. Set on
    # the provider SDK client so a hung call actually aborts at this mark and
    # raises -- WITHOUT this the SDK default (~600s) applies and the
    # orchestrator's `asyncio.wait_for` cannot interrupt a synchronous
    # blocking call. Retried by `execute_task_row` up to `llm_max_attempts`.
    llm_timeout_seconds: int = Field(
        default=60, description="Per-request LLM timeout in seconds (provider-enforced)"
    )
    # Max total LLM request attempts per Task (the first try + retries). 3 =>
    # first try + 2 retries. `execute_task_row` derives `retries` from this.
    llm_max_attempts: int = Field(
        default=3, description="Max total LLM request attempts per Task (incl. first try)"
    )

    # Story 2.7 (AR-14 stored credentials / NFR-6) — Fernet key for
    # encrypting stored Integration auth headers at rest. A missing/blank
    # key surfaces as a clear error only when encrypt/decrypt is CALLED
    # (app.core.crypto), not at import time.
    encryption_key: str = Field(
        default="", description="Fernet key (urlsafe base64, 32 bytes) for stored credentials"
    )

    # Story 4-5 (sandbox build plane) — root directory under which each
    # built Mini-App's static bundle lands at `{mini_app_bundle_root}/
    # {app_id}/` (bundle.js + index.html). Served read-only by
    # `StaticFiles` mounted at `/mini-app-runtime` in `app/main.py`.
    # Repo-relative default under `backend/` keeps it out of the frontend
    # tree (which esbuild's per-app workdir already occupies) and writable
    # without extra OS-level permissioning in dev.
    mini_app_bundle_root: str = Field(
        default=".miniapp-bundles",
        description="Root directory for built Mini-App static bundles (relative to the "
        "process cwd, which is `backend/` per README run instructions — resolves to "
        "`backend/.miniapp-bundles`)",
    )

    # 3E — root directory for uploaded workflow files (typed node/run I/O of
    # type "file"). Bytes land at `{workflow_files_root}/{tenant_id}/{id}_{name}`.
    # Repo-relative default under `backend/` (resolves to `backend/.workflow-files`).
    # Served ONLY via the authenticated GET /workflows/files/{id} route (never a
    # public StaticFiles mount) — run data is tenant-private.
    workflow_files_root: str = Field(
        default=".workflow-files",
        description="Root directory for uploaded workflow files (relative to cwd `backend/`)."
    )
      
    # vaic_tools integration — real MCP tool server (retrieve/gmail/calendar
    # via MCP /mcp/, KB ingest/delete via REST /api/v1/documents). When
    # disabled the McpClientStub is used, so dev/test without a running
    # vaic_tools stays green.
    vaic_tools_enabled: bool = Field(
        default=False, description="Route MCP tool calls to the real vaic_tools server"
    )
    vaic_tools_base_url: str = Field(
        default="http://localhost:8002", description="vaic_tools REST root (ingest/delete)"
    )
    vaic_tools_mcp_url: str = Field(
        default="http://localhost:8002/mcp/",
        description="vaic_tools MCP Streamable HTTP endpoint",
    )
    vaic_tools_api_key: str = Field(
        default="", description="Bearer key matching vaic_tools MCP_API_KEYS"
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton — import once per process."""
    return Settings()
