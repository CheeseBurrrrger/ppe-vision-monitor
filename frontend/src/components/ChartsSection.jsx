import React from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell 
} from 'recharts';

const weeklyData = [
  { day: 'Monday',    Vest: 15, Helmet: 20, Shoes: 8,  Gloves: 10 },
  { day: 'Tuesday',   Vest: 16, Helmet: 22, Shoes: 10, Gloves: 18 },
  { day: 'Wednesday', Vest: 14, Helmet: 21, Shoes: 9,  Gloves: 15 },
  { day: 'Thursday',  Vest: 15, Helmet: 23, Shoes: 11, Gloves: 17 },
  { day: 'Friday',    Vest: 16, Helmet: 22, Shoes: 9,  Gloves: 13 },
  { day: 'Saturday',  Vest: 15, Helmet: 21, Shoes: 10, Gloves: 14 },
];

const hourlyData = Array.from({ length: 17 }, (_, i) => ({ 
  time: `${i + 8}:00`, 
  value: Math.floor(Math.random() * 8) 
}));

const pieData = [
  { name: 'Vest',   value: 52, color: '#22C55E' },
  { name: 'Helmet', value: 44, color: '#FACC15' },
  { name: 'Shoes',  value: 30, color: '#92400E' },
  { name: 'Gloves', value: 22, color: '#0250C5' },
];

const ChartsSection = () => {
  return (
    <div className="space-y-4">

      {/* Row 1: Bar Chart + Donut Chart */}
      <div className="grid grid-cols-3 gap-4">

        {/* Kiri: Bar Chart Trend */}
        <div className="col-span-2 bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col">
          <div className="mb-3">
            <h4 className="text-sm font-bold text-gray-800">Trend Jenis Pelanggaran</h4>
            <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">
              29 Maret 2026 - 4 April 2026
            </p>
          </div>
          {/* vh-based height: 30% tinggi layar, min 160px agar tidak terlalu kecil */}
          <div className="w-full" style={{ height: 'clamp(160px, 30vh, 320px)' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={weeklyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend 
                  verticalAlign="top" 
                  align="right" 
                  iconType="circle" 
                  wrapperStyle={{ fontSize: '10px', paddingBottom: '10px' }} 
                />
                <Bar dataKey="Vest"   fill="#22C55E" radius={[2,2,0,0]} barSize={10} />
                <Bar dataKey="Helmet" fill="#FACC15" radius={[2,2,0,0]} barSize={10} />
                <Bar dataKey="Shoes"  fill="#92400E" radius={[2,2,0,0]} barSize={10} />
                <Bar dataKey="Gloves" fill="#0250C5" radius={[2,2,0,0]} barSize={10} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Kanan: Donut Chart */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col items-center justify-center relative"
          style={{ height: 'clamp(220px, 38vh, 400px)' }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                dataKey="value"
                innerRadius="40%"   /* pakai % agar skala ikut ukuran container */
                outerRadius="60%"
                paddingAngle={5}
                stroke="none"
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend 
                layout="vertical" 
                align="right" 
                verticalAlign="middle" 
                iconType="circle"
                wrapperStyle={{ fontSize: '11px' }}
              />
            </PieChart>
          </ResponsiveContainer>

          {/* Label total di tengah donut */}
          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
            style={{ paddingRight: '30%' }} /* dorong ke kiri menjauhi legend */
          >
            <span className="text-2xl font-extrabold text-gray-800">148</span>
            <span className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Total</span>
          </div>
        </div>
      </div>

      {/* Row 2: Bar Chart Harian */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <h4 className="text-sm font-bold text-gray-800 mb-3">Pelanggaran Hari Ini</h4>
        {/* vh-based: 20% tinggi layar, min 120px */}
        <div className="w-full" style={{ height: 'clamp(120px, 20vh, 220px)' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hourlyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
              <Bar dataKey="value" fill="#FF5722" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

    </div>
  );
};

export default ChartsSection;