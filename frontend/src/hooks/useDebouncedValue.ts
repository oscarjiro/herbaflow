import { useEffect, useState } from "react";

/**
 * Returns a debounced copy of `value` that updates only after `delayMs`
 * milliseconds have elapsed without another change.
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(id);
  }, [value, delayMs]);

  return debounced;
}
