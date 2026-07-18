"use client";

import React, { useState, useEffect } from "react";
import { Search, X, Command } from "lucide-react";
import Link from "next/link";

interface SearchResult {
  id: string;
  title: string;
  description?: string;
  category: string;
  href: string;
  icon?: React.ReactNode;
}

interface CommandPaletteProps {
  searchFn?: (query: string) => Promise<SearchResult[]>;
}

export default function CommandPalette({ searchFn }: CommandPaletteProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);

  // Default quick actions
  const quickActions: SearchResult[] = [
    { id: "1", title: "Dashboard", category: "Navigate", href: "/dashboard", description: "Go to main dashboard" },
    { id: "2", title: "Orders", category: "Navigate", href: "/dashboard/orders", description: "View all orders" },
    { id: "3", title: "Customers", category: "Navigate", href: "/dashboard/customers", description: "Manage customers" },
    { id: "4", title: "Inventory", category: "Navigate", href: "/dashboard/inventory", description: "Check inventory levels" },
    { id: "5", title: "Products", category: "Navigate", href: "/dashboard/products", description: "Product catalog" },
    { id: "6", title: "Settings", category: "Navigate", href: "/dashboard/settings/team", description: "Team settings" }
  ];

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen(true);
      }
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  useEffect(() => {
    const searchResults = async () => {
      if (!query.trim()) {
        setResults(quickActions);
        setSelectedIndex(0);
        return;
      }

      setLoading(true);
      const lowerQuery = query.toLowerCase();

      if (searchFn) {
        try {
          const customResults = await searchFn(query);
          setResults(customResults);
        } catch {
          console.error("Search failed");
          const filtered = quickActions.filter(
            (a) => a.title.toLowerCase().includes(lowerQuery) || a.description?.toLowerCase().includes(lowerQuery)
          );
          setResults(filtered);
        }
      } else {
        const filtered = quickActions.filter(
          (a) => a.title.toLowerCase().includes(lowerQuery) || a.description?.toLowerCase().includes(lowerQuery)
        );
        setResults(filtered);
      }

      setLoading(false);
      setSelectedIndex(0);
    };

    const timer = setTimeout(searchResults, 300);
    return () => clearTimeout(timer);
  }, [query, searchFn]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % results.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev === 0 ? results.length - 1 : prev - 1));
    } else if (e.key === "Enter" && results[selectedIndex]) {
      e.preventDefault();
      window.location.href = results[selectedIndex].href;
    }
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 left-6 flex items-center gap-2 px-4 py-2 bg-white border border-dashboard-border rounded-lg shadow-lg hover:shadow-xl transition-shadow z-40"
      >
        <Command className="w-4 h-4 text-slate-400" />
        <span className="text-xs text-slate-500 font-semibold">Cmd+K</span>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-32 bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-2xl mx-4 bg-white rounded-lg shadow-2xl overflow-hidden">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-4 border-b border-dashboard-border">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            autoFocus
            type="text"
            placeholder="Search orders, products, customers... or press ? for help"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-sm font-semibold outline-none text-slate-800 placeholder-slate-400"
          />
          <button
            onClick={() => setIsOpen(false)}
            className="text-slate-400 hover:text-slate-600 p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 rounded-full border-2 border-slate-200 border-t-brand-blue animate-spin" />
            </div>
          ) : results.length === 0 ? (
            <div className="py-8 px-4 text-center">
              <p className="text-sm text-slate-500 font-semibold">No results found</p>
            </div>
          ) : (
            <div className="py-2">
              {results.map((result, idx) => (
                <Link
                  key={result.id}
                  href={result.href}
                  className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors ${
                    idx === selectedIndex ? "bg-slate-50" : "hover:bg-slate-50"
                  }`}
                  onClick={() => setIsOpen(false)}
                >
                  <div className="mt-1">
                    {result.icon || <Search className="w-4 h-4 text-slate-400" />}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-slate-800">{result.title}</p>
                    {result.description && (
                      <p className="text-xs text-slate-500 mt-0.5">{result.description}</p>
                    )}
                  </div>
                  <span className="text-xs font-semibold text-slate-400 whitespace-nowrap">
                    {result.category}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-dashboard-border flex items-center justify-between bg-slate-50">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>Esc Close</span>
          </div>
        </div>
      </div>
    </div>
  );
}
