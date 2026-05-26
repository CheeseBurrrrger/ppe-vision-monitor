import { useState } from "react";
import { fetchViolations } from "../api/violationApi";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

const VIOLATION_OPTIONS = [
  { value: "",           label: "Semua Jenis Pelanggaran" },
  { value: "no_helmet",  label: "Tanpa Helm" },
  { value: "no_vest",    label: "Tanpa Rompi" },
  { value: "no_boots",   label: "Tanpa Sepatu Safety" },
  { value: "no_gloves",  label: "Tanpa Sarung Tangan" },
  { value: "no_goggles", label: "Tanpa Goggle" },
];

const SHIFT_OPTIONS = [
  { value: "",  label: "Semua Shift" },
  { value: "1", label: "Shift 1 (06:00-14:00)" },
  { value: "2", label: "Shift 2 (14:00-22:00)" },
  { value: "3", label: "Shift 3 (22:00-06:00)" },
];

export default function FilterBar({ onFilterChange }) {
  const [type, setType]       = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo]   = useState("");

  const handleTypeChange = (e) => {
    const val = e.target.value;
    setType(val);
    onFilterChange?.({ type: val, dateFrom, dateTo });
  };

  const handleDateFrom = (e) => {
    setDateFrom(e.target.value);
    onFilterChange?.({ type, dateFrom: e.target.value, dateTo });
  };

  const handleDateTo = (e) => {
    setDateTo(e.target.value);
    onFilterChange?.({ type, dateFrom, dateTo: e.target.value });
  };

  const exportUrl = `${API_BASE}/export-csv?${new URLSearchParams({
    ...(type     && { violation_type: type }),
    ...(dateFrom && { date_from: dateFrom }),
    ...(dateTo   && { date_to: dateTo }),
  }).toString()}`;

  return (
    <div className="bg-white rounded-xl p-4 mb-6 shadow-sm">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <select className="border p-2 rounded-lg w-full" value={type} onChange={handleTypeChange}>
          {VIOLATION_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select className="border p-2 rounded-lg w-full">
          {SHIFT_OPTIONS.map(o => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
      <div className="grid grid-cols-2 gap-4 mb-4">
        <input type="date" className="border p-2 rounded-lg w-full"
          value={dateFrom} onChange={handleDateFrom} />
        <input type="date" className="border p-2 rounded-lg w-full"
          value={dateTo} onChange={handleDateTo} />
      </div>
      <div className="flex justify-end">
        <a href={exportUrl} download
          className="border px-4 py-2 rounded-lg hover:bg-gray-100 text-sm font-medium">
          Export CSV
        </a>
      </div>
    </div>
  );
}