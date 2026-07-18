# Mini-Apps list→detail + unified Database page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sidebar **Database** page (Knowledge Base tab + Mini-App Databases tab) backed by a new reusable `mini_app_databases` schema-template entity, and let mini-apps reference a database via a dropdown; keep a clean list→detail flow for mini-apps.

**Architecture:** New back-end entity `mini_app_databases` (name + description + `entity_schema`) with RLS; `mini_apps.database_id` nullable FK for traceability; binding a DB copies its schema into the app (row data + build pipeline untouched). Front end swaps the `Knowledge Base` nav item for a two-tab `Database` page and adds a Database dropdown to mini-app creation.

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / Python 3.13 (back end); Vite + React 19 + TypeScript + TanStack Query (front end).

## Global Constraints

- Routes are thin adapters returning `{"data","error","meta"}` via a local `_ok(...)` helper.
- New tenant tables: RLS `ENABLE` + `FORCE`, policy `tenant_id = current_setting('app.tenant_id')::uuid`, `vaic_app` granted `SELECT, INSERT, UPDATE, DELETE`. Mirror `alembic/versions/c4f1a9d3e7b2_create_mini_apps_rls.py`.
- **The repo currently has TWO Alembic heads** (`2848501cd966` shared_pool_reshape and `f7a8b9c0d1e2` grant_delete_graph_authoring_tables). The new migration MUST merge them: `down_revision = ("2848501cd966", "f7a8b9c0d1e2")` — so `alembic upgrade head` resolves to a single head. (This makes the feature migration double as the head-merge; acceptable for this branch.)
- **KB reuse:** the `rebuild` branch already ships a tenant-wide KB pool — `lib/kbApi.ts` (`listKbDocuments`/`uploadKbDocument`/`deleteKbDocument` against `/kb/documents`, `KbDocument` type), `hooks/useKbPool.ts` (`useKbPool`/`useKbPoolMutations`), and a full `routes/knowledge-base/KnowledgeBasePage.tsx`. **Reuse these** — do NOT create `globalKbApi`/`useGlobalKb`/`KnowledgeBaseSection`. The Database page's KB tab renders the existing `<KnowledgeBasePage />`.
- Entity schemas validated with `app.modules.mini_app.schema_validation.validate_entity_schema` (raises `SchemaValidationError(reason)`).
- Front end: TanStack Query, `components/ui` primitives, branch order **error → loading → empty → data**, toasts on mutation success/error.
- **NO automated tests. Do NOT run typecheck / lint / build / format** — user verifies manually. (Overrides any TDD mandate.)
- Windows shell is PowerShell; venv Python at `backend/.venv`. Run backend cmds from `backend/`.
- Keep files focused (< ~200 LOC), kebab-case descriptive names.

---

## File Structure

**Back end (new):**
- `backend/app/modules/mini_app/database_models.py` — `MiniAppDatabase` ORM model.
- `backend/app/modules/mini_app/database_service.py` — CRUD + rows aggregation + serializers.
- `backend/app/modules/mini_app/database_routes.py` — `mini_app_databases_router`.
- `backend/alembic/versions/aa10database01_create_mini_app_databases.py` — table + RLS + `mini_apps.database_id`.

**Back end (modified):**
- `backend/app/modules/mini_app/models.py` — add `database_id` column to `MiniApp`.
- `backend/app/modules/mini_app/provisioner.py` — thread `database_id` through `ProvisioningPlan` + `build_provisioning_plan`.
- `backend/app/modules/mini_app/lifecycle.py` — `plan_to_model` sets `database_id`.
- `backend/app/modules/mini_app/service.py` — `create_app_from_schema(database_id=...)`; `serialize_app` adds `database_id`.
- `backend/app/modules/mini_app/routes.py` — `CreateMiniAppRequest.database_id`; create route resolves DB → schema.
- `backend/app/main.py` — include `mini_app_databases_router`.

**Front end (new):**
- `frontend/src/lib/miniAppDatabasesApi.ts`
- `frontend/src/hooks/useMiniAppDatabases.ts`
- `frontend/src/routes/database.tsx` — `DatabasePage` (two-tab shell)
- `frontend/src/components/database/MiniAppDatabaseSection.tsx`
- `frontend/src/components/database/SchemaFieldEditor.tsx`
- `frontend/src/components/mini-apps/CreateMiniAppModal.tsx`

**Front end (reused as-is — do NOT recreate):**
- `frontend/src/routes/knowledge-base/KnowledgeBasePage.tsx` — rendered as the Database page's KB tab.
- `frontend/src/hooks/useKbPool.ts`, `frontend/src/lib/kbApi.ts` — tenant-wide KB pool.

**Front end (modified):**
- `frontend/src/components/Sidebar.tsx` — `Knowledge Base` → `Database`.
- `frontend/src/components/CommandPalette/navigationCommands.ts` — nav target + icon.
- `frontend/src/App.tsx` — add `/database` route (keep existing `/knowledge-base` + `/tools`).
- `frontend/src/lib/miniAppsApi.ts` — `MiniApp.database_id`; `CreateMiniAppInput.database_id`.
- `frontend/src/routes/mini-apps.tsx` — list-only landing + create modal.
- `frontend/src/routes/mini-app-host.tsx` — show bound database.

---

## Task 1: Back end — `mini_app_databases` table, model, migration

**Files:**
- Create: `backend/app/modules/mini_app/database_models.py`
- Modify: `backend/app/modules/mini_app/models.py`
- Create: `backend/alembic/versions/aa10database01_create_mini_app_databases.py`

**Interfaces:**
- Produces: `MiniAppDatabase` ORM (`__tablename__ = "mini_app_databases"`, cols `id, tenant_id, owner_id, name, description, entity_schema, created_at, updated_at`); `mini_apps.database_id` nullable UUID FK.

- [ ] **Step 1: Create the model**

`backend/app/modules/mini_app/database_models.py`:
```python
"""Mini-App Database model — a reusable entity-schema template (Database page).

A `mini_app_databases` row is a named, tenant-scoped `entity_schema` that
mini-apps reference via `mini_apps.database_id`. Binding copies the schema
into the app at create time; row data stays per-app (`mini_app_rows.app_id`).

RLS (accompanying migration): tenant-isolation only
`tenant_id = current_setting('app.tenant_id')::uuid` (ENABLE + FORCE).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class MiniAppDatabase(Base):
    __tablename__ = "mini_app_databases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_mini_app_databases_tenant_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    entity_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 2: Add `database_id` to the `MiniApp` model**

In `backend/app/modules/mini_app/models.py`, add this column to `MiniApp` (place after `created_by_agent_id`, before `created_at`):
```python
    database_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("mini_app_databases.id", ondelete="SET NULL"),
        nullable=True,
    )
```
(`ForeignKey` and `UUID` are already imported in that file.)

- [ ] **Step 3: Write the migration**

`backend/app/modules/mini_app/database_models.py` must be importable by Alembic's env; it already imports `Base`. Create `backend/alembic/versions/aa10database01_create_mini_app_databases.py`:
```python
"""create mini_app_databases + mini_apps.database_id with RLS.

Tenant-isolation RLS only (app.tenant_id GUC), mirroring
c4f1a9d3e7b2_create_mini_apps_rls.py. A mini_app_databases row is a reusable
entity-schema template referenced by mini_apps.database_id (SET NULL on delete).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "aa10database01"
# Merge the two pre-existing heads (shared_pool_reshape + grant_delete_graph_...)
# so `alembic upgrade head` resolves to a single head.
down_revision: str | Sequence[str] | None = ("2848501cd966", "f7a8b9c0d1e2")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def upgrade() -> None:
    op.create_table(
        "mini_app_databases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("entity_schema", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_mini_app_databases_tenant_name"),
    )
    op.create_index("ix_mini_app_databases_tenant_id", "mini_app_databases", ["tenant_id"])

    op.execute("ALTER TABLE mini_app_databases ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE mini_app_databases FORCE ROW LEVEL SECURITY;")
    op.execute(
        """CREATE POLICY tenant_isolation_policy ON mini_app_databases
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON mini_app_databases TO vaic_app;")

    op.add_column(
        "mini_apps",
        sa.Column(
            "database_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mini_app_databases.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("mini_apps", "database_id")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON mini_app_databases;")
    op.execute("ALTER TABLE mini_app_databases NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE mini_app_databases DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_mini_app_databases_tenant_id", table_name="mini_app_databases")
    op.drop_table("mini_app_databases")
```

- [ ] **Step 4: Apply the migration** (this is a DB action the user expects to run for real back end)

Run from `backend/`:
```
.venv\Scripts\python.exe -m alembic upgrade head
```
Expected: `Running upgrade f7a8b9c0d1e2 -> aa10database01`.

- [ ] **Step 5: Commit**
```
git add backend/app/modules/mini_app/database_models.py backend/app/modules/mini_app/models.py backend/alembic/versions/aa10database01_create_mini_app_databases.py
git commit -m "feat(mini-app): add mini_app_databases table + mini_apps.database_id"
```

---

## Task 2: Back end — database service + routes + wiring

**Files:**
- Create: `backend/app/modules/mini_app/database_service.py`
- Create: `backend/app/modules/mini_app/database_routes.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `MiniAppDatabase` (Task 1), `validate_entity_schema` / `SchemaValidationError`, `MiniAppPrincipal`, `MiniApp`, `MiniAppRow`.
- Produces: `mini_app_databases_router` with the 6 endpoints in the spec; `serialize_database(db) -> dict`.

- [ ] **Step 1: Write the service**

`backend/app/modules/mini_app/database_service.py`:
```python
"""Mini-App Database service — CRUD over reusable entity-schema templates.

A database is a named `entity_schema`. Mini-apps reference it via
`mini_apps.database_id`; binding copies the schema. `list_database_rows`
aggregates `mini_app_rows` for every app referencing the database (read-only).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.mini_app.database_models import MiniAppDatabase
from app.modules.mini_app.models import MiniApp, MiniAppRow
from app.modules.mini_app.schema_validation import validate_entity_schema
from app.modules.mini_app.visibility import MiniAppPrincipal


def list_databases(session: Session) -> list[MiniAppDatabase]:
    return list(
        session.execute(
            select(MiniAppDatabase).order_by(MiniAppDatabase.created_at.desc())
        ).scalars()
    )


def get_database(session: Session, db_id: uuid.UUID) -> MiniAppDatabase:
    db = session.get(MiniAppDatabase, db_id)
    if db is None:
        raise NotFoundError(f"mini-app database {db_id} not found")
    return db


def create_database(
    session: Session, *, principal: MiniAppPrincipal,
    name: str, description: str, entity_schema: dict[str, Any],
) -> MiniAppDatabase:
    validate_entity_schema(entity_schema)  # raises SchemaValidationError (-> 422)
    if _name_taken(session, principal.tenant_id, name):
        raise ConflictError(f"a database named '{name}' already exists")
    db = MiniAppDatabase(
        tenant_id=principal.tenant_id, owner_id=principal.user_id,
        name=name, description=description or "", entity_schema=entity_schema,
    )
    session.add(db)
    session.commit()
    session.refresh(db)
    return db


def update_database(
    session: Session, db_id: uuid.UUID, *,
    name: str | None, description: str | None, entity_schema: dict[str, Any] | None,
) -> MiniAppDatabase:
    db = get_database(session, db_id)
    if entity_schema is not None:
        validate_entity_schema(entity_schema)
        db.entity_schema = entity_schema
    if name is not None and name != db.name:
        if _name_taken(session, db.tenant_id, name):
            raise ConflictError(f"a database named '{name}' already exists")
        db.name = name
    if description is not None:
        db.description = description
    session.commit()
    session.refresh(db)
    return db


def delete_database(session: Session, db_id: uuid.UUID) -> None:
    db = get_database(session, db_id)
    session.delete(db)  # referencing apps' database_id -> NULL via FK ON DELETE
    session.commit()


def list_database_rows(session: Session, db_id: uuid.UUID) -> list[dict[str, Any]]:
    get_database(session, db_id)  # 404 if missing
    stmt = (
        select(MiniAppRow)
        .join(MiniApp, MiniApp.id == MiniAppRow.app_id)
        .where(MiniApp.database_id == db_id)
        .order_by(MiniAppRow.created_at.desc())
    )
    rows = session.execute(stmt).scalars()
    return [
        {
            "row_id": str(r.id), "app_id": str(r.app_id), "data": r.data,
            "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
        }
        for r in rows
    ]


def _name_taken(session: Session, tenant_id: uuid.UUID, name: str) -> bool:
    stmt = select(MiniAppDatabase.id).where(
        MiniAppDatabase.tenant_id == tenant_id, MiniAppDatabase.name == name
    )
    return session.execute(stmt).first() is not None


def serialize_database(db: MiniAppDatabase) -> dict[str, Any]:
    return {
        "id": str(db.id), "name": db.name, "description": db.description,
        "entity_schema": db.entity_schema, "owner_id": str(db.owner_id),
        "created_at": db.created_at.isoformat(), "updated_at": db.updated_at.isoformat(),
    }
```
Note: confirm `ConflictError` exists in `app.core.errors` (it is used in `service.py`). If it maps to 409, that is the desired duplicate-name status.

- [ ] **Step 2: Write the routes**

`backend/app/modules/mini_app/database_routes.py`:
```python
"""Mini-App Database HTTP routes (Database page).

Thin adapters: parse -> service -> _ok envelope. Tenant isolation is enforced
by RLS (app.tenant_id GUC); no per-row visibility tiers here.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.mini_app import database_service as svc
from app.modules.mini_app.visibility import MiniAppPrincipal

mini_app_databases_router = APIRouter(prefix="/mini-app-databases", tags=["mini-app-databases"])


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


class CreateDatabaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    entity_schema: dict[str, Any]


class UpdateDatabaseRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    entity_schema: dict[str, Any] | None = None


@mini_app_databases_router.get("")
def list_databases_route(session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok([svc.serialize_database(d) for d in svc.list_databases(session)]))


@mini_app_databases_router.post("")
def create_database_route(
    body: CreateDatabaseRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    db = svc.create_database(
        session, principal=_principal(request),
        name=body.name, description=body.description, entity_schema=body.entity_schema,
    )
    return JSONResponse(status_code=201, content=_ok(svc.serialize_database(db)))


@mini_app_databases_router.get("/{db_id}")
def get_database_route(db_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok(svc.serialize_database(svc.get_database(session, db_id))))


@mini_app_databases_router.patch("/{db_id}")
def update_database_route(
    db_id: uuid.UUID, body: UpdateDatabaseRequest,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    db = svc.update_database(
        session, db_id, name=body.name, description=body.description, entity_schema=body.entity_schema,
    )
    return JSONResponse(status_code=200, content=_ok(svc.serialize_database(db)))


@mini_app_databases_router.delete("/{db_id}")
def delete_database_route(db_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    svc.delete_database(session, db_id)
    return JSONResponse(status_code=200, content=_ok({"id": str(db_id)}))


@mini_app_databases_router.get("/{db_id}/rows")
def list_database_rows_route(db_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok(svc.list_database_rows(session, db_id)))
```
Note: schema-validation failures raise `SchemaValidationError` (a plain `Exception`, not a `DomainError`). Confirm it converts to 422 — in `routes.py` the create path wraps it into `DomainError(..., http_status=422)`. If `SchemaValidationError` is **not** globally handled, wrap the service calls here in `try/except SchemaValidationError as exc: raise DomainError(exc.reason, code="schema_rejected", http_status=422)` (import `DomainError` from `app.core.errors`, `SchemaValidationError` from `schema_validation`). Apply the same wrap in `create_database_route` and `update_database_route`.

- [ ] **Step 3: Wire the router**

In `backend/app/main.py`, add the import near the other mini_app import:
```python
from app.modules.mini_app.database_routes import mini_app_databases_router
```
And after `app.include_router(mini_app_rows_router)` (line ~116):
```python
# Database page — Mini-App Database (reusable schema template) CRUD routes.
app.include_router(mini_app_databases_router)
```

- [ ] **Step 4: Manual smoke** (optional, user-run) — start backend, `GET /mini-app-databases` returns `{"data": [], ...}`.

- [ ] **Step 5: Commit**
```
git add backend/app/modules/mini_app/database_service.py backend/app/modules/mini_app/database_routes.py backend/app/main.py
git commit -m "feat(mini-app): Mini-App Database CRUD service + routes"
```

---

## Task 3: Back end — mini-app create accepts `database_id`; serialize exposes it

**Files:**
- Modify: `backend/app/modules/mini_app/provisioner.py`
- Modify: `backend/app/modules/mini_app/lifecycle.py`
- Modify: `backend/app/modules/mini_app/service.py`
- Modify: `backend/app/modules/mini_app/routes.py`

**Interfaces:**
- Consumes: `get_database` / `serialize`-schema from Task 2 module; `MiniAppDatabase.entity_schema`.
- Produces: `POST /mini-apps` accepts optional `database_id`; `serialize_app` returns `database_id`.

- [ ] **Step 1: Thread `database_id` through the provisioner**

In `provisioner.py`, add to `ProvisioningPlan` (after `whitelist_user_ids`):
```python
    database_id: uuid.UUID | None = None
```
And in `build_provisioning_plan`, add param `database_id: uuid.UUID | None = None` (after `created_by_agent_id`) and pass `database_id=database_id` into the returned `ProvisioningPlan(...)`.

- [ ] **Step 2: Set `database_id` on the model**

In `lifecycle.py` `plan_to_model`, add to the `MiniApp(...)` kwargs:
```python
        database_id=plan.database_id,
```

- [ ] **Step 3: Accept `database_id` in the service create fn**

In `service.py` `create_app_from_schema`, add param `database_id: uuid.UUID | None = None` (after `created_by_agent_id`) and pass `database_id=database_id` into `build_provisioning_plan(...)`. Add `"database_id": str(app.database_id) if app.database_id else None` to the dict returned by `serialize_app`.

- [ ] **Step 4: Resolve `database_id` → schema in the route**

In `routes.py`, add to `CreateMiniAppRequest`:
```python
    database_id: uuid.UUID | None = None
```
Update the `_require_schema_or_description` validator to also accept a database id:
```python
    @model_validator(mode="after")
    def _require_schema_or_description(self) -> "CreateMiniAppRequest":
        if self.database_id is None and self.entity_schema is None and not self.expected_output:
            raise ValueError(
                "one of 'database_id', 'entity_schema', or ('description' + 'expected_output') is required"
            )
        return self
```
In `create_mini_app_route`, add the database branch **before** the `entity_schema`/emission branches:
```python
    from app.modules.mini_app import database_service
    from app.modules.mini_app.schema_validation import validate_ui_spec, validate_entity_schema

    principal = _principal(request)
    prompt: str | None = None
    if body.database_id is not None:
        db = database_service.get_database(session, body.database_id)
        schema = validate_entity_schema(db.entity_schema)
        ui_spec = validate_ui_spec(body.ui_spec or {})
    elif body.entity_schema is not None:
        schema = validate_entity_schema(body.entity_schema)
        ui_spec = validate_ui_spec(body.ui_spec or {})
    else:
        try:
            schema, ui_spec, prompt = emit_schema(body.description, body.expected_output or "")
        except SchemaValidationError as exc:
            _audit_emission(principal.user_id, "mini_app.schema_rejected", {"reason": exc.reason})
            raise DomainError(exc.reason, code="schema_rejected", http_status=422) from exc
```
Then pass `database_id=body.database_id` into `service.create_app_from_schema(...)`. (Keep the existing `enqueue_build` + response.)

- [ ] **Step 5: Manual smoke** (user-run) — `POST /mini-apps {name, database_id}` returns 201 with `database_id` set and `entity_schema` matching the database.

- [ ] **Step 6: Commit**
```
git add backend/app/modules/mini_app/provisioner.py backend/app/modules/mini_app/lifecycle.py backend/app/modules/mini_app/service.py backend/app/modules/mini_app/routes.py
git commit -m "feat(mini-app): create from database_id (copy schema) + expose database_id"
```

---

## Task 4: Front end — API + hooks (mini-app databases)

**Files:**
- Create: `frontend/src/lib/miniAppDatabasesApi.ts`
- Create: `frontend/src/hooks/useMiniAppDatabases.ts`

**Interfaces:**
- Produces: `MiniAppDatabase`, `MiniAppDatabaseRow`, `EntitySchema`, `SchemaField` types; `useMiniAppDatabases()`, `useMiniAppDatabaseMutations()`, `useMiniAppDatabaseRows(id)`.

> Note: global/tenant-wide KB already exists on this branch (`useKbPool`, `kbApi`) — do NOT create `globalKbApi`/`useGlobalKb`. Steps 3–4 of the original plan are removed.

- [ ] **Step 1: Mini-app databases API**

`frontend/src/lib/miniAppDatabasesApi.ts`:
```typescript
import { apiFetch } from "./api";

export type FieldType =
  | "string" | "longtext" | "integer" | "number" | "boolean" | "date" | "enum";

export interface SchemaField {
  name: string;
  type: FieldType;
  label?: string;
  required?: boolean;
  options?: string[];
}

export interface EntitySchema {
  fields: SchemaField[];
  primary_display?: string | null;
}

export interface MiniAppDatabase {
  id: string;
  name: string;
  description: string;
  entity_schema: EntitySchema;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface MiniAppDatabaseRow {
  row_id: string;
  app_id: string;
  data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CreateDatabaseInput {
  name: string;
  description?: string;
  entity_schema: EntitySchema;
}

export interface UpdateDatabaseInput {
  name?: string;
  description?: string;
  entity_schema?: EntitySchema;
}

export const listDatabases = () => apiFetch<MiniAppDatabase[]>("/mini-app-databases");
export const getDatabase = (id: string) => apiFetch<MiniAppDatabase>(`/mini-app-databases/${id}`);
export const createDatabase = (input: CreateDatabaseInput) =>
  apiFetch<MiniAppDatabase>("/mini-app-databases", { method: "POST", body: JSON.stringify(input) });
export const updateDatabase = (id: string, input: UpdateDatabaseInput) =>
  apiFetch<MiniAppDatabase>(`/mini-app-databases/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const deleteDatabase = (id: string) =>
  apiFetch<{ id: string }>(`/mini-app-databases/${id}`, { method: "DELETE" });
export const listDatabaseRows = (id: string) =>
  apiFetch<MiniAppDatabaseRow[]>(`/mini-app-databases/${id}/rows`);
```

- [ ] **Step 2: Mini-app databases hooks**

`frontend/src/hooks/useMiniAppDatabases.ts`:
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDatabase, deleteDatabase, listDatabaseRows, listDatabases, updateDatabase,
  type CreateDatabaseInput, type MiniAppDatabase, type MiniAppDatabaseRow, type UpdateDatabaseInput,
} from "../lib/miniAppDatabasesApi";

const KEY = ["mini-app-databases"] as const;

export function useMiniAppDatabases() {
  return useQuery<MiniAppDatabase[], Error>({ queryKey: KEY, queryFn: listDatabases });
}

export function useMiniAppDatabaseRows(id: string | undefined) {
  return useQuery<MiniAppDatabaseRow[], Error>({
    queryKey: [...KEY, id, "rows"],
    queryFn: () => listDatabaseRows(id as string),
    enabled: Boolean(id),
  });
}

export function useMiniAppDatabaseMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const create = useMutation<MiniAppDatabase, Error, CreateDatabaseInput>({
    mutationFn: createDatabase, onSuccess: invalidate,
  });
  const update = useMutation<MiniAppDatabase, Error, { id: string; input: UpdateDatabaseInput }>({
    mutationFn: ({ id, input }) => updateDatabase(id, input), onSuccess: invalidate,
  });
  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: deleteDatabase, onSuccess: invalidate,
  });
  return { create, update, remove };
}
```

- [ ] **Step 3: Commit**
```
git add frontend/src/lib/miniAppDatabasesApi.ts frontend/src/hooks/useMiniAppDatabases.ts
git commit -m "feat(frontend): mini-app database api/hooks"
```

---

## Task 5: Front end — Sidebar `Database` nav + route swap

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/components/CommandPalette/navigationCommands.ts`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `DatabasePage` (Task 6) — import may temporarily be a stub if Task 6 runs after; recommended order is Task 6 before Task 5, or create `database.tsx` stub first.
- Produces: `/database` route live; nav item points to it.

- [ ] **Step 1: Sidebar item**

In `frontend/src/components/Sidebar.tsx`: change the import `BookOpen` → `Database` in the lucide import block, and replace the nav entry:
```typescript
  { to: "/database", label: "Database", icon: Database },
```
(Remove the old `{ to: "/knowledge-base", label: "Knowledge Base", icon: BookOpen }` line.)

- [ ] **Step 2: Command palette nav target**

In `navigationCommands.ts`: replace the `knowledge-base` `NAV_TARGETS` entry with
```typescript
  { id: "database", title: "Go to Database", path: "/database" },
```
Replace the `BookOpen` import with `Database`, and in `NAV_ICON_BY_ID` replace `"knowledge-base": BookOpen,` with `database: Database,`.

- [ ] **Step 3: Route**

In `frontend/src/App.tsx`: add `import DatabasePage from "./routes/database";`. The `/knowledge-base` and `/tools` routes already exist and point to real pages (`KnowledgeBasePage`, `ToolsPage`) — **leave them unchanged**. Add the new `/database` route beside them (after the `/tools` line):
```typescript
        <Route path="/database" element={<DatabasePage />} />
```
The sidebar no longer links to `/knowledge-base` directly (it now links to `/database`), but the `/knowledge-base` route stays reachable (e.g. from the command palette / deep links). No redirect.

- [ ] **Step 4: Commit**
```
git add frontend/src/components/Sidebar.tsx frontend/src/components/CommandPalette/navigationCommands.ts frontend/src/App.tsx
git commit -m "feat(frontend): replace Knowledge Base nav with Database page route"
```

---

## Task 6: Front end — DatabasePage shell (reuses existing KnowledgeBasePage)

**Files:**
- Create: `frontend/src/routes/database.tsx`

**Interfaces:**
- Consumes: existing `routes/knowledge-base/KnowledgeBasePage.tsx` (default export, no props); `MiniAppDatabaseSection` (Task 7).
- Produces: `DatabasePage` default export with two tabs.

- [ ] **Step 1: Page shell with two tabs**

The KB tab renders the **existing** `<KnowledgeBasePage />` verbatim (it already owns tenant-wide upload/list/delete via `useKbPool`). The Mini-App Databases tab renders `MiniAppDatabaseSection` (Task 7). `frontend/src/routes/database.tsx`:
```typescript
/* Database page — two sections: Knowledge Base (agents, reuses the existing
 * tenant-wide KnowledgeBasePage) + Mini-App Databases. Sidebar item now points
 * here (/database). */
import { useState } from "react";
import KnowledgeBasePage from "./knowledge-base/KnowledgeBasePage";
import MiniAppDatabaseSection from "../components/database/MiniAppDatabaseSection";

type Tab = "kb" | "mini-app-db";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "kb", label: "Knowledge Base" },
  { id: "mini-app-db", label: "Mini-App Databases" },
];

export function DatabasePage() {
  const [tab, setTab] = useState<Tab>("kb");
  return (
    <div data-testid="vaic-database-page">
      <div
        role="tablist"
        aria-label="Database sections"
        style={{ display: "flex", gap: "var(--space-2)", borderBottom: "1px solid var(--color-border)", marginBottom: "var(--space-4)" }}
      >
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className="vaic-focusable"
            onClick={() => setTab(t.id)}
            style={{
              padding: "var(--space-2) var(--space-3)",
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t.id ? "var(--color-primary)" : "transparent"}`,
              color: tab === t.id ? "var(--color-primary)" : "var(--color-text-secondary)",
              fontWeight: tab === t.id ? 600 : 500,
              cursor: "pointer",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "kb" ? <KnowledgeBasePage /> : <MiniAppDatabaseSection />}
    </div>
  );
}

export default DatabasePage;
```
Note: `KnowledgeBasePage` renders its own "Knowledge Base" `<h1>` + advisory — that serves as the KB section header under the tab bar (no separate Database `<h1>`, to avoid a redundant stacked title). If Task 7 (`MiniAppDatabaseSection`) is not yet created, do Task 7 **before** this task (recommended order 7 → 6 → 5) so the import resolves.

- [ ] **Step 2: Commit**
```
git add frontend/src/routes/database.tsx
git commit -m "feat(frontend): Database page shell (KB + Mini-App Databases tabs)"
```

---

## Task 7: Front end — Schema field editor + Mini-App Databases tab

**Files:**
- Create: `frontend/src/components/database/SchemaFieldEditor.tsx`
- Create: `frontend/src/components/database/MiniAppDatabaseSection.tsx`

**Interfaces:**
- Consumes: `useMiniAppDatabases`, `useMiniAppDatabaseMutations`, `useMiniAppDatabaseRows`, types (Task 4); `ui` primitives.
- Produces: `SchemaFieldEditor` (`value: EntitySchema`, `onChange: (s: EntitySchema) => void`); `MiniAppDatabaseSection` default export.

- [ ] **Step 1: Schema field editor**

`frontend/src/components/database/SchemaFieldEditor.tsx`:
```typescript
/* Editor for a Mini-App Database entity_schema: a list of fields
 * (name, type, required, label; comma-separated options when type=enum). */
import { Trash2, Plus } from "lucide-react";
import { Button } from "../ui";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import type { EntitySchema, FieldType, SchemaField } from "../../lib/miniAppDatabasesApi";

const FIELD_TYPES: FieldType[] = ["string", "longtext", "integer", "number", "boolean", "date", "enum"];

export interface SchemaFieldEditorProps {
  value: EntitySchema;
  onChange: (schema: EntitySchema) => void;
}

export default function SchemaFieldEditor({ value, onChange }: SchemaFieldEditorProps) {
  const fields = value.fields;

  function update(idx: number, patch: Partial<SchemaField>) {
    const next = fields.map((f, i) => (i === idx ? { ...f, ...patch } : f));
    onChange({ ...value, fields: next });
  }
  function add() {
    onChange({ ...value, fields: [...fields, { name: "", type: "string", required: false }] });
  }
  function remove(idx: number) {
    onChange({ ...value, fields: fields.filter((_, i) => i !== idx) });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
      {fields.map((f, idx) => (
        <div key={idx} style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr 1.2fr auto auto", gap: "var(--space-2)", alignItems: "center" }}>
          <input
            className="vaic-form-input vaic-focusable" placeholder="field_name"
            value={f.name} onChange={(e) => update(idx, { name: e.target.value })}
          />
          <select
            className="vaic-form-input vaic-focusable"
            value={f.type} onChange={(e) => update(idx, { type: e.target.value as FieldType })}
          >
            {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          {f.type === "enum" ? (
            <input
              className="vaic-form-input vaic-focusable" placeholder="opt1, opt2, opt3"
              value={(f.options ?? []).join(", ")}
              onChange={(e) => update(idx, { options: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
            />
          ) : (
            <input
              className="vaic-form-input vaic-focusable" placeholder="Label (optional)"
              value={f.label ?? ""} onChange={(e) => update(idx, { label: e.target.value || undefined })}
            />
          )}
          <label style={{ display: "inline-flex", gap: "var(--space-1)", alignItems: "center", fontSize: "var(--text-small)" }}>
            <input type="checkbox" checked={Boolean(f.required)} onChange={(e) => update(idx, { required: e.target.checked })} />
            Required
          </label>
          <Button variant="icon" aria-label={`Remove field ${f.name || idx + 1}`} onClick={() => remove(idx)}>
            <Trash2 size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
          </Button>
        </div>
      ))}
      <div>
        <Button variant="secondary" onClick={add}>
          <Plus size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" /> Add field
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Mini-App Databases section (list + create/edit + rows viewer)**

`frontend/src/components/database/MiniAppDatabaseSection.tsx`:
```typescript
/* Mini-App Databases section (Database page) — list, create/edit schema,
 * read-only rows viewer. Branch order: error -> loading -> empty -> data. */
import { useState, type FormEvent } from "react";
import {
  Button, Card, ConfirmDialog, EmptyState, ErrorState, FormField, Skeleton, Table, useToast,
  type TableColumn,
} from "../ui";
import SchemaFieldEditor from "./SchemaFieldEditor";
import { useMiniAppDatabases, useMiniAppDatabaseMutations, useMiniAppDatabaseRows } from "../../hooks/useMiniAppDatabases";
import type { EntitySchema, MiniAppDatabase, MiniAppDatabaseRow } from "../../lib/miniAppDatabasesApi";

const EMPTY_SCHEMA: EntitySchema = { fields: [{ name: "", type: "string", required: false }] };

interface DraftState {
  id: string | null;         // null = creating
  name: string;
  description: string;
  schema: EntitySchema;
}

export default function MiniAppDatabaseSection() {
  const query = useMiniAppDatabases();
  const { create, update, remove } = useMiniAppDatabaseMutations();
  const { show } = useToast();

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [viewingRowsFor, setViewingRowsFor] = useState<MiniAppDatabase | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const databases = query.data ?? [];

  function startCreate() {
    setDraft({ id: null, name: "", description: "", schema: EMPTY_SCHEMA });
  }
  function startEdit(db: MiniAppDatabase) {
    setDraft({ id: db.id, name: db.name, description: db.description, schema: db.entity_schema });
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!draft) return;
    if (!draft.name.trim()) { show("Name is required", "error"); return; }
    if (draft.schema.fields.length === 0 || draft.schema.fields.some((f) => !f.name.trim())) {
      show("Every field needs a name", "error"); return;
    }
    const input = { name: draft.name, description: draft.description, entity_schema: draft.schema };
    if (draft.id === null) {
      create.mutate(input, {
        onSuccess: () => { show("Database created"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to create database", "error"),
      });
    } else {
      update.mutate({ id: draft.id, input }, {
        onSuccess: () => { show("Database updated"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to update database", "error"),
      });
    }
  }

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Database deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  const columns: TableColumn<MiniAppDatabase>[] = [
    { key: "name", header: "Name" },
    { key: "description", header: "Description", render: (d) => d.description || "—" },
    { key: "fields", header: "Fields", render: (d) => String(d.entity_schema.fields.length) },
    {
      key: "actions", header: "",
      render: (d) => (
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <Button variant="secondary" onClick={() => setViewingRowsFor(d)}>Data</Button>
          <Button variant="secondary" onClick={() => startEdit(d)}>Edit</Button>
          <Button variant="secondary" onClick={() => setPendingDeleteId(d.id)}>Delete</Button>
        </div>
      ),
    },
  ];

  function renderList() {
    if (query.isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load databases"}
          retry={<Button variant="secondary" onClick={() => query.refetch()}>Retry</Button>}
        />
      );
    }
    if (query.isLoading) return <Skeleton lines={3} height="24px" />;
    if (databases.length === 0) {
      return <EmptyState title="No databases yet" description="Create a database to define a reusable schema for Mini-Apps." />;
    }
    return <Table<MiniAppDatabase> columns={columns} rows={databases} rowId={(d) => d.id} caption="Mini-App Databases" />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card
        title="Mini-App Databases"
        headerAction={<Button variant="primary" onClick={startCreate}>New database</Button>}
      >
        {renderList()}
      </Card>

      {draft && (
        <Card title={draft.id === null ? "Create database" : "Edit database"}>
          <form onSubmit={handleSubmit}>
            <FormField
              label="Name" required value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-db-description">Description</label>
              <textarea
                id="vaic-db-description" rows={2} className="vaic-form-input vaic-focusable"
                value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </div>
            <div className="vaic-form-field">
              <label className="vaic-form-label">Schema fields</label>
              <SchemaFieldEditor value={draft.schema} onChange={(schema) => setDraft({ ...draft, schema })} />
            </div>
            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
              <Button variant="primary" type="submit" disabled={create.isPending || update.isPending}>
                {draft.id === null ? "Create" : "Save"}
              </Button>
              <Button variant="secondary" type="button" onClick={() => setDraft(null)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {viewingRowsFor && (
        <DatabaseRowsCard db={viewingRowsFor} onClose={() => setViewingRowsFor(null)} />
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this database?"
        body="Mini-Apps referencing it keep their copied schema but lose the link. This cannot be undone."
        confirmLabel="Delete" cancelLabel="Cancel"
        onConfirm={confirmDelete} onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}

function DatabaseRowsCard({ db, onClose }: { db: MiniAppDatabase; onClose: () => void }) {
  const rowsQuery = useMiniAppDatabaseRows(db.id);
  const rows = rowsQuery.data ?? [];
  const fieldNames = db.entity_schema.fields.map((f) => f.name);

  const columns: TableColumn<MiniAppDatabaseRow>[] = fieldNames.map((name) => ({
    key: name, header: name,
    render: (r) => {
      const v = r.data[name];
      return v === undefined || v === null ? "—" : String(v);
    },
  }));

  return (
    <Card title={`Data — ${db.name}`} headerAction={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      {rowsQuery.isError ? (
        <ErrorState
          message={rowsQuery.error?.message ?? "Failed to load rows"}
          retry={<Button variant="secondary" onClick={() => rowsQuery.refetch()}>Retry</Button>}
        />
      ) : rowsQuery.isLoading ? (
        <Skeleton lines={3} height="20px" />
      ) : rows.length === 0 ? (
        <EmptyState title="No data yet" description="Mini-Apps using this database will show their records here." />
      ) : (
        <Table<MiniAppDatabaseRow> columns={columns} rows={rows} rowId={(r) => r.row_id} caption={`${db.name} rows`} />
      )}
    </Card>
  );
}
```
Note: confirm `FormField`, `Table`, `ConfirmDialog`, `EmptyState`, `Skeleton`, `useToast` are exported from `components/ui/index.ts` (they are used across existing routes). `Button variant` supports `primary`/`secondary`/`icon`.

- [ ] **Step 3: Commit**
```
git add frontend/src/components/database/SchemaFieldEditor.tsx frontend/src/components/database/MiniAppDatabaseSection.tsx
git commit -m "feat(frontend): Mini-App Databases tab (schema editor + rows viewer)"
```

---

## Task 8: Front end — Mini-apps list-only landing + create modal with DB dropdown

**Files:**
- Modify: `frontend/src/lib/miniAppsApi.ts`
- Create: `frontend/src/components/mini-apps/CreateMiniAppModal.tsx`
- Modify: `frontend/src/routes/mini-apps.tsx`

**Interfaces:**
- Consumes: `useMiniAppDatabases` (Task 4), `createMiniApp` (existing).
- Produces: `MiniApp.database_id`; `CreateMiniAppInput.database_id`; `CreateMiniAppModal` component.

- [ ] **Step 1: Extend the mini-apps API types**

In `frontend/src/lib/miniAppsApi.ts`: add `database_id: string | null;` to `MiniApp` (after `build_error`), and `database_id?: string;` to `CreateMiniAppInput`.

- [ ] **Step 2: Create-mini-app modal**

`frontend/src/components/mini-apps/CreateMiniAppModal.tsx`:
```typescript
/* Create Mini-App modal. Primary path: pick an existing Database (sends
 * database_id; server copies its schema). Fallback: description + expected
 * output (LLM emission). Visibility tier + whitelist as before. */
import { useState, type FormEvent } from "react";
import { Button, Card, FormField, useToast } from "../ui";
import { useMiniAppDatabases } from "../../hooks/useMiniAppDatabases";
import { createMiniApp, type CreateMiniAppInput, type MiniApp } from "../../lib/miniAppsApi";
import { useMutation, useQueryClient } from "@tanstack/react-query";

type Tier = MiniApp["visibility_tier"];

export interface CreateMiniAppModalProps {
  onClose: () => void;
}

export default function CreateMiniAppModal({ onClose }: CreateMiniAppModalProps) {
  const qc = useQueryClient();
  const { show } = useToast();
  const dbQuery = useMiniAppDatabases();
  const databases = dbQuery.data ?? [];

  const [name, setName] = useState("");
  const [databaseId, setDatabaseId] = useState<string>("");
  const [description, setDescription] = useState("");
  const [expectedOutput, setExpectedOutput] = useState("");
  const [tier, setTier] = useState<Tier>("public");
  const [whitelist, setWhitelist] = useState("");

  const create = useMutation<MiniApp, Error, CreateMiniAppInput>({
    mutationFn: createMiniApp,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["mini-apps"] });
      show("Mini-App created");
      onClose();
    },
    onError: (err) => show(err.message || "Failed to create Mini-App", "error"),
  });

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!name.trim()) { show("Name is required", "error"); return; }
    if (!databaseId && !expectedOutput.trim()) {
      show("Pick a Database or provide an expected output", "error"); return;
    }
    const wl = tier === "private" ? whitelist.split(",").map((s) => s.trim()).filter(Boolean) : [];
    const input: CreateMiniAppInput = {
      name,
      description: description || undefined,
      visibility_tier: tier,
      whitelist_user_ids: wl,
    };
    if (databaseId) input.database_id = databaseId;
    else input.expected_output = expectedOutput;
    create.mutate(input);
  }

  return (
    <div
      role="dialog" aria-modal="true" aria-label="Create Mini-App"
      style={{
        position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
        display: "flex", alignItems: "center", justifyContent: "center", zIndex: 50, padding: "var(--space-4)",
      }}
      onClick={onClose}
    >
      <div style={{ width: "min(560px, 100%)", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
        <Card title="Create Mini-App" headerAction={<Button variant="secondary" onClick={onClose}>Close</Button>}>
          <form onSubmit={handleSubmit} data-testid="vaic-create-mini-app-form">
            <FormField
              label="Name" required value={name}
              onChange={(e) => setName(e.target.value)}
              validate={(v) => (v.trim() ? null : "Name is required")}
            />

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-mini-app-database">Database</label>
              <select
                id="vaic-mini-app-database" className="vaic-form-input vaic-focusable"
                value={databaseId} onChange={(e) => setDatabaseId(e.target.value)}
              >
                <option value="">— None (describe below) —</option>
                {databases.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
              <p className="text-small" style={{ color: "var(--color-text-tertiary)" }}>
                Pick a Database to reuse its schema, or leave blank and describe the app below.
              </p>
            </div>

            {!databaseId && (
              <>
                <div className="vaic-form-field">
                  <label className="vaic-form-label" htmlFor="vaic-mini-app-description">Description</label>
                  <textarea
                    id="vaic-mini-app-description" rows={2} className="vaic-form-input vaic-focusable"
                    value={description} onChange={(e) => setDescription(e.target.value)}
                  />
                </div>
                <div className="vaic-form-field">
                  <label className="vaic-form-label" htmlFor="vaic-mini-app-expected-output">Expected output</label>
                  <textarea
                    id="vaic-mini-app-expected-output" rows={3} className="vaic-form-input vaic-focusable"
                    value={expectedOutput} onChange={(e) => setExpectedOutput(e.target.value)}
                  />
                </div>
              </>
            )}

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-mini-app-tier">Visibility tier</label>
              <select
                id="vaic-mini-app-tier" className="vaic-form-input vaic-focusable"
                value={tier} onChange={(e) => setTier(e.target.value as Tier)}
              >
                <option value="public">Public</option>
                <option value="need_auth">Need Auth</option>
                <option value="private">Private</option>
              </select>
            </div>

            {tier === "private" && (
              <FormField
                label="Whitelist user ids"
                helperText="Comma-separated user ids allowed to access this Mini-App"
                value={whitelist} onChange={(e) => setWhitelist(e.target.value)}
              />
            )}

            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
              <Button variant="primary" type="submit" disabled={create.isPending}>
                {create.isPending ? "Creating…" : "Create Mini-App"}
              </Button>
              <Button variant="secondary" type="button" onClick={onClose}>Cancel</Button>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Slim down the list page to list-only + modal trigger**

Rewrite `frontend/src/routes/mini-apps.tsx` so the landing is only the header + grid + a "Create Mini-App" button that opens the modal. Remove the inline create `<form>` and its state; keep `BUILD_STATUS_TO_RUN_STATE`, `TIER_LABELS`, and `renderList`. New body:
```typescript
import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Button, Card, EmptyState, ErrorState, Skeleton, StatusPill } from "../components/ui";
import type { RunState } from "../lib/icons";
import { semanticIcons, ICON_STROKE_WIDTH } from "../lib/icons";
import { listMiniApps, type MiniApp } from "../lib/miniAppsApi";
import CreateMiniAppModal from "../components/mini-apps/CreateMiniAppModal";

const BUILD_STATUS_TO_RUN_STATE: Record<MiniApp["build_status"], RunState> = {
  pending: "pending", building: "running", ready: "success", failed: "error",
};
const TIER_LABELS: Record<MiniApp["visibility_tier"], string> = {
  public: "Public", need_auth: "Need Auth", private: "Private",
};

export function MiniAppsPage() {
  const query = useQuery<MiniApp[], Error>({ queryKey: ["mini-apps"], queryFn: listMiniApps });
  const [showCreate, setShowCreate] = useState(false);

  const apps = query.data ?? [];
  const isLoading = query.isLoading;
  const isError = query.isError;
  const isEmpty = !isLoading && !isError && apps.length === 0;
  const MiniAppIcon = semanticIcons.MiniApp;

  function renderList() {
    if (isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load Mini-Apps"}
          retry={<Button variant="secondary" onClick={() => query.refetch()}>Retry</Button>}
        />
      );
    }
    if (isLoading) {
      return (
        <div data-testid="vaic-mini-apps-loading" style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <Skeleton height="80px" /><Skeleton height="80px" /><Skeleton height="80px" />
        </div>
      );
    }
    if (isEmpty) {
      return (
        <EmptyState
          icon={<MiniAppIcon size={48} strokeWidth={ICON_STROKE_WIDTH} />}
          title="No Mini-Apps yet."
          description="Create your first Mini-App with the button above."
        />
      );
    }
    return (
      <div
        data-testid="vaic-mini-apps-grid"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "var(--space-3)" }}
      >
        {apps.map((app) => (
          <Card
            key={app.id} title={app.name} subtitle={TIER_LABELS[app.visibility_tier]}
            headerAction={<StatusPill state={BUILD_STATUS_TO_RUN_STATE[app.build_status]} />}
          >
            {app.description && (
              <p className="text-small" style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-2)" }}>
                {app.description}
              </p>
            )}
            <Link
              to={`/mini-apps/${app.id}`} className="vaic-btn vaic-btn-secondary vaic-focusable"
              style={{ textDecoration: "none", display: "inline-flex" }}
            >
              Open
            </Link>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div data-testid="vaic-mini-apps-page">
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "var(--space-4)" }}>
        <div>
          <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>Mini-Apps</h1>
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            Lightweight, LLM-generated data apps scoped to your Tenant.
          </p>
        </div>
        <Button variant="primary" onClick={() => setShowCreate(true)}>Create Mini-App</Button>
      </header>

      {renderList()}

      {showCreate && <CreateMiniAppModal onClose={() => setShowCreate(false)} />}
    </div>
  );
}

export default MiniAppsPage;
```

- [ ] **Step 4: Commit**
```
git add frontend/src/lib/miniAppsApi.ts frontend/src/components/mini-apps/CreateMiniAppModal.tsx frontend/src/routes/mini-apps.tsx
git commit -m "feat(frontend): mini-apps list-only landing + create modal with database dropdown"
```

---

## Task 9: Front end — Mini-app detail shows bound database

**Files:**
- Modify: `frontend/src/routes/mini-app-host.tsx`

**Interfaces:**
- Consumes: `MiniApp.database_id` (Task 8), `useMiniAppDatabases` (Task 4).

- [ ] **Step 1: Render the bound database line**

In `frontend/src/routes/mini-app-host.tsx`, add imports:
```typescript
import { Link } from "react-router-dom";
import { useMiniAppDatabases } from "../hooks/useMiniAppDatabases";
```
Inside `MiniAppHostPage`, after `const app = appQuery.data;`, add:
```typescript
  const dbQuery = useMiniAppDatabases();
  const boundDb = app?.database_id
    ? (dbQuery.data ?? []).find((d) => d.id === app.database_id)
    : undefined;
```
In the returned header (after the `{app.description && ...}` block, still inside `<header>`), add:
```typescript
        {app.database_id && (
          <p className="text-small" style={{ color: "var(--color-text-tertiary)", marginTop: "var(--space-1)" }}>
            Database:{" "}
            <Link to="/database" className="vaic-focusable" style={{ color: "var(--color-primary)" }}>
              {boundDb?.name ?? "View in Database"}
            </Link>
          </p>
        )}
```

- [ ] **Step 2: Manual verification** (user-run) — create a database, create a mini-app bound to it, open the app; header shows "Database: <name>" linking to `/database`. Confirm the database's Data viewer lists rows the app writes.

- [ ] **Step 3: Commit**
```
git add frontend/src/routes/mini-app-host.tsx
git commit -m "feat(frontend): show bound database on mini-app detail page"
```

---

## Self-Review notes (author)

- **Spec coverage:** sidebar Database swap (Task 5), two-tab page (Tasks 6–7), KB tab reuses `/kb/documents` (Task 6), Mini-App Database entity + RLS + FK (Tasks 1–2), create-from-`database_id` copy (Task 3), list→detail with create modal + dropdown (Task 8), detail shows binding (Task 9). All spec sections mapped.
- **Type consistency:** `MiniAppDatabase`, `EntitySchema`, `SchemaField`, `MiniAppDatabaseRow` defined once in `miniAppDatabasesApi.ts` and imported everywhere; `CreateMiniAppInput.database_id` matches back-end `CreateMiniAppRequest.database_id`; `serialize_app` `database_id` matches `MiniApp.database_id` front-end field.
- **Ordering:** Task 5 imports `DatabasePage` (Task 6) and Task 6 imports `MiniAppDatabaseSection` (Task 7). Implement **Task 7 → 6 → 5** (or stub) to avoid a broken import between commits. Back-end Tasks 1→2→3 are strictly ordered.
- **Assumptions to verify during implementation (noted inline):** `ConflictError` maps to 409; `SchemaValidationError` needs explicit 422 wrapping in the new routes; `KbStatusPill` prop names; `ui` exports (`FormField`, `Table`, `ConfirmDialog`, `Button variant="icon"`, `StatusPill`). These are existing symbols used by current code — confirm signatures, don't assume.
