/* Test: ConfirmDialog — renders when open, Esc/Cancel/Confirm callbacks fire. */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConfirmDialog from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("renders nothing when open=false", () => {
    render(
      <ConfirmDialog
        open={false}
        title="Discard unsaved changes?"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByTestId("vaic-confirm-dialog")).not.toBeInTheDocument();
  });

  it("renders title and body when open=true", () => {
    render(
      <ConfirmDialog
        open
        title="Discard unsaved changes?"
        body="Your changes will be lost."
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("vaic-confirm-dialog")).toBeInTheDocument();
    expect(screen.getByText("Discard unsaved changes?")).toBeInTheDocument();
    expect(screen.getByText("Your changes will be lost.")).toBeInTheDocument();
  });

  it("calls onConfirm when the confirm button is clicked", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        open
        title="Discard?"
        confirmLabel="Discard"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );
    await user.click(screen.getByText("Discard"));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when the cancel button is clicked", async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog open title="Discard?" onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    await user.click(screen.getByText("Cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("calls onCancel when Esc is pressed", () => {
    const onCancel = vi.fn();
    render(
      <ConfirmDialog open title="Discard?" onConfirm={vi.fn()} onCancel={onCancel} />,
    );
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it("renders a three-button Save/Discard/Cancel variant via tertiaryAction (Story 2.8 AC #4)", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const onTertiary = vi.fn();
    const user = userEvent.setup();
    render(
      <ConfirmDialog
        open
        title="Save changes before leaving?"
        confirmLabel="Save"
        cancelLabel="Cancel"
        tertiaryAction={{ label: "Discard", onClick: onTertiary }}
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );
    expect(screen.getByText("Save")).toBeInTheDocument();
    expect(screen.getByText("Discard")).toBeInTheDocument();
    expect(screen.getByText("Cancel")).toBeInTheDocument();

    await user.click(screen.getByText("Discard"));
    expect(onTertiary).toHaveBeenCalledTimes(1);
  });

  it("shows an inline error above the actions when `error` is set", () => {
    render(
      <ConfirmDialog
        open
        title="Save changes before leaving?"
        error="Failed to save Agent"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByTestId("vaic-confirm-dialog-error")).toHaveTextContent(
      "Failed to save Agent",
    );
  });
});
