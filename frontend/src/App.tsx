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
import AgentsPage from "./routes/agents";
import AgentDetailPage from "./routes/agent-detail";
import WorkflowsPage from "./routes/workflows";
import WorkflowDetailPage from "./routes/workflow-detail";
import RunTrackingPage from "./routes/orchestrator/RunTrackingPage";
import MiniAppsPage from "./routes/mini-apps";
import MiniAppHostPage from "./routes/mini-app-host";
import AuditPage from "./routes/audit";
import ToolsPage from "./routes/tools/ToolsPage";
import KnowledgeBasePage from "./routes/knowledge-base/KnowledgeBasePage";
import ChatPage from "./routes/chat/ChatPage";
import { isAuthenticated } from "./lib/auth";
import { CommandPaletteProvider } from "./components/CommandPalette/CommandPaletteContext";
import CommandPalette from "./components/CommandPalette/CommandPalette";
import { registerNavigationCommands } from "./components/CommandPalette/navigationCommands";
import { ToastProvider } from "./components/ui";

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
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/agents/:id" element={<AgentDetailPage />} />
        {/* Task 9 — shared Tools + Knowledge Base pages. */}
        <Route path="/knowledge-base" element={<KnowledgeBasePage />} />
        <Route path="/tools" element={<ToolsPage />} />
        {/* Story 3.1 — Workflow list + Definition tab detail. */}
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/workflows/:id" element={<WorkflowDetailPage />} />
        <Route path="/workflows/:id/runs/:runId" element={<RunTrackingPage />} />
        {/* Story 4.7 — Mini-App catalog list + create. */}
        <Route path="/mini-apps" element={<MiniAppsPage />} />
        {/* Task 16 — sandboxed Mini-App host page (iframe + scoped token). */}
        <Route path="/mini-apps/:appId" element={<MiniAppHostPage />} />
        {/* Placeholder routes for nav — real surfaces arrive in later stories */}
        <Route path="/actions" element={<ComingSoon title="Actions" />} />
        {/* Epic 6 (FR-22) — Trace Dashboard. */}
        <Route path="/audit" element={<AuditPage />} />
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
      <ToastProvider>
        <CommandPaletteProvider>
          <AppRoutes />
          <CommandPaletteRegistrations />
          <CommandPalette />
        </CommandPaletteProvider>
      </ToastProvider>
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
