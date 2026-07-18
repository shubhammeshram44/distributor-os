import React from "react";

/**
 * Debounce hook for search inputs and form changes
 * Delays state updates by specified milliseconds
 */
export function useDebounce<T>(value: T, delayMs: number = 300): [T, boolean] {
  const [debouncedValue, setDebouncedValue] = React.useState<T>(value);
  const [isDebouncing, setIsDebouncing] = React.useState(false);

  React.useEffect(() => {
    setIsDebouncing(true);
    const handler = setTimeout(() => {
      setDebouncedValue(value);
      setIsDebouncing(false);
    }, delayMs);

    return () => clearTimeout(handler);
  }, [value, delayMs]);

  return [debouncedValue, isDebouncing];
}

/**
 * Debounce function for generic callbacks
 * Returns a debounced version of the provided function
 */
export function debounce<T extends (...args: any[]) => any>(
  func: T,
  delayMs: number = 300
): (...args: Parameters<T>) => void {
  let timeoutId: NodeJS.Timeout | null = null;

  return function (...args: Parameters<T>) {
    if (timeoutId) clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      func(...args);
    }, delayMs);
  };
}

/**
 * Request timeout wrapper - resolves/rejects a fetch after specified time
 * High impact: prevents hanging requests from blocking UI
 */
export function fetchWithTimeout(
  url: string,
  options: RequestInit & { timeout?: number } = {}
): Promise<Response> {
  const { timeout = 10000, ...fetchOptions } = options;
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  return fetch(url, { ...fetchOptions, signal: controller.signal })
    .finally(() => clearTimeout(timeoutId))
    .catch(err => {
      if (err.name === "AbortError") {
        throw new Error(`Request timeout after ${timeout}ms`);
      }
      throw err;
    });
}

/**
 * Page Visibility Hook - detects if page is visible/focused
 * High impact: pause API polling when tab is not visible
 * Reduces server load and improves battery life on mobile
 */
export function usePageVisibility(): boolean {
  const [isVisible, setIsVisible] = React.useState(true);

  React.useEffect(() => {
    const handleVisibilityChange = () => {
      setIsVisible(document.visibilityState === "visible");
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, []);

  return isVisible;
}

/**
 * Conditional polling hook - returns true if should poll
 * Use with usePageVisibility to pause polling when tab is hidden
 * Example: const shouldPoll = usePageVisibility() && !isDebouncing;
 */
export function useConditionalPolling(
  condition: boolean,
  pollFn: () => Promise<any>,
  intervalMs: number = 3000
): void {
  React.useEffect(() => {
    if (!condition) return;

    const pollInterval = setInterval(() => {
      pollFn().catch(err => console.error("Poll error:", err));
    }, intervalMs);

    return () => clearInterval(pollInterval);
  }, [condition, pollFn, intervalMs]);
}
