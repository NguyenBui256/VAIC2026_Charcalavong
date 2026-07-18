# Shared Tools Library + Shared KB Store (Sub-project A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Tools and KB documents from agent-owned CASCADE children to tenant-wide shared resources — an agent gains a capability by *referencing* a tool (M2M) and gains data scope by *being granted* specific KB documents (M2M) with per-document user ACLs — and expose it behind a new 6-section sidebar.

**Architecture:** Backend-first domain re-platform inside the existing `agent_builder` module (no new module, preserves AD-1). Greenfield schema reset (rebuild branch, demo-only data). Two-gate KB: `rag` tool reference + per-agent doc grant. Frontend adds the new sidebar IA plus two functional sections (Tools, Database→KB) and converts the agent Tools/KB tabs into reference pickers.

**Tech Stack:** Backend — FastAPI, SQLAlchemy 2.0, Postgres RLS, Alembic, uuid7. Frontend — React 19, react-router v7 (inline routes in `App.tsx`), TanStack Query, in-house CSS-variable design-token components (`components/ui/`), lucide-react icons.

**Spec:** `docs/superpowers/specs/2026-07-18-shared-tools-kb-re-platform-design.md`

## Global Constraints

- **No tests / no auto typecheck-lint-build** (user working-preference, overrides the skill's TDD mandate). Tasks are *implement + commit*. Verification steps are optional and manual; run them only if you choose to.
- **RLS on every new table**: `tenant_id = current_setting('app.tenant_id')::uuid`, `ENABLE` + `FORCE`, `GRANT ... TO vaic_app`. Mirror `alembic/versions/9e84be8908a0_create_kb_documents_rls.py`.
- **AD-1 module boundary**: cross-module access only via `service.py`; new tables live inside `agent_builder`.
- **AD-4 audit**: every write routes through `AuditPort` (`PostgresAuditSink`), never direct SQL to `audit_trail`. Use `crud_audit_ids(entity_id)` for CRUD audit ids.
- **Tenant context**: service functions read `tenant_context.get()`; NEVER accept `tenant_id` as an argument. RLS owns tenant isolation; intra-tenant user ACL is enforced in Python.
- **Envelope**: routes return `{"data": ..., "error": None, "meta": {}}` via the `_ok(...)` helper; `Principal` extracted via `_principal(request)`.
- **Impact analysis**: per repo `CLAUDE.md`, run GitNexus `impact({target, direction:"upstream"})` before editing a shared symbol (`Tool`, `KbDocument`, `invoke_tool`, `kb_search`, `AgentExecutor`, `get_tool_by_name`) and warn on HIGH/CRITICAL.
- **Alembic chaining**: before writing any migration, run `cd backend && uv run alembic heads` and set the new migration's `down_revision` to the reported head. Chain migrations in the order tasks create them.
- **tool_type vocabulary** (exact strings): `rag`, `gmail`, `calendar`. **grant role** (exact strings): `viewer`, `manager`. **kb status** (exact strings): `processing`, `indexed`, `failed`.

---

## File Structure

**Backend (all under `backend/app/modules/agent_builder/` unless noted):**

| File | Responsibility | Action |
|---|---|---|
| `models.py` | `Tool` reshaped to tenant-wide catalog; new `AgentTool` M2M | Modify |
| `kb_models.py` | `KbDocument` reshaped (owner, no agent_id); new `KbDocumentGrant`, `AgentKbDocument` | Modify |
| `tool_catalog_service.py` | list/get catalog tools; attach/detach agent tool refs; seed defaults | Create |
| `kb_service.py` | KB store: upload/list/get/delete + owner/grants ACL (tenant-wide) | Rewrite |
| `kb_grants_service.py` | doc user-ACL grants + access-check helpers | Create |
| `agent_kb_service.py` | per-agent doc grant (tick) + access-gated | Create |
| `kb_retrieval.py` | two-gate retrieval scoped to `agent_kb_documents` | Modify |
| `agent_executor.py` | resolve tools via `agent_tools`; two-gate KB | Modify |
| `tool_service.py` | `get_tool_by_name` via `agent_tools`; simplify `invoke_tool` (no embedded_python) | Modify |
| `routes.py` | remove nested tool/kb authoring routes; add agent tool-ref + kb-grant routes | Modify |
| `tool_routes.py` | tenant-wide `/tools` catalog routes | Create |
| `kb_routes.py` | tenant-wide `/kb/documents` + grants routes | Create |
| `alembic/versions/*` (2 files) | schema migrations | Create |
| `app/main.py` | register `tool_routes`, `kb_routes` routers | Modify |
| `app/core/adapters/mcp_client_stub.py` | deterministic stub for `gmail`/`calendar` tool calls | Modify |
| `scripts/demo_agent_specs.py` | default tool + KB doc specs (new shape) | Modify |
| `scripts/bootstrap_demo_agents_workflow.py` | seed catalog tools + docs + refs/grants | Modify |

**Frontend (all under `frontend/src/`):**

| File | Responsibility | Action |
|---|---|---|
| `components/Sidebar.tsx` | new 6-section nav + Workflows/Audit secondary group | Modify |
| `App.tsx` | wire `/chat`,`/apps`,`/tools`,`/database` routes + placeholders | Modify |
| `routes/tools.tsx` | Tools section page | Create |
| `routes/database.tsx` | Database section page (KB half + mini-app-DB placeholder) | Create |
| `lib/toolCatalogApi.ts` | tenant `/tools` + agent tool-ref client | Create |
| `lib/kbStoreApi.ts` | tenant `/kb/documents` + grants + agent kb-doc client | Create |
| `hooks/useToolCatalog.ts`, `hooks/useAgentToolRefs.ts` | tools query/mutation hooks | Create |
| `hooks/useKbStore.ts`, `hooks/useKbGrants.ts`, `hooks/useAgentKbDocs.ts` | KB query/mutation hooks | Create |
| `components/agents/tabs/ToolsTab.tsx` | convert to library reference picker | Rewrite |
| `components/agents/tabs/KnowledgeBaseTab.tsx` | convert to doc tick picker | Rewrite |

---

## PHASE 1 — Backend domain: schema, models, migrations

### Task 1: Reshape `Tool` to a tenant-wide catalog + `AgentTool` M2M

**Files:**
- Modify: `backend/app/modules/agent_builder/models.py`
- Create: `backend/alembic/versions/<rev>_reshape_tools_catalog.py`

**Interfaces:**
- Produces: `Tool` columns `{id, tenant_id, owner_id, tool_type, display_name, description, params_schema, output_schema, config, credential_ref, is_deleted, deleted_at, created_at, updated_at}`; `AgentTool` columns `{agent_id, tool_id, tenant_id}` (composite PK).

- [ ] **Step 1: Run impact analysis on `Tool`**

Run GitNexus: `impact({target: "Tool", direction: "upstream"})`. Note callers (`tool_service`, `tool_crud`, `agent_executor`, `routes`, seed). Proceed (they are all rewritten in this plan). Warn the user if risk is HIGH/CRITICAL.

- [ ] **Step 2: Replace the `Tool` class in `models.py`**

Replace the entire `class Tool(Base):` block (lines ~132-190) with the catalog shape and add `AgentTool`. Keep the `Agent` and `ApiIntegration` classes untouched.

```python
class Tool(Base):
    """A shared, tenant-wide Tool in the catalog (Sub-project A).

    Tools are no longer agent-owned; agents reference them via `agent_tools`.
    Only the built-in catalog types exist for now (`rag`/`gmail`/`calendar`) —
    seeded per tenant, not user-authored (spec D4). `params_schema` is the
    call interface the LLM reads; `description` is LLM- and human-facing (D5).
    Execution of `gmail`/`calendar` is stubbed (spec §5); `rag` is consumed
    via the two-gate KB path, not `invoke_tool`.
    """

    __tablename__ = "tools"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    tool_type: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    params_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    credential_ref: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentTool(Base):
    """M2M: an Agent references a catalog Tool (Sub-project A)."""

    __tablename__ = "agent_tools"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tools.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Write the migration**

Run `cd backend && uv run alembic heads`, use the head as `down_revision`. Create the file (replace `<rev>` with a fresh 12-hex id and `<HEAD>` with the reported head). Greenfield: DROP the old `tools` table and CREATE the new shape + `agent_tools`.

```python
"""reshape tools catalog + agent_tools

Revision ID: <rev>
Revises: <HEAD>
Create Date: 2026-07-18

Greenfield reset (Sub-project A): tools become a tenant-wide catalog; agents
reference them via agent_tools. Old agent-owned tool rows are demo-only and
are dropped + reseeded. Mirrors the RLS DDL of 9e84be8908a0.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "<rev>"
down_revision: str | Sequence[str] | None = "<HEAD>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str, *, delete: bool = True) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    verbs = "SELECT, INSERT, UPDATE, DELETE" if delete else "SELECT, INSERT, UPDATE"
    op.execute(f"GRANT {verbs} ON {table} TO {APP_ROLE};")


def upgrade() -> None:
    # Drop the old agent-owned tools table (demo data only, reseeded later).
    op.execute("DROP TABLE IF EXISTS tools CASCADE;")

    op.create_table(
        "tools",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tool_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("params_schema", postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("credential_ref", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("tool_type IN ('rag','gmail','calendar')", name="ck_tools_type"),
    )
    op.create_index("ix_tools_tenant_id", "tools", ["tenant_id"])
    _enable_rls("tools", delete=True)

    op.create_table(
        "agent_tools",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tool_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tools.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_tools_tenant_id", "agent_tools", ["tenant_id"])
    op.create_index("ix_agent_tools_tool_id", "agent_tools", ["tool_id"])
    _enable_rls("agent_tools", delete=True)


def downgrade() -> None:
    for t in ("agent_tools", "tools"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {t};")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(t)
```

Note: `DROP TABLE tools CASCADE` also drops the old `tools.integration_id` FK to `api_integrations`; the `api_integrations` table itself is untouched (out of scope for A).

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/agent_builder/models.py backend/alembic/versions
git commit -m "feat(agent-builder): reshape Tool to tenant-wide catalog + agent_tools M2M"
```

---

### Task 2: Reshape `KbDocument` (owner, no agent_id) + `KbDocumentGrant` + `AgentKbDocument`

**Files:**
- Modify: `backend/app/modules/agent_builder/kb_models.py`
- Create: `backend/alembic/versions/<rev>_reshape_kb_store_grants.py`

**Interfaces:**
- Produces: `KbDocument` columns `{id, tenant_id, owner_id, department_id(nullable), filename, content_type, size_bytes, status, failure_reason, external_document_id, chunk_count, created_at, updated_at}`; `KbDocumentGrant{document_id, user_id, role, tenant_id}` (PK document_id+user_id); `AgentKbDocument{agent_id, document_id, tenant_id}` (PK agent_id+document_id).

- [ ] **Step 1: Run impact analysis on `KbDocument`**

`impact({target: "KbDocument", direction: "upstream"})`. Callers: `kb_service`, `kb_retrieval`, `routes`. All rewritten here.

- [ ] **Step 2: Rewrite `kb_models.py`**

Replace the `KbDocument` class: drop `agent_id`, add `owner_id`, make `department_id` nullable. Add `KbDocumentGrant` and `AgentKbDocument`. Keep imports; add `Text` already imported.

```python
class KbDocument(Base):
    """A document in the tenant-wide Knowledge Base store (Sub-project A).

    No longer agent-owned. `owner_id` is the uploader (implicit manager).
    Access is governed by `kb_document_grants` (user ACL); agents that may
    RAG over a doc are listed in `agent_kb_documents`.
    """

    __tablename__ = "kb_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True
    )

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="processing", server_default="processing"
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_document_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class KbDocumentGrant(Base):
    """User-level access grant on a KB document (spec D2)."""

    __tablename__ = "kb_document_grants"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # viewer|manager
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentKbDocument(Base):
    """M2M: an Agent is granted a KB document for RAG (spec D3)."""

    __tablename__ = "agent_kb_documents"

    agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

- [ ] **Step 3: Write the migration**

`alembic heads` → `down_revision` = the Task-1 migration rev (chain after it). Greenfield: DROP + recreate `kb_documents`, create the two association tables.

```python
"""reshape kb store + grants + agent_kb_documents

Revision ID: <rev>
Revises: <TASK1_REV>
Create Date: 2026-07-18
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "<rev>"
down_revision: str | Sequence[str] | None = "<TASK1_REV>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "vaic_app"


def _enable_rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
    op.execute(
        f"""CREATE POLICY tenant_isolation_policy ON {table}
            USING (tenant_id = current_setting('app.tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);"""
    )
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE};")


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS kb_documents CASCADE;")
    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("external_document_id", sa.String(255), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_kb_documents_tenant_id", "kb_documents", ["tenant_id"])
    op.create_index("ix_kb_documents_owner_id", "kb_documents", ["owner_id"])
    _enable_rls("kb_documents")

    op.create_table(
        "kb_document_grants",
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.CheckConstraint("role IN ('viewer','manager')", name="ck_kb_grant_role"),
    )
    op.create_index("ix_kb_document_grants_tenant_id", "kb_document_grants", ["tenant_id"])
    op.create_index("ix_kb_document_grants_user_id", "kb_document_grants", ["user_id"])
    _enable_rls("kb_document_grants")

    op.create_table(
        "agent_kb_documents",
        sa.Column("agent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("agents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("kb_documents.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_agent_kb_documents_tenant_id", "agent_kb_documents", ["tenant_id"])
    op.create_index("ix_agent_kb_documents_document_id", "agent_kb_documents", ["document_id"])
    _enable_rls("agent_kb_documents")


def downgrade() -> None:
    for t in ("agent_kb_documents", "kb_document_grants", "kb_documents"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {t};")
        op.execute(f"ALTER TABLE {t} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(t)
```

- [ ] **Step 4: (optional) Apply migrations to verify DDL**

Only if you want to verify now: `cd backend && uv run alembic upgrade head`. Expect no errors. (Skip per no-auto-run preference; the seed task will apply them anyway.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent_builder/kb_models.py backend/alembic/versions
git commit -m "feat(agent-builder): reshape KB store with owner + user grants + agent doc M2M"
```

---

## PHASE 2 — Backend services + routes

### Task 3: Tool catalog service + tenant routes + agent tool-ref routes

**Files:**
- Create: `backend/app/modules/agent_builder/tool_catalog_service.py`
- Create: `backend/app/modules/agent_builder/tool_routes.py`
- Modify: `backend/app/modules/agent_builder/routes.py` (remove nested tool authoring routes; add tool-ref routes)

**Interfaces:**
- Consumes: `Principal`, `_authorize_mutation`, `get_agent` (from `service.py`); `Tool`, `AgentTool` (models).
- Produces:
  - `list_catalog_tools(session) -> list[Tool]`
  - `get_catalog_tool(session, tool_id) -> Tool`
  - `serialize_tool(tool) -> dict`
  - `list_agent_tool_refs(session, *, agent_id) -> list[Tool]`
  - `attach_agent_tool(session, *, agent_id, tool_id, principal) -> None`
  - `detach_agent_tool(session, *, agent_id, tool_id, principal) -> None`
  - `seed_default_tools(session, *, tenant_id, owner_id) -> dict[str, Tool]` (keyed by tool_type)
  - `DEFAULT_TOOL_SPECS: tuple[dict, ...]`

- [ ] **Step 1: Create `tool_catalog_service.py`**

```python
"""Tenant-wide Tool catalog service (Sub-project A).

Tools are shared catalog rows (`rag`/`gmail`/`calendar`), seeded per tenant.
Agents reference them via `agent_tools`. No user-authored tools yet (spec D4);
there is no create/update/delete of catalog rows through the API — only the
seed builds them. Attach/detach of an agent reference requires the same
builder-or-owner mutation guard as other agent mutations (`_authorize_mutation`).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import tenant_context
from app.modules.agent_builder.models import AgentTool, Tool
from app.modules.agent_builder.service import Principal, _authorize_mutation, get_agent

__all__ = [
    "DEFAULT_TOOL_SPECS",
    "list_catalog_tools",
    "get_catalog_tool",
    "serialize_tool",
    "list_agent_tool_refs",
    "attach_agent_tool",
    "detach_agent_tool",
    "seed_default_tools",
]

# The built-in catalog. `params_schema` is the LLM call interface (spec D5).
DEFAULT_TOOL_SPECS: tuple[dict[str, Any], ...] = (
    {
        "tool_type": "rag",
        "display_name": "Knowledge Base Search (RAG)",
        "description": (
            "Search the agent's granted Knowledge Base documents for passages "
            "relevant to a query. Only documents granted to this agent are searched."
        ),
        "params_schema": {
            "type": "object",
            "required": ["query"],
            "properties": {"query": {"type": "string"}},
        },
        "output_schema": {"type": "object"},
        "config": {},
    },
    {
        "tool_type": "gmail",
        "display_name": "Send Gmail",
        "description": (
            "Send an email on the user's behalf. Provide the recipient address, "
            "subject line, and message body."
        ),
        "params_schema": {
            "type": "object",
            "required": ["to", "subject", "body"],
            "properties": {
                "to": {"type": "string", "description": "Recipient email address"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"message_id": {"type": "string"}, "status": {"type": "string"}},
        },
        "config": {},
    },
    {
        "tool_type": "calendar",
        "display_name": "Create Calendar Event",
        "description": (
            "Create a calendar event. Provide a title, start and end time "
            "(ISO 8601), and optional attendees."
        ),
        "params_schema": {
            "type": "object",
            "required": ["title", "start", "end"],
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 datetime"},
                "end": {"type": "string", "description": "ISO 8601 datetime"},
                "attendees": {"type": "array", "items": {"type": "string"}},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {"event_id": {"type": "string"}, "status": {"type": "string"}},
        },
        "config": {},
    },
)


def list_catalog_tools(session: Session) -> list[Tool]:
    """All non-deleted catalog tools in the tenant (RLS-scoped)."""
    return list(
        session.execute(
            select(Tool).where(Tool.is_deleted.is_(False)).order_by(Tool.display_name)
        ).scalars().all()
    )


def get_catalog_tool(session: Session, tool_id: uuid.UUID) -> Tool:
    from app.core.errors import NotFoundError

    tool = session.execute(
        select(Tool).where(Tool.id == tool_id, Tool.is_deleted.is_(False))
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError("Tool not found")
    return tool


def serialize_tool(tool: Tool) -> dict:
    """Response shape — never exposes `credential_ref`."""
    return {
        "id": str(tool.id),
        "tool_type": tool.tool_type,
        "display_name": tool.display_name,
        "description": tool.description,
        "params_schema": tool.params_schema,
        "output_schema": tool.output_schema,
        "config": tool.config,
        "created_at": tool.created_at.isoformat(timespec="milliseconds"),
        "updated_at": tool.updated_at.isoformat(timespec="milliseconds"),
    }


def list_agent_tool_refs(session: Session, *, agent_id: uuid.UUID) -> list[Tool]:
    """Catalog tools this agent references (via `agent_tools`)."""
    return list(
        session.execute(
            select(Tool)
            .join(AgentTool, AgentTool.tool_id == Tool.id)
            .where(AgentTool.agent_id == agent_id, Tool.is_deleted.is_(False))
            .order_by(Tool.display_name)
        ).scalars().all()
    )


def attach_agent_tool(
    session: Session, *, agent_id: uuid.UUID, tool_id: uuid.UUID, principal: Principal
) -> None:
    """Add an agent→tool reference (idempotent). Guarded like an agent mutation."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)
    tool = get_catalog_tool(session, tool_id)  # 404 if not in tenant
    existing = session.get(AgentTool, {"agent_id": agent_id, "tool_id": tool.id})
    if existing is not None:
        return
    session.add(
        AgentTool(agent_id=agent_id, tool_id=tool.id, tenant_id=tenant_context.get())
    )
    session.commit()


def detach_agent_tool(
    session: Session, *, agent_id: uuid.UUID, tool_id: uuid.UUID, principal: Principal
) -> None:
    """Remove an agent→tool reference (idempotent)."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)
    row = session.get(AgentTool, {"agent_id": agent_id, "tool_id": tool_id})
    if row is not None:
        session.delete(row)
        session.commit()


def seed_default_tools(
    session: Session, *, tenant_id: uuid.UUID, owner_id: uuid.UUID
) -> dict[str, Tool]:
    """Idempotently seed the built-in catalog for a tenant; return by tool_type."""
    from app.core.ids import uuid7

    result: dict[str, Tool] = {}
    for spec in DEFAULT_TOOL_SPECS:
        existing = session.execute(
            select(Tool).where(
                Tool.tool_type == spec["tool_type"], Tool.is_deleted.is_(False)
            )
        ).scalars().first()
        if existing is not None:
            result[spec["tool_type"]] = existing
            continue
        tool = Tool(
            id=uuid7(),
            tenant_id=tenant_id,
            owner_id=owner_id,
            tool_type=spec["tool_type"],
            display_name=spec["display_name"],
            description=spec["description"],
            params_schema=spec["params_schema"],
            output_schema=spec["output_schema"],
            config=spec["config"],
        )
        session.add(tool)
        result[spec["tool_type"]] = tool
    session.commit()
    for tool in result.values():
        session.refresh(tool)
    return result
```

- [ ] **Step 2: Create `tool_routes.py` (tenant-wide catalog)**

```python
"""Tenant-wide Tool catalog routes (Sub-project A) — GET only.

Read-only catalog: agents reference these tools; there is no user-authored
tool creation yet (spec D4).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.tool_catalog_service import (
    get_catalog_tool,
    list_catalog_tools,
    serialize_tool,
)

router = APIRouter(prefix="/tools", tags=["tools"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


@router.get("")
def list_tools_route(
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    tools = list_catalog_tools(session)
    return JSONResponse(status_code=200, content=_ok([serialize_tool(t) for t in tools]))


@router.get("/{tool_id}")
def get_tool_route(
    tool_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    return JSONResponse(status_code=200, content=_ok(serialize_tool(get_catalog_tool(session, tool_id))))
```

- [ ] **Step 3: Rewire agent tool routes in `routes.py`**

In `backend/app/modules/agent_builder/routes.py`: **delete** the old Tool authoring routes (`create_tool_route`, `list_tools_route`, `update_tool_route`, `delete_tool_route`, `test_tool_route`), the `CreateToolRequest`/`UpdateToolRequest`/`TestToolRequest` schemas, and the now-unused imports from `tool_crud`/`tool_service`. Add reference routes below the agent CRUD block:

```python
# ---------------------------------------------------------------------------
# Agent -> Tool references (Sub-project A)
# ---------------------------------------------------------------------------

class AttachToolRequest(BaseModel):
    tool_id: uuid.UUID


@router.get("/{agent_id}/tools")
def list_agent_tools_route(
    agent_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /agents/{id}/tools — catalog tools this agent references."""
    tools = list_agent_tool_refs(session, agent_id=agent_id)
    return JSONResponse(status_code=200, content=_ok([serialize_catalog_tool(t) for t in tools]))


@router.post("/{agent_id}/tools")
def attach_agent_tool_route(
    agent_id: uuid.UUID,
    body: AttachToolRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """POST /agents/{id}/tools — add a tool reference."""
    attach_agent_tool(session, agent_id=agent_id, tool_id=body.tool_id, principal=_principal(request))
    return JSONResponse(status_code=201, content=_ok({"agent_id": str(agent_id), "tool_id": str(body.tool_id)}))


@router.delete("/{agent_id}/tools/{tool_id}")
def detach_agent_tool_route(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /agents/{id}/tools/{tool_id} — remove a tool reference."""
    detach_agent_tool(session, agent_id=agent_id, tool_id=tool_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"agent_id": str(agent_id), "tool_id": str(tool_id)}))
```

Add imports at the top of `routes.py`:

```python
from app.modules.agent_builder.tool_catalog_service import (
    attach_agent_tool,
    detach_agent_tool,
    list_agent_tool_refs,
)
from app.modules.agent_builder.tool_catalog_service import serialize_tool as serialize_catalog_tool
```

Delete `tool_crud.py` and `tool_test_panel`-related backend imports only if nothing else references them — check with `grep -rn "tool_crud" backend/app`. `tool_crud.py` may be safely deleted (its `create_tool`/`update_tool`/`serialize_tool`/`soft_delete_tool`/`list_tools` are no longer used once the seed switches to `seed_default_tools` in Task 8). If the seed still imports it at this point, defer deleting `tool_crud.py` until Task 8.

- [ ] **Step 4: Commit**

```bash
git add backend/app/modules/agent_builder/tool_catalog_service.py backend/app/modules/agent_builder/tool_routes.py backend/app/modules/agent_builder/routes.py
git commit -m "feat(agent-builder): tenant Tool catalog service + agent tool-ref routes"
```

---

### Task 4: KB store service rewrite (tenant-wide + owner/grants ACL) + `kb_grants_service` + tenant routes

**Files:**
- Create: `backend/app/modules/agent_builder/kb_grants_service.py`
- Rewrite: `backend/app/modules/agent_builder/kb_service.py`
- Create: `backend/app/modules/agent_builder/kb_routes.py`
- Modify: `backend/app/modules/agent_builder/routes.py` (remove nested KB routes)

**Interfaces:**
- Consumes: `Principal` (service.py); `KbDocument`, `KbDocumentGrant` (kb_models); `get_mcp_client`, `crud_audit_ids`; `McpClientPort`.
- Produces (kb_grants_service): `effective_role(session, doc, user_id) -> str|None` (`manager`/`viewer`/`None`); `require_access(session, doc, user_id, *, need_manage=False) -> None` (raises `AuthorizationError`); `list_grants(session, doc_id) -> list[KbDocumentGrant]`; `set_grant(session, *, doc_id, principal, user_id, role) -> KbDocumentGrant`; `revoke_grant(session, *, doc_id, principal, user_id) -> None`; `serialize_grant(g) -> dict`.
- Produces (kb_service): `upload_document(session, *, principal, filename, content_type, data, ...) -> KbDocument` (no agent_id); `list_documents(session, *, principal) -> list[KbDocument]` (owned+granted); `get_document(session, *, document_id, principal) -> KbDocument`; `delete_document(session, *, document_id, principal, ...) -> None`; `serialize_document(doc, *, effective_role=None) -> dict`.

- [ ] **Step 1: Create `kb_grants_service.py`**

```python
"""KB document user-ACL (owner + grants) — Sub-project A (spec D2).

Access resolution (service layer; RLS only isolates tenants):
- Owner  -> effective 'manager'.
- Grant  -> its role ('viewer'|'manager').
- Else   -> no access.
`viewer` may read + tick into an editable agent; `manager` may also
add/remove grants + delete the doc.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AuthorizationError, ValidationError
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_models import KbDocument, KbDocumentGrant
from app.modules.agent_builder.service import Principal

__all__ = [
    "effective_role", "require_access", "list_grants", "set_grant",
    "revoke_grant", "serialize_grant",
]

_VALID_ROLES = {"viewer", "manager"}


def effective_role(session: Session, doc: KbDocument, user_id: uuid.UUID) -> str | None:
    if doc.owner_id == user_id:
        return "manager"
    grant = session.get(KbDocumentGrant, {"document_id": doc.id, "user_id": user_id})
    return grant.role if grant is not None else None


def require_access(
    session: Session, doc: KbDocument, user_id: uuid.UUID, *, need_manage: bool = False
) -> None:
    role = effective_role(session, doc, user_id)
    if role is None or (need_manage and role != "manager"):
        raise AuthorizationError("Not authorized for this document", code="FORBIDDEN")


def list_grants(session: Session, doc_id: uuid.UUID) -> list[KbDocumentGrant]:
    return list(
        session.execute(
            select(KbDocumentGrant).where(KbDocumentGrant.document_id == doc_id)
        ).scalars().all()
    )


def set_grant(
    session: Session, *, doc_id: uuid.UUID, principal: Principal,
    user_id: uuid.UUID, role: str,
) -> KbDocumentGrant:
    if role not in _VALID_ROLES:
        raise ValidationError(f"Invalid role '{role}'", code="validation_error")
    from app.modules.agent_builder.kb_service import _get_document_row  # local import avoids cycle
    doc = _get_document_row(session, doc_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    grant = session.get(KbDocumentGrant, {"document_id": doc_id, "user_id": user_id})
    if grant is None:
        grant = KbDocumentGrant(
            document_id=doc_id, user_id=user_id, role=role, tenant_id=tenant_context.get()
        )
        session.add(grant)
    else:
        grant.role = role
    session.commit()
    session.refresh(grant)
    return grant


def revoke_grant(
    session: Session, *, doc_id: uuid.UUID, principal: Principal, user_id: uuid.UUID
) -> None:
    from app.modules.agent_builder.kb_service import _get_document_row
    doc = _get_document_row(session, doc_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    grant = session.get(KbDocumentGrant, {"document_id": doc_id, "user_id": user_id})
    if grant is not None:
        session.delete(grant)
        session.commit()


def serialize_grant(g: KbDocumentGrant) -> dict:
    return {"document_id": str(g.document_id), "user_id": str(g.user_id), "role": g.role}
```

- [ ] **Step 2: Rewrite `kb_service.py`**

Rewrite to the tenant-wide store shape. Ingestion still routes through `McpClientPort` (`rag.ingest`/`rag.delete`) but scope no longer derives from an Agent — use the caller's tenant + the doc's optional `department_id` (pass a fresh mcp client keyed on the doc's department or a nil-uuid when absent). Full file:

```python
"""Tenant-wide Knowledge Base store service (Sub-project A).

Documents are shared, owner-scoped (spec D1/D2), no longer agent-owned.
Ingestion/deletion route through `McpClientPort` (`rag.ingest`/`rag.delete`).
Access is enforced via `kb_grants_service` (owner + grants).
"""

from __future__ import annotations

import asyncio
import base64
import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.adapters.audit_postgres import PostgresAuditSink
from app.core.deps import crud_audit_ids, get_mcp_client
from app.core.errors import NotFoundError, ValidationError
from app.core.ids import utcnow_iso_ms, uuid7
from app.core.ports.audit import AuditEntry, AuditPort
from app.core.ports.mcp_client import McpClientPort
from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_models import AgentKbDocument, KbDocument, KbDocumentGrant
from app.modules.agent_builder.service import Principal

__all__ = [
    "KB_MAX_BYTES", "KB_ALLOWED_CONTENT_TYPES", "INGEST_TIMEOUT_S",
    "upload_document", "delete_document", "list_documents", "get_document",
    "serialize_document", "_get_document_row",
]

KB_MAX_BYTES = 20 * 1024 * 1024
INGEST_TIMEOUT_S = 30
KB_ALLOWED_CONTENT_TYPES = {
    "application/pdf", "text/plain", "text/markdown", "text/x-markdown",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_NIL_UUID = uuid.UUID("00000000-0000-0000-0000-000000000000")
McpFactory = Callable[..., McpClientPort]
logger = logging.getLogger(__name__)


def _validate_upload(content_type: str, data: bytes) -> None:
    if content_type not in KB_ALLOWED_CONTENT_TYPES:
        raise ValidationError(f"Unsupported content_type '{content_type}'", code="unsupported_content_type")
    if len(data) > KB_MAX_BYTES:
        raise ValidationError("File exceeds the 20MB limit", code="file_too_large")


def _get_document_row(session: Session, document_id: uuid.UUID) -> KbDocument:
    doc = session.execute(
        select(KbDocument).where(KbDocument.id == document_id)
    ).scalar_one_or_none()
    if doc is None:
        raise NotFoundError("KB document not found")
    return doc


def _run_ingest(session: Session, doc: KbDocument, data: bytes, mcp_factory: McpFactory) -> None:
    dept = doc.department_id or _NIL_UUID
    mcp = mcp_factory(agent_department_id=dept)
    try:
        result = asyncio.run(
            asyncio.wait_for(
                mcp.call_tool(
                    "rag.ingest",
                    {
                        "document_id": str(doc.id),
                        "filename": doc.filename,
                        "content_type": doc.content_type,
                        "data": base64.b64encode(data).decode("ascii"),
                    },
                    tenant_id=doc.tenant_id,
                    department_id=dept,
                ),
                timeout=INGEST_TIMEOUT_S,
            )
        )
        doc.status = "indexed"
        doc.external_document_id = result.output.get("document_id")
        doc.chunk_count = int(result.output.get("chunk_count", 0))
    except TimeoutError:
        doc.status = "failed"
        doc.failure_reason = "Timeout"
    except Exception as exc:  # noqa: BLE001
        logger.exception("KB ingest failed for document %s: %s", doc.id, exc)
        doc.status = "failed"
        doc.failure_reason = "Ingestion failed"
    finally:
        doc.updated_at = datetime.now(UTC)
        session.commit()
        session.refresh(doc)


def upload_document(
    session: Session, *, principal: Principal, filename: str, content_type: str,
    data: bytes, department_id: uuid.UUID | None = None,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> KbDocument:
    """Any authenticated tenant user may upload (spec OQ-3); uploader = owner."""
    _validate_upload(content_type, data)
    doc = KbDocument(
        id=uuid7(),
        tenant_id=tenant_context.get(),
        owner_id=principal.user_id,
        department_id=department_id,
        filename=filename,
        content_type=content_type,
        size_bytes=len(data),
        status="processing",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    _run_ingest(session, doc, data, mcp_factory)
    _emit_kb_audit(audit or PostgresAuditSink(), doc, "kb.document.uploaded")
    return doc


def list_documents(session: Session, *, principal: Principal) -> list[KbDocument]:
    """Docs the caller can access: owned OR granted (RLS already scopes tenant)."""
    granted_ids = select(KbDocumentGrant.document_id).where(
        KbDocumentGrant.user_id == principal.user_id
    )
    return list(
        session.execute(
            select(KbDocument)
            .where(or_(KbDocument.owner_id == principal.user_id, KbDocument.id.in_(granted_ids)))
            .order_by(KbDocument.created_at.desc())
        ).scalars().all()
    )


def get_document(session: Session, *, document_id: uuid.UUID, principal: Principal) -> KbDocument:
    from app.modules.agent_builder.kb_grants_service import require_access
    doc = _get_document_row(session, document_id)
    require_access(session, doc, principal.user_id)
    return doc


def delete_document(
    session: Session, *, document_id: uuid.UUID, principal: Principal,
    mcp_factory: McpFactory = get_mcp_client, audit: AuditPort | None = None,
) -> None:
    """Manager/owner only. Removes the external index + doc + refs/grants (CASCADE)."""
    from app.modules.agent_builder.kb_grants_service import require_access
    doc = _get_document_row(session, document_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    dept = doc.department_id or _NIL_UUID
    mcp = mcp_factory(agent_department_id=dept)
    asyncio.run(
        mcp.call_tool(
            "rag.delete",
            {"external_document_id": doc.external_document_id, "document_id": str(doc.id)},
            tenant_id=doc.tenant_id,
            department_id=dept,
        )
    )
    _emit_kb_audit(audit or PostgresAuditSink(), doc, "kb.document.deleted")
    session.delete(doc)  # grants + agent_kb_documents cascade at DB
    session.commit()


def serialize_document(doc: KbDocument, *, effective_role: str | None = None) -> dict:
    return {
        "id": str(doc.id),
        "owner_id": str(doc.owner_id),
        "department_id": str(doc.department_id) if doc.department_id else None,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "size_bytes": doc.size_bytes,
        "status": doc.status,
        "failure_reason": doc.failure_reason,
        "chunk_count": doc.chunk_count,
        "effective_role": effective_role,
        "created_at": doc.created_at.isoformat(timespec="milliseconds"),
        "updated_at": doc.updated_at.isoformat(timespec="milliseconds"),
    }


def _emit_kb_audit(audit: AuditPort, doc: KbDocument, entry_type: str) -> None:
    run_id, step_id = crud_audit_ids(str(doc.id))
    payload = {"document_id": str(doc.id), "filename": doc.filename, "status": doc.status}
    audit.log(AuditEntry(
        run_id=run_id, step_id=step_id, agent_id=str(doc.owner_id),
        ts=utcnow_iso_ms(), type=entry_type, input=payload, output=payload,
        latency_ms=0, model="",
    ))
```

- [ ] **Step 3: Create `kb_routes.py` (tenant-wide store + grants)**

```python
"""Tenant-wide Knowledge Base store routes (Sub-project A)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.modules.agent_builder.kb_grants_service import (
    list_grants, revoke_grant, serialize_grant, set_grant,
)
from app.modules.agent_builder.kb_service import (
    delete_document, get_document, list_documents, serialize_document, upload_document,
)
from app.modules.agent_builder.kb_grants_service import effective_role
from app.modules.agent_builder.kb_service import _get_document_row
from app.modules.agent_builder.service import Principal

router = APIRouter(prefix="/kb/documents", tags=["kb"])


def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> Principal:
    dept = getattr(request.state, "department_id", None)
    return Principal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        department_id=uuid.UUID(str(dept)) if dept else None,
        role=str(getattr(request.state, "role", "")),
    )


class SetGrantRequest(BaseModel):
    user_id: uuid.UUID
    role: str  # viewer|manager


@router.post("")
def upload_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    doc = upload_document(
        session, principal=_principal(request),
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        data=file.file.read(),
    )
    return JSONResponse(status_code=201, content=_ok(serialize_document(doc, effective_role="manager")))


@router.get("")
def list_route(
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    docs = list_documents(session, principal=principal)
    return JSONResponse(status_code=200, content=_ok([
        serialize_document(d, effective_role=("manager" if d.owner_id == principal.user_id else None))
        for d in docs
    ]))


@router.get("/{doc_id}")
def get_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    doc = get_document(session, document_id=doc_id, principal=principal)
    role = effective_role(session, doc, principal.user_id)
    return JSONResponse(status_code=200, content=_ok(serialize_document(doc, effective_role=role)))


@router.delete("/{doc_id}")
def delete_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    delete_document(session, document_id=doc_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"id": str(doc_id)}))


@router.get("/{doc_id}/grants")
def list_grants_route(
    doc_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    from app.modules.agent_builder.kb_grants_service import require_access
    principal = _principal(request)
    doc = _get_document_row(session, doc_id)
    require_access(session, doc, principal.user_id, need_manage=True)
    return JSONResponse(status_code=200, content=_ok([serialize_grant(g) for g in list_grants(session, doc_id)]))


@router.post("/{doc_id}/grants")
def set_grant_route(
    doc_id: uuid.UUID, body: SetGrantRequest, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    grant = set_grant(session, doc_id=doc_id, principal=_principal(request), user_id=body.user_id, role=body.role)
    return JSONResponse(status_code=201, content=_ok(serialize_grant(grant)))


@router.delete("/{doc_id}/grants/{user_id}")
def revoke_grant_route(
    doc_id: uuid.UUID, user_id: uuid.UUID, request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    revoke_grant(session, doc_id=doc_id, principal=_principal(request), user_id=user_id)
    return JSONResponse(status_code=200, content=_ok({"document_id": str(doc_id), "user_id": str(user_id)}))
```

- [ ] **Step 4: Remove nested KB routes from `routes.py`**

Delete `upload_kb_document_route`, `list_kb_documents_route`, `delete_kb_document_route` and the `kb_service` imports in `backend/app/modules/agent_builder/routes.py`. (Agent-side doc grants come in Task 5.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/modules/agent_builder/kb_grants_service.py backend/app/modules/agent_builder/kb_service.py backend/app/modules/agent_builder/kb_routes.py backend/app/modules/agent_builder/routes.py
git commit -m "feat(agent-builder): tenant KB store with owner/grants ACL + grant routes"
```

---

### Task 5: Agent KB-doc grant service + routes (the tick), access-gated

**Files:**
- Create: `backend/app/modules/agent_builder/agent_kb_service.py`
- Modify: `backend/app/modules/agent_builder/routes.py` (add `/agents/{id}/kb-documents` routes)

**Interfaces:**
- Consumes: `get_agent`, `_authorize_mutation`, `Principal` (service.py); `require_access`, `effective_role` (kb_grants_service); `_get_document_row` (kb_service); `AgentKbDocument`, `KbDocument` (kb_models).
- Produces: `list_agent_documents(session, *, agent_id) -> list[KbDocument]`; `attach_agent_document(session, *, agent_id, document_id, principal) -> None`; `detach_agent_document(session, *, agent_id, document_id, principal) -> None`; `list_agent_document_ids(session, agent_id) -> list[uuid.UUID]`.

- [ ] **Step 1: Create `agent_kb_service.py`**

```python
"""Per-agent KB document grants (the tick) — Sub-project A (spec D3).

Invariant: a row may only be created by a user who has viewer+ on the
document AND can edit the agent. `list_agent_document_ids` is the runtime
scope source for two-gate RAG (`kb_retrieval`).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import tenant_context
from app.modules.agent_builder.kb_grants_service import require_access
from app.modules.agent_builder.kb_models import AgentKbDocument, KbDocument
from app.modules.agent_builder.kb_service import _get_document_row
from app.modules.agent_builder.service import Principal, _authorize_mutation, get_agent

__all__ = [
    "list_agent_documents", "attach_agent_document",
    "detach_agent_document", "list_agent_document_ids",
]


def list_agent_documents(session: Session, *, agent_id: uuid.UUID) -> list[KbDocument]:
    return list(
        session.execute(
            select(KbDocument)
            .join(AgentKbDocument, AgentKbDocument.document_id == KbDocument.id)
            .where(AgentKbDocument.agent_id == agent_id)
            .order_by(KbDocument.filename)
        ).scalars().all()
    )


def list_agent_document_ids(session: Session, agent_id: uuid.UUID) -> list[uuid.UUID]:
    return list(
        session.execute(
            select(AgentKbDocument.document_id).where(AgentKbDocument.agent_id == agent_id)
        ).scalars().all()
    )


def attach_agent_document(
    session: Session, *, agent_id: uuid.UUID, document_id: uuid.UUID, principal: Principal
) -> None:
    """Tick a doc into an agent. Requires edit-on-agent AND viewer+ on the doc."""
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)          # can edit this agent
    doc = _get_document_row(session, document_id)
    require_access(session, doc, principal.user_id)  # viewer+ on the doc
    existing = session.get(AgentKbDocument, {"agent_id": agent_id, "document_id": document_id})
    if existing is not None:
        return
    session.add(AgentKbDocument(
        agent_id=agent_id, document_id=document_id, tenant_id=tenant_context.get()
    ))
    session.commit()


def detach_agent_document(
    session: Session, *, agent_id: uuid.UUID, document_id: uuid.UUID, principal: Principal
) -> None:
    agent = get_agent(session, agent_id)
    _authorize_mutation(agent, principal)
    row = session.get(AgentKbDocument, {"agent_id": agent_id, "document_id": document_id})
    if row is not None:
        session.delete(row)
        session.commit()
```

- [ ] **Step 2: Add agent kb-doc routes in `routes.py`**

Add below the agent tool-ref routes; add imports.

```python
from app.modules.agent_builder.agent_kb_service import (
    attach_agent_document, detach_agent_document, list_agent_documents,
)
from app.modules.agent_builder.kb_service import serialize_document as serialize_kb_document
from app.modules.agent_builder.kb_grants_service import effective_role as kb_effective_role


class AttachDocRequest(BaseModel):
    document_id: uuid.UUID


@router.get("/{agent_id}/kb-documents")
def list_agent_kb_docs_route(
    agent_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    principal = _principal(request)
    docs = list_agent_documents(session, agent_id=agent_id)
    return JSONResponse(status_code=200, content=_ok([
        serialize_kb_document(d, effective_role=kb_effective_role(session, d, principal.user_id))
        for d in docs
    ]))


@router.post("/{agent_id}/kb-documents")
def attach_agent_kb_doc_route(
    agent_id: uuid.UUID,
    body: AttachDocRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    attach_agent_document(session, agent_id=agent_id, document_id=body.document_id, principal=_principal(request))
    return JSONResponse(status_code=201, content=_ok({"agent_id": str(agent_id), "document_id": str(body.document_id)}))


@router.delete("/{agent_id}/kb-documents/{document_id}")
def detach_agent_kb_doc_route(
    agent_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    detach_agent_document(session, agent_id=agent_id, document_id=document_id, principal=_principal(request))
    return JSONResponse(status_code=200, content=_ok({"agent_id": str(agent_id), "document_id": str(document_id)}))
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/modules/agent_builder/agent_kb_service.py backend/app/modules/agent_builder/routes.py
git commit -m "feat(agent-builder): per-agent KB doc grant (tick) service + routes"
```

---

### Task 6: Runtime two-gate — retrieval, executor, tool resolution, stub

**Files:**
- Modify: `backend/app/modules/agent_builder/kb_retrieval.py`
- Modify: `backend/app/modules/agent_builder/agent_executor.py`
- Modify: `backend/app/modules/agent_builder/tool_service.py`
- Modify: `backend/app/core/adapters/mcp_client_stub.py`

**Interfaces:**
- Consumes: `list_agent_document_ids` (agent_kb_service); `list_agent_tool_refs` (tool_catalog_service).
- Produces: `kb_search(session, agent_id, query, *, top_k=5, ...) -> list[RetrievalPassage]` (two-gate); `get_tool_by_name(session, *, agent_id, display_name) -> Tool` (via `agent_tools`).

- [ ] **Step 1: Impact analysis**

`impact({target: "kb_search", direction: "upstream"})` and `impact({target: "AgentExecutor", direction: "upstream"})`. Note the Orchestrator/worker + `test_demo_smoke` consume these. Warn on HIGH/CRITICAL.

- [ ] **Step 2: Rewrite `kb_search` for two gates in `kb_retrieval.py`**

Replace the `kb_search` body so it (1) only runs if the agent references the `rag` tool, (2) scopes to the agent's granted doc ids, (3) passes `document_ids` to `rag.search`. Change the query-scope derivation: keep tenant/department from the agent record (for MCP scope), but add the doc-id filter. Replace lines ~83-118 (`kb_search`) with:

```python
async def kb_search(
    session: Session,
    agent_id: uuid.UUID,
    query: str,
    *,
    top_k: int = 5,
    mcp_factory: McpFactory = get_mcp_client,
    audit: AuditPort | None = None,
    agent_loader: AgentLoader = get_agent_row,
) -> list[RetrievalPassage]:
    """Two-gate KB retrieval (spec D3).

    Gate 1: the agent must reference the `rag` tool. Gate 2: it must have
    granted documents. `rag.search` is scoped to exactly those documents;
    scope is derived from `agent_kb_documents`, never caller-supplied.
    """
    from app.modules.agent_builder.agent_kb_service import list_agent_document_ids
    from app.modules.agent_builder.tool_catalog_service import list_agent_tool_refs

    agent = agent_loader(session, agent_id)

    has_rag = any(t.tool_type == "rag" for t in list_agent_tool_refs(session, agent_id=agent_id))
    if not has_rag:
        return []
    doc_ids = [str(d) for d in list_agent_document_ids(session, agent_id)]
    if not doc_ids:
        return []

    mcp = mcp_factory(agent_department_id=agent.department_id)
    result = await mcp.call_tool(
        "rag.search",
        {
            "agent_id": str(agent.id),
            "query": query,
            "document_ids": doc_ids,
            "tenant_id": str(agent.tenant_id),
            "department_id": str(agent.department_id),
        },
        tenant_id=agent.tenant_id,
        department_id=agent.department_id,
    )
    passages = _map_passages(result.output.get("passages", []))
    _emit_retrieval_audit(audit or PostgresAuditSink(), agent, query, passages)
    return passages
```

- [ ] **Step 3: Update tool resolution in `tool_service.py`**

`get_tool_by_name` and `AgentToolPort.invoke` must resolve via `agent_tools` (not `Tool.agent_id`, which no longer exists) and match on `tool_type` OR `display_name`. Replace `get_tool_by_name` (lines ~53-64):

```python
def get_tool_by_name(session: Session, *, agent_id: uuid.UUID, display_name: str) -> Tool:
    """Resolve a catalog Tool the agent references, by display_name or tool_type."""
    from app.modules.agent_builder.models import AgentTool

    tool = session.execute(
        select(Tool)
        .join(AgentTool, AgentTool.tool_id == Tool.id)
        .where(
            AgentTool.agent_id == agent_id,
            Tool.is_deleted.is_(False),
            (Tool.display_name == display_name) | (Tool.tool_type == display_name),
        )
    ).scalar_one_or_none()
    if tool is None:
        raise NotFoundError(f"Tool '{display_name}' not found for this Agent")
    return tool
```

Delete `get_tool(session, *, agent_id, tool_id)` (used only by the removed test-tool route). In `AgentToolPort.invoke`, replace the inline `select(Tool).where(Tool.agent_id == ...)` block with a call to `get_tool_by_name(self._session, agent_id=self._agent_id, display_name=name)`.

Simplify `_execute`: catalog tools have no `embedded_python`, so remove the sandbox branch — always route to MCP by `tool.tool_type`:

```python
def _execute(
    tool: Tool,
    arguments: dict[str, Any],
    *,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    sandbox: SandboxPort | None,
    mcp_factory: McpFactory,
) -> tuple[dict[str, Any] | None, Any, int]:
    """Route every catalog tool to MCP by its tool_type (gmail/calendar stubbed)."""
    _ = sandbox  # embedded-Python tools are out of scope in Sub-project A
    start = time.monotonic()
    mcp = mcp_factory(agent_department_id=department_id)
    mcp_result = _call_mcp(mcp, tool.tool_type, arguments, tenant_id, department_id)
    latency_ms = int((time.monotonic() - start) * 1000)
    return mcp_result.output, None, latency_ms
```

Update `invoke_tool` to validate against `tool.params_schema` instead of `tool.input_schema` (the column was renamed): change `validate_instance(tool.input_schema, arguments)` → `validate_instance(tool.params_schema, arguments)`. Leave the `output_schema` validation as-is. Remove the `SubprocessSandbox` import if now unused.

- [ ] **Step 4: Extend the MCP stub for gmail/calendar in `mcp_client_stub.py`**

Read the file first. Add deterministic stub branches so `call_tool("gmail", ...)` and `call_tool("calendar", ...)` return a success `ToolResult` (mirror how `rag.*` is stubbed). Target output: gmail → `{"output": {"message_id": "stub-<uuid-less deterministic>", "status": "sent"}}`; calendar → `{"output": {"event_id": "stub-evt", "status": "created"}}`. Keep existing `rag.search`/`rag.ingest`/`rag.delete` behavior. Match the file's existing `ToolResult` construction exactly (do not invent a shape — copy the file's pattern). If `rag.search` currently ignores `document_ids`, that's fine (stub returns `[]`); no change needed for the two-gate wiring.

- [ ] **Step 5: `agent_executor.py` — no structural change needed**

`AgentExecutor` already calls `self._kb.retrieve(...)` (now two-gate underneath) and `get_tool_by_name`/`invoke_tool` (now agent_tools-based). Verify it still imports cleanly. No code change unless imports break; if `get_tool` was imported, remove it.

- [ ] **Step 6: Commit**

```bash
git add backend/app/modules/agent_builder/kb_retrieval.py backend/app/modules/agent_builder/tool_service.py backend/app/modules/agent_builder/agent_executor.py backend/app/core/adapters/mcp_client_stub.py
git commit -m "feat(agent-builder): two-gate KB retrieval + agent_tools resolution + stub connectors"
```

---

### Task 7: Wire the new routers into `main.py`

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Register the tenant tool + kb routers**

Add imports near the other module route imports:

```python
from app.modules.agent_builder.tool_routes import router as tools_router
from app.modules.agent_builder.kb_routes import router as kb_router
```

And after `app.include_router(agents_router)`:

```python
# Sub-project A — tenant-wide Tool catalog + KB store.
app.include_router(tools_router)
app.include_router(kb_router)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat(app): register tenant Tool catalog + KB store routers"
```

---

## PHASE 3 — Backend seed

### Task 8: Reseed demo in the new shape

**Files:**
- Modify: `backend/scripts/demo_agent_specs.py`
- Modify: `backend/scripts/bootstrap_demo_agents_workflow.py`
- Delete (if now unused): `backend/app/modules/agent_builder/tool_crud.py`

**Interfaces:**
- Consumes: `seed_default_tools` (tool_catalog_service); `attach_agent_tool`; `upload_document` is NOT used in seed (no file bytes) — seed KB docs directly via ORM + mark `indexed`.

- [ ] **Step 1: Simplify `demo_agent_specs.py`**

The embedded-Python tool sources are obsolete (catalog tools are stubbed). Replace `AGENT_SPECS` tool wiring: each agent now declares which catalog `tool_type`s it references and which demo KB doc filenames it is granted. Replace the `ToolSpec`/`AgentSpec` TypedDicts and the `_*_SRC`/`AGENT_SPECS` block with:

```python
class AgentSpec(TypedDict):
    name: str
    department: str
    system_prompt: str
    tool_types: list[str]        # catalog tool_types this agent references
    kb_doc_filenames: list[str]  # demo KB docs granted to this agent


# Demo KB documents seeded into the tenant-wide store (filename -> content_type).
DEMO_KB_DOCS: tuple[dict[str, str], ...] = (
    {"filename": "SHB-Lending-Policy.md", "content_type": "text/markdown"},
    {"filename": "KYC-AML-Circular.md", "content_type": "text/markdown"},
    {"filename": "Ops-Document-Checklist.md", "content_type": "text/markdown"},
)

AGENT_SPECS: tuple[AgentSpec, ...] = (
    {
        "name": "Credit Analyst",
        "department": "Credit",
        "system_prompt": (
            "You are the Credit Analyst for SHB Demo Bank. Retrieve relevant "
            "lending-policy clauses from your Knowledge Base and return ONLY a "
            "JSON object with a numeric 'confidence' in [0,1] and a 'rationale'."
        ),
        "tool_types": ["rag"],
        "kb_doc_filenames": ["SHB-Lending-Policy.md"],
    },
    {
        "name": "Compliance Analyst",
        "department": "Legal/Compliance",
        "system_prompt": (
            "You are the Compliance Analyst for SHB Demo Bank. Retrieve the "
            "KYC/AML circular from your Knowledge Base and return ONLY a JSON "
            "object with a numeric 'confidence' in [0,1] and a 'rationale'."
        ),
        "tool_types": ["rag"],
        "kb_doc_filenames": ["KYC-AML-Circular.md"],
    },
    {
        "name": "Operations Analyst",
        "department": "Operations",
        "system_prompt": (
            "You are the Operations Analyst for SHB Demo Bank. Retrieve the "
            "document checklist from your Knowledge Base and return ONLY a JSON "
            "object with a numeric 'confidence' in [0,1] and a 'rationale'."
        ),
        "tool_types": ["rag"],
        "kb_doc_filenames": ["Ops-Document-Checklist.md"],
    },
)
```

Keep `get_agent_model_ref`, `DEMO_WORKFLOW_NAME`, `DEMO_WORKFLOW_DESCRIPTION`. Update `__all__` to drop `ToolSpec` and add `DEMO_KB_DOCS`.

- [ ] **Step 2: Rewrite the seed wiring in `bootstrap_demo_agents_workflow.py`**

Replace `_find_tool`/`_upsert_tool` with catalog seeding + reference + doc grant. Full replacement of the tool/doc helpers and the loop body:

```python
from app.core.ids import uuid7  # noqa: E402
from app.modules.agent_builder.kb_models import AgentKbDocument, KbDocument  # noqa: E402
from app.modules.agent_builder.models import Agent, AgentTool  # noqa: E402
from app.modules.agent_builder.tool_catalog_service import seed_default_tools  # noqa: E402
from scripts.demo_agent_specs import DEMO_KB_DOCS  # noqa: E402


def _seed_kb_docs(session, tenant_id, owner) -> dict[str, KbDocument]:
    """Seed demo KB docs directly (no file bytes); mark indexed. Idempotent."""
    tenant_context.set(tenant_id)
    by_name: dict[str, KbDocument] = {}
    for spec in DEMO_KB_DOCS:
        existing = session.execute(
            select(KbDocument).where(
                KbDocument.tenant_id == tenant_id, KbDocument.filename == spec["filename"]
            )
        ).scalars().first()
        if existing is not None:
            by_name[spec["filename"]] = existing
            continue
        doc = KbDocument(
            id=uuid7(), tenant_id=tenant_id, owner_id=owner.id, department_id=None,
            filename=spec["filename"], content_type=spec["content_type"],
            size_bytes=0, status="indexed",
            external_document_id=f"demo-{spec['filename']}", chunk_count=0,
        )
        session.add(doc)
        by_name[spec["filename"]] = doc
    session.commit()
    for doc in by_name.values():
        session.refresh(doc)
    return by_name


def _ref_tool(session, agent, tool, tenant_id) -> None:
    if session.get(AgentTool, {"agent_id": agent.id, "tool_id": tool.id}) is None:
        session.add(AgentTool(agent_id=agent.id, tool_id=tool.id, tenant_id=tenant_id))
        session.commit()


def _grant_doc(session, agent, doc, tenant_id) -> None:
    if session.get(AgentKbDocument, {"agent_id": agent.id, "document_id": doc.id}) is None:
        session.add(AgentKbDocument(agent_id=agent.id, document_id=doc.id, tenant_id=tenant_id))
        session.commit()
```

Then in `seed_agents_tools_workflow`, after computing `dept_by_name`, seed catalog + docs once, and in the per-agent loop reference tools + grant docs:

```python
    tools_by_type = seed_default_tools(session, tenant_id=tenant_id, owner_id=builder_user.id)
    docs_by_name = _seed_kb_docs(session, tenant_id, builder_user)

    for spec in AGENT_SPECS:
        dept = dept_by_name.get(spec["department"])
        if dept is None:
            raise RuntimeError(f"Department {spec['department']!r} not seeded")
        agent, agent_created = _upsert_agent(session, tenant_id, dept, builder_user, spec)
        agents_created += int(agent_created)
        for ttype in spec["tool_types"]:
            _ref_tool(session, agent, tools_by_type[ttype], tenant_id)
        for fname in spec["kb_doc_filenames"]:
            _grant_doc(session, agent, docs_by_name[fname], tenant_id)
        agents.append(agent)
        print(f"[bootstrap] agent={agent.name!r} tools={spec['tool_types']} docs={spec['kb_doc_filenames']}")
```

Remove the old `tools_created` counter usage / `_find_tool` / `_upsert_tool` / the `Tool` import and the old per-agent print. Update the returned `created` dict to `{"agents": agents_created, "tools": len(tools_by_type), "workflow": int(workflow_created)}`. Remove the "KB seeding skipped" NOTE print.

- [ ] **Step 3: Delete `tool_crud.py` if unused**

`grep -rn "tool_crud" backend/`. If only this plan's already-edited files referenced it, delete `backend/app/modules/agent_builder/tool_crud.py`.

- [ ] **Step 4: (optional) Run the seed end-to-end**

If you want to verify: `cd backend && uv run alembic upgrade head && uv run python -m scripts.bootstrap_demo_tenant` (or the documented bootstrap entrypoint). Expect agents seeded with `tools=['rag']` and one doc each. Skip per no-auto-run preference.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/demo_agent_specs.py backend/scripts/bootstrap_demo_agents_workflow.py
git rm backend/app/modules/agent_builder/tool_crud.py  # only if Step 3 confirmed unused
git commit -m "feat(seed): reseed demo with catalog tools + KB store + agent refs/grants"
```

---

## PHASE 4 — Frontend

> All new components follow the established in-house pattern: **inline `style` objects driven by CSS custom properties** (`var(--color-*)`, `var(--space-*)`, `var(--text-*)`), `components/ui/` primitives (`Button`, `Card`, `Table`, `EmptyState`, `Skeleton`, `Toast`, `FormField`, `ConfirmDialog`), TanStack Query hooks, and API clients using the `api.ts` fetch base. Before writing each component, READ one existing sibling for the exact import surface: `frontend/src/routes/agents.tsx`, `frontend/src/lib/agentsApi.ts`, `frontend/src/hooks/useAgents.ts`, and `frontend/src/components/ui/index.ts`.

### Task 9: New 6-section sidebar + route wiring + placeholders

**Files:**
- Modify: `frontend/src/components/Sidebar.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Produces: routes `/chat`, `/apps`, `/tools`, `/database` (Chat/Apps placeholders; Tools/Database real in Tasks 10-11); Workflows/Audit retained.

- [ ] **Step 1: Rewrite `NAV_ITEMS` + add a secondary group in `Sidebar.tsx`**

Replace the `NAV_ITEMS` array and the imports of icons. Primary = the 6 sections; secondary = Workflows, Audit (kept, spec OQ-1 resolved). Replace lines 8-35:

```tsx
import { NavLink } from "react-router-dom";
import {
  MessageSquare, Bot, AppWindow, Wrench, Database,
  Settings, Workflow, Activity, HelpCircle,
} from "lucide-react";
import type { ComponentType } from "react";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/chat", label: "Chat", icon: MessageSquare },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/apps", label: "Apps", icon: AppWindow },
  { to: "/tools", label: "Tools", icon: Wrench },
  { to: "/database", label: "Database", icon: Database },
  { to: "/settings", label: "Settings", icon: Settings },
];

const SECONDARY_ITEMS: NavItem[] = [
  { to: "/workflows", label: "Workflows", icon: Workflow },
  { to: "/audit", label: "Audit", icon: Activity },
];
```

In the `<nav>`, render `NAV_ITEMS`, then a divider (`<div style={{height:1, background:"var(--color-border)", margin:"var(--space-2) var(--space-4)"}} />`), then `SECONDARY_ITEMS` using the same `NavLink` render logic. Extract the per-item render into a small local `renderItem(item)` to avoid duplication. Keep the existing style objects, footer, and Help link unchanged. Update the file's top doc-comment nav list.

- [ ] **Step 2: Wire routes in `App.tsx`**

Add imports for the new pages (created in Tasks 10-11):

```tsx
import ToolsPage from "./routes/tools";
import DatabasePage from "./routes/database";
```

Inside the protected `<Route element={<AppShell/>}>` block, replace the Mini-Apps/Actions/Settings placeholder routes with the new IA (keep Agents/Workflows/Audit as-is):

```tsx
<Route path="/chat" element={<ComingSoon title="Chat" />} />
<Route path="/apps" element={<ComingSoon title="Apps" />} />
<Route path="/tools" element={<ToolsPage />} />
<Route path="/database" element={<DatabasePage />} />
<Route path="/settings" element={<ComingSoon title="Settings" />} />
```

Keep `/mini-apps` route mapped to `MiniAppsPage` if you want the existing page reachable, or remove it (Apps section supersedes it in sub-project F). For A: leave the `/mini-apps` route in place but drop it from the sidebar (already done in Step 1). Keep `/dashboard`, `/agents`, `/agents/:id`, `/workflows`, `/workflows/:id`, `/audit`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/Sidebar.tsx frontend/src/App.tsx
git commit -m "feat(frontend): new 6-section sidebar IA + Tools/Database routes"
```

---

### Task 10: Tools section page + API client + hook

**Files:**
- Create: `frontend/src/lib/toolCatalogApi.ts`
- Create: `frontend/src/hooks/useToolCatalog.ts`
- Create: `frontend/src/routes/tools.tsx`

**Interfaces:**
- Consumes: `api.ts` fetch base (READ `frontend/src/lib/api.ts` for the exact exported helper name/signature — e.g. `apiGet<T>(path)`).
- Produces: `CatalogTool` type `{id, tool_type, display_name, description, params_schema, output_schema, config, created_at, updated_at}`; `useToolCatalog()` returning `{data, isLoading, error}`.

- [ ] **Step 1: Create `toolCatalogApi.ts`**

Mirror `agentsApi.ts`. Provide:

```ts
import { apiGet } from "./api"; // adjust to the actual export in lib/api.ts

export interface CatalogTool {
  id: string;
  tool_type: "rag" | "gmail" | "calendar";
  display_name: string;
  description: string;
  params_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export function listCatalogTools(): Promise<CatalogTool[]> {
  return apiGet<CatalogTool[]>("/tools");
}
```

If `api.ts` unwraps the `{data}` envelope already, return `data`; otherwise unwrap `.data` here (match `agentsApi.ts`).

- [ ] **Step 2: Create `useToolCatalog.ts`**

Mirror `useAgents.ts`:

```ts
import { useQuery } from "@tanstack/react-query";
import { listCatalogTools } from "../lib/toolCatalogApi";

export function useToolCatalog() {
  return useQuery({ queryKey: ["tools", "catalog"], queryFn: listCatalogTools });
}
```

- [ ] **Step 3: Create `routes/tools.tsx`**

A read-mostly catalog page: header "Tools", subtitle explaining these are the built-in tools agents can reference, then a card grid — one card per tool showing `display_name`, a `tool_type` pill, `description`, and an expandable "Parameters" section rendering `params_schema.properties` as a small table (name / type / description). Use `useToolCatalog()`; render `Skeleton` while loading, `EmptyState` if empty, `ErrorState` on error. Follow the layout idiom in `routes/agents.tsx`. Full component:

```tsx
import { useToolCatalog, } from "../hooks/useToolCatalog";
import type { CatalogTool } from "../lib/toolCatalogApi";
import { Card, EmptyState, ErrorState, Skeleton } from "../components/ui";

const TYPE_LABEL: Record<CatalogTool["tool_type"], string> = {
  rag: "Knowledge Base", gmail: "Email", calendar: "Calendar",
};

function ParamsTable({ schema }: { schema: Record<string, unknown> }) {
  const props = (schema?.properties ?? {}) as Record<string, { type?: string; description?: string }>;
  const required = new Set((schema?.required ?? []) as string[]);
  const rows = Object.entries(props);
  if (rows.length === 0) return <p className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>No parameters</p>;
  return (
    <table style={{ width: "100%", fontSize: "var(--text-caption)", borderCollapse: "collapse" }}>
      <thead>
        <tr style={{ textAlign: "left", color: "var(--color-text-tertiary)" }}>
          <th style={{ padding: "var(--space-1)" }}>Param</th>
          <th style={{ padding: "var(--space-1)" }}>Type</th>
          <th style={{ padding: "var(--space-1)" }}>Description</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([name, def]) => (
          <tr key={name} style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={{ padding: "var(--space-1)", fontWeight: 600 }}>
              {name}{required.has(name) ? " *" : ""}
            </td>
            <td style={{ padding: "var(--space-1)" }}>{def.type ?? "any"}</td>
            <td style={{ padding: "var(--space-1)", color: "var(--color-text-secondary)" }}>{def.description ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function ToolsPage() {
  const { data, isLoading, error } = useToolCatalog();
  return (
    <div style={{ padding: "var(--space-6)", maxWidth: 960, margin: "0 auto" }}>
      <h1 className="text-h1" style={{ marginBottom: "var(--space-1)" }}>Tools</h1>
      <p className="text-body" style={{ color: "var(--color-text-tertiary)", marginBottom: "var(--space-4)" }}>
        Built-in tools agents can reference. Configure which tools an agent uses from its detail page.
      </p>
      {isLoading && <Skeleton />}
      {error && <ErrorState title="Failed to load tools" />}
      {data && data.length === 0 && <EmptyState title="No tools available" />}
      <div style={{ display: "grid", gap: "var(--space-3)" }}>
        {data?.map((tool) => (
          <Card key={tool.id}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <h3 className="text-h3">{tool.display_name}</h3>
              <span className="text-caption" style={{
                padding: "2px 8px", borderRadius: "var(--radius-pill)",
                background: "var(--color-primary-soft)", color: "var(--color-primary)",
              }}>{TYPE_LABEL[tool.tool_type]}</span>
            </div>
            <p className="text-body" style={{ color: "var(--color-text-secondary)", margin: "var(--space-2) 0" }}>
              {tool.description}
            </p>
            <details>
              <summary className="text-caption" style={{ cursor: "pointer", color: "var(--color-text-tertiary)" }}>Parameters</summary>
              <div style={{ marginTop: "var(--space-2)" }}><ParamsTable schema={tool.params_schema} /></div>
            </details>
          </Card>
        ))}
      </div>
    </div>
  );
}
```

Adjust the imported `ui` primitive names to whatever `components/ui/index.ts` actually exports (READ it first; if `ErrorState`/`EmptyState` differ, use the real names).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/toolCatalogApi.ts frontend/src/hooks/useToolCatalog.ts frontend/src/routes/tools.tsx
git commit -m "feat(frontend): Tools section — built-in catalog list"
```

---

### Task 11: Database section (KB) page + API client + hooks (upload/list/grants)

**Files:**
- Create: `frontend/src/lib/kbStoreApi.ts`
- Create: `frontend/src/hooks/useKbStore.ts`
- Create: `frontend/src/hooks/useKbGrants.ts`
- Create: `frontend/src/routes/database.tsx`

**Interfaces:**
- Produces: `KbDoc` type `{id, owner_id, department_id, filename, content_type, size_bytes, status, failure_reason, chunk_count, effective_role, created_at, updated_at}`; `KbGrant` `{document_id, user_id, role}`; hooks `useKbDocuments()`, `useUploadKbDocument()`, `useDeleteKbDocument()`, `useKbGrants(docId)`, `useSetKbGrant()`, `useRevokeKbGrant()`.

- [ ] **Step 1: Create `kbStoreApi.ts`**

Mirror `kbApi.ts` (READ it for the multipart-upload idiom against `api.ts`). Provide `listKbDocuments()`, `uploadKbDocument(file: File)`, `deleteKbDocument(id)`, `listKbGrants(docId)`, `setKbGrant(docId, userId, role)`, `revokeKbGrant(docId, userId)`. Types `KbDoc`, `KbGrant` as above. Endpoints: `GET/POST /kb/documents`, `DELETE /kb/documents/{id}`, `GET/POST /kb/documents/{id}/grants`, `DELETE /kb/documents/{id}/grants/{userId}`. Upload uses `FormData` with field name `file` (matches `UploadFile = File(...)`).

- [ ] **Step 2: Create the hooks**

Mirror `useKbMutations.ts`/`useKbDocuments.ts`. `useKbStore.ts` exports `useKbDocuments()` (query key `["kb","docs"]`), `useUploadKbDocument()` + `useDeleteKbDocument()` (invalidate `["kb","docs"]` on success, toast on error). `useKbGrants.ts` exports `useKbGrants(docId)` (query key `["kb","grants",docId]`, `enabled: !!docId`), `useSetKbGrant()`, `useRevokeKbGrant()` (invalidate the grants key).

- [ ] **Step 3: Create `routes/database.tsx`**

Two-level layout. Top: a tab strip "Knowledge Base" | "Mini-App Databases" (the latter renders a `ComingSoon`-style placeholder — spec defers it to sub-project D). Knowledge Base tab: an "Upload" button (hidden file input → `useUploadKbDocument`), a table of docs (`filename`, `status` pill, `size`, `owner`, `created_at`, actions), and a "Manage access" affordance on rows where `effective_role === "manager"` that opens a grants panel (list grants from `useKbGrants(docId)`, an add-grant form with a `user_id` input + role select, and a revoke button per grant). Delete action on manager rows (guard with `ConfirmDialog`). Use `Skeleton`/`EmptyState`/`ErrorState`. Follow the table idiom in `routes/agents.tsx` / `components/ui` `Table`. Keep the file focused; if it exceeds ~200 lines, split the grants panel into `frontend/src/components/database/KbGrantsPanel.tsx` (per the repo modularization rule).

Key upload handler shape:

```tsx
const upload = useUploadKbDocument();
const inputRef = useRef<HTMLInputElement>(null);
// ...
<input ref={inputRef} type="file" hidden
  accept=".pdf,.txt,.md,.docx"
  onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
<Button onClick={() => inputRef.current?.click()} disabled={upload.isPending}>Upload</Button>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/kbStoreApi.ts frontend/src/hooks/useKbStore.ts frontend/src/hooks/useKbGrants.ts frontend/src/routes/database.tsx frontend/src/components/database/
git commit -m "feat(frontend): Database section — KB store with upload/list/grants"
```

---

### Task 12: Agent detail — convert Tools tab to a library reference picker

**Files:**
- Rewrite: `frontend/src/components/agents/tabs/ToolsTab.tsx`
- Create: `frontend/src/hooks/useAgentToolRefs.ts`
- Modify: `frontend/src/lib/toolCatalogApi.ts` (add agent-ref calls)

**Interfaces:**
- Consumes: `useToolCatalog()`, agent id from `AgentBuilderContext`/route.
- Produces: `listAgentToolRefs(agentId)`, `attachAgentTool(agentId, toolId)`, `detachAgentTool(agentId, toolId)`; `useAgentToolRefs(agentId)` + mutations.

- [ ] **Step 1: Add agent-ref calls to `toolCatalogApi.ts`**

```ts
export function listAgentToolRefs(agentId: string): Promise<CatalogTool[]> {
  return apiGet<CatalogTool[]>(`/agents/${agentId}/tools`);
}
export function attachAgentTool(agentId: string, toolId: string): Promise<unknown> {
  return apiPost(`/agents/${agentId}/tools`, { tool_id: toolId });
}
export function detachAgentTool(agentId: string, toolId: string): Promise<unknown> {
  return apiDelete(`/agents/${agentId}/tools/${toolId}`);
}
```

Use the real `apiPost`/`apiDelete` exports from `lib/api.ts` (READ it).

- [ ] **Step 2: Create `useAgentToolRefs.ts`**

Query `["agent", agentId, "tools"]` → `listAgentToolRefs`; mutations `attach`/`detach` invalidate that key. Mirror `useAgentTools.ts`.

- [ ] **Step 3: Rewrite `ToolsTab.tsx`**

READ the current file first to preserve the tab's props/shell contract (it receives the agent id / dirty-tracking context). Replace its body: render the full catalog from `useToolCatalog()` as a checklist; each tool row has a checkbox reflecting whether it's in `useAgentToolRefs(agentId).data`; toggling calls attach/detach. Show `display_name` + `tool_type` pill + `description`. Note above the list: "Tools are shared — manage the catalog under the Tools section." Remove all tool-authoring UI (ToolEditor/ToolTestPanel usage) from this tab. If `TabCountBadge`/`useTabCounts` counts tools, point the count at `useAgentToolRefs(agentId).data.length` (READ `useTabCounts.ts`).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/toolCatalogApi.ts frontend/src/hooks/useAgentToolRefs.ts frontend/src/components/agents/tabs/ToolsTab.tsx
git commit -m "feat(frontend): agent Tools tab is now a catalog reference picker"
```

---

### Task 13: Agent detail — convert KB tab to a doc tick picker

**Files:**
- Rewrite: `frontend/src/components/agents/tabs/KnowledgeBaseTab.tsx`
- Create: `frontend/src/hooks/useAgentKbDocs.ts`
- Modify: `frontend/src/lib/kbStoreApi.ts` (add agent kb-doc calls)

**Interfaces:**
- Produces: `listAgentKbDocs(agentId)`, `attachAgentKbDoc(agentId, docId)`, `detachAgentKbDoc(agentId, docId)`; `useAgentKbDocs(agentId)` + mutations.

- [ ] **Step 1: Add agent kb-doc calls to `kbStoreApi.ts`**

Endpoints `GET /agents/{id}/kb-documents`, `POST /agents/{id}/kb-documents` `{document_id}`, `DELETE /agents/{id}/kb-documents/{documentId}`. Return `KbDoc[]` for the list.

- [ ] **Step 2: Create `useAgentKbDocs.ts`**

Query `["agent", agentId, "kb-docs"]`; attach/detach mutations invalidate it. Mirror `useKbDocuments.ts`.

- [ ] **Step 3: Rewrite `KnowledgeBaseTab.tsx`**

READ the current file for the shell contract. Replace body: list documents the current user can access (`useKbDocuments()` from `useKbStore`), each with a checkbox reflecting membership in `useAgentKbDocs(agentId).data`; toggling attaches/detaches the grant. Only docs the user can access are listed (the API already filters). Add a hint: "Tick the documents this agent may search with the RAG tool. Upload/manage documents under the Database section." If the RAG tool isn't referenced, show an inline note: "Enable the Knowledge Base Search (RAG) tool in the Tools tab for these documents to be used at runtime." (read tool refs via `useAgentToolRefs(agentId)`). Remove all upload UI from this tab. Update the tab count to `useAgentKbDocs(agentId).data.length`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/kbStoreApi.ts frontend/src/hooks/useAgentKbDocs.ts frontend/src/components/agents/tabs/KnowledgeBaseTab.tsx
git commit -m "feat(frontend): agent KB tab is now a document tick picker (two-gate)"
```

---

## PHASE 5 — Docs

### Task 14: Update project docs

**Files:**
- Modify: `docs/codebase-summary.md`
- Modify: `docs/system-architecture.md`
- Modify: `docs/project-changelog.md`

- [ ] **Step 1: Update `codebase-summary.md`**

Under the `agent_builder` module row, note: Tools + KB are now tenant-wide shared resources (`tools` catalog + `agent_tools`; `kb_documents` store + `kb_document_grants` + `agent_kb_documents`), consumed via two-gate RAG. Update the Frontend routes table: add `/tools`, `/database` (real), `/chat`, `/apps`, `/settings` (placeholders); note Workflows/Audit are secondary sidebar entries. Add the new Alembic revisions to the migrations list.

- [ ] **Step 2: Update `system-architecture.md`**

Add a short "Shared Tools & KB (Sub-project A)" subsection: the two-gate model (RAG tool reference + per-agent doc grant), the doc user-ACL (owner + viewer/manager grants), and that catalog tool execution for gmail/calendar is stubbed.

- [ ] **Step 3: Append a `project-changelog.md` entry** dated 2026-07-18 summarizing the re-platform.

- [ ] **Step 4: (before final commit) Run `detect_changes()`**

Per repo `CLAUDE.md`: `detect_changes({scope: "compare", base_ref: "main"})` and confirm the affected symbols/flows match this plan's scope. Warn the user on anything unexpected.

- [ ] **Step 5: Commit**

```bash
git add docs/codebase-summary.md docs/system-architecture.md docs/project-changelog.md
git commit -m "docs: shared Tools + KB re-platform (Sub-project A)"
```

---

## Self-Review

**Spec coverage:**
- D1 tenant-wide + optional department tag → Task 1/2 (no department on tools; nullable on docs). ✓
- D2 owner + viewer/manager grants → Task 2 (`kb_document_grants`), Task 4 (`kb_grants_service`). ✓
- D3 two-gate (RAG tool + per-agent doc grant) → Task 5 (`agent_kb_documents`), Task 6 (`kb_search`). ✓
- D4 built-in catalog only, gmail/calendar stubbed → Task 1 (CHECK constraint), Task 3 (`DEFAULT_TOOL_SPECS`), Task 6 (stub). ✓
- D5 tool `description` + `params_schema` → Task 1 (columns), Task 3 (specs). ✓
- D6 greenfield reset + reseed → Task 1/2 (DROP+CREATE), Task 8 (reseed). ✓
- D7 new sidebar + Tools/Database real, others placeholder → Task 9/10/11. ✓
- D8 KB UI full (upload+list+grants) → Task 11. ✓
- Agent reference-picker tabs → Task 12/13. ✓
- API surface (§6 of spec) → Tasks 3/4/5/7. ✓
- OQ-2 (gmail/calendar creds deferred) → not built (stub). ✓ OQ-3 (any user uploads, becomes owner) → Task 4 `upload_document`. ✓

**Placeholder scan:** Frontend Tasks 10-13 intentionally instruct "READ the sibling file for exact export names" rather than reproducing unread code — this is precise interface specification, not a TODO. All backend code blocks are complete.

**Type consistency:** `params_schema` (not `input_schema`) used consistently in model, migration, serializer, `invoke_tool` validation, and frontend type. `tool_type` values `rag`/`gmail`/`calendar` consistent across CHECK constraint, `DEFAULT_TOOL_SPECS`, stub, and frontend union. Grant roles `viewer`/`manager` consistent across model CHECK, `kb_grants_service._VALID_ROLES`, and frontend. `effective_role` returned by serializer and consumed by frontend `KbDoc`.

## Open questions

- **Alembic head**: the two migrations must chain onto the current head — the executor resolves it via `alembic heads` at Task 1/2 (the mini-app migrations from recent commits are the likely current head).
- **`lib/api.ts` surface**: exact exported helper names (`apiGet`/`apiPost`/`apiDelete` vs an axios-style client) must be confirmed by reading the file; frontend snippets assume a thin fetch-wrapper matching `agentsApi.ts`.
- **`components/ui` exports**: `EmptyState`/`ErrorState`/`ErrorState` names assumed from the frontend explorer report; confirm against `components/ui/index.ts`.
- **Mini-app DB half** of the Database section is a placeholder here (deferred to sub-project D) — confirm that's acceptable for A's demo.
