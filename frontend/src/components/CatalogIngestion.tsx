"use client";

import React, { useState, useRef } from "react";
import { UploadCloud, FileText, X, Loader2, Info } from "lucide-react";

interface CatalogIngestionProps {
  activeTenantId: string;
  onSuccess: (msg: string) => void;
  onError: (msg: string) => void;
}

export default function CatalogIngestion({
  activeTenantId,
  onSuccess,
  onError
}: CatalogIngestionProps) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith(".csv")) {
        setSelectedFile(file);
      } else {
        onError("Only CSV files (.csv) are supported.");
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith(".csv")) {
        setSelectedFile(file);
      } else {
        onError("Only CSV files (.csv) are supported.");
      }
    }
  };

  const onButtonClick = () => {
    fileInputRef.current?.click();
  };

  const clearFile = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append("tenant_id", activeTenantId);
    formData.append("file", selectedFile);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
      const response = await fetch(`${apiBase}/api/v1/products/import`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (response.ok) {
        if (typeof data.inserted_count === "number" && typeof data.updated_count === "number") {
          onSuccess(
            `Catalog sync complete! Added ${data.inserted_count} new products and updated ${data.updated_count} existing prices.`
          );
        } else {
          onSuccess(`Imported ${data.successful_rows} products successfully!`);
        }
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      } else {
        const errorDetail = data.detail;
        let errMsg = "Validation failed during import.";
        if (typeof errorDetail === "object" && errorDetail.message) {
          errMsg = errorDetail.message;
        } else if (typeof errorDetail === "string") {
          errMsg = errorDetail;
        }
        onError(errMsg);
      }
    } catch (err) {
      onError("Network connection breakdown during file upload.");
    } finally {
      setIsUploading(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const dm = 2;
    const sizes = ["Bytes", "KB", "MB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
  };

  return (
    <div className="bg-white p-5 rounded-xl border border-dashboard-border shadow-sm flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between pb-3 border-b border-dashboard-border mb-4">
        <div>
          <h3 className="font-bold text-slate-800 text-base">Product Pricing Ingestion</h3>
          <p className="text-[11px] text-slate-400 font-semibold mt-0.5">Bulk catalog updates via CSV sheet</p>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-4">
        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".csv"
          onChange={handleFileChange}
        />

        {/* Drag and Drop Zone */}
        {!selectedFile ? (
          <div
            className={`flex-1 border-2 border-dashed rounded-xl p-6 flex flex-col items-center justify-center gap-2 cursor-pointer transition-all ${
              dragActive
                ? "border-brand-blue bg-blue-50/20"
                : "border-slate-200 hover:border-brand-blue hover:bg-slate-50/30"
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={onButtonClick}
          >
            <div className="w-10 h-10 rounded-full bg-slate-50 flex items-center justify-center text-slate-400 shadow-sm border border-slate-100">
              <UploadCloud className="w-5 h-5" />
            </div>
            <p className="text-xs font-bold text-slate-700 mt-1">
              Drag & drop CSV file or <span className="text-brand-blue hover:underline">browse</span>
            </p>
            <p className="text-[10px] text-slate-400 font-medium">Supported file type: .csv</p>
          </div>
        ) : (
          <div className="flex-1 border border-slate-200 bg-slate-50/40 rounded-xl p-4 flex flex-col justify-between gap-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-9 h-9 rounded-lg bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-500 shrink-0">
                  <FileText className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold text-slate-800 truncate">{selectedFile.name}</p>
                  <p className="text-[10px] text-slate-400 font-semibold mt-0.5">{formatFileSize(selectedFile.size)}</p>
                </div>
              </div>
              <button
                onClick={clearFile}
                className="text-slate-400 hover:text-slate-600 p-1 hover:bg-slate-100 rounded-full transition-all shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <button
              onClick={handleUpload}
              disabled={isUploading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white font-bold text-xs p-2.5 rounded-lg transition-colors shadow-sm flex items-center justify-center gap-2 cursor-pointer"
            >
              {isUploading ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : (
                <span>⚡ Upload & Update Catalog</span>
              )}
            </button>
          </div>
        )}

        {/* Reference Format Info Box */}
        <div className="p-3 bg-slate-50 border border-slate-200/60 rounded-xl text-[10px] flex gap-2">
          <Info className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold text-slate-700">Required CSV Columns:</p>
            <code className="block bg-slate-100 px-2 py-1 rounded text-slate-600 font-semibold border border-slate-200/50">
              sku_id, brand, category, pack_size, base_price
            </code>
            <p className="text-slate-400 font-semibold mt-1">Updates price if SKU exists, otherwise inserts a new SKU row.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
