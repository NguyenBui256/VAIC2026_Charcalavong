# A5. App Event Envelope (referenced by FR-17, FR-19)

```json
{
  "event_id": "uuid",
  "app_id": "uuid",
  "tenant_id": "uuid",
  "department_id": "uuid",
  "actor_user_id": "uuid | null",
  "sequence_no": 42,
  "event_type": "row.created | row.updated | row.deleted",
  "payload": { /* event-specific */ },
  "ts": "2026-07-17T08:34:12.123Z"
}
```

Event Triggers filter on `(app_id, event_type, optional JSON-path predicate on payload)`.
