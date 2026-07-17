/* Story 1.8 — Theme state hook. Respects prefers-color-scheme, allows manual override.
 * Manual choice persisted in localStorage under "vaic_theme".
 * Applies `data-theme` attribute on <html> for CSS variable cascading.
 */

import { useState, useEffect, useCallback } from "react";

export type Theme = "light" | "dark";

const STORAGE_KEY = "vaic_theme";

/** Read the user's OS-level color scheme preference. */
function prefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

/** Read initial theme: explicit override > OS preference > light. */
function initialTheme(): Theme {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return prefersDark() ? "dark" : "light";
}

export interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (t: Theme) => void;
}

export function useTheme(): ThemeState {
  const [theme, setThemeState] = useState<Theme>(initialTheme);

  // Apply to <html> and persist when theme changes.
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Listen to OS changes when no manual override is set.
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    function onSchemeChange(e: MediaQueryListEvent) {
      // Only react if the user has NOT explicitly chosen a theme.
      if (localStorage.getItem(STORAGE_KEY) === null) {
        setThemeState(e.matches ? "dark" : "light");
      }
    }
    mq.addEventListener("change", onSchemeChange);
    return () => mq.removeEventListener("change", onSchemeChange);
  }, []);

  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const next = prev === "light" ? "dark" : "light";
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  return { theme, toggleTheme, setTheme };
}
