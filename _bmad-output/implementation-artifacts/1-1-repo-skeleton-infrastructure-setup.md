---
baseline_commit: 36a28cdd3ba60d7a96fe2ed29d321650bb274fe3
---

# Story 1.1: Repo Skeleton & Infrastructure Setup

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **developer**,
I want **a clean monorepo skeleton with Postgres and Redis running via docker-compose**,
so that **I can start backend and frontend work without spending time on environment setup**.

## Acceptance Criteria

1. **AC1 — Docker Compose brings up infra**: Given a clean clone on a dev machine with Docker installed, When the developer runs `docker-compose up`, Then Postgres 18 and Redis 7.4+ containers start and pass healthchecks. *(Verification: docker-compose.yml syntax validated; runtime `docker compose up` requires Docker Desktop running — manual gate.)*
2. **AC2 — Backend skeleton pinned to AR-13 stack**: `backend/` contains `app/main.py`, `pyproject.toml` pinned to AR-13 stack (Python 3.13, FastAPI 0.139.x, SQLAlchemy 2.x, Pydantic 2.x, Alembic, arq 0.26+, mcp v1.x, anthropic 0.114.0). ✅
3. **AC3 — Frontend skeleton pinned to AR-13 stack**: `frontend/` contains a Vite 8 + React 19 + TypeScript 7.x + Tailwind CSS 4 setup with `package.json` and `vite.config.ts`. ✅
4. **AC4 — Container port mapping with persistent volumes**: `infra/docker-compose.yml` exposes Postgres on `:5432` and Redis on `:6379` with persistent volumes. ✅ (compose syntax validated)
5. **AC5 — Backend health endpoint**: `GET /health` on the FastAPI backend returns `200` with `{"status": "ok"}`. ✅ Verified via `tests/integration/test_health.py` and live uvicorn boot.
6. **AC6 — Frontend dev server boots**: `npm run dev` on the frontend starts Vite dev server on `:5173` without errors. ✅ Verified Vite 8.1.5 boots in 9.5s, HTTP 200 on `:5173`.
7. **AC7 — Directory structure matches AR-1**: Directory structure matches AR-1 structural seed (`backend/app/{modules,core,bootstrap}`, `backend/tests/{unit,integration,e2e}`, `frontend/src/{routes,components,hooks,lib}`, `infra/`, `docs/`). ✅

## Tasks / Subtasks

- [x] **T1 — Repo root layout** (AC: #7)
  - [x] T1.1 Create `vaic/` monorepo root (this repo is the root; create subdirs only — do NOT nest under `vaic/`)
  - [x] T1.2 `docs/` already exists (contains source PDF + screenshot). No `.gitkeep` needed.
  - [x] T1.3 Create root `README.md` with one-paragraph project blurb and clone→run instructions (cross-ref AC1, AC5, AC6)
  - [x] T1.4 Existing `.gitignore` already covers Python venv, `__pycache__`, `node_modules`, `dist`, `.env*`, `.venv/`, IDE folders, `*.log`. No changes.
  - [x] T1.5 Create root `.env.example` listing every var Stories 1.2+ will need (DATABASE_URL, REDIS_URL, JWT_SECRET, ANTHROPIC_API_KEY, etc.) — empty values, no real secrets
- [x] **T2 — `infra/docker-compose.yml`** (AC: #1, #4)
  - [x] T2.1 Create `infra/docker-compose.yml`
  - [x] T2.2 Add `postgres:18` service: port `5432:5432`, env vars `POSTGRES_USER/PASSWORD/DB` sourced from `.env`, persistent named volume `pgdata`, `healthcheck` using `pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB` with 5s interval / 10 retries
  - [x] T2.3 Add `redis:7.4` service: port `6379:6379`, persistent named volume `redisdata`, `healthcheck` using `redis-cli ping` with 5s interval / 10 retries
  - [x] T2.4 Verified `docker compose config` parses cleanly. Runtime `up` requires Docker Desktop running — manual gate.
- [x] **T3 — Backend `pyproject.toml` pinned to AR-13** (AC: #2)
  - [x] T3.1 Create `backend/pyproject.toml` using PEP 621 `[project]` table; `requires-python = ">=3.13,<3.14"`
  - [x] T3.2 Pin runtime deps per AR-13. **Deviation:** used `psycopg[binary]>=3.2` (psycopg3) instead of `asyncpg` because architecture spine mandates sync SQLAlchemy. `asyncpg` is not used; Story 1.2 can add if it diverges.
  - [x] T3.3 Pin dev/test deps in `[project.optional-dependencies.dev]`: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`, `types-passlib`
  - [x] T3.4 Add `[tool.ruff]` config: line-length 100, target Python 3.13
  - [x] T3.5 Add `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `asyncio_mode = "auto"`
- [x] **T4 — Backend `app/` skeleton per AR-1** (AC: #2, #7)
  - [x] T4.1 Create the EXACT directory tree from `structural-seed.md` — every `__init__.py` is a package marker
  - [x] T4.2 `backend/app/main.py`: FastAPI app instance, `GET /health` returning `{"status": "ok"}` with HTTP 200, no DB dependency
  - [x] T4.3 Six empty module packages with `__init__.py`: `tenant/`, `agent_builder/`, `orchestrator/`, `mini_app/`, `actions/`, `audit/`
  - [x] T4.4 Empty placeholder files per structural-seed.md in each module
  - [x] T4.5 `app/core/` with empty packages: `ports/`, `adapters/`, plus placeholder `tenant_context.py` and `errors.py`
  - [x] T4.6 `app/bootstrap/` with empty `__init__.py`
  - [x] T4.7 `backend/alembic.ini` stub — migrations start in Story 1.2
- [x] **T5 — Backend tests skeleton** (AC: #7)
  - [x] T5.1 Create `backend/tests/{unit,integration,e2e}/` with `__init__.py` in each
  - [x] T5.2 `backend/tests/integration/test_health.py` — tests `GET /health` returns 200 + `{"status": "ok"}` via `fastapi.testclient.TestClient`
  - [x] T5.3 `uv run pytest` PASSES (1 passed in 0.76s)
- [x] **T6 — Frontend skeleton pinned to AR-13** (AC: #3, #6, #7)
  - [x] T6.1 `frontend/package.json` pins Vite `^8`, React `^19`, TypeScript `^7`, Tailwind `^4`, TanStack Query `^5`
  - [x] T6.2 Tailwind CSS 4 via `@tailwindcss/vite` plugin (no `tailwind.config.js` — v4 is CSS-first)
  - [x] T6.3 TanStack Query installed and wired in `main.tsx` (`QueryClientProvider` wrapping `App`)
  - [x] T6.4 `frontend/vite.config.ts`: `server.port = 5173`, `server.host = true`, plugins `[react(), tailwindcss()]`
  - [x] T6.5 Route directories per structural-seed.md: `agent-builder/`, `orchestrator/`, `actions/`, `mini-apps.$appId/`, `trace.$runId/` — `.gitkeep`'d
  - [x] T6.6 `src/{components,hooks,lib}/` packages with `.gitkeep`
  - [x] T6.7 Minimal `App.tsx` ("VAIC skeleton ready"); default Vite cruft removed
  - [x] T6.8 `npm run dev` boots Vite 8.1.5 in 9.5s on `:5173` with HTTP 200; `npx tsc --noEmit` clean
- [x] **T7 — Verify clone-to-run loop end-to-end** (AC: #1, #4, #5, #6)
  - [x] T7.1 `README.md` documents the exact command sequence
  - [x] T7.2 Smoke-tested: pytest green, uvicorn boots, /health → 200, Vite boots → 200. Docker runtime deferred (Docker Desktop not running locally).
- [x] **T8 — Definition of Done evidence** (AC: all)
  - [x] T8.1 Test evidence: `tests/integration/test_health.py:14` PASSED (pytest output captured above)
  - [x] T8.2 Production code reference: `backend/app/main.py:21-26` (`/health` handler), `infra/docker-compose.yml:1-44`
  - [x] T8.3 All ACs checked off above

## Dev Notes

### Scope Boundaries — CRITICAL

**Story 1.1 is SKELETON ONLY.** Do NOT implement:
- DB connection wiring, SQLAlchemy engine/session factory, RLS policies → **Story 1.2**
- Auth middleware, JWT issuance, `tenant_context.ContextVar` population → **Story 1.3**
- Port interfaces (`LlmPort`, `AuditPort`, etc.) — only empty `__init__.py` in `core/ports/` → **Story 1.4**
- Alembic migrations — only `alembic.ini` stub → **Story 1.2**
- Design tokens / Tailwind config content — only empty `tokens.css` placeholder → **Story 1.8**
- Domain logic of ANY kind

The dev agent owns end-to-end correctness: even if not in ACs, if `npm run dev` produces console errors or `GET /health` requires a DB round-trip, that's a Story 1.1 bug.

### Architecture Compliance (AD-1 → AR-15)

**AD-1 — Hexagonal Modular Monolith**: Skeleton must instantiate the six bounded modules as Python packages (`tenant`, `agent_builder`, `orchestrator`, `mini_app`, `actions`, `audit`) under `app/modules/`. Even though empty, their existence signals downstream devs where to put code. [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-1, epics.md L154]

**AR-1 — Structural Seed**: The directory tree is contractually fixed — Stories 1.2–1.12 and Epics 2–7 import from these exact paths. Deviate and downstream stories break silently. Cross-check final tree against `architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/structural-seed.md`. [Source: ARCHITECTURE-SPINE/structural-seed.md, epics.md L113–L152]

**AR-13 — Pinned Stack**: Use EXACTLY these versions. Do not "round up" or accept a newer major.
- Python 3.13 (3.12 is security-only — rejected)
- FastAPI 0.139.x (not 0.140)
- SQLAlchemy 2.x (sync only — async adds complexity not needed for MVP)
- Pydantic 2.x
- PostgreSQL 18 (RLS behavior identical to 16; 18 is current stable)
- Redis 7.4+ (7.2 reached EOL 2026-02-28 — must be ≥7.4)
- arq 0.26+
- `mcp` Python SDK **v1.x — NOT v2.0.0** (v2.0.0 due 2026-07-28; stay on v1 per stack.md)
- `anthropic` 0.114.0 (exact pin)
- React 19, Vite 8, TypeScript 7.x, Tailwind CSS 4, TanStack Query
[Source: ARCHITECTURE-SPINE/stack.md, epics.md L179–L181]

**AR-14 — Consistency Conventions applicable to skeleton**:
- File naming: Python `snake_case`; routes `kebab-case`; React components `PascalCase`; CSS `kebab-case`. The structural seed already follows this — preserve.
- Function size ceiling 50 lines (no domain code yet, but keep `main.py` minimal).
- No premature abstraction: do NOT introduce ports/adapters/stubs in Story 1.1 — Stories 1.4 and 1.6 own that.
- Error shape and API envelope: not yet relevant (no domain endpoints), but the skeleton's `core/errors.py` placeholder exists so Story 1.4 has a home.
[Source: ARCHITECTURE-SPINE/consistency-conventions.md]

**AR-5 / AD-4 — Audit sink**: Not implemented in Story 1.1. The `audit/sink.py` placeholder file's existence is required so downstream stories have a target path. [Source: ARCHITECTURE-SPINE/invariants-rules.md#AD-4]

### Library/Framework Requirements

- **Python**: Use `uv` (preferred) or `pip` + `venv` for env management. `uv sync` should work after cloning.
- **Backend dev server**: `uvicorn[standard]` with `--reload` for dev. The `main.py` must expose `app` at module level (`uvicorn app.main:app`).
- **Frontend**: `npm` is the documented package manager (AC6 references `npm run dev`). Do not switch to pnpm/yarn without updating AC6.
- **Docker Compose**: Use `docker-compose` v2 syntax (the `compose` subcommand of Docker CLI is also acceptable). Volume names must be explicit (`pgdata`, `redisdata`) — anonymous volumes break persistent AC.

### File Structure Requirements

Reproduce this EXACT tree (files marked "empty" still must exist as touchpoints for downstream stories):

```
/
├── README.md
├── .gitignore
├── .env.example
├── docs/
│   └── .gitkeep
├── infra/
│   └── docker-compose.yml
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini                      # stub; migrations start in Story 1.2
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI app + GET /health
│   │   ├── modules/
│   │   │   ├── __init__.py
│   │   │   ├── tenant/{__init__.py, routes.py, service.py, models.py}      # empty
│   │   │   ├── agent_builder/{__init__.py, routes.py, service.py, models.py}
│   │   │   ├── orchestrator/{__init__.py, routes.py, service.py, models.py}
│   │   │   ├── mini_app/{__init__.py, routes.py, service.py, models.py, provisioner.py, ui_renderer.py}
│   │   │   ├── actions/{__init__.py, routes.py, bus.py, triggers.py}
│   │   │   └── audit/{__init__.py, routes.py, sink.py}
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── ports/__init__.py        # empty
│   │   │   ├── adapters/__init__.py     # empty
│   │   │   ├── tenant_context.py        # empty
│   │   │   └── errors.py                # empty
│   │   └── bootstrap/__init__.py        # empty
│   └── tests/
│       ├── __init__.py
│       ├── unit/{__init__.py, .gitkeep}
│       ├── integration/{__init__.py, test_health.py}
│       └── e2e/{__init__.py, .gitkeep}
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tsconfig.json
    ├── index.html
    └── src/
        ├── main.tsx
        ├── App.tsx                      # minimal "VAIC skeleton ready"
        ├── styles/tokens.css            # empty placeholder
        ├── routes/
        │   ├── agent-builder/.gitkeep
        │   ├── orchestrator/.gitkeep
        │   ├── mini-apps.$appId/.gitkeep
        │   ├── trace.$runId/.gitkeep
        │   └── actions/.gitkeep
        ├── components/.gitkeep
        ├── hooks/.gitkeep
        └── lib/.gitkeep
```

### Testing Requirements

- **Coverage target**: not enforced in Story 1.1 (skeleton has near-zero surface area), but the health endpoint test is mandatory — it proves the FastAPI app boots and AC5 holds.
- **Test framework**: `pytest` + `httpx` (per AR-13 and consistency-conventions.md). Use `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))` pattern.
- **Frontend tests**: Vitest is configured (per AR-13) but no test file is required for Story 1.1 (no components to test). The placeholder `src/App.tsx` doesn't need a test.
- **Definition of Done** (AR-14): PR must include test evidence (`file:line` + green run output) AND production code reference (`file:line`).

### Anti-Patterns to Avoid

1. **Don't add a DB session dependency to `GET /health`.** Health check is liveness, not readiness. If `/health` requires DB, container orchestrators will kill the backend during Postgres restarts. Story 1.2 can add `/ready` for DB-readiness.
2. **Don't initialize Alembic with a migration.** `alembic init` creates a migration environment; Story 1.2 owns the first migration (`create_tenants_users_departments`). Story 1.1 only ships `alembic.ini` so downstream stories can run `alembic upgrade head`.
3. **Don't add `python-jose` JWT logic.** Auth is Story 1.3. Including `python-jose` in deps is fine (forward prep); importing it is not.
4. **Don't run `npm create vite` and ship the default Vite template.** Replace `App.tsx` cruft (Vite logo, Counter component, CSS) with a minimal "VAIC skeleton ready" message. The template's default `index.css` is acceptable to keep; do not delete it (Vite needs the entry).
5. **Don't commit `.env` (only `.env.example`).** NFR-6 forbids hard-coded secrets; `.env` belongs in `.gitignore`.
6. **Don't add any code under `modules/`, `core/ports/`, or `core/adapters/` beyond empty files.** Downstream stories populate these. Adding code now risks conflicts with parallel streams.

### Project Structure Notes

- The architecture's `structural-seed.md` shows `vaic/backend/...` — that `vaic/` is the conceptual repo root. **This repo IS the root.** Do NOT create a nested `vaic/` directory; `backend/`, `frontend/`, `infra/`, `docs/` live at repo root.
- The repo currently contains `_bmad/` and `_bmad-output/` (planning artifacts) at root level. These are NOT in the structural seed — they're meta-directories for BMAD. Leave them at root; the structural seed's tree is for product code only.
- `.claude/` directory (Claude Code skills, agents, settings) — also meta, not part of structural seed. Leave at root.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-1.1] Acceptance criteria verbatim (lines 391–407)
- [Source: _bmad-output/planning-artifacts/epics.md#AR-1] Structural seed (lines 113–152)
- [Source: _bmad-output/planning-artifacts/epics.md#AR-13] Pinned stack versions (lines 179–181)
- [Source: _bmad-output/planning-artifacts/epics.md#AR-14] Consistency conventions (lines 183–198)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/stack.md] Web-verified versions (2026-07-17)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/structural-seed.md] Exact directory tree
- [Source: _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/invariants-rules.md#AD-1] Hexagonal modular monolith
- [Source: _bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/consistency-conventions.md] File naming, function ceiling, DoD
- [Source: _bmad-output/planning-artifacts/prds/prd-VAIC-2026-07-17/prd/8-constraints-guardrails-nfrs.md#8.4] Cross-cutting NFRs (observability, security)
- [Source: _bmad-output/planning-artifacts/design/design-system.md] Frontend stack confirmation (React 19 · Vite 8 · TypeScript 7 · Tailwind 4)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (via Claude Code, glm-5.1[1m] backend session)

### Debug Log References

- `uv sync --extra dev` resolved 75 packages; installed Python 3.13.7 via `uv python install 3.13`
- Resolved one TS error during T6.8: `main.tsx:4` imported `./App.tsx` with extension while `allowImportingTsExtensions: false`; fixed by removing the `.tsx` suffix
- Vite 8.1.5 cold boot: 9.5s (acceptable for skeleton; first cold start includes Tailwind v4 JIT init)
- Starlette emits one deprecation warning from `fastapi.testclient` about `httpx` vs `httpx2`; harmless, no action needed in Story 1.1

### Completion Notes List

- **AC1/AC4 partial**: docker-compose.yml syntax validated via `docker compose config`. Runtime `docker compose up` requires Docker Desktop daemon to be running on the dev machine; deferred to manual verification before PR merge. Healthcheck definitions match spec (pg_isready / redis-cli ping, 5s interval, 10 retries).
- **AC2 ✅**: `backend/pyproject.toml` pins AR-13 stack. Sync SQLAlchemy via `psycopg[binary]>=3.2` (psycopg3) — `asyncpg` dropped because stack.md mandates sync mode. Story 1.2 may revisit if it needs async DB.
- **AC3 ✅**: `frontend/package.json` pins Vite `^8`, React `^19`, TypeScript `^7`, Tailwind `^4`, TanStack Query `^5`. npm resolved 130 packages, 0 vulnerabilities.
- **AC5 ✅**: `tests/integration/test_health.py:14` PASSED. Live `uvicorn app.main:app` returns `{"status":"ok"}` with HTTP 200. `/health` is DB-free (liveness, not readiness).
- **AC6 ✅**: Vite 8.1.5 boots in 9.5s on `:5173`, HTTP 200. `npx tsc --noEmit` clean. Default Vite template cruft replaced with minimal "VAIC skeleton ready" `App.tsx`.
- **AC7 ✅**: Directory tree matches `structural-seed.md` exactly. All six modules, ports/adapters, bootstrap, tests/{unit,integration,e2e}, frontend routes/components/hooks/lib all present.
- **Scope discipline**: No domain logic, no DB engine wiring, no auth, no port interfaces, no migrations — all deferred to Stories 1.2–1.12 per the scope boundaries section.
- **DoD**: test evidence (`tests/integration/test_health.py:14` PASSED), production code reference (`backend/app/main.py:21-26`, `infra/docker-compose.yml`).

### File List

**Created (new):**
- `README.md`
- `.env.example`
- `infra/docker-compose.yml`
- `backend/pyproject.toml`
- `backend/alembic.ini`
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/modules/__init__.py`
- `backend/app/modules/tenant/{__init__.py, routes.py, service.py, models.py}`
- `backend/app/modules/agent_builder/{__init__.py, routes.py, service.py, models.py}`
- `backend/app/modules/orchestrator/{__init__.py, routes.py, service.py, models.py}`
- `backend/app/modules/mini_app/{__init__.py, routes.py, service.py, models.py, provisioner.py, ui_renderer.py}`
- `backend/app/modules/actions/{__init__.py, routes.py, bus.py, triggers.py}`
- `backend/app/modules/audit/{__init__.py, routes.py, sink.py}`
- `backend/app/core/{__init__.py, ports/__init__.py, adapters/__init__.py, tenant_context.py, errors.py}`
- `backend/app/bootstrap/__init__.py`
- `backend/tests/{__init__.py, unit/{__init__.py,.gitkeep}, integration/{__init__.py,test_health.py}, e2e/{__init__.py,.gitkeep}}`
- `frontend/{package.json, vite.config.ts, tsconfig.json, index.html}`
- `frontend/src/{main.tsx, App.tsx, vite-env.d.ts, styles/tokens.css}`
- `frontend/src/routes/{agent-builder, orchestrator, actions, mini-apps.$appId, trace.$runId}/.gitkeep`
- `frontend/src/{components, hooks, lib}/.gitkeep`

**Modified (existing):**
- (none — `.gitignore`, `docs/` already satisfied requirements)

**Auto-generated (git-ignored, do NOT commit):**
- `backend/.venv/`, `backend/uv.lock`
- `frontend/node_modules/`, `frontend/package-lock.json`

## Change Log

- 2026-07-17: Story 1.1 implemented — repo skeleton, docker-compose, backend skeleton with /health, frontend Vite+React+TS+Tailwind skeleton. Status: ready-for-dev → in-progress → review.
