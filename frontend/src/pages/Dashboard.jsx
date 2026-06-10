import React, { useState } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import {StatsOverview} from "../components/StatsOverview"; // Komponen baru
import ChartsSection from "../components/ChartsSection"; // Komponen baru
import { LogTable } from '../components/LogTable';
import FilterBar from "../components/FilterBar";
// import LogTable from "../components/LogTable";
import LiveCam from "../components/LiveCam";
import DashboardCamFeed from "../components/DashboardCamFeed";
import { useCameraDevices } from "../hooks/useCameraDevices";



export default function Dashboard() {
  // State untuk melacak menu mana yang aktif
  const [activeMenu, setActiveMenu] = useState("Dashboard");
  const [filters, setFilters] = useState({ type: "", shift: "", dateFrom: "", dateTo: "" });
  const { cameraSlots, refresh } = useCameraDevices(3);


return (
    <div className="flex h-screen bg-[#E5DCC5] overflow-hidden">
      {/* Sidebar tetap di kiri */}
      <Sidebar activeMenu={activeMenu} setActiveMenu={setActiveMenu} />

      <div className="flex-1 flex flex-col min-h-0"> 
        {/* Header tetap di atas */}
        <Header />
        
        {/* Area konten yang bisa di-scroll */}
        <main className="flex-1 p-6 overflow-y-auto custom-scrollbar">
          {activeMenu === "Dashboard" && (
            <div className="flex gap-6 h-full">
              {/* Left: Stats + Charts */}
              <div className="flex-1 space-y-6 min-w-0">
                <StatsOverview />
                <ChartsSection />
              </div>

              {/* Right: Live Camera Panel */}
              <div className="w-80 shrink-0 flex flex-col gap-4">
                <h2 className="text-sm font-bold text-gray-700 uppercase tracking-widest">Live Camera</h2>
                <DashboardCamFeed
                  label="Ruang Produksi 1"
                  device={cameraSlots[0]}
                  allowDefaultCamera={!cameraSlots[0]?.deviceId}
                  onStreamReady={refresh}
                />
                <DashboardCamFeed
                  label="Ruang Produksi 2"
                  device={cameraSlots[1]}
                  onStreamReady={refresh}
                />
              </div>
            </div>
          )}
          
          {activeMenu === "Live Cam" && <LiveCam />}
          
          {activeMenu === "Log Pelanggaran" && (
            <div className="space-y-4"> {/* Tambahkan wrapper div agar rapi */}
              <FilterBar onFilterChange={setFilters} />
              <LogTable filters={filters} />
            </div>
          )}

          {activeMenu === "Tentang Sistem" && (
            <div className="bg-white p-6 rounded-xl shadow-sm">
              <h2 className="text-xl font-bold">Tentang VisionGuard</h2>
              <p className="mt-2 text-gray-600">Sistem monitoring K3 berbasis AI...</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
