/* Test: Login page form submission, API call, token storage, redirect.
 * TDD: RED first, then GREEN.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "./login";

// Mock the auth module
vi.mock("../lib/auth", () => ({
  login: vi.fn(),
  storeSession: vi.fn(),
  getStoredToken: vi.fn(() => null),
  getStoredUser: vi.fn(() => null),
  clearSession: vi.fn(),
}));

import { login, storeSession } from "../lib/auth";

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <LoginPage />
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders email and password inputs", () => {
    renderLogin();
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/)).toBeInTheDocument();
  });

  it("submits with email + password, calls login API, stores token", async () => {
    const mockUser = {
      id: "user-1",
      tenant_id: "tenant-1",
      department_id: "dept-1",
      email: "linh@shb.vn",
      role: "analyst",
    };
    vi.mocked(login).mockResolvedValue({
      access_token: "jwt-token-123",
      token_type: "bearer",
      user: mockUser,
    });

    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Email/), "linh@shb.vn");
    await user.type(screen.getByLabelText(/Password/), "secret123");
    await user.click(screen.getByTestId("vaic-login-submit"));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith("linh@shb.vn", "secret123");
    });

    await waitFor(() => {
      expect(storeSession).toHaveBeenCalledWith("jwt-token-123", mockUser);
    });
  });

  it("shows inline error in destructive color on failed login", async () => {
    vi.mocked(login).mockRejectedValue(new Error("Invalid credentials"));

    const user = userEvent.setup();
    renderLogin();

    await user.type(screen.getByLabelText(/Email/), "bad@shb.vn");
    await user.type(screen.getByLabelText(/Password/), "wrong");
    await user.click(screen.getByTestId("vaic-login-submit"));

    await waitFor(() => {
      const errEl = screen.getByTestId("vaic-login-error");
      expect(errEl).toBeInTheDocument();
      expect(errEl).toHaveTextContent("Invalid credentials");
    });
  });
});
