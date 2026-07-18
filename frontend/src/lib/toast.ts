/**
 * Toast notification utilities
 * Provides better toast management with auto-dismiss, stacking, etc.
 */

export type ToastType = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration: number;
  timestamp: number;
}

// Simple toast manager for client-side state
let toastId = 0;
let toastListeners: ((toasts: Toast[]) => void)[] = [];
let toasts: Toast[] = [];

/**
 * Subscribe to toast changes
 */
export function subscribeToToasts(listener: (toasts: Toast[]) => void): () => void {
  toastListeners.push(listener);
  return () => {
    toastListeners = toastListeners.filter(l => l !== listener);
  };
}

/**
 * Emit toast changes to all listeners
 */
function notifyListeners() {
  toastListeners.forEach(listener => listener([...toasts]));
}

/**
 * Show a toast notification with auto-dismiss
 * @param message - Toast message
 * @param type - Toast type (success, error, info, warning)
 * @param duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
 */
export function showToast(message: string, type: ToastType = "info", duration: number = 4000): string {
  const id = `toast-${++toastId}`;
  const newToast: Toast = {
    id,
    message,
    type,
    duration,
    timestamp: Date.now()
  };

  toasts = [...toasts, newToast];
  notifyListeners();

  // Auto-dismiss after duration
  if (duration > 0) {
    setTimeout(() => {
      dismissToast(id);
    }, duration);
  }

  return id;
}

/**
 * Dismiss a specific toast
 */
export function dismissToast(id: string): void {
  toasts = toasts.filter(t => t.id !== id);
  notifyListeners();
}

/**
 * Dismiss all toasts
 */
export function dismissAllToasts(): void {
  toasts = [];
  notifyListeners();
}

/**
 * Get current toasts
 */
export function getToasts(): Toast[] {
  return [...toasts];
}

/**
 * Show success toast
 */
export function showSuccess(message: string, duration: number = 3000): string {
  return showToast(message, "success", duration);
}

/**
 * Show error toast
 */
export function showError(message: string, duration: number = 5000): string {
  return showToast(message, "error", duration);
}

/**
 * Show info toast
 */
export function showInfo(message: string, duration: number = 4000): string {
  return showToast(message, "info", duration);
}

/**
 * Show warning toast
 */
export function showWarning(message: string, duration: number = 4000): string {
  return showToast(message, "warning", duration);
}
