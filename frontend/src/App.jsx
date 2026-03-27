// src/App.jsx
import React from 'react';

function App() {
  return (
    <div className="flex h-screen bg-slate-50">
      {/* Sidebar */}
      <div className="w-64 bg-slate-900 text-white p-6 flex flex-col">
        <h1 className="text-xl font-bold mb-8 text-amber-500">Monitoring K3</h1>
        <nav className="space-y-4">
          <div className="p-3 bg-slate-800 rounded-lg cursor-pointer">Review Mode</div>
          <div className="p-3 hover:bg-slate-800 rounded-lg cursor-pointer text-slate-400">Live Mode</div>
        </nav>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white border-b flex items-center px-8 justify-between">
          <h2 className="font-semibold text-slate-700">Rekap Historis Pelanggaran</h2>
          <div className="text-sm text-slate-500">Admin Pabrik</div>
        </header>
        
        <main className="flex-1 overflow-y-auto p-8">
          {/* Dashboard Content akan di sini */}
          <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
            <p className="text-slate-500">Selamat datang! Siap untuk memproses data Computer Vision.</p>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;