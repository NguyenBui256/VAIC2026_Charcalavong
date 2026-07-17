/* Story 1.8 — Theme toggle button. Uses Sun/Moon icons, aria-label for a11y. */

import { Sun, Moon } from "lucide-react";
import { useTheme } from "../hooks/useTheme";

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="vaic-theme-toggle"
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
      title={isDark ? "Light mode" : "Dark mode"}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: "36px",
        height: "36px",
        border: "1px solid var(--color-border)",
        borderRadius: "var(--radius-control)",
        background: "var(--color-surface)",
        color: "var(--color-text-secondary)",
        transition: `color var(--duration-hover) ease-out, background var(--duration-hover) ease-out`,
      }}
    >
      {isDark ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}
    </button>
  );
}
