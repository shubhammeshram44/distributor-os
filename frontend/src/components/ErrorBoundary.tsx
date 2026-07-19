"use client";

import React, { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export default class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  resetError = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="flex items-center justify-center py-16 px-4">
            <div className="bg-white rounded-lg border border-dashboard-border shadow-sm p-8 max-w-md">
              <div className="w-16 h-16 rounded-full bg-rose-100 flex items-center justify-center mb-6 mx-auto">
                <AlertTriangle className="w-8 h-8 text-rose-600" />
              </div>
              <h3 className="text-lg font-bold text-slate-800 text-center mb-2">
                Something went wrong
              </h3>
              <p className="text-sm text-slate-500 text-center mb-6">
                {this.state.error?.message || "An unexpected error occurred. Please try again."}
              </p>
              <button
                onClick={this.resetError}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-brand-blue text-white text-sm font-semibold rounded-lg hover:bg-brand-blueHover transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try Again
              </button>
            </div>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
