"use client";

import React, { useState, useEffect, useCallback } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import { useDebounce } from "@/lib/debounce";
import {
  Search,
  Loader2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  X,
  Plus,
  Shield,
  Users,
  Lock,
  UserCheck,
  Edit2
} from "lucide-react";

interface UserRow {
  id: string;
  full_name: string;
  phone_number: string | null;
  email_or_phone: string;
  role: string;
  is_active: boolean;
}

interface RolePrivilege {
  role: string;
  title: string;
  description: string;
  permissions: {
    feature: string;
    allowed: boolean;
    description: string;
  }[];
}

const ROLE_PRIVILEGES_MATRIX: RolePrivilege[] = [
  {
    role: "SUPER_ADMIN",
    title: "Super Administrator",
    description: "Unrestricted system-wide master override settings configuration access.",
    permissions: [
      { feature: "Workspace Configuration", allowed: true, description: "Full tenant administration controls" },
      { feature: "Financial Ledgers & Statements", allowed: true, description: "Unrestricted auditing and debit/credit ledger access" },
      { feature: "Fulfillment & Driver Runs", allowed: true, description: "Allocate vehicle deliveries and assign driver logs" },
      { feature: "Catalog & Pricing", allowed: true, description: "Alter inventory stock levels and master SKU pricing catalog" },
      { feature: "User & Roster invites", allowed: true, description: "Invite new users and alter access privilege bounds" }
    ]
  },
  {
    role: "FINANCE",
    title: "Financial Auditor",
    description: "Manage billing ledgers, collection vouchers, outstanding customer debts, and statements.",
    permissions: [
      { feature: "Workspace Configuration", allowed: false, description: "Restricted from editing tenant settings parameters" },
      { feature: "Financial Ledgers & Statements", allowed: true, description: "Full auditing, statement retrieval, and collection logs" },
      { feature: "Fulfillment & Driver Runs", allowed: false, description: "No physical shipment allocation or driver log edits" },
      { feature: "Catalog & Pricing", allowed: false, description: "No direct stock adjustments or base price edits allowed" },
      { feature: "User & Roster invites", allowed: false, description: "No staff roster invitation or permission modification access" }
    ]
  },
  {
    role: "OPERATOR",
    title: "Operations Manager",
    description: "Manage orders, physical warehouse logistics, stock counts, and driver fulfillment dispatch runs.",
    permissions: [
      { feature: "Workspace Configuration", allowed: false, description: "Restricted from editing tenant settings parameters" },
      { feature: "Financial Ledgers & Statements", allowed: false, description: "Restricted from customer financial ledger collections" },
      { feature: "Fulfillment & Driver Runs", allowed: true, description: "Allocate shipments, dispatch drivers, and update milestone logs" },
      { feature: "Catalog & Pricing", allowed: true, description: "Full stock count imports, SKU alias mapping, and catalog updates" },
      { feature: "User & Roster invites", allowed: false, description: "No staff roster invitation or permission modification access" }
    ]
  },
  {
    role: "DRIVER",
    title: "Delivery Carrier",
    description: "Read-only access to delivery runs, vehicle schedules, and customer store drop locations.",
    permissions: [
      { feature: "Workspace Configuration", allowed: false, description: "Restricted from editing tenant settings parameters" },
      { feature: "Financial Ledgers & Statements", allowed: false, description: "Restricted from customer financial ledger collections" },
      { feature: "Fulfillment & Driver Runs", allowed: true, description: "Mark assigned shipment runs as completed or delivered" },
      { feature: "Catalog & Pricing", allowed: false, description: "No product catalog or warehouse inventory access" },
      { feature: "User & Roster invites", allowed: false, description: "No staff roster invitation or permission modification access" }
    ]
  }
];

export default function TeamSettingsPage() {
  const [activeTenantId, setActiveTenantId] = useState("");
  const [activeTab, setActiveTab] = useState<"directory" | "roles">("directory");
  const [users, setUsers] = useState<UserRow[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearchQuery] = useDebounce(searchQuery, 300);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Role card for Privileges tab
  const [selectedRoleCode, setSelectedRoleCode] = useState("SUPER_ADMIN");

  // Invite Modal States
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [fullName, setFullName] = useState("");
  const [emailOrPhone, setEmailOrPhone] = useState("");
  const [role, setRole] = useState("OPERATOR");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Edit Modal States
  const [selectedUserForEdit, setSelectedUserForEdit] = useState<UserRow | null>(null);
  const [editRole, setEditRole] = useState("OPERATOR");

  const [toast, setToast] = useState<{ show: boolean; message: string; type: "success" | "error" }>({
    show: false,
    message: "",
    type: "success"
  });

  const showToast = (message: string, type: "success" | "error") => {
    setToast({ show: true, message, type });
    setTimeout(() => {
      setToast(prev => ({ ...prev, show: false }));
    }, 4000);
  };

  // Sync tenant from localStorage on load
  useEffect(() => {
    const stored = localStorage.getItem("tenant_id");
    if (stored) {
      setActiveTenantId(stored);
    }
  }, []);

  const handleTenantChange = (id: string) => {
    setActiveTenantId(id);
    localStorage.setItem("tenant_id", id);
  };

  const getTenantName = () => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("tenant_name") || "My Workspace";
    }
    return "My Workspace";
  };

  const fetchUsers = useCallback(async (tenantId?: string) => {
    const targetTenant = tenantId || activeTenantId;
    if (!targetTenant) return;
    setLoading(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const resp = await fetch(`${apiBase}/api/v1/users?tenant_id=${targetTenant}`, {
        credentials: "include"
      });
      if (!resp.ok) throw new Error("Failed to retrieve user staff registry");
      const data = await resp.json();
      setUsers(data);
      setError(null);
    } catch (err: any) {
      console.error("Users load failed:", err);
      setError(err.message || "Failed to load active roster from server");
    } finally {
      setLoading(false);
    }
  }, [activeTenantId]);

  useEffect(() => {
    if (activeTenantId) {
      setUsers([]);
      fetchUsers(activeTenantId);
    }
  }, [activeTenantId, fetchUsers]);

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim() || !emailOrPhone.trim() || !password.trim()) {
      showToast("Please fill in all mandatory fields.", "error");
      return;
    }

    if (password.length < 6) {
      showToast("Password must be at least 6 characters long.", "error");
      return;
    }

    setSubmitting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const resp = await fetch(`${apiBase}/api/v1/users/invite?tenant_id=${activeTenantId}`, {
        method: "POST",
        credentials: "include",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email_or_phone: emailOrPhone.trim(),
          role: role,
          password: password
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        showToast("Roster invitation successful!", "success");
        setIsInviteModalOpen(false);
        setFullName("");
        setEmailOrPhone("");
        setPassword("");
        setRole("OPERATOR");
        
        setTimeout(() => fetchUsers(activeTenantId), 50);
      } else {
        const detail = data.detail || "Failed to invite new staff member.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network breakdown during staff invitation.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (user: UserRow) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const resp = await fetch(`${apiBase}/api/v1/users/${user.id}?tenant_id=${activeTenantId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          is_active: !user.is_active
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        showToast(`User ${!user.is_active ? "activated" : "deactivated"} successfully!`, "success");
        setTimeout(() => fetchUsers(activeTenantId), 50);
      } else {
        const detail = data.detail || "Failed to update user status.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network breakdown during status update.", "error");
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedUserForEdit) return;

    setSubmitting(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const token = typeof window !== "undefined" ? localStorage.getItem("accessToken") : null;
      const resp = await fetch(`${apiBase}/api/v1/users/${selectedUserForEdit.id}?tenant_id=${activeTenantId}`, {
        method: "PATCH",
        credentials: "include",
        headers: { 
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: JSON.stringify({
          role: editRole
        })
      });

      const data = await resp.json();
      if (resp.ok) {
        showToast("User role modified successfully!", "success");
        setSelectedUserForEdit(null);
        setTimeout(() => fetchUsers(activeTenantId), 50);
      } else {
        const detail = data.detail || "Failed to modify user role.";
        showToast(detail, "error");
      }
    } catch (err) {
      console.error(err);
      showToast("Network breakdown during role modification.", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const getRoleBadgeStyle = (userRole: string) => {
    switch (userRole.toUpperCase()) {
      case "SUPER_ADMIN":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "FINANCE":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "OPERATOR":
        return "bg-blue-50 text-blue-700 border-blue-200";
      case "DRIVER":
        return "bg-amber-50 text-amber-700 border-amber-200";
      default:
        return "bg-slate-50 text-slate-700 border-slate-200";
    }
  };

  const filteredUsers = users.filter(u => {
    const q = debouncedSearchQuery.toLowerCase();
    return (
      u.full_name.toLowerCase().includes(q) ||
      u.role.toLowerCase().includes(q) ||
      (u.email_or_phone && u.email_or_phone.toLowerCase().includes(q))
    );
  });

  const activeRoleDetails = ROLE_PRIVILEGES_MATRIX.find(r => r.role === selectedRoleCode) || ROLE_PRIVILEGES_MATRIX[0];

  if (!activeTenantId) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-blue" />
      </div>
    );
  }

  return (
    <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
      <Sidebar
        activeTab="Team Settings"
        setActiveTab={() => {}}
        tenantName={getTenantName()}
      />

      <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
        <DashboardHeader
          activeTenantId={activeTenantId}
          setActiveTenantId={handleTenantChange}
          tenantName={getTenantName()}
        />

        <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-xl font-bold text-slate-800 tracking-tight flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-blue" />
                <span>Distributor Team Directory</span>
              </h1>
              <p className="text-xs text-slate-400 font-semibold mt-0.5">
                Onboard logistics operators, finance clerks, and carriers, and outline role privilege constraints
              </p>
            </div>

            {activeTab === "directory" && (
              <button
                onClick={() => setIsInviteModalOpen(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-bold transition-all shadow-sm cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>+ Add Team Member</span>
              </button>
            )}
          </div>

          {/* Segment Navigation Menu */}
          <div className="flex border-b border-dashboard-border gap-6">
            <button
              onClick={() => setActiveTab("directory")}
              className={`pb-3 text-sm font-bold transition-all cursor-pointer ${activeTab === "directory" ? "border-b-2 border-brand-blue text-brand-blue" : "text-slate-400 hover:text-slate-600"}`}
            >
              Staff Roster Directory
            </button>
            <button
              onClick={() => setActiveTab("roles")}
              className={`pb-3 text-sm font-bold transition-all cursor-pointer ${activeTab === "roles" ? "border-b-2 border-brand-blue text-brand-blue" : "text-slate-400 hover:text-slate-600"}`}
            >
              RBAC Privilege Inspector
            </button>
          </div>

          {/* Tab Panel Content */}
          {activeTab === "directory" ? (
            <div className="bg-white rounded-xl border border-dashboard-border shadow-sm flex flex-col min-h-[400px]">
              <div className="p-5 border-b border-dashboard-border flex items-center justify-between bg-slate-50/50 rounded-t-xl gap-4">
                <div className="relative max-w-sm w-full">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search by Name, Role, or Credential..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-dashboard-border rounded-lg text-sm bg-white focus:outline-none focus:ring-1 focus:ring-brand-blue focus:border-brand-blue transition-all text-slate-700 font-medium"
                  />
                </div>

                <div className="text-xs font-bold text-slate-400">
                  Total Staff Logged: <span className="text-slate-700">{filteredUsers.length}</span>
                </div>
              </div>

              <div className="flex-1 overflow-x-auto">
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-24 gap-3">
                    <Loader2 className="w-8 h-8 text-brand-blue animate-spin" />
                    <span className="text-sm font-semibold text-slate-500">Loading active roster...</span>
                  </div>
                ) : error ? (
                  <div className="flex flex-col items-center justify-center py-24 gap-3 text-rose-600">
                    <AlertCircle className="w-8 h-8" />
                    <span className="text-sm font-semibold">{error}</span>
                    <button
                      onClick={() => fetchUsers(activeTenantId)}
                      className="mt-2 px-4 py-2 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs font-bold hover:bg-rose-100 transition-all cursor-pointer"
                    >
                      Try Again
                    </button>
                  </div>
                ) : filteredUsers.length === 0 ? (
                  <div className="text-center text-slate-400 py-24">
                    <p className="text-sm font-medium">No personnel found.</p>
                    <p className="text-xs text-slate-400 mt-1">Try refining search query parameters.</p>
                  </div>
                ) : (
                  <table className="w-full text-left text-sm border-collapse">
                    <thead>
                      <tr className="text-slate-400 font-semibold text-xs border-b border-dashboard-border bg-slate-50/50">
                        <th className="py-3 px-6">Name</th>
                        <th className="py-3 px-6">Assigned Role</th>
                        <th className="py-3 px-6">Credential Locator</th>
                        <th className="py-3 px-6 text-center">Status</th>
                        <th className="py-3 px-6 text-center">ACTIONS</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredUsers.map((u) => (
                        <tr key={u.id} className="hover:bg-slate-50/50 transition-colors">
                          <td className="py-4 px-6 font-bold text-slate-800 text-sm">
                            {u.full_name}
                          </td>
                          <td className="py-4 px-6">
                            <span className={`inline-flex px-2.5 py-0.5 border rounded-full text-[10px] font-bold uppercase tracking-wider ${getRoleBadgeStyle(u.role)}`}>
                              {u.role.replace("_", " ")}
                            </span>
                          </td>
                          <td className="py-4 px-6 font-semibold text-slate-500 text-xs">
                            {u.email_or_phone || u.phone_number || "—"}
                          </td>
                          <td className="py-4 px-6 text-center">
                            {u.is_active ? (
                              <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                Active
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded-full text-[10px] font-bold">
                                Deactivated
                              </span>
                            )}
                          </td>
                          <td className="py-4 px-6">
                            <div className="flex items-center justify-center gap-3">
                              <button
                                onClick={() => {
                                  setSelectedUserForEdit(u);
                                  setEditRole(u.role);
                                }}
                                className="p-1.5 hover:bg-slate-100 rounded-lg text-slate-500 hover:text-slate-700 transition-all cursor-pointer border border-transparent hover:border-slate-200"
                                title="Edit Role"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => handleToggleStatus(u)}
                                className={`w-24 text-center block px-2.5 py-1 text-xs rounded-md border font-bold transition-all cursor-pointer ${
                                  u.is_active
                                    ? "bg-rose-50 border-rose-200 text-rose-500 hover:bg-rose-100 hover:text-rose-600"
                                    : "bg-emerald-50 border-emerald-200 text-emerald-500 hover:bg-emerald-100 hover:text-emerald-600"
                                }`}
                              >
                                {u.is_active ? "Deactivate" : "Activate"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          ) : (
            /* Tab 2: Privilege Matrix View */
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Role Cards List */}
              <div className="md:col-span-1 space-y-4">
                {ROLE_PRIVILEGES_MATRIX.map((r) => {
                  const isSelected = r.role === selectedRoleCode;
                  return (
                    <button
                      key={r.role}
                      onClick={() => setSelectedRoleCode(r.role)}
                      className={`w-full p-4 text-left border rounded-xl shadow-sm transition-all flex flex-col gap-1 cursor-pointer bg-white ${
                        isSelected ? "border-brand-blue ring-1 ring-brand-blue" : "border-dashboard-border hover:bg-slate-50/50"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="font-extrabold text-slate-800 text-sm tracking-tight">{r.title}</span>
                        <span className={`px-2 py-0.5 border rounded-full text-[9px] font-bold uppercase tracking-wider ${getRoleBadgeStyle(r.role)}`}>
                          {r.role}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 font-medium leading-relaxed mt-1">
                        {r.description}
                      </p>
                    </button>
                  );
                })}
              </div>

              {/* Privilege Inspector Card */}
              <div className="md:col-span-2 bg-white rounded-xl border border-dashboard-border shadow-sm p-6 space-y-6">
                <div>
                  <h3 className="font-extrabold text-slate-800 text-base flex items-center gap-2">
                    <Shield className="w-5 h-5 text-brand-blue" />
                    <span>Access Bounds: {activeRoleDetails.title}</span>
                  </h3>
                  <p className="text-xs text-slate-400 font-semibold mt-1">
                    System boundaries and module rules defined for active personnel mapped to this role.
                  </p>
                </div>

                <div className="divide-y divide-slate-100 border border-slate-100 rounded-xl overflow-hidden">
                  {activeRoleDetails.permissions.map((p, idx) => (
                    <div key={idx} className="flex items-center justify-between p-4 hover:bg-slate-50/20 transition-colors">
                      <div>
                        <p className="text-xs font-bold text-slate-800">{p.feature}</p>
                        <p className="text-[11px] text-slate-400 font-medium mt-0.5">{p.description}</p>
                      </div>

                      <div>
                        {p.allowed ? (
                          <span className="inline-flex items-center gap-1 bg-emerald-50 text-emerald-700 border border-emerald-200 px-2.5 py-1 rounded-lg text-[10px] font-bold">
                            <UserCheck className="w-3.5 h-3.5" />
                            <span>Permitted</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 bg-rose-50 text-rose-700 border border-rose-200 px-2.5 py-1 rounded-lg text-[10px] font-bold">
                            <Lock className="w-3.5 h-3.5" />
                            <span>Restricted</span>
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* Invite Staff Modal */}
      {isInviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl w-full max-w-md p-6 animate-scale-up relative mx-4 animate-slide-in">
            <button
              onClick={() => setIsInviteModalOpen(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-full hover:bg-slate-50 transition-all cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">👤</span>
              <h3 className="font-bold text-slate-800 text-lg">Add Team Member</h3>
            </div>

            <p className="text-xs text-slate-400 font-semibold mb-6">
              Invite new operational staff members and partition their operational bounds.
            </p>

            <form onSubmit={handleInviteSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Full Name *</label>
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                  placeholder="e.g. Anand Sharma"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Credential Locator (Email or Phone) *</label>
                <input
                  type="text"
                  value={emailOrPhone}
                  onChange={(e) => setEmailOrPhone(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                  placeholder="e.g. anand@svdistributors.com or +919876500111"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Assigned Privilege Role *</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold cursor-pointer"
                  required
                >
                  <option value="SUPER_ADMIN">Super Administrator (SUPER_ADMIN)</option>
                  <option value="FINANCE">Financial Auditor (FINANCE)</option>
                  <option value="OPERATOR">Operations Manager (OPERATOR)</option>
                  <option value="DRIVER">Delivery Carrier (DRIVER)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Account Password *</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold"
                  placeholder="At least 6 characters"
                  required
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 mt-6">
                <button
                  type="button"
                  onClick={() => setIsInviteModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Invite Member</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Role Modal */}
      {selectedUserForEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm animate-fade-in">
          <div className="bg-white rounded-xl border border-slate-200 shadow-2xl w-full max-w-md p-6 animate-scale-up relative mx-4 animate-slide-in">
            <button
              onClick={() => setSelectedUserForEdit(null)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 p-1.5 rounded-full hover:bg-slate-50 transition-all cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-2 mb-4">
              <span className="text-xl">✏️</span>
              <h3 className="font-bold text-slate-800 text-lg">Modify User Role</h3>
            </div>

            <p className="text-xs text-slate-400 font-semibold mb-6">
              Update the privilege role tier for <span className="text-slate-700 font-bold">{selectedUserForEdit.full_name}</span>.
            </p>

            <form onSubmit={handleEditSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 mb-1.5 uppercase">Assigned Privilege Role *</label>
                <select
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-sm text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue bg-white font-semibold cursor-pointer"
                  required
                >
                  <option value="SUPER_ADMIN">Super Administrator (SUPER_ADMIN)</option>
                  <option value="FINANCE">Financial Auditor (FINANCE)</option>
                  <option value="OPERATOR">Operations Manager (OPERATOR)</option>
                  <option value="DRIVER">Delivery Carrier (DRIVER)</option>
                </select>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 mt-6">
                <button
                  type="button"
                  onClick={() => setSelectedUserForEdit(null)}
                  className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 cursor-pointer shadow-sm"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-3 h-3 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <span>Save Changes</span>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Sleek Floating Toast Notification */}
      {toast.show && (
        <div className="fixed top-5 right-5 z-50 flex items-center gap-3 bg-white/95 backdrop-blur-md border border-slate-100 shadow-2xl px-4 py-3.5 rounded-xl animate-slide-in pointer-events-auto max-w-sm">
          {toast.type === "success" ? (
            <div className="w-8 h-8 rounded-full bg-emerald-50 flex items-center justify-center text-emerald-600 shrink-0 shadow-sm">
              <CheckCircle2 className="w-4.5 h-4.5" />
            </div>
          ) : (
            <div className="w-8 h-8 rounded-full bg-rose-50 flex items-center justify-center text-rose-600 shrink-0 shadow-sm">
              <AlertCircle className="w-4.5 h-4.5" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <p className="text-xs font-bold text-slate-800">{toast.type === "success" ? "Success" : "Error"}</p>
            <p className="text-[11px] text-slate-500 font-semibold mt-0.5 break-words">{toast.message}</p>
          </div>
          <button
            onClick={() => setToast(prev => ({ ...prev, show: false }))}
            className="text-slate-400 hover:text-slate-600 p-0.5 rounded-full hover:bg-slate-50 transition-all shrink-0 cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
