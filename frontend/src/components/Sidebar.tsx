/* Story 1.8 — Sidebar navigation.
 * UX-DR14: 256px (collapses to 72px icon rail under 1280px viewport).
 * Nav items: Dashboard, Agents, Workflows, Mini-Apps, Actions, Audit, Settings.
 * Active: bg-primary-soft, text-primary, border-l-2 border-primary.
 * Hover: bg-surface-muted.
 */

import { NavLink } from "react-router-dom";
import {
  LayoutGrid,
  Bot,
  Workflow,
  AppWindow,
  Zap,
  Activity,
  Settings,
  HelpCircle,
} from "lucide-react";
import type { ComponentType } from "react";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/workflows", label: "Workflows", icon: Workflow },
  { to: "/mini-apps", label: "Mini-Apps", icon: AppWindow },
  { to: "/actions", label: "Actions", icon: Zap },
  { to: "/audit", label: "Audit", icon: Activity },
  { to: "/settings", label: "Settings", icon: Settings },
];

const sidebarStyle = {
  width: "var(--sidebar-w)",
  flexShrink: 0,
  background: "var(--color-surface)",
  borderRight: "1px solid var(--color-border)",
  display: "flex",
  flexDirection: "column" as const,
  height: "100%",
};

const navStyle = {
  flex: 1,
  padding: "var(--space-2) 0",
  overflowY: "auto" as const,
};

const linkBase: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-3)",
  padding: "var(--space-2) var(--space-4)",
  margin: "var(--space-1) var(--space-2)",
  borderRadius: "var(--radius-control)",
  color: "var(--color-text-secondary)",
  textDecoration: "none",
  fontSize: "var(--text-body)",
  fontWeight: 500,
  borderLeft: "2px solid transparent",
  transition: `background var(--duration-hover) ease-out, color var(--duration-hover) ease-out`,
};

const linkActive: React.CSSProperties = {
  background: "var(--color-primary-soft)",
  color: "var(--color-primary)",
  borderLeft: "2px solid var(--color-primary)",
  fontWeight: 600,
};

const linkHover: React.CSSProperties = {
  background: "var(--color-surface-muted)",
};

const footerStyle = {
  padding: "var(--space-3) var(--space-4)",
  borderTop: "1px solid var(--color-border)",
};

export default function Sidebar() {
  return (
    <aside className="vaic-sidebar" style={sidebarStyle} data-testid="vaic-sidebar">
      <nav style={navStyle} aria-label="Primary">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className="vaic-nav-item"
              style={({ isActive }) => ({
                ...linkBase,
                ...(isActive ? linkActive : {}),
              })}
              onMouseEnter={(e) => {
                const el = e.currentTarget;
                // Only apply hover bg if not active (active has its own bg).
                if (!el.classList.contains("active")) {
                  Object.assign(el.style, linkHover);
                }
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget;
                if (!el.classList.contains("active")) {
                  el.style.background = "";
                }
              }}
            >
              <Icon size={18} strokeWidth={1.5} />
              <span>{item.label}</span>
            </NavLink>
          );
        })}
      </nav>
      <div style={footerStyle}>
        <NavLink
          to="/help"
          className="vaic-nav-item vaic-nav-help"
          style={linkBase}
        >
          <HelpCircle size={18} strokeWidth={1.5} />
          <span>Help</span>
        </NavLink>
      </div>
    </aside>
  );
}
