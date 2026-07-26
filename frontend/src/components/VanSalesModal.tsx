"use client";

import React, { useState, useEffect, useRef } from "react";
import { X, Search, Mic, MicOff, ChevronLeft, Check, Loader2 } from "lucide-react";
import { v4 as uuidv4 } from "uuid";

// ── TYPES ────────────────────────────────────────────────────────────────────

interface Customer {
    id: string;
    retailer_name: string;
    phone_number: string;
    outstanding_balance: number;
    credit_limit: number;
}

interface Product {
    id: string;
    brand: string;
    pack_size: string;
    base_price: number;
    sku_id: string;
    category: string;
}

interface OrderItem {
    product: Product;
    quantity: number;
}

type Screen = "customer" | "order" | "payment" | "success";
type PaymentMethod = "cash" | "upi" | "credit";

interface VanSalesModalProps {
    isOpen: boolean;
    onClose: () => void;
    activeTenantId: string;
}

// ── COMPONENT ────────────────────────────────────────────────────────────────

export default function VanSalesModal({ isOpen, onClose, activeTenantId }: VanSalesModalProps) {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

    // Screen state
    const [screen, setScreen] = useState<Screen>("customer");

    // Customer screen
    const [customers, setCustomers] = useState<Customer[]>([]);
    const [customerSearch, setCustomerSearch] = useState("");
    const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
    const [addingNewCustomer, setAddingNewCustomer] = useState(false);
    const [newCustomerName, setNewCustomerName] = useState("");
    const [newCustomerPhone, setNewCustomerPhone] = useState("");

    // Order screen
    const [products, setProducts] = useState<Product[]>([]);
    const [productSearch, setProductSearch] = useState("");
    const [filteredProducts, setFilteredProducts] = useState<Product[]>([]);
    const [orderItems, setOrderItems] = useState<OrderItem[]>([]);
    const [alreadyDelivered, setAlreadyDelivered] = useState(false);
    const [isListening, setIsListening] = useState(false);
    const recognitionRef = useRef<any>(null);

    // Recent items for quick-add
    const [recentProducts, setRecentProducts] = useState<Product[]>([]);

    // Payment screen
    const [paymentMethod, setPaymentMethod] = useState<PaymentMethod | null>(null);
    const [cashAmount, setCashAmount] = useState("");
    const [paymentReference, setPaymentReference] = useState("");
    const [paymentLinkUrl, setPaymentLinkUrl] = useState<string | null>(null);

    // Submission
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [successData, setSuccessData] = useState<any>(null);
    const [idempotencyKey, setIdempotencyKey] = useState(uuidv4());

    // ── ORDER TOTAL ──────────────────────────────────────────────────────────
    const orderTotal = orderItems.reduce(
        (sum, item) => sum + item.quantity * item.product.base_price, 0
    );

    // ── FETCH CUSTOMERS ──────────────────────────────────────────────────────
    useEffect(() => {
        if (!isOpen || !activeTenantId) return;
        fetch(`${apiBase}/api/v1/customers?tenant_id=${activeTenantId}&limit=200`)
            .then(r => r.json())
            .then(data => {
                const list = Array.isArray(data) ? data : data.customers || data.items || [];
                setCustomers(list);
            })
            .catch(console.error);
    }, [isOpen, activeTenantId]);

    // ── FETCH PRODUCTS ───────────────────────────────────────────────────────
    useEffect(() => {
        if (!isOpen || !activeTenantId) return;
        fetch(`${apiBase}/api/v1/products?tenant_id=${activeTenantId}&limit=500&is_active=true`)
            .then(r => r.json())
            .then(data => {
                const list = Array.isArray(data) ? data : data.products || data.items || [];
                setProducts(list);
            })
            .catch(console.error);
    }, [isOpen, activeTenantId]);

    // ── FETCH RECENT PRODUCTS FOR QUICK ADD ──────────────────────────────────
    useEffect(() => {
        if (!selectedCustomer || !activeTenantId) {
            setRecentProducts([]);
            return;
        }
        fetch(`${apiBase}/api/v1/customers/${selectedCustomer.id}/recent-products?tenant_id=${activeTenantId}`)
            .then(r => {
                if (r.ok) return r.json();
                return [];
            })
            .then(data => {
                setRecentProducts(data || []);
            })
            .catch(console.error);
    }, [selectedCustomer, activeTenantId]);

    // ── PRODUCT SEARCH FILTER ────────────────────────────────────────────────
    useEffect(() => {
        if (!productSearch.trim()) {
            setFilteredProducts([]);
            return;
        }
        const q = productSearch.toLowerCase();
        setFilteredProducts(
            products.filter(p =>
                p.brand?.toLowerCase().includes(q) ||
                p.sku_id?.toLowerCase().includes(q) ||
                p.category?.toLowerCase().includes(q) ||
                p.pack_size?.toLowerCase().includes(q)
            ).slice(0, 10)
        );
    }, [productSearch, products]);

    // ── CUSTOMER FILTER ──────────────────────────────────────────────────────
    const filteredCustomers = customers.filter(c =>
        c.retailer_name?.toLowerCase().includes(customerSearch.toLowerCase()) ||
        c.phone_number?.includes(customerSearch)
    );

    // ── VOICE INPUT ──────────────────────────────────────────────────────────
    const startListening = () => {
        const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
        if (!SpeechRecognition) return;
        const recognition = new SpeechRecognition();
        recognition.lang = "hi-IN";
        recognition.continuous = false;
        recognition.onstart = () => setIsListening(true);
        recognition.onend = () => setIsListening(false);
        recognition.onerror = () => setIsListening(false);
        recognition.onresult = (event: any) => {
            const transcript = event.results[0][0].transcript;
            setProductSearch(transcript);
        };
        recognitionRef.current = recognition;
        recognition.start();
    };

    // ── ORDER ITEM MANAGEMENT ────────────────────────────────────────────────
    const updateQuantity = (product: Product, delta: number) => {
        setOrderItems(prev => {
            const existing = prev.find(i => i.product.id === product.id);
            if (existing) {
                const newQty = existing.quantity + delta;
                if (newQty <= 0) return prev.filter(i => i.product.id !== product.id);
                return prev.map(i => i.product.id === product.id ? { ...i, quantity: newQty } : i);
            } else if (delta > 0) {
                return [...prev, { product, quantity: delta }];
            }
            return prev;
        });
    };

    const getQuantity = (productId: string) =>
        orderItems.find(i => i.product.id === productId)?.quantity || 0;

    // ── SUBMIT TRANSACTION ───────────────────────────────────────────────────
    const handleSubmit = async () => {
        if (!paymentMethod) return;
        setIsSubmitting(true);
        setError("");

        try {
            const payload: any = {
                idempotency_key: idempotencyKey,
                items: orderItems.map(i => ({
                    product_id: i.product.id,
                    quantity: i.quantity
                })),
                already_delivered: alreadyDelivered,
                payment_method: paymentMethod,
                payment_amount: paymentMethod === "cash" ? parseFloat(cashAmount) || orderTotal : null,
                payment_reference: paymentReference || null
            };

            if (selectedCustomer) {
                payload.customer_id = selectedCustomer.id;
            } else {
                payload.new_customer_name = newCustomerName;
                payload.new_customer_phone = newCustomerPhone || null;
            }

            const res = await fetch(
                `${apiBase}/api/v1/orders/instant-transaction?tenant_id=${activeTenantId}`,
                {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                }
            );

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.detail || "Transaction failed");
            }

            setSuccessData(data);
            if (data.payment_link_url) setPaymentLinkUrl(data.payment_link_url);
            setScreen("success");

        } catch (e: any) {
            setError(e.message || "Something went wrong");
        } finally {
            setIsSubmitting(false);
        }
    };

    // ── RESET ────────────────────────────────────────────────────────────────
    const handleReset = () => {
        setScreen("customer");
        setSelectedCustomer(null);
        setOrderItems([]);
        setPaymentMethod(null);
        setCashAmount("");
        setPaymentReference("");
        setPaymentLinkUrl(null);
        setSuccessData(null);
        setError("");
        setAlreadyDelivered(false);
        setCustomerSearch("");
        setProductSearch("");
        setAddingNewCustomer(false);
        setNewCustomerName("");
        setNewCustomerPhone("");
        setIdempotencyKey(uuidv4());
    };

    const handleClose = () => {
        handleReset();
        onClose();
    };

    if (!isOpen) return null;

    // ── RENDER ───────────────────────────────────────────────────────────────
    return (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center">
            <div className="bg-white dark:bg-slate-900 w-full max-w-md mx-auto rounded-t-2xl sm:rounded-2xl shadow-2xl h-[90vh] sm:h-[80vh] flex flex-col overflow-hidden transition-colors duration-200">

                {/* ── SCREEN 1: SELECT CUSTOMER ── */}
                {screen === "customer" && (
                    <>
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                            <h2 className="font-bold text-slate-800 dark:text-white">🚚 Van Sale — Select Retailer</h2>
                            <button onClick={handleClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="px-5 pt-4 pb-2">
                            <div className="relative">
                                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                                <input
                                    type="text"
                                    value={customerSearch}
                                    onChange={e => setCustomerSearch(e.target.value)}
                                    placeholder="Search retailer name or phone..."
                                    className="w-full pl-9 pr-4 py-2.5 border border-slate-200 dark:border-slate-700 rounded-xl text-sm outline-none focus:border-emerald-500 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white"
                                    autoFocus
                                />
                            </div>
                        </div>

                        <div className="flex-1 overflow-y-auto px-5 pb-4">
                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mt-3 mb-2">
                                {customerSearch ? "Search Results" : "All Customers"}
                            </p>
                            <div className="space-y-2">
                                {filteredCustomers.slice(0, 20).map(customer => (
                                    <button
                                        key={customer.id}
                                        onClick={() => {
                                            setSelectedCustomer(customer);
                                            setScreen("order");
                                        }}
                                        className="w-full flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 hover:bg-emerald-50 dark:hover:bg-emerald-950/20 border border-slate-200 dark:border-slate-700/60 hover:border-emerald-300 dark:hover:border-emerald-800 rounded-xl transition-all text-left"
                                    >
                                        <div>
                                            <p className="text-sm font-semibold text-slate-800 dark:text-white">
                                                {customer.retailer_name}
                                            </p>
                                            <p className="text-xs text-slate-400">{customer.phone_number || "No phone"}</p>
                                        </div>
                                        {customer.outstanding_balance > 0 && (
                                            <span className="text-xs font-bold text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/25 px-2 py-1 rounded-full">
                                                ₹{customer.outstanding_balance.toLocaleString("en-IN")} due
                                            </span>
                                        )}
                                    </button>
                                ))}
                            </div>

                            {/* New customer inline creation */}
                            {!addingNewCustomer ? (
                                <button
                                    onClick={() => setAddingNewCustomer(true)}
                                    className="w-full mt-4 py-3 border-2 border-dashed border-slate-300 dark:border-slate-700 rounded-xl text-sm font-semibold text-slate-500 hover:border-emerald-400 hover:text-emerald-600 dark:hover:text-emerald-400 transition-all"
                                >
                                    + Add New Customer Inline
                                </button>
                            ) : (
                                <div className="mt-4 p-4 border border-slate-200 dark:border-slate-800 rounded-xl space-y-3">
                                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">New Customer</p>
                                    <input
                                        type="text"
                                        value={newCustomerName}
                                        onChange={e => setNewCustomerName(e.target.value)}
                                        placeholder="Retailer Name *"
                                        className="w-full border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-emerald-500 bg-white dark:bg-slate-800 text-slate-800 dark:text-white"
                                    />
                                    <input
                                        type="tel"
                                        value={newCustomerPhone}
                                        onChange={e => setNewCustomerPhone(e.target.value)}
                                        placeholder="Phone Number (optional)"
                                        className="w-full border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2.5 text-sm outline-none focus:border-emerald-500 bg-white dark:bg-slate-800 text-slate-800 dark:text-white"
                                    />
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => setAddingNewCustomer(false)}
                                            className="flex-1 py-2 text-sm text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700 rounded-lg"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            onClick={() => {
                                                if (!newCustomerName.trim()) return;
                                                setSelectedCustomer(null);
                                                setScreen("order");
                                            }}
                                            disabled={!newCustomerName.trim()}
                                            className="flex-1 py-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg disabled:opacity-50"
                                        >
                                            Continue →
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </>
                )}

                {/* ── SCREEN 2: BUILD ORDER ── */}
                {screen === "order" && (
                    <>
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                            <button onClick={() => setScreen("customer")} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                                <ChevronLeft className="w-5 h-5" />
                            </button>
                            <div className="text-center">
                                <p className="font-bold text-slate-800 dark:text-white text-sm">
                                    {selectedCustomer?.retailer_name || newCustomerName}
                                </p>
                                {selectedCustomer?.outstanding_balance > 0 && (
                                    <p className="text-xs text-red-500 dark:text-red-400 font-medium">
                                        ₹{selectedCustomer.outstanding_balance.toLocaleString("en-IN")} outstanding
                                    </p>
                                )}
                            </div>
                            <button onClick={handleClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Quick-add section (only if selectedCustomer has recent products) */}
                        {recentProducts.length > 0 && !productSearch && (
                            <div className="px-5 pt-3 pb-1 border-b border-slate-50 dark:border-slate-800/40">
                                <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
                                    Recently Ordered Items
                                </p>
                                <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
                                    {recentProducts.slice(0, 5).map(prod => (
                                        <button
                                            key={prod.id}
                                            onClick={() => updateQuantity(prod, 1)}
                                            className="flex-shrink-0 px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full text-xs font-medium text-slate-700 dark:text-slate-300 hover:border-emerald-400 hover:bg-emerald-50/20 transition-all"
                                        >
                                            + {prod.brand} ({prod.pack_size})
                                        </button>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Search input with microphone option */}
                        <div className="px-5 pt-3 pb-2">
                            <div className="relative">
                                <Search className="absolute left-3 top-2.5 w-4 h-4 text-slate-400" />
                                <input
                                    type="text"
                                    value={productSearch}
                                    onChange={e => setProductSearch(e.target.value)}
                                    placeholder="Type brand, SKU or category..."
                                    className="w-full pl-9 pr-12 py-2.5 border border-slate-200 dark:border-slate-700 rounded-xl text-sm outline-none focus:border-emerald-500 bg-slate-50 dark:bg-slate-800 text-slate-800 dark:text-white"
                                />
                                <button
                                    onClick={isListening ? () => recognitionRef.current?.stop() : startListening}
                                    className={`absolute right-3 top-2.5 p-1 rounded-lg ${isListening ? "text-red-500 animate-pulse" : "text-slate-400"}`}
                                >
                                    {isListening ? <MicOff className="w-4.5 h-4.5" /> : <Mic className="w-4.5 h-4.5" />}
                                </button>
                            </div>
                        </div>

                        {/* Products list */}
                        <div className="flex-1 overflow-y-auto px-5 pb-4">
                            {(filteredProducts.length > 0 ? filteredProducts : products.slice(0, 30)).map(product => {
                                const quantity = getQuantity(product.id);
                                return (
                                    <div key={product.id} className="flex items-center justify-between py-3 border-b border-slate-50 dark:border-slate-800/40">
                                        <div className="flex-1 min-w-0 pr-3">
                                            <p className="text-sm font-semibold text-slate-800 dark:text-white truncate">
                                                {product.brand}
                                            </p>
                                            <p className="text-xs text-slate-400 truncate">
                                                {product.sku_id} · {product.pack_size} · ₹{product.base_price}
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2.5 flex-shrink-0">
                                            <button
                                                onClick={() => updateQuantity(product, -1)}
                                                className="w-8 h-8 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-bold text-lg flex items-center justify-center hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
                                            >
                                                −
                                            </button>
                                            <span className="w-6 text-center text-sm font-bold text-slate-850 dark:text-white">
                                                {quantity}
                                            </span>
                                            <button
                                                onClick={() => updateQuantity(product, 1)}
                                                className="w-8 h-8 rounded-full bg-emerald-100 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 font-bold text-lg flex items-center justify-center hover:bg-emerald-200 dark:hover:bg-emerald-900/60 transition-colors"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Sticky bottom panel */}
                        <div className="px-5 py-4 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                            {/* Toggle already_delivered */}
                            <div className="flex items-center justify-between mb-4 p-3 bg-slate-50 dark:bg-slate-800/30 rounded-xl">
                                <div>
                                    <p className="text-xs font-semibold text-slate-750 dark:text-slate-300">Mark Already Delivered</p>
                                    <p className="text-[10px] text-slate-400">Skips logistics/dispatch pipeline</p>
                                </div>
                                <button
                                    onClick={() => setAlreadyDelivered(!alreadyDelivered)}
                                    className={`w-11 h-6 rounded-full transition-all relative ${alreadyDelivered ? "bg-emerald-500" : "bg-slate-350 dark:bg-slate-700"}`}
                                >
                                    <div className={`w-5 h-5 bg-white rounded-full shadow absolute top-0.5 transition-transform ${alreadyDelivered ? "translate-x-5.5" : "translate-x-0.5"}`} />
                                </button>
                            </div>

                            <div className="flex items-center justify-between mb-3">
                                <span className="text-sm font-semibold text-slate-500 dark:text-slate-400">Total Items: {orderItems.length}</span>
                                <span className="text-lg font-bold text-slate-900 dark:text-white">
                                    ₹{orderTotal.toLocaleString("en-IN")}
                                </span>
                            </div>

                            <button
                                onClick={() => setScreen("payment")}
                                disabled={orderTotal === 0}
                                className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl disabled:opacity-50 transition-all text-sm"
                            >
                                Confirm & Choose Payment →
                            </button>
                        </div>
                    </>
                )}

                {/* ── SCREEN 3: COLLECT PAYMENT ── */}
                {screen === "payment" && (
                    <>
                        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-800">
                            <button onClick={() => setScreen("order")} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                                <ChevronLeft className="w-5 h-5" />
                            </button>
                            <h2 className="font-bold text-slate-800 dark:text-white">Collect Payment</h2>
                            <button onClick={handleClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto px-5 py-4">
                            {/* Summary panel */}
                            <div className="bg-slate-50 dark:bg-slate-800/40 rounded-xl p-4 mb-4">
                                <div className="flex justify-between text-xs mb-1.5">
                                    <span className="text-slate-500 dark:text-slate-400">Order Amount</span>
                                    <span className="font-semibold text-slate-800 dark:text-white">₹{orderTotal.toLocaleString("en-IN")}</span>
                                </div>
                                {selectedCustomer?.outstanding_balance > 0 && (
                                    <div className="flex justify-between text-xs mb-1.5">
                                        <span className="text-slate-500 dark:text-slate-400">Previous Outstanding</span>
                                        <span className="font-semibold text-red-655 dark:text-red-400">
                                            ₹{selectedCustomer.outstanding_balance.toLocaleString("en-IN")}
                                        </span>
                                    </div>
                                )}
                                <div className="flex justify-between text-sm font-bold border-t border-slate-200 dark:border-slate-700 pt-2 mt-2">
                                    <span className="text-slate-700 dark:text-slate-350">Net Balance</span>
                                    <span className="text-slate-900 dark:text-white">
                                        ₹{(orderTotal + (selectedCustomer?.outstanding_balance || 0)).toLocaleString("en-IN")}
                                    </span>
                                </div>
                            </div>

                            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
                                Payment Method
                            </p>
                            <div className="space-y-3">
                                {/* UPI */}
                                <button
                                    onClick={() => setPaymentMethod("upi")}
                                    className={`w-full p-3.5 rounded-xl border-2 text-left transition-all ${paymentMethod === "upi" ? "border-emerald-500 bg-emerald-50/20 dark:bg-emerald-950/10" : "border-slate-205 dark:border-slate-800 bg-white dark:bg-slate-900"}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="text-xl">📱</span>
                                        <div>
                                            <p className="font-semibold text-slate-800 dark:text-white text-xs">UPI QR Code</p>
                                            <p className="text-[10px] text-slate-455 dark:text-slate-400">Display QR code to scan</p>
                                        </div>
                                        {paymentMethod === "upi" && <Check className="ml-auto w-4.5 h-4.5 text-emerald-600 dark:text-emerald-400" />}
                                    </div>
                                </button>

                                {/* Cash */}
                                <button
                                    onClick={() => setPaymentMethod("cash")}
                                    className={`w-full p-3.5 rounded-xl border-2 text-left transition-all ${paymentMethod === "cash" ? "border-emerald-500 bg-emerald-50/20 dark:bg-emerald-950/10" : "border-slate-205 dark:border-slate-800 bg-white dark:bg-slate-900"}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="text-xl">💵</span>
                                        <div>
                                            <p className="font-semibold text-slate-800 dark:text-white text-xs">Cash Payment</p>
                                            <p className="text-[10px] text-slate-455 dark:text-slate-400">Log cash received</p>
                                        </div>
                                        {paymentMethod === "cash" && <Check className="ml-auto w-4.5 h-4.5 text-emerald-600 dark:text-emerald-400" />}
                                    </div>
                                    {paymentMethod === "cash" && (
                                        <div className="mt-3 space-y-2" onClick={e => e.stopPropagation()}>
                                            <input
                                                type="number"
                                                value={cashAmount}
                                                onChange={e => setCashAmount(e.target.value)}
                                                placeholder={`Enter cash (e.g. ₹${orderTotal})`}
                                                className="w-full border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 text-xs outline-none focus:border-emerald-500 bg-white dark:bg-slate-800 text-slate-800 dark:text-white"
                                            />
                                            {cashAmount && parseFloat(cashAmount) > orderTotal && (
                                                <p className="text-[10px] text-emerald-600 dark:text-emerald-400 font-medium">
                                                    Change to return: ₹{(parseFloat(cashAmount) - orderTotal).toLocaleString("en-IN")}
                                                </p>
                                            )}
                                        </div>
                                    )}
                                </button>

                                {/* Credit */}
                                <button
                                    onClick={() => setPaymentMethod("credit")}
                                    className={`w-full p-3.5 rounded-xl border-2 text-left transition-all ${paymentMethod === "credit" ? "border-emerald-500 bg-emerald-50/20 dark:bg-emerald-950/10" : "border-slate-205 dark:border-slate-800 bg-white dark:bg-slate-900"}`}
                                >
                                    <div className="flex items-center gap-3">
                                        <span className="text-xl">📋</span>
                                        <div>
                                            <p className="font-semibold text-slate-800 dark:text-white text-xs">On Credit</p>
                                            <p className="text-[10px] text-slate-455 dark:text-slate-400">
                                                {selectedCustomer
                                                    ? `Available Credit: ₹${(selectedCustomer.credit_limit - selectedCustomer.outstanding_balance).toLocaleString("en-IN")}`
                                                    : "Add to outstanding account"}
                                            </p>
                                        </div>
                                        {paymentMethod === "credit" && <Check className="ml-auto w-4.5 h-4.5 text-emerald-600 dark:text-emerald-400" />}
                                    </div>
                                    {paymentMethod === "credit" && selectedCustomer &&
                                        orderTotal > (selectedCustomer.credit_limit - selectedCustomer.outstanding_balance) && (
                                        <div className="mt-2.5 p-2 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800/40 rounded-lg">
                                            <p className="text-[10px] text-red-600 dark:text-red-400 font-medium">
                                                ⚠️ Exceeds credit limit by ₹{(orderTotal - (selectedCustomer.credit_limit - selectedCustomer.outstanding_balance)).toLocaleString("en-IN")}
                                            </p>
                                        </div>
                                    )}
                                </button>
                            </div>

                            {/* Error Alert */}
                            {error && (
                                <div className="mt-4 p-3 bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800/40 rounded-xl text-xs text-red-700 dark:text-red-400">
                                    {error}
                                </div>
                            )}
                        </div>

                        <div className="px-5 py-4 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                            <button
                                onClick={handleSubmit}
                                disabled={!paymentMethod || isSubmitting || (paymentMethod === "cash" && !cashAmount)}
                                className="w-full py-3.5 bg-emerald-600 hover:bg-emerald-700 text-white font-bold rounded-xl disabled:opacity-50 flex items-center justify-center gap-2 transition-all text-xs"
                            >
                                {isSubmitting ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        Completing Transaction...
                                    </>
                                ) : (
                                    "Log Sale & Complete ✓"
                                )}
                            </button>
                        </div>
                    </>
                )}

                {/* ── SCREEN 4: SUCCESS STATE ── */}
                {screen === "success" && (
                    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
                        <div className="w-16 h-16 bg-emerald-100 dark:bg-emerald-950/30 rounded-full flex items-center justify-center mb-4">
                            <Check className="w-8 h-8 text-emerald-600 dark:text-emerald-400" />
                        </div>
                        <h2 className="text-xl font-bold text-slate-800 dark:text-white mb-1">Transaction Recorded!</h2>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
                            Order ID: <span className="font-semibold">{successData?.internal_order_id}</span>
                        </p>

                        {/* UPI QR Display */}
                        {paymentLinkUrl && (
                            <div className="bg-slate-50 dark:bg-slate-850 p-4 border border-slate-200 dark:border-slate-850/60 rounded-2xl mb-5 flex flex-col items-center">
                                <p className="text-[10px] font-semibold text-slate-455 dark:text-slate-400 mb-2 uppercase tracking-wide">
                                    Scan QR code to pay ₹{orderTotal.toLocaleString("en-IN")}
                                </p>
                                <img
                                    src={`https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(paymentLinkUrl)}`}
                                    alt="Payment Link QR"
                                    className="w-36 h-36 border border-slate-100 dark:border-slate-800 bg-white rounded-lg p-1.5"
                                />
                                <a
                                    href={paymentLinkUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="text-xs text-emerald-600 dark:text-emerald-400 font-medium hover:underline mt-3.5"
                                >
                                    Open payment link directly
                                </a>
                            </div>
                        )}

                        <div className="w-full max-w-xs space-y-2.5 mt-2">
                            <div className="flex justify-between text-xs text-slate-550 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800/40 pb-2">
                                <span>Customer</span>
                                <span className="font-semibold text-slate-800 dark:text-white">{successData?.customer_name}</span>
                            </div>
                            <div className="flex justify-between text-xs text-slate-550 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800/40 pb-2">
                                <span>Order Value</span>
                                <span className="font-semibold text-slate-800 dark:text-white">₹{orderTotal.toLocaleString("en-IN")}</span>
                            </div>
                            <div className="flex justify-between text-xs text-slate-550 dark:text-slate-400 border-b border-slate-100 dark:border-slate-800/40 pb-2">
                                <span>Payment Method</span>
                                <span className="font-semibold capitalize text-slate-800 dark:text-white">{successData?.payment_method}</span>
                            </div>
                        </div>

                        <button
                            onClick={handleReset}
                            className="w-full max-w-xs py-3.5 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-xl text-xs mt-8 transition-colors"
                        >
                            Log Another Transaction
                        </button>
                        <button
                            onClick={handleClose}
                            className="text-xs font-semibold text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 mt-4 transition-colors"
                        >
                            Close Modal
                        </button>
                    </div>
                )}

            </div>
        </div>
    );
}
