# Per-Technology Verification Table

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
