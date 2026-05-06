import React from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
  PieChart, Pie, Cell 
} from 'recharts';

const ChartsSection = ({ hourlyData = [], pieData = {} }) => {
  
  // 1. Transformasi data untuk Donut Chart (pieData dari backend berupa object)
  const formattedPieData = [
    { name: 'Vest',   value: pieData.no_vest || 0, color: '#22C55E' },
    { name: 'Helmet', value: pieData.no_helmet || 0, color: '#FACC15' },
    { name: 'Shoes',  value: pieData.no_shoes || 0, color: '#92400E' },
    { name: 'Gloves', value: pieData.no_gloves || 0, color: '#0250C5' },
  ];

  // Hitung total untuk angka di tengah donut
  const totalViolations = formattedPieData.reduce((acc, curr) => acc + curr.value, 0);

  // 2. Transformasi data untuk Bar Chart Harian (hourlyData dari backend)
  // Backend mengirim: [{hour: 8, count: 2}, ...]
  const formattedHourlyData = Array.from({ length: 24 }, (_, i) => {
    const found = hourlyData.find(d => d.hour === i);
    return {
      time: `${i}:00`,
      value: found ? found.count : 0
    };
  }).slice(7, 23); // Kita ambil jam 07:00 sampai 22:00 agar rapi

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        
        {/* Kiri: Bar Chart Trend (Sementara pakai dummy karena backend belum kirim tren mingguan) */}
        <div className="col-span-2 bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col">
          <div className="mb-3">
            <h4 className="text-sm font-bold text-gray-800">Trend Jenis Pelanggaran</h4>
            <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">
               Data Real-time Database
            </p>
          </div>
          <div className="w-full" style={{ height: 'clamp(160px, 30vh, 320px)' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={formattedPieData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#0250C5" radius={[2,2,0,0]} barSize={30} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Kanan: Donut Chart (Data Asli) */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col items-center justify-center relative"
          style={{ height: 'clamp(220px, 38vh, 400px)' }}
        >
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={formattedPieData}
                dataKey="value"
                innerRadius="40%"
                outerRadius="60%"
                paddingAngle={5}
                stroke="none"
              >
                {formattedPieData.map((entry, index) => (
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

          <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
            style={{ paddingRight: '30%' }}
          >
            <span className="text-2xl font-extrabold text-gray-800">{totalViolations}</span>
            <span className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Total</span>
          </div>
        </div>
      </div>

      {/* Row 2: Bar Chart Harian (Data Asli) */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <h4 className="text-sm font-bold text-gray-800 mb-3">Pelanggaran Hari Ini (Per Jam)</h4>
        <div className="w-full" style={{ height: 'clamp(120px, 20vh, 220px)' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={formattedHourlyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
              <Tooltip />
              <Bar dataKey="value" fill="#FF5722" radius={[4,4,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default ChartsSection;