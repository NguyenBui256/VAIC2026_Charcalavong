/* Story 1.11 — Command Palette modal.
 *
 * Opens via Cmd/Ctrl+K (wired in CommandPaletteProvider) or the
 * `useCommandPalette().openPalette()` hook.
 *
 * Behaviour:
 *  - Esc closes without action (UX-DR1 escape routes).
 *  - ↑/↓ navigate; Enter selects.
 *  - Typing filters the list by fuzzy match (lib/fuzzyMatch.ts).
 *  - Selecting a navigation command closes the palette + navigates.
 *  - "Run workflow…" placeholder shows "No workflows yet" until Epic 3.
 *
 * Motion: 200ms modal easing cubic-bezier(0.16, 1, 0.3, 1) (UX-DR9).
 * Focus trap: Tab cycles within the palette while it's open.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import { Search, CornerDownLeft, ArrowUp, ArrowDown } from "lucide-react";
import { useCommandPalette } from "./CommandPaletteContext";
import {
  commandRegistry,
  type Command,
  type CommandSection,
} from "./CommandRegistry";
import { WORKFLOW_PLACEHOLDER_ID } from "./navigationCommands";
import { fuzzyFilter } from "../../lib/fuzzyMatch";
import { easings, durations } from "../../lib/motion";

/** Stable section ordering. */
const SECTION_ORDER: CommandSection[] = [
  "Navigation",
  "Workflows",
  "Actions",
  "Audit",
  "Settings",
  "Help",
  "Custom",
];

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "rgba(15, 23, 42, 0.45)",
  backdropFilter: "blur(2px)",
  zIndex: 100,
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "center",
  paddingTop: "12vh",
  // 200ms modal easing per UX-DR9
  animation: `vaic-palette-overlay ${durations.modal}ms ${easings.modal}`,
};

const dialogStyle: React.CSSProperties = {
  width: "min(640px, calc(100vw - 48px))",
  maxHeight: "60vh",
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-panel)",
  boxShadow: "var(--shadow-md)",
  overflow: "hidden",
  display: "flex",
  flexDirection: "column",
  animation: `vaic-palette-in ${durations.modal}ms ${easings.modal}`,
};

const inputWrapStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-2)",
  padding: "var(--space-3) var(--space-4)",
  borderBottom: "1px solid var(--color-border)",
};

const inputStyle: React.CSSProperties = {
  flex: 1,
  border: "none",
  outline: "none",
  background: "transparent",
  fontFamily: "var(--font-sans)",
  fontSize: "var(--text-body)",
  color: "var(--color-text)",
};

const listStyle: React.CSSProperties = {
  flex: 1,
  minHeight: 0,
  overflowY: "auto",
  padding: "var(--space-2)",
};

const sectionHeaderStyle: React.CSSProperties = {
  padding: "var(--space-2) var(--space-3) var(--space-1)",
  fontSize: "var(--text-caption)",
  fontWeight: 700,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: "var(--color-text-tertiary)",
};

const rowBaseStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-3)",
  width: "100%",
  padding: "var(--space-2) var(--space-3)",
  borderRadius: "var(--radius-control)",
  border: "1px solid transparent",
  background: "transparent",
  textAlign: "left",
  color: "var(--color-text)",
  fontSize: "var(--text-body)",
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
};

const rowActiveStyle: React.CSSProperties = {
  background: "var(--color-primary-soft)",
  borderColor: "var(--color-primary)",
  color: "var(--color-primary)",
};

const titleStyle: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};

const subtitleStyle: React.CSSProperties = {
  fontSize: "var(--text-caption)",
  color: "var(--color-text-tertiary)",
  flexShrink: 0,
};

const hintStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-1)",
  fontSize: "var(--text-caption)",
  color: "var(--color-text-tertiary)",
  flexShrink: 0,
};

const footerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "var(--space-4)",
  padding: "var(--space-2) var(--space-4)",
  borderTop: "1px solid var(--color-border)",
  background: "var(--color-surface-muted)",
  fontSize: "var(--text-caption)",
  color: "var(--color-text-tertiary)",
};

const emptyStyle: React.CSSProperties = {
  padding: "var(--space-8) var(--space-4)",
  textAlign: "center",
  color: "var(--color-text-tertiary)",
  fontSize: "var(--text-body)",
};

const noWorkflowsStyle: React.CSSProperties = {
  padding: "var(--space-3) var(--space-4)",
  fontSize: "var(--text-small)",
  color: "var(--color-text-tertiary)",
  fontStyle: "italic",
};

export default function CommandPalette() {
  const { isOpen, closePalette } = useCommandPalette();

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const [registryVersion, setRegistryVersion] = useState(0);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  // Subscribe to registry changes so runtime add/remove reflects in the list.
  useEffect(() => {
    if (!isOpen) return;
    return commandRegistry.subscribe(() => setRegistryVersion((v) => v + 1));
  }, [isOpen]);

  // Reset state on open + focus input.
  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setActiveIndex(0);
      // Focus after the open animation ticks.
      const id = window.setTimeout(() => inputRef.current?.focus(), 0);
      return () => window.clearTimeout(id);
    }
  }, [isOpen]);

  // Build flat list of visible commands filtered + sorted by fuzzy match.
  const filtered = useMemo(() => {
    void registryVersion; // re-run on registry change
    if (!isOpen) return [];
    const all = commandRegistry.visible();
    const matched = fuzzyFilter(all, query, (c) =>
      [c.title, ...(c.keywords ?? [])].join(" "),
    );
    return matched.map((m) => m.item);
  }, [query, registryVersion, isOpen]);

  // Group filtered commands by section, preserving SECTION_ORDER.
  const grouped = useMemo(() => {
    const map = new Map<CommandSection, Command[]>();
    for (const cmd of filtered) {
      const list = map.get(cmd.section) ?? [];
      list.push(cmd);
      map.set(cmd.section, list);
    }
    // Filter SECTION_ORDER to only include present sections + append unknown.
    const present = SECTION_ORDER.filter((s) => map.has(s));
    const unknown = [...map.keys()].filter((s) => !SECTION_ORDER.includes(s));
    return [...present, ...unknown].map((section) => ({
      section,
      commands: map.get(section)!,
    }));
  }, [filtered]);

  // Clamp activeIndex when filtered list changes.
  useEffect(() => {
    if (activeIndex >= filtered.length) {
      setActiveIndex(Math.max(0, filtered.length - 1));
    }
  }, [filtered.length, activeIndex]);

  // Scroll active row into view.
  useEffect(() => {
    if (!isOpen || !listRef.current) return;
    const activeRow = listRef.current.querySelector<HTMLButtonElement>(
      `[data-index="${activeIndex}"]`,
    );
    activeRow?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, isOpen]);

  const selectCommand = useCallback(
    (cmd: Command) => {
      // Special-case: workflow placeholder shows "No workflows yet".
      if (cmd.id === WORKFLOW_PLACEHOLDER_ID) return;
      cmd.run({ closePalette });
    },
    [closePalette],
  );

  const onKeyDown = useCallback(
    (e: ReactKeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Escape") {
        e.preventDefault();
        closePalette();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => (filtered.length === 0 ? 0 : (i + 1) % filtered.length));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) =>
          filtered.length === 0 ? 0 : (i - 1 + filtered.length) % filtered.length,
        );
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const cmd = filtered[activeIndex];
        if (cmd) selectCommand(cmd);
        return;
      }
      // Simple focus trap: Tab cycles within palette.
      if (e.key === "Tab") {
        e.preventDefault();
        const focusable = [
          inputRef.current,
          ...Array.from(
            listRef.current?.querySelectorAll<HTMLButtonElement>("button[data-index]") ??
              [],
          ),
        ].filter(Boolean) as HTMLElement[];
        if (focusable.length === 0) return;
        const current = document.activeElement as HTMLElement;
        const idx = focusable.indexOf(current);
        const next = e.shiftKey
          ? focusable[(idx - 1 + focusable.length) % focusable.length]
          : focusable[(idx + 1) % focusable.length];
        next?.focus();
      }
    },
    [activeIndex, closePalette, filtered, selectCommand],
  );

  if (!isOpen) return null;

  // Compute flat index per command across grouped sections.
  let flatIndex = -1;

  return (
    <div
      role="presentation"
      style={overlayStyle}
      onClick={(e) => {
        // Click on the overlay (outside dialog) closes.
        if (e.target === e.currentTarget) closePalette();
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        style={dialogStyle}
        data-testid="vaic-command-palette"
        onKeyDown={onKeyDown}
      >
        {/* Search input */}
        <div style={inputWrapStyle}>
          <Search
            size={18}
            strokeWidth={1.5}
            color="var(--color-text-tertiary)"
          />
          <input
            ref={inputRef}
            type="text"
            aria-label="Search commands"
            aria-autocomplete="list"
            placeholder="Type a command or page name…"
            style={inputStyle}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setActiveIndex(0);
            }}
            data-testid="vaic-command-palette-input"
          />
        </div>

        {/* Command list */}
        <div ref={listRef} style={listStyle} role="listbox" aria-label="Commands">
          {filtered.length === 0 && (
            <div style={emptyStyle}>No matching commands.</div>
          )}

          {grouped.map(({ section, commands }) => (
            <div key={section} role="group" aria-label={section}>
              <div style={sectionHeaderStyle} role="presentation">
                {section}
              </div>
              {commands.map((cmd) => {
                flatIndex += 1;
                const isActive = flatIndex === activeIndex;
                const isPlaceholder = cmd.id === WORKFLOW_PLACEHOLDER_ID;
                const Icon = cmd.icon;
                return (
                  <div key={cmd.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={isActive}
                      data-index={flatIndex}
                      data-testid={`vaic-command-${cmd.id}`}
                      style={{
                        ...rowBaseStyle,
                        ...(isActive ? rowActiveStyle : null),
                      }}
                      onMouseEnter={() => setActiveIndex(flatIndex)}
                      onClick={() => selectCommand(cmd)}
                    >
                      {Icon && (
                        <Icon
                          size={16}
                          strokeWidth={1.5}
                          color="currentColor"
                          style={{ flexShrink: 0 }}
                        />
                      )}
                      <span style={titleStyle}>{cmd.title}</span>
                      {cmd.subtitle && (
                        <span style={subtitleStyle}>{cmd.subtitle}</span>
                      )}
                      {cmd.shortcut && (
                        <span style={hintStyle}>{cmd.shortcut}</span>
                      )}
                      {isActive && !isPlaceholder && (
                        <CornerDownLeft
                          size={14}
                          strokeWidth={1.5}
                          color="currentColor"
                          style={{ flexShrink: 0 }}
                        />
                      )}
                    </button>
                    {isPlaceholder && isActive && (
                      <div
                        style={noWorkflowsStyle}
                        data-testid="vaic-no-workflows-message"
                      >
                        No workflows yet — Epic 3 will register real workflows
                        here.
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div style={footerStyle}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-1)" }}>
            <ArrowUp size={12} strokeWidth={1.5} />
            <ArrowDown size={12} strokeWidth={1.5} />
            navigate
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-1)" }}>
            <CornerDownLeft size={12} strokeWidth={1.5} />
            select
          </span>
          <span>Esc to close</span>
          <span style={{ marginLeft: "auto" }}>
            {filtered.length} command{filtered.length === 1 ? "" : "s"}
          </span>
        </div>
      </div>
    </div>
  );
}
