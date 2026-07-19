"""ARQ jobs for extraction and persistent message processing."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from arq.cron import cron
from sqlalchemy import delete, select

from app.core.adapters.registry import select_llm_adapter
from app.core.db import AdminSessionLocal
from app.core.ids import uuid7
from app.core.jobs import enqueue_job_with_context, tenant_aware_job
from app.core.ports.llm import CompletionResult, Message, ModelRef
from app.core.settings import get_settings
from app.modules.agent_builder.kb_retrieval import kb_search
from app.modules.agent_builder.models import Agent
from app.modules.chat.extraction import extract_text, select_attachment_context
from app.modules.chat.models import ChatAttachment, ChatMessage, ChatMessageAttachment, ChatSession


async def cleanup_chat_attachments(ctx: dict[str, Any]) -> int:
    """Delete uploads older than 24h that were never attached to a message."""
    _ = ctx
    cutoff = datetime.now(UTC) - timedelta(hours=24)
    root = Path(get_settings().chat_files_root).resolve()
    with AdminSessionLocal() as db:
        rows = db.scalars(
            select(ChatAttachment)
            .outerjoin(
                ChatMessageAttachment,
                ChatMessageAttachment.attachment_id == ChatAttachment.id,
            )
            .where(
                ChatMessageAttachment.attachment_id.is_(None),
                ChatAttachment.created_at < cutoff,
            )
        ).all()
        paths = [Path(row.storage_path).resolve() for row in rows]
        if rows:
            db.execute(
                delete(ChatAttachment).where(ChatAttachment.id.in_([row.id for row in rows]))
            )
            db.commit()
    for path in paths:
        if path.is_relative_to(root):
            path.unlink(missing_ok=True)
    return len(paths)


chat_cron_jobs = [cron(cleanup_chat_attachments, hour={3}, minute={15}, unique=True)]


@tenant_aware_job
async def extract_chat_attachment(ctx: dict[str, Any], *, attachment_id: str) -> None:
    db = ctx["session"]
    row = db.get(ChatAttachment, uuid.UUID(attachment_id))
    if row is None or row.extraction_status != "extracting":
        return
    try:
        row.extracted_text = await asyncio.to_thread(
            extract_text, Path(row.storage_path), row.filename, row.content_type
        )
        row.extraction_status, row.extraction_error = "ready", None
    except Exception as exc:
        row.extraction_status, row.extraction_error = "failed", str(exc)[:2000]
    db.commit()


def _retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    return isinstance(exc, TimeoutError | ConnectionError) or status in {
        408,
        429,
        500,
        502,
        503,
        504,
    }


async def _complete_with_retry(messages: list[Message], model: ModelRef) -> CompletionResult:
    adapter = select_llm_adapter(model.provider)
    attempts = max(1, get_settings().llm_max_attempts)
    for attempt in range(attempts):
        try:
            return await asyncio.to_thread(adapter.complete, messages, model)
        except Exception as exc:
            if attempt + 1 >= attempts or not _retryable(exc):
                raise
            await asyncio.sleep(min(2**attempt, 8))
    raise RuntimeError("unreachable")


def _history(db: Any, chat_session: ChatSession, current_user_id: uuid.UUID) -> list[Message]:
    rows = list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == chat_session.id,
                ChatMessage.status == "completed",
                ChatMessage.id != current_user_id,
                ChatMessage.role.in_(("user", "assistant")),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(12)
        ).all()
    )
    rows.reverse()
    result: list[Message] = []
    used = 0
    for row in reversed(rows):
        remaining = 24_000 - used
        if remaining <= 0:
            break
        result.append(Message(role=row.role, content=row.content[-remaining:]))
        used += min(len(row.content), remaining)
    result.reverse()
    return result


def _attachment_context(db: Any, user_message: ChatMessage) -> str:
    rows = db.execute(
        select(ChatAttachment.filename, ChatAttachment.extracted_text)
        .join(ChatMessageAttachment, ChatMessageAttachment.attachment_id == ChatAttachment.id)
        .where(ChatMessageAttachment.message_id == user_message.id)
    ).all()
    return select_attachment_context(
        user_message.content,
        [(filename, extracted or "") for filename, extracted in rows],
    )


async def _process_agent(
    db: Any, chat_session: ChatSession, user_message: ChatMessage
) -> tuple[str, CompletionResult, dict[str, Any]]:
    agent = db.get(Agent, chat_session.target_id)
    if agent is None or agent.is_deleted:
        raise RuntimeError("Agent không tồn tại hoặc đã bị xóa")
    citations: list[dict[str, Any]] = []
    kb_context = ""
    try:
        passages = await kb_search(db, agent.id, user_message.content, top_k=5)
        kb_context = "\n\n".join(
            f"[KB: {item.document_name} — {item.chunk_reference}]\n{item.passage}"
            for item in passages
        )
        citations = [
            {
                "document_name": item.document_name,
                "chunk_reference": item.chunk_reference,
                "score": item.score,
            }
            for item in passages
        ]
    except Exception as exc:
        citations = [{"warning": f"KB retrieval unavailable: {exc}"}]
    source_context = "\n\n".join(
        value for value in (_attachment_context(db, user_message), kb_context) if value
    )
    system = agent.system_prompt
    if source_context:
        system += (
            "\n\nDùng các nguồn dưới đây làm tài liệu tham khảo. Không bịa nội dung ngoài "
            "nguồn; nêu rõ khi nguồn không đủ.\n\n" + source_context
        )
    model = ModelRef(
        provider=chat_session.provider_id or "",
        model_name=chat_session.model_name or "",
        parameters=(agent.model or {}).get("parameters", {}),
    )
    messages = [
        Message(role="system", content=system),
        *_history(db, chat_session, user_message.id),
    ]
    messages.append(Message(role="user", content=user_message.content))
    completion = await _complete_with_retry(messages, model)
    return completion.content, completion, {"citations": citations, "tool_results": []}


async def _process_workflow(
    ctx: dict[str, Any], db: Any, chat_session: ChatSession, user_message: ChatMessage
) -> tuple[str, dict[str, Any]]:
    from app.modules.orchestrator.service import create_run

    run = create_run(
        db,
        chat_session.target_id,
        role="builder",
        input={
            "message": user_message.content,
            "chat_session_id": str(chat_session.id),
            "chat_message_id": str(user_message.id),
            "attachment_context": _attachment_context(db, user_message),
        },
    )
    pool = ctx.get("redis") or ctx.get("arq_redis")
    if pool is None:
        raise RuntimeError("ARQ worker Redis context is unavailable")
    await enqueue_job_with_context(pool, "run_workflow", run_id=str(run.id))
    return "Đã tạo Workflow Run. Theo dõi tiến độ và phê duyệt bên dưới.", {
        "run_id": str(run.id),
        "run_status": run.status,
        "model_policy": "agent_configuration",
    }


@tenant_aware_job
async def process_chat_message(
    ctx: dict[str, Any], *, user_message_id: str, assistant_message_id: str
) -> None:
    db = ctx["session"]
    user_message = db.get(ChatMessage, uuid.UUID(user_message_id))
    assistant = db.get(ChatMessage, uuid.UUID(assistant_message_id))
    if user_message is None or assistant is None or assistant.status != "pending":
        return
    chat_session = db.get(ChatSession, user_message.session_id)
    if chat_session is None:
        return
    trace_id = uuid7()
    try:
        if chat_session.scope == "execution" and chat_session.target_type == "agent":
            assistant.content, completion, assistant.metadata_json = await _process_agent(
                db, chat_session, user_message
            )
            assistant.provider_id, assistant.model_name = chat_session.provider_id, completion.model
            assistant.input_tokens = completion.usage.get("input_tokens")
            assistant.output_tokens = completion.usage.get("output_tokens")
            assistant.latency_ms = completion.latency_ms
        elif chat_session.scope == "execution" and chat_session.target_type == "workflow":
            assistant.content, assistant.metadata_json = await _process_workflow(
                ctx, db, chat_session, user_message
            )
        else:
            from app.modules.chat.mutations import process_mutation_message

            assistant.content, assistant.metadata_json, completion = await process_mutation_message(
                ctx, db, chat_session, user_message
            )
            assistant.provider_id, assistant.model_name = chat_session.provider_id, completion.model
            assistant.input_tokens = completion.usage.get("input_tokens")
            assistant.output_tokens = completion.usage.get("output_tokens")
            assistant.latency_ms = completion.latency_ms
        assistant.status, assistant.trace_id, assistant.error = "completed", trace_id, None
    except Exception as exc:
        db.rollback()
        assistant = db.get(ChatMessage, uuid.UUID(assistant_message_id))
        if assistant is None:
            return
        assistant.status = "failed"
        assistant.trace_id = trace_id
        assistant.error = {"code": "provider_or_processing_error", "message": str(exc)[:2000]}
    assistant.updated_at = datetime.now(UTC)
    db.commit()
