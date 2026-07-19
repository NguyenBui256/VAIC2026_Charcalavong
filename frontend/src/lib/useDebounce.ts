/* Story 2.2 — Generic debounce hook (used by the Agent list search input, AC #3). */

import { useEffect, useState } from "react";

export function useDebounce<T>(value: T, delayMs = 200): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}
