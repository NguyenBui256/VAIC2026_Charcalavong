/* Test: AppShell renders sidebar nav items.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AppShell from "./AppShell";

// Mock useAuth to return authenticated state
vi.mock("../hooks/useAuth", () => ({
  useAuth: () => ({
    user: {
      id: "u1",
      tenant_id: "t1",
      department_id: "d1",
      email: "test@shb.vn",
      role: "analyst",
    },
    token: "fake-token",
    isAuthenticated: true,
    logout: vi.fn(),
  }),
}));

function renderShell() {
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<div>Dashboard content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the sidebar with all nav items", () => {
    renderShell();
    const navLabels = [
      "Dashboard",
      "Agents",
      "Workflows",
      "Mini-Apps",
      "Actions",
      "Audit",
      "Settings",
    ];
    navLabels.forEach((label) => {
      expect(screen.getByText(label)).toBeInTheDocument();
    });
  });

  it("renders the topbar with wordmark and breadcrumb", () => {
    renderShell();
    expect(screen.getByTestId("vaic-topbar")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-breadcrumb")).toBeInTheDocument();
  });

  it("renders the Run button in topbar", () => {
    renderShell();
    expect(screen.getByText("Run")).toBeInTheDocument();
  });
});
