"""Notification module — persisted, per-user staff alerts (Actions/Events pairing).

Tenant-scoped via RLS (app.tenant_id GUC); each row also carries `user_id` (the
recipient). Delivery is frontend polling of `GET /notifications` (no SSE/websocket).
"""
