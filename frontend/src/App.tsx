/* Story 1.8 — App router with auth guard.
 * Unauthenticated users → /login. Authenticated → AppShell with nested routes.
 */

import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import AppShell from "./components/AppShell";
import LoginPage from "./routes/login";
import DashboardPage from "./routes/dashboard";
import { isAuthenticated } from "./lib/auth";

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
        <Route path="/audit" element={<ComingSoon title="Audit" />} />
        <Route path="/settings" element={<ComingSoon title="Settings" />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
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
