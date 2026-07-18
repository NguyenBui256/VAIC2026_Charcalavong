/* Story 1.8 — Sidebar navigation.
 * UX-DR14: 256px (collapses to 72px icon rail under 1280px viewport).
 * Nav items: Dashboard, Agents, Knowledge Base, Tools, Workflows, Mini-Apps, Actions, Audit, Settings.
 * Active: bg-primary-soft, text-primary, border-l-2 border-primary.
 * Hover: bg-surface-muted.
 */

import { NavLink } from "react-router-dom";
import {
  LayoutGrid,
  Bot,
  Database,
  Wrench,
  Workflow,
  AppWindow,
  Zap,
  Activity,
  Settings,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useState, type ComponentType } from "react";

// UX-DR14: expanded 256px, collapsed to icon-only rail 72px.
const COLLAPSED_W = "72px";
const STORAGE_KEY = "vaic:sidebar-collapsed";

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ size?: number; strokeWidth?: number }>;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutGrid },
  { to: "/agents", label: "Agents", icon: Bot },
  { to: "/database", label: "Database", icon: Database },
  { to: "/tools", label: "Tools", icon: Wrench },
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

// Floating toggle tab pinned to the right vertical edge of the sidebar,
// vertically centered on the border divider.
const toggleBtnStyle: React.CSSProperties = {
  position: "absolute",
  top: "16px",
  right: "-14px",
  zIndex: 10,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "28px",
  height: "28px",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-full, 9999px)",
  background: "var(--color-surface)",
  color: "var(--color-text-secondary)",
  cursor: "pointer",
  boxShadow: "var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.12))",
  transition: `background var(--duration-hover) ease-out`,
};

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState<boolean>(
    () => localStorage.getItem(STORAGE_KEY) === "1",
  );

  const toggle = () => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
      return next;
    });
  };

  // When collapsed: narrow rail, hide labels, center icons.
  const rootStyle: React.CSSProperties = {
    ...sidebarStyle,
    position: "relative",
    width: collapsed ? COLLAPSED_W : "var(--sidebar-w)",
    transition: "width var(--duration-hover) ease-out",
  };

  const itemStyle = (isActive: boolean): React.CSSProperties => ({
    ...linkBase,
    ...(isActive ? linkActive : {}),
    ...(collapsed ? { justifyContent: "center", padding: "var(--space-2)" } : {}),
  });

  return (
    <aside
      className="vaic-sidebar"
      style={rootStyle}
      data-testid="vaic-sidebar"
      data-collapsed={collapsed}
    >
      <button
        type="button"
        onClick={toggle}
        className="vaic-sidebar-toggle"
        style={toggleBtnStyle}
        title={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
        aria-label={collapsed ? "Mở rộng sidebar" : "Thu gọn sidebar"}
        aria-expanded={!collapsed}
        onMouseEnter={(e) => Object.assign(e.currentTarget.style, linkHover)}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "var(--color-surface)";
        }}
      >
        {collapsed ? (
          <ChevronRight size={16} strokeWidth={1.5} />
        ) : (
          <ChevronLeft size={16} strokeWidth={1.5} />
        )}
      </button>
      <nav style={navStyle} aria-label="Primary">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className="vaic-nav-item"
              title={collapsed ? item.label : undefined}
              style={({ isActive }) => itemStyle(isActive)}
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
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>
      <div style={footerStyle}>
        <NavLink
          to="/help"
          className="vaic-nav-item vaic-nav-help"
          title={collapsed ? "Help" : undefined}
          style={itemStyle(false)}
        >
          <HelpCircle size={18} strokeWidth={1.5} />
          {!collapsed && <span>Help</span>}
        </NavLink>
      </div>
    </aside>
  );
}
