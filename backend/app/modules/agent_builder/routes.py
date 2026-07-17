"""Agent Builder HTTP routes — /agents CRUD (Story 2.1).

Thin adapter: parse request -> call service -> envelope (AD-1). No SQL or
business rules live here. `DomainError` subclasses raised by the service
flow through the registered exception handlers (`core/errors.py`).

Success envelope: `{data, error: null, meta: {}}` (AR-14).
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_tenant_session
from app.core.model_catalog import get_provider_catalog
from app.core.settings import get_settings
from app.modules.agent_builder.integration_client import test_integration as run_test_integration
from app.modules.agent_builder.integration_service import (
    create_integration,
    list_integrations,
    serialize_integration,
    soft_delete_integration,
    update_integration,
)
from app.modules.agent_builder.kb_service import (
    delete_document as delete_kb_document,
)
from app.modules.agent_builder.kb_service import (
    list_documents as list_kb_documents,
)
from app.modules.agent_builder.kb_service import serialize_document as serialize_kb_document
from app.modules.agent_builder.kb_service import upload_document as upload_kb_document
from app.modules.agent_builder.service import (
    Principal,
    create_agent,
    list_agents,
    serialize_agent,
    soft_delete_agent,
    update_agent,
)
from app.modules.agent_builder.service import get_agent as get_agent_service
from app.modules.agent_builder.tool_crud import (
    create_tool,
    list_tools,
    serialize_tool,
    soft_delete_tool,
    update_tool,
)
from app.modules.agent_builder.tool_service import get_tool, invoke_tool

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    department_id: uuid.UUID
    system_prompt: str = Field(..., min_length=1)


class UpdateAgentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    system_prompt: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1, max_length=32)
    department_id: uuid.UUID | None = None
    # Story 2.3 (AD-7): ModelRef {provider, model_name, parameters} as data.
    model: dict[str, Any] | None = None


class CreateToolRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    header: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    embedded_python: str | None = None


class UpdateToolRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    header: dict[str, Any] | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    embedded_python: str | None = None


class TestToolRequest(BaseModel):
    sample_input: dict[str, Any] = Field(default_factory=dict)


class CreateIntegrationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    base_url: str = Field(..., min_length=1, max_length=2048)
    auth_header: str = Field(..., min_length=1)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


class UpdateIntegrationRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    base_url: str | None = Field(default=None, min_length=1, max_length=2048)
    auth_header: str | None = Field(default=None, min_length=1)
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Envelope + principal helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": {}}


def _principal(request: Request) -> Principal:
    """Extract the caller's Principal from `request.state` (set by AuthMiddleware)."""
    dept = getattr(request.state, "department_id", None)
    return Principal(
        user_id=uuid.UUID(str(request.state.user_id)),
        tenant_id=uuid.UUID(str(request.state.tenant_id)),
        department_id=uuid.UUID(str(dept)) if dept else None,
        role=str(getattr(request.state, "role", "")),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("")
def create_agent_route(
    body: CreateAgentRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008 -- FastAPI idiom
) -> JSONResponse:
    """POST /agents — create a scoped Agent (AC1, AC10)."""
    principal = _principal(request)
    agent = create_agent(
        session,
        owner_id=principal.user_id,
        role=principal.role,
        name=body.name,
        department_id=body.department_id,
        system_prompt=body.system_prompt,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_agent(agent)))


@router.get("/providers")
def list_providers_route() -> JSONResponse:
    """GET /agents/providers — runtime provider/model catalog (T1, AC1, AC2).

    Registered before `/{agent_id}` so "providers" is never parsed as an
    agent id. `configured` reflects `Settings` only -- no live API calls.
    """
    catalog = get_provider_catalog(get_settings())
    return JSONResponse(
        status_code=200,
        content=_ok([p.model_dump() for p in catalog]),
    )


@router.get("/{agent_id}")
def get_agent_route(
    agent_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /agents/{id} — cross-tenant returns 404 via RLS (AC2, AC3)."""
    agent = get_agent_service(session, agent_id)
    return JSONResponse(status_code=200, content=_ok(serialize_agent(agent)))


@router.get("")
def list_agents_route(
    session: Session = Depends(get_tenant_session),  # noqa: B008
    department_id: uuid.UUID | None = None,
) -> JSONResponse:
    """GET /agents — tenant-scoped list, optional department filter (AC4, AC5)."""
    agents = list_agents(session, department_id=department_id)
    return JSONResponse(
        status_code=200, content=_ok([serialize_agent(a) for a in agents])
    )


@router.patch("/{agent_id}")
def update_agent_route(
    agent_id: uuid.UUID,
    body: UpdateAgentRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PATCH /agents/{id} — owner or builder-in-department only (AC6)."""
    principal = _principal(request)
    agent = update_agent(
        session,
        agent_id,
        principal,
        **body.model_dump(exclude_unset=True),
    )
    return JSONResponse(status_code=200, content=_ok(serialize_agent(agent)))


@router.delete("/{agent_id}")
def delete_agent_route(
    agent_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /agents/{id} — soft-delete only, same scoping as PATCH (AC7)."""
    principal = _principal(request)
    soft_delete_agent(session, agent_id, principal)
    return JSONResponse(status_code=200, content=_ok({"id": str(agent_id)}))


# ---------------------------------------------------------------------------
# Knowledge Base routes (Story 2.4)
# ---------------------------------------------------------------------------

@router.post("/{agent_id}/kb/documents")
def upload_kb_document_route(
    agent_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
) -> JSONResponse:
    """POST /agents/{id}/kb/documents — upload + ingest (AC1, AC2, AC3, AC4)."""
    principal = _principal(request)
    data = file.file.read()
    doc = upload_kb_document(
        session,
        agent_id=agent_id,
        principal=principal,
        filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        data=data,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_kb_document(doc)))


@router.get("/{agent_id}/kb/documents")
def list_kb_documents_route(
    agent_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /agents/{id}/kb/documents — status-aware document list (AC2)."""
    docs = list_kb_documents(session, agent_id=agent_id)
    return JSONResponse(
        status_code=200, content=_ok([serialize_kb_document(d) for d in docs])
    )


@router.delete("/{agent_id}/kb/documents/{document_id}")
def delete_kb_document_route(
    agent_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /agents/{id}/kb/documents/{doc_id} — index removal (AC5)."""
    _ = agent_id  # path scoping only; ownership resolved via the document's Agent
    principal = _principal(request)
    delete_kb_document(session, document_id=document_id, principal=principal)
    return JSONResponse(status_code=200, content=_ok({"id": str(document_id)}))


# ---------------------------------------------------------------------------
# Tool routes (Story 2.6)
# ---------------------------------------------------------------------------

@router.post("/{agent_id}/tools")
def create_tool_route(
    agent_id: uuid.UUID,
    body: CreateToolRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """POST /agents/{id}/tools — register a Tool (AC1)."""
    principal = _principal(request)
    tool = create_tool(
        session,
        agent_id=agent_id,
        principal=principal,
        display_name=body.display_name,
        header=body.header,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        embedded_python=body.embedded_python,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_tool(tool)))


@router.get("/{agent_id}/tools")
def list_tools_route(
    agent_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /agents/{id}/tools — list, RLS-scoped, header masked."""
    tools = list_tools(session, agent_id=agent_id)
    return JSONResponse(status_code=200, content=_ok([serialize_tool(t) for t in tools]))


@router.patch("/{agent_id}/tools/{tool_id}")
def update_tool_route(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    body: UpdateToolRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PATCH /agents/{id}/tools/{tool_id} — owner-or-same-department only."""
    principal = _principal(request)
    tool = update_tool(
        session,
        agent_id=agent_id,
        tool_id=tool_id,
        principal=principal,
        **body.model_dump(exclude_unset=True),
    )
    return JSONResponse(status_code=200, content=_ok(serialize_tool(tool)))


@router.delete("/{agent_id}/tools/{tool_id}")
def delete_tool_route(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /agents/{id}/tools/{tool_id} — soft-delete only."""
    principal = _principal(request)
    soft_delete_tool(session, agent_id=agent_id, tool_id=tool_id, principal=principal)
    return JSONResponse(status_code=200, content=_ok({"id": str(tool_id)}))


@router.post("/{agent_id}/tools/{tool_id}/test")
def test_tool_route(
    agent_id: uuid.UUID,
    tool_id: uuid.UUID,
    body: TestToolRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """POST /agents/{id}/tools/{tool_id}/test — Test Tool affordance (AC7).

    Exercises the SAME invoke -> validate -> (sandbox|MCP) -> validate path
    as a real invocation, so validation/sandbox errors surface here first.
    """
    principal = _principal(request)
    tool = get_tool(session, agent_id=agent_id, tool_id=tool_id)
    result = invoke_tool(
        session,
        tool,
        body.sample_input,
        tenant_id=principal.tenant_id,
        department_id=tool.department_id,
    )
    return JSONResponse(status_code=200, content=_ok(result.model_dump()))


# ---------------------------------------------------------------------------
# API Integration routes (Story 2.7)
# ---------------------------------------------------------------------------

@router.post("/{agent_id}/integrations")
def create_integration_route(
    agent_id: uuid.UUID,
    body: CreateIntegrationRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """POST /agents/{id}/integrations — register an Integration (AC1, AC2)."""
    principal = _principal(request)
    integration = create_integration(
        session,
        agent_id=agent_id,
        principal=principal,
        name=body.name,
        base_url=body.base_url,
        auth_header=body.auth_header,
        schema=body.schema_,
    )
    return JSONResponse(status_code=201, content=_ok(serialize_integration(integration)))


@router.get("/{agent_id}/integrations")
def list_integrations_route(
    agent_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """GET /agents/{id}/integrations — list, RLS-scoped, header masked (AC8)."""
    integrations = list_integrations(session, agent_id=agent_id)
    return JSONResponse(
        status_code=200, content=_ok([serialize_integration(i) for i in integrations])
    )


@router.patch("/{agent_id}/integrations/{integration_id}")
def update_integration_route(
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    body: UpdateIntegrationRequest,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """PATCH /agents/{id}/integrations/{integration_id} — owner-or-same-department only."""
    principal = _principal(request)
    integration = update_integration(
        session,
        agent_id=agent_id,
        integration_id=integration_id,
        principal=principal,
        **body.model_dump(exclude_unset=True, by_alias=True),
    )
    return JSONResponse(status_code=200, content=_ok(serialize_integration(integration)))


@router.delete("/{agent_id}/integrations/{integration_id}")
def delete_integration_route(
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    request: Request,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """DELETE /agents/{id}/integrations/{integration_id} — soft-delete only, symmetric authz."""
    principal = _principal(request)
    soft_delete_integration(
        session, agent_id=agent_id, integration_id=integration_id, principal=principal
    )
    return JSONResponse(status_code=200, content=_ok({"id": str(integration_id)}))


@router.post("/{agent_id}/integrations/{integration_id}/test")
def test_integration_route(
    agent_id: uuid.UUID,
    integration_id: uuid.UUID,
    session: Session = Depends(get_tenant_session),  # noqa: B008
) -> JSONResponse:
    """POST /agents/{id}/integrations/{integration_id}/test — Test Integration (AC9).

    Pings `GET {base_url}/health` with the decrypted header; NEVER returns
    the header, only `{status, status_code, latency_ms}`.
    """
    result = run_test_integration(session, agent_id=agent_id, integration_id=integration_id)
    return JSONResponse(status_code=200, content=_ok(result))
