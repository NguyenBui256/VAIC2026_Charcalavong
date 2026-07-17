/* Story 1.11 — Command Palette context.
 *
 * Provides open/close state for the Cmd+K palette via React context.
 * Also exposes a tiny `useCommandPalette()` hook so any component can
 * open the palette programmatically (e.g. Topbar hint button).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

interface CommandPaletteContextValue {
  /** Whether the palette modal is currently open. */
  isOpen: boolean;
  /** Open the palette. */
  openPalette: () => void;
  /** Close the palette. */
  closePalette: () => void;
  /** Toggle open/close. */
  togglePalette: () => void;
}

const CommandPaletteContext = createContext<CommandPaletteContextValue | null>(
  null,
);

interface ProviderProps {
  children: ReactNode;
}

export function CommandPaletteProvider({ children }: ProviderProps) {
  const [isOpen, setIsOpen] = useState(false);

  const openPalette = useCallback(() => setIsOpen(true), []);
  const closePalette = useCallback(() => setIsOpen(false), []);
  const togglePalette = useCallback(() => setIsOpen((p) => !p), []);

  // Global Cmd/Ctrl+K listener — wired here so it works on every route.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && (e.key === "k" || e.key === "K")) {
        e.preventDefault();
        setIsOpen((p) => !p);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const value = useMemo<CommandPaletteContextValue>(
    () => ({ isOpen, openPalette, closePalette, togglePalette }),
    [isOpen, openPalette, closePalette, togglePalette],
  );

  return (
    <CommandPaletteContext.Provider value={value}>
      {children}
    </CommandPaletteContext.Provider>
  );
}

/** Hook: access the palette open/close state and controls. */
export function useCommandPalette(): CommandPaletteContextValue {
  const ctx = useContext(CommandPaletteContext);
  if (!ctx) {
    throw new Error(
      "useCommandPalette must be used within <CommandPaletteProvider>",
    );
  }
  return ctx;
}
