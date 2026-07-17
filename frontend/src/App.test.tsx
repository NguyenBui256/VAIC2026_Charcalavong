/* Test: Unauthenticated user hitting /dashboard redirects to /login.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppRoutes } from "./App";

// Mock auth — unauthenticated
vi.mock("./lib/auth", () => ({
  isAuthenticated: vi.fn(() => false),
  getStoredToken: vi.fn(() => null),
  getStoredUser: vi.fn(() => null),
  clearSession: vi.fn(),
  logout: vi.fn(),
}));

import { isAuthenticated } from "./lib/auth";

function renderRoutesAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

describe("Route guards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isAuthenticated).mockReturnValue(false);
  });

  it("redirects unauthenticated user from /dashboard to /login", () => {
    renderRoutesAt("/dashboard");
    expect(screen.getByTestId("vaic-login-page")).toBeInTheDocument();
  });

  it("shows login page for unauthenticated user at root", () => {
    renderRoutesAt("/");
    // Root redirects to /dashboard → which redirects to /login
    expect(screen.getByTestId("vaic-login-page")).toBeInTheDocument();
  });
});
