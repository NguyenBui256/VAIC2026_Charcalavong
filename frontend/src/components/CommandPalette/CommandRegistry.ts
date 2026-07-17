/* Story 1.11 — Command Registry.
 *
 * Extensible command catalogue for the Cmd+K palette.
 *
 * Downstream epics register commands at runtime, e.g.:
 *   registry.register({
 *     id: "workflow.run:abc-123",
 *     title: "Run workflow: Verify KYC",
 *     section: "Workflows",
 *     run: () => startWorkflow("abc-123"),
 *   });
 *
 * The registry is a plain class instance — it does NOT own React state.
 * The CommandPaletteContext subscribes via the tiny pub/sub below so
 * React can re-render when commands are added/removed.
 */

import type { LucideIcon } from "lucide-react";

/** Logical section a command belongs to (controls grouping in the palette). */
export type CommandSection =
  | "Navigation"
  | "Workflows"
  | "Actions"
  | "Audit"
  | "Settings"
  | "Help"
  | "Custom";

export interface Command {
  /** Stable unique id. Use prefix conventions: `nav:dashboard`, `workflow.run:<id>`. */
  id: string;
  /** Visible label (also the fuzzy-match target). */
  title: string;
  /** Optional secondary text shown muted next to the title. */
  subtitle?: string;
  /** Optional keywords appended to the fuzzy-match target. */
  keywords?: string[];
  /** Section heading — commands are grouped by this in the palette. */
  section: CommandSection;
  /** Optional leading icon (lucide-react). */
  icon?: LucideIcon;
  /** Execute the command. Called on Enter / click. */
  run: (ctx: CommandRunContext) => void | Promise<void>;
  /**
   * If false, the command is hidden. Used for feature-flagging (e.g. hide
   * "Export audit" until Epic 6 lands).
   */
  available?: boolean;
  /**
   * Optional shortcut hint rendered on the right (display only — actual
   * keyboard handling is the palette's responsibility).
   */
  shortcut?: string;
}

/** Context passed to `command.run`. Lets commands close the palette, navigate, etc. */
export interface CommandRunContext {
  /** Close the palette (e.g. after navigation). */
  closePalette: () => void;
}

type Listener = () => void;

class CommandRegistryImpl {
  private commands = new Map<string, Command>();
  private listeners = new Set<Listener>();

  /** Register a command. Replaces an existing command with the same id. */
  register(command: Command): () => void {
    if (!command.id) {
      throw new Error("CommandRegistry.register: command.id is required");
    }
    this.commands.set(command.id, command);
    this.emit();
    return () => this.unregister(command.id);
  }

  /** Remove a command by id. No-op if not present. */
  unregister(id: string): void {
    if (this.commands.delete(id)) {
      this.emit();
    }
  }

  /** Remove every command whose id starts with the given prefix. */
  unregisterByPrefix(prefix: string): void {
    let changed = false;
    for (const id of [...this.commands.keys()]) {
      if (id.startsWith(prefix)) {
        this.commands.delete(id);
        changed = true;
      }
    }
    if (changed) this.emit();
  }

  /** Returns all currently-registered commands (in insertion order). */
  list(): Command[] {
    return [...this.commands.values()];
  }

  /** Returns commands filtered by `available !== false`. */
  visible(): Command[] {
    return this.list().filter((c) => c.available !== false);
  }

  /** Subscribe to add/remove events. Returns an unsubscribe fn. */
  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  /** Clear all commands. Primarily for tests. */
  clear(): void {
    this.commands.clear();
    this.emit();
  }

  private emit(): void {
    for (const l of this.listeners) l();
  }
}

/** Singleton registry — import this everywhere. */
export const commandRegistry = new CommandRegistryImpl();

/** Re-export for tests that need a fresh instance. */
export { CommandRegistryImpl };
