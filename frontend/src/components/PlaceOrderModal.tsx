"use client";

import React, { useState, useEffect, useRef } from "react";
import { Mic, MicOff, Send, X, ShoppingCart } from "lucide-react";

interface Customer {
    id: string;
    retailer_name: string;
    phone: string;
}

interface PlaceOrderModalProps {
    activeTenantId: string;
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export default function PlaceOrderModal({
    activeTenantId, isOpen, onClose, onSuccess
}: PlaceOrderModalProps) {
    const [customers, setCustomers] = useState<Customer[]>([]);
    const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
    const [orderText, setOrderText] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
    const recognitionRef = useRef<any>(null);

    // Fetch customers
    useEffect(() => {
        if (!isOpen || !activeTenantId) return;
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
        fetch(`${apiBase}/api/v1/customers?tenant_id=${activeTenantId}`)
            .then(r => r.json())
            .then(data => {
                const list = Array.isArray(data) ? data : data.customers || data.items || [];
                setCustomers(list);
                if (list.length > 0) setSelectedCustomer(list[0]);
            })
            .catch(console.error);
    }, [isOpen, activeTenantId]);

    // Voice input using Web Speech API
    const startListening = () => {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (!SpeechRecognition) {
            alert("Voice input not supported in this browser. Please use Chrome.");
            return;
        }
        const recognition = new SpeechRecognition();
        recognition.lang = "hi-IN"; // Hindi + English
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onstart = () => setIsListening(true);
        recognition.onend = () => setIsListening(false);
        recognition.onerror = () => setIsListening(false);
        recognition.onresult = (event: any) => {
            const transcript = event.results[0][0].transcript;
            setOrderText(prev => prev ? `${prev} ${transcript}` : transcript);
        };

        recognitionRef.current = recognition;
        recognition.start();
    };

    const stopListening = () => {
        recognitionRef.current?.stop();
        setIsListening(false);
    };

    const handleSubmit = async () => {
        if (!selectedCustomer || !orderText.trim()) return;
        setIsSending(true);
        setResult(null);

        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
            const response = await fetch(`${apiBase}/api/v1/whatsapp/webhook`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    tenant_id: activeTenantId,
                    phone_number: selectedCustomer.phone,
                    message_text: orderText
                })
            });

            if (response.ok) {
                setResult({ success: true, message: "Order created successfully!" });
                setOrderText("");
                setTimeout(() => {
                    onSuccess();
                    onClose();
                    setResult(null);
                }, 1500);
            } else {
                setResult({ success: false, message: "Failed to create order. Please try again." });
            }
        } catch {
            setResult({ success: false, message: "Network error. Please try again." });
        } finally {
            setIsSending(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="place-order-modal-title">
            <div className="bg-white dark:bg-dashboard-card rounded-2xl shadow-2xl w-full max-w-md">
                {/* Header */}
                <div className="flex items-center justify-between p-5 border-b border-slate-100 dark:border-white/5">
                    <div className="flex items-center gap-2">
                        <ShoppingCart className="w-5 h-5 text-emerald-600" />
                        <h2 id="place-order-modal-title" className="font-semibold text-slate-800 dark:text-slate-100">Place Order</h2>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-slate-600" aria-label="Close order modal">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-5 space-y-4">
                    {/* Customer selector */}
                    <div>
                        <label className="text-xs font-semibold text-slate-500 dark:text-slate-500 uppercase tracking-wide mb-1.5 block">
                            Placing order for
                        </label>
                        <select
                            value={selectedCustomer?.id || ""}
                            onChange={e => {
                                const c = customers.find(c => c.id === e.target.value);
                                setSelectedCustomer(c || null);
                            }}
                            className="w-full border border-slate-200 dark:border-white/10 rounded-xl px-3 py-2.5 text-sm font-medium text-slate-700 dark:text-slate-300 outline-none focus:border-emerald-500 bg-slate-50 dark:bg-dashboard-inset"
                        >
                            {customers.map(c => (
                                <option key={c.id} value={c.id}>
                                    {c.retailer_name} ({c.phone})
                                </option>
                            ))}
                        </select>
                    </div>

                    {/* Order text input */}
                    <div>
                        <label className="text-xs font-semibold text-slate-500 dark:text-slate-500 uppercase tracking-wide mb-1.5 block">
                            Order message
                        </label>
                        <div className="relative">
                            <textarea
                                rows={4}
                                value={orderText}
                                onChange={e => setOrderText(e.target.value)}
                                placeholder={`Type or speak the order...\ne.g. "50 Lux soap aur 30 Rin bhejo"`}
                                className="w-full border border-slate-200 dark:border-white/10 rounded-xl p-3 pr-12 text-sm text-slate-700 dark:text-slate-300 outline-none focus:border-emerald-500 resize-none bg-slate-50 dark:bg-dashboard-inset leading-relaxed"
                            />
                            {/* Voice button */}
                            <button
                                onClick={isListening ? stopListening : startListening}
                                className={`absolute bottom-3 right-3 p-2 rounded-lg transition-all ${isListening
                                        ? "bg-red-100 text-red-600 animate-pulse"
                                        : "bg-slate-100 dark:bg-white/5 text-slate-500 dark:text-slate-500 hover:bg-emerald-100 hover:text-emerald-600"
                                    }`}
                                title={isListening ? "Stop listening" : "Speak order"}
                            >
                                {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
                            </button>
                        </div>
                        {isListening && (
                            <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
                                <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse" />
                                Listening... speak your order
                            </p>
                        )}
                    </div>

                    {/* Result message */}
                    {result && (
                        <div className={`text-sm font-medium p-3 rounded-lg ${result.success
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-red-50 text-red-700"
                            }`}>
                            {result.message}
                        </div>
                    )}

                    {/* Submit */}
                    <button
                        onClick={handleSubmit}
                        disabled={isSending || !selectedCustomer || !orderText.trim()}
                        className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold py-3 rounded-xl flex items-center justify-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Send className="w-4 h-4" />
                        {isSending ? "Creating order..." : "Place Order"}
                    </button>

                    <p className="text-xs text-slate-400 text-center">
                        Order will be processed through AI — same as WhatsApp
                    </p>
                </div>
            </div>
        </div>
    );
}
