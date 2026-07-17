# 13. Assumptions Index

Every `[ASSUMPTION]` from the document, surfaced for explicit confirmation:

- **§2.1 / §2.3** — At least one LLM provider available at demo time.
- **§2.3 (UJ-2)** — Judge availability and demo format (booth vs. stage).
- **§3 (User)** — v1 roles are light: builder + manager + operator. Full RBAC deferred.
- **§4.1 / FR-2** — Document upload ceiling 20 MB.
- **§4.1 / FR-3** — Tool execution sandbox tech chosen by Architecture; 10-second execution budget.
- **§4.1 / FR-4** — For MVP, API Integrations point at stubbed endpoints (no live OAuth).
- **§4.2 / FR-9** — Retry policy: 2 retries with exponential backoff; per-Agent timeout 60 s.
- **§4.2 / FR-9** — For MVP, no streaming partial results during a Run.
- **§4.2 / FR-10** — Unresolved escalation timeout: 5 minutes.
- **§4.4 / FR-18** — Scheduler resolution: 60 s.
- **§4.5 / FR-22 / FR-23** — Demo hardware is a single laptop; graph-size ceiling 10 Specialist Agent invocations.
- **§4.5 / FR-24** — Audit signing key management deferred to Architecture.
- **§4.6 / FR-28** — Team pre-configures ≥ 3 Agents and 1 Workflow before demo day.
- **§6.1** — Same as FR-28: ≥ 3 pre-configured Agents.
- **§8.1** — Demo data is synthetic; no real customer PII.
- **§8.2** — Per-Run token ceiling placeholder: 50,000 tokens.
- **§8.4** — Demo concurrency target: ≥ 5 simultaneous Runs.
- **§8.4** — Run state persisted to PostgreSQL.
- **§9** — Team supplies at least one working provider key.
- **§9** — Architecture picks the embedding model.
- **§9** — Team supplies 3–5 sample SHB-relevant policy documents.
- **§11** — Team size 3–5; mentor identity to confirm.

---

*Draft v1 — Fast path. `[ASSUMPTION]` tags and Open Questions surfaced for Nguyen's review. Next step: Nguyen confirms/overrides assumptions, then we walk Finalize (memlog audit, reconcile against brief + problem statement, optional reviewer gate, triage open items, polish, close).*

---
