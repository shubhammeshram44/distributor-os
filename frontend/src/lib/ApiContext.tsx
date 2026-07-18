"use client";

import React, { createContext, useContext, useState, useCallback } from "react";

interface ApiContextType {
  apiBase: string;
  token: string | null;
  setToken: (token: string | null) => void;
  fetch: <T = any>(endpoint: string, options?: RequestInit) => Promise<{ data?: T; error?: string; status: number }>;
  isLoading: boolean;
  error: string | null;
}

const ApiContext = createContext<ApiContextType | undefined>(undefined);

export function ApiProvider({ children }: { children: React.ReactNode }) {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load token from localStorage on mount
  React.useEffect(() => {
    const storedToken = localStorage.getItem("accessToken");
    if (storedToken) {
      setToken(storedToken);
    }
  }, []);

  const fetch = useCallback(
    async <T = any,>(
      endpoint: string,
      options?: RequestInit
    ): Promise<{ data?: T; error?: string; status: number }> => {
      setIsLoading(true);
      setError(null);

      try {
        const url = endpoint.startsWith("http") ? endpoint : `${apiBase}${endpoint}`;
        const headers = {
          "Accept": "application/json",
          "Content-Type": "application/json",
          ...(token && { "Authorization": `Bearer ${token}` }),
          ...options?.headers
        };

        const response = await window.fetch(url, {
          ...options,
          credentials: "include",
          headers
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
          const errorMsg = data.detail || data.message || `Error: ${response.status}`;
          setError(errorMsg);
          return { error: errorMsg, status: response.status };
        }

        return { data: data as T, status: response.status };
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : "Network error";
        setError(errorMsg);
        return { error: errorMsg, status: 0 };
      } finally {
        setIsLoading(false);
      }
    },
    [apiBase, token]
  );

  return (
    <ApiContext.Provider value={{ apiBase, token, setToken, fetch, isLoading, error }}>
      {children}
    </ApiContext.Provider>
  );
}

export function useApi() {
  const context = useContext(ApiContext);
  if (!context) {
    throw new Error("useApi must be used within ApiProvider");
  }
  return context;
}
