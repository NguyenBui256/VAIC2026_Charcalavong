/* Story 1.11 — Default navigation commands.
 *
 * Registered once at app startup. Each command navigates via `react-router`'s
 * `useNavigate()` (passed in via the register function so the module stays
 * framework-friendly and testable).
 */

import {
  LayoutGrid,
  Bot,
  Database,
  Wrench,
  Workflow,
  AppWindow,
  Zap,
  FileSearch,
  Settings,
  Play,
} from "lucide-react";
import type { Command } from "./CommandRegistry";
import { commandRegistry } from "./CommandRegistry";

/** The top-level navigation destinations (matches Sidebar UX-DR14). */
export interface NavTarget {
  id: string;
  title: string;
  path: string;
}

export const NAV_TARGETS: readonly NavTarget[] = [
  { id: "dashboard", title: "Go to Dashboard", path: "/dashboard" },
  { id: "agents", title: "Go to Agents", path: "/agents" },
  { id: "database", title: "Go to Database", path: "/database" },
  { id: "tools", title: "Go to Tools", path: "/tools" },
  { id: "workflows", title: "Go to Workflows", path: "/workflows" },
  { id: "mini-apps", title: "Go to Mini-Apps", path: "/mini-apps" },
  { id: "actions", title: "Go to Actions", path: "/actions" },
  { id: "audit", title: "Go to Audit", path: "/audit" },
  { id: "settings", title: "Go to Settings", path: "/settings" },
] as const;

const NAV_ICON_BY_ID: Record<string, typeof LayoutGrid> = {
  dashboard: LayoutGrid,
  agents: Bot,
  database: Database,
  tools: Wrench,
  workflows: Workflow,
  "mini-apps": AppWindow,
  actions: Zap,
  audit: FileSearch,
  settings: Settings,
};

/** Prefix used for all navigation command ids. */
export const NAV_PREFIX = "nav:";

/**
 * Register navigation commands. `navigate` is `react-router`'s navigate fn.
 * Returns an unregister function (used in tests).
 */
export function registerNavigationCommands(navigate: (path: string) => void): () => void {
  const unregisters: Array<() => void> = [];

  for (const target of NAV_TARGETS) {
    const cmd: Command = {
      id: `${NAV_PREFIX}${target.id}`,
      title: target.title,
      section: "Navigation",
      icon: NAV_ICON_BY_ID[target.id],
      keywords: [target.id],
      shortcut: undefined,
      run: ({ closePalette }) => {
        navigate(target.path);
        closePalette();
      },
    };
    unregisters.push(commandRegistry.register(cmd));
  }

  // Placeholder "Run workflow…" command — surfaces "No workflows yet" until
  // Epic 3 registers real workflow commands. Available=false hides it from
  // the visible list, but our palette special-cases it via id for the message.
  unregisters.push(
    commandRegistry.register({
      id: "workflow.run:__placeholder__",
      title: "Run workflow…",
      section: "Workflows",
      icon: Play,
      keywords: ["workflow", "run", "execute"],
      available: true,
      run: () => {
        // No-op: the palette intercepts this id and shows the "No workflows
        // yet" message instead of executing. Downstream epics will replace
        // this placeholder with real workflow commands.
      },
    }),
  );

  return () => unregisters.forEach((fn) => fn());
}

/** Id of the placeholder workflow command. */
export const WORKFLOW_PLACEHOLDER_ID = "workflow.run:__placeholder__";
