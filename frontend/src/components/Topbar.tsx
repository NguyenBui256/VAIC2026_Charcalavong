/* Story 1.8 — Topbar (56px).
 * Left: gradient logo mark + wordmark + live section breadcrumb.
 * Right: command palette + notifications + theme toggle + avatar identity menu.
 */

import { useState, useRef, useEffect } from "react";
import { useLocation } from "react-router-dom";
import {
  LogOut,
  User as UserIcon,
  Command as CommandIcon,
  ChevronDown,
  ChevronRight,
  Landmark,
} from "lucide-react";
import type { AuthUser } from "../lib/auth";
import ThemeToggle from "./ThemeToggle";
import { useCommandPalette } from "../hooks/useCommandPalette";
import NotificationsBell from "./NotificationsBell";

interface TopbarProps {
  user: AuthUser | null;
  onLogout: () => void;
}

/* Map the first path segment to a human label for the breadcrumb.
 * Unknown segments fall back to a title-cased version of the slug. */
const SECTION_LABELS: Record<string, string> = {
  dashboard: "Overview",
  chat: "Chat",
  agents: "Agents",
  "knowledge-base": "Knowledge Base",
  tools: "Tools",
  database: "Database",
  workflows: "Workflows",
  "mini-apps": "Mini Apps",
  actions: "Actions",
  audit: "Audit Trail",
  settings: "Settings",
};

function sectionLabel(pathname: string): string {
  const seg = pathname.split("/").filter(Boolean)[0];
  if (!seg) return "Overview";
  return (
    SECTION_LABELS[seg] ??
    seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

const topbarStyle: React.CSSProperties = {
  height: "var(--topbar-h)",
  flexShrink: 0,
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "0 var(--space-5)",
  background: "color-mix(in srgb, var(--color-surface) 88%, transparent)",
  borderBottom: "1px solid var(--color-border)",
};

const leftSection: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-3)",
  minWidth: 0,
};

const brandStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-2)",
};

const brandMarkStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: "30px",
  height: "30px",
  borderRadius: "8px",
  background: "linear-gradient(135deg, var(--indigo-500), var(--indigo-700))",
  color: "#fff",
  boxShadow: "0 2px 6px rgba(79, 70, 229, 0.28)",
  flexShrink: 0,
};

const wordmarkStyle: React.CSSProperties = {
  fontSize: "var(--text-h3)",
  fontWeight: 800,
  color: "var(--color-text)",
  letterSpacing: "-0.02em",
  whiteSpace: "nowrap",
};

const breadcrumbStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-1)",
  color: "var(--color-text-tertiary)",
  fontSize: "var(--text-small)",
  fontWeight: 500,
  minWidth: 0,
};

const rightSection: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-2)",
};

const dividerStyle: React.CSSProperties = {
  width: "1px",
  height: "22px",
  background: "var(--color-border)",
  margin: "0 var(--space-1)",
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

const kbdStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: "18px",
  height: "18px",
  padding: "0 5px",
  borderRadius: "4px",
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  fontSize: "11px",
  fontWeight: 600,
  color: "var(--color-text-tertiary)",
  fontFamily: "var(--font-mono)",
  lineHeight: 1,
};

const avatarMenuStyle: React.CSSProperties = {
  position: "absolute",
  top: "calc(var(--topbar-h) - 4px)",
  right: "var(--space-5)",
  minWidth: "220px",
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
  const { openPalette } = useCommandPalette();
  const location = useLocation();
  const section = sectionLabel(location.pathname);

  // Detect platform to render the right shortcut hint (Cmd vs Ctrl).
  const isMac =
    typeof navigator !== "undefined" &&
    /Mac|iPhone|iPad|iPod/.test(navigator.platform || navigator.userAgent);

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
  const displayName = user?.email ? user.email.split("@")[0] : "Unknown";

  return (
    <header className="vaic-topbar" style={topbarStyle} data-testid="vaic-topbar">
      {/* Left: brand lockup + section breadcrumb */}
      <div style={leftSection}>
        <div className="vaic-brand" style={brandStyle}>
          <span className="vaic-brand-mark" style={brandMarkStyle} aria-hidden="true">
            <Landmark size={17} strokeWidth={2} />
          </span>
          <span className="vaic-wordmark" style={wordmarkStyle}>
            Banking Agent Hub
          </span>
        </div>
        <div style={breadcrumbStyle}>
          <ChevronRight size={14} strokeWidth={2} style={{ opacity: 0.55, flexShrink: 0 }} />
          <span
            style={{
              color: "var(--color-text-secondary)",
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {section}
          </span>
        </div>
      </div>

      {/* Right: Command palette + Notifications + Theme + Avatar */}
      <div style={rightSection}>
        <button
          type="button"
          onClick={openPalette}
          aria-label="Open command palette"
          title="Open command palette"
          data-testid="vaic-cmdk-hint"
          className="vaic-cmdk-btn"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "var(--space-2)",
            padding: "6px 10px 6px var(--space-3)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-control)",
            background: "var(--color-surface-muted)",
            color: "var(--color-text-tertiary)",
            fontSize: "var(--text-small)",
          }}
        >
          <CommandIcon size={14} strokeWidth={1.5} />
          <span style={{ fontWeight: 500 }}>Search</span>
          <span style={{ display: "flex", gap: "3px" }}>
            <kbd style={kbdStyle}>{isMac ? "⌘" : "Ctrl"}</kbd>
            <kbd style={kbdStyle}>K</kbd>
          </span>
        </button>

        <div style={dividerStyle} aria-hidden="true" />

        <div className="vaic-icon-btn" style={{ ...iconBtnStyle, padding: 0 }}>
          <NotificationsBell />
        </div>

        <ThemeToggle />

        <div style={dividerStyle} aria-hidden="true" />

        {/* Avatar dropdown */}
        <div ref={menuRef} style={{ position: "relative" }}>
          <button
            type="button"
            className="vaic-avatar-btn"
            onClick={() => setMenuOpen((p) => !p)}
            aria-label="User menu"
            aria-expanded={menuOpen}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-2)",
              padding: "3px 8px 3px 3px",
              border: "1px solid var(--color-border)",
              borderRadius: "999px",
              background: "var(--color-surface)",
            }}
          >
            <span
              style={{
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                width: "28px",
                height: "28px",
                borderRadius: "50%",
                background: "linear-gradient(135deg, var(--indigo-500), var(--indigo-700))",
                color: "#fff",
                fontSize: "11px",
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              {initials}
            </span>
            <span
              className="vaic-avatar-identity"
              style={{ display: "flex", flexDirection: "column", lineHeight: 1.2, textAlign: "left" }}
            >
              <span style={{ fontSize: "var(--text-small)", fontWeight: 600, color: "var(--color-text)" }}>
                {displayName}
              </span>
              <span style={{ fontSize: "11px", color: "var(--color-text-tertiary)" }}>
                {user?.role ?? "Member"}
              </span>
            </span>
            <ChevronDown
              size={15}
              strokeWidth={1.75}
              className={`vaic-avatar-chevron${menuOpen ? " is-open" : ""}`}
              style={{ color: "var(--color-text-tertiary)", flexShrink: 0 }}
            />
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
              <button className="vaic-menu-item" style={menuItemStyle} role="menuitem">
                <UserIcon size={16} strokeWidth={1.5} />
                Profile
              </button>
              <button
                className="vaic-menu-item is-destructive"
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
