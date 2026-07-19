"use client";

import { retryWithBackoff, getErrorMessage, logError, formatErrorMessage } from "./errorHandling";

export interface ApiRequestConfig extends RequestInit {
  retryable?: boolean;
  timeout?: number;
}

export interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: number;
  message?: string;
}

class ApiClient {
  private baseUrl: string;
  private token: string | null = null;
  private requestTimeout: number = 30000; // 30 seconds default

  constructor(baseUrl: string = "") {
    this.baseUrl = baseUrl || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
    this.loadToken();
  }

  private loadToken(): void {
    if (typeof window !== "undefined") {
      this.token = localStorage.getItem("accessToken");
    }
  }

  setToken(token: string | null): void {
    this.token = token;
    if (token) {
      localStorage.setItem("accessToken", token);
    } else {
      localStorage.removeItem("accessToken");
    }
  }

  private getHeaders(custom?: HeadersInit): HeadersInit {
    return {
      "Accept": "application/json",
      "Content-Type": "application/json",
      ...(this.token && { "Authorization": `Bearer ${this.token}` }),
      ...custom
    };
  }

  private createAbortController(timeout: number): { controller: AbortController; timeoutId: NodeJS.Timeout } {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);
    return { controller, timeoutId };
  }

  async get<T = any>(
    endpoint: string,
    config?: ApiRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...config, method: "GET" });
  }

  async post<T = any>(
    endpoint: string,
    body?: any,
    config?: ApiRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      ...config,
      method: "POST",
      body: body ? JSON.stringify(body) : undefined
    });
  }

  async put<T = any>(
    endpoint: string,
    body?: any,
    config?: ApiRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      ...config,
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined
    });
  }

  async patch<T = any>(
    endpoint: string,
    body?: any,
    config?: ApiRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, {
      ...config,
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined
    });
  }

  async delete<T = any>(
    endpoint: string,
    config?: ApiRequestConfig
  ): Promise<ApiResponse<T>> {
    return this.request<T>(endpoint, { ...config, method: "DELETE" });
  }

  private async request<T = any>(
    endpoint: string,
    config: ApiRequestConfig = {}
  ): Promise<ApiResponse<T>> {
    const url = endpoint.startsWith("http") ? endpoint : `${this.baseUrl}${endpoint}`;
    const timeout = config.timeout || this.requestTimeout;
    const retryable = config.retryable !== false;

    const makeRequest = async (): Promise<ApiResponse<T>> => {
      const { controller, timeoutId } = this.createAbortController(timeout);

      try {
        const response = await fetch(url, {
          ...config,
          credentials: "include",
          headers: this.getHeaders(config.headers),
          signal: controller.signal
        });

        clearTimeout(timeoutId);

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          const error = getErrorMessage({
            status: response.status,
            message: data.detail || data.message || `HTTP ${response.status}`,
            detail: data.error
          });

          logError(error, `${config.method || "GET"} ${endpoint}`);

          return {
            error: formatErrorMessage(error),
            status: response.status,
            message: data.detail || data.message
          };
        }

        return { data: data as T, status: response.status };
      } catch (err: any) {
        clearTimeout(timeoutId);

        if (err.name === "AbortError") {
          return {
            error: "Request timeout. Please try again.",
            status: 408
          };
        }

        const error = getErrorMessage(err);
        logError(error, `${config.method || "GET"} ${endpoint}`);

        return {
          error: formatErrorMessage(error),
          status: error.status
        };
      }
    };

    if (retryable) {
      try {
        return await retryWithBackoff(makeRequest, {
          maxRetries: 2,
          initialDelay: 1000
        });
      } catch {
        return makeRequest();
      }
    }

    return makeRequest();
  }
}

export const apiClient = new ApiClient();
