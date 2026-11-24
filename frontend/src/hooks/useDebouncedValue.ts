import { useEffect, useState } from "react";

/**
 * Returns `value` after it has stayed unchanged for `delay` milliseconds.
 * Used so search and location inputs do not fire a request per keystroke.
 */
export function useDebouncedValue<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
