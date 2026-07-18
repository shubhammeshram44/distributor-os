"use client";

import React, { useState } from "react";
import Sidebar from "@/components/Sidebar";
import DashboardHeader from "@/components/DashboardHeader";
import ErrorBoundary from "@/components/ErrorBoundary";
import { Download, FileText, BarChart3, CreditCard, Users, Package } from "lucide-react";

const reportTemplates = [
  {
    id: "sales_summary",
    name: "Sales Summary",
    description: "Total sales, orders count, and revenue trends",
    icon: BarChart3,
    color: "emerald"
  },
  {
    id: "customer_analysis",
    name: "Customer Analysis",
    description: "Customer acquisition, retention, and lifetime value",
    icon: Users,
    color: "blue"
  },
  {
    id: "product_performance",
    name: "Product Performance",
    description: "Best selling products and inventory status",
    icon: Package,
    color: "purple"
  },
  {
    id: "collections_report",
    name: "Collections Report",
    description: "Outstanding receivables and aging analysis",
    icon: CreditCard,
    color: "amber"
  }
];

const savedReports = [
  { id: 1, name: "Monthly Sales Report", type: "Sales Summary", date: "2025-06-20", status: "ready" },
  { id: 2, name: "Q2 Customer Analysis", type: "Customer Analysis", date: "2025-06-15", status: "ready" },
  { id: 3, name: "Inventory Status June", type: "Product Performance", date: "2025-06-10", status: "ready" }
];

export default function ReportsPage() {
  const [tenantId, setTenantId] = React.useState("");
  const [selectedReport, setSelectedReport] = React.useState<string | null>(null);

  React.useEffect(() => {
    const storedTenant = localStorage.getItem("tenant_id");
    if (storedTenant) setTenantId(storedTenant);
  }, []);

  const handleGenerateReport = (reportId: string) => {
    // TODO: Implement report generation
    console.log("Generating report:", reportId);
  };

  const handleDownloadReport = (reportId: number) => {
    // TODO: Implement report download
    console.log("Downloading report:", reportId);
  };

  return (
    <ErrorBoundary>
      <div className="flex bg-dashboard-bg min-h-screen text-slate-800">
        <Sidebar activeTab="Reports" setActiveTab={() => {}} tenantName="Workspace" />

        <div className="flex-1 pl-64 flex flex-col h-screen overflow-hidden">
          <DashboardHeader activeTenantId={tenantId} setActiveTenantId={() => {}} tenantName="Workspace" userProfile={null} />

          <main className="flex-1 mt-16 p-6 overflow-y-auto space-y-8">
            <div>
              <h1 className="text-2xl font-bold text-slate-800">Reports</h1>
              <p className="text-xs text-slate-400 font-semibold mt-1">Generate and manage custom reports</p>
            </div>

            {/* Report Templates */}
            <div>
              <h2 className="text-lg font-bold text-slate-800 mb-4">Report Templates</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {reportTemplates.map((template) => {
                  const Icon = template.icon;
                  const colorClasses = {
                    emerald: "bg-emerald-50 text-emerald-600 border-emerald-200",
                    blue: "bg-blue-50 text-blue-600 border-blue-200",
                    purple: "bg-purple-50 text-purple-600 border-purple-200",
                    amber: "bg-amber-50 text-amber-600 border-amber-200"
                  };

                  return (
                    <button
                      key={template.id}
                      onClick={() => handleGenerateReport(template.id)}
                      className={`p-6 rounded-lg border-2 transition-all hover:shadow-md ${colorClasses[template.color as keyof typeof colorClasses]}`}
                    >
                      <Icon className="w-8 h-8 mb-3" />
                      <h3 className="text-sm font-bold text-slate-800 mb-1">{template.name}</h3>
                      <p className="text-xs text-slate-600 mb-4">{template.description}</p>
                      <span className="text-xs font-semibold opacity-70">Generate</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Saved Reports */}
            <div>
              <h2 className="text-lg font-bold text-slate-800 mb-4">Saved Reports</h2>
              {savedReports.length === 0 ? (
                <div className="p-8 bg-white rounded-lg border border-dashboard-border text-center">
                  <FileText className="w-12 h-12 text-slate-300 mx-auto mb-3" />
                  <p className="text-slate-500 text-sm font-semibold">No saved reports yet</p>
                  <p className="text-xs text-slate-400 mt-1">Generate your first report from templates above</p>
                </div>
              ) : (
                <div className="bg-white rounded-lg border border-dashboard-border shadow-sm overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="border-b border-dashboard-border bg-slate-50">
                        <tr>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Report Name</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Type</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Generated</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Status</th>
                          <th className="px-6 py-3 text-left text-xs font-bold text-slate-600 uppercase">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-dashboard-border">
                        {savedReports.map((report) => (
                          <tr key={report.id} className="hover:bg-slate-50 transition-colors">
                            <td className="px-6 py-4">
                              <p className="text-sm font-semibold text-slate-800">{report.name}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm text-slate-600">{report.type}</p>
                            </td>
                            <td className="px-6 py-4">
                              <p className="text-sm text-slate-600">{new Date(report.date).toLocaleDateString()}</p>
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700">
                                {report.status}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <button
                                onClick={() => handleDownloadReport(report.id)}
                                className="flex items-center gap-2 px-3 py-1.5 bg-brand-blue text-white text-xs font-semibold rounded hover:bg-brand-blueHover transition-colors"
                              >
                                <Download className="w-3.5 h-3.5" />
                                Download
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            {/* Report Scheduling */}
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
              <h2 className="text-lg font-bold text-blue-900 mb-2">Schedule Reports</h2>
              <p className="text-sm text-blue-700 mb-4">Set up automatic reports to be generated and emailed to you on a regular basis</p>
              <button className="px-4 py-2 bg-brand-blue text-white text-sm font-semibold rounded-lg hover:bg-brand-blueHover transition-colors">
                Create Schedule
              </button>
            </div>
          </main>
        </div>
      </div>
    </ErrorBoundary>
  );
}
