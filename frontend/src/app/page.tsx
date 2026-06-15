"use client";

import React, { useState } from "react";
import Link from "next/link";
import { MessageSquare, Map, Database, ArrowRight, Check, Sparkles, MessageCircle, BarChart3, Clock, AlertTriangle } from "lucide-react";

export default function MarketingPage() {
  const [showSandbox, setShowSandbox] = useState(false);

  return (
    <div className="bg-slate-50 min-h-screen text-slate-800 font-sans selection:bg-blue-100">
      
      {/* 1. Header Navigation */}
      <header className="border-b border-slate-100 bg-white/85 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-blue-650 flex items-center justify-center text-white text-base font-black shadow-md shadow-blue-200 transition-transform group-hover:scale-105">
              D
            </div>
            <span className="font-extrabold text-slate-800 text-lg tracking-tight">DistributorOS</span>
          </Link>

          <nav className="hidden md:flex items-center gap-8">
            <a href="#features" className="text-xs font-bold text-slate-500 hover:text-slate-855 transition-colors uppercase tracking-wider">Features</a>
            <a href="#sandbox" className="text-xs font-bold text-slate-500 hover:text-slate-855 transition-colors uppercase tracking-wider">Sandbox Simulation</a>
            <a href="#pricing" className="text-xs font-bold text-slate-500 hover:text-slate-855 transition-colors uppercase tracking-wider">Pricing Plans</a>
          </nav>

          <div>
            <Link 
              href="/auth" 
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-blue-100 flex items-center gap-1.5 cursor-pointer hover:scale-[1.02] active:scale-[0.98]"
            >
              <span>Start Free Trial 🚀</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* 2. Hero Section */}
      <section className="py-20 px-6 max-w-7xl mx-auto text-center relative overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[550px] h-[550px] bg-blue-100/30 rounded-full blur-3xl -z-10 animate-pulse" />
        
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-blue-50 border border-blue-100/50 rounded-full text-blue-700 text-[11px] font-bold uppercase tracking-wider mb-6 shadow-sm">
          <Sparkles className="w-3.5 h-3.5 text-blue-500 animate-spin-slow" />
          <span>FMCG Order Ingestion Engine</span>
        </div>

        <h1 className="text-4xl sm:text-5xl md:text-6xl font-black text-slate-900 tracking-tight max-w-4xl mx-auto leading-[1.1]">
          The AI-First Operations Workspace for <span className="text-blue-600">FMCG Distributors</span>
        </h1>
        
        <p className="text-sm sm:text-base text-slate-500 max-w-2xl mx-auto mt-6 leading-relaxed font-semibold">
          Forwarding a chaotic text order on WhatsApp automatically converts it into a digital invoice line in seconds. Coordinate routes, ledger entries, and low-stock alerts on a single clean board.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link 
            href="/auth" 
            className="w-full sm:w-auto px-8 py-4 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-sm transition-all shadow-lg shadow-blue-100 flex items-center justify-center gap-2 cursor-pointer hover:scale-[1.01]"
          >
            <span>Start Free Trial 🚀</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
          <button 
            onClick={() => {
              setShowSandbox(true);
              document.getElementById("sandbox")?.scrollIntoView({ behavior: "smooth" });
            }}
            className="w-full sm:w-auto px-8 py-4 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 font-bold rounded-xl text-sm transition-all shadow-sm flex items-center justify-center gap-1.5 cursor-pointer"
          >
            Simulate App Workspace
          </button>
        </div>
      </section>

      {/* 3. Interactive Sandbox Simulation */}
      <section id="sandbox" className="py-16 px-6 max-w-5xl mx-auto border-t border-slate-100 scroll-mt-20">
        <div className="text-center max-w-xl mx-auto mb-10">
          <h2 className="text-2xl sm:text-3xl font-black text-slate-800 tracking-tight">Interactive Sandbox Simulation</h2>
          <p className="text-xs text-slate-400 font-bold mt-2 uppercase tracking-widest">Experience the cockpit instantly</p>
        </div>

        <div className="flex justify-center mb-8">
          <button
            onClick={() => setShowSandbox(!showSandbox)}
            className={`px-6 py-3 rounded-2xl text-xs font-bold transition-all shadow-md flex items-center gap-2 cursor-pointer ${
              showSandbox 
                ? "bg-slate-900 text-white hover:bg-slate-800" 
                : "bg-blue-600 text-white hover:bg-blue-700 shadow-blue-100"
            }`}
          >
            <span>{showSandbox ? "Close Sandbox View" : "Simulate App Workspace ⚡"}</span>
            <Sparkles className="w-4 h-4" />
          </button>
        </div>

        {/* Dynamic Sandbox Display */}
        <div className={`transition-all duration-500 ease-in-out ${
          showSandbox ? "opacity-100 max-h-[1000px] scale-100" : "opacity-0 max-h-0 scale-95 pointer-events-none overflow-hidden"
        }`}>
          <div className="bg-slate-900 text-white border border-slate-800 rounded-3xl p-6 md:p-8 shadow-2xl relative">
            <div className="absolute top-4 right-4 flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-450 text-[10px] font-bold uppercase tracking-wider">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              <span>Simulated Sandbox Active</span>
            </div>

            {/* Dashboard Mock Header */}
            <div className="mb-6 border-b border-slate-800 pb-4">
              <h4 className="font-extrabold text-sm text-slate-300 uppercase tracking-wider">DistributorOS Console</h4>
              <p className="text-[11px] text-slate-500 font-medium mt-0.5">Mock workspace preview for: <strong>S.V. Distributors</strong></p>
            </div>

            {/* Mini Dashboard Grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-slate-950 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Total Sales Ingestion</span>
                <span className="text-lg font-black text-blue-400 mt-2">₹1,84,500.00</span>
                <span className="text-[10px] text-emerald-450 font-bold mt-1">↑ 12.4% vs last week</span>
              </div>
              <div className="bg-slate-950 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Live AI Webhook Listeners</span>
                <span className="text-lg font-black text-emerald-400 mt-2">Active</span>
                <span className="text-[10px] text-slate-400 font-semibold mt-1">Listening on WhatsApp API</span>
              </div>
              <div className="bg-slate-950 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between">
                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Low Stock SKUs alert</span>
                <span className="text-lg font-black text-amber-500 mt-2">2 Alert Items</span>
                <span className="text-[10px] text-slate-400 font-semibold mt-1">Requires urgent dispatch review</span>
              </div>
            </div>

            {/* Simulated Activity logs */}
            <div className="bg-slate-950 border border-slate-850 rounded-2xl p-4">
              <h5 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-blue-500" />
                <span>Real-Time Operation Feed (Simulation)</span>
              </h5>
              
              <div className="space-y-3">
                <div className="flex items-start justify-between text-xs border-b border-slate-900 pb-2">
                  <div className="flex gap-2">
                    <MessageCircle className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-semibold text-slate-350">WhatsApp Order Received from Kaveri Provision Store</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">"Need 20 packs Aata, 5 boxes Chips..."</p>
                    </div>
                  </div>
                  <span className="text-[10px] font-bold text-emerald-450 uppercase">Parsed By AI</span>
                </div>

                <div className="flex items-start justify-between text-xs border-b border-slate-900 pb-2">
                  <div className="flex gap-2">
                    <BarChart3 className="w-4 h-4 text-blue-550 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-semibold text-slate-350">Draft Invoice #INV-2026-102 Generated</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Total Amount: ₹8,450.00</p>
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-500 font-semibold">1 min ago</span>
                </div>

                <div className="flex items-start justify-between text-xs pb-1">
                  <div className="flex gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-550 mt-0.5 shrink-0" />
                    <div>
                      <p className="font-semibold text-slate-350">Stock Alert: Brand "ITC Chips" is below threshold</p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Quantity on hand: 5 units (Threshold: 10)</p>
                    </div>
                  </div>
                  <span className="text-[10px] text-amber-500 font-bold uppercase">Low Stock</span>
                </div>
              </div>
            </div>

            {/* Sandbox CTA */}
            <div className="mt-8 flex items-center justify-between gap-4 flex-wrap border-t border-slate-800 pt-6">
              <span className="text-xs font-semibold text-slate-400">Ready to ingest your actual supply chain records?</span>
              <Link 
                href="/auth" 
                className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-xs transition-all shadow-md flex items-center gap-1.5 cursor-pointer"
              >
                <span>Launch My Active Trial</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>

          </div>
        </div>
      </section>

      {/* 4. Features Grid */}
      <section id="features" className="py-20 px-6 max-w-7xl mx-auto border-t border-slate-100">
        <div className="text-center max-w-xl mx-auto mb-16">
          <h2 className="text-2xl sm:text-3xl font-black text-slate-800 tracking-tight">Supercharged features built for scale</h2>
          <p className="text-xs text-slate-400 font-bold mt-2 uppercase tracking-widest">Core Capabilities</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Card 1 */}
          <div className="bg-white border border-slate-100 rounded-2xl p-8 shadow-sm hover:shadow-md transition-all flex flex-col justify-between h-[300px]">
            <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-sm">
              <MessageSquare className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-800 mb-2">WhatsApp AI Ingestion</h3>
              <p className="text-xs text-slate-500 font-semibold leading-relaxed">
                Automatically parse unstructured Hinglish message streams or audio memos into canonical draft digital orders. Gemini AI maps products, quantities, and customer profile details.
              </p>
            </div>
          </div>

          {/* Card 2 */}
          <div className="bg-white border border-slate-100 rounded-2xl p-8 shadow-sm hover:shadow-md transition-all flex flex-col justify-between h-[300px]">
            <div className="w-12 h-12 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center shadow-sm">
              <Map className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-800 mb-2">Real-Time Route Sheets</h3>
              <p className="text-xs text-slate-500 font-semibold leading-relaxed">
                Compile unallocated confirmed invoice checkpoints into optimal transport run sheets. Track drivers, vehicle assignments, and milestone delivery completions instantly.
              </p>
            </div>
          </div>

          {/* Card 3 */}
          <div className="bg-white border border-slate-100 rounded-2xl p-8 shadow-sm hover:shadow-md transition-all flex flex-col justify-between h-[300px]">
            <div className="w-12 h-12 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center shadow-sm">
              <Database className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-slate-800 mb-2">Digital Stock Ledger</h3>
              <p className="text-xs text-slate-500 font-semibold leading-relaxed">
                Strict inequality low-stock bounds prevent fulfillment lockups. Maintain a clean ledger mapping real warehouse location bins, threshold counts, and Tally/Marg ERP catalog sync.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Pricing Matrix */}
      <section id="pricing" className="py-20 px-6 max-w-7xl mx-auto border-t border-slate-100 bg-slate-50">
        <div className="text-center max-w-xl mx-auto mb-16">
          <h2 className="text-2xl sm:text-3xl font-black text-slate-800 tracking-tight">Simple, transparent, self-service pricing</h2>
          <p className="text-xs text-slate-400 font-bold mt-2 uppercase tracking-widest">Pricing Matrix Tiers</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          
          {/* Tier 1 */}
          <div className="bg-white border border-slate-150 rounded-2xl p-8 shadow-sm flex flex-col justify-between min-h-[420px]">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">Trial</span>
              <h3 className="text-xl font-bold text-slate-800 mt-1">Starter Trial</h3>
              <div className="mt-4 flex items-baseline gap-1 text-slate-800">
                <span className="text-3xl font-extrabold">₹0</span>
                <span className="text-xs text-slate-400 font-semibold">/15 days</span>
              </div>
              <p className="text-xs text-slate-500 font-semibold mt-3">15 Days Unrestricted Access for testing operations.</p>
              
              <ul className="mt-6 space-y-3">
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Unrestricted Workspace Features</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>WhatsApp AI parsing simulation</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Interactive Route Sheet Generator</span>
                </li>
              </ul>
            </div>
            
            <Link href="/auth" className="mt-8 w-full py-2.5 bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold rounded-xl text-xs text-center transition-all cursor-pointer block">
              Get Started
            </Link>
          </div>

          {/* Tier 2 */}
          <div className="bg-white border-2 border-blue-500 rounded-2xl p-8 shadow-md flex flex-col justify-between min-h-[420px] relative">
            <div className="absolute top-0 right-6 -translate-y-1/2 bg-blue-500 text-white text-[9px] font-black uppercase tracking-wider px-3 py-1 rounded-full">
              Most Popular
            </div>
            <div>
              <span className="text-[10px] uppercase font-bold text-blue-500">Growth</span>
              <h3 className="text-xl font-bold text-slate-800 mt-1">Growth Tier</h3>
              <div className="mt-4 flex items-baseline gap-1 text-slate-800">
                <span className="text-3xl font-extrabold">₹4,999</span>
                <span className="text-xs text-slate-400 font-semibold">/month</span>
              </div>
              <p className="text-xs text-slate-500 font-semibold mt-3">Up to 500 WhatsApp Orders processed per month.</p>
              
              <ul className="mt-6 space-y-3">
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>3 Warehouses & Bin Control</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Up to 500 WhatsApp Orders</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Live Driver Optimization Run Sheets</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>FIFO Collection Allocation & Ledgers</span>
                </li>
              </ul>
            </div>
            
            <Link href="/auth" className="mt-8 w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-xs text-center transition-all shadow-md shadow-blue-100 cursor-pointer block">
              Start Free Trial 🚀
            </Link>
          </div>

          {/* Tier 3 */}
          <div className="bg-white border border-slate-150 rounded-2xl p-8 shadow-sm flex flex-col justify-between min-h-[420px]">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400">Enterprise</span>
              <h3 className="text-xl font-bold text-slate-800 mt-1">Enterprise Tier</h3>
              <div className="mt-4 flex items-baseline gap-1 text-slate-800">
                <span className="text-3xl font-extrabold">₹12,499</span>
                <span className="text-xs text-slate-400 font-semibold">/month</span>
              </div>
              <p className="text-xs text-slate-500 font-semibold mt-3">Unlimited AI Ingestions & full Tally ERP Integration placeholders.</p>
              
              <ul className="mt-6 space-y-3">
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Unlimited Warehouses</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Tally ERP Synchronization Placeholders</span>
                </li>
                <li className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                  <Check className="w-4 h-4 text-emerald-500 shrink-0" />
                  <span>Dedicated Server Instance & 24/7 SLA</span>
                </li>
              </ul>
            </div>
            
            <Link href="/auth" className="mt-8 w-full py-2.5 bg-slate-850 hover:bg-slate-950 text-white font-bold rounded-xl text-xs text-center transition-all cursor-pointer block">
              Contact Sales
            </Link>
          </div>

        </div>
      </section>

      {/* 6. Footer */}
      <footer className="border-t border-slate-100 bg-white py-12 px-6 text-center">
        <p className="text-[11px] text-slate-400 font-semibold">
          © 2026 DistributorOS. All rights reserved. Supply chain control pipelines engineered for modern distributors.
        </p>
      </footer>

    </div>
  );
}
