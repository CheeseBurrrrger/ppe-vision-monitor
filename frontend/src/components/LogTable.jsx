import { useQuery } from "@tanstack/react-query";
import { fetchViolations } from "../api/violationApi";
import { useState, useEffect } from "react";


const PAGE_SIZE = 20;
 
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const VIOLATION_OPTIONS = [
  { value: "All",        label: "Semua Pelanggaran" },
  { value: "no_helmet",  label: "Tanpa Helm" },
  { value: "no_vest",    label: "Tanpa Rompi" },
  { value: "no_boots",   label: "Tanpa Sepatu Safety" },
  { value: "no_gloves",  label: "Tanpa Sarung Tangan" },
  { value: "no_goggles", label: "Tanpa Goggle" },
];

const VIOLATION_LABELS = {
  no_helmet:  "Tanpa Helm Safety",
  no_vest:    "Tanpa Rompi",
  no_gloves:  "Tanpa Sarung Tangan",
  no_boots:   "Tanpa Sepatu Safety",
  no_goggles: "Tanpa Goggle",
};

const BADGE_COLORS = {
  no_helmet:  "bg-red-100 text-red-700 border-red-200",
  no_vest:    "bg-orange-100 text-orange-700 border-orange-200",
  no_gloves:  "bg-purple-100 text-purple-700 border-purple-200",
  no_boots:   "bg-yellow-100 text-yellow-700 border-yellow-200",
  no_goggles: "bg-blue-100 text-blue-700 border-blue-200",
};

const getShift = (timestamp) => {
  const hour = new Date(timestamp).getHours();
  if (hour >= 6 && hour < 14) return "Shift 1";
  if (hour >= 14 && hour < 22) return "Shift 2";
  return "Shift 3";
};
export function LogTable({ filters = {} }) {
  const [page, setPage] = useState(0);
  const { type = "All", dateFrom, dateTo } = filters;
  useEffect(() => {
    setPage(0);
  }, [type, dateFrom, dateTo]);
  const { data: violations = [], isLoading, isError } = useQuery({
    queryKey: ["violations", type, dateFrom, dateTo, page],
    queryFn: () => fetchViolations({
      type,        
      dateFrom,      
      dateTo,        
      limit: PAGE_SIZE,
      offset: page * PAGE_SIZE,
    }),
    refetchInterval: 3000,
    refetchOnWindowFocus: true,
  });

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b flex justify-between items-center bg-slate-50">
        <div className="flex items-center gap-3">
          <h2 className="font-semibold text-slate-800">Log Pelanggaran</h2>
          {isLoading && (
            <span className="text-xs text-slate-400 animate-pulse">Memuat...</span>
          )}
        </div>
      </div>
 
      {/* Table */}
      <div className="overflow-x-auto">
        {isError ? (
          <div className="p-10 text-center text-red-500">
            Gagal mengambil data dari backend.
          </div>
        ) : (
          <table className="w-full text-left border-collapse">
            <thead className="bg-slate-100 text-slate-600 text-xs uppercase tracking-wider">
              <tr>
                <th className="p-4 font-bold">#</th>
                <th className="p-4 font-bold">Timestamp</th>
                <th className="p-4 font-bold">Jenis Pelanggaran</th>
                <th className="p-4 font-bold">Confidence</th>
                <th className="p-4 font-bold">Shift</th>
                <th className="p-4 font-bold">ID Kamera</th>
                <th className="p-4 font-bold">Bukti</th>
              </tr>
            </thead>
            <tbody className="divide-y text-slate-700">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="p-4">
                        <div className="h-4 bg-slate-200 rounded w-3/4" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : violations.length > 0 ? (
                violations.map((v, idx) => (
                  <tr key={v.id} className="hover:bg-slate-50/80 transition text-sm">
                    <td className="p-4 font-mono text-slate-400 text-xs">
                      {String(page * PAGE_SIZE + idx + 1).padStart(3, "0")}
                    </td>
                    <td className="p-4 font-medium">
                      {new Date(v.timestamp).toLocaleString("id-ID")}
                    </td>
                    <td className="p-4">
                      <span className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase border ${
                        BADGE_COLORS[v.violation_type] ?? "bg-gray-100 text-gray-700 border-gray-200"
                      }`}>
                        {(VIOLATION_LABELS[v.violation_type] ?? v.violation_type).replace(/_/g, " ")}
                      </span>
                    </td>
                    <td className="p-4">
                      <span className="font-mono text-slate-600">
                        {(v.confidence * 100).toFixed(1)}%
                      </span>
                    </td>
                    <td className="p-4 text-slate-600">
                      {getShift(v.timestamp)}
                    </td>
                    <td className="p-4 text-slate-600 font-medium">
                      {v.camera_id || "CAM-DEFAULT"}
                    </td>
                    <td className="p-4">
                      {v.screenshot_url ? (
                        <a
                          href={`${API_BASE}${v.screenshot_url}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-blue-600 hover:text-blue-800 text-xs font-semibold underline"
                        >
                          Lihat Bukti
                        </a>
                      ) : (
                        <span className="text-slate-300 text-xs">—</span>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="7" className="p-10 text-center text-slate-400 italic">
                    Tidak ada data pelanggaran ditemukan.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
 
      {/* Pagination */}
      <div className="p-4 border-t flex justify-between items-center bg-slate-50 text-sm">
        <span className="text-slate-500">
          Halaman {page + 1}
        </span>
        <div className="flex gap-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="px-3 py-1.5 rounded-lg border text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            ← Sebelumnya
          </button>
          <button
            onClick={() => setPage((p) => p + 1)}
            disabled={violations.length < PAGE_SIZE}
            className="px-3 py-1.5 rounded-lg border text-slate-600 hover:bg-slate-100 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Berikutnya →
          </button>
        </div>
      </div>
    </div>
  );
}