const StatCard = ({ title, value, change, isUp }) => (
  <div className="bg-white px-2 py-3 rounded-xl border border-gray-200 shadow-sm text-center min-w-0">
    <h3 className="text-[9px] font-bold uppercase text-gray-600 mb-1 leading-tight 
                   min-h-[2rem] flex items-center justify-center">
      {title}
    </h3>
    {/* ⬇️ text-2xl bukan text-3xl agar tidak terlalu besar */}
    <p className="text-2xl font-bold mb-1 truncate">{value}</p>
    <p className={`text-[9px] font-bold ${isUp ? 'text-red-500' : 'text-green-500'}`}>
      {isUp ? '+' : ''}{change}%{' '}
      <span className="text-gray-400 font-normal">vs minggu lalu</span>
    </p>
  </div>
);

export default function StatsOverview() {
  return (
    // ⬇️ grid-cols-5 diganti pakai minmax agar card bisa shrink
    <div className="grid gap-3" style={{ 
      gridTemplateColumns: 'repeat(5, minmax(0, 1fr))' 
    }}>
      <StatCard title="Total Pelanggaran"   value="148" change="12" isUp={true}  />
      <StatCard title="Tanpa Helm Safety"   value="44"  change="62" isUp={true}  />
      <StatCard title="Tanpa Sarung Tangan" value="22"  change="20" isUp={false} />
      <StatCard title="Tanpa Vest"          value="52"  change="15" isUp={false} />
      <StatCard title="Tanpa Sepatu Safety" value="30"  change="2"  isUp={true}  />
    </div>
  );
}