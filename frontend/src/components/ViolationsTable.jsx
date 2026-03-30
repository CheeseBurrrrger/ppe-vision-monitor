import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getViolations } from '../../api/violationApi';
import { CSVLink } from 'react-csv';

const ViolationTable = () => {
  const [filterType, setFilterType] = useState('All');

  // 1. Fetch data menggunakan React Query
  const { data: violations = [], isLoading, isError } = useQuery({
    queryKey: ['violations'],
    queryFn: getViolations,
  });

  // 2. Logika Filtering disesuaikan dengan isi database (lowercase)
  const filteredData = filterType === 'All' 
    ? violations 
    : violations.filter(v => v.violation_type === filterType);

  if (isLoading) return <div className="p-10 text-center font-medium text-slate-500">Memuat log K3...</div>;
  if (isError) return <div className="p-10 text-center text-red-500">Gagal mengambil data dari Backend.</div>;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* Header Tabel & Actions */}
      <div className="p-4 border-b flex justify-between items-center bg-slate-50">
        <div className="flex gap-2">
          <select 
            className="border rounded-lg px-3 py-2 text-sm outline-none bg-white focus:ring-2 focus:ring-blue-500"
            onChange={(e) => setFilterType(e.target.value)}
          >
            <option value="All">Semua Pelanggaran</option>
            <option value="no_helmet">Tanpa Helm (No Helmet)</option>
            <option value="no_vest">Tanpa Rompi (No Vest)</option>
          </select>
        </div>

        {/* Fitur Ekspor CSV */}
        <CSVLink 
          data={filteredData} 
          filename={`rekap-k3-${new Date().toLocaleDateString()}.csv`}
          className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition shadow-sm"
        >
          📊 Ekspor CSV
        </CSVLink>
      </div>

      {/* Tabel Log */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead className="bg-slate-100 text-slate-600 text-xs uppercase tracking-wider">
            <tr>
              <th className="p-4 font-bold">Waktu</th>
              <th className="p-4 font-bold">Jenis Pelanggaran</th>
              <th className="p-4 font-bold">Confidence</th>
              <th className="p-4 font-bold">ID Kamera</th>
              <th className="p-4 font-bold">Aksi</th>
            </tr>
          </thead>
          <tbody className="divide-y text-slate-700">
            {filteredData.length > 0 ? filteredData.map((v) => (
              <tr key={v.id} className="hover:bg-slate-50/80 transition text-sm">
                <td className="p-4 font-medium">
                  {new Date(v.timestamp).toLocaleString('id-ID')}
                </td>
                <td className="p-4">
                  <span className={`px-3 py-1 rounded-full text-[11px] font-bold uppercase ${
                    v.violation_type === 'no_helmet' 
                      ? 'bg-red-100 text-red-700 border border-red-200' 
                      : 'bg-orange-100 text-orange-700 border border-orange-200'
                  }`}>
                    {v.violation_type.replace('_', ' ')}
                  </span>
                </td>
                <td className="p-4">
                   <span className="font-mono text-slate-600">
                     {(v.confidence * 100).toFixed(1)}%
                   </span>
                </td>
                <td className="p-4 text-slate-600 font-medium">
                  {v.camera_id || 'CAM-DEFAULT'}
                </td>
                <td className="p-4">
                  <button className="text-blue-600 hover:text-blue-800 text-xs font-semibold underline">
                    Lihat Bukti
                  </button>
                </td>
              </tr>
            )) : (
              <tr>
                <td colSpan="5" className="p-10 text-center text-slate-400 italic">
                  Tidak ada data pelanggaran ditemukan.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ViolationTable;