"""Public persistence and upload API shared by all chat surfaces."""

# FastAPI intentionally uses Depends/File calls as default values.
# ruff: noqa: B008

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.arq_pool import get_arq_pool
from app.core.deps import get_tenant_session
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.ids import uuid7
from app.core.jobs import enqueue_job_with_context
from app.core.model_catalog import get_provider_catalog
from app.core.settings import get_settings
from app.core.tenant_context import tenant_context
from app.modules.chat.models import (
    ChatAttachment,
    ChatMessage,
    ChatMessageAttachment,
    ChatMutation,
    ChatSession,
)

router = APIRouter(prefix="/chat", tags=["chat"])
# Edit chats (workflow graph / mini-app) always run on this fixed Gemini model
# via GEMINI_API_KEY (settings.google_api_key). The UI selects no model.
EDIT_CHAT_DEFAULT_PROVIDER = "google"
EDIT_CHAT_DEFAULT_MODEL = "gemini-3.1-flash-lite"
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_MESSAGE = 5
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]")


class CreateSessionRequest(BaseModel):
    scope: str
    target_type: str
    target_id: uuid.UUID
    provider_id: str | None = None
    model_name: str | None = None
    title: str = Field(default="Cuộc trò chuyện mới", min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_model_selection(self) -> CreateSessionRequest:
        if self.target_type == "workflow" and self.scope == "execution":
            if self.provider_id is not None or self.model_name is not None:
                raise ValueError("Workflow Chat uses each Agent's configured model")
        elif self.scope in {"graph_authoring", "mini_app_edit"}:
            # Edit chats (workflow graph / mini-app): the UI does not pick an
            # Agent or a model. The backend fills a default model at creation.
            pass
        elif not self.provider_id or not self.model_name:
            raise ValueError("provider_id and model_name are required for this chat")
        return self


class UpdateSessionRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class UpdateModelRequest(BaseModel):
    provider_id: str = Field(..., min_length=1, max_length=32)
    model_name: str = Field(..., min_length=1, max_length=255)


class CreateMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=200_000)
    client_message_id: str = Field(..., min_length=1, max_length=128)
    attachment_ids: list[uuid.UUID] = Field(default_factory=list, max_length=MAX_FILES_PER_MESSAGE)


def _ok(data: Any, **meta: Any) -> dict[str, Any]:
    return {"data": data, "error": None, "meta": meta}


def _user_id(request: Request) -> uuid.UUID:
    return uuid.UUID(str(request.state.user_id))


def _owned_session(db: Session, session_id: uuid.UUID, owner_id: uuid.UUID) -> ChatSession:
    row = db.scalar(
        select(ChatSession).where(ChatSession.id == session_id, ChatSession.owner_id == owner_id)
    )
    if row is None:
        raise NotFoundError("chat session not found")
    return row


def _serialize_session(row: ChatSession) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "scope": row.scope,
        "target_type": row.target_type,
        "target_id": str(row.target_id),
        "provider_id": row.provider_id,
        "model_name": row.model_name,
        "title": row.title,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_message(
    row: ChatMessage | None, attachment_ids: list[str] | None = None
) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "id": str(row.id),
        "session_id": str(row.session_id),
        "role": row.role,
        "content": row.content,
        "status": row.status,
        "client_message_id": row.client_message_id,
        "reply_to_id": str(row.reply_to_id) if row.reply_to_id else None,
        "provider_id": row.provider_id,
        "model_name": row.model_name,
        "usage": {"input_tokens": row.input_tokens, "output_tokens": row.output_tokens},
        "latency_ms": row.latency_ms,
        "trace_id": str(row.trace_id) if row.trace_id else None,
        "metadata": row.metadata_json,
        "error": row.error,
        "attachment_ids": attachment_ids or [],
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _serialize_attachment(row: ChatAttachment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "extraction_status": row.extraction_status,
        "extraction_error": row.extraction_error,
        "created_at": row.created_at.isoformat(),
    }


def _configured_model(provider_id: str, model_name: str) -> bool:
    return any(
        provider.id == provider_id
        and provider.configured
        and any(model.name == model_name for model in provider.models)
        for provider in get_provider_catalog(get_settings())
    )


def _default_model() -> tuple[str, str] | None:
    """Fixed edit-chat model (Gemini flash-lite), available when GEMINI_API_KEY is set."""
    if get_settings().google_api_key:
        return EDIT_CHAT_DEFAULT_PROVIDER, EDIT_CHAT_DEFAULT_MODEL
    return None


@router.get("/models")
def list_chat_models() -> dict[str, Any]:
    providers = [
        item.model_dump(mode="json")
        for item in get_provider_catalog(get_settings())
        if item.configured and item.id in {"openai", "google"}
    ]
    return _ok(providers)


@router.post("/sessions")
def create_chat_session(
    body: CreateSessionRequest, request: Request, db: Session = Depends(get_tenant_session)
) -> JSONResponse:  # noqa: B008,E501
    if body.scope in {"graph_authoring", "mini_app_edit"} and not (
        body.provider_id and body.model_name
    ):
        # Edit chats use the fixed Gemini default; it is intentionally not in the
        # global catalog, so skip the catalog check for this path.
        default = _default_model()
        if default is None:
            raise ValidationError("no chat model configured", code="model_not_configured")
        body.provider_id, body.model_name = default
    elif body.provider_id and not _configured_model(body.provider_id, body.model_name or ""):
        raise ValidationError("provider/model is not configured", code="model_not_configured")
    row = ChatSession(
        tenant_id=tenant_context.get(), owner_id=_user_id(request), **body.model_dump()
    )
    db.add(row)
    db.commit()
    return JSONResponse(status_code=201, content=_ok(_serialize_session(row)))


@router.get("/sessions")
def list_chat_sessions(
    request: Request,
    db: Session = Depends(get_tenant_session),
    scope: str | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
) -> dict[str, Any]:  # noqa: B008,E501
    statement = select(ChatSession).where(ChatSession.owner_id == _user_id(request))
    if scope:
        statement = statement.where(ChatSession.scope == scope)
    if target_type:
        statement = statement.where(ChatSession.target_type == target_type)
    if target_id:
        statement = statement.where(ChatSession.target_id == target_id)
    rows = db.scalars(statement.order_by(ChatSession.updated_at.desc())).all()
    return _ok([_serialize_session(row) for row in rows])


@router.get("/sessions/{session_id}")
def get_chat_session(
    session_id: uuid.UUID, request: Request, db: Session = Depends(get_tenant_session)
) -> dict[str, Any]:  # noqa: B008,E501
    return _ok(_serialize_session(_owned_session(db, session_id, _user_id(request))))


@router.patch("/sessions/{session_id}")
def rename_chat_session(
    session_id: uuid.UUID,
    body: UpdateSessionRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
) -> dict[str, Any]:  # noqa: B008,E501
    row = _owned_session(db, session_id, _user_id(request))
    row.title = body.title
    row.updated_at = datetime.now(UTC)
    db.commit()
    return _ok(_serialize_session(row))


@router.patch("/sessions/{session_id}/model")
def switch_chat_model(
    session_id: uuid.UUID,
    body: UpdateModelRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
) -> dict[str, Any]:  # noqa: B008,E501
    row = _owned_session(db, session_id, _user_id(request))
    if row.target_type == "workflow" and row.scope == "execution":
        raise ValidationError("Workflow Chat follows Agent configuration", code="model_locked")
    pending = db.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.session_id == row.id, ChatMessage.status == "pending")
    )  # noqa: E501
    if pending:
        raise ConflictError("cannot switch model while a message is pending", code="chat_pending")
    if not _configured_model(body.provider_id, body.model_name):
        raise ValidationError("provider/model is not configured", code="model_not_configured")
    row.provider_id, row.model_name, row.updated_at = (
        body.provider_id,
        body.model_name,
        datetime.now(UTC),
    )
    db.commit()
    return _ok(_serialize_session(row))


@router.delete("/sessions/{session_id}")
def delete_chat_session(
    session_id: uuid.UUID, request: Request, db: Session = Depends(get_tenant_session)
) -> JSONResponse:  # noqa: B008,E501
    row = _owned_session(db, session_id, _user_id(request))
    attachments = db.scalars(
        select(ChatAttachment)
        .join(ChatMessageAttachment)
        .join(ChatMessage)
        .where(ChatMessage.session_id == row.id)
    ).all()  # noqa: E501
    db.delete(row)
    db.flush()
    for attachment in attachments:
        refs = db.scalar(
            select(func.count())
            .select_from(ChatMessageAttachment)
            .where(ChatMessageAttachment.attachment_id == attachment.id)
        )  # noqa: E501
        if not refs:
            db.delete(attachment)
            Path(attachment.storage_path).unlink(missing_ok=True)
    db.commit()
    return JSONResponse(status_code=200, content=_ok({"deleted": str(session_id)}))


@router.get("/sessions/{session_id}/messages")
def list_chat_messages(
    session_id: uuid.UUID, request: Request, db: Session = Depends(get_tenant_session)
) -> dict[str, Any]:  # noqa: B008,E501
    _owned_session(db, session_id, _user_id(request))
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at, ChatMessage.id)
    ).all()  # noqa: E501
    links = (
        db.execute(
            select(ChatMessageAttachment.message_id, ChatMessageAttachment.attachment_id).where(
                ChatMessageAttachment.message_id.in_([row.id for row in rows])
            )
        ).all()
        if rows
        else []
    )  # noqa: E501
    by_message: dict[uuid.UUID, list[str]] = {}
    for message_id, attachment_id in links:
        by_message.setdefault(message_id, []).append(str(attachment_id))
    return _ok([_serialize_message(row, by_message.get(row.id)) for row in rows])


@router.post("/sessions/{session_id}/messages")
async def create_chat_message(
    session_id: uuid.UUID,
    body: CreateMessageRequest,
    request: Request,
    db: Session = Depends(get_tenant_session),
    pool: ArqRedis = Depends(get_arq_pool),
) -> JSONResponse:  # noqa: B008,E501
    chat_session = _owned_session(db, session_id, _user_id(request))
    existing = db.scalar(
        select(ChatMessage).where(
            ChatMessage.session_id == session_id,
            ChatMessage.client_message_id == body.client_message_id,
        )
    )  # noqa: E501
    if existing:
        reply = db.scalar(select(ChatMessage).where(ChatMessage.reply_to_id == existing.id))
        return JSONResponse(
            status_code=202,
            content=_ok(
                {"user": _serialize_message(existing), "assistant": _serialize_message(reply)},
                idempotent=True,
            ),
        )  # noqa: E501
    attachments = (
        list(
            db.scalars(
                select(ChatAttachment).where(
                    ChatAttachment.id.in_(body.attachment_ids),
                    ChatAttachment.owner_id == _user_id(request),
                )
            ).all()
        )
        if body.attachment_ids
        else []
    )  # noqa: E501
    if len(attachments) != len(set(body.attachment_ids)):
        raise NotFoundError("one or more attachments were not found")
    if any(item.extraction_status != "ready" for item in attachments):
        raise ConflictError(
            "all attachments must finish extraction before sending", code="attachment_not_ready"
        )
    now = datetime.now(UTC)
    user_message = ChatMessage(
        id=uuid7(),
        tenant_id=chat_session.tenant_id,
        session_id=chat_session.id,
        role="user",
        content=body.content,
        status="completed",
        client_message_id=body.client_message_id,
        created_at=now,
        updated_at=now,
    )  # noqa: E501
    assistant = ChatMessage(
        id=uuid7(),
        tenant_id=chat_session.tenant_id,
        session_id=chat_session.id,
        role="assistant",
        content="",
        status="pending",
        reply_to_id=user_message.id,
        created_at=now,
        updated_at=now,
    )  # noqa: E501
    db.add_all([user_message, assistant])
    db.flush()
    db.add_all(
        ChatMessageAttachment(
            tenant_id=chat_session.tenant_id, message_id=user_message.id, attachment_id=item.id
        )
        for item in attachments
    )  # noqa: E501
    chat_session.updated_at = now
    db.commit()
    try:
        await enqueue_job_with_context(
            pool,
            "process_chat_message",
            job_id=f"chat:{assistant.id}",
            user_message_id=str(user_message.id),
            assistant_message_id=str(assistant.id),
        )  # noqa: E501
    except Exception as exc:
        assistant.status, assistant.error = "failed", {"code": "queue_error", "message": str(exc)}
        assistant.updated_at = datetime.now(UTC)
        db.commit()
    return JSONResponse(
        status_code=202,
        content=_ok(
            {"user": _serialize_message(user_message), "assistant": _serialize_message(assistant)}
        ),
    )  # noqa: E501


@router.post("/attachments")
async def upload_chat_attachment(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_tenant_session),
    pool: ArqRedis = Depends(get_arq_pool),
) -> JSONResponse:  # noqa: B008,E501
    tenant_id, attachment_id = tenant_context.get(), uuid7()
    filename = (
        SAFE_FILENAME.sub("_", Path(file.filename or "file").name).strip("._")[:255] or "file"
    )
    root = Path(get_settings().chat_files_root) / str(tenant_id)
    root.mkdir(parents=True, exist_ok=True)
    path, digest, total = root / f"{attachment_id}_{filename}", hashlib.sha256(), 0
    try:
        with path.open("xb") as destination:
            while chunk := await file.read(64 * 1024):
                total += len(chunk)
                if total > MAX_FILE_BYTES:
                    raise ValidationError("file too large (max 20 MB)", code="file_too_large")
                digest.update(chunk)
                destination.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    row = ChatAttachment(
        id=attachment_id,
        tenant_id=tenant_id,
        owner_id=_user_id(request),
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        size_bytes=total,
        sha256=digest.hexdigest(),
        storage_path=str(path.resolve()),
        extraction_status="extracting",
    )  # noqa: E501
    db.add(row)
    db.commit()
    try:
        await enqueue_job_with_context(
            pool,
            "extract_chat_attachment",
            job_id=f"chat-extract:{row.id}",
            attachment_id=str(row.id),
        )  # noqa: E501
    except Exception as exc:
        row.extraction_status, row.extraction_error = (
            "failed",
            f"Không thể xếp hàng trích xuất: {exc}",
        )
        db.commit()
    return JSONResponse(status_code=201, content=_ok(_serialize_attachment(row)))


@router.get("/attachments/{attachment_id}")
def get_chat_attachment(
    attachment_id: uuid.UUID, request: Request, db: Session = Depends(get_tenant_session)
) -> dict[str, Any]:  # noqa: B008,E501
    row = db.scalar(
        select(ChatAttachment).where(
            ChatAttachment.id == attachment_id, ChatAttachment.owner_id == _user_id(request)
        )
    )  # noqa: E501
    if row is None:
        raise NotFoundError("attachment not found")
    return _ok(_serialize_attachment(row))


@router.get("/attachments/{attachment_id}/content")
def download_chat_attachment(
    attachment_id: uuid.UUID, request: Request, db: Session = Depends(get_tenant_session)
) -> FileResponse:  # noqa: B008,E501
    row = db.scalar(
        select(ChatAttachment).where(
            ChatAttachment.id == attachment_id, ChatAttachment.owner_id == _user_id(request)
        )
    )  # noqa: E501
    if row is None or not os.path.isfile(row.storage_path):
        raise NotFoundError("attachment not found")
    return FileResponse(row.storage_path, filename=row.filename, media_type=row.content_type)


@router.delete("/attachments/{attachment_id}")
def delete_chat_attachment(
    attachment_id: uuid.UUID, request: Request, db: Session = Depends(get_tenant_session)
) -> JSONResponse:  # noqa: B008,E501
    row = db.scalar(
        select(ChatAttachment).where(
            ChatAttachment.id == attachment_id, ChatAttachment.owner_id == _user_id(request)
        )
    )  # noqa: E501
    if row is None:
        raise NotFoundError("attachment not found")
    if db.scalar(
        select(func.count())
        .select_from(ChatMessageAttachment)
        .where(ChatMessageAttachment.attachment_id == row.id)
    ):
        raise ConflictError("attachment is already linked to a message", code="attachment_in_use")
    path = Path(row.storage_path)
    db.delete(row)
    db.commit()
    path.unlink(missing_ok=True)
    return JSONResponse(status_code=200, content=_ok({"deleted": str(attachment_id)}))


@router.post("/mutations/{mutation_id}/undo")
async def undo_chat_mutation(
    mutation_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_tenant_session),
    pool: ArqRedis = Depends(get_arq_pool),
) -> dict[str, Any]:  # noqa: B008,E501
    mutation = db.scalar(
        select(ChatMutation)
        .join(ChatSession)
        .where(ChatMutation.id == mutation_id, ChatSession.owner_id == _user_id(request))
    )  # noqa: E501
    if mutation is None:
        raise NotFoundError("mutation not found")
    if mutation.status != "applied":
        raise ConflictError("mutation was already undone", code="mutation_already_undone")
    from app.modules.chat.mutations import undo_mutation

    return _ok(await undo_mutation(db, mutation, pool))
