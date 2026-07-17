/* Story 1.8 — Topbar (56px).
 * Left: wordmark + Tenant/Department breadcrumb.
 * Right: global Run split-button + Escalation bell + theme toggle + avatar menu.
 */

import { useState, useRef, useEffect } from "react";
import {
  Play,
  ChevronDown,
  Bell,
  LogOut,
  User as UserIcon,
} from "lucide-react";
import type { AuthUser } from "../lib/auth";
import ThemeToggle from "./ThemeToggle";

interface TopbarProps {
  user: AuthUser | null;
  onLogout: () => void;
}

const topbarStyle: React.CSSProperties = {
  height: "var(--topbar-h)",
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 var(--space-4)",
  background: "var(--color-surface)",
  borderBottom: "1px solid var(--color-border)",
};

const leftSection: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-4)",
};

const wordmarkStyle: React.CSSProperties = {
  fontSize: "var(--text-h3)",
  fontWeight: 800,
  color: "var(--color-primary)",
  letterSpacing: "-0.02em",
};

const breadcrumbStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-2)",
  fontSize: "var(--text-small)",
  color: "var(--color-text-tertiary)",
};

const rightSection: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-3)",
};

const runButtonStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "var(--space-2)",
  padding: "6px var(--space-3)",
  border: "1px solid var(--color-primary)",
  borderRadius: "var(--radius-control)",
  background: "var(--color-primary)",
  color: "var(--color-on-primary)",
  fontSize: "var(--text-small)",
  fontWeight: 600,
};

const runArrowStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: "20px",
  height: "28px",
  borderLeft: "1px solid var(--color-primary-hover)",
  marginLeft: "var(--space-1)",
};

const iconBtnStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: "36px",
  height: "36px",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-control)",
  background: "var(--color-surface)",
  color: "var(--color-text-secondary)",
  position: "relative",
};

const badgeStyle: React.CSSProperties = {
  position: "absolute",
  top: "-4px",
  right: "-4px",
  minWidth: "16px",
  height: "16px",
  padding: "0 4px",
  borderRadius: "8px",
  background: "var(--color-error)",
  color: "#fff",
  fontSize: "10px",
  fontWeight: 700,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  lineHeight: 1,
};

const avatarMenuStyle: React.CSSProperties = {
  position: "absolute",
  top: "calc(var(--topbar-h) - 4px)",
  right: "var(--space-4)",
  minWidth: "200px",
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-card)",
  boxShadow: "var(--shadow-md)",
  zIndex: 50,
  overflow: "hidden",
};

const menuItemStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-2)",
  padding: "var(--space-2) var(--space-3)",
  width: "100%",
  border: "none",
  background: "transparent",
  color: "var(--color-text-secondary)",
  fontSize: "var(--text-small)",
  textAlign: "left" as const,
};

export default function Topbar({ user, onLogout }: TopbarProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const initials = user?.email
    ? user.email.substring(0, 2).toUpperCase()
    : "U";

  const tenantName = "SHB Demo";
  const deptName = user?.department_id ?? "Unassigned";

  return (
    <header className="vaic-topbar" style={topbarStyle} data-testid="vaic-topbar">
      {/* Left: wordmark + breadcrumb */}
      <div style={leftSection}>
        <span className="vaic-wordmark" style={wordmarkStyle}>
          VAIC&#9888;
        </span>
        <div style={breadcrumbStyle} data-testid="vaic-breadcrumb">
          <span>Tenant: {tenantName}</span>
          <span>/</span>
          <span>Dept: {deptName}</span>
        </div>
      </div>

      {/* Right: Run + Bell + Theme + Avatar */}
      <div style={rightSection}>
        <button type="button" className="vaic-run-button" style={runButtonStyle}>
          <Play size={14} strokeWidth={2} fill="currentColor" />
          <span>Run</span>
          <span style={runArrowStyle}>
            <ChevronDown size={14} strokeWidth={1.5} />
          </span>
        </button>

        <button
          type="button"
          className="vaic-escalation-bell"
          style={iconBtnStyle}
          aria-label="Escalation inbox"
          title="Escalation inbox"
        >
          <Bell size={18} strokeWidth={1.5} />
          <span style={badgeStyle}>3</span>
        </button>

        <ThemeToggle />

        {/* Avatar dropdown */}
        <div ref={menuRef} style={{ position: "relative" }}>
          <button
            type="button"
            onClick={() => setMenuOpen((p) => !p)}
            aria-label="User menu"
            style={{
              ...iconBtnStyle,
              borderRadius: "50%",
              width: "32px",
              height: "32px",
              border: "2px solid var(--color-primary)",
              background: "var(--color-primary-soft)",
              color: "var(--color-primary)",
              fontSize: "12px",
              fontWeight: 700,
            }}
          >
            {initials}
          </button>
          {menuOpen && (
            <div style={avatarMenuStyle} role="menu">
              <div
                style={{
                  padding: "var(--space-3)",
                  borderBottom: "1px solid var(--color-border)",
                }}
              >
                <div className="text-small" style={{ fontWeight: 600 }}>
                  {user?.email ?? "Unknown"}
                </div>
                <div className="text-caption" style={{ color: "var(--color-text-tertiary)" }}>
                  {user?.role ?? ""}
                </div>
              </div>
              <button style={menuItemStyle} role="menuitem">
                <UserIcon size={16} strokeWidth={1.5} />
                Profile
              </button>
              <button
                style={{ ...menuItemStyle, color: "var(--color-destructive)" }}
                role="menuitem"
                onClick={() => {
                  setMenuOpen(false);
                  onLogout();
                }}
              >
                <LogOut size={16} strokeWidth={1.5} />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
