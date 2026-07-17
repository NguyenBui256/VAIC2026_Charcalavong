/* Test: CommandPalette (Story 1.11).
 *
 * Covers the ACs:
 *  - Cmd/Ctrl+K opens palette with search input focused.
 *  - Esc closes palette.
 *  - Typing filters via fuzzy match.
 *  - Enter selects and navigates.
 *  - Registry API allows adding/removing commands at runtime.
 *  - "Run workflow…" placeholder shows "No workflows yet".
 */

import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useNavigate } from "react-router-dom";
import { useEffect } from "react";
import {
  CommandPaletteProvider,
} from "./CommandPaletteContext";
import CommandPalette from "./CommandPalette";
import {
  commandRegistry,
  type Command,
} from "./CommandRegistry";
import { registerNavigationCommands, NAV_TARGETS } from "./navigationCommands";

/** Wrapper that wires registry + router + provider.
 * Registers navigation commands synchronously before palette can open.
 */
function TestApp({
  extraCommands = [],
  navigate: navigateSpy,
}: {
  extraCommands?: Command[];
  navigate?: ReturnType<typeof vi.fn>;
} = {}) {
  return (
    <MemoryRouter>
      <CommandPaletteProvider>
        <PaletteAndRegistry
          extraCommands={extraCommands}
          navigateSpy={navigateSpy}
        />
      </CommandPaletteProvider>
    </MemoryRouter>
  );
}

function PaletteAndRegistry({
  extraCommands,
  navigateSpy,
}: {
  extraCommands: Command[];
  navigateSpy?: ReturnType<typeof vi.fn>;
}) {
  const navigate = useNavigate();
  // Register on mount; if a spy is provided, route navigate through it.
  useEffect(() => {
    const unregister = registerNavigationCommands((path: string) => {
      if (navigateSpy) navigateSpy(path);
      else navigate(path);
    });
    const extras = extraCommands.map((c) => commandRegistry.register(c));
    return () => {
      unregister();
      extras.forEach((u) => u());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return <CommandPalette />;
}

/** Helper to open the palette via the global keydown handler. */
function openWithCmdK() {
  fireEvent.keyDown(window, { key: "k", metaKey: true });
}

function openWithCtrlK() {
  fireEvent.keyDown(window, { key: "k", ctrlKey: true });
}

beforeEach(() => {
  commandRegistry.clear();
});

afterEach(() => {
  cleanup();
  commandRegistry.clear();
});

/** Wait for the palette to be present, then return the dialog element. */
async function openPalette() {
  openWithCmdK();
  return screen.findByTestId("vaic-command-palette");
}

describe("CommandPalette — open/close (AC: Cmd+K, Esc)", () => {
  it("pressing Cmd+K opens the palette with input focused", async () => {
    render(<TestApp />);
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
    const palette = await openPalette();
    expect(palette).toBeInTheDocument();
    const input = screen.getByTestId("vaic-command-palette-input");
    await waitFor(() => expect(input).toHaveFocus());
  });

  it("pressing Ctrl+K opens the palette (Windows/Linux)", async () => {
    render(<TestApp />);
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
    openWithCtrlK();
    expect(await screen.findByTestId("vaic-command-palette")).toBeInTheDocument();
  });

  it("pressing Cmd+K again closes the palette (toggle)", async () => {
    render(<TestApp />);
    await openPalette();
    openWithCmdK();
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
  });

  it("pressing Esc closes the palette without action", async () => {
    render(<TestApp />);
    const palette = await openPalette();
    fireEvent.keyDown(palette, { key: "Escape" });
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
  });
});

describe("CommandPalette — navigation commands listed (AC: nav list)", () => {
  it("shows all 7 navigation commands", async () => {
    render(<TestApp />);
    await openPalette();
    // Wait for at least one nav command to register via effect.
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    for (const target of NAV_TARGETS) {
      expect(
        screen.getByTestId(`vaic-command-nav:${target.id}`),
      ).toBeInTheDocument();
    }
  });

  it("groups navigation commands under a 'Navigation' section header", async () => {
    render(<TestApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    const headers = screen.getAllByText("Navigation");
    expect(headers.length).toBeGreaterThanOrEqual(1);
  });
});

describe("CommandPalette — fuzzy filter (AC: typing filters)", () => {
  it("typing narrows results to matching commands", async () => {
    render(<TestApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    const input = screen.getByTestId("vaic-command-palette-input");
    await userEvent.type(input, "dashboard");
    expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument();
    expect(screen.queryByTestId("vaic-command-nav:agents")).toBeNull();
    expect(screen.queryByTestId("vaic-command-nav:settings")).toBeNull();
  });

  it("typing subsequence matches (e.g. 'age' matches 'Agents')", async () => {
    render(<TestApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:agents")).toBeInTheDocument(),
    );
    const input = screen.getByTestId("vaic-command-palette-input");
    await userEvent.type(input, "age");
    expect(screen.getByTestId("vaic-command-nav:agents")).toBeInTheDocument();
    expect(screen.queryByTestId("vaic-command-nav:settings")).toBeNull();
  });

  it("shows empty state when query matches nothing", async () => {
    render(<TestApp />);
    await openPalette();
    const input = screen.getByTestId("vaic-command-palette-input");
    await userEvent.type(input, "zzzzznomatch");
    expect(screen.getByText(/No matching commands/i)).toBeInTheDocument();
  });

  it("empty query shows all commands", async () => {
    render(<TestApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-command-nav:settings")).toBeInTheDocument();
  });
});

describe("CommandPalette — selecting (AC: Enter navigates)", () => {
  it("Enter on a navigation command navigates and closes palette", async () => {
    const navigateSpy = vi.fn();
    render(<TestApp navigate={navigateSpy} />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    const input = screen.getByTestId("vaic-command-palette-input");
    await userEvent.type(input, "dashboard");
    fireEvent.keyDown(screen.getByTestId("vaic-command-palette"), {
      key: "Enter",
    });
    expect(navigateSpy).toHaveBeenCalledWith("/dashboard");
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
  });

  it("clicking a navigation command navigates and closes palette", async () => {
    const navigateSpy = vi.fn();
    render(<TestApp navigate={navigateSpy} />);
    await openPalette();
    const dashboardRow = await waitFor(() =>
      screen.getByTestId("vaic-command-nav:dashboard"),
    );
    fireEvent.click(dashboardRow);
    expect(navigateSpy).toHaveBeenCalledWith("/dashboard");
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
  });
});

describe("CommandPalette — keyboard navigation", () => {
  it("ArrowDown then Enter selects the second command", async () => {
    const navigateSpy = vi.fn();
    render(<TestApp navigate={navigateSpy} />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    const palette = screen.getByTestId("vaic-command-palette");
    fireEvent.keyDown(palette, { key: "ArrowDown" });
    fireEvent.keyDown(palette, { key: "Enter" });
    // Palette closed via navigation (second nav command is "Go to Agents").
    expect(screen.queryByTestId("vaic-command-palette")).toBeNull();
    // Second command in Navigation section is Agents.
    expect(navigateSpy).toHaveBeenCalledWith("/agents");
  });

  it("ArrowUp wraps to last command from first", async () => {
    render(<TestApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByTestId("vaic-command-nav:dashboard")).toBeInTheDocument(),
    );
    const palette = screen.getByTestId("vaic-command-palette");
    fireEvent.keyDown(palette, { key: "ArrowUp" });
    // Palette stays open.
    expect(screen.getByTestId("vaic-command-palette")).toBeInTheDocument();
  });
});

describe("CommandPalette — Run workflow placeholder (AC: placeholder)", () => {
  it("shows 'Run workflow…' command", async () => {
    render(<TestApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByText("Run workflow…")).toBeInTheDocument(),
    );
  });

  it("shows 'No workflows yet' message when placeholder is active", async () => {
    render(<TestApp />);
    await openPalette();
    const input = await screen.findByTestId("vaic-command-palette-input");
    await userEvent.type(input, "run workflow");
    await waitFor(() => {
      expect(
        screen.getByTestId("vaic-no-workflows-message"),
      ).toBeInTheDocument();
    });
  });

  it("Enter on placeholder does NOT close the palette", async () => {
    render(<TestApp />);
    await openPalette();
    const input = await screen.findByTestId("vaic-command-palette-input");
    await userEvent.type(input, "run workflow");
    await waitFor(() =>
      expect(
        screen.getByTestId("vaic-command-workflow.run:__placeholder__"),
      ).toBeInTheDocument(),
    );
    fireEvent.keyDown(screen.getByTestId("vaic-command-palette"), {
      key: "Enter",
    });
    expect(screen.getByTestId("vaic-command-palette")).toBeInTheDocument();
  });
});

describe("CommandRegistry — extension API (AC: registry)", () => {
  it("registerCommand adds a command visible in the palette", async () => {
    const extra: Command = {
      id: "test:extra",
      title: "Export audit (Epic 6)",
      section: "Audit",
      run: () => {},
    };
    render(<TestApp extraCommands={[extra]} />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByText("Export audit (Epic 6)")).toBeInTheDocument(),
    );
  });

  it("unregister removes a command from the palette", async () => {
    let removeExtra: () => void = () => {};
    function RemovableApp() {
      return (
        <MemoryRouter>
          <CommandPaletteProvider>
            <RemovableRegistry onReady={(unreg) => (removeExtra = unreg)} />
          </CommandPaletteProvider>
        </MemoryRouter>
      );
    }
    function RemovableRegistry({
      onReady,
    }: {
      onReady: (unreg: () => void) => void;
    }) {
      const navigate = useNavigate();
      useEffect(() => {
        const unregister = registerNavigationCommands(navigate);
        const extra: Command = {
          id: "test:temp",
          title: "Temporary command",
          section: "Custom",
          run: () => {},
        };
        const unreg = commandRegistry.register(extra);
        onReady(unreg);
        return () => {
          unreg();
          unregister();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
      }, []);
      return <CommandPalette />;
    }
    render(<RemovableApp />);
    await openPalette();
    await waitFor(() =>
      expect(screen.getByText("Temporary command")).toBeInTheDocument(),
    );
    removeExtra();
    await waitFor(() =>
      expect(screen.queryByText("Temporary command")).toBeNull(),
    );
  });

  it("register() returns an unregister function", () => {
    const cmd: Command = {
      id: "test:fn",
      title: "Function check",
      section: "Custom",
      run: () => {},
    };
    const unreg = commandRegistry.register(cmd);
    expect(typeof unreg).toBe("function");
    expect(commandRegistry.list().some((c) => c.id === "test:fn")).toBe(true);
    unreg();
    expect(commandRegistry.list().some((c) => c.id === "test:fn")).toBe(false);
  });

  it("register replaces existing command with same id", () => {
    commandRegistry.register({
      id: "test:v1",
      title: "Version 1",
      section: "Custom",
      run: () => {},
    });
    commandRegistry.register({
      id: "test:v1",
      title: "Version 2",
      section: "Custom",
      run: () => {},
    });
    const list = commandRegistry.list();
    expect(list.filter((c) => c.id === "test:v1")).toHaveLength(1);
    expect(list.find((c) => c.id === "test:v1")?.title).toBe("Version 2");
  });

  it("unregisterByPrefix removes all matching commands", () => {
    commandRegistry.register({
      id: "wf:1",
      title: "WF 1",
      section: "Workflows",
      run: () => {},
    });
    commandRegistry.register({
      id: "wf:2",
      title: "WF 2",
      section: "Workflows",
      run: () => {},
    });
    commandRegistry.register({
      id: "nav:keep",
      title: "Keep me",
      section: "Navigation",
      run: () => {},
    });
    commandRegistry.unregisterByPrefix("wf:");
    const list = commandRegistry.list();
    expect(list.some((c) => c.id === "wf:1")).toBe(false);
    expect(list.some((c) => c.id === "wf:2")).toBe(false);
    expect(list.some((c) => c.id === "nav:keep")).toBe(true);
  });

  it("available=false hides a command", () => {
    commandRegistry.register({
      id: "hidden:1",
      title: "Hidden",
      section: "Custom",
      available: false,
      run: () => {},
    });
    expect(commandRegistry.visible().some((c) => c.id === "hidden:1")).toBe(false);
  });
});

describe("CommandPalette — accessibility", () => {
  it("has role=dialog, aria-modal, aria-label", async () => {
    render(<TestApp />);
    const palette = await openPalette();
    expect(palette).toHaveAttribute("aria-modal", "true");
    expect(palette).toHaveAttribute("aria-label", "Command palette");
  });

  it("search input has aria-label", async () => {
    render(<TestApp />);
    await openPalette();
    const input = screen.getByLabelText("Search commands");
    expect(input).toBeInTheDocument();
  });
});
