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
  "/mini-apps",
  "/kb",
  "/tools",
  "/integrations",
] as const;

// Shared proxy map — reused by both `dev` (server) and `preview` so that
// `npm run preview` (serving the production build from dist/) reaches the
// backend the same way dev does. Vite's `server.proxy` does NOT apply to
// preview, hence the explicit `preview.proxy` below. Setting `VITE_API_BASE`
// at build time bypasses the proxy entirely (calls backend directly; CORS) —
// this is the cross-origin deploy path (separate app/api hostnames).
// The proxy prefixes above (/agents, /workflows, /audit, ...) collide with the
// SPA's own client-side route paths. A browser page refresh (F5) on such a
// route issues a *document navigation* GET with `Accept: text/html` — without
// this bypass, Vite would proxy that navigation to the backend, which returns a
// raw 401 "Missing or malformed Authorization header" JSON page (a plain
// navigation carries no Authorization header). `bypass` returns `/index.html`
// for HTML navigations so they fall through to the SPA router, while real API
// traffic (fetch/XHR `*/*` or `application/json`, SSE `text/event-stream`) is
// still proxied normally.
function bypassHtmlNavigation(req: { headers: { accept?: string } }) {
  if (req.headers.accept?.includes("text/html")) {
    return "/index.html";
  }
}

const proxy = Object.fromEntries(
  proxyTargets.map((p) => [
    p,
    { target: backend, changeOrigin: true, bypass: bypassHtmlNavigation },
  ]),
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
