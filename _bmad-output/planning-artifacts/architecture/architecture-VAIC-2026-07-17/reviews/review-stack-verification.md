# Stack Verification Review — VAIC Architecture Spine

**Reviewer Lens:** Reality-check every committed technology decision against current web sources (2026-07-17).
**Spine Reviewed:** `ARCHITECTURE-SPINE.md` (draft, 2026-07-17)
**Review Date:** 2026-07-17

---

## Verdict: PASS-WITH-WARNINGS

The spine's technology choices are architecturally sound and all named technologies exist, are maintained, and fill the roles assigned. However, **five version pins are stale** relative to the current stable releases as of 2026-07-17. None of these are blocking, but the spine should update the version column to reflect reality so builders do not pin outdated versions and then discover incompatibilities.

---

## Per-Technology Verification Table

| # | Technology | Spine Claims | Verified Current (2026-07-17) | Status | Notes |
|---|---|---|---|---|---|
| 1 | Python | 3.12 | 3.14.6 (latest stable); 3.12 is security-only | WARNING | 3.12 works but is in security-only support. 3.13 or 3.14 are the boring choices for a greenfield project in 2026. |
| 2 | FastAPI | 0.139.x | 0.139.2 (2026-07-16) | OK | Exact match. The current stable is within the claimed range. |
| 3 | SQLAlchemy | 2.x | 2.0.51 (2026-06-15) | OK | 2.x range is correct. 2.1 is in beta (2.1.0b3). |
| 4 | Pydantic | 2.x | 2.13.4 (2026-05-06) | OK | 2.x range is correct and current. |
| 5 | Alembic | latest | 1.18.5 (2026-06-25) | OK | "latest" resolves correctly. Note: min Python is now 3.10. |
| 6 | PostgreSQL | 16 | 18.4 (latest stable); 16.14 (latest patch on 16) | WARNING | PG 16 is still supported but is two major versions behind. PG 18 is the boring choice for greenfield in 2026. RLS works identically on both. |
| 7 | pgvector | 0.7+ | 0.8.1 (latest) | WARNING | Spine says "0.7+" which technically covers 0.8.1, but 0.7 is no longer the current version. Should read "0.8+" or just "latest". |
| 8 | Redis | 7 | 8.8.0 (latest stable); 7.4.6 (latest 7.x) | WARNING | Redis 7.2 reached EOL 2026-02-28. Redis 7.4.x still supported. Redis 8.8 is the current stable major. For an arq broker, 7.4 is fine, but the spine should specify "7.4+" not bare "7" since 7.2 is dead. |
| 9 | arq | 0.26+ | 0.28.0 (2026-04-16) | WARNING | "0.26+" covers 0.28.0 via semver range, but the current stable is 0.28.0. Spine should say "0.28+" to avoid pinning an older version. `cron_jobs` feature is confirmed real and documented. |
| 10 | `mcp` (Python SDK) | v1.x; v2.0.0 due 2026-07-28 | v1.x stable confirmed; v2 in alpha targeting 2026-07-28 spec | OK | The spine's claim is precisely accurate. The MCP Python SDK repo confirms v2 is a major rework supporting the 2026-07-28 spec release. v1.x is the right choice for the hackathon. |
| 11 | `anthropic` | 0.114.0 | 0.114.0 (released ~2026-07-16) | OK | Exact match. Released ~1 day before the spine was written. |
| 12 | `openai` | latest | 2.45.0 (2026-07-09) | OK | "latest" resolves correctly. |
| 13 | `google-genai` | latest | 2.11.0 (2026-07-09) | OK | "latest" resolves correctly. Package name confirmed correct (replaces old `google-generativeai`). |
| 14 | React | 19 | 19.2.7 (latest 19.x) | OK | React 19 is the current stable major line. |
| 15 | Vite | 7 | 8.1.x (current stable major) | WARNING | Vite 7 was released June 2025. Vite 8.0 shipped March 2026 and is the current stable. Vite 7 is one major version behind. Vitest 4.1 already supports Vite 8. |
| 16 | TypeScript | 5.6+ | 7.0.2 (current stable on npm) | WARNING | TypeScript has jumped to 7.0.x. The "5.6+" claim is significantly outdated. TS 5.6 shipped September 2024 — nearly two years ago. The current boring choice is TS 7.x. |
| 17 | Tailwind CSS | 4 | 4.3.2 (2026-06-29) | OK | Tailwind 4 is the current major and 4.3.2 is the latest patch. |
| 18 | TanStack Query | latest | 5.101.2 (2026-06-27) | OK | "latest" resolves correctly. |
| 19 | Vitest | latest | 4.1.10 (2026-06) | OK | "latest" resolves correctly. |
| 20 | Playwright | latest | 1.61 (2026) | OK | "latest" resolves correctly. |

---

## Key Capability Verifications

### MCP Python SDK v1.x stable / v2 due 2026-07-28 — CONFIRMED

The spine states: "`mcp` (Python SDK) | v1.x | MCP client (v2.0.0 due 2026-07-28 — stick to v1)"

**Verified:** The [GitHub repository for modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) confirms that v2 is a major rework designed to support the 2026-07-28 MCP specification release. v2 is currently in alpha. The v1.x line is the stable release on PyPI. The spine's guidance to "stick to v1" for a hackathon happening before 2026-07-28 is correct and prudent.

### arq supports `cron_jobs` — CONFIRMED

The spine's AD-9 and Consistency Conventions depend on arq's `cron_jobs` for Schedule Triggers (FR-18), claiming "arq only — both Schedule Triggers (via `cron_jobs`) and background Workflow Run execution."

**Verified:** The [arq v0.28.0 documentation](https://arq-docs.helpmanual.io/) has a dedicated "Cron Jobs" section. The `cron_jobs` parameter accepts a list of `CronJob` instances in `WorkerSettings`. Workers enqueue the job at or just after the scheduled times. The `CronJob` class supports month/day/hour/minute/second fields, a `unique` parameter, `timeout`, and `max_tries`. This is a real, documented, production feature.

### pgvector on PostgreSQL 16 — SOUND (if needed at all)

The spine defers pgvector: "Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise."

**Verified:** [pgvector 0.8.1](https://github.com/pgvector/pgvector) is the current version and supports PostgreSQL 13-18. The spine's "0.7+" minimum is technically satisfied. The conditional inclusion ("skip otherwise") is the right call — no action needed unless FR-2 reconciliation goes VAIC-side.

### PostgreSQL RLS — REAL AND SOUND

The spine's AD-2 depends entirely on PostgreSQL Row-Level Security for multi-tenant isolation.

**Verified:** PostgreSQL RLS is a mature, production-grade feature available since PostgreSQL 9.5. The pattern the spine describes (`tenant_id = current_setting('app.tenant_id')` with FastAPI middleware setting the session variable) is the canonical multi-tenant RLS pattern, documented by [AWS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/), [Crunchy Data](https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres), and many production SaaS applications. The spine's reliance on it is architecturally sound. The `BYPASSRLS` escape hatch for migrations is the correct pattern.

### React+Vite+TypeScript starter defaults — PARTIALLY OUT OF DATE

The spine implies the "boring choice" React SPA starter is React 19 + Vite 7 + TypeScript 5.6+.

**Verified current boring choice (2026-07-17):** React 19 + **Vite 8** + **TypeScript 7**. Vite 7 shipped June 2025 and has been superseded by Vite 8 (March 2026). TypeScript 5.6 shipped September 2024 and the language has since moved through 5.7, 5.8, and jumped to 7.0.x. The spine's versions are one-to-two major versions behind for two of three components.

---

## Specific Corrections Needed

### Correction 1: TypeScript version is stale

**Spine text (line 225):**
```
| TypeScript | 5.6+ | Type safety |
```

**Should read:**
```
| TypeScript | 7.x | Type safety |
```

**Reason:** TypeScript 7.0.2 is the current stable on npm (published ~July 9, 2026). TS 5.6 was released September 2024 — nearly two years ago. The "5.6+" range misleadingly suggests anything in the 5.x line is current when the language has moved to 7.x.

### Correction 2: Vite version is one major behind

**Spine text (line 224):**
```
| Vite | 7 | Bundler/dev server |
```

**Should read:**
```
| Vite | 8 | Bundler/dev server |
```

**Reason:** Vite 8.0 was released March 2026; Vite 8.1.x is the current stable. Vite 7 shipped June 2025. Vitest 4.1 already targets Vite 8. New projects should start on Vite 8.

### Correction 3: Python version is in security-only support

**Spine text (line 210):**
```
| Python | 3.12 | Backend language |
```

**Should read:**
```
| Python | 3.13 | Backend language |
```

**Reason:** Python 3.12 entered security-only support (no bug fixes). Python 3.13 is in active bugfix support and has the best library compatibility for greenfield projects in 2026. Python 3.14 is also stable but some libraries may still be catching up. 3.13 is the conservative boring choice.

### Correction 4: PostgreSQL should target 18 for greenfield

**Spine text (line 215):**
```
| PostgreSQL | 16 | Primary DB, RLS |
```

**Should read:**
```
| PostgreSQL | 18 | Primary DB, RLS |
```

**Reason:** PostgreSQL 18.4 is the current stable. PG 16 is still supported but two major versions behind. For a greenfield build with no legacy constraints, PG 18 is the boring choice. RLS behavior is identical. All named dependencies (pgvector, SQLAlchemy, Alembic) support PG 18.

### Correction 5: arq minimum version should be 0.28+

**Spine text (line 218):**
```
| arq | 0.26+ | Async jobs + cron |
```

**Should read:**
```
| arq | 0.28+ | Async jobs + cron |
```

**Reason:** arq 0.28.0 (April 2026) is the current stable. While "0.26+" technically includes 0.28.0 via semver, a builder might pin 0.26.x and encounter bugs fixed in 0.28. The minimum should reflect the version the architecture was verified against.

### Correction 6: Redis version should be more specific

**Spine text (line 217):**
```
| Redis | 7 | arq broker only |
```

**Should read:**
```
| Redis | 7.4+ | arq broker only |
```

**Reason:** Redis 7.2 reached EOL on 2026-02-28. Bare "7" is ambiguous — a builder might use 7.0 or 7.2. The minimum supported version in the 7.x line is 7.4.x. Alternatively, Redis 8.8 is the current stable major.

### Correction 7: pgvector minimum version

**Spine text (line 216):**
```
| pgvector | 0.7+ | Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise |
```

**Should read:**
```
| pgvector | 0.8+ | Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise |
```

**Reason:** pgvector 0.8.1 is the current version. 0.7.x is outdated. If included at all, the minimum should be 0.8+.

---

## Technologies That Should Be Removed or Replaced

None. Every technology in the spine is real, maintained, and fills its assigned role correctly. No technology needs replacement. The issue is purely stale version pins.

---

## Assertions Without Evidence (Flagged)

1. **`wasmtime-py` as production sandbox replacement (line 199):** The spine mentions `wasmtime-py` as a future production sandbox upgrade. This was not web-verified in the spine and the package's current status was not confirmed in this review either. It is deferred, so it is not blocking, but builders should verify `wasmtime-py` exists and supports the use case before relying on the note.

2. **"E2B" as alternative sandbox (line 199):** E2B (e2b.dev) is a cloud sandbox service. Not verified in this review. Same status as wasmtime-py — deferred, not blocking.

3. **TanStack Router or React Router (line 291):** The spine mentions "TanStack Router or React Router" for file-based routing without committing to one. TanStack Router is real and maintained (part of the TanStack ecosystem). React Router v7 is also current. This ambiguity is a design decision, not a factual error, but the spine should note which is the default to prevent builder divergence.

---

## Sources

- [FastAPI Release Notes](https://fastapi.tiangolo.com/release-notes/) — FastAPI 0.139.2 (2026-07-16)
- [Python.org Downloads](https://www.python.org/downloads/) — Python 3.14.6 latest, 3.12 in security-only
- [Vite Releases](https://vite.dev/releases) — Vite 8.1.x current stable; [Vite 8 Announcement](https://vite.dev/blog/announcing-vite8)
- [TypeScript on npm](https://www.npmjs.com/package/typescript) — TypeScript 7.0.2 current
- [React Versions](https://react.dev/versions) — React 19.2.7 current
- [MCP Python SDK — GitHub](https://github.com/modelcontextprotocol/python-sdk) — v1.x stable, v2 alpha targeting 2026-07-28 spec
- [MCP 2026-07-28 Release Candidate Blog](https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/)
- [arq v0.28.0 Documentation](https://arq-docs.helpmanual.io/) — cron_jobs feature confirmed
- [arq on PyPI](https://pypi.org/project/arq/) — 0.28.0 (2026-04-16)
- [PostgreSQL Release Notes](https://www.postgresql.org/docs/release/) — PG 18.4 latest stable, 16.14 still supported
- [pgvector on GitHub](https://github.com/pgvector/pgvector) — 0.8.1 latest, supports PG 13-18
- [Redis Docs — Release Notes](https://redis.io/docs/latest/operate/rs/release-notes/) — Redis 8.8.0 current; 7.2 EOL 2026-02-28
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/) — 2.0.51 stable, 2.1 in beta
- [Pydantic on PyPI](https://pypi.org/project/pydantic/) — 2.13.4 (2026-05-06)
- [Alembic Documentation](https://alembic.sqlalchemy.org/) — 1.18.5 (2026-06-25)
- [Anthropic Python SDK on PyPI](https://pypi.org/project/anthropic/) — 0.114.0 confirmed
- [OpenAI Python SDK — GitHub](https://github.com/openai/openai-python) — 2.45.0 (2026-07-09)
- [google-genai on PyPI](https://pypi.org/project/google-genai/) — 2.11.0 (2026-07-09)
- [Tailwind CSS v4 Blog](https://tailwindcss.com/blog/tailwindcss-v4) — v4 stable since Jan 2025; 4.3.2 current
- [TanStack Query — GitHub Releases](https://github.com/tanstack/query/releases) — 5.101.2 latest
- [Vitest 4.1 Blog](https://vitest.dev/blog/vitest-4-1.html) — 4.1.10 current, supports Vite 8
- [Playwright Release Notes](https://playwright.dev/docs/release-notes) — v1.61 latest
- [AWS — Multi-tenant Data Isolation with PostgreSQL RLS](https://aws.amazon.com/blogs/database/multi-tenant-data-isolation-with-postgresql-row-level-security/)
- [Crunchy Data — Row Level Security for Tenants](https://www.crunchydata.com/blog/row-level-security-for-tenants-in-postgres)
