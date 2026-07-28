import { useState, useEffect } from "react";

const PERMISSIONS_CACHE_KEY = "user_permissions";

export function usePermissions() {
    const [permissions, setPermissions] = useState<string[]>(() => {
        if (typeof window !== "undefined") {
            try {
                const cached = localStorage.getItem(PERMISSIONS_CACHE_KEY);
                return cached ? JSON.parse(cached) : [];
            } catch {
                return [];
            }
        }
        return [];
    });

    const [isLoading, setIsLoading] = useState(() => {
        if (typeof window !== "undefined") {
            try {
                const cached = localStorage.getItem(PERMISSIONS_CACHE_KEY);
                return cached ? false : true;
            } catch {
                return true;
            }
        }
        return true;
    });

    const fetchPermissions = async () => {
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
            const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
            const res = await fetch(`${apiBase}/api/v1/users/permissions`, {
                headers: token ? { Authorization: `Bearer ${token}` } : {}
            });
            if (res.ok) {
                const data = await res.json();
                setPermissions(data.permissions);
                if (typeof window !== "undefined") {
                    localStorage.setItem(PERMISSIONS_CACHE_KEY, JSON.stringify(data.permissions));
                }
            }
        } catch (e) {
            console.error("Failed to fetch permissions", e);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchPermissions();
    }, []);

    const has = (permission: string): boolean => {
        return permissions.includes(permission);
    };

    const clearPermissions = () => {
        if (typeof window !== "undefined") {
            localStorage.removeItem(PERMISSIONS_CACHE_KEY);
        }
        setPermissions([]);
        setIsLoading(true);
    };

    return { permissions, has, isLoading, fetchPermissions, clearPermissions };
}
