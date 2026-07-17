/* Test: Toast — shows on useToast().show(), auto-dismisses, close button works. */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { ToastProvider, useToast } from "./Toast";

function TriggerButton({ variant }: { variant?: "success" | "error" }) {
  const { show } = useToast();
  return (
    <button onClick={() => show("Agent saved", variant)}>Trigger</button>
  );
}

describe("Toast", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows a toast with aria-live region when show() is called", () => {
    render(
      <ToastProvider>
        <TriggerButton />
      </ToastProvider>,
    );

    expect(screen.queryByTestId("vaic-toast")).not.toBeInTheDocument();

    act(() => {
      fireEvent.click(screen.getByText("Trigger"));
    });

    expect(screen.getByTestId("vaic-toast")).toBeInTheDocument();
    expect(screen.getByText("Agent saved")).toBeInTheDocument();
    expect(screen.getByTestId("vaic-toast-stack")).toHaveAttribute(
      "aria-live",
      "polite",
    );
  });

  it("auto-dismisses after the timeout", () => {
    render(
      <ToastProvider>
        <TriggerButton />
      </ToastProvider>,
    );
    act(() => {
      fireEvent.click(screen.getByText("Trigger"));
    });
    expect(screen.getByTestId("vaic-toast")).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(4000);
    });

    expect(screen.queryByTestId("vaic-toast")).not.toBeInTheDocument();
  });

  it("dismisses when the close button is clicked", () => {
    render(
      <ToastProvider>
        <TriggerButton />
      </ToastProvider>,
    );
    act(() => {
      fireEvent.click(screen.getByText("Trigger"));
    });
    act(() => {
      fireEvent.click(screen.getByLabelText("Dismiss notification"));
    });
    expect(screen.queryByTestId("vaic-toast")).not.toBeInTheDocument();
  });

  it("throws if useToast is used outside ToastProvider", () => {
    function Bare() {
      useToast();
      return null;
    }
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => render(<Bare />)).toThrow(
      "useToast must be used within a ToastProvider",
    );
    spy.mockRestore();
  });
});
