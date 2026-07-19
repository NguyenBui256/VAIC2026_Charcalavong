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
cp infra/.env.example infra/.env
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d
docker compose --env-file infra/.env -f infra/docker-compose.yml ps    # both services should report "healthy"
```

Env is split by consumer — `infra/.env` (compose), `backend/.env` (app), `frontend/.env` (Vite). See the root `.env.example` for the layout. There is no root `.env`.

### Run the backend

```bash
cd backend
cp .env.example .env          # VAIC_* config; ports must match infra/.env
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/health> → `{"status": "ok"}`

### Run the frontend

```bash
cd frontend
cp .env.example .env          # optional; VITE_API_BASE (default: same-origin via Vite proxy)
npm install
npm run dev
```

Vite dev server: <http://localhost:5173>

## Service Ports

| Service | Dev | Prod | Notes |
|---|---|---|---|
| Frontend | 5173 (`vite dev`) | 4173 (`vite preview`) | — |
| Backend API | 8000 (`uvicorn --reload`) | 8001 (pm2 `vaic-api`) | — |
| MCP tool server (`vaic_tools`) | 8002 (`uvicorn --reload`) | 8003 (pm2 `vaic-tools`) | REST + MCP at `/mcp/` |
| Worker (ARQ) | — | — | **No port** — consumes Redis jobs only |

Dev and prod ports differ so both can run side by side on one host. Prod services sit behind Cloudflare Tunnel domains: `charcalavon.site` (frontend), `api.charcalavon.site` (backend), `mcp.charcalavon.site` (MCP tool server → localhost:8003).

Dev backend reaches the MCP server at `http://localhost:8002`; prod backend reaches it at `https://mcp.charcalavon.site` (`VAIC_VAIC_TOOLS_*` in `backend/.env` / `.env.production`).

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
