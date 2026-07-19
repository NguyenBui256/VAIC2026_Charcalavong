"""arq worker entrypoint — Mini-App build pipeline (Epic 4, story 4-5).

`build_mini_app` — dispatched after a MiniApp row is created (`pending`
build_status). Wrapped in `@tenant_aware_job` (`app/core/jobs.py`) — the
SAME established idiom `orchestrator_worker.run_workflow` uses — rather
than re-deriving tenant/RLS bootstrap here. The decorator materializes
`tenant_context`, opens an RLS-scoped `SessionLocal()`, and stashes it on
`ctx["session"]`.

Pipeline: validate stored schema/ui_spec dicts -> codegen a .tsx source ->
lexical guard -> esbuild bundle into `{bundle_root}/{app_id}/`. Never lets
a bad app (guard rejection, esbuild failure) raise past the job body —
that would crash the worker process and take down every other tenant's
in-flight job; failures are recorded on the row instead (`build_status=
'failed'`, `build_error=...`).

Deliberately does NOT import anything from `orchestrator_worker` (AD-1 —
avoid coupling unrelated feature modules); only shares the generic
`app/core/jobs.py` infrastructure.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.esbuild_build import EsbuildBuild
from app.core.deps import assume_app_role
from app.core.jobs import tenant_aware_job
from app.core.settings import get_settings
from app.core.tenant_context import set_tenant_context, set_tenant_session_var, tenant_context
from app.modules.mini_app.codegen import generate_app_source
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.schema_validation import (
    SchemaValidationError,
    validate_entity_schema,
    validate_ui_spec,
)
from app.modules.mini_app.source_guard import SourceGuardError, assert_source_safe

logger = logging.getLogger(__name__)

__all__ = ["build_mini_app"]


def _reassert_rls(session: Session, tenant_id: uuid.UUID) -> None:
    """Re-apply `SET LOCAL ROLE` + `app.tenant_id` GUC on this session.

    Mirrors `orchestrator_worker._transition`'s rationale: `SET LOCAL` is
    transaction-scoped, so a prior commit within this same job execution
    drops both the role and the RLS GUC. Call this immediately before any
    statement that follows a commit.
    """
    assume_app_role(session)
    set_tenant_session_var(session, tenant_id)


def _load_app(session: Session, app_id: uuid.UUID) -> MiniApp | None:
    return session.execute(select(MiniApp).where(MiniApp.id == app_id)).scalar_one_or_none()


def _set_status(
    session: Session,
    tenant_id: uuid.UUID,
    app: MiniApp,
    *,
    build_status: str,
    build_error: str | None = None,
    bundle_path: str | None = None,
) -> None:
    _reassert_rls(session, tenant_id)
    app.build_status = build_status
    if build_error is not None:
        app.build_error = build_error
    if bundle_path is not None:
        app.bundle_path = bundle_path
    session.commit()


@tenant_aware_job
async def build_mini_app(ctx: dict[str, Any], *, app_id: str) -> None:
    """Worker entrypoint — builds one MiniApp's bundle (`pending -> building -> ready|failed`).

    Never raises past this function body on a build-pipeline failure
    (schema validation, guard rejection, esbuild failure) — those are
    expected per-app outcomes recorded on the row, not worker crashes. A
    truly unexpected error (DB unreachable, etc.) is still allowed to
    propagate so arq's retry/failure bookkeeping sees it.
    """
    session = ctx["session"]
    tenant_id = tenant_context.get()
    if tenant_id is None:
        # Defensive — `@tenant_aware_job` always sets this before calling us.
        raise RuntimeError("build_mini_app: tenant_context unset at job entry")

    loop = asyncio.get_running_loop()
    app_uuid = uuid.UUID(str(app_id))

    def _load() -> MiniApp | None:
        _reassert_rls(session, tenant_id)
        return _load_app(session, app_uuid)

    app = await loop.run_in_executor(None, _load)
    if app is None:
        logger.warning("build_mini_app: app_id=%s not found for tenant=%s", app_id, tenant_id)
        return

    await loop.run_in_executor(
        None, lambda: _set_status(session, tenant_id, app, build_status="building")
    )

    def _run_pipeline() -> tuple[bool, str, str | None]:
        """Runs entirely off the event loop (validation, codegen, subprocess build).

        Returns (ok, error_or_bundle_path_placeholder, bundle_path).
        """
        try:
            schema = validate_entity_schema(app.entity_schema)
            ui_spec = validate_ui_spec(app.ui_spec)
        except SchemaValidationError as exc:
            return False, f"schema validation failed: {exc.reason}", None

        src = generate_app_source(app.id, app.name, schema, ui_spec)

        try:
            assert_source_safe(src)
        except SourceGuardError as exc:
            return False, f"source guard rejected: {exc}", None

        out_dir = str(Path(get_settings().mini_app_bundle_root) / str(app.id))
        result = EsbuildBuild().build(str(app.id), src, out_dir=out_dir)
        if not result.ok:
            return False, result.error or "build failed", None
        return True, "", result.bundle_path or out_dir

    ok, error, bundle_path = await loop.run_in_executor(None, _run_pipeline)

    def _persist() -> None:
        if ok:
            _set_status(
                session, tenant_id, app, build_status="ready", bundle_path=bundle_path
            )
        else:
            logger.info("build_mini_app: app_id=%s failed: %s", app_id, error)
            _set_status(session, tenant_id, app, build_status="failed", build_error=error)

    await loop.run_in_executor(None, _persist)
