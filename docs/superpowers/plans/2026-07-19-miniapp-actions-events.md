# Mini-App Actions / Events — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a new row is written to a Mini-App whose data model is a Mini-App Database, fire an **Action** that dispatches the bound **Workflow** to run in the background (ARQ) and sends **notifications** to human staff — demo: a customer appraisal profile submitted through a mini-app auto-starts the appraisal workflow while staff get notified.

**Architecture:** The existing (currently no-op) `_emit_row_change` seam in `mini_app/service.py` becomes a **transactional-ish outbox writer**: each material row change inserts an `action_events` row. A new ARQ **cron fan-out** (mirroring the proven `run_schedule_trigger_fanout` pattern) enumerates tenants with pending events and enqueues a per-tenant `@tenant_aware_job` that (1) resolves matching **Action bindings** (`database_id` + `event_type` → `workflow_id`), (2) creates a `WorkflowRun` via `create_run(..., role="builder")` and enqueues the existing `run_workflow` job, (3) creates `notifications` for the staff on the binding, and (4) on a later sweep, notifies again when the run reaches a terminal status. A new **`notifications`** table + REST + a **Topbar bell** (polling) surface staff alerts. A filled-in **`/actions`** page manages bindings.

**Tech Stack:** FastAPI / SQLAlchemy / Alembic / ARQ / Python 3.13 (back end); Vite + React 19 + TypeScript + TanStack Query (front end).

## Global Constraints

- Routes are thin adapters returning the `{"data","error","meta"}` envelope via a local `_ok(...)` helper (mirror `mini_app/database_routes.py`).
- New tenant tables get RLS: `ALTER TABLE ... ENABLE ROW LEVEL SECURITY;` + `FORCE`, policy `tenant_id = current_setting('app.tenant_id')::uuid` (USING + WITH CHECK), and `GRANT SELECT, INSERT, UPDATE, DELETE ... TO vaic_app;`. Mirror `alembic/versions/aa10database01_create_mini_app_databases.py` **exactly**.
- **Alembic head is a single revision `aa10database01`** (it already merged the two prior heads). The first new migration's `down_revision = "aa10database01"`; the second chains off the first. No further head-merge needed.
- Background jobs: enqueue only via `enqueue_job_with_context(pool, "job_name", **kwargs)` (materializes `_tenant_id`, AD-10). Worker functions are `@tenant_aware_job async def fn(ctx, **kwargs)`; read the RLS-scoped session from `ctx["session"]`; run sync SQLAlchemy via `loop.run_in_executor`; **re-assert RLS** (`assume_app_role(session)` + `set_tenant_session_var(session, tenant_id)`) after every commit because `SET LOCAL` is transaction-scoped (see `orchestrator_worker._transition` and `mini_app_worker._reassert_rls`).
- Cross-tenant cron sweeps run under `AdminSessionLocal` (BYPASSRLS) and enqueue **one job per tenant** with `_tenant_id` materialized directly — mirror `run_schedule_trigger_fanout` (`app/core/jobs.py`).
- `create_run` requires `role == "builder"` and reads `tenant_context.get()` for the tenant — the poller passes `role="builder"` as a system actor (tenant_context is already set by `@tenant_aware_job`).
- Front end: TanStack Query (query keys are arrays; mutations invalidate the same key), `components/ui` primitives only (there is **no** `Modal`/`Select`/`Tabs` primitive — use native `<select class="vaic-form-input vaic-focusable">` and `Card`/`FormField`/`Table`/`ConfirmDialog`), branch order **error → loading → empty → data**, toasts on mutation success/error. `apiFetch<T>` already unwraps the envelope and throws `ApiError`.
- **NO automated tests. Do NOT run typecheck / lint / build / format** — the user verifies manually. (Overrides any TDD mandate in the sub-skills.)
- Windows shell is PowerShell; venv Python at `backend/.venv`. Run backend commands from `backend/`.
- Keep files focused (< ~200 LOC); kebab-case/snake-case descriptive names; descriptive comments.

---

## File Structure

**Back end — new module `backend/app/modules/notification/`:**
- `__init__.py` — module marker.
- `models.py` — `Notification` ORM.
- `service.py` — `create_notification` / `list_notifications` / `mark_read` / `mark_all_read` / `serialize_notification`.
- `routes.py` — `notifications_router` (prefix `/notifications`).

**Back end — new module `backend/app/modules/action/`:**
- `__init__.py` — module marker.
- `models.py` — `ActionBinding` + `ActionEvent` ORM.
- `emit.py` — `emit_action_event(session, *, tenant_id, app_id, database_id, event_type, row_id, payload)` (outbox writer called by the mini_app seam).
- `service.py` — binding CRUD + serializers; `dispatch_pending_events` + `notify_completed_events` (worker logic, sync).
- `routes.py` — `actions_router` (prefix `/actions`).
- `worker.py` — `dispatch_action_events_fanout` (cron) + `process_tenant_action_events` (`@tenant_aware_job`).

**Back end — new migrations:**
- `backend/alembic/versions/ac10notify01_create_notifications.py` — `notifications` table + RLS.
- `backend/alembic/versions/ac20actions01_create_actions.py` — `action_bindings` + `action_events` tables + RLS.

**Back end — modified:**
- `backend/app/modules/mini_app/service.py` — `_emit_row_change` writes the outbox (signature gains `session`, `app`).
- `backend/app/main.py` — include `notifications_router` + `actions_router`.
- `backend/scripts/run_worker.py` — register `process_tenant_action_events` + the `dispatch_action_events_fanout` cron.

**Front end — new:**
- `frontend/src/lib/notificationsApi.ts`, `frontend/src/hooks/useNotifications.ts`, `frontend/src/components/NotificationsBell.tsx`.
- `frontend/src/lib/actionsApi.ts`, `frontend/src/hooks/useActions.ts`, `frontend/src/routes/actions/ActionsPage.tsx`.

**Front end — modified:**
- `frontend/src/components/Topbar.tsx` — mount `<NotificationsBell/>`.
- `frontend/src/App.tsx` — swap the `/actions` `ComingSoon` for `ActionsPage`.

---

## Task 1: Back end — `notifications` table, model, migration, service, routes

**Files:**
- Create: `backend/app/modules/notification/__init__.py`
- Create: `backend/app/modules/notification/models.py`
- Create: `backend/app/modules/notification/service.py`
- Create: `backend/app/modules/notification/routes.py`
- Create: `backend/alembic/versions/ac10notify01_create_notifications.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Produces: `Notification` ORM (`__tablename__ = "notifications"`); `create_notification(session, *, tenant_id, user_id, category, title, body="", ref=None) -> Notification`; `serialize_notification(n) -> dict`; `notifications_router`.

- [ ] **Step 1: Module marker**

`backend/app/modules/notification/__init__.py`:
```python
"""Notification module — persisted, per-user staff alerts (Actions/Events pairing).

Tenant-scoped via RLS (app.tenant_id GUC); each row also carries `user_id` (the
recipient). Delivery is frontend polling of `GET /notifications` (no SSE/websocket).
"""
```

- [ ] **Step 2: Model**

`backend/app/modules/notification/models.py`:
```python
"""Notification ORM — one persisted alert for one recipient user."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    ref: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Service**

`backend/app/modules/notification/service.py`:
```python
"""Notification service — create + list + mark-read over per-user alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.modules.notification.models import Notification


def create_notification(
    session: Session, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    category: str, title: str, body: str = "", ref: dict[str, Any] | None = None,
) -> Notification:
    """Insert one notification. Caller owns the surrounding transaction/commit."""
    n = Notification(
        tenant_id=tenant_id, user_id=user_id, category=category,
        title=title, body=body or "", ref=ref or {},
    )
    session.add(n)
    session.flush()  # assign id; caller commits
    return n


def list_notifications(session: Session, user_id: uuid.UUID, *, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc())
    return list(session.execute(stmt).scalars())


def mark_read(session: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    n = session.get(Notification, notification_id)
    if n is None or n.user_id != user_id:
        raise NotFoundError(f"notification {notification_id} not found")
    if n.read_at is None:
        n.read_at = datetime.now(UTC)
    session.commit()
    session.refresh(n)
    return n


def mark_all_read(session: Session, user_id: uuid.UUID) -> int:
    result = session.execute(
        sa_update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    session.commit()
    return int(result.rowcount or 0)


def serialize_notification(n: Notification) -> dict[str, Any]:
    return {
        "id": str(n.id), "category": n.category, "title": n.title, "body": n.body,
        "ref": n.ref, "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat(),
    }
```

- [ ] **Step 4: Routes**

`backend/app/modules/notification/routes.py`:
```python
"""Notification HTTP routes — the current user's own alerts (RLS + user_id filter)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.notification import service as svc

notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _current_user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


@notifications_router.get("")
def list_notifications_route(  # noqa: B008
    request: Request, unread: bool = False, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    items = svc.list_notifications(session, _current_user_id(request), unread_only=unread)
    return JSONResponse(status_code=200, content=_ok([svc.serialize_notification(n) for n in items]))


@notifications_router.patch("/{notification_id}/read")
def mark_read_route(  # noqa: B008
    notification_id: uuid.UUID, request: Request, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    n = svc.mark_read(session, _current_user_id(request), notification_id)
    return JSONResponse(status_code=200, content=_ok(svc.serialize_notification(n)))


@notifications_router.post("/read-all")
def mark_all_read_route(  # noqa: B008
    request: Request, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    updated = svc.mark_all_read(session, _current_user_id(request))
    return JSONResponse(status_code=200, content=_ok({"updated": updated}))
```

- [ ] **Step 5: Migration**

`backend/alembic/versions/ac10notify01_create_notifications.py` (mirror `aa10database01` RLS shape):
```python
"""create notifications table with RLS.

Tenant-isolation RLS (app.tenant_id GUC), mirroring
aa10database01_create_mini_app_databases.py. Each row also carries user_id
(recipient); the API additionally filters WHERE user_id = current user.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ac10notify01"
down_revision: str | Sequence[str] | None = "aa10database01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("ref", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])

    op.execute("ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE notifications FORCE ROW LEVEL SECURITY;")
    op.execute(
        """CREATE POLICY tenant_isolation_policy ON notifications
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON notifications TO vaic_app;")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON notifications;")
    op.execute("ALTER TABLE notifications NO FORCE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE notifications DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
```

- [ ] **Step 6: Wire the router**

In `backend/app/main.py`, add near the other module imports:
```python
from app.modules.notification.routes import notifications_router
```
And after `app.include_router(mini_app_databases_router)` (line ~124):
```python
# Actions/Events — per-user staff notifications.
app.include_router(notifications_router)
```

- [ ] **Step 7: Apply the migration** (real DB action)

Run from `backend/`:
```
.venv\Scripts\python.exe -m alembic upgrade head
```
Expected: `Running upgrade aa10database01 -> ac10notify01`.

- [ ] **Step 8: Commit**
```
git add backend/app/modules/notification backend/alembic/versions/ac10notify01_create_notifications.py backend/app/main.py
git commit -m "feat(notification): notifications table + service + routes (RLS, per-user)"
```

---

## Task 2: Back end — `action_bindings` + `action_events` tables, models, migration

**Files:**
- Create: `backend/app/modules/action/__init__.py`
- Create: `backend/app/modules/action/models.py`
- Create: `backend/alembic/versions/ac20actions01_create_actions.py`

**Interfaces:**
- Produces: `ActionBinding` ORM (`action_bindings`: `id, tenant_id, owner_id, name, database_id, event_type, workflow_id, notify_user_ids, is_active, created_at, updated_at`); `ActionEvent` ORM (`action_events`: `id, tenant_id, app_id, database_id, event_type, row_id, payload, status, workflow_run_id, result, completed_notified, error, created_at, processed_at`); `EVENT_TYPES`, `ACTION_EVENT_STATUSES`.

- [ ] **Step 1: Module marker**

`backend/app/modules/action/__init__.py`:
```python
"""Action/Event module — bind Mini-App Database row events to Workflow dispatch.

An `action_bindings` row maps (database_id, event_type) -> workflow_id + a staff
notify list. The mini_app row-change seam writes `action_events` (outbox); an ARQ
cron fan-out resolves bindings, creates + enqueues a WorkflowRun, and notifies staff.
"""
```

- [ ] **Step 2: Models**

`backend/app/modules/action/models.py`:
```python
"""Action ORM models — bindings (config) + events (outbox)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.ids import uuid7

EVENT_TYPES = ("row.created", "row.updated", "row.deleted")
ACTION_EVENT_STATUSES = ("pending", "dispatched", "failed", "skipped")


class ActionBinding(Base):
    __tablename__ = "action_bindings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_action_bindings_tenant_name"),
        CheckConstraint(
            "event_type IN ('row.created','row.updated','row.deleted')",
            name="ck_action_bindings_event_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    database_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mini_app_databases.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, default="row.created", server_default="row.created")
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    notify_user_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ActionEvent(Base):
    __tablename__ = "action_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','dispatched','failed','skipped')",
            name="ck_action_events_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False
    )
    # Denormalized snapshot of the app's database_id at emit time (no FK: the
    # database may be deleted; the event is an immutable historical record).
    database_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", server_default="pending")
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    completed_notified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 3: Migration**

`backend/alembic/versions/ac20actions01_create_actions.py`:
```python
"""create action_bindings + action_events tables with RLS.

Tenant-isolation RLS (app.tenant_id GUC), mirroring
aa10database01_create_mini_app_databases.py. action_bindings = config
(database_id + event_type -> workflow_id); action_events = the row-change outbox.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "ac20actions01"
down_revision: str | Sequence[str] | None = "ac10notify01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO vaic_app;")


def upgrade() -> None:
    op.create_table(
        "action_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("database_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mini_app_databases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False, server_default="row.created"),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notify_user_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
                  nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("tenant_id", "name", name="uq_action_bindings_tenant_name"),
        sa.CheckConstraint("event_type IN ('row.created','row.updated','row.deleted')",
                           name="ck_action_bindings_event_type"),
    )
    op.create_index("ix_action_bindings_db_event", "action_bindings", ["database_id", "event_type"])
    _enable_rls("action_bindings")

    op.create_table(
        "action_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("app_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mini_apps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("database_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("workflow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("completed_notified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','dispatched','failed','skipped')",
                           name="ck_action_events_status"),
    )
    op.create_index("ix_action_events_tenant_status", "action_events", ["tenant_id", "status"])
    _enable_rls("action_events")


def downgrade() -> None:
    for table in ("action_events", "action_bindings"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
    op.drop_index("ix_action_events_tenant_status", table_name="action_events")
    op.drop_table("action_events")
    op.drop_index("ix_action_bindings_db_event", table_name="action_bindings")
    op.drop_table("action_bindings")
```

- [ ] **Step 4: Apply the migration**

From `backend/`:
```
.venv\Scripts\python.exe -m alembic upgrade head
```
Expected: `Running upgrade ac10notify01 -> ac20actions01`.

- [ ] **Step 5: Commit**
```
git add backend/app/modules/action/__init__.py backend/app/modules/action/models.py backend/alembic/versions/ac20actions01_create_actions.py
git commit -m "feat(action): action_bindings + action_events tables + models (RLS)"
```

---

## Task 3: Back end — Action binding CRUD service + routes + wiring

**Files:**
- Create: `backend/app/modules/action/service.py`
- Create: `backend/app/modules/action/routes.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Consumes: `ActionBinding` (Task 2), `MiniAppPrincipal` (`mini_app/visibility.py`), `ConflictError`/`NotFoundError` (`app.core.errors`).
- Produces: `actions_router` (prefix `/actions`) with list/create/get/patch/delete; `serialize_binding(b) -> dict`. (Worker functions `dispatch_pending_events` / `notify_completed_events` are added to this same `service.py` in Task 5.)

- [ ] **Step 1: Service (binding CRUD)**

`backend/app/modules/action/service.py`:
```python
"""Action service — CRUD over action_bindings (Database-event -> Workflow config).

Worker-side resolution (`dispatch_pending_events` / `notify_completed_events`) is
appended in Task 5; this file starts with binding CRUD only.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.modules.action.models import EVENT_TYPES, ActionBinding
from app.modules.mini_app.visibility import MiniAppPrincipal


def list_bindings(session: Session) -> list[ActionBinding]:
    return list(
        session.execute(select(ActionBinding).order_by(ActionBinding.created_at.desc())).scalars()
    )


def get_binding(session: Session, binding_id: uuid.UUID) -> ActionBinding:
    b = session.get(ActionBinding, binding_id)
    if b is None:
        raise NotFoundError(f"action binding {binding_id} not found")
    return b


def create_binding(
    session: Session, *, principal: MiniAppPrincipal, name: str,
    database_id: uuid.UUID, event_type: str, workflow_id: uuid.UUID,
    notify_user_ids: list[uuid.UUID], is_active: bool = True,
) -> ActionBinding:
    _validate_event_type(event_type)
    if _name_taken(session, principal.tenant_id, name):
        raise ConflictError(f"an action named '{name}' already exists")
    b = ActionBinding(
        tenant_id=principal.tenant_id, owner_id=principal.user_id, name=name,
        database_id=database_id, event_type=event_type, workflow_id=workflow_id,
        notify_user_ids=notify_user_ids, is_active=is_active,
    )
    session.add(b)
    session.commit()
    session.refresh(b)
    return b


def update_binding(
    session: Session, binding_id: uuid.UUID, *,
    name: str | None, database_id: uuid.UUID | None, event_type: str | None,
    workflow_id: uuid.UUID | None, notify_user_ids: list[uuid.UUID] | None, is_active: bool | None,
) -> ActionBinding:
    b = get_binding(session, binding_id)
    if name is not None and name != b.name:
        if _name_taken(session, b.tenant_id, name):
            raise ConflictError(f"an action named '{name}' already exists")
        b.name = name
    if database_id is not None:
        b.database_id = database_id
    if event_type is not None:
        _validate_event_type(event_type)
        b.event_type = event_type
    if workflow_id is not None:
        b.workflow_id = workflow_id
    if notify_user_ids is not None:
        b.notify_user_ids = notify_user_ids
    if is_active is not None:
        b.is_active = is_active
    b.updated_at = datetime.now(UTC)
    session.commit()
    session.refresh(b)
    return b


def delete_binding(session: Session, binding_id: uuid.UUID) -> None:
    b = get_binding(session, binding_id)
    session.delete(b)
    session.commit()


def serialize_binding(b: ActionBinding) -> dict[str, Any]:
    return {
        "id": str(b.id), "name": b.name, "database_id": str(b.database_id),
        "event_type": b.event_type, "workflow_id": str(b.workflow_id),
        "notify_user_ids": [str(u) for u in (b.notify_user_ids or [])],
        "is_active": b.is_active, "owner_id": str(b.owner_id),
        "created_at": b.created_at.isoformat(), "updated_at": b.updated_at.isoformat(),
    }


def _validate_event_type(event_type: str) -> None:
    if event_type not in EVENT_TYPES:
        raise ConflictError(f"event_type must be one of {EVENT_TYPES}")


def _name_taken(session: Session, tenant_id: uuid.UUID, name: str) -> bool:
    stmt = select(ActionBinding.id).where(
        ActionBinding.tenant_id == tenant_id, ActionBinding.name == name
    )
    return session.execute(stmt).first() is not None
```

- [ ] **Step 2: Routes**

`backend/app/modules/action/routes.py`:
```python
"""Action binding HTTP routes (Actions page). Thin adapters -> service -> _ok."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.action import service as svc
from app.modules.mini_app.visibility import MiniAppPrincipal

actions_router = APIRouter(prefix="/actions", tags=["actions"])


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


class CreateActionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    database_id: uuid.UUID
    event_type: str = "row.created"
    workflow_id: uuid.UUID
    notify_user_ids: list[uuid.UUID] = Field(default_factory=list)
    is_active: bool = True


class UpdateActionRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    database_id: uuid.UUID | None = None
    event_type: str | None = None
    workflow_id: uuid.UUID | None = None
    notify_user_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None


@actions_router.get("")
def list_actions_route(session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok([svc.serialize_binding(b) for b in svc.list_bindings(session)]))


@actions_router.post("")
def create_action_route(  # noqa: B008
    body: CreateActionRequest, request: Request, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    b = svc.create_binding(
        session, principal=_principal(request), name=body.name,
        database_id=body.database_id, event_type=body.event_type, workflow_id=body.workflow_id,
        notify_user_ids=body.notify_user_ids, is_active=body.is_active,
    )
    return JSONResponse(status_code=201, content=_ok(svc.serialize_binding(b)))


@actions_router.get("/{binding_id}")
def get_action_route(binding_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    return JSONResponse(status_code=200, content=_ok(svc.serialize_binding(svc.get_binding(session, binding_id))))


@actions_router.patch("/{binding_id}")
def update_action_route(  # noqa: B008
    binding_id: uuid.UUID, body: UpdateActionRequest, session: Session = Depends(get_tenant_session),
) -> JSONResponse:
    b = svc.update_binding(
        session, binding_id, name=body.name, database_id=body.database_id,
        event_type=body.event_type, workflow_id=body.workflow_id,
        notify_user_ids=body.notify_user_ids, is_active=body.is_active,
    )
    return JSONResponse(status_code=200, content=_ok(svc.serialize_binding(b)))


@actions_router.delete("/{binding_id}")
def delete_action_route(binding_id: uuid.UUID, session: Session = Depends(get_tenant_session)) -> JSONResponse:  # noqa: B008
    svc.delete_binding(session, binding_id)
    return JSONResponse(status_code=200, content=_ok({"id": str(binding_id)}))
```

- [ ] **Step 3: Wire the router**

In `backend/app/main.py`, add the import:
```python
from app.modules.action.routes import actions_router
```
And after `app.include_router(notifications_router)` (added in Task 1):
```python
# Actions/Events — Mini-App Database event -> Workflow binding CRUD.
app.include_router(actions_router)
```

- [ ] **Step 4: Manual smoke** (optional, user-run) — start backend, `GET /actions` returns `{"data": [], ...}`.

- [ ] **Step 5: Commit**
```
git add backend/app/modules/action/service.py backend/app/modules/action/routes.py backend/app/main.py
git commit -m "feat(action): action binding CRUD service + routes"
```

---

## Task 4: Back end — row-change seam writes the action-event outbox

**Files:**
- Create: `backend/app/modules/action/emit.py`
- Modify: `backend/app/modules/mini_app/service.py`

**Interfaces:**
- Consumes: `ActionEvent` (Task 2).
- Produces: `emit_action_event(session, *, tenant_id, app_id, database_id, event_type, row_id, payload) -> None`; `_emit_row_change` now writes an `action_events` row for every material row change.

- [ ] **Step 1: Outbox writer**

`backend/app/modules/action/emit.py`:
```python
"""Outbox writer — the mini_app row-change seam's Action Bus publish (FR-17).

Inserts one `action_events` row per material row change. Best-effort outbox:
the mini_app service commits the row first, then this appends the event in the
same session (a short follow-up commit). The ARQ fan-out consumes pending rows.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.modules.action.models import ActionEvent


def emit_action_event(
    session: Session, *, tenant_id: uuid.UUID, app_id: uuid.UUID,
    database_id: uuid.UUID | None, event_type: str, row_id: uuid.UUID | None,
    payload: dict[str, Any],
) -> None:
    event = ActionEvent(
        tenant_id=tenant_id, app_id=app_id, database_id=database_id,
        event_type=event_type, row_id=row_id, payload=payload, status="pending",
    )
    session.add(event)
    session.commit()
```

- [ ] **Step 2: Rewrite the seam in `mini_app/service.py`**

Replace the current no-op `_emit_row_change` (service.py:32-34):
```python
def _emit_row_change(app_id: uuid.UUID, event_type: str, payload: dict[str, Any]) -> None:
    """Seam for FR-17 App Event emission (Epic 5). Intentional no-op now."""
    return None
```
with (note the new `session`, `app` parameters — carries `app.database_id` + tenant):
```python
def _emit_row_change(
    session: Session, app: MiniApp, event_type: str, payload: dict[str, Any]
) -> None:
    """FR-17 App Event emission — write the action-event outbox (Actions/Events).

    Best-effort: the row is already committed by the caller; we append an
    `action_events` row (its own short commit). Import is function-local to keep
    the mini_app module decoupled from the action module at import time.
    """
    from app.modules.action.emit import emit_action_event

    row_id = payload.get("row_id")
    emit_action_event(
        session,
        tenant_id=app.tenant_id,
        app_id=app.id,
        database_id=app.database_id,
        event_type=event_type,
        row_id=uuid.UUID(row_id) if row_id else None,
        payload=payload,
    )
```

- [ ] **Step 3: Update the three call sites in `mini_app/service.py`**

In `create_row` (service.py:111) — pass the row data so the workflow gets it as input:
```python
    _emit_row_change(session, app, "row.created", {"row_id": str(row.id), "data": coerced})
```
In `update_row` (service.py:155):
```python
    _emit_row_change(session, app, "row.updated", {"row_id": str(row_id), "data": coerced})
```
In `delete_row` (service.py:163):
```python
    _emit_row_change(session, app, "row.deleted", {"row_id": str(row_id)})
```
(`app` and `session` are already in scope in all three functions; `coerced` is the coerced data already computed in `create_row`/`update_row`.)

- [ ] **Step 4: Manual smoke** (user-run) — with backend running, `POST /apps/{app_id}/rows` on an app whose `database_id` is set, then confirm one `action_events` row exists (`status='pending'`) via psql/DB tool. (No worker yet — dispatch lands in Task 5.)

- [ ] **Step 5: Commit**
```
git add backend/app/modules/action/emit.py backend/app/modules/mini_app/service.py
git commit -m "feat(action): row-change seam writes action_events outbox"
```

---

## Task 5: Back end — dispatch worker (resolve bindings → run workflow → notify)

**Files:**
- Modify: `backend/app/modules/action/service.py` (append worker-side resolution functions)
- Create: `backend/app/modules/action/worker.py`
- Modify: `backend/scripts/run_worker.py`

**Interfaces:**
- Consumes: `ActionBinding`/`ActionEvent` (Task 2), `create_run` (`orchestrator/service.py`), `WorkflowRun`/`RUN_STATUSES` (`orchestrator/models.py`), `create_notification` (`notification/service.py`), `enqueue_job_with_context`/`tenant_aware_job`/`TENANT_ID_KWARG` (`app.core.jobs`), `assume_app_role` (`app.core.deps`), `set_tenant_context`/`set_tenant_session_var`/`tenant_context` (`app.core.tenant_context`).
- Produces: `dispatch_pending_events(session, tenant_id) -> list[str]` (returns run ids to enqueue); `notify_completed_events(session, tenant_id) -> None`; ARQ `process_tenant_action_events` (`@tenant_aware_job`) + `dispatch_action_events_fanout` (cron); both registered on the worker process.

- [ ] **Step 1: Append resolution logic to `action/service.py`**

Add these imports at the top of `backend/app/modules/action/service.py` (below the existing imports):
```python
from app.core.deps import assume_app_role
from app.core.tenant_context import set_tenant_context, set_tenant_session_var
from app.modules.action.models import ActionEvent
```
Then append the following functions to the end of the file:
```python
# --- Worker-side resolution (called from action/worker.py inside a job) -----

# Terminal run statuses that should trigger a completion notification.
# Confirm against orchestrator.models.RUN_STATUSES.
TERMINAL_RUN_STATUSES = {"completed", "failed", "completed_with_failures"}


def _reassert(session: Session, tenant_id: uuid.UUID) -> None:
    """Re-apply role + tenant RLS var after a commit (SET LOCAL is txn-scoped)."""
    set_tenant_context(tenant_id)
    assume_app_role(session)
    set_tenant_session_var(session, tenant_id)


def dispatch_pending_events(session: Session, tenant_id: uuid.UUID) -> list[str]:
    """Resolve each pending action_event -> create WorkflowRun(s) + notifications.

    Returns the list of created run ids for the caller to enqueue as
    `run_workflow` jobs. `create_run` commits internally, so we re-fetch the
    event and re-assert RLS around every commit boundary.
    """
    from app.modules.notification.service import create_notification
    from app.modules.orchestrator.service import create_run

    _reassert(session, tenant_id)
    event_ids = list(
        session.execute(
            select(ActionEvent.id)
            .where(ActionEvent.status == "pending")
            .order_by(ActionEvent.created_at)
        ).scalars()
    )

    run_ids: list[str] = []
    for event_id in event_ids:
        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is None or ev.status != "pending":
            continue

        # No database bound -> nothing can match.
        if ev.database_id is None:
            _finish_event(session, ev, status="skipped", result={"reason": "app has no database"})
            continue

        bindings = list(
            session.execute(
                select(ActionBinding).where(
                    ActionBinding.database_id == ev.database_id,
                    ActionBinding.event_type == ev.event_type,
                    ActionBinding.is_active.is_(True),
                )
            ).scalars()
        )
        if not bindings:
            _finish_event(session, ev, status="skipped", result={"reason": "no matching active binding"})
            continue

        # Snapshot primitives before create_run commits + expires ORM state.
        app_id = str(ev.app_id)
        row_id = str(ev.row_id) if ev.row_id else None
        event_type = ev.event_type
        data = (ev.payload or {}).get("data", {})

        dispatched: list[dict[str, Any]] = []
        for b in bindings:
            binding_id = str(b.id)
            binding_name = b.name
            workflow_id = b.workflow_id
            recipients = list(b.notify_user_ids or []) or [b.owner_id]

            _reassert(session, tenant_id)
            run = create_run(
                session, workflow_id, role="builder",
                input={
                    "source": "action", "action_id": binding_id, "app_id": app_id,
                    "row_id": row_id, "event_type": event_type, "data": data,
                },
            )
            run_id = str(run.id)
            run_ids.append(run_id)

            _reassert(session, tenant_id)
            notif_ids: list[str] = []
            for uid in recipients:
                n = create_notification(
                    session, tenant_id=tenant_id, user_id=uid,
                    category="action.dispatched",
                    title=f"New submission received — {binding_name}",
                    body="A new record started background workflow processing.",
                    ref={"workflow_run_id": run_id, "app_id": app_id,
                         "action_id": binding_id, "row_id": row_id},
                )
                notif_ids.append(str(n.id))
            session.commit()
            dispatched.append({"action_id": binding_id, "run_id": run_id, "notification_ids": notif_ids})

        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is not None:
            _finish_event(
                session, ev, status="dispatched",
                result={"dispatched": dispatched},
                workflow_run_id=uuid.UUID(dispatched[0]["run_id"]) if dispatched else None,
            )

    return run_ids


def notify_completed_events(session: Session, tenant_id: uuid.UUID) -> None:
    """Sweep dispatched events whose run reached a terminal status; notify once."""
    from app.modules.notification.service import create_notification
    from app.modules.orchestrator.models import WorkflowRun

    _reassert(session, tenant_id)
    event_ids = list(
        session.execute(
            select(ActionEvent.id).where(
                ActionEvent.status == "dispatched",
                ActionEvent.completed_notified.is_(False),
                ActionEvent.workflow_run_id.isnot(None),
            )
        ).scalars()
    )

    for event_id in event_ids:
        _reassert(session, tenant_id)
        ev = session.get(ActionEvent, event_id)
        if ev is None:
            continue
        run = session.get(WorkflowRun, ev.workflow_run_id)
        if run is None or run.status not in TERMINAL_RUN_STATUSES:
            continue

        app_id = str(ev.app_id)
        run_status = run.status
        run_id = str(run.id)
        for d in (ev.result or {}).get("dispatched", []):
            b = session.get(ActionBinding, uuid.UUID(d["action_id"]))
            if b is None:
                continue
            recipients = list(b.notify_user_ids or []) or [b.owner_id]
            for uid in recipients:
                create_notification(
                    session, tenant_id=tenant_id, user_id=uid,
                    category="action.completed",
                    title=f"Workflow {run_status} — {b.name}",
                    body="Background processing finished.",
                    ref={"workflow_run_id": run_id, "app_id": app_id},
                )
        ev.completed_notified = True
        session.commit()


def _finish_event(
    session: Session, ev: ActionEvent, *, status: str,
    result: dict[str, Any], workflow_run_id: uuid.UUID | None = None,
) -> None:
    ev.status = status
    ev.result = result
    ev.workflow_run_id = workflow_run_id
    ev.processed_at = datetime.now(UTC)
    session.commit()
```

- [ ] **Step 2: Worker functions**

`backend/app/modules/action/worker.py`:
```python
"""ARQ worker — Action/Event dispatch.

`dispatch_action_events_fanout` (cron, BYPASSRLS) enumerates tenants that have
pending events OR dispatched-but-not-yet-completion-notified events, and enqueues
one per-tenant `process_tenant_action_events` job (mirrors run_schedule_trigger_fanout).

`process_tenant_action_events` (@tenant_aware_job) resolves bindings, creates +
enqueues WorkflowRun(s), creates notifications, and sweeps completed runs.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from arq.connections import ArqRedis
from arq.cron import cron
from sqlalchemy import text

from app.core.db import AdminSessionLocal
from app.core.jobs import TENANT_ID_KWARG, enqueue_job_with_context, tenant_aware_job
from app.core.tenant_context import tenant_context
from app.modules.action.service import dispatch_pending_events, notify_completed_events

logger = logging.getLogger(__name__)

__all__ = ["dispatch_action_events_fanout", "process_tenant_action_events", "action_cron_jobs"]


async def dispatch_action_events_fanout(ctx: dict[str, Any]) -> None:
    """Cron entrypoint — enumerate tenants with work, enqueue one job per tenant."""
    pool: ArqRedis | None = ctx.get("arq_redis") or ctx.get("redis")
    if pool is None:
        raise RuntimeError("dispatch_action_events_fanout requires `arq_redis`/`redis` in ctx.")

    loop = asyncio.get_running_loop()

    def _tenants_with_work() -> list[uuid.UUID]:
        with AdminSessionLocal() as s:  # BYPASSRLS cross-tenant enumeration (AD-9)
            rows = s.execute(
                text(
                    "SELECT DISTINCT tenant_id FROM action_events "
                    "WHERE status = 'pending' "
                    "   OR (status = 'dispatched' AND completed_notified = false)"
                )
            ).scalars().all()
            return [uuid.UUID(str(r)) for r in rows]

    tenant_ids = await loop.run_in_executor(None, _tenants_with_work)
    if tenant_ids:
        logger.info("action dispatch fan-out: %d tenant(s) with work", len(tenant_ids))
    for tid in tenant_ids:
        # No caller contextvar in cron — materialize `_tenant_id` directly.
        await pool.enqueue_job("process_tenant_action_events", **{TENANT_ID_KWARG: str(tid)})


@tenant_aware_job
async def process_tenant_action_events(ctx: dict[str, Any]) -> None:
    """Per-tenant: dispatch pending events (+ enqueue runs), then completion sweep."""
    session = ctx["session"]
    tenant_id = tenant_context.get()
    if tenant_id is None:
        raise RuntimeError("process_tenant_action_events: tenant_context unset at entry")
    pool: ArqRedis | None = ctx.get("redis") or ctx.get("arq_redis")
    loop = asyncio.get_running_loop()

    # Sync DB work (create runs + notifications) on the executor thread.
    run_ids: list[str] = await loop.run_in_executor(
        None, dispatch_pending_events, session, tenant_id
    )

    # Enqueue each created run through the existing run_workflow job.
    # tenant_context is set on THIS async task by @tenant_aware_job, so
    # enqueue_job_with_context materializes the correct _tenant_id.
    if pool is not None:
        for run_id in run_ids:
            await enqueue_job_with_context(pool, "run_workflow", run_id=run_id)

    # Completion sweep (sync).
    await loop.run_in_executor(None, notify_completed_events, session, tenant_id)


# Cron cadence — poll every 5s for snappy demo dispatch. `unique=True` prevents
# overlap; `run_at_startup=False` keeps tests quiet.
action_cron_jobs = [
    cron(
        dispatch_action_events_fanout,
        name="action_events_fanout",
        second=set(range(0, 60, 5)),
        run_at_startup=False,
        unique=True,
    ),
]
```

- [ ] **Step 3: Register on the worker process**

In `backend/scripts/run_worker.py`, add the import beside the existing worker imports:
```python
from app.modules.action.worker import (  # noqa: E402
    action_cron_jobs,
    process_tenant_action_events,
)
```
Then extend the merged config (replace the existing `_combined_worker_config = replace(...)` block) to add the new function **and** cron entries:
```python
# Merge Mini-App builder + Action dispatch onto the orchestrator worker (AD-1).
_combined_worker_config = replace(
    worker_config,
    functions=[*worker_config.functions, build_mini_app, process_tenant_action_events],
    cron_jobs_list=[*worker_config.cron_jobs_list, *action_cron_jobs],
)
```

- [ ] **Step 4: Manual end-to-end smoke** (user-run) — full demo path:
  1. Ensure Redis + backend running; start the worker: `.venv\Scripts\python.exe -m scripts.run_worker`.
  2. Create a Mini-App Database (`POST /mini-app-databases`), create a Mini-App bound to it (`POST /mini-apps {name, database_id}`), create a Workflow, then an Action (`POST /actions {name, database_id, event_type:"row.created", workflow_id, notify_user_ids:[...]}`).
  3. `POST /apps/{app_id}/rows` a new record. Within ~5s: an `action_events` row flips `pending→dispatched`, a `workflow_runs` row is created + runs, and `notifications` rows appear for the staff. `GET /notifications` returns them.

- [ ] **Step 5: Commit**
```
git add backend/app/modules/action/service.py backend/app/modules/action/worker.py backend/scripts/run_worker.py
git commit -m "feat(action): ARQ fan-out dispatch — resolve bindings, run workflow, notify staff"
```

---

## Task 6: Front end — notifications API + hook + Topbar bell

**Files:**
- Create: `frontend/src/lib/notificationsApi.ts`
- Create: `frontend/src/hooks/useNotifications.ts`
- Create: `frontend/src/components/NotificationsBell.tsx`
- Modify: `frontend/src/components/Topbar.tsx`

**Interfaces:**
- Consumes: `apiFetch` (`lib/api.ts`), `useToast`/UI primitives.
- Produces: `Notification` type; `useNotifications()` (polls every 10s), `useNotificationMutations()`; `<NotificationsBell/>` mounted in the Topbar right section.

- [ ] **Step 1: API module**

`frontend/src/lib/notificationsApi.ts`:
```typescript
import { apiFetch } from "./api";

export interface Notification {
  id: string;
  category: string;
  title: string;
  body: string;
  ref: Record<string, unknown>;
  read_at: string | null;
  created_at: string;
}

export const listNotifications = (unread = false) =>
  apiFetch<Notification[]>(`/notifications${unread ? "?unread=true" : ""}`);

export const markNotificationRead = (id: string) =>
  apiFetch<Notification>(`/notifications/${id}/read`, { method: "PATCH" });

export const markAllNotificationsRead = () =>
  apiFetch<{ updated: number }>(`/notifications/read-all`, { method: "POST" });
```

- [ ] **Step 2: Hook**

`frontend/src/hooks/useNotifications.ts`:
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  listNotifications, markAllNotificationsRead, markNotificationRead,
  type Notification,
} from "../lib/notificationsApi";

const KEY = ["notifications"] as const;
const POLL_INTERVAL_MS = 10_000;

export function useNotifications() {
  return useQuery<Notification[], Error>({
    queryKey: KEY,
    queryFn: () => listNotifications(false),
    refetchInterval: POLL_INTERVAL_MS,
  });
}

export function useNotificationMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const markRead = useMutation<Notification, Error, string>({
    mutationFn: markNotificationRead, onSuccess: invalidate,
  });
  const markAllRead = useMutation<{ updated: number }, Error, void>({
    mutationFn: markAllNotificationsRead, onSuccess: invalidate,
  });
  return { markRead, markAllRead };
}
```

- [ ] **Step 3: Bell component**

`frontend/src/components/NotificationsBell.tsx` (reuses the Topbar's existing badge/icon-button visual language — `Bell` icon + red count badge + a simple dropdown panel):
```typescript
/* Notifications bell for the Topbar. Polls GET /notifications (10s), shows the
 * unread count as a badge, and a click-to-open dropdown listing recent alerts
 * with mark-read / mark-all-read. */
import { useState } from "react";
import { Bell } from "lucide-react";
import { useNotifications, useNotificationMutations } from "../hooks/useNotifications";

export default function NotificationsBell() {
  const { data } = useNotifications();
  const { markRead, markAllRead } = useNotificationMutations();
  const [open, setOpen] = useState(false);

  const items = data ?? [];
  const unread = items.filter((n) => n.read_at === null).length;

  return (
    <div style={{ position: "relative" }}>
      <button
        type="button"
        className="vaic-focusable"
        aria-label="Notifications"
        title="Notifications"
        onClick={() => setOpen((v) => !v)}
        style={{
          position: "relative", background: "none", border: "none",
          cursor: "pointer", color: "var(--color-text-secondary)",
          display: "inline-flex", alignItems: "center", padding: "var(--space-1)",
        }}
      >
        <Bell size={18} strokeWidth={1.5} aria-hidden="true" />
        {unread > 0 && (
          <span
            style={{
              position: "absolute", top: -4, right: -4, minWidth: 16, height: 16,
              padding: "0 4px", borderRadius: 8, background: "var(--color-error)",
              color: "#fff", fontSize: 10, lineHeight: "16px", textAlign: "center",
            }}
          >
            {unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          style={{
            position: "absolute", right: 0, top: "calc(100% + 8px)", width: 340,
            maxHeight: 420, overflowY: "auto", zIndex: 60,
            background: "var(--color-surface)", border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-md)", boxShadow: "var(--shadow-md)",
            padding: "var(--space-2)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-2)" }}>
            <strong style={{ fontSize: "var(--text-small)" }}>Notifications</strong>
            <button
              type="button" className="vaic-focusable"
              onClick={() => markAllRead.mutate()}
              disabled={unread === 0 || markAllRead.isPending}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--color-primary)", fontSize: "var(--text-small)" }}
            >
              Mark all read
            </button>
          </div>

          {items.length === 0 ? (
            <p style={{ color: "var(--color-text-tertiary)", fontSize: "var(--text-small)", padding: "var(--space-2)" }}>
              No notifications yet.
            </p>
          ) : (
            items.map((n) => (
              <button
                key={n.id}
                type="button"
                className="vaic-focusable"
                onClick={() => n.read_at === null && markRead.mutate(n.id)}
                style={{
                  display: "block", width: "100%", textAlign: "left", cursor: "pointer",
                  background: n.read_at === null ? "var(--color-surface-hover)" : "transparent",
                  border: "none", borderRadius: "var(--radius-sm)",
                  padding: "var(--space-2)", marginBottom: "var(--space-1)",
                }}
              >
                <div style={{ fontSize: "var(--text-small)", fontWeight: n.read_at === null ? 600 : 400, color: "var(--color-text-primary)" }}>
                  {n.title}
                </div>
                {n.body && (
                  <div style={{ fontSize: "var(--text-xsmall, 11px)", color: "var(--color-text-secondary)" }}>{n.body}</div>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
```
Note: if any CSS custom property above is not defined in the theme (e.g. `--shadow-md`, `--text-xsmall`, `--color-surface-hover`), substitute the nearest existing token from `frontend/src/index.css` / the theme file — do not invent new tokens; a hardcoded fallback (e.g. `boxShadow: "0 4px 12px rgba(0,0,0,0.15)"`) is acceptable.

- [ ] **Step 4: Mount in the Topbar**

In `frontend/src/components/Topbar.tsx`: add the import near the top:
```typescript
import NotificationsBell from "./NotificationsBell";
```
Then in the right-section JSX, render `<NotificationsBell />` immediately before the existing "Escalation bell" `<button className="vaic-escalation-bell" ...>` (the escalation bell stays as-is; the notifications bell is the live one). If unsure where the right section is, it is the cluster containing the Cmd-K, Run split-button, `vaic-escalation-bell`, ThemeToggle, and avatar (`Topbar.tsx` ~185-227) — insert `<NotificationsBell />` just before the `vaic-escalation-bell` button.

- [ ] **Step 5: Commit**
```
git add frontend/src/lib/notificationsApi.ts frontend/src/hooks/useNotifications.ts frontend/src/components/NotificationsBell.tsx frontend/src/components/Topbar.tsx
git commit -m "feat(frontend): notifications api/hook + Topbar bell (polling)"
```

---

## Task 7: Front end — Actions page (bindings CRUD)

**Files:**
- Create: `frontend/src/lib/actionsApi.ts`
- Create: `frontend/src/hooks/useActions.ts`
- Create: `frontend/src/routes/actions/ActionsPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `apiFetch` (`lib/api.ts`), `useWorkflows` (`hooks/useWorkflows.ts`, existing), UI primitives (`Card`, `Table`, `Button`, `FormField`, `EmptyState`, `ErrorState`, `Skeleton`, `ConfirmDialog`, `useToast`), `TableColumn` type.
- Produces: `ActionBinding` type; `useActions()`, `useActionMutations()`, `useMiniAppDatabasesList()`; `<ActionsPage/>` at `/actions`.

- [ ] **Step 1: API module** (includes a lightweight databases list for the dropdown — the `GET /mini-app-databases` endpoint already exists on the back end):

`frontend/src/lib/actionsApi.ts`:
```typescript
import { apiFetch } from "./api";

export type ActionEventType = "row.created" | "row.updated" | "row.deleted";

export interface ActionBinding {
  id: string;
  name: string;
  database_id: string;
  event_type: ActionEventType;
  workflow_id: string;
  notify_user_ids: string[];
  is_active: boolean;
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface CreateActionInput {
  name: string;
  database_id: string;
  event_type: ActionEventType;
  workflow_id: string;
  notify_user_ids?: string[];
  is_active?: boolean;
}

export type UpdateActionInput = Partial<CreateActionInput>;

// Minimal shape of a Mini-App Database for the dropdown (endpoint already exists).
export interface MiniAppDatabaseOption {
  id: string;
  name: string;
}

export const listActions = () => apiFetch<ActionBinding[]>("/actions");
export const createAction = (input: CreateActionInput) =>
  apiFetch<ActionBinding>("/actions", { method: "POST", body: JSON.stringify(input) });
export const updateAction = (id: string, input: UpdateActionInput) =>
  apiFetch<ActionBinding>(`/actions/${id}`, { method: "PATCH", body: JSON.stringify(input) });
export const deleteAction = (id: string) =>
  apiFetch<{ id: string }>(`/actions/${id}`, { method: "DELETE" });

export const listMiniAppDatabases = () =>
  apiFetch<MiniAppDatabaseOption[]>("/mini-app-databases");
```

- [ ] **Step 2: Hook**

`frontend/src/hooks/useActions.ts`:
```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAction, deleteAction, listActions, listMiniAppDatabases, updateAction,
  type ActionBinding, type CreateActionInput, type MiniAppDatabaseOption, type UpdateActionInput,
} from "../lib/actionsApi";

const KEY = ["actions"] as const;

export function useActions() {
  return useQuery<ActionBinding[], Error>({ queryKey: KEY, queryFn: listActions });
}

export function useMiniAppDatabasesList() {
  return useQuery<MiniAppDatabaseOption[], Error>({
    queryKey: ["mini-app-databases", "options"],
    queryFn: listMiniAppDatabases,
  });
}

export function useActionMutations() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: KEY });

  const create = useMutation<ActionBinding, Error, CreateActionInput>({
    mutationFn: createAction, onSuccess: invalidate,
  });
  const update = useMutation<ActionBinding, Error, { id: string; input: UpdateActionInput }>({
    mutationFn: ({ id, input }) => updateAction(id, input), onSuccess: invalidate,
  });
  const remove = useMutation<{ id: string }, Error, string>({
    mutationFn: deleteAction, onSuccess: invalidate,
  });
  return { create, update, remove };
}
```

- [ ] **Step 3: Actions page**

`frontend/src/routes/actions/ActionsPage.tsx`:
```typescript
/* Actions page — bind a Mini-App Database row event to a Workflow. List +
 * create/edit + delete. Branch order: error -> loading -> empty -> data. */
import { useState, type FormEvent } from "react";
import {
  Button, Card, ConfirmDialog, EmptyState, ErrorState, FormField, Skeleton, Table, useToast,
  type TableColumn,
} from "../../components/ui";
import { useActions, useActionMutations, useMiniAppDatabasesList } from "../../hooks/useActions";
import { useWorkflows } from "../../hooks/useWorkflows";
import type { ActionBinding, ActionEventType, CreateActionInput } from "../../lib/actionsApi";

const EVENT_TYPES: ActionEventType[] = ["row.created", "row.updated", "row.deleted"];

interface DraftState {
  id: string | null;
  name: string;
  database_id: string;
  event_type: ActionEventType;
  workflow_id: string;
  notify_user_ids: string; // comma-separated in the form
  is_active: boolean;
}

const EMPTY_DRAFT: DraftState = {
  id: null, name: "", database_id: "", event_type: "row.created",
  workflow_id: "", notify_user_ids: "", is_active: true,
};

export default function ActionsPage() {
  const query = useActions();
  const dbQuery = useMiniAppDatabasesList();
  const wfQuery = useWorkflows({});
  const { create, update, remove } = useActionMutations();
  const { show } = useToast();

  const [draft, setDraft] = useState<DraftState | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const actions = query.data ?? [];
  const databases = dbQuery.data ?? [];
  const workflows = wfQuery.data ?? [];
  const dbName = (id: string) => databases.find((d) => d.id === id)?.name ?? id;
  const wfName = (id: string) => workflows.find((w) => w.id === id)?.name ?? id;

  function startCreate() { setDraft({ ...EMPTY_DRAFT }); }
  function startEdit(a: ActionBinding) {
    setDraft({
      id: a.id, name: a.name, database_id: a.database_id, event_type: a.event_type,
      workflow_id: a.workflow_id, notify_user_ids: a.notify_user_ids.join(", "), is_active: a.is_active,
    });
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!draft) return;
    if (!draft.name.trim()) { show("Name is required", "error"); return; }
    if (!draft.database_id) { show("Pick a Mini-App Database", "error"); return; }
    if (!draft.workflow_id) { show("Pick a Workflow", "error"); return; }
    const input: CreateActionInput = {
      name: draft.name.trim(),
      database_id: draft.database_id,
      event_type: draft.event_type,
      workflow_id: draft.workflow_id,
      notify_user_ids: draft.notify_user_ids.split(",").map((s) => s.trim()).filter(Boolean),
      is_active: draft.is_active,
    };
    if (draft.id === null) {
      create.mutate(input, {
        onSuccess: () => { show("Action created"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to create action", "error"),
      });
    } else {
      update.mutate({ id: draft.id, input }, {
        onSuccess: () => { show("Action updated"); setDraft(null); },
        onError: (err) => show(err.message || "Failed to update action", "error"),
      });
    }
  }

  function confirmDelete() {
    if (!pendingDeleteId) return;
    remove.mutate(pendingDeleteId, {
      onSuccess: () => show("Action deleted"),
      onError: (err) => show(err.message, "error"),
    });
    setPendingDeleteId(null);
  }

  const columns: TableColumn<ActionBinding>[] = [
    { key: "name", header: "Name" },
    { key: "database", header: "Database", render: (a) => dbName(a.database_id) },
    { key: "event", header: "Event", render: (a) => a.event_type },
    { key: "workflow", header: "Workflow", render: (a) => wfName(a.workflow_id) },
    { key: "active", header: "Active", render: (a) => (a.is_active ? "Yes" : "No") },
    {
      key: "actions", header: "",
      render: (a) => (
        <div style={{ display: "flex", gap: "var(--space-1)" }}>
          <Button variant="secondary" onClick={() => startEdit(a)}>Edit</Button>
          <Button variant="secondary" onClick={() => setPendingDeleteId(a.id)}>Delete</Button>
        </div>
      ),
    },
  ];

  function renderList() {
    if (query.isError) {
      return (
        <ErrorState
          message={query.error?.message ?? "Failed to load actions"}
          retry={<Button variant="secondary" onClick={() => query.refetch()}>Retry</Button>}
        />
      );
    }
    if (query.isLoading) return <Skeleton lines={3} height="24px" />;
    if (actions.length === 0) {
      return <EmptyState title="No actions yet" description="Create an action to run a workflow when a Mini-App Database receives new records." />;
    }
    return <Table<ActionBinding> columns={columns} rows={actions} rowId={(a) => a.id} caption="Actions" />;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
      <Card
        title="Actions"
        subtitle="Run a Workflow automatically when a Mini-App Database row event fires."
        headerAction={<Button variant="primary" onClick={startCreate}>New action</Button>}
      >
        {renderList()}
      </Card>

      {draft && (
        <Card title={draft.id === null ? "Create action" : "Edit action"}>
          <form onSubmit={handleSubmit}>
            <FormField
              label="Name" required value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-database">Mini-App Database</label>
              <select
                id="vaic-action-database" className="vaic-form-input vaic-focusable"
                value={draft.database_id} onChange={(e) => setDraft({ ...draft, database_id: e.target.value })}
              >
                <option value="">— Select a database —</option>
                {databases.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-event">Event</label>
              <select
                id="vaic-action-event" className="vaic-form-input vaic-focusable"
                value={draft.event_type}
                onChange={(e) => setDraft({ ...draft, event_type: e.target.value as ActionEventType })}
              >
                {EVENT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>

            <div className="vaic-form-field">
              <label className="vaic-form-label" htmlFor="vaic-action-workflow">Workflow</label>
              <select
                id="vaic-action-workflow" className="vaic-form-input vaic-focusable"
                value={draft.workflow_id} onChange={(e) => setDraft({ ...draft, workflow_id: e.target.value })}
              >
                <option value="">— Select a workflow —</option>
                {workflows.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
              </select>
            </div>

            <FormField
              label="Notify user IDs (comma-separated, optional)"
              helperText="Staff to notify. Leave blank to notify the action owner."
              value={draft.notify_user_ids}
              onChange={(e) => setDraft({ ...draft, notify_user_ids: e.target.value })}
            />

            <label style={{ display: "inline-flex", gap: "var(--space-1)", alignItems: "center", fontSize: "var(--text-small)" }}>
              <input
                type="checkbox" checked={draft.is_active}
                onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
              />
              Active
            </label>

            <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-3)" }}>
              <Button variant="primary" type="submit" disabled={create.isPending || update.isPending}>
                {draft.id === null ? "Create" : "Save"}
              </Button>
              <Button variant="secondary" type="button" onClick={() => setDraft(null)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      <ConfirmDialog
        open={pendingDeleteId !== null}
        title="Delete this action?"
        body="New records will no longer trigger the bound workflow. This cannot be undone."
        confirmLabel="Delete" cancelLabel="Cancel"
        onConfirm={confirmDelete} onCancel={() => setPendingDeleteId(null)}
      />
    </div>
  );
}
```
Note: `FormField` renders a controlled `<input>` and forwards `value`/`onChange`/`helperText` (confirm the prop names against `frontend/src/components/ui/FormField.tsx`; the mini-app-database plan uses the same `label`/`required`/`value`/`onChange` shape). If `FormField` does not accept `onChange` directly, use its `children` slot with a raw `<input className="vaic-form-input vaic-focusable" />` instead (same pattern used for the `<select>` fields above).

- [ ] **Step 4: Swap the route element**

In `frontend/src/App.tsx`: add the import beside the other route imports (top of file):
```typescript
import ActionsPage from "./routes/actions/ActionsPage";
```
Replace the placeholder route (App.tsx:78):
```tsx
        <Route path="/actions" element={<ComingSoon title="Actions" />} />
```
with:
```tsx
        <Route path="/actions" element={<ActionsPage />} />
```
(The Sidebar "Actions" nav item already points to `/actions` — no Sidebar change needed.)

- [ ] **Step 5: Commit**
```
git add frontend/src/lib/actionsApi.ts frontend/src/hooks/useActions.ts frontend/src/routes/actions/ActionsPage.tsx frontend/src/App.tsx
git commit -m "feat(frontend): Actions page — DB event -> workflow bindings CRUD"
```

---

## Self-Review

**Spec coverage vs the four locked decisions:**
- *Notifications = minimal DB + polling* → Task 1 (table/service/routes) + Task 6 (api/hook/bell polling every 10s). ✓
- *Dispatch = outbox + worker poller* → Task 4 (`_emit_row_change` writes `action_events`) + Task 5 (fan-out cron → per-tenant job → `create_run` + `run_workflow` enqueue). ✓
- *Actions UI = full CRUD tab* → Task 3 (backend CRUD) + Task 7 (Actions page). ✓
- *Triggers = configurable, default row.created* → `event_type` on `ActionBinding` (Task 2), the seam emits all three (Task 4), UI dropdown defaults to `row.created` (Task 7). ✓
- *Notify staff while running in background* → dispatch-time notification (Task 5 `dispatch_pending_events`) + completion notification (Task 5 `notify_completed_events`). ✓

**Type/interface consistency:**
- `create_run(session, workflow_id, *, role, input)` — called with `role="builder"` in Task 5 (matches `orchestrator/service.py:221`). ✓
- `enqueue_job_with_context(pool, "run_workflow", run_id=...)` — matches existing enqueue contract; `_tenant_id` injected by helper (never passed). ✓
- `create_notification(session, *, tenant_id, user_id, category, title, body="", ref=None)` — signature defined in Task 1, called in Task 5. ✓
- Migration chain: `aa10database01` → `ac10notify01` → `ac20actions01` (single linear head). ✓
- Front-end query keys: `["notifications"]`, `["actions"]` — mutations invalidate the same key. ✓

**Assumptions to verify during execution (flagged inline in tasks, not blockers):**
1. `TERMINAL_RUN_STATUSES` — confirm the exact terminal status strings in `orchestrator/models.py` `RUN_STATUSES` (Task 5 Step 1 comment).
2. `MiniAppPrincipal` constructor fields (`user_id, tenant_id, department_id, role`) — confirm against `mini_app/visibility.py` (reused verbatim from `database_routes.py:_principal`).
3. `FormField` prop surface (`onChange` vs `children` slot) — confirm against `components/ui/FormField.tsx` (Task 7 Step 3 note).
4. Theme CSS tokens used in `NotificationsBell` — substitute nearest existing token if any are undefined (Task 6 Step 3 note).

## Open questions

- **Completion notification recipients** — the plan notifies the same `notify_user_ids` (or owner) at both dispatch and terminal. If staff should only get the *terminal* result (not the dispatch ping), drop the `action.dispatched` block in `dispatch_pending_events`. Not blocking; current default = notify at both.
- **Poll cadence** — the dispatch cron runs every 5s (demo-snappy). For production this would move to event-driven enqueue or a longer interval; left at 5s for the demo.
