# Key Capability Verifications

## MCP Python SDK v1.x stable / v2 due 2026-07-28 — CONFIRMED

The spine states: "`mcp` (Python SDK) | v1.x | MCP client (v2.0.0 due 2026-07-28 — stick to v1)"

**Verified:** The [GitHub repository for modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) confirms that v2 is a major rework designed to support the 2026-07-28 MCP specification release. v2 is currently in alpha. The v1.x line is the stable release on PyPI. The spine's guidance to "stick to v1" for a hackathon happening before 2026-07-28 is correct and prudent.

## arq supports `cron_jobs` — CONFIRMED

The spine's AD-9 and Consistency Conventions depend on arq's `cron_jobs` for Schedule Triggers (FR-18), claiming "arq only — both Schedule Triggers (via `cron_jobs`) and background Workflow Run execution."

**Verified:** The [arq v0.28.0 documentation](https://arq-docs.helpmanual.io/) has a dedicated "Cron Jobs" section. The `cron_jobs` parameter accepts a list of `CronJob` instances in `WorkerSettings`. Workers enqueue the job at or just after the scheduled times. The `CronJob` class supports month/day/hour/minute/second fields, a `unique` parameter, `timeout`, and `max_tries`. This is a real, documented, production feature.

## pgvector on PostgreSQL 16 — SOUND (if needed at all)

The spine defers pgvector: "Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise."

**Verified:** [pgvector 0.8.1](https://github.com/pgvector/pgvector) is the current version and supports PostgreSQL 13-18. The spine's "0.7+" minimum is technically satisfied. The conditional inclusion ("skip otherwise") is the right call — no action needed unless FR-2 reconciliation goes VAIC-side.

## PostgreSQL RLS — REAL AND SOUND

The spine's AD-2 depends entirely on PostgreSQL Row-Level Security for multi-tenant isolation.

**Verified:** PostgreSQL RLS is a mature, production-grade feature available since PostgreSQL 9.5. The pattern the spine describes (`tenant_id = current_setting('app.tenant_id')` with FastAPI middleware setting the session variable) is the canonical multi-tenant RLS pattern, documented by [AWS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/), [Crunchy Data](https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres), and many production SaaS applications. The spine's reliance on it is architecturally sound. The `BYPASSRLS` escape hatch for migrations is the correct pattern.

## React+Vite+TypeScript starter defaults — PARTIALLY OUT OF DATE

The spine implies the "boring choice" React SPA starter is React 19 + Vite 7 + TypeScript 5.6+.

**Verified current boring choice (2026-07-17):** React 19 + **Vite 8** + **TypeScript 7**. Vite 7 shipped June 2025 and has been superseded by Vite 8 (March 2026). TypeScript 5.6 shipped September 2024 and the language has since moved through 5.7, 5.8, and jumped to 7.0.x. The spine's versions are one-to-two major versions behind for two of three components.

---
