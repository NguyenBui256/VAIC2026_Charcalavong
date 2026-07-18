import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Vite config — Story 1.8.
// AC: `npm run dev` boots Vite dev server on :5173 without errors.
// API proxy forwards backend prefixes to FastAPI on :8000. Backend routes are
// mounted at their own top-level prefixes (no shared `/api`), so each must be
// proxied explicitly. When `VITE_API_BASE` is set, `lib/api.ts` bypasses this
// proxy and calls the backend directly (CORS on the backend covers that path).
const backend = "http://localhost:8000";
const proxyTargets = [
  "/auth",
  "/api",
  "/workflows",
  "/agents",
  "/audit",
  "/departments",
] as const;

// Shared proxy map — reused by both `dev` (server) and `preview` so that
// `npm run preview` (serving the production build from dist/) reaches the
// backend the same way dev does. Vite's `server.proxy` does NOT apply to
// preview, hence the explicit `preview.proxy` below. Setting `VITE_API_BASE`
// at build time bypasses the proxy entirely (calls backend directly; CORS) —
// this is the cross-origin deploy path (separate app/api hostnames).
const proxy = Object.fromEntries(
  proxyTargets.map((p) => [p, { target: backend, changeOrigin: true }]),
);

// Function form so `loadEnv` picks up `VITE_ALLOWED_HOSTS` from BOTH the shell
// and `.env*` files (the plain config callback does not auto-load .env).
export default defineConfig(({ mode }) => {
  // "" prefix → load all vars (incl. non-VITE_ ones) from .env* + process.env.
  const env = loadEnv(mode, process.cwd(), "");

  // Vite 8 rejects requests whose Host header isn't allow-listed (anti
  // DNS-rebinding). When serving `preview` behind a public hostname (e.g. a
  // Cloudflare Tunnel), set
  //   VITE_ALLOWED_HOSTS=app.example.com,foo.trycloudflare.com
  // Undefined → Vite's localhost-only default (fine for local runs).
  const allowedHosts = env.VITE_ALLOWED_HOSTS
    ? env.VITE_ALLOWED_HOSTS.split(",").map((h) => h.trim()).filter(Boolean)
    : undefined;

  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      host: true,
      strictPort: false,
      proxy,
      allowedHosts,
    },
    preview: {
      port: 4173,
      host: true,
      strictPort: false,
      proxy,
      allowedHosts,
    },
    build: {
      outDir: "dist",
      sourcemap: true,
    },
  };
});
