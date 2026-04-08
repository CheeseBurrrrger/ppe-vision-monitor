import React from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell 
} from 'recharts';

const weeklyData = [
  { day: 'Monday', Vest: 15, Helmet: 20, Shoes: 8, Gloves: 10 },
  { day: 'Tuesday', Vest: 16, Helmet: 22, Shoes: 10, Gloves: 18 },
  { day: 'Wednesday', Vest: 14, Helmet: 21, Shoes: 9, Gloves: 15 },
  { day: 'Thursday', Vest: 15, Helmet: 23, Shoes: 11, Gloves: 17 },
  { day: 'Friday', Vest: 16, Helmet: 22, Shoes: 9, Gloves: 13 },
  { day: 'Saturday', Vest: 15, Helmet: 21, Shoes: 10, Gloves: 14 },
];

// DATA YANG HARUS ADA (Agar tidak error ReferenceError)
const hourlyData = Array.from({ length: 17 }, (_, i) => ({ 
  time: `${i + 8}:00`, 
  value: Math.floor(Math.random() * 8) 
}));

// Data untuk Donut Chart sesuai UI
const pieData = [
  { name: 'Vest', value: 52, color: '#22C55E' },
  { name: 'Helmet', value: 44, color: '#FACC15' },
  { name: 'Shoes', value: 30, color: '#92400E' },
  { name: 'Gloves', value: 22, color: '#0250C5' },
];

const ChartsSection = () => {
  return (
<div className="space-y-6">
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    
    {/* Kiri: Bar Chart (Trend Jenis Pelanggaran) */}
    <div className="lg:col-span-2 bg-white p-6 rounded-xl shadow-sm border border-gray-100">
      <div className="mb-6">
        <h4 className="text-sm font-bold text-gray-800">Trend Jenis Pelanggaran</h4>
        <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">29 Maret 2026 - 4 April 2026</p>
      </div>
      <div className="h-[300px] w-full">
        {/* UBAH width menjadi 100% */}
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={weeklyData}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
            <Tooltip />
            <Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{ fontSize: '10px', paddingBottom: '20px' }} />
            <Bar dataKey="Vest" fill="#22C55E" radius={[2, 2, 0, 0]} barSize={10} />
            <Bar dataKey="Helmet" fill="#FACC15" radius={[2, 2, 0, 0]} barSize={10} />
            <Bar dataKey="Shoes" fill="#92400E" radius={[2, 2, 0, 0]} barSize={10} />
            <Bar dataKey="Gloves" fill="#0250C5" radius={[2, 2, 0, 0]} barSize={10} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>

    {/* Kanan: Donut Chart */}
    <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100 relative h-[380px]">
      <div className="h-full w-full flex items-center justify-center">
        {/* UBAH width menjadi 100% dan HAPUS width/height di PieChart */}
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={pieData}
              dataKey="value"
              innerRadius={60}
              outerRadius={85}
              paddingAngle={5}
              stroke="none"
            >
              {pieData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.color} />
              ))}
            </Pie>
            <Tooltip />
            <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" />
          </PieChart>
        </ResponsiveContainer>
        
        {/* Angka Total di Tengah */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none pr-12">
          <span className="text-3xl font-extrabold text-gray-800">148</span>
          <span className="text-[10px] font-bold text-gray-400 uppercase">Total</span>
        </div>
      </div>
    </div>
  </div>

  {/* Bar Chart Bawah */}
  <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-100">
    <h4 className="text-sm font-bold text-gray-800 mb-6">Pelanggaran Hari Ini</h4>
    <div className="h-[200px] w-full">
      {/* UBAH width menjadi 100% */}
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={hourlyData}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
          <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
          <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
          <Bar dataKey="value" fill="#FF5722" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  </div>
</div>
  );
};

export default ChartsSection;