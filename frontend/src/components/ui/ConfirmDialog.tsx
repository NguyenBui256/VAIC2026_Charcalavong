/* Story 2.2 — ConfirmDialog primitive (UX-DR1 escape routes, UX-DR9 motion).
 *
 * Modal confirm (title, body, Confirm/Cancel). Reuses the overlay + Esc-to-
 * close pattern from CommandPalette.tsx, and `durations.modal` / `easings.modal`.
 */

import { useEffect, useRef } from "react";
import { durations, easings } from "../../lib/motion";
import Button from "./Button";

export interface ConfirmDialogTertiaryAction {
  label: string;
  onClick: () => void;
}

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  body?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
  /** Story 2.8 T5.2 — optional third action (e.g. "Discard") for the
   * Save/Discard/Cancel switch-with-unsaved-changes confirmation (AC #4).
   * Rendered as a destructive-styled button between Cancel and Confirm. */
  tertiaryAction?: ConfirmDialogTertiaryAction;
  /** Inline error shown above the actions (e.g. Save failed — stay open). */
  error?: string | null;
}

export default function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
  tertiaryAction,
  error,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  // Esc closes (Cancel semantics) — UX-DR1 escape routes.
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    const id = window.setTimeout(() => dialogRef.current?.focus(), 0);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.clearTimeout(id);
    };
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      role="presentation"
      className="vaic-confirm-overlay"
      data-testid="vaic-confirm-overlay"
      style={{
        animationDuration: `${durations.modal}ms`,
        animationTimingFunction: easings.modal,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="vaic-confirm-dialog-title"
        tabIndex={-1}
        className="vaic-confirm-dialog"
        data-testid="vaic-confirm-dialog"
        style={{
          animationDuration: `${durations.modal}ms`,
          animationTimingFunction: easings.modal,
        }}
      >
        <h3 id="vaic-confirm-dialog-title" className="text-h3">
          {title}
        </h3>
        {body && (
          <p className="text-body" style={{ color: "var(--color-text-tertiary)" }}>
            {body}
          </p>
        )}
        {error && (
          <div className="vaic-inline-alert" role="alert" data-testid="vaic-confirm-dialog-error">
            {error}
          </div>
        )}
        <div className="vaic-confirm-actions">
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel}
          </Button>
          {tertiaryAction && (
            <Button variant="destructive" onClick={tertiaryAction.onClick}>
              {tertiaryAction.label}
            </Button>
          )}
          {/* Two-button dialogs (e.g. Delete confirmations) keep the
              original destructive-styled confirm action; the three-button
              Save/Discard/Cancel variant (AC #4) promotes Save to Primary
              since Discard already carries the destructive styling. */}
          <Button variant={tertiaryAction ? "primary" : "destructive"} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
