"use client";

import React, { useState } from "react";
import { MessageSquare, X, Send, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react";

interface WhatsAppSimulatorProps {
  activeTenantId: string;
  onSuccess: () => void;
}

export default function WhatsAppSimulator({ activeTenantId, onSuccess }: WhatsAppSimulatorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [phone, setPhone] = useState("+919999888877"); // Default Kaveri Provision Store
  const [message, setMessage] = useState("Bhaiya, please deliver 50 HUL Soap and 12 ITC Aashirvaad Aata immediately");
  const [customPhone, setCustomPhone] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [result, setResult] = useState<{
    success: boolean;
    job_id?: string;
    message: string;
    details?: string;
  } | null>(null);

  const mockCustomers = [
    { name: "Kaveri Provision Store", phone: "+919999888877" },
    { name: "Maruthi Stores", phone: "+919999777766" },
    { name: "Sri Venkateshwara Traders", phone: "+919999666655" },
    { name: "Unknown Number (Simulate Fail)", phone: "+919876543210" }
  ];

  const handleSend = async () => {
    setIsSending(true);
    setResult(null);

    const targetPhone = phone === "custom" ? customPhone : phone;
    const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    try {
      const response = await fetch(`${BASE_URL}/api/v1/whatsapp/webhook`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          tenant_id: activeTenantId,
          phone_number: targetPhone,
          message_text: message
        })
      });

      const data = await response.json();

      if (response.ok && data.failed_rows === 0) {
        setResult({
          success: true,
          job_id: data.job_id,
          message: "Ingestion completed successfully! Order generated and committed to the database."
        });
        // Trigger parent dashboard refresh
        onSuccess();
      } else {
        setResult({
          success: false,
          message: data.error_message || "WhatsApp Ingestion processing failed.",
          details: `Job ID: ${data.job_id || "N/A"} | Failed Rows: ${data.failed_rows}`
        });
      }
    } catch (err: any) {
      console.error(err);
      setResult({
        success: false,
        message: "Failed to connect to the backend server. Please verify Uvicorn is running."
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <>
      {/* Floating Toggle Button */}
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 z-40 bg-emerald-500 hover:bg-emerald-600 text-white p-4 rounded-full shadow-2xl flex items-center justify-center gap-2 hover:scale-105 active:scale-95 transition-all duration-300 group border-2 border-white"
        title="Open WhatsApp Ingestion Simulator"
      >
        <MessageSquare className="w-6 h-6 animate-pulse" />
        <span className="max-w-0 overflow-hidden group-hover:max-w-xs transition-all duration-300 font-bold text-sm tracking-wide">
          WhatsApp Simulator
        </span>
      </button>

      {/* Modal Dialog */}
      {isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm transition-all animate-fade-in">
          <div className="bg-white rounded-2xl border border-dashboard-border shadow-2xl w-full max-w-lg overflow-hidden flex flex-col scale-in relative">
            
            {/* Header */}
            <div className="bg-slate-900 text-white p-5 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center text-white">
                  <MessageSquare className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h3 className="font-bold text-base">WhatsApp Ingestion Console</h3>
                  <p className="text-[10px] text-slate-400 font-semibold mt-0.5">NLP Order Processing Simulator</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setIsOpen(false);
                  setResult(null);
                }}
                className="text-slate-400 hover:text-white p-1 rounded-full hover:bg-slate-800 transition-all"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content Body */}
            <div className="p-6 space-y-5 flex-1 overflow-y-auto">
              
              {/* Phone Selector */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Simulated Sender Profile</label>
                <select
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2.5 border border-dashboard-border rounded-xl text-sm font-medium text-slate-700 bg-slate-50 focus:outline-none focus:ring-1 focus:ring-brand-blue focus:bg-white cursor-pointer transition-all"
                >
                  {mockCustomers.map((cust) => (
                    <option key={cust.phone} value={cust.phone}>
                      {cust.name} ({cust.phone})
                    </option>
                  ))}
                  <option value="custom">Custom Phone Number...</option>
                </select>
              </div>

              {/* Custom Phone Input */}
              {phone === "custom" && (
                <div className="space-y-1.5 animate-slide-down">
                  <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Custom Phone Number</label>
                  <input
                    type="text"
                    placeholder="+919999888877"
                    value={customPhone}
                    onChange={(e) => setCustomPhone(e.target.value)}
                    className="w-full px-3 py-2 border border-dashboard-border rounded-xl text-sm font-medium focus:outline-none focus:ring-1 focus:ring-brand-blue"
                  />
                </div>
              )}

              {/* Message Payload Textarea */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-wider">Raw Message (Unstructured Order)</label>
                <textarea
                  rows={4}
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  placeholder="Type order message in natural language..."
                  className="w-full px-3 py-2 border border-dashboard-border rounded-xl text-sm font-medium text-slate-700 focus:outline-none focus:ring-1 focus:ring-brand-blue resize-none"
                />
              </div>

              {/* Action Buttons */}
              <button
                onClick={handleSend}
                disabled={isSending || (phone === "custom" && !customPhone) || !message}
                className="w-full bg-emerald-500 hover:bg-emerald-600 disabled:bg-slate-200 disabled:text-slate-400 text-white font-bold py-3 px-4 rounded-xl flex items-center justify-center gap-2 hover:scale-[1.01] active:scale-95 transition-all shadow-lg shadow-emerald-500/10 cursor-pointer text-sm"
              >
                {isSending ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Parsing unstructured text with Gemini NLP...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-4.5 h-4.5" />
                    <span>Send Mock Webhook</span>
                  </>
                )}
              </button>

              {/* Results Output */}
              {result && (
                <div className={`p-4 rounded-xl border text-xs leading-relaxed animate-fade-in ${
                  result.success 
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800" 
                    : "bg-rose-50 border-rose-200 text-rose-800"
                }`}>
                  <div className="flex gap-2 items-start">
                    {result.success ? (
                      <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />
                    ) : (
                      <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
                    )}
                    <div className="space-y-1">
                      <p className="font-bold">{result.success ? "Ingestion Success" : "Processing Failure"}</p>
                      <p className="font-semibold text-slate-600">{result.message}</p>
                      {result.job_id && (
                        <p className="font-mono text-[10px] text-slate-400 mt-1">Job ID: {result.job_id}</p>
                      )}
                      {result.details && (
                        <p className="font-mono text-[9px] text-slate-400 mt-0.5">{result.details}</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

            </div>
          </div>
        </div>
      )}
    </>
  );
}
