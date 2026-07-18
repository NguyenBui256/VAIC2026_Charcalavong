# VAIC Tools MCP Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cho agent platform gọi & thực thi thật 3 tool của `vaic_tools` (retrieve_knowledge / send_gmail_email / create_calendar_event) + nối KB ingest/delete qua REST, bằng cách thay `McpClientStub` bằng một adapter thật.

**Architecture:** Một `VaicToolsAdapter` implement `McpClientPort`. Route theo tên tool: retrieve/gmail/calendar → MCP Streamable HTTP `/mcp/` (Bearer); ingest/delete → REST `/api/v1/documents`. Mapping tên/tham số/output tách sang module thuần (`vaic_tools_mapping.py`). Chọn adapter qua `get_mcp_client` (config-gated); stub là fallback nên dev/test không cần vaic_tools vẫn chạy.

**Tech Stack:** Python 3.13, FastAPI backend, `mcp~=1.0` (đã có), `httpx` (đã có ở dev), pydantic-settings.

## Global Constraints

- Không phá ranh giới hexagonal (AD-1): callers chỉ phụ thuộc `McpClientPort`, không phụ thuộc lớp cụ thể.
- Mọi `call_tool` bắt buộc `tenant_id` + `department_id`; adapter phải `_assert_scope` (raise `AuthorizationError`, code `mcp_scope_mismatch`) **trước** network (AD-11), y như `McpClientStub`.
- Không đổi hợp đồng audit / schema validation / frontend.
- File code > 200 dòng phải tách (rule modularization). Adapter (transport) và mapping (pure) tách sẵn từ đầu.
- **User override:** không bắt buộc viết test / chạy typecheck-lint-build. Các bước test dưới đây **OPTIONAL** — executor bỏ qua nếu user không yêu cầu. Commit **chỉ local, không push**.
- Không commit secret (`vaic_tools_api_key`) vào git.

---

### Task 1: Thêm config vaic_tools vào Settings

**Files:**
- Modify: `backend/app/core/settings.py` (thêm 4 field sau field `mini_app_bundle_root`, trước `@lru_cache`)

**Interfaces:**
- Produces: `Settings.vaic_tools_enabled: bool`, `Settings.vaic_tools_base_url: str`, `Settings.vaic_tools_mcp_url: str`, `Settings.vaic_tools_api_key: str` (env `VAIC_VAIC_TOOLS_ENABLED`, `VAIC_VAIC_TOOLS_BASE_URL`, `VAIC_VAIC_TOOLS_MCP_URL`, `VAIC_VAIC_TOOLS_API_KEY`).

- [ ] **Step 1: Thêm field vào class `Settings`**

```python
    # vaic_tools integration — real MCP tool server (retrieve/gmail/calendar
    # via MCP /mcp/, KB ingest/delete via REST /api/v1/documents). When
    # disabled the McpClientStub is used, so dev/test without a running
    # vaic_tools stays green.
    vaic_tools_enabled: bool = Field(
        default=False, description="Route MCP tool calls to the real vaic_tools server"
    )
    vaic_tools_base_url: str = Field(
        default="http://localhost:8000", description="vaic_tools REST root (ingest/delete)"
    )
    vaic_tools_mcp_url: str = Field(
        default="http://localhost:8000/mcp/", description="vaic_tools MCP Streamable HTTP endpoint"
    )
    vaic_tools_api_key: str = Field(
        default="", description="Bearer key matching vaic_tools MCP_API_KEYS"
    )
```

- [ ] **Step 2 (OPTIONAL verify):** import kiểm tra

Run: `.venv\Scripts\python.exe -c "from app.core.settings import get_settings; s=get_settings(); print(s.vaic_tools_enabled, s.vaic_tools_mcp_url)"` (chạy trong `backend/`)
Expected: `False http://localhost:8000/mcp/`

- [ ] **Step 3: Commit (local)**

```
git add backend/app/core/settings.py
git commit -m "feat(config): add vaic_tools connection settings"
```

---

### Task 2: Module mapping thuần (args + output)

**Files:**
- Create: `backend/app/core/adapters/vaic_tools_mapping.py`
- Test (OPTIONAL): `backend/tests/unit/test_vaic_tools_mapping.py`

**Interfaces:**
- Produces:
  - `MCP_TOOL_NAMES: dict[str, str]` — platform name → vaic MCP tool name.
  - `map_arguments(platform_tool: str, arguments: dict, *, idempotency_key: str) -> dict`
  - `map_output(platform_tool: str, raw: dict) -> dict`
- Consumes: nothing (pure).

- [ ] **Step 1 (OPTIONAL): Viết test thất bại**

```python
# backend/tests/unit/test_vaic_tools_mapping.py
from app.core.adapters import vaic_tools_mapping as m


def test_gmail_args_wrap_to_and_inject_key():
    out = m.map_arguments("gmail", {"to": "a@b.com", "subject": "S", "body": "B"}, idempotency_key="k" * 8)
    assert out == {"idempotency_key": "k" * 8, "to": ["a@b.com"], "subject": "S", "text_body": "B"}


def test_calendar_args_title_to_summary():
    out = m.map_arguments("calendar", {"title": "T", "start": "s", "end": "e", "attendees": ["x@y.com"]}, idempotency_key="k" * 8)
    assert out["summary"] == "T" and out["start"] == "s" and out["attendees"] == ["x@y.com"]


def test_ragsearch_output_maps_results_to_passages():
    raw = {"results": [{"text": "hello", "score": 0.9, "source": {"filename": "f.pdf", "section": "S", "chunk_index": 2}}]}
    out = m.map_output("rag.search", raw)
    assert out == {"passages": [{"passage": "hello", "document_name": "f.pdf", "chunk_reference": "S#2", "score": 0.9}]}


def test_gmail_output_normalized():
    assert m.map_output("gmail", {"message_id": "m", "status": "sent", "thread_id": "t"}) == {"message_id": "m", "status": "sent"}
```

- [ ] **Step 2 (OPTIONAL): Chạy test — kỳ vọng FAIL** (`ModuleNotFoundError`)

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_vaic_tools_mapping.py -v`

- [ ] **Step 3: Viết `vaic_tools_mapping.py`**

```python
"""Pure translation between VAIC platform tool contracts and vaic_tools.

No I/O. Maps the platform's internal call_tool names/args/outputs to the
vaic_tools MCP tool signatures (and back). Kept separate from transport
(vaic_tools_adapter.py) so the mapping is unit-testable without a network.
"""
from __future__ import annotations

from typing import Any

__all__ = ["MCP_TOOL_NAMES", "map_arguments", "map_output"]

# platform call_tool name -> vaic_tools MCP tool name
MCP_TOOL_NAMES: dict[str, str] = {
    "rag.search": "retrieve_knowledge",
    "gmail": "send_gmail_email",
    "calendar": "create_calendar_event",
}


def map_arguments(platform_tool: str, arguments: dict[str, Any], *, idempotency_key: str) -> dict[str, Any]:
    """Translate platform tool args -> vaic_tools MCP tool args.

    gmail/calendar require `idempotency_key` (min 8 chars) — injected here.
    """
    if platform_tool == "rag.search":
        args: dict[str, Any] = {"query": arguments["query"]}
        if arguments.get("top_k") is not None:
            args["top_k"] = arguments["top_k"]
        if arguments.get("document_ids"):
            args["document_ids"] = arguments["document_ids"]
        return args
    if platform_tool == "gmail":
        to = arguments["to"]
        return {
            "idempotency_key": idempotency_key,
            "to": [to] if isinstance(to, str) else list(to),
            "subject": arguments["subject"],
            "text_body": arguments.get("body") or arguments.get("text_body"),
        }
    if platform_tool == "calendar":
        out: dict[str, Any] = {
            "idempotency_key": idempotency_key,
            "summary": arguments.get("title") or arguments.get("summary"),
            "start": arguments["start"],
            "end": arguments["end"],
        }
        if arguments.get("attendees"):
            out["attendees"] = arguments["attendees"]
        return out
    raise ValueError(f"Unsupported MCP tool: {platform_tool}")


def map_output(platform_tool: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Translate vaic_tools tool output -> the platform's expected output shape."""
    if platform_tool == "rag.search":
        return {
            "passages": [
                {
                    "passage": item.get("text", ""),
                    "document_name": (item.get("source") or {}).get("filename", ""),
                    "chunk_reference": _chunk_ref(item.get("source") or {}),
                    "score": float(item.get("score", 0.0)),
                }
                for item in raw.get("results", [])
            ]
        }
    if platform_tool == "gmail":
        return {"message_id": raw.get("message_id", ""), "status": raw.get("status", "")}
    if platform_tool == "calendar":
        return {"event_id": raw.get("event_id", ""), "status": raw.get("status", "")}
    raise ValueError(f"Unsupported MCP tool: {platform_tool}")


def _chunk_ref(source: dict[str, Any]) -> str:
    section = source.get("section") or ""
    chunk_index = source.get("chunk_index")
    return f"{section}#{chunk_index}" if chunk_index is not None else section
```

- [ ] **Step 4 (OPTIONAL): Chạy test — kỳ vọng PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_vaic_tools_mapping.py -v`

- [ ] **Step 5: Commit (local)**

```
git add backend/app/core/adapters/vaic_tools_mapping.py backend/tests/unit/test_vaic_tools_mapping.py
git commit -m "feat(mcp): add vaic_tools arg/output mapping"
```

---

### Task 3: VaicToolsAdapter (transport MCP + REST)

**Files:**
- Create: `backend/app/core/adapters/vaic_tools_adapter.py`
- Test (OPTIONAL): `backend/tests/unit/test_vaic_tools_adapter.py`

**Interfaces:**
- Consumes: `vaic_tools_mapping.MCP_TOOL_NAMES / map_arguments / map_output` (Task 2); `McpClientPort`, `ToolResult` (`app.core.ports.mcp_client`); `AuthorizationError` (`app.core.errors`); `uuid7` (`app.core.ids`).
- Produces: `VaicToolsAdapter(*, agent_department_id: uuid.UUID, base_url: str, mcp_url: str, api_key: str)` implement `McpClientPort` (dùng bởi Task 4).

- [ ] **Step 1 (OPTIONAL): Viết test scope-mismatch (không cần network)**

```python
# backend/tests/unit/test_vaic_tools_adapter.py
import uuid
import pytest
from app.core.adapters.vaic_tools_adapter import VaicToolsAdapter
from app.core.errors import AuthorizationError


@pytest.mark.asyncio
async def test_call_tool_raises_on_department_mismatch():
    dept = uuid.uuid4()
    adapter = VaicToolsAdapter(agent_department_id=dept, base_url="http://x", mcp_url="http://x/mcp/", api_key="k")
    with pytest.raises(AuthorizationError):
        await adapter.call_tool("gmail", {}, tenant_id=uuid.uuid4(), department_id=uuid.uuid4())


@pytest.mark.asyncio
async def test_list_tools_reports_five(monkeypatch):
    dept = uuid.uuid4()
    adapter = VaicToolsAdapter(agent_department_id=dept, base_url="http://x", mcp_url="http://x/mcp/", api_key="k")
    names = await adapter.list_tools(tenant_id=uuid.uuid4(), department_id=dept)
    assert set(names) == {"rag.ingest", "rag.delete", "rag.search", "gmail", "calendar"}
```

- [ ] **Step 2 (OPTIONAL): Chạy — kỳ vọng FAIL** (`ModuleNotFoundError`)

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_vaic_tools_adapter.py -v`

- [ ] **Step 3: Viết `vaic_tools_adapter.py`**

```python
"""VaicToolsAdapter -- real McpClientPort backed by the vaic_tools server.

Routes retrieve/gmail/calendar over MCP Streamable HTTP (/mcp/, Bearer) and
KB ingest/delete over vaic_tools REST (/api/v1/documents). Enforces the
AD-11 client-side department scope before any network call, exactly like
McpClientStub. Names/args/outputs translate via vaic_tools_mapping (pure).

Selected by get_mcp_client when VAIC_TOOLS_ENABLED is true; otherwise the
stub is used. Any transport/upstream error is returned as a failed
ToolResult (success=False) so the caller audits tool.rejected / sets the
KB doc to failed — the adapter never leaks a raw exception except the
AD-11 AuthorizationError, which must propagate.
"""
from __future__ import annotations

import base64
import json
import uuid
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.adapters import vaic_tools_mapping as mapping
from app.core.errors import AuthorizationError
from app.core.ids import uuid7
from app.core.ports.mcp_client import McpClientPort, ToolResult

__all__ = ["VaicToolsAdapter"]

_REST_TOOLS = {"rag.ingest", "rag.delete"}
_TIMEOUT_S = 30


class VaicToolsAdapter(McpClientPort):
    def __init__(
        self, *, agent_department_id: uuid.UUID, base_url: str, mcp_url: str, api_key: str
    ) -> None:
        self._agent_department_id = agent_department_id
        self._base_url = base_url.rstrip("/")
        self._mcp_url = mcp_url
        self._api_key = api_key

    def _assert_scope(self, department_id: uuid.UUID) -> None:
        if department_id != self._agent_department_id:
            raise AuthorizationError(
                "VaicToolsAdapter.call_tool: department_id does not match the "
                "calling Agent's Department (AD-11)",
                code="mcp_scope_mismatch",
            )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> ToolResult:
        self._assert_scope(department_id)
        _ = tenant_id  # scoping only
        try:
            if tool_name in _REST_TOOLS:
                return await self._call_rest(tool_name, arguments)
            return await self._call_mcp(tool_name, arguments)
        except AuthorizationError:
            raise
        except Exception as exc:  # noqa: BLE001 -- surface upstream failures as failed result
            return ToolResult(tool_name=tool_name, output={}, success=False, error=str(exc))

    async def _call_mcp(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        vaic_name = mapping.MCP_TOOL_NAMES[tool_name]
        args = mapping.map_arguments(tool_name, arguments, idempotency_key=str(uuid7()))
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with streamablehttp_client(self._mcp_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(vaic_name, args)
        if getattr(result, "isError", False):
            text = _first_text(result) or "vaic_tools MCP tool returned an error"
            return ToolResult(tool_name=tool_name, output={}, success=False, error=text)
        raw = _extract_structured(result)
        return ToolResult(
            tool_name=tool_name, output=mapping.map_output(tool_name, raw), success=True
        )

    async def _call_rest(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(base_url=self._base_url, timeout=_TIMEOUT_S) as client:
            if tool_name == "rag.ingest":
                data = base64.b64decode(arguments["data"])
                files = {
                    "file": (
                        arguments["filename"],
                        data,
                        arguments.get("content_type") or "application/octet-stream",
                    )
                }
                resp = await client.post("/api/v1/documents", files=files, headers=headers)
                resp.raise_for_status()
                body = resp.json()
                return ToolResult(
                    tool_name=tool_name,
                    success=True,
                    output={
                        "document_id": body.get("id"),
                        "chunk_count": body.get("chunk_count", 0),
                    },
                )
            # rag.delete
            ext = arguments.get("external_document_id")
            resp = await client.delete(f"/api/v1/documents/{ext}", headers=headers)
            resp.raise_for_status()
            body = resp.json()
            return ToolResult(
                tool_name=tool_name, success=True, output={"deleted": bool(body.get("deleted"))}
            )

    async def list_tools(
        self, *, tenant_id: uuid.UUID, department_id: uuid.UUID
    ) -> list[str]:
        self._assert_scope(department_id)
        _ = tenant_id
        return ["rag.ingest", "rag.delete", "rag.search", "gmail", "calendar"]


def _first_text(result: Any) -> str:
    content = getattr(result, "content", None) or []
    if content and getattr(content[0], "text", None):
        return content[0].text
    return ""


def _extract_structured(result: Any) -> dict[str, Any]:
    """Pull the tool's dict result from an MCP CallToolResult.

    FastMCP (json_response=True) returns dict tool results as structuredContent.
    Some SDK/server combos wrap a non-dict return under a single "result" key;
    when the dict is exactly {"result": ...} we unwrap it. Falls back to
    JSON-parsing the first text content block.
    """
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        if set(sc.keys()) == {"result"} and isinstance(sc["result"], dict):
            return sc["result"]
        return sc
    text = _first_text(result)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    return {}
```

> **Verification point cho executor:** `_extract_structured` giả định shape của `CallToolResult` từ FastMCP `json_response=True`. Khi verify live (Task 6), gọi thật `retrieve_knowledge` và in `result` để xác nhận `structuredContent` chứa `{request_id, query, results, ...}`; chỉnh hàm nếu server bọc khác.

- [ ] **Step 4 (OPTIONAL): Chạy — kỳ vọng PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_vaic_tools_adapter.py -v`

- [ ] **Step 5: Commit (local)**

```
git add backend/app/core/adapters/vaic_tools_adapter.py backend/tests/unit/test_vaic_tools_adapter.py
git commit -m "feat(mcp): add VaicToolsAdapter (MCP + REST transport)"
```

---

### Task 4: Wire factory get_mcp_client

**Files:**
- Modify: `backend/app/core/deps.py` (hàm `get_mcp_client`, dòng ~87-97)

**Interfaces:**
- Consumes: `Settings.vaic_tools_*` (Task 1), `VaicToolsAdapter` (Task 3), `McpClientStub` (hiện có).
- Produces: `get_mcp_client(*, agent_department_id)` trả `VaicToolsAdapter` khi enabled, ngược lại `McpClientStub`. Chữ ký không đổi (callers không sửa).

- [ ] **Step 1: Thay thân hàm `get_mcp_client`**

Thay đoạn hiện tại:

```python
    from app.core.adapters.mcp_client_stub import McpClientStub

    return McpClientStub(agent_department_id=agent_department_id)
```

bằng:

```python
    settings = get_settings()
    if settings.vaic_tools_enabled:
        from app.core.adapters.vaic_tools_adapter import VaicToolsAdapter

        return VaicToolsAdapter(
            agent_department_id=agent_department_id,
            base_url=settings.vaic_tools_base_url,
            mcp_url=settings.vaic_tools_mcp_url,
            api_key=settings.vaic_tools_api_key,
        )

    from app.core.adapters.mcp_client_stub import McpClientStub

    return McpClientStub(agent_department_id=agent_department_id)
```

(`get_settings` đã được import ở đầu `deps.py`.)

- [ ] **Step 2 (OPTIONAL verify):** với `vaic_tools_enabled=false` (mặc định), factory trả stub

Run: `.venv\Scripts\python.exe -c "import uuid; from app.core.deps import get_mcp_client; print(type(get_mcp_client(agent_department_id=uuid.uuid4())).__name__)"`
Expected: `McpClientStub`

- [ ] **Step 3: Commit (local)**

```
git add backend/app/core/deps.py
git commit -m "feat(mcp): select VaicToolsAdapter when vaic_tools enabled"
```

---

### Task 5: Dịch platform doc-id → external-id trong kb_search

**Files:**
- Modify: `backend/app/modules/agent_builder/kb_retrieval.py` (hàm `kb_search`, dòng ~102-124)

**Interfaces:**
- Consumes: `KbDocument.external_document_id` (`app.modules.agent_builder.kb_models`), `select` (đã import).
- Produces: `kb_search` truyền `document_ids` = external ids của vaic (fallback về platform ids khi chưa có external — giữ stub/test cũ xanh).

**Lý do:** `rag.ingest` lưu `KbDocument.external_document_id` = id do vaic sinh. `retrieve_knowledge` filter theo id của vaic, không phải UUID nội bộ. Không dịch → filter sai → luôn rỗng.

- [ ] **Step 1: Thay đoạn build `doc_ids` và call**

Đoạn hiện tại:

```python
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
```

thay bằng:

```python
    from app.modules.agent_builder.kb_models import KbDocument

    has_rag = any(t.tool_type == "rag" for t in list_agent_tool_refs(session, agent_id=agent_id))
    if not has_rag:
        return []
    platform_ids = list(list_agent_document_ids(session, agent_id))
    if not platform_ids:
        return []
    # vaic_tools filters retrieval by ITS OWN document id (stored at ingest as
    # external_document_id), not the platform UUID. Translate; fall back to the
    # platform ids when no external id exists yet (stub/test path).
    external_ids = list(
        session.execute(
            select(KbDocument.external_document_id).where(
                KbDocument.id.in_(platform_ids),
                KbDocument.external_document_id.is_not(None),
            )
        ).scalars().all()
    )
    doc_ids = external_ids or [str(d) for d in platform_ids]

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
```

- [ ] **Step 2 (OPTIONAL): Chạy test hồi quy KB retrieval — kỳ vọng vẫn PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_kb_retrieval.py -v`
Expected: PASS (fallback giữ hành vi cũ khi external id trống)

- [ ] **Step 3: Commit (local)**

```
git add backend/app/modules/agent_builder/kb_retrieval.py
git commit -m "fix(kb): translate platform doc ids to vaic external ids for retrieval"
```

---

### Task 6: Verify end-to-end với vaic_tools thật (manual)

**Files:** none (vận hành). Điều kiện: vaic_tools chạy (`docker compose up` ở `vaic_tools/`) với `.env` đủ MongoDB Atlas + Jina + Google + `MCP_API_KEYS`.

**Interfaces:** none.

- [ ] **Step 1: Bật integration ở backend `.env`**

Thêm vào `backend/.env` (KHÔNG commit):
```
VAIC_VAIC_TOOLS_ENABLED=true
VAIC_VAIC_TOOLS_BASE_URL=http://localhost:8000
VAIC_VAIC_TOOLS_MCP_URL=http://localhost:8000/mcp/
VAIC_VAIC_TOOLS_API_KEY=<khớp MCP_API_KEYS của vaic_tools>
```

- [ ] **Step 2: Verify `_extract_structured` shape (retrieve)**

Chạy đoạn probe (trong `backend/`, sau khi upload ≥1 tài liệu qua UI KB):
- Upload tài liệu qua Knowledge Base UI → kiểm tra `KbDocument.status="indexed"` và `external_document_id` không rỗng.
- Attach tool **Knowledge Base Search (RAG)** vào 1 agent, grant tài liệu đó cho agent.
- Gọi Test Tool trên RAG với `{"query": "..."}` → mong đợi `passages[]` có nội dung thật.
- Nếu rỗng bất thường: in `result` thô trong `_call_mcp` để xác nhận shape `structuredContent`, chỉnh `_extract_structured` nếu server bọc khác (xem verification point Task 3).

- [ ] **Step 3: Verify gmail + calendar (side-effect thật — cẩn trọng)**

- Calendar: Test Tool với `summary`/`title` = `[TEST] ...`, `start`/`end` là RFC3339 có offset (vd `2026-07-20T09:00:00+07:00`), `send_updates` mặc định `none`. Sau khi tạo, xoá event bằng id trả về.
- Gmail: gửi tới địa chỉ nội bộ của bạn; email gửi thật, không rollback được.
- Kỳ vọng: output `{message_id, status}` / `{event_id, status}`, và audit `tool.invoked` xuất hiện.

- [ ] **Step 4: Verify delete**

- Xoá tài liệu KB đã upload → xác nhận biến mất khỏi vaic (`GET /api/v1/documents` không còn) và `KbDocument` bị xoá ở platform.

---

## Self-Review

**Spec coverage:**
- Adapter thật thay stub → Task 3 + Task 4. ✔
- Mapping 5 tool (retrieve/gmail/calendar MCP; ingest/delete REST) → Task 2 (args/output) + Task 3 (transport). ✔
- Config gated + stub fallback → Task 1 + Task 4. ✔
- Dịch id search → Task 5. ✔
- Scope AD-11 / audit / schema / frontend không đổi → Task 3 giữ `_assert_scope`; callers không sửa (chỉ kb_search đổi cách build document_ids, không đổi hợp đồng). ✔
- Edge: idempotency_key inject (Task 2 map_arguments), lỗi upstream → failed ToolResult (Task 3), side-effect thật (Task 6). ✔
- Unresolved questions của spec đã giải: id tự sinh (Task 5 lý do), output shape gmail/calendar (Task 2 map_output). ✔

**Placeholder scan:** không có TBD/TODO; mọi step code có nội dung thật. Verification point Task 3 là chỉ dẫn kiểm chứng cụ thể, không phải placeholder.

**Type consistency:** `map_arguments`/`map_output`/`MCP_TOOL_NAMES` dùng nhất quán giữa Task 2 và Task 3. `ToolResult` field (`tool_name`, `output`, `success`, `error`) khớp `app.core.ports.mcp_client.ToolResult`. `VaicToolsAdapter.__init__` kwargs khớp giữa Task 3 và Task 4.

## Unresolved questions

1. Multi-tenant: vaic_tools là instance chia sẻ, isolation chỉ dựa trên `document_ids` filter lúc retrieve. Nhiều tenant thật cần tách instance/DB — ngoài scope đợt này.
2. `_extract_structured` cần xác nhận bằng live call (Task 6 Step 2) — shape `CallToolResult` của FastMCP có thể khác giữa các phiên bản SDK.
3. Idempotency hiện best-effort (`uuid7()` mỗi call). Nếu cần dedupe thật khi orchestrator retry, nên dẫn xuất key từ `run_id + step_id` — cân nhắc ở epic orchestrator, không phải đợt này.
4. **Giới hạn 100 doc/retrieval:** vaic `RetrieveRequest.document_ids` cap 100. Agent được cấp >100 KB doc → `rag.search` reject cả call (KB hiện rỗng). Không truncate (sẽ sai isolation). Cần quyết định sản phẩm: chunk nhiều call rồi merge, hay giới hạn số doc/agent, hay tách vaic instance theo tenant. (Đã comment tại `kb_retrieval.py`.)
