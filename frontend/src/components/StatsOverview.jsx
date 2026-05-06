import React from "react";

const StatCard = ({ title, value, change, isUp }) => (
  <div className="bg-white px-2 py-3 rounded-xl border border-gray-200 shadow-sm text-center min-w-0">
    <h3 className="text-[9px] font-bold uppercase text-gray-600 mb-1 leading-tight 
                   min-h-[2rem] flex items-center justify-center text-center">
      {title}
    </h3>
    <p className="text-2xl font-bold mb-1 truncate">{value}</p>
    {/* Kita biarkan persentase ini statis atau 0 jika backend belum menyediakan perbandingan mingguan */}
    <p className={`text-[9px] font-bold ${isUp ? 'text-red-500' : 'text-green-500'}`}>
      {isUp ? '+' : ''}{change}%{' '}
      <span className="text-gray-400 font-normal">vs minggu lalu</span>
    </p>
  </div>
);

// Tambahkan { stats } sebagai props yang diterima dari Dashboard.jsx
export default function StatsOverview({ stats }) {
  // Jika data stats belum datang (null), gunakan angka 0 agar tidak error
  const data = stats || {
    total_violations: 0,
    by_type: {
      no_helmet: 0,
      no_gloves: 0,
      no_vest: 0,
      no_shoes: 0
    }
  };

  return (
    <div className="grid gap-3" style={{ 
      gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' 
    }}>
      {/* Ambil data sesuai dengan struktur JSON dari FastAPI Anda:
          total_violations dan by_type
      */}
      <StatCard 
        title="Total Pelanggaran"   
        value={data.total_violations} 
        change="0" 
        isUp={true}  
      />
      <StatCard 
        title="Tanpa Helm Safety"   
        value={data.by_type.no_helmet || 0}  
        change="0" 
        isUp={true}  
      />
      <StatCard 
        title="Tanpa Sarung Tangan" 
        value={data.by_type.no_gloves || 0}  
        change="0" 
        isUp={false} 
      />
      <StatCard 
        title="Tanpa Vest"           
        value={data.by_type.no_vest || 0}    
        change="0" 
        isUp={false} 
      />
      <StatCard 
        title="Tanpa Sepatu Safety" 
        value={data.by_type.no_shoes || 0}   
        change="0" 
        isUp={true}  
      />
    </div>
  );
}