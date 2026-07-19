/* Story 2.2 — Toast primitive (UX-DR9 durations.toast = 280ms).
 *
 * Transient success/error notification. Mounted once at the app root via
 * `ToastProvider`; any component calls `useToast().show(message, variant)`.
 * `aria-live="polite"` announces the toast to screen readers without
 * interrupting.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { ICON_STROKE_WIDTH } from "../../lib/icons";
import { durations, easings } from "../../lib/motion";

export type ToastVariant = "success" | "error";

interface ToastItem {
  id: string;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  /** Show a transient toast. Auto-dismisses after ~4s. */
  show: (message: string, variant?: ToastVariant) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const AUTO_DISMISS_MS = 4000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const show = useCallback(
    (message: string, variant: ToastVariant = "success") => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      setToasts((prev) => [...prev, { id, message, variant }]);
      const timer = setTimeout(() => dismiss(id), AUTO_DISMISS_MS);
      timers.current.set(id, timer);
    },
    [dismiss],
  );

  useEffect(() => {
    const timersMap = timers.current;
    return () => {
      timersMap.forEach((t) => clearTimeout(t));
    };
  }, []);

  return (
    <ToastContext.Provider value={{ show }}>
      {children}
      <div
        className="vaic-toast-stack"
        aria-live="polite"
        data-testid="vaic-toast-stack"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`vaic-toast vaic-toast-${t.variant}`}
            role="status"
            data-testid="vaic-toast"
            style={{
              animationDuration: `${durations.toast}ms`,
              animationTimingFunction: easings.out,
            }}
          >
            {t.variant === "success" ? (
              <CheckCircle2
                size={16}
                strokeWidth={ICON_STROKE_WIDTH}
                aria-hidden="true"
              />
            ) : (
              <XCircle size={16} strokeWidth={ICON_STROKE_WIDTH} aria-hidden="true" />
            )}
            <span>{t.message}</span>
            <button
              type="button"
              className="vaic-toast-close vaic-focusable"
              aria-label="Dismiss notification"
              onClick={() => dismiss(t.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

/** Read the toast API from context. Must be used within `ToastProvider`. */
export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}
