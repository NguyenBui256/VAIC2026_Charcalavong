// PM2 process manager config for the VAIC stack (production run).
//
// PM2 does NOT build or provision anything — before `pm2 start` you must:
//   1. Postgres + Redis running (Docker containers, ports 5434 / 6381).
//   2. DB seeded once:  backend\.venv\Scripts\python.exe scripts\bootstrap_demo_tenant.py
//   3. Frontend built:  cd frontend && npm run build   (bakes VITE_API_BASE)
//
// Then from the repo root:
//   pm2 start ecosystem.config.cjs
//   pm2 status | pm2 logs | pm2 restart all | pm2 stop all
//   pm2 save                      # persist process list for resurrect-on-boot
//
// Paths are relative to this file (repo root). `.cjs` extension keeps this a
// CommonJS module even though frontend/package.json is `type: module`.

const path = require("path");

const BACKEND = path.join(__dirname, "backend");
const FRONTEND = path.join(__dirname, "frontend");
// Windows venv layout: .venv\Scripts\python.exe (POSIX would be bin/python).
const VENV_PY = path.join(BACKEND, ".venv", "Scripts", "python.exe");

module.exports = {
  apps: [
    {
      // FastAPI (uvicorn) — PRODUCTION API on :8001.
      // Dev runs on :8000 (see frontend/vite.config.ts proxy target), so prod
      // uses :8001 → both can run side by side (dev-test + prod at once).
      // The Cloudflare Tunnel ingress for api.charcalavon.site must point here
      // (http://localhost:8001).
      name: "vaic-api",
      cwd: BACKEND,
      script: VENV_PY,
      interpreter: "none", // script IS the interpreter; don't wrap it again
      args: [
        "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1",
        "--port", "8001",
        "--proxy-headers",
        "--forwarded-allow-ips", "127.0.0.1",
      ],
      env: { VAIC_ENV: "production" }, // -> loads backend/.env.production
      autorestart: true,
      max_restarts: 10,
    },
    {
      // ARQ worker — consumes run_workflow jobs from Redis. No open port.
      name: "vaic-worker",
      cwd: BACKEND,
      script: VENV_PY,
      interpreter: "none",
      args: ["-m", "scripts.run_worker"],
      env: { VAIC_ENV: "production" },
      autorestart: true,
      max_restarts: 10,
    },
    {
      // Frontend — serves the built dist/ via `vite preview` on :4173.
      // Runs vite.js under node directly (robust on Windows; avoids the
      // .bin/vite shell shim). preview mode = production -> loads .env.production.
      name: "vaic-web",
      cwd: FRONTEND,
      script: path.join(FRONTEND, "node_modules", "vite", "bin", "vite.js"),
      interpreter: "node",
      args: ["preview", "--port", "4173", "--host"],
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
