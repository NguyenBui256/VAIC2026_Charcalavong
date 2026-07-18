/* Story 1.8 — App Shell layout (UX-DR13).
 * Sidebar (256px, collapses to 72px < 1280px) + Topbar (56px) + main content + optional Inspector (320px).
 */

import { Outlet, useNavigate, useLocation } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import Inspector from "./Inspector";
import { useAuth } from "../hooks/useAuth";
import { useCallback } from "react";

const shellStyle: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  height: "100vh",
  overflow: "hidden",
  background: "var(--color-bg)",
};

const bodyStyle: React.CSSProperties = {
  display: "flex",
  flex: 1,
  minHeight: 0,
};

const mainStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  overflow: "auto",
  padding: "var(--space-6)",
};

// Full-bleed routes own their own scroll + padding (e.g. the chat surface),
// so <main> drops its padding and hands the height straight through.
const mainStyleFullBleed: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  overflow: "hidden",
  padding: 0,
};

export default function AppShell() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const fullBleed = location.pathname === "/chat";

  const handleLogout = useCallback(() => {
    logout();
    navigate("/login");
  }, [logout, navigate]);

  return (
    <div className="vaic-app-shell" style={shellStyle} data-testid="vaic-app-shell">
      <Topbar user={user} onLogout={handleLogout} />
      <div style={bodyStyle}>
        <Sidebar />
        <main
          style={fullBleed ? mainStyleFullBleed : mainStyle}
          className="vaic-main-content"
        >
          <Outlet />
        </main>
        <Inspector open={false} />
      </div>
    </div>
  );
}
