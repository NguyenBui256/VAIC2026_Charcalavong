"""DocIntakePort -- hexagonal port for the Knowledge Base document pipeline.

Per structural-seed.md: ``doc_intake.py -- document upload -> parallel-team
MCP server``.

The KB upload pipeline: chunk, embed, index, and make retrievable. Per FR-2,
KB access is isolated to the Agent's Department. Per AD-11, every retrieval
call carries tenant_id + department_id.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

__all__ = ["DocIntakePort", "DocumentInput", "IngestResult", "RetrievalResult"]


class DocumentInput(BaseModel):
    """A document to ingest into the KB."""

    filename: str
    content_type: str  # e.g. "application/pdf", "text/plain"
    data: bytes  # raw document bytes
    agent_id: uuid.UUID


class IngestResult(BaseModel):
    """Result of a document ingest operation."""

    document_id: str
    chunk_count: int
    success: bool = True
    error: str = ""


class RetrievalResult(BaseModel):
    """A retrieval result from the KB."""

    passages: list[dict[str, Any]]  # cited passages with doc name + chunk ref
    latency_ms: int


@runtime_checkable
class DocIntakePort(Protocol):
    """Hexagonal port for the document intake / KB pipeline.

    Implementation routes to the parallel-team MCP server for indexing and
    retrieval (AD-3).
    """

    async def ingest(
        self,
        agent_id: uuid.UUID,
        document: DocumentInput,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
    ) -> IngestResult:
        """Upload, chunk, embed, and index a document into the Agent's KB.

        Per FR-2: upload completes within 30 s per document up to 20 MB.
        KB access is isolated to the Agent's Department.
        """
        ...

    async def retrieve(
        self,
        agent_id: uuid.UUID,
        query: str,
        *,
        tenant_id: uuid.UUID,
        department_id: uuid.UUID,
        top_k: int = 5,
    ) -> RetrievalResult:
        """Retrieve cited passages from the Agent's KB.

        Per FR-2: returns cited passages with document name and chunk reference.
        A wrong-department retrieval returns an empty result set (AD-11).
        """
        ...
