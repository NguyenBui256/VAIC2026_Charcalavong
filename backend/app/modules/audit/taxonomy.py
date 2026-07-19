"""Versioned Audit V2 event taxonomy."""

from __future__ import annotations

EVENT_TYPES = frozenset(
    f"{domain}.{event}"
    for domain, events in {
        "session": ("created", "started", "completed", "failed", "timed_out", "cancelled"),
        "orchestrator": ("planning_started", "decomposed", "aggregated", "decision_recorded"),
        "task": ("created", "routed", "claimed", "completed", "failed", "retried", "dropped"),
        "agent": ("started", "feedback_emitted", "completed", "failed"),
        "llm": ("started", "first_token", "completed", "failed"),
        "tool": ("requested", "validated", "completed", "failed"),
        "kb": ("query_started", "retrieved", "cited", "access_rejected"),
        "escalation": ("created", "viewed", "resolved", "timed_out"),
        "mini_app": ("schema_emitted", "validated", "provisioned", "failed"),
        "app_event": ("emitted", "delivered", "matched", "gap_detected"),
        "evaluation": ("started", "completed", "failed"),
        "audit": ("exported", "redacted", "integrity_failed"),
    }.items()
    for event in events
)

TERMINAL_SUFFIXES = (".completed", ".failed", ".timed_out", ".cancelled")
SCHEMA_VERSION = 2


def validate_event_type(event_type: str) -> str:
    if event_type not in EVENT_TYPES:
        raise ValueError(f"Unknown Audit V2 event type: {event_type}")
    return event_type
