import { useEffect, useState } from "react";
import axios from "axios";
import DetailPegawai from "./DetailPegawai";

const API_BASE = "http://localhost:8000";

export default function RekapPegawai() {
  const [selected, setSelected] = useState(null);
  const [search, setSearch] = useState("");
  const [pegawai, setPegawai] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const fetchPegawai = async () => {
      try {
        setLoading(true);
        const token = localStorage.getItem("access_token");
        const { data } = await axios.get(`${API_BASE}/pegawai/rekap`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        });
        setPegawai(data);
      } catch (err) {
        console.error("Gagal mengambil rekap pegawai:", err);
        setError(err.response?.data?.detail || "Gagal mengambil data pegawai");
      } finally {
        setLoading(false);
      }
    };
    fetchPegawai();
  }, []);

  if (selected) {
    return (
      <DetailPegawai
        pegawai={selected}
        onBack={() => setSelected(null)}
      />
    );
  }

  const filtered = pegawai.filter((p) =>
    p.nama.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="bg-white rounded-xl border border-[#d4cfc4] px-4 py-3 flex items-center gap-3">
        <svg className="w-4 h-4 text-stone-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M21 21l-4.35-4.35M17 11A6 6 0 1 1 5 11a6 6 0 0 1 12 0z" />
        </svg>
        <input
          type="text"
          placeholder="Cari nama pegawai..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="flex-1 bg-transparent text-sm text-stone-700 placeholder-stone-400 outline-none"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-[#d4cfc4] overflow-hidden">
        <div className="px-6 py-4 border-b border-[#e8e3d8]">
          <h2 className="text-base font-bold text-stone-800">Rekap Pelanggaran Pegawai</h2>
          <p className="text-xs text-stone-400 mt-0.5">
            Total {pegawai.length} pegawai terdaftar
          </p>
        </div>

        {loading ? (
          <div className="px-6 py-10 text-center text-sm text-stone-400">Memuat data pegawai...</div>
        ) : error ? (
          <div className="px-6 py-10 text-center text-sm text-red-500">{error}</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="bg-[#f5f2ec] text-xs font-semibold text-stone-500 uppercase tracking-wide">
                <th className="text-left px-6 py-3 w-16">#</th>
                <th className="text-left px-6 py-3">Kode</th>
                <th className="text-left px-6 py-3">Nama Pegawai</th>
                <th className="text-left px-6 py-3">Divisi</th>
                <th className="text-right px-6 py-3">Jumlah Pelanggaran</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((p, idx) => (
                <tr
                  key={p.id}
                  className="border-t border-[#f0ece3] hover:bg-[#faf8f4] transition-colors"
                >
                  <td className="px-6 py-3.5 text-sm text-stone-400">
                    {String(idx + 1).padStart(3, "0")}
                  </td>
                  <td className="px-6 py-3.5 text-sm text-stone-600 font-mono">
                    {p.employee_code}
                  </td>
                  <td className="px-6 py-3.5">
                    <button
                      onClick={() => setSelected(p)}
                      className="text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline transition-colors text-left"
                    >
                      {p.nama}
                    </button>
                  </td>
                  <td className="px-6 py-3.5 text-sm text-stone-500">
                    {p.divisi || "-"}
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    <span
                      className={`inline-block text-sm font-bold px-3 py-1 rounded-full ${
                        p.pelanggaran >= 15
                          ? "bg-red-100 text-red-600"
                          : p.pelanggaran >= 8
                          ? "bg-orange-100 text-orange-600"
                          : "bg-green-100 text-green-700"
                      }`}
                    >
                      {p.pelanggaran}
                    </span>
                  </td>
                </tr>
              ))}

              {filtered.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-6 py-10 text-center text-sm text-stone-400">
                    Pegawai tidak ditemukan.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
