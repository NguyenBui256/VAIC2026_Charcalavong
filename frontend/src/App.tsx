/* Story 1.8 — App router with auth guard.
 * Unauthenticated users → /login. Authenticated → AppShell with nested routes.
 *
 * Story 1.11 — Cmd+K command palette wired at root via CommandPaletteProvider.
 */

import { BrowserRouter, Routes, Route, Navigate, useNavigate } from "react-router-dom";
import { useEffect, type ReactNode } from "react";
import AppShell from "./components/AppShell";
import LoginPage from "./routes/login";
import DashboardPage from "./routes/dashboard";
import AuditExplorerPage from "./routes/audit-explorer";
import AuditSessionPage from "./routes/audit-session";
import { isAuthenticated } from "./lib/auth";
import { CommandPaletteProvider } from "./components/CommandPalette/CommandPaletteContext";
import CommandPalette from "./components/CommandPalette/CommandPalette";
import { registerNavigationCommands } from "./components/CommandPalette/navigationCommands";

/** Auth guard: redirects to /login if no token. */
function ProtectedRoute({ children }: { children: ReactNode }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** Inverse guard: redirect authenticated users away from /login. */
function PublicOnlyRoute({ children }: { children: ReactNode }) {
  if (isAuthenticated()) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
}

/** AppRoutes — extracted so tests can wrap in MemoryRouter without double-router. */
export function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicOnlyRoute>
            <LoginPage />
          </PublicOnlyRoute>
        }
      />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        {/* Placeholder routes for nav — real surfaces arrive in later stories */}
        <Route path="/agents" element={<ComingSoon title="Agents" />} />
        <Route path="/workflows" element={<ComingSoon title="Workflows" />} />
        <Route path="/mini-apps" element={<ComingSoon title="Mini-Apps" />} />
        <Route path="/actions" element={<ComingSoon title="Actions" />} />
        <Route path="/audit" element={<AuditExplorerPage />} />
        <Route path="/audit/:sessionId" element={<AuditSessionPage />} />
        <Route path="/settings" element={<ComingSoon title="Settings" />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

/**
 * Invisible component that registers navigation commands into the
 * command-registry on mount. Must be inside Router context.
 */
function CommandPaletteRegistrations() {
  const navigate = useNavigate();
  useEffect(() => {
    const unregister = registerNavigationCommands((path) => navigate(path));
    return unregister;
  }, [navigate]);
  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <CommandPaletteProvider>
        <AppRoutes />
        <CommandPaletteRegistrations />
        <CommandPalette />
      </CommandPaletteProvider>
    </BrowserRouter>
  );
}

/** Tiny placeholder for nav routes that don't have real surfaces yet. */
function ComingSoon({ title }: { title: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "50vh",
      }}
    >
      <h1 className="text-h1" style={{ marginBottom: "var(--space-2)" }}>
        {title}
      </h1>
      <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
        Coming soon
      </p>
    </div>
  );
}
