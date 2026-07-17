/* Story 2.8 T1.2 — shared Agent Builder surface types.
 *
 * `TabRegistration` is the contract each tab exposes to the shell via
 * `useRegisterTab` (see AgentBuilderContext.tsx) so the shell never owns a
 * tab's internal form state (Dev Notes "Dirty/save contract").
 */

export type TabKey =
  | "identity"
  | "knowledge-base"
  | "tools"
  | "api-integrations"
  | "prompt"
  | "model";

export interface TabRegistration {
  /** Whether this tab currently has unsaved edits. */
  isDirty: boolean;
  /** Persist the tab's current edits. Rejects/throws on failure. */
  save: () => Promise<void>;
  /** Discard the tab's current edits, reverting to the last-saved baseline. */
  reset: () => void;
}

export type TabDirtyState = Partial<Record<TabKey, boolean>>;

export interface TabCounts {
  documents?: number;
  tools?: number;
  integrations?: number;
}
