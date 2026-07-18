# Mini-App Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Epic 4 demo vertical slice — from a description, an LLM emits an entity schema + UI spec; the platform validates it, provisions a JSONB namespace, exposes visibility-gated generic CRUD, compiles a per-app UI bundle in an isolated build sandbox, and serves it inside a sandboxed iframe with a per-app scoped token.

**Architecture:** Hexagonal module `backend/app/modules/mini_app` following the `orchestrator`/`agent_builder` conventions. Pure `provisioner`/`codegen` (AD-8) + impure `lifecycle` (side effects). Single JSONB `mini_app_rows` table, tenant-isolated by RLS, visibility-tier enforced at the app layer. Build runs as a resource-capped subprocess behind a new `BuildPort`, dispatched via the existing arq worker. Generated UI compiles to a separate bundle served in `<iframe sandbox>` with an audience-scoped JWT — never merged into the platform SPA.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 (`Mapped`/`mapped_column`), Alembic, Postgres 18 (RLS), arq + Redis, `jose` JWT, esbuild (Node) for per-app bundling; React 19 + react-router-dom + TanStack Query on the frontend.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-18-mini-app-builder-design.md`. Read it before starting.
- **Tenant context**: domain functions read `tenant_context.get()` / rely on RLS — NEVER accept `tenant_id` as an argument (consistency-conventions).
- **Audit (AD-4)**: every material write emits exactly one `AuditEntry` via `AuditPort` (`PostgresAuditSink`) — never direct SQL to `audit_trail`. Use `crud_audit_ids(entity_id)` for the run_id/step_id stopgap on CRUD-outside-a-Run.
- **Single writer (Divergence-3)**: `mini_app.service` is the sole writer to `mini_app_rows`. Row updates are CAS on `updated_at` → 409 on mismatch.
- **Purity (AD-8)**: `provisioner.py` and `codegen.py` perform no I/O and are deterministic. All side effects live in `lifecycle.py` and the build adapter.
- **IDs**: UUID v7 app-side via `from app.core.ids import uuid7`. Timestamps `func.now()`.
- **Enums**: `String` column + `CheckConstraint(f"col IN {TUPLE!r}")` (mirrors `orchestrator.models`), NOT Postgres ENUM types.
- **Envelope**: routes return `{"data": ..., "error": None, "meta": {}}` via a local `_ok`; raise `core.errors` `DomainError` subclasses (`AuthorizationError`, `NotFoundError`, plus new `ValidationError`/`ConflictError` if absent) — handlers in `core/errors.py` render the AR-14 envelope.
- **RLS DDL**: ENABLE + FORCE + `tenant_isolation_policy` on `tenant_id = current_setting('app.tenant_id')::uuid`; `GRANT` to role `vaic_app`. Mirror `1ad51bb8e8cb_create_workflows_rls.py`.
- **Slug/field-name safety**: app `slug` `^[a-z0-9-]{1,64}$`; schema field `name` `^[a-z][a-z0-9_]{0,63}$`. Used in paths/JSONB keys — validate before use, no interpolation of untrusted strings into SQL or shell.
- **Testing preference (project override, CLAUDE.md)**: do NOT author pytest/vitest suites or run typecheck/lint/build unless the user explicitly asks. Each task's verification uses running-app checks (curl/manual) instead. The `pytest`/`vitest` commands shown are OPTIONAL and only run on request. Test files listed under **Files → Test** are deferred stubs, not required deliverables this pass.

---

## Phase 1 — Data model, schema validation, generic CRUD, visibility (Stories 4-1, 4-2 data, 4-3, 4-4)

Milestone: a builder can `POST /mini-apps` (with a caller-supplied schema for now), get a provisioned app, and drive `/apps/{id}/rows` CRUD with tier enforcement. LLM emission is added in Phase 2.

### Task 1: Enums, ORM models, Pydantic schema types

**Files:**
- Create: `backend/app/modules/mini_app/models.py`
- Create: `backend/app/modules/mini_app/schemas.py`
- Modify: `backend/app/modules/mini_app/__init__.py` (replace 1-line stub with module docstring)

**Interfaces:**
- Produces: `MiniApp`, `MiniAppRow` ORM models; `VISIBILITY_TIERS = ("public","need_auth","private")`, `BUILD_STATUSES = ("pending","building","ready","failed")`; Pydantic `EntitySchema`, `FieldSpec`, `UiSpec`.

- [ ] **Step 1: Write `models.py`**

```python
"""Mini-App SQLAlchemy models (Epic 4).

Two tables:
- `mini_apps`   — one row per generated app: schema + ui_spec (JSONB),
  visibility tier + whitelist, build status, bundle path.
- `mini_app_rows` — one row per user record across ALL apps (single-table
  JSONB namespace, PRD FR-13). The four access fields are NOT NULL.

Enum-ish columns use String + CheckConstraint (mirrors orchestrator.models
`RUN_STATUSES` pattern) so adding a value never needs an ALTER TYPE.

RLS (applied by the accompanying migration) is tenant-isolation only:
`tenant_id = current_setting('app.tenant_id')::uuid` (ENABLE + FORCE).
Visibility-tier enforcement lives in `visibility.py` at the app layer
(the platform only propagates `app.tenant_id` as a GUC — see spec §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7

VISIBILITY_TIERS = ("public", "need_auth", "private")
BUILD_STATUSES = ("pending", "building", "ready", "failed")


class MiniApp(Base):
    __tablename__ = "mini_apps"
    __table_args__ = (
        CheckConstraint(
            f"visibility_tier IN {VISIBILITY_TIERS!r}",
            name="ck_mini_apps_visibility_tier",
        ),
        CheckConstraint(
            f"build_status IN {BUILD_STATUSES!r}", name="ck_mini_apps_build_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    entity_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    ui_spec: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    visibility_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default="need_auth", server_default="need_auth"
    )
    whitelist_user_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}"
    )
    build_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default="pending"
    )
    build_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    bundle_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MiniAppRow(Base):
    __tablename__ = "mini_app_rows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    department_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Write `schemas.py` (Pydantic DTOs + the meta-schema field set)**

```python
"""Pydantic DTOs for Mini-App entity schema + UI spec (Epic 4).

`EntitySchema`/`FieldSpec` are the *validated* shape a Mini-App's schema
takes once it passes `schema_validation.validate_entity_schema`. Kept
separate from the ORM `entity_schema` JSONB (stored as a plain dict).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

FIELD_TYPES = ("string", "longtext", "integer", "number", "boolean", "date", "enum")


class FieldSpec(BaseModel):
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{0,63}$")
    type: Literal["string", "longtext", "integer", "number", "boolean", "date", "enum"]
    label: str | None = None
    required: bool = False
    min: float | None = None
    max: float | None = None
    minLength: int | None = None
    maxLength: int | None = None
    pattern: str | None = None
    options: list[str] | None = None


class EntitySchema(BaseModel):
    fields: list[FieldSpec] = Field(..., min_length=1)
    primary_display: str | None = None


class UiSpec(BaseModel):
    layout: Literal["table", "cards"] = "table"
    components: list[dict[str, Any]] = Field(default_factory=list)
    primary_actions: list[Literal["create", "edit", "delete"]] = Field(
        default_factory=lambda: ["create", "edit", "delete"]
    )
```

- [ ] **Step 3: Verify import**

Run: `cd backend && uv run python -c "from app.modules.mini_app import models, schemas; print(models.MiniApp.__tablename__, schemas.FIELD_TYPES)"`
Expected: `mini_apps ('string', 'longtext', 'integer', 'number', 'boolean', 'date', 'enum')`

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/mini_app/models.py backend/app/modules/mini_app/schemas.py backend/app/modules/mini_app/__init__.py
git commit -m "feat(mini-app): ORM models + entity/ui-spec schema DTOs (story 4-1/4-2)"
```

### Task 2: Alembic migration — `mini_apps` + `mini_app_rows` with RLS

**Files:**
- Create: `backend/alembic/versions/<rev>_create_mini_apps_rls.py` (generate rev id with the command below)

**Interfaces:**
- Consumes: models from Task 1.
- Produces: two RLS-enabled tables; `down_revision` = current head.

- [ ] **Step 1: Find the current migration head**

Run: `cd backend && uv run alembic heads`
Record the single head revision id — use it as `down_revision`.

- [ ] **Step 2: Write the migration** (`revision` = a fresh 12-hex id, e.g. `c4f1a9d3e7b2`)

```python
"""create mini_apps + mini_app_rows with RLS (Epic 4, stories 4-2/4-3).

Tenant-isolation RLS only (app.tenant_id GUC), mirroring
1ad51bb8e8cb_create_workflows_rls.py. Visibility tier is enforced at the
app layer (spec §4).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4f1a9d3e7b2"
down_revision: str | Sequence[str] | None = "<HEAD_FROM_STEP_1>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str, *, with_delete: bool) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    grants = "SELECT, INSERT, UPDATE, DELETE" if with_delete else "SELECT, INSERT, UPDATE"
    op.execute(f"GRANT {grants} ON {table} TO {APP_ROLE};")


def upgrade() -> None:
    op.create_table(
        "mini_apps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("entity_schema", postgresql.JSONB(), nullable=False),
        sa.Column("ui_spec", postgresql.JSONB(), nullable=False),
        sa.Column("visibility_tier", sa.String(16), nullable=False, server_default="need_auth"),
        sa.Column("whitelist_user_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default="{}"),
        sa.Column("build_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("build_error", sa.Text(), nullable=True),
        sa.Column("bundle_path", sa.Text(), nullable=True),
        sa.Column("created_by_agent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "visibility_tier IN ('public','need_auth','private')",
            name="ck_mini_apps_visibility_tier",
        ),
        sa.CheckConstraint(
            "build_status IN ('pending','building','ready','failed')",
            name="ck_mini_apps_build_status",
        ),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_mini_apps_tenant_slug"),
    )
    op.create_index("ix_mini_apps_tenant_id", "mini_apps", ["tenant_id"])

    op.create_table(
        "mini_app_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("app_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_mini_app_rows_app_id", "mini_app_rows", ["app_id"])
    op.create_index("ix_mini_app_rows_tenant_id", "mini_app_rows", ["tenant_id"])

    _enable_rls("mini_apps", with_delete=True)
    _enable_rls("mini_app_rows", with_delete=True)


def downgrade() -> None:
    for table in ("mini_app_rows", "mini_apps"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.drop_table("mini_app_rows")
    op.drop_table("mini_apps")
```

- [ ] **Step 3: Apply + verify single head**

Run: `cd backend && uv run alembic upgrade head && uv run alembic heads`
Expected: upgrade OK; exactly one head printed.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/*_create_mini_apps_rls.py
git commit -m "feat(mini-app): migration for mini_apps + mini_app_rows with tenant RLS"
```

### Task 3: Schema meta-schema validation (Story 4-1 core)

**Files:**
- Create: `backend/app/modules/mini_app/schema_validation.py`

**Interfaces:**
- Produces: `validate_entity_schema(raw: dict) -> EntitySchema` (raises `SchemaValidationError` with a reason); `validate_ui_spec(raw: dict) -> UiSpec`; `coerce_row_data(schema: EntitySchema, data: dict) -> dict` (validates a row payload against the schema, raises `SchemaValidationError`).

- [ ] **Step 1: Implement**

```python
"""Entity-schema + UI-spec validation against the platform meta-schema (4-1).

Pure functions — no I/O. Rejection reasons are human-readable and surfaced
to the caller (audited as `mini_app.schema_rejected`).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from app.modules.mini_app.schemas import EntitySchema, FieldSpec, UiSpec

_NUMERIC_TYPES = {"integer", "number"}
_STRING_TYPES = {"string", "longtext"}


class SchemaValidationError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_entity_schema(raw: dict[str, Any]) -> EntitySchema:
    try:
        schema = EntitySchema.model_validate(raw)
    except PydanticValidationError as exc:
        raise SchemaValidationError(f"schema shape invalid: {exc.errors()[:3]}") from exc

    seen: set[str] = set()
    for f in schema.fields:
        if f.name in seen:
            raise SchemaValidationError(f"duplicate field name: {f.name}")
        seen.add(f.name)
        _check_field(f)
    if schema.primary_display and schema.primary_display not in seen:
        raise SchemaValidationError(f"primary_display '{schema.primary_display}' is not a field")
    return schema


def _check_field(f: FieldSpec) -> None:
    if f.type == "enum" and not f.options:
        raise SchemaValidationError(f"enum field '{f.name}' requires non-empty options")
    if f.type != "enum" and f.options is not None:
        raise SchemaValidationError(f"field '{f.name}' has options but is not an enum")
    if (f.min is not None or f.max is not None) and f.type not in _NUMERIC_TYPES:
        raise SchemaValidationError(f"min/max only valid on numeric fields ('{f.name}')")
    if (f.minLength is not None or f.maxLength is not None) and f.type not in _STRING_TYPES:
        raise SchemaValidationError(f"minLength/maxLength only valid on string fields ('{f.name}')")
    if f.pattern is not None:
        if f.type not in _STRING_TYPES:
            raise SchemaValidationError(f"pattern only valid on string fields ('{f.name}')")
        try:
            re.compile(f.pattern)
        except re.error as exc:
            raise SchemaValidationError(f"field '{f.name}' pattern invalid: {exc}") from exc


def validate_ui_spec(raw: dict[str, Any]) -> UiSpec:
    try:
        return UiSpec.model_validate(raw)
    except PydanticValidationError as exc:
        raise SchemaValidationError(f"ui_spec invalid: {exc.errors()[:3]}") from exc


def coerce_row_data(schema: EntitySchema, data: dict[str, Any]) -> dict[str, Any]:
    """Validate + coerce a row payload against the entity schema.

    Returns a dict containing ONLY the schema-defined fields (drops extras).
    Raises SchemaValidationError on any violation.
    """
    out: dict[str, Any] = {}
    for f in schema.fields:
        present = f.name in data
        value = data.get(f.name)
        if not present or value is None:
            if f.required:
                raise SchemaValidationError(f"missing required field: {f.name}")
            continue
        out[f.name] = _coerce_value(f, value)
    return out


def _coerce_value(f: FieldSpec, value: Any) -> Any:  # noqa: ANN401
    if f.type == "boolean":
        if not isinstance(value, bool):
            raise SchemaValidationError(f"field '{f.name}' must be boolean")
        return value
    if f.type in _NUMERIC_TYPES:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SchemaValidationError(f"field '{f.name}' must be numeric")
        num = float(value)
        if f.type == "integer" and int(num) != num:
            raise SchemaValidationError(f"field '{f.name}' must be an integer")
        if f.min is not None and num < f.min:
            raise SchemaValidationError(f"field '{f.name}' below min {f.min}")
        if f.max is not None and num > f.max:
            raise SchemaValidationError(f"field '{f.name}' above max {f.max}")
        return int(num) if f.type == "integer" else num
    if f.type == "enum":
        if value not in (f.options or []):
            raise SchemaValidationError(f"field '{f.name}' not in options")
        return value
    if f.type == "date":
        if not isinstance(value, str):
            raise SchemaValidationError(f"field '{f.name}' date must be an ISO string")
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise SchemaValidationError(f"field '{f.name}' invalid date: {exc}") from exc
        return value
    # string / longtext
    if not isinstance(value, str):
        raise SchemaValidationError(f"field '{f.name}' must be a string")
    if f.minLength is not None and len(value) < f.minLength:
        raise SchemaValidationError(f"field '{f.name}' shorter than {f.minLength}")
    if f.maxLength is not None and len(value) > f.maxLength:
        raise SchemaValidationError(f"field '{f.name}' longer than {f.maxLength}")
    if f.pattern is not None and not re.fullmatch(f.pattern, value):
        raise SchemaValidationError(f"field '{f.name}' fails pattern")
    return value
```

- [ ] **Step 2: Verify at REPL**

Run:
```bash
cd backend && uv run python -c "
from app.modules.mini_app.schema_validation import validate_entity_schema, coerce_row_data, SchemaValidationError
s = validate_entity_schema({'fields':[{'name':'amount','type':'integer','required':True,'min':0},{'name':'status','type':'enum','options':['open','closed']}]})
print('ok', coerce_row_data(s, {'amount':5,'status':'open','junk':1}))
try:
    coerce_row_data(s, {'status':'nope'})
except SchemaValidationError as e:
    print('rejected:', e.reason)
"
```
Expected: `ok {'amount': 5, 'status': 'open'}` then `rejected: missing required field: amount` (amount checked first).

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/mini_app/schema_validation.py
git commit -m "feat(mini-app): entity-schema meta-validation + row coercion (story 4-1)"
```

### Task 4: Pure provisioner + `ProvisioningPlan` (Story 4-2, AD-8)

**Files:**
- Create: `backend/app/modules/mini_app/provisioner.py`

**Interfaces:**
- Consumes: `EntitySchema`, `UiSpec`.
- Produces: `ProvisioningPlan` dataclass `{app_id, tenant_id, department_id, owner_id, name, slug, description, entity_schema, ui_spec, visibility_tier, whitelist_user_ids, created_by_agent_id}`; `build_provisioning_plan(...) -> ProvisioningPlan`; `slugify(name: str) -> str`.

- [ ] **Step 1: Implement (pure — no DB, no I/O; the tsx source is produced in Phase 2 codegen, not here)**

```python
"""Pure Mini-App provisioner (AD-8).

`build_provisioning_plan` is deterministic and side-effect free: given the
validated schema + ui spec + owner context, it returns a ProvisioningPlan
value. The lifecycle module (Task 6) performs the DB insert and enqueues
the build. Codegen of the .tsx bundle source (Phase 2) is a separate pure
step keyed off the plan.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.ids import uuid7
from app.modules.mini_app.schemas import EntitySchema, UiSpec

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    slug = _SLUG_STRIP.sub("-", name.lower()).strip("-")
    return (slug or "app")[:64]


@dataclass(frozen=True)
class ProvisioningPlan:
    app_id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    slug: str
    description: str
    entity_schema: dict[str, Any]
    ui_spec: dict[str, Any]
    visibility_tier: str
    whitelist_user_ids: list[uuid.UUID] = field(default_factory=list)
    created_by_agent_id: uuid.UUID | None = None


def build_provisioning_plan(
    *,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    owner_id: uuid.UUID,
    name: str,
    description: str,
    schema: EntitySchema,
    ui_spec: UiSpec,
    visibility_tier: str,
    whitelist_user_ids: list[uuid.UUID] | None = None,
    created_by_agent_id: uuid.UUID | None = None,
) -> ProvisioningPlan:
    return ProvisioningPlan(
        app_id=uuid7(),
        tenant_id=tenant_id,
        department_id=department_id,
        owner_id=owner_id,
        name=name,
        slug=slugify(name),
        description=description,
        entity_schema=schema.model_dump(),
        ui_spec=ui_spec.model_dump(),
        visibility_tier=visibility_tier,
        whitelist_user_ids=list(whitelist_user_ids or []),
        created_by_agent_id=created_by_agent_id,
    )
```

- [ ] **Step 2: Verify purity (same input → identical plan except app_id; no I/O)**

Run:
```bash
cd backend && uv run python -c "
from app.modules.mini_app.provisioner import build_provisioning_plan, slugify
from app.modules.mini_app.schemas import EntitySchema, UiSpec
import uuid
s=EntitySchema.model_validate({'fields':[{'name':'title','type':'string'}]})
p=build_provisioning_plan(tenant_id=uuid.uuid4(),department_id=uuid.uuid4(),owner_id=uuid.uuid4(),name='Loan Case!',description='d',schema=s,ui_spec=UiSpec(),visibility_tier='need_auth')
print(slugify('Loan Case!'), p.slug, p.entity_schema['fields'][0]['name'])
"
```
Expected: `loan-case loan-case title`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/mini_app/provisioner.py
git commit -m "feat(mini-app): pure provisioner + ProvisioningPlan (story 4-2, AD-8)"
```

### Task 5: App-layer visibility enforcement (Story 4-3)

**Files:**
- Create: `backend/app/modules/mini_app/visibility.py`

**Interfaces:**
- Consumes: `MiniApp` model; a `Principal` (reuse the orchestrator dataclass shape — `user_id`, `tenant_id`, `role`; extend the local caller with `department_id`).
- Produces: `MiniAppPrincipal` dataclass `{user_id, tenant_id, department_id, role}`; `assert_can_access(app: MiniApp, principal: MiniAppPrincipal) -> None` (raises `AuthorizationError`); `can_access(app, principal) -> bool`.

- [ ] **Step 1: Implement**

```python
"""App-layer Visibility Tier enforcement (FR-16, story 4-3).

Tenant isolation is guaranteed at the DB by RLS; THIS module enforces the
per-app tier using the caller's principal (user_id/department_id already on
request.state). Raises AuthorizationError (403) — the auth middleware has
already produced 401 for anonymous callers on protected paths.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.errors import AuthorizationError
from app.modules.mini_app.models import MiniApp


@dataclass(frozen=True)
class MiniAppPrincipal:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    department_id: uuid.UUID | None
    role: str


def can_access(app: MiniApp, principal: MiniAppPrincipal) -> bool:
    tier = app.visibility_tier
    if tier == "public":
        return True  # RLS already scoped to the same tenant
    if tier == "need_auth":
        return principal.department_id is not None and principal.department_id == app.department_id
    if tier == "private":
        return principal.user_id == app.owner_id or principal.user_id in (app.whitelist_user_ids or [])
    return False


def assert_can_access(app: MiniApp, principal: MiniAppPrincipal) -> None:
    if not can_access(app, principal):
        raise AuthorizationError(
            f"visibility tier '{app.visibility_tier}' denies access to mini-app {app.id}"
        )
```

- [ ] **Step 2: Confirm `AuthorizationError` exists**

Run: `cd backend && uv run python -c "from app.core.errors import AuthorizationError; print('ok')"`
Expected: `ok`. If it errors, add `AuthorizationError`/`NotFoundError`/`ValidationError`/`ConflictError` to `core/errors.py` following the existing `DomainError` pattern (check the file first).

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/mini_app/visibility.py
git commit -m "feat(mini-app): app-layer visibility tier enforcement (story 4-3)"
```

### Task 6: Service layer — create app, list/get, generic row CRUD with CAS (Stories 4-2/4-4, Divergence-3)

**Files:**
- Create: `backend/app/modules/mini_app/service.py`
- Create: `backend/app/modules/mini_app/lifecycle.py`

**Interfaces:**
- Consumes: Tasks 1–5; `PostgresAuditSink`, `crud_audit_ids`, `AuditEntry`, `enqueue_job_with_context`.
- Produces (service): `create_app_from_schema(session, *, principal, name, description, schema, ui_spec, visibility_tier, whitelist, created_by_agent_id=None, pool=None) -> MiniApp`; `get_app(session, app_id) -> MiniApp`; `list_apps(session) -> list[MiniApp]`; `create_row(session, app, principal, data) -> MiniAppRow`; `list_rows(session, app) -> list[MiniAppRow]`; `get_row(session, app, row_id) -> MiniAppRow`; `update_row(session, app, principal, row_id, data, expected_updated_at) -> MiniAppRow`; `delete_row(session, app, row_id) -> None`; `serialize_app`/`serialize_row`. Row writes call `_emit_row_change(...)` (no-op seam).
- Produces (lifecycle): `apply_plan(session, plan, *, pool) -> MiniApp` — inserts the `mini_apps` row (build_status=pending) and enqueues `build_mini_app`.

- [ ] **Step 1: Write `lifecycle.py`**

```python
"""Mini-App lifecycle — the impure side of AD-8.

Applies a ProvisioningPlan: inserts the mini_apps row (build_status=pending)
and enqueues the isolated UI build. No schema/codegen logic here.
"""

from __future__ import annotations

from arq.connections import ArqRedis
from sqlalchemy.orm import Session

from app.core.jobs import enqueue_job_with_context
from app.modules.mini_app.models import MiniApp
from app.modules.mini_app.provisioner import ProvisioningPlan


def plan_to_model(plan: ProvisioningPlan) -> MiniApp:
    return MiniApp(
        id=plan.app_id,
        tenant_id=plan.tenant_id,
        department_id=plan.department_id,
        owner_id=plan.owner_id,
        name=plan.name,
        slug=plan.slug,
        description=plan.description,
        entity_schema=plan.entity_schema,
        ui_spec=plan.ui_spec,
        visibility_tier=plan.visibility_tier,
        whitelist_user_ids=plan.whitelist_user_ids,
        build_status="pending",
        created_by_agent_id=plan.created_by_agent_id,
    )


async def enqueue_build(pool: ArqRedis, app_id: str) -> None:
    await enqueue_job_with_context(pool, "build_mini_app", app_id=app_id)
```

- [ ] **Step 2: Write `service.py`** (sole writer; CAS updates; audit on create)

```python
"""Mini-App service — sole writer to mini_app_rows (Divergence-3).

CRUD-outside-a-Run audit ids via `crud_audit_ids` (OQ-1). Row updates are
compare-and-set on `updated_at` → ConflictError (409) on mismatch. Every
material row change funnels through `_emit_row_change` — a no-op seam that
becomes the Action Bus publish in the Epic 5 pairing (FR-17).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids
from app.core.errors import ConflictError, NotFoundError
from app.core.ids import utcnow_iso_ms
from app.core.ports.audit import AuditEntry
from app.modules.mini_app.models import MiniApp, MiniAppRow
from app.modules.mini_app.schema_validation import (
    SchemaValidationError,
    coerce_row_data,
    validate_entity_schema,
)
from app.modules.mini_app.schemas import EntitySchema, UiSpec
from app.modules.mini_app.visibility import MiniAppPrincipal


def _emit_row_change(app_id: uuid.UUID, event_type: str, payload: dict[str, Any]) -> None:
    """Seam for FR-17 App Event emission (Epic 5). Intentional no-op now."""
    return None


def _audit(session: Session, entity_id: uuid.UUID, event_type: str, detail: dict[str, Any]) -> None:
    run_id, step_id = crud_audit_ids(str(entity_id))
    PostgresAuditSink(session).write(
        AuditEntry(
            run_id=run_id, step_id=step_id, type=event_type,
            payload=detail, model="", latency_ms=0, timestamp=utcnow_iso_ms(),
        )
    )


def create_app_from_schema(
    session: Session,
    *,
    principal: MiniAppPrincipal,
    name: str,
    description: str,
    schema: EntitySchema,
    ui_spec: UiSpec,
    visibility_tier: str,
    whitelist_user_ids: list[uuid.UUID],
    created_by_agent_id: uuid.UUID | None = None,
) -> MiniApp:
    from app.modules.mini_app.lifecycle import plan_to_model
    from app.modules.mini_app.provisioner import build_provisioning_plan

    if principal.role not in ("builder", "admin"):
        from app.core.errors import AuthorizationError
        raise AuthorizationError("mini-app creation requires the builder role")

    plan = build_provisioning_plan(
        tenant_id=principal.tenant_id, department_id=principal.department_id or principal.tenant_id,
        owner_id=principal.user_id, name=name, description=description,
        schema=schema, ui_spec=ui_spec, visibility_tier=visibility_tier,
        whitelist_user_ids=whitelist_user_ids, created_by_agent_id=created_by_agent_id,
    )
    app = plan_to_model(plan)
    session.add(app)
    _audit(session, app.id, "mini_app.provisioned",
           {"slug": app.slug, "visibility_tier": app.visibility_tier})
    session.commit()
    session.refresh(app)
    return app


def get_app(session: Session, app_id: uuid.UUID) -> MiniApp:
    app = session.get(MiniApp, app_id)
    if app is None:
        raise NotFoundError(f"mini-app {app_id} not found")
    return app


def list_apps(session: Session) -> list[MiniApp]:
    return list(session.execute(select(MiniApp).order_by(MiniApp.created_at.desc())).scalars())


def _schema_of(app: MiniApp) -> EntitySchema:
    return validate_entity_schema(app.entity_schema)


def create_row(session: Session, app: MiniApp, principal: MiniAppPrincipal, data: dict[str, Any]) -> MiniAppRow:
    coerced = coerce_row_data(_schema_of(app), data)
    row = MiniAppRow(
        app_id=app.id, tenant_id=principal.tenant_id,
        department_id=principal.department_id or app.department_id,
        owner_id=principal.user_id, data=coerced,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    _emit_row_change(app.id, "row.created", {"row_id": str(row.id)})
    return row


def list_rows(session: Session, app: MiniApp) -> list[MiniAppRow]:
    stmt = select(MiniAppRow).where(MiniAppRow.app_id == app.id).order_by(MiniAppRow.created_at.desc())
    return list(session.execute(stmt).scalars())


def get_row(session: Session, app: MiniApp, row_id: uuid.UUID) -> MiniAppRow:
    row = session.get(MiniAppRow, row_id)
    if row is None or row.app_id != app.id:
        raise NotFoundError(f"row {row_id} not found")
    return row


def update_row(
    session: Session, app: MiniApp, principal: MiniAppPrincipal,
    row_id: uuid.UUID, data: dict[str, Any], expected_updated_at: datetime,
) -> MiniAppRow:
    """CAS on updated_at (Divergence-3). Mismatch -> ConflictError (409)."""
    from sqlalchemy import update as sa_update
    coerced = coerce_row_data(_schema_of(app), data)
    result = session.execute(
        sa_update(MiniAppRow)
        .where(
            MiniAppRow.id == row_id,
            MiniAppRow.app_id == app.id,
            MiniAppRow.updated_at == expected_updated_at,
        )
        .values(data=coerced, updated_at=datetime_now())
        .returning(MiniAppRow.id)
    )
    if result.first() is None:
        # Distinguish "gone" from "stale" for a correct 404 vs 409.
        exists = session.get(MiniAppRow, row_id)
        session.rollback()
        if exists is None or exists.app_id != app.id:
            raise NotFoundError(f"row {row_id} not found")
        raise ConflictError("row was modified concurrently (updated_at mismatch)")
    session.commit()
    row = session.get(MiniAppRow, row_id)
    _emit_row_change(app.id, "row.updated", {"row_id": str(row_id)})
    return row


def delete_row(session: Session, app: MiniApp, row_id: uuid.UUID) -> None:
    row = get_row(session, app, row_id)
    session.delete(row)
    session.commit()
    _emit_row_change(app.id, "row.deleted", {"row_id": str(row_id)})


def datetime_now() -> datetime:
    from datetime import UTC, datetime as _dt
    return _dt.now(UTC)


def serialize_app(app: MiniApp) -> dict[str, Any]:
    return {
        "id": str(app.id), "name": app.name, "slug": app.slug,
        "description": app.description, "entity_schema": app.entity_schema,
        "ui_spec": app.ui_spec, "visibility_tier": app.visibility_tier,
        "whitelist_user_ids": [str(u) for u in (app.whitelist_user_ids or [])],
        "build_status": app.build_status, "build_error": app.build_error,
        "created_at": app.created_at.isoformat(), "updated_at": app.updated_at.isoformat(),
    }


def serialize_row(row: MiniAppRow) -> dict[str, Any]:
    return {
        "id": str(row.id), "app_id": str(row.app_id), "owner_id": str(row.owner_id),
        "data": row.data, "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }
```

> Note: confirm `ConflictError` exists in `core/errors.py` (409). If missing, add it beside `AuthorizationError` following the `DomainError` pattern, and ensure the handler maps it to 409. Confirm `PostgresAuditSink(session).write(AuditEntry(...))` matches the real constructor/method signature (open `core/adapters/audit_postgres.py` and `core/ports/audit.py`) and adjust field names if they differ.

- [ ] **Step 2: Verify service imports resolve**

Run: `cd backend && uv run python -c "from app.modules.mini_app import service, lifecycle; print('ok', [f for f in service.__dict__ if not f.startswith('_')][:6])"`
Expected: `ok [...]` (no ImportError). Fix any signature mismatch flagged by the note above.

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/mini_app/service.py backend/app/modules/mini_app/lifecycle.py
git commit -m "feat(mini-app): service (sole writer, CAS rows) + lifecycle apply (stories 4-2/4-4)"
```

### Task 7: Routes — catalog CRUD + generic row CRUD, wired into the app (Stories 4-2/4-4)

**Files:**
- Create: `backend/app/modules/mini_app/routes.py`
- Modify: `backend/app/main.py` (register `mini_app_router` beside the others near line 84)

**Interfaces:**
- Consumes: service (Task 6), visibility (Task 5), `get_tenant_session`, `get_arq_pool`.
- Produces: routers `mini_apps_router` (`/mini-apps`) and `mini_app_rows_router` (`/apps/{app_id}/rows`).

- [ ] **Step 1: Implement `routes.py`** (thin adapter, envelope, principal helper, tier gate on every row op)

```python
"""Mini-App HTTP routes — catalog CRUD + generic row CRUD (Epic 4).

Thin adapters: parse -> service -> _ok envelope. Visibility tier is
asserted on every read/write of a specific app (`assert_can_access`). For
this slice, `POST /mini-apps` accepts a caller-supplied validated schema;
Phase 2 adds the LLM-emission path.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.arq_pool import get_arq_pool
from app.core.deps import get_tenant_session
from app.modules.mini_app import service
from app.modules.mini_app.lifecycle import enqueue_build
from app.modules.mini_app.schema_validation import validate_entity_schema, validate_ui_spec
from app.modules.mini_app.visibility import MiniAppPrincipal, assert_can_access

mini_apps_router = APIRouter(prefix="/mini-apps", tags=["mini-apps"])
mini_app_rows_router = APIRouter(prefix="/apps", tags=["mini-app-rows"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> MiniAppPrincipal:
    dept = getattr(request.state, "department_id", None)
    return MiniAppPrincipal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        department_id=uuid.UUID(str(dept)) if dept else None,
        role=str(getattr(request.state, "role", "")),
    )


class CreateMiniAppRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    entity_schema: dict[str, Any]
    ui_spec: dict[str, Any] | None = None
    visibility_tier: str = "need_auth"
    whitelist_user_ids: list[uuid.UUID] = Field(default_factory=list)


class RowWriteRequest(BaseModel):
    data: dict[str, Any]


class RowUpdateRequest(BaseModel):
    data: dict[str, Any]
    expected_updated_at: datetime


@mini_apps_router.post("")
async def create_mini_app_route(
    body: CreateMiniAppRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    pool: ArqRedis = Depends(get_arq_pool),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    schema = validate_entity_schema(body.entity_schema)
    ui_spec = validate_ui_spec(body.ui_spec or {})
    app = service.create_app_from_schema(
        session, principal=principal, name=body.name, description=body.description,
        schema=schema, ui_spec=ui_spec, visibility_tier=body.visibility_tier,
        whitelist_user_ids=body.whitelist_user_ids,
    )
    await enqueue_build(pool, str(app.id))
    return JSONResponse(status_code=201, content=_ok(service.serialize_app(app)))


@mini_apps_router.get("")
def list_mini_apps_route(session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok([service.serialize_app(a) for a in service.list_apps(session)]))


@mini_apps_router.get("/{app_id}")
def get_mini_app_route(app_id: uuid.UUID, request: Request,
                       session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app = service.get_app(session, app_id)
    assert_can_access(app, _principal(request))
    return JSONResponse(status_code=200, content=_ok(service.serialize_app(app)))


@mini_apps_router.post("/{app_id}/rebuild")
async def rebuild_mini_app_route(app_id: uuid.UUID, request: Request,
                                 session: Session = Depends(get_tenant_session),  # noqa: B008
                                 pool: ArqRedis = Depends(get_arq_pool)) -> JSONResponse:  # noqa: B008
    app = service.get_app(session, app_id)
    assert_can_access(app, _principal(request))
    await enqueue_build(pool, str(app.id))
    return JSONResponse(status_code=202, content=_ok({"app_id": str(app.id), "build_status": "pending"}))


def _load_and_gate(app_id: uuid.UUID, request: Request, session: Session):  # noqa: ANN202
    app = service.get_app(session, app_id)
    principal = _principal(request)
    assert_can_access(app, principal)
    return app, principal


@mini_app_rows_router.post("/{app_id}/rows")
def create_row_route(app_id: uuid.UUID, body: RowWriteRequest, request: Request,
                     session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, principal = _load_and_gate(app_id, request, session)
    row = service.create_row(session, app, principal, body.data)
    return JSONResponse(status_code=201, content=_ok(service.serialize_row(row)))


@mini_app_rows_router.get("/{app_id}/rows")
def list_rows_route(app_id: uuid.UUID, request: Request,
                    session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, _ = _load_and_gate(app_id, request, session)
    return JSONResponse(status_code=200, content=_ok([service.serialize_row(r) for r in service.list_rows(session, app)]))


@mini_app_rows_router.get("/{app_id}/rows/{row_id}")
def get_row_route(app_id: uuid.UUID, row_id: uuid.UUID, request: Request,
                  session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, _ = _load_and_gate(app_id, request, session)
    return JSONResponse(status_code=200, content=_ok(service.serialize_row(service.get_row(session, app, row_id))))


@mini_app_rows_router.patch("/{app_id}/rows/{row_id}")
def update_row_route(app_id: uuid.UUID, row_id: uuid.UUID, body: RowUpdateRequest, request: Request,
                     session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, principal = _load_and_gate(app_id, request, session)
    row = service.update_row(session, app, principal, row_id, body.data, body.expected_updated_at)
    return JSONResponse(status_code=200, content=_ok(service.serialize_row(row)))


@mini_app_rows_router.delete("/{app_id}/rows/{row_id}")
def delete_row_route(app_id: uuid.UUID, row_id: uuid.UUID, request: Request,
                     session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    app, _ = _load_and_gate(app_id, request, session)
    service.delete_row(session, app, row_id)
    return JSONResponse(status_code=200, content=_ok({"deleted": str(row_id)}))
```

- [ ] **Step 2: Register routers in `main.py`** (add imports + `include_router` beside the existing block ~line 84)

```python
from app.modules.mini_app.routes import mini_apps_router, mini_app_rows_router
app.include_router(mini_apps_router)
app.include_router(mini_app_rows_router)
```

- [ ] **Step 3: Verify end-to-end with the running app** (uses the demo tenant from `bootstrap_demo_tenant.py`)

Run (backend up per README; login to get a token):
```bash
TOKEN=$(curl -s localhost:8000/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"admin@shbdemo.vaic","password":"Password123!"}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
# create an app with a supplied schema
APP=$(curl -s localhost:8000/mini-apps -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Loan Case","visibility_tier":"public","entity_schema":{"fields":[{"name":"applicant","type":"string","required":true},{"name":"amount","type":"integer","min":0}]}}')
echo "$APP"
APP_ID=$(echo "$APP" | python -c "import sys,json;print(json.load(sys.stdin)['data']['id'])")
# create + list a row
curl -s "localhost:8000/apps/$APP_ID/rows" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"data":{"applicant":"Acme Co","amount":50000}}'
curl -s "localhost:8000/apps/$APP_ID/rows" -H "Authorization: Bearer $TOKEN"
```
Expected: 201 app with `build_status:"pending"`; 201 row; list returns the row. (The build job will log a failure until Phase 2 registers `build_mini_app` — that's fine here.)

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/mini_app/routes.py backend/app/main.py
git commit -m "feat(mini-app): catalog + generic row CRUD routes with tier gating (stories 4-2/4-4)"
```

---

## Phase 2 — LLM emission + codegen + isolated build sandbox (Story 4-1 emission, 4-5 backend + sandbox)

Milestone: `POST /mini-apps` can take a natural-language description, an LLM emits + validates the schema/ui-spec, and an arq build job compiles a per-app bundle in a resource-capped subprocess with an AST allowlist gate.

### Task 8: LLM schema emission (Story 4-1, FR-12)

**Files:**
- Create: `backend/app/modules/mini_app/emission.py`
- Modify: `backend/app/modules/mini_app/routes.py` (add `POST /mini-apps/generate` OR a `description`-only branch)

**Interfaces:**
- Consumes: the LLM adapter registry (`select_llm_adapter` / `ModelRef` / `Message` — mirror `orchestrator.service._orchestrator_model`), `validate_entity_schema`.
- Produces: `emit_schema(description: str, expected_output: str, *, llm=None) -> tuple[EntitySchema, UiSpec, str]` returning schema, ui_spec, and the raw prompt (for audit). Raises `SchemaValidationError` if the model output can't be coerced.

- [ ] **Step 1: Implement `emission.py`** — build a strict JSON-only prompt, call the model port, parse, validate. (Open `orchestrator/service.py` `decompose_run` for the exact adapter call shape and copy it.)

```python
"""LLM emission of a Mini-App {entity_schema, ui_spec} from a description (FR-12).

Reuses the env-driven model port (VAIC_LLM_PROVIDER / VAIC_LLM_MODEL) exactly
as orchestrator.service does. The model is instructed to return STRICT JSON;
output is parsed then run through the meta-schema validator (invalid -> reject).
"""

from __future__ import annotations

import json

from app.core.adapters.registry import select_llm_adapter
from app.core.ports.llm import Message, ModelRef
from app.core.settings import get_settings
from app.modules.mini_app.schema_validation import (
    SchemaValidationError, validate_entity_schema, validate_ui_spec,
)
from app.modules.mini_app.schemas import EntitySchema, UiSpec

_ALLOWED_TYPES = "string, longtext, integer, number, boolean, date, enum"

_SYSTEM = (
    "You design data-entry mini-apps for a bank. Given a description and the "
    "expected output, return STRICT JSON only (no prose, no markdown fences) "
    'of the form: {"entity_schema": {"fields": [{"name","type","label","required",'
    '"min","max","minLength","maxLength","pattern","options"}], "primary_display"}, '
    '"ui_spec": {"layout":"table","primary_actions":["create","edit","delete"]}}. '
    f"Allowed field types: {_ALLOWED_TYPES}. Field names must match ^[a-z][a-z0-9_]*$. "
    "enum fields MUST include a non-empty options array. Include only fields the app needs."
)


def _model() -> ModelRef:
    s = get_settings()
    return ModelRef(provider=s.llm_provider, model_name=s.llm_model)


def emit_schema(description: str, expected_output: str, *, llm=None) -> tuple[EntitySchema, UiSpec, str]:
    prompt = f"Description:\n{description}\n\nExpected output:\n{expected_output}"
    adapter = llm or select_llm_adapter(_model().provider)
    messages = [Message(role="system", content=_SYSTEM), Message(role="user", content=prompt)]
    raw = adapter.complete(messages, model=_model())  # adjust to the real adapter signature
    text = raw.content if hasattr(raw, "content") else str(raw)
    try:
        parsed = json.loads(_strip_fences(text))
    except json.JSONDecodeError as exc:
        raise SchemaValidationError(f"model did not return valid JSON: {exc}") from exc
    schema = validate_entity_schema(parsed.get("entity_schema", {}))
    ui_spec = validate_ui_spec(parsed.get("ui_spec", {}))
    return schema, ui_spec, prompt


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        if t.endswith("```"):
            t = t.rsplit("```", 1)[0]
    return t.strip()
```

> The exact adapter method (`adapter.complete(...)` vs `.chat(...)`) and `Message`/`ModelRef` construction MUST be copied from `orchestrator/service.py::decompose_run`. Adjust the two marked lines to match; do not invent a signature.

- [ ] **Step 2: Add the emission branch to `create_mini_app_route`** — accept optional `description`+`expected_output` with no `entity_schema`; when the schema is absent, call `emit_schema(...)`, audit `mini_app.schema_emitted` (agent id + prompt) on success or `mini_app.schema_rejected` on `SchemaValidationError` (map to 422). Keep the supplied-schema path working.

- [ ] **Step 3: Verify** (requires a live LLM key in the env; if none, skip and note it — the supplied-schema path from Task 7 still works)

```bash
curl -s localhost:8000/mini-apps -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Sanctions Review","description":"track counterparties needing a sanctions check","expected_output":"a list of parties with name, country, risk level (low/med/high), and whether cleared"}'
```
Expected: 201 with an LLM-emitted `entity_schema` (fields like name/country/risk enum/cleared boolean). On invalid model output: 422 with a reason.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/mini_app/emission.py backend/app/modules/mini_app/routes.py
git commit -m "feat(mini-app): LLM schema+ui-spec emission with meta-validation (story 4-1 FR-12)"
```

### Task 9: Pure codegen — `.tsx` source from schema + UI spec (Story 4-5)

**Files:**
- Create: `backend/app/modules/mini_app/codegen.py`

**Interfaces:**
- Consumes: `EntitySchema`, `UiSpec`.
- Produces: `generate_app_source(app_id, name, schema, ui_spec) -> str` (a self-contained React component `.tsx` string that imports ONLY `react` + the vendored `./sdk`); pure, deterministic.

- [ ] **Step 1: Implement** — map each field type to a form widget + a table column; the component uses a small injected `sdk` (Task 11) for CRUD. Keep it a single default-exported component. (Full template: a `useEffect` load, a form built by iterating fields, a table listing rows, create/edit/delete handlers calling `sdk.list/create/update/delete`.)

```python
"""Pure codegen: EntitySchema + UiSpec -> a React .tsx source string (story 4-5).

Deterministic, no I/O (AD-8). The generated component imports ONLY `react`
and the vendored `./sdk` (enforced by the AST allowlist in Task 10). Field
type -> widget mapping is fixed by the meta-schema.
"""

from __future__ import annotations

import json
import uuid

from app.modules.mini_app.schemas import EntitySchema, UiSpec

_WIDGET = {
    "string": "text", "longtext": "textarea", "integer": "number",
    "number": "number", "boolean": "checkbox", "date": "date", "enum": "select",
}


def generate_app_source(app_id: uuid.UUID, name: str, schema: EntitySchema, ui_spec: UiSpec) -> str:
    fields_json = json.dumps([f.model_dump() for f in schema.fields])
    safe_name = json.dumps(name)
    return f"""import {{ useEffect, useState }} from "react";
import {{ sdk }} from "./sdk";

const FIELDS = {fields_json};
const APP_NAME = {safe_name};

export default function MiniApp() {{
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState({{}});
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState("");

  async function reload() {{ try {{ setRows(await sdk.list()); }} catch (e) {{ setError(String(e)); }} }}
  useEffect(() => {{ reload(); }}, []);

  async function submit(e) {{
    e.preventDefault();
    try {{
      if (editing) await sdk.update(editing.id, form, editing.updated_at);
      else await sdk.create(form);
      setForm({{}}); setEditing(null); setError(""); reload();
    }} catch (err) {{ setError(String(err)); }}
  }}

  return (
    <div style={{{{ fontFamily: "system-ui", padding: 16 }}}}>
      <h2>{{APP_NAME}}</h2>
      {{error && <p style={{{{ color: "crimson" }}}}>{{error}}</p>}}
      <form onSubmit={{submit}}>
        {{FIELDS.map((f) => (
          <label key={{f.name}} style={{{{ display: "block", margin: "8px 0" }}}}>
            <span style={{{{ marginRight: 8 }}}}>{{f.label || f.name}}</span>
            {{renderWidget(f, form, setForm)}}
          </label>
        ))}}
        <button type="submit">{{editing ? "Save" : "Create"}}</button>
        {{editing && <button type="button" onClick={{() => {{ setEditing(null); setForm({{}}); }}}}>Cancel</button>}}
      </form>
      <table border={{1}} cellPadding={{6}} style={{{{ marginTop: 16, borderCollapse: "collapse" }}}}>
        <thead><tr>{{FIELDS.map((f) => <th key={{f.name}}>{{f.label || f.name}}</th>)}}<th></th></tr></thead>
        <tbody>
          {{rows.map((r) => (
            <tr key={{r.id}}>
              {{FIELDS.map((f) => <td key={{f.name}}>{{String(r.data?.[f.name] ?? "")}}</td>)}}
              <td>
                <button onClick={{() => {{ setEditing(r); setForm(r.data || {{}}); }}}>Edit</button>
                <button onClick={{async () => {{ await sdk.remove(r.id); reload(); }}}}>Delete</button>
              </td>
            </tr>
          ))}}
        </tbody>
      </table>
    </div>
  );
}}

function renderWidget(f, form, setForm) {{
  const set = (v) => setForm((s) => ({{ ...s, [f.name]: v }}));
  const val = form[f.name] ?? "";
  if (f.type === "boolean") return <input type="checkbox" checked={{!!form[f.name]}} onChange={{(e) => set(e.target.checked)}} />;
  if (f.type === "longtext") return <textarea value={{val}} onChange={{(e) => set(e.target.value)}} />;
  if (f.type === "enum") return <select value={{val}} onChange={{(e) => set(e.target.value)}}><option value="">--</option>{{(f.options||[]).map((o) => <option key={{o}} value={{o}}>{{o}}</option>)}}</select>;
  const inputType = {{ integer: "number", number: "number", date: "date" }}[f.type] || "text";
  return <input type={{inputType}} value={{val}} onChange={{(e) => set(f.type === "integer" || f.type === "number" ? Number(e.target.value) : e.target.value)}} />;
}}
"""
```

- [ ] **Step 2: Verify determinism + no I/O**

```bash
cd backend && uv run python -c "
from app.modules.mini_app.codegen import generate_app_source
from app.modules.mini_app.schemas import EntitySchema, UiSpec
import uuid
s=EntitySchema.model_validate({'fields':[{'name':'applicant','type':'string'},{'name':'risk','type':'enum','options':['low','high']}]})
a=generate_app_source(uuid.uuid4(),'Loan',s,UiSpec()); b=generate_app_source(uuid.uuid4(),'Loan',s,UiSpec())
print('deterministic', a==b, 'imports-sdk', './sdk' in a)
"
```
Expected: `deterministic True imports-sdk True`

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/mini_app/codegen.py
git commit -m "feat(mini-app): pure .tsx codegen from schema+ui-spec (story 4-5)"
```

### Task 10: AST allowlist gate for generated source (sandbox — build plane)

**Files:**
- Create: `backend/app/modules/mini_app/source_guard.py`

**Interfaces:**
- Produces: `assert_source_safe(tsx: str) -> None` (raises `SourceGuardError` with the offending token); `SAFE_IMPORTS = {"react", "./sdk"}`.

- [ ] **Step 1: Implement** — a lightweight lexical/regex guard (no full TS parser needed for MVP): reject any `import ... from "X"` where `X ∉ SAFE_IMPORTS`; reject the token set `eval(`, `new Function`, `window.parent`, `window.top`, `window.opener`, `document.cookie`, `localStorage`, `fetch(` (the app must go through `sdk`), `import(` (dynamic). Document that this is best-effort lexical hardening layered under the iframe sandbox (the real boundary), mirroring the `SubprocessSandbox` disclaimer.

```python
"""Best-effort lexical guard on generated .tsx before it is built (sandbox).

This is NOT the security boundary — the sandboxed iframe + scoped token is
(see spec §7). This guard blocks the easy escapes in LLM/codegen output:
non-allowlisted imports and direct platform-reaching tokens. Layered
defense, mirroring core/adapters/sandbox.py's philosophy.
"""

from __future__ import annotations

import re

SAFE_IMPORTS = {"react", "./sdk"}
_IMPORT_RE = re.compile(r"""import\s+[^;]*?from\s+['"]([^'"]+)['"]""")
_BANNED = ("eval(", "new Function", "window.parent", "window.top",
           "window.opener", "document.cookie", "localStorage",
           "sessionStorage", "fetch(", "XMLHttpRequest", "import(")


class SourceGuardError(Exception):
    def __init__(self, token: str) -> None:
        super().__init__(f"generated source rejected: '{token}'")
        self.token = token


def assert_source_safe(tsx: str) -> None:
    for mod in _IMPORT_RE.findall(tsx):
        if mod not in SAFE_IMPORTS:
            raise SourceGuardError(f"import '{mod}'")
    for token in _BANNED:
        if token in tsx:
            raise SourceGuardError(token)
```

- [ ] **Step 2: Verify**

```bash
cd backend && uv run python -c "
from app.modules.mini_app.source_guard import assert_source_safe, SourceGuardError
assert_source_safe('import { sdk } from \"./sdk\";')
for bad in ['import x from \"axios\";', 'window.parent.postMessage(1)', 'fetch(\"/agents\")']:
    try: assert_source_safe(bad); print('MISS', bad)
    except SourceGuardError as e: print('blocked', e.token)
"
```
Expected: three `blocked ...` lines, no `MISS`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/mini_app/source_guard.py
git commit -m "feat(mini-app): AST/lexical allowlist guard for generated source (sandbox build plane)"
```

### Task 11: `BuildPort` + resource-capped esbuild adapter + runtime template (sandbox — build execution)

**Files:**
- Create: `backend/app/core/ports/build.py`
- Create: `backend/app/core/adapters/esbuild_build.py`
- Create: `backend/app/modules/mini_app/runtime_template/index.html`
- Create: `backend/app/modules/mini_app/runtime_template/sdk.ts`
- Create: `backend/app/modules/mini_app/runtime_template/entry.tsx`

**Interfaces:**
- Produces: `BuildPort` protocol `build(app_id, tsx_source, out_dir, *, timeout_s=60, memory_mb=512) -> BuildResult{ok, error, bundle_path}`; `EsbuildBuild` adapter shelling to `npx esbuild` under a wall-clock timeout in an isolated temp workdir; a static `index.html` + `sdk.ts` (CRUD via the scoped token) + `entry.tsx` (mounts the generated `MiniApp`).

- [ ] **Step 1: Write the port** (`core/ports/build.py`)

```python
from __future__ import annotations
from typing import Protocol, runtime_checkable
from pydantic import BaseModel

class BuildResult(BaseModel):
    ok: bool
    bundle_path: str | None = None
    error: str = ""

@runtime_checkable
class BuildPort(Protocol):
    def build(self, app_id: str, tsx_source: str, out_dir: str, *,
              timeout_s: int = 60, memory_mb: int = 512) -> BuildResult: ...
```

- [ ] **Step 2: Write the runtime template files.** `sdk.ts` reads a per-app scoped token injected on the host page (via `window.__MINIAPP__ = {appId, token, apiBase}`) and calls `/apps/{appId}/rows*`. `entry.tsx` imports the generated component (written next to it at build time as `app.tsx`) and mounts it. `index.html` loads the built `bundle.js`.

`runtime_template/sdk.ts`:
```ts
declare global { interface Window { __MINIAPP__: { appId: string; token: string; apiBase: string } } }
const cfg = () => window.__MINIAPP__;
async function call(path: string, init?: RequestInit) {
  const c = cfg();
  const resp = await fetch(`${c.apiBase}/apps/${c.appId}/rows${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${c.token}`, ...(init?.headers || {}) },
  });
  const body = await resp.json();
  if (!resp.ok) throw new Error(body?.error?.message || "request failed");
  return body.data;
}
export const sdk = {
  list: () => call(""),
  create: (data: unknown) => call("", { method: "POST", body: JSON.stringify({ data }) }),
  update: (id: string, data: unknown, expected_updated_at: string) =>
    call(`/${id}`, { method: "PATCH", body: JSON.stringify({ data, expected_updated_at }) }),
  remove: (id: string) => call(`/${id}`, { method: "DELETE" }),
};
```

`runtime_template/entry.tsx`:
```tsx
import { createRoot } from "react-dom/client";
import MiniApp from "./app";
createRoot(document.getElementById("root")!).render(<MiniApp />);
```

`runtime_template/index.html`:
```html
<!doctype html><html><head><meta charset="utf-8"><title>Mini-App</title></head>
<body><div id="root"></div><script src="./bundle.js"></script></body></html>
```

- [ ] **Step 3: Write the esbuild adapter** — copy the generated source to `app.tsx` in a temp dir with the template, run `npx esbuild entry.tsx --bundle --outfile=<out>/bundle.js` under `subprocess.run(timeout=...)`, copy `index.html` to `out_dir`. Return `BuildResult`. Reuse the wall-clock-timeout + kill pattern from `core/adapters/sandbox.py` (don't re-derive the watchdog; a `subprocess.run(..., timeout=timeout_s)` with `TimeoutExpired -> ok=False` is sufficient for the build plane).

```python
"""EsbuildBuild — BuildPort adapter (sandbox build plane, story 4-5).

Runs `npx esbuild` in an isolated temp workdir under a wall-clock timeout.
The generated component is written as app.tsx alongside the vendored
runtime template (entry.tsx/sdk.ts/index.html). Output: bundle.js + index.html
in out_dir. A failed/timed-out build returns ok=False (never raises into
the worker) so one bad app can't take down the platform.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.core.ports.build import BuildResult

_TEMPLATE = Path(__file__).resolve().parents[1] / "modules" / "mini_app" / "runtime_template"


class EsbuildBuild:
    def build(self, app_id: str, tsx_source: str, out_dir: str, *,
              timeout_s: int = 60, memory_mb: int = 512) -> BuildResult:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            for name in ("entry.tsx", "sdk.ts"):
                shutil.copy(_TEMPLATE / name, work / name)
            (work / "app.tsx").write_text(tsx_source, encoding="utf-8")
            try:
                proc = subprocess.run(  # noqa: S603,S607 -- fixed args, sandboxed inputs
                    ["npx", "esbuild", "entry.tsx", "--bundle",
                     "--loader:.tsx=tsx", "--jsx=automatic",
                     f"--outfile={out / 'bundle.js'}"],
                    cwd=work, capture_output=True, text=True, timeout=timeout_s,
                )
            except subprocess.TimeoutExpired:
                return BuildResult(ok=False, error="build timed out")
            if proc.returncode != 0:
                return BuildResult(ok=False, error=proc.stderr[-2000:])
            shutil.copy(_TEMPLATE / "index.html", out / "index.html")
        return BuildResult(ok=True, bundle_path=str(out))
```

> Confirm `npx esbuild` is runnable on the host (`npx esbuild --version`). If esbuild isn't installed, `cd frontend && npm i -D esbuild` and invoke it via the frontend `node_modules/.bin/esbuild` path, or add esbuild as a repo-root dev dep. React is resolved from the frontend `node_modules` — set `--resolve-dir` or run the build with `cwd` under `frontend/` if bundling can't find `react`; verify in Step 4.

- [ ] **Step 4: Verify a real build** of a codegen sample to a temp dir; confirm `bundle.js` + `index.html` exist and a bad source returns `ok=False`.

```bash
cd backend && uv run python -c "
from app.core.adapters.esbuild_build import EsbuildBuild
from app.modules.mini_app.codegen import generate_app_source
from app.modules.mini_app.schemas import EntitySchema, UiSpec
import uuid, tempfile, os
s=EntitySchema.model_validate({'fields':[{'name':'x','type':'string'}]})
src=generate_app_source(uuid.uuid4(),'T',s,UiSpec())
d=tempfile.mkdtemp(); r=EsbuildBuild().build('a',src,d)
print(r.ok, os.path.exists(os.path.join(d,'bundle.js')), r.error[:120])
"
```
Expected: `True True ` (adjust resolve-dir per the note if react can't resolve).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/ports/build.py backend/app/core/adapters/esbuild_build.py backend/app/modules/mini_app/runtime_template/
git commit -m "feat(mini-app): BuildPort + esbuild adapter + iframe runtime template (sandbox build plane)"
```

### Task 12: arq build worker + static serving of bundles (Story 4-5)

**Files:**
- Create: `backend/app/workers/mini_app_worker.py`
- Modify: `backend/app/workers/` worker registration (add `build_mini_app` to the worker `functions` — check how `run_worker.py`/`WorkerConfig` aggregates functions; append there)
- Modify: `backend/app/main.py` (mount static files at `/mini-app-runtime` from the bundle root dir; add a settings key `mini_app_bundle_root`, default under a writable runtime dir)

**Interfaces:**
- Consumes: `EsbuildBuild`, `generate_app_source`, `assert_source_safe`, `validate_entity_schema`, `validate_ui_spec`; `@tenant_aware_job` + `AdminSessionLocal` pattern from `orchestrator_worker.py`.
- Produces: `build_mini_app(ctx, *, app_id)` job that transitions `pending→building→ready|failed`, writes the bundle under `{bundle_root}/{app_id}/`, sets `bundle_path`.

- [ ] **Step 1: Implement the job** — load the app (tenant-scoped via the job's RLS session), set `build_status='building'`, run the guard→codegen→build pipeline, persist `ready`+`bundle_path` or `failed`+`build_error`. On guard rejection or build failure, set `failed` (never raise past the job body). Mirror `orchestrator_worker.run_workflow`'s `@tenant_aware_job` + `_reassert_rls` structure.

- [ ] **Step 2: Register** `build_mini_app` in the worker functions list and mount static serving in `main.py`:

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path
_bundle_root = Path(get_settings().mini_app_bundle_root)
_bundle_root.mkdir(parents=True, exist_ok=True)
app.mount("/mini-app-runtime", StaticFiles(directory=str(_bundle_root), html=True), name="mini-app-runtime")
```

- [ ] **Step 3: Verify** — start the worker (`cd backend && uv run python -m scripts.run_worker`), create an app via the API (Task 7 curl), poll `GET /mini-apps/{id}` until `build_status:"ready"`, then `curl -s localhost:8000/mini-app-runtime/{app_id}/index.html` returns the HTML and `.../bundle.js` returns JS.
Expected: build reaches `ready`; static assets served.

- [ ] **Step 4: Commit**

```bash
git add backend/app/workers/mini_app_worker.py backend/app/main.py backend/app/core/settings.py
git commit -m "feat(mini-app): arq build worker + static bundle serving (story 4-5 sandbox runtime)"
```

### Task 13: Per-app scoped session token (sandbox — runtime plane)

**Files:**
- Create: `backend/app/modules/mini_app/scoped_token.py`
- Modify: `backend/app/modules/mini_app/routes.py` (`POST /mini-apps/{app_id}/session-token`)
- Modify: `backend/app/core/auth.py` OR the row-CRUD dependency — accept a scoped token whose `aud` == the path `app_id` for `/apps/{app_id}/rows*` only.

**Interfaces:**
- Produces: `mint_scoped_token(app_id, principal) -> str` (JWT with `aud=str(app_id)`, `scope="miniapp:rows"`, short TTL, plus `tenant_id`/`user_id`/`department_id`/`role`); `verify_scoped_token(token, app_id) -> claims`.

- [ ] **Step 1: Implement `scoped_token.py`** using `create_access_token`/`decode_access_token` (add `aud`+`scope` claims). Gate: the row routes accept EITHER a normal platform JWT (tier-checked as today) OR a scoped token whose `aud` matches the `app_id` and `scope=="miniapp:rows"` — the scoped token authorizes ONLY that app's rows, nothing else on the platform.
- [ ] **Step 2: Add `POST /mini-apps/{app_id}/session-token`** — platform-JWT-gated, runs `assert_can_access`, returns `mint_scoped_token(app_id, principal)`. This is what the host page calls before mounting the iframe.
- [ ] **Step 3: Verify** — mint a token for app A, confirm it works on `/apps/A/rows` and is rejected (401/403) on `/apps/B/rows`.
- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/mini_app/scoped_token.py backend/app/modules/mini_app/routes.py backend/app/core/auth.py
git commit -m "feat(mini-app): per-app scoped session token for sandboxed iframe (sandbox runtime plane)"
```

---

## Phase 3 — Frontend catalog + sandboxed host (Stories 4-7, 4-5 frontend)

Milestone: `/mini-apps` lists apps and creates them; `/mini-apps/:appId` mounts the generated app in a sandboxed iframe using a scoped token.

### Task 14: Mini-App API client

**Files:**
- Create: `frontend/src/lib/miniAppsApi.ts`

**Interfaces:**
- Produces: `MiniApp` type; `listMiniApps()`, `getMiniApp(id)`, `createMiniApp(input)`, `rebuildMiniApp(id)`, `getScopedToken(id)` — all via `apiFetch` (mirror `workflowsApi.ts`).

- [ ] **Step 1: Implement** following `workflowsApi.ts` exactly (envelope auto-unwrapped by `apiFetch`).

```ts
import { apiFetch } from "./api";

export interface MiniApp {
  id: string; name: string; slug: string; description: string;
  entity_schema: { fields: Array<{ name: string; type: string; label?: string; options?: string[]; required?: boolean }> };
  ui_spec: Record<string, unknown>;
  visibility_tier: "public" | "need_auth" | "private";
  whitelist_user_ids: string[]; build_status: "pending" | "building" | "ready" | "failed";
  build_error: string | null; created_at: string; updated_at: string;
}

export interface CreateMiniAppInput {
  name: string; description?: string; expected_output?: string;
  entity_schema?: MiniApp["entity_schema"]; visibility_tier?: string; whitelist_user_ids?: string[];
}

export const listMiniApps = () => apiFetch<MiniApp[]>("/mini-apps");
export const getMiniApp = (id: string) => apiFetch<MiniApp>(`/mini-apps/${id}`);
export const createMiniApp = (input: CreateMiniAppInput) =>
  apiFetch<MiniApp>("/mini-apps", { method: "POST", body: JSON.stringify(input) });
export const rebuildMiniApp = (id: string) =>
  apiFetch<{ app_id: string; build_status: string }>(`/mini-apps/${id}/rebuild`, { method: "POST" });
export const getScopedToken = (id: string) =>
  apiFetch<{ token: string }>(`/mini-apps/${id}/session-token`, { method: "POST" });
```

- [ ] **Step 2: Verify** `npx tsc --noEmit` compiles this file (only if the user asks to run typecheck; otherwise eyeball against `workflowsApi.ts`).
- [ ] **Step 3: Commit** `git add frontend/src/lib/miniAppsApi.ts && git commit -m "feat(mini-app): frontend API client (story 4-7)"`

### Task 15: Catalog page — list + create + "view generated code" (Story 4-7)

**Files:**
- Create: `frontend/src/routes/mini-apps.tsx`
- Modify: `frontend/src/App.tsx` (replace `<Route path="/mini-apps" element={<ComingSoon .../>} />` with `<MiniAppsPage/>`; add `<Route path="/mini-apps/:appId" element={<MiniAppHostPage/>} />`)

**Interfaces:**
- Consumes: `miniAppsApi`, TanStack Query, existing `ui` primitives (`components/ui`).

- [ ] **Step 1: Implement `MiniAppsPage`** — `useQuery(listMiniApps)` grid of cards (name, tier badge, build-status pill); a "Create Mini-App" form (name, description, expected output, tier select, whitelist input for private) calling `createMiniApp` via `useMutation` + invalidate; a "View generated code" affordance (Phase-2 note: the generated `.tsx` can be shown by adding a `GET /mini-apps/{id}/source` route returning the codegen output — add that small route if the "view code" feature is wanted, else omit the button). Open button links to `/mini-apps/:appId`. Follow `routes/workflows.tsx` structure.
- [ ] **Step 2: Wire routes in `App.tsx`** (imports + the two `<Route>` lines).
- [ ] **Step 3: Verify in the browser** — `npm run dev`, visit `/mini-apps`, create an app, see it listed with a build-status pill that flips to `ready`.
- [ ] **Step 4: Commit** `git add frontend/src/routes/mini-apps.tsx frontend/src/App.tsx && git commit -m "feat(mini-app): catalog list + create page (story 4-7)"`

### Task 16: Sandboxed host page — iframe + scoped token (Story 4-5 frontend, sandbox runtime)

**Files:**
- Create: `frontend/src/routes/mini-app-host.tsx` (imported as `MiniAppHostPage`)

**Interfaces:**
- Consumes: `getMiniApp`, `getScopedToken`.

- [ ] **Step 1: Implement `MiniAppHostPage`** — read `:appId`; `useQuery(getMiniApp)`; render build-status/empty/error states; when `build_status==="ready"`, `POST` for a scoped token, then render a **sandboxed iframe**:

```tsx
// After fetching { token } via getScopedToken(appId) and app.build_status === "ready":
const apiBase = import.meta.env.VITE_API_BASE ?? "";
const src = `${apiBase}/mini-app-runtime/${appId}/index.html`;
// Inject config into the iframe via query params the runtime reads into window.__MINIAPP__,
// OR postMessage after load. Simplest: pass token+appId+apiBase as URL hash and have sdk.ts read them.
<iframe
  title={app.name}
  src={`${src}#${new URLSearchParams({ appId, token, apiBase }).toString()}`}
  sandbox="allow-scripts allow-forms"
  style={{ width: "100%", height: "80vh", border: "1px solid var(--border)" }}
/>
```

> Update `runtime_template/sdk.ts` (Task 11) to hydrate `window.__MINIAPP__` from `location.hash` on load if not already set, so the host passes config via the hash without `allow-same-origin`. Keep `sandbox` WITHOUT `allow-same-origin` so the iframe can't read the parent's storage/token — the scoped token in the hash is the only credential it holds.

- [ ] **Step 2: Verify** — open `/mini-apps/:appId` for a `ready` app; the iframe loads the generated table+form; create/edit/delete a row and confirm it persists (reload). Confirm the parent's platform token is NOT reachable from the iframe (DevTools: `window.parent` access blocked by sandbox).
- [ ] **Step 3: Commit** `git add frontend/src/routes/mini-app-host.tsx frontend/src/App.tsx backend/app/modules/mini_app/runtime_template/sdk.ts && git commit -m "feat(mini-app): sandboxed iframe host page with scoped token (story 4-5 sandbox runtime)"`

---

## Self-Review

**Spec coverage:**
- FR-12 emission → Task 8; validation → Task 3. ✓
- FR-13 JSONB namespace + four NOT-NULL access fields → Tasks 1,2,6. ✓
- FR-14 generic CRUD + tier → Tasks 6,7. ✓
- FR-15 generated auth-gated UI → Tasks 9,11,12,16. ✓
- FR-16 tier matrix (401/403/200) → Task 5 (+ auth middleware 401) + Task 7 gating. ✓
- Sandbox (data/build/runtime planes) → declarative backend (Tasks 6,7) + guard (10) + capped build (11,12) + scoped token + iframe (13,16). ✓
- Divergence-3 single writer + CAS → Task 6. ✓ AD-8 purity → Tasks 4,9. ✓
- Deferred seam `_emit_row_change` → Task 6. ✓
- Catalog UI (4-7) → Task 15. ✓

**Known adjustments the implementer MUST confirm against the real code (flagged inline, not placeholders):**
1. `core/errors.py` — presence of `AuthorizationError`, `NotFoundError`, `ConflictError`, `ValidationError`; add any missing following the existing `DomainError` pattern + handler status mapping (Tasks 5,6).
2. `PostgresAuditSink` constructor + `AuditEntry` field names (Task 6) — copy the exact shape from `orchestrator/service.py::_emit_audit`.
3. LLM adapter call signature (`select_llm_adapter` + `Message`/`ModelRef`) — copy from `orchestrator/service.py::decompose_run` (Task 8).
4. Worker `functions` aggregation + `mini_app_bundle_root` setting + esbuild `react` resolution (Tasks 11,12).

**Placeholder scan:** no "TBD/TODO/handle edge cases" — every code step carries real code; the four items above are explicit "copy the exact signature from file X" instructions, not vague gaps.

**Type consistency:** `MiniAppPrincipal` (Task 5) used verbatim in Tasks 6,7. `ProvisioningPlan` (Task 4) → `plan_to_model` (Task 6). `BuildResult`/`BuildPort` (Task 11) → worker (Task 12). `sdk` interface (Task 11) matches codegen calls `sdk.list/create/update/remove` (Task 9). ✓

## Deferred (not in this plan — Epic 5 pairing)
- FR-17 App Event emission — `_emit_row_change` seam becomes the Action Bus publish.
- Story 4-8 live event stream UI.
- Orchestrator-triggered mid-Run emission (the `service.provision`/`create_app_from_schema` path is already orchestrator-callable).
