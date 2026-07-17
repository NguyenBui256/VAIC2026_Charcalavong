/* Test: TabBoundary — UX-DR23 branch order (error -> loading -> empty -> data). */

import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TabBoundary from "./TabBoundary";

describe("TabBoundary", () => {
  it("renders ErrorState with retry when isError", async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(
      <TabBoundary isError errorMessage="Boom" isLoading={false} onRetry={onRetry}>
        <div>content</div>
      </TabBoundary>,
    );
    expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument();
    expect(screen.getByText("Boom")).toBeInTheDocument();
    await user.click(screen.getByText("Retry"));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders a Skeleton when isLoading (never a generic spinner)", () => {
    render(
      <TabBoundary isError={false} isLoading onRetry={vi.fn()}>
        <div>content</div>
      </TabBoundary>,
    );
    expect(screen.getByTestId("vaic-skeleton")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders the emptyState when isEmpty and not loading/erroring", () => {
    render(
      <TabBoundary
        isError={false}
        isLoading={false}
        isEmpty
        emptyState={<div data-testid="empty-marker">nothing here</div>}
        onRetry={vi.fn()}
      >
        <div>content</div>
      </TabBoundary>,
    );
    expect(screen.getByTestId("empty-marker")).toBeInTheDocument();
  });

  it("renders children once loaded, non-empty, non-erroring", () => {
    render(
      <TabBoundary isError={false} isLoading={false} onRetry={vi.fn()}>
        <div data-testid="data-marker">real content</div>
      </TabBoundary>,
    );
    expect(screen.getByTestId("data-marker")).toBeInTheDocument();
  });

  it("error takes precedence over loading and empty", () => {
    render(
      <TabBoundary
        isError
        errorMessage="Boom"
        isLoading
        isEmpty
        emptyState={<div data-testid="empty-marker" />}
        onRetry={vi.fn()}
      >
        <div>content</div>
      </TabBoundary>,
    );
    expect(screen.getByTestId("vaic-error-state")).toBeInTheDocument();
    expect(screen.queryByTestId("vaic-skeleton")).not.toBeInTheDocument();
    expect(screen.queryByTestId("empty-marker")).not.toBeInTheDocument();
  });
});
