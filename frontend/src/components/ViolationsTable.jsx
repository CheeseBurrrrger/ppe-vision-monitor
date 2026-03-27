import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getViolations } from '../../api/violationApi';
import { CSVLink } from 'react-csv'; // Install: npm install react-csv

const ViolationTable = () => {
  const [filterType, setFilterType] = useState('All');

  // 1. Fetch data menggunakan React Query
  const { data: violations = [], isLoading, isError } = useQuery({
    queryKey: ['violations'],
    queryFn: getViolations,
  });

  // 2. Logika Filtering (Tugas Slicing & Monitoring)
  const filteredData = filterType === 'All' 
    ? violations 
    : violations.filter(v => v.violation_type === filterType);

  if (isLoading) return <div className="p-10 text-center">Memuat data log...</div>;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header Tabel & Actions */}
      <div className="p-4 border-b flex justify-between items-center bg-slate-50">
        <div className="flex gap-2">
          <select 
            className="border rounded-lg px-3 py-2 text-sm outline-none"
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="All">Semua Pelanggaran</option>
            <option value="No Helmet">Tanpa Helm</option>
            <option value="No Vest">Tanpa Rompi</option>
            <option value="No Boots">Tanpa Sepatu</option>
          </select>
        </div>

        {/* Fitur Ekspor CSV */}
        <CSVLink 
          data={filteredData} 
          filename={"rekap-pelanggaran-k3.csv"}
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm transition"
        >
          Ekspor CSV
        </CSVLink>
      </div>

      {/* Tabel Log */}
      <table className="w-full text-left border-collapse">
        <thead className="bg-slate-100 text-slate-600 text-sm">
          <tr>
            <th className="p-4 font-semibold">Waktu</th>
            <th className="p-4 font-semibold">Jenis Pelanggaran</th>
            <th className="p-4 font-semibold">Lokasi</th>
            <th className="p-4 font-semibold">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y text-slate-700">
          {filteredData.map((v) => (
            <tr key={v.id} className="hover:bg-slate-50 transition">
              <td className="p-4 text-sm">{v.timestamp}</td>
              <td className="p-4">
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  v.violation_type === 'No Helmet' ? 'bg-red-100 text-red-700' : 'bg-orange-100 text-orange-700'
                }`}>
                  {v.violation_type}
                </span>
              </td>
              <td className="p-4 text-sm">{v.location || 'Area Pabrik'}</td>
              <td className="p-4 text-xs text-slate-500 italic">Terekam</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ViolationTable;