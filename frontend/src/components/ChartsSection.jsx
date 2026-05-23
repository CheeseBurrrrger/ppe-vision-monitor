import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/violationApi";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";

const PPE_COLORS = {
  no_vest:    "#22C55E",
  no_helmet:  "#FACC15",
  no_boots:   "#92400E",
  no_gloves:  "#0250C5",
  no_goggles: "#F97316",
};

const PPE_LABELS = {
  no_vest:    "Rompi",
  no_helmet:  "Helm",
  no_boots:   "Sepatu",
  no_gloves:  "Srt Tgn",
  no_goggles: "Goggle",
};

const DAYS_ID = ["Min", "Sen", "Sel", "Rab", "Kam", "Jum", "Sab"];

const ChartSkeleton = ({ height }) => (
  <div className="w-full bg-slate-100 animate-pulse rounded-lg" style={{ height }} />
);

// Parse "2024-01-15" without timezone shift
const parseDayLabel = (dateStr) => {
  const [y, m, d] = dateStr.split("-").map(Number);
  return DAYS_ID[new Date(y, m - 1, d).getDay()];
};

const ChartsSection = () => {
  const { data, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 10000,
  });
  console.log("stats data:", data);          
  console.log("by_day:", data?.by_day);

  const pieData = Object.entries(data?.by_type ?? {}).map(([key, value]) => ({
    name:  PPE_LABELS[key] ?? key,
    value,
    color: PPE_COLORS[key] ?? "#94A3B8",
  }));

  const totalViolations = data?.total_violations ?? 0;
  const totalPie = pieData.reduce((s, d) => s + d.value, 0);

  const hourlyData = (data?.by_hour ?? []).map((row) => ({
    time:  `${String(row.hour).padStart(2, "0")}:00`,
    value: row.count,
  }));

  const weeklyRaw = data?.by_day ?? [];
  const weeklyData = weeklyRaw.map((row) => ({
    day:       parseDayLabel(row.date),   // ← fixed timezone issue
    Helm:      row.no_helmet  ?? 0,
    Rompi:     row.no_vest    ?? 0,
    Sepatu:    row.no_boots   ?? 0,
    "Srt Tgn": row.no_gloves  ?? 0,
    Goggle:    row.no_goggles ?? 0,
  }));

  const hasWeeklyData = weeklyData.length > 0;

  return (
    <div className="space-y-4">

      {/* Row 1: Weekly trend (2/3) + Donut (1/3) */}
      <div className="grid grid-cols-3 gap-4 items-start">

        {/* Weekly bar chart */}
        <div className="col-span-2 bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col">
          <h4 className="text-sm font-bold text-gray-800">Trend Jenis Pelanggaran</h4>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-3">
            7 hari terakhir
          </p>

          {/* Custom legend — above chart, no Recharts Legend */}
          {hasWeeklyData && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 mb-2">
              {Object.entries(PPE_LABELS).map(([key, label]) => (
                <span key={key} className="flex items-center gap-1 text-[10px] text-gray-500">
                  <span
                    className="inline-block w-2 h-2 rounded-sm flex-shrink-0"
                    style={{ background: PPE_COLORS[key] }}
                  />
                  {label}
                </span>
              ))}
            </div>
          )}

          <div className="w-full" style={{ height: "clamp(160px, 28vh, 300px)" }}>
            {isLoading ? (
              <ChartSkeleton height="100%" />
            ) : !hasWeeklyData ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2">
                <span className="text-3xl">📊</span>
                <p className="text-xs font-medium">Data trend mingguan belum tersedia</p>
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={weeklyData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                  <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="Rompi"    fill="#22C55E" radius={[2,2,0,0]} barSize={8} />
                  <Bar dataKey="Helm"     fill="#FACC15" radius={[2,2,0,0]} barSize={8} />
                  <Bar dataKey="Sepatu"   fill="#92400E" radius={[2,2,0,0]} barSize={8} />
                  <Bar dataKey="Srt Tgn"  fill="#0250C5" radius={[2,2,0,0]} barSize={8} />
                  <Bar dataKey="Goggle"   fill="#F97316" radius={[2,2,0,0]} barSize={8} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Donut chart — NO Recharts Legend inside */}
        <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100 flex flex-col">
          <h4 className="text-sm font-bold text-gray-800">Distribusi tipe</h4>
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-2">
            Semua waktu
          </p>

          {isLoading ? (
            <ChartSkeleton height="160px" />
          ) : (
            <>
              {/* Donut — fixed height, no legend competing for space */}
              <div className="relative" style={{ height: "160px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      innerRadius="48%"
                      outerRadius="70%"
                      paddingAngle={4}
                      stroke="none"
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value, name) => [`${value} kejadian`, name]} />
                  </PieChart>
                </ResponsiveContainer>

                {/* Center label — no legend fighting for space, so centering is reliable */}
                <div
                  className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
                >
                  <span className="text-xl font-bold text-gray-800">{totalViolations}</span>
                  <span className="text-[9px] font-bold text-gray-400 uppercase tracking-widest">Total</span>
                </div>
              </div>

              {/* Custom legend OUTSIDE ResponsiveContainer — clean, no overlap */}
              <div className="mt-3 flex flex-col gap-1.5">
                {pieData.map((d) => {
                  const pct = totalPie > 0 ? Math.round((d.value / totalPie) * 100) : 0;
                  return (
                    <div key={d.name} className="flex items-center justify-between text-[11px] text-gray-500">
                      <span className="flex items-center gap-1.5">
                        <span
                          className="inline-block w-2 h-2 rounded-sm flex-shrink-0"
                          style={{ background: d.color }}
                        />
                        {d.name}
                      </span>
                      <span className="font-medium text-gray-700">{d.value} <span className="text-gray-400">({pct}%)</span></span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Row 2: Hourly bar chart */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-100">
        <h4 className="text-sm font-bold text-gray-800 mb-1">Pelanggaran per Jam</h4>
        <p className="text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-3">
          Semua waktu
        </p>
        <div className="w-full" style={{ height: "clamp(120px, 20vh, 220px)" }}>
          {isLoading ? (
            <ChartSkeleton height="100%" />
          ) : hourlyData.length === 0 ? (
            <div className="h-full flex items-center justify-center text-slate-400 text-xs">
              Belum ada data
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={hourlyData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
                <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 9 }} />
                <Tooltip formatter={(value) => [`${value} kejadian`, "Pelanggaran"]} />
                <Bar dataKey="value" fill="#FF5722" radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

    </div>
  );
};

export default ChartsSection;