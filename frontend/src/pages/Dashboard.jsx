import React, { useState, useEffect } from "react";
import axios from "axios";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import StatsOverview from "../components/StatsOverview";
import ChartsSection from "../components/ChartsSection";
import FilterBar from "../components/FilterBar";
import LogTable from "../components/LogTable";
import LiveCam from "../components/LiveCam";
import DashboardCamFeed from "../components/DashboardCamFeed";
import RekapPegawai from "../components/RekapPegawai";

const api = axios.create({
  baseURL: "http://localhost:8000",
});

export default function Dashboard({ onLogout }) {
  const [activeMenu, setActiveMenu] = useState("Dashboard");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem("access_token");
      const response = await api.get("/stats", {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      setStats(response.data);
    } catch (error) {
      console.error("Gagal mengambil data stats:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeMenu === "Dashboard") {
      fetchStats();
    }
  }, [activeMenu]);

  return (
    <div className="flex h-screen bg-[#E5DCC5] overflow-hidden">
      <Sidebar activeMenu={activeMenu} setActiveMenu={setActiveMenu} onLogout={onLogout} />

      <div className="flex-1 flex flex-col min-h-0">
        <Header />

        <main className="flex-1 p-6 overflow-y-auto custom-scrollbar">

          {/* Dashboard */}
          {activeMenu === "Dashboard" && (
            <div className="flex gap-6 h-full">
              {/* Left: Stats + Charts */}
              <div className="flex-1 space-y-6 min-w-0">
                {loading ? (
                  <div className="flex justify-center items-center h-64 text-gray-600 font-bold">
                    Memuat data dari database...
                  </div>
                ) : (
                  <>
                    <StatsOverview stats={stats} />
                    <ChartsSection
                      hourlyData={stats?.by_hour || []}
                      pieData={stats?.by_type || {}}
                    />
                  </>
                )}
              </div>

              {/* Right: Live Camera Panel */}
              <div className="w-80 shrink-0 flex flex-col gap-4">
                <h2 className="text-sm font-bold text-gray-700 uppercase tracking-widest">
                  Live Camera
                </h2>
                <DashboardCamFeed label="Ruang Produksi 1" cameraIndex={0} />
                <DashboardCamFeed label="Ruang Produksi 2" cameraIndex={1} />
              </div>
            </div>
          )}

          {/* Live Cam */}
          {activeMenu === "Live Cam" && <LiveCam />}

          {/* Log Pelanggaran */}
          {activeMenu === "Log Pelanggaran" && (
            <div className="space-y-4">
              <FilterBar />
              <LogTable />
            </div>
          )}
          {activeMenu === "Rekap Pegawai" && <RekapPegawai />}

          {/* Tentang Sistem */}
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
