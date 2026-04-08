import React, { useState } from "react";
import Sidebar from "../components/Sidebar";
import Header from "../components/Header";
import StatsOverview from "../components/StatsOverview"; // Komponen baru
import ChartsSection from "../components/ChartsSection"; // Komponen baru
import FilterBar from "../components/FilterBar";
import LogTable from "../components/LogTable";
import LiveCam from "../components/LiveCam";

export default function Dashboard() {
  // State untuk melacak menu mana yang aktif
  const [activeMenu, setActiveMenu] = useState("Dashboard");

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
            <div className="space-y-6">
              <StatsOverview />
              <ChartsSection />
            </div>
          )}
          
          {activeMenu === "Live Cam" && <LiveCam />}
          
          {activeMenu === "Log Pelanggaran" && (
            <div className="space-y-4"> {/* Tambahkan wrapper div agar rapi */}
              <FilterBar />
              <LogTable />
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