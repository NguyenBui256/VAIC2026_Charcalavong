/* Story 2.8 T5.1 — Switch-with-unsaved confirmation (AC #4).
 *
 * Intercepts a tab-switch intent: if the CURRENT tab is dirty, opens a
 * Save/Discard/Cancel `ConfirmDialog`. Save persists then switches (aborts
 * the switch and shows an inline error if save fails, per Dev Notes T5.1);
 * Discard resets then switches; Cancel closes and stays. Esc = Cancel
 * (UX-DR1, handled by ConfirmDialog itself).
 */

import { useCallback, useState } from "react";
import { ConfirmDialog } from "../ui";
import { useAgentBuilder } from "./AgentBuilderContext";
import type { TabKey } from "./agentBuilderTypes";

export interface UseTabSwitchGuardResult {
  /** Wrap a tab-switch intent — runs immediately if the current tab is clean. */
  guardedTabChange: (fromTab: TabKey, toTab: TabKey) => void;
  dialog: React.ReactNode;
  /** Whether the confirmation dialog is currently open (UX-DR3 — callers
   * should suppress their own Primary CTA while this modal's Primary is
   * mounted, e.g. the shell's "Save All"). */
  isOpen: boolean;
}

export function useTabSwitchGuard(onSwitch: (tab: TabKey) => void): UseTabSwitchGuardResult {
  const { getRegistration } = useAgentBuilder();
  const [pending, setPending] = useState<{ from: TabKey; to: TabKey } | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const guardedTabChange = useCallback(
    (fromTab: TabKey, toTab: TabKey) => {
      if (fromTab === toTab) return;
      const registration = getRegistration(fromTab);
      if (registration?.isDirty) {
        setSaveError(null);
        setPending({ from: fromTab, to: toTab });
      } else {
        onSwitch(toTab);
      }
    },
    [getRegistration, onSwitch],
  );

  async function handleSave() {
    if (!pending) return;
    const registration = getRegistration(pending.from);
    try {
      await registration?.save();
      const to = pending.to;
      setPending(null);
      onSwitch(to);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save — still on this tab");
    }
  }

  function handleDiscard() {
    if (!pending) return;
    const registration = getRegistration(pending.from);
    registration?.reset();
    const to = pending.to;
    setPending(null);
    onSwitch(to);
  }

  function handleCancel() {
    setPending(null);
    setSaveError(null);
  }

  const dialog = (
    <ConfirmDialog
      open={pending !== null}
      title="Save changes before leaving?"
      body="This tab has unsaved changes."
      confirmLabel="Save"
      cancelLabel="Cancel"
      tertiaryAction={{ label: "Discard", onClick: handleDiscard }}
      error={saveError}
      onConfirm={handleSave}
      onCancel={handleCancel}
    />
  );

  return { guardedTabChange, dialog, isOpen: pending !== null };
}
