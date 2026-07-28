"use client";
import { useState, useEffect } from "react";

const PERMISSIONS_KEY = "user_permissions";
const ROLE_KEY = "user_role";

export function usePermissions() {
    const [permissions, setPermissions] = useState<string[]>([]);
    const [role, setRole] = useState<string>("");
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const fetchPermissions = async () => {
            try {
                const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
                const token = localStorage.getItem("access_token");

                if (!token) {
                    setIsLoading(false);
                    return;
                }

                const res = await fetch(`${apiBase}/api/v1/users/permissions`, {
                    headers: { "Authorization": `Bearer ${token}` }
                });

                if (res.ok) {
                    const data = await res.json();
                    const perms = data.permissions || [];
                    const userRole = data.role || "";

                    setPermissions(perms);
                    setRole(userRole);
                    localStorage.setItem(PERMISSIONS_KEY, JSON.stringify(perms));
                    localStorage.setItem(ROLE_KEY, userRole);
                }
            } catch (e) {
                console.error("Failed to fetch permissions:", e);
            } finally {
                setIsLoading(false);
            }
        };

        fetchPermissions();
    }, []);

    const has = (permission: string): boolean => {
        if (isLoading) return true;  // show everything while loading
        if (role === "SUPER_ADMIN") return true;  // SUPER_ADMIN sees everything
        return permissions.includes(permission);
    };

    const clearPermissions = () => {
        localStorage.removeItem(PERMISSIONS_KEY);
        localStorage.removeItem(ROLE_KEY);
        setPermissions([]);
        setRole("");
    };

    return { permissions, role, has, isLoading, clearPermissions };
}
