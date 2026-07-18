export interface ApiError {
  status: number;
  message: string;
  details?: string;
  code?: string;
  retryable?: boolean;
}

export interface RetryConfig {
  maxRetries: number;
  initialDelay: number;
  maxDelay: number;
  backoffMultiplier: number;
}

const DEFAULT_RETRY_CONFIG: RetryConfig = {
  maxRetries: 3,
  initialDelay: 1000,
  maxDelay: 10000,
  backoffMultiplier: 2
};

export function getErrorMessage(error: unknown): ApiError {
  if (error instanceof Error) {
    return {
      status: 500,
      message: error.message,
      details: error.stack,
      retryable: false
    };
  }

  if (typeof error === "object" && error !== null) {
    const err = error as any;
    return {
      status: err.status || 500,
      message: err.message || "An unknown error occurred",
      details: err.detail || err.description,
      code: err.code,
      retryable: isRetryableError(err.status)
    };
  }

  return {
    status: 500,
    message: String(error) || "An unknown error occurred",
    retryable: false
  };
}

export function isRetryableError(status: number): boolean {
  // Retry on 5xx server errors and specific 4xx errors
  return (
    status >= 500 ||
    status === 408 || // Request Timeout
    status === 429    // Too Many Requests
  );
}

export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  config: Partial<RetryConfig> = {}
): Promise<T> {
  const finalConfig = { ...DEFAULT_RETRY_CONFIG, ...config };
  let lastError: any;
  let delay = finalConfig.initialDelay;

  for (let attempt = 0; attempt <= finalConfig.maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      const apiError = getErrorMessage(error);

      // Don't retry if not retryable or last attempt
      if (!apiError.retryable || attempt === finalConfig.maxRetries) {
        throw error;
      }

      // Wait before retrying
      await new Promise((resolve) => setTimeout(resolve, delay));
      delay = Math.min(delay * finalConfig.backoffMultiplier, finalConfig.maxDelay);
    }
  }

  throw lastError;
}

export function formatErrorMessage(error: ApiError): string {
  // User-friendly error messages based on status code
  const errorMessages: Record<number, string> = {
    400: "Invalid request. Please check your input.",
    401: "Unauthorized. Please log in again.",
    403: "You don't have permission to perform this action.",
    404: "The requested resource was not found.",
    408: "Request timed out. Please try again.",
    429: "Too many requests. Please wait a moment and try again.",
    500: "Server error. Please try again later.",
    502: "Service temporarily unavailable. Please try again later.",
    503: "Service maintenance. Please try again later.",
    504: "Gateway timeout. Please try again later."
  };

  return errorMessages[error.status] || error.message || "An error occurred. Please try again.";
}

export function shouldShowRetryButton(error: ApiError): boolean {
  return Boolean(error.retryable) && error.status >= 500;
}

export function logError(error: ApiError, context: string = ""): void {
  const timestamp = new Date().toISOString();
  const log = {
    timestamp,
    context,
    status: error.status,
    message: error.message,
    code: error.code,
    details: error.details
  };

  // Log to console in development
  if (process.env.NODE_ENV === "development") {
    console.error("[API Error]", log);
  }

  // In production, send to error tracking service
  if (process.env.NODE_ENV === "production") {
    // TODO: Send to Sentry, LogRocket, or similar service
    // sendErrorToTracker(log);
  }
}
