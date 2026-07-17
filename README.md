# VAIC

Vietnamese banking AI-agent platform — Specialist Agents, cross-department Workflow Orchestrator, and Mini-App Builder with full audit trail.

## Quick Start

### Prerequisites

- Docker 28+ with Docker Compose v2
- Python 3.13 (install via `uv python install 3.13`)
- [uv](https://docs.astral.sh/uv/) 0.8+
- Node.js 22+ and npm 10+

### Bring up infrastructure

```bash
cp .env.example .env
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps    # both services should report "healthy"
```

### Run the backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/health> → `{"status": "ok"}`

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Vite dev server: <http://localhost:5173>

## Repository Layout

See [`_bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/structural-seed.md`](./_bmad-output/planning-artifacts/architecture/architecture-VAIC-2026-07-17/ARCHITECTURE-SPINE/structural-seed.md) for the authoritative source-tree contract.

```
backend/    FastAPI app (Python 3.13, hexagonal modular monolith)
frontend/   Vite + React 19 + TypeScript 7 SPA
infra/      docker-compose for Postgres 18 + Redis 7.4
docs/       Project documentation
_bmad/      BMAD Method skill engine (meta)
_bmad-output/  BMAD planning + implementation artifacts (meta)
```
