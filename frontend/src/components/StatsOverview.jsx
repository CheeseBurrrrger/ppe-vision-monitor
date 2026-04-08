const StatCard = ({ title, value, change, isUp }) => (
  <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm text-center">
    <h3 className="text-[10px] font-bold uppercase text-gray-600 mb-2 h-8 flex items-center justify-center leading-tight">
      {title}
    </h3>
    <p className="text-3xl font-bold mb-1">{value}</p>
    <p className={`text-[10px] font-bold ${isUp ? 'text-red-500' : 'text-green-500'}`}>
      {isUp ? '+' : ''}{change}% <span className="text-gray-400 font-normal">vs minggu lalu</span>
    </p>
  </div>
);

export default function StatsOverview() {
  return (
    <div className="grid grid-cols-5 gap-4 mb-6">
      <StatCard title="Total Pelanggaran" value="148" change="12" isUp={true} />
      <StatCard title="Tanpa Helm Safety" value="44" change="62" isUp={true} />
      <StatCard title="Tanpa Sarung Tangan" value="22" change="20" isUp={false} />
      <StatCard title="Tanpa Vest" value="52" change="15" isUp={false} />
      <StatCard title="Tanpa Sepatu Safety" value="30" change="2" isUp={true} />
    </div>
  );
}