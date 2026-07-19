/* Story 2.2 — Unsaved-changes navigation guard (AC #11).
 *
 * The app uses <BrowserRouter> (not a react-router-dom data router), so
 * `useBlocker` (which requires a data router) is not available. This hook
 * provides an equivalent guard for in-app navigation actions (Back to
 * Agents link, tab switches) plus a `beforeunload` handler for full-page
 * unload/refresh while dirty (T7.2).
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface UnsavedChangesGuard {
  /** Wrap a navigation action — runs immediately if not dirty, else opens the confirm dialog. */
  guardedNavigate: (action: () => void) => void;
  /** Props to spread onto <ConfirmDialog open onConfirm onCancel />. */
  confirmProps: {
    open: boolean;
    onConfirm: () => void;
    onCancel: () => void;
  };
}

export function useUnsavedChangesGuard(isDirty: boolean): UnsavedChangesGuard {
  const [hasPending, setHasPending] = useState(false);
  const pendingActionRef = useRef<(() => void) | null>(null);

  const guardedNavigate = useCallback(
    (action: () => void) => {
      if (isDirty) {
        pendingActionRef.current = action;
        setHasPending(true);
      } else {
        action();
      }
    },
    [isDirty],
  );

  const onConfirm = useCallback(() => {
    const action = pendingActionRef.current;
    pendingActionRef.current = null;
    setHasPending(false);
    action?.();
  }, []);

  const onCancel = useCallback(() => {
    pendingActionRef.current = null;
    setHasPending(false);
  }, []);

  // Full-page unload/refresh guard (T7.2).
  useEffect(() => {
    function beforeUnload(e: BeforeUnloadEvent) {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", beforeUnload);
    return () => window.removeEventListener("beforeunload", beforeUnload);
  }, [isDirty]);

  return {
    guardedNavigate,
    confirmProps: { open: hasPending, onConfirm, onCancel },
  };
}
