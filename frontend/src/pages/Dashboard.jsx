import React, { useState, useEffect } from "react";
import axios from "axios"; // Pastikan sudah install: npm install axios
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import StatsOverview from "../components/StatsOverview";
import ChartsSection from "../components/ChartsSection";
import FilterBar from "../components/FilterBar";
import LogTable from "../components/LogTable";
import LiveCam from "../components/LiveCam";

// Buat instance axios agar lebih rapi
const api = axios.create({
  baseURL: "http://localhost:8000", 
});

export default function Dashboard() {
  const [activeMenu, setActiveMenu] = useState("Dashboard");
  
  // State untuk menyimpan data dari backend
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fungsi untuk mengambil data statistik (untuk Dashboard)
  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await api.get("/stats");
      setStats(response.data);
    } catch (error) {
      console.error("Gagal mengambil data stats:", error);
    } finally {
      setLoading(false);
    }
  };

  // Jalankan fetch saat komponen pertama kali dimuat
  useEffect(() => {
    if (activeMenu === "Dashboard") {
      fetchStats();
    }
  }, [activeMenu]);

  return (
    <div className="flex h-screen bg-[#E5DCC5] overflow-hidden">
      {/* Sidebar tetap di kiri */}
      <Sidebar activeMenu={activeMenu} setActiveMenu={setActiveMenu} />

      <div className="flex-1 flex flex-col min-h-0"> 
        {/* Header tetap di atas */}
        <Header />
        
        {/* Area konten yang bisa di-scroll */}
        <main className="flex-1 p-6 overflow-y-auto custom-scrollbar">
          
          {/* Tampilan Dashboard */}
          {activeMenu === "Dashboard" && (
            <div className="space-y-6">
              {loading ? (
                <div className="flex justify-center items-center h-64 text-gray-600 font-bold">
                  Memuat data dari database...
                </div>
              ) : (
                <>
                  {/* StatsOverview sekarang menerima data asli */}
                  <StatsOverview stats={stats} />
                  {/* ChartsSection menerima data by_hour dan by_type */}
                  <ChartsSection 
                    hourlyData={stats?.by_hour || []} 
                    pieData={stats?.by_type || {}} 
                  />
                </>
              )}
            </div>
          )}
          
          {/* Tampilan Live Cam */}
          {activeMenu === "Live Cam" && <LiveCam />}
          
          {/* Tampilan Log Pelanggaran */}
          {activeMenu === "Log Pelanggaran" && (
            <div className="space-y-4">
              <FilterBar />
              {/* LogTable bisa melakukan fetch sendiri ke /violations */}
              <LogTable />
            </div>
          )}

          {/* Tampilan Tentang Sistem */}
          {activeMenu === "Tentang Sistem" && (
            <div className="bg-[#f1eada] p-8 rounded-2xl shadow-sm border-l-[10px] border-black">
              <h2 className="text-3xl font-extrabold text-[#373d3f]">Tentang VisionGuard</h2>
              <p className="mt-4 text-lg text-gray-700 leading-relaxed font-medium">
                VisionGuard adalah sistem monitoring K3 berbasis AI yang dirancang untuk 
                mendeteksi penggunaan APD secara real-time di lingkungan industri. 
                Sistem ini membantu memastikan keselamatan pekerja dengan mendeteksi 
                pelanggaran seperti tidak memakai helm, rompi, atau sepatu safety.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}