/* Story 2.8 T1.3 — Agent Builder shell context.
 *
 * Owns the map of per-tab `TabRegistration` handles (children register via
 * `useRegisterTab`), an `anyDirty` selector, and `saveAll()` (Identity first,
 * then the rest — Identity creates the Agent record on first save so other
 * tabs' saves are meaningless before it exists).
 *
 * The context has a no-op DEFAULT value (not `undefined`) so tabs can call
 * `useRegisterTab` safely even when unit-tested standalone, outside an
 * `AgentBuilderProvider` (Dev Notes "graceful degradation").
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { TabKey, TabRegistration } from "./agentBuilderTypes";

export interface AgentBuilderContextValue {
  registerTab: (key: TabKey, registration: TabRegistration) => void;
  unregisterTab: (key: TabKey) => void;
  dirtyTabs: Partial<Record<TabKey, boolean>>;
  anyDirty: boolean;
  /** Save every currently-dirty tab, Identity first. Throws on first failure. */
  saveAll: () => Promise<void>;
  /** Get a tab's registration (used by the switch-guard). */
  getRegistration: (key: TabKey) => TabRegistration | undefined;
}

const noopRegistration: TabRegistration = {
  isDirty: false,
  save: async () => {},
  reset: () => {},
};

const AgentBuilderContext = createContext<AgentBuilderContextValue>({
  registerTab: () => {},
  unregisterTab: () => {},
  dirtyTabs: {},
  anyDirty: false,
  saveAll: async () => {},
  getRegistration: () => noopRegistration,
});

// Identity first — it creates the Agent record on first save (AC #7); the
// rest are ordered to match the tab registry for a predictable Save All.
const SAVE_ORDER: TabKey[] = ["identity", "knowledge-base", "tools", "prompt", "model"];

export function AgentBuilderProvider({ children }: { children: ReactNode }) {
  const registrationsRef = useRef<Partial<Record<TabKey, TabRegistration>>>({});
  const [dirtyTabs, setDirtyTabs] = useState<Partial<Record<TabKey, boolean>>>({});

  const registerTab = useCallback((key: TabKey, registration: TabRegistration) => {
    registrationsRef.current[key] = registration;
    setDirtyTabs((prev) =>
      prev[key] === registration.isDirty ? prev : { ...prev, [key]: registration.isDirty },
    );
  }, []);

  const unregisterTab = useCallback((key: TabKey) => {
    delete registrationsRef.current[key];
    setDirtyTabs((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const getRegistration = useCallback(
    (key: TabKey) => registrationsRef.current[key],
    [],
  );

  const saveAll = useCallback(async () => {
    for (const key of SAVE_ORDER) {
      const registration = registrationsRef.current[key];
      if (registration?.isDirty) {
        await registration.save();
      }
    }
  }, []);

  const anyDirty = useMemo(() => Object.values(dirtyTabs).some(Boolean), [dirtyTabs]);

  const value = useMemo<AgentBuilderContextValue>(
    () => ({ registerTab, unregisterTab, dirtyTabs, anyDirty, saveAll, getRegistration }),
    [registerTab, unregisterTab, dirtyTabs, anyDirty, saveAll, getRegistration],
  );

  return (
    <AgentBuilderContext.Provider value={value}>{children}</AgentBuilderContext.Provider>
  );
}

/** Register (and keep up to date) a tab's `{isDirty, save, reset}` handle. */
export function useRegisterTab(key: TabKey, registration: TabRegistration): void {
  const { registerTab, unregisterTab } = useContext(AgentBuilderContext);
  const registrationRef = useRef(registration);
  registrationRef.current = registration;

  // Re-announce on every render (post-commit, not render-phase) so the
  // shell always has the latest save/reset closure over the tab's current
  // form state — registerTab() is a cheap ref write + a state update only
  // when the dirty flag actually flips.
  useEffect(() => {
    registerTab(key, registrationRef.current);
  });

  // Unregister only on unmount / key change — NOT on every render, so the
  // tab doesn't flicker out of the registry between renders.
  useEffect(() => {
    return () => unregisterTab(key);
  }, [key, unregisterTab]);
}

export function useAgentBuilder(): AgentBuilderContextValue {
  return useContext(AgentBuilderContext);
}
