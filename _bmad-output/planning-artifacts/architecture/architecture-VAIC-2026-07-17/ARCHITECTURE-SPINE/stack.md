# Stack

Web-verified 2026-07-17. Pin these in `pyproject.toml` and `package.json`; the code owns upgrades once it exists.

| Name | Version | Role |
| --- | --- | --- |
| Python | 3.13 | Backend language (3.12 is security-only; 3.13 is the 2026 boring choice) |
| FastAPI | 0.139.x | HTTP API |
| SQLAlchemy | 2.x | ORM (sync; async adds complexity not needed for MVP) |
| Pydantic | 2.x | Validation, schemas |
| Alembic | latest | Migrations |
| PostgreSQL | 18 | Primary DB, RLS (RLS behavior identical to 16; 18 is current stable) |
| pgvector | 0.7+ | Only if FR-2 reconciliation yields VAIC-side retrieval; skip otherwise |
| Redis | 7.4+ | arq broker only (7.2 reached EOL 2026-02-28) |
| arq | 0.26+ | Async jobs + cron |
| `mcp` (Python SDK) | v1.x | MCP client (v2.0.0 due 2026-07-28 — stick to v1) |
| `anthropic` | 0.114.0 | Claude adapter |
| `openai` | latest | OpenAI adapter |
| `google-genai` | latest | Gemini adapter (optional — only if team brings Google keys) |
| React | 19 | SPA |
| Vite | 8 | Bundler/dev server |
| TypeScript | 7.x | Type safety |
| Tailwind CSS | 4 | Styling |
| TanStack Query | latest | Server state (SPA convention) |
| Vitest | latest | Unit tests |
| Playwright | latest | E2E for UJ-1 and UJ-2 |
