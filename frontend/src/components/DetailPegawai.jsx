import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, PieChart, Pie,
} from "recharts";

// ── Per-employee mock data generator ─────────────────────────────────────────
function generateData(nama) {
  const seed = nama.charCodeAt(0);
  const rand = (base, range) => base + ((seed * 7) % range);

  const stats = [
    { label: "Total Pelanggaran",   value: rand(10, 12), delta: "+8%",  up: true  },
    { label: "Tanpa Helm Safety",   value: rand(2, 6),   delta: "+20%", up: true  },
    { label: "Tanpa Sarung Tangan", value: rand(1, 5),   delta: "-10%", up: false },
    { label: "Tanpa Vest",          value: rand(2, 6),   delta: "-5%",  up: false },
    { label: "Tanpa Sepatu Safety", value: rand(1, 4),   delta: "+2%",  up: true  },
  ];

  const weekly = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"].map((day) => ({
    day,
    vest:   rand(2, 8),
    helmet: rand(3, 10),
    shoes:  rand(1, 6),
    gloves: rand(2, 7),
  }));

  const helmVal   = rand(2, 6);
  const glovesVal = rand(1, 5);
  const shoesVal  = rand(2, 5);
  const vestVal   = rand(2, 6);
  const donut = [
    { name: "Vest",   value: vestVal,   color: "#4ade80" },
    { name: "Helmet", value: helmVal,   color: "#facc15" },
    { name: "Shoes",  value: shoesVal,  color: "#92400e" },
    { name: "Gloves", value: glovesVal, color: "#3b82f6" },
  ];

  const hourly = Array.from({ length: 9 }, (_, i) => ({
    time: `${(8 + i * 2).toString().padStart(2, "0")}:00`,
    count: rand(0, 7),
  }));

  return { stats, weekly, donut, hourly };
}

// ── Donut center label ────────────────────────────────────────────────────────
function DonutCenter({ cx, cy, total }) {
  return (
    <text x={cx} y={cy} textAnchor="middle" dominantBaseline="central">
      <tspan x={cx} dy="-6" fontSize="20" fontWeight="700" fill="#1c1917">
        {total}
      </tspan>
      <tspan x={cx} dy="18" fontSize="9" fill="#78716c">
        TOTAL
      </tspan>
    </text>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function DetailPegawai({ pegawai, onBack }) {
  const { stats, weekly, donut, hourly } = generateData(pegawai.nama);
  const total = donut.reduce((s, d) => s + d.value, 0);

  return (
    <div className="space-y-4">
      {/* Back + title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-stone-500 hover:text-stone-800 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
          Kembali
        </button>
        <span className="text-stone-300">/</span>
        <span className="text-sm text-stone-500">Rekap Pegawai</span>
        <span className="text-stone-300">/</span>
        <span className="text-sm font-semibold text-stone-800">{pegawai.nama}</span>
      </div>

      {/* Employee info card */}
      <div className="bg-white rounded-xl border border-[#d4cfc4] px-6 py-4 flex items-center gap-4">
        <div className="w-12 h-12 rounded-full bg-stone-600 flex items-center justify-center text-white font-bold text-sm shrink-0">
          {pegawai.nama.split(" ").map((w) => w[0]).slice(0, 2).join("")}
        </div>
        <div>
          <p className="text-base font-bold text-stone-800">{pegawai.nama}</p>
          <p className="text-xs text-stone-400">ID Pegawai: EPS-{String(pegawai.id).padStart(4, "0")}</p>
        </div>
        <div className="ml-auto text-right">
          <p className="text-2xl font-black text-stone-800">{pegawai.pelanggaran}</p>
          <p className="text-xs text-stone-400">Total Pelanggaran</p>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-5 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-[#d4cfc4] px-4 py-4">
            <p className="text-[10px] font-semibold text-stone-400 uppercase tracking-wide leading-tight mb-2">
              {s.label}
            </p>
            <p className="text-3xl font-black text-stone-800">{s.value}</p>
            <p className={`text-xs font-semibold mt-1 ${s.up ? "text-red-500" : "text-green-600"}`}>
              {s.delta} vs minggu lalu
            </p>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-3 gap-4">
        {/* Weekly bar chart */}
        <div className="col-span-2 bg-white rounded-xl border border-[#d4cfc4] p-4">
          <p className="text-sm font-semibold text-stone-700 mb-0.5">Trend Jenis Pelanggaran</p>
          <p className="text-xs text-stone-400 mb-3">29 Maret 2026 – 4 April 2026</p>
          <div className="flex gap-4 mb-2">
            {[
              { label: "Vest",   color: "#4ade80" },
              { label: "Helmet", color: "#facc15" },
              { label: "Shoes",  color: "#92400e" },
              { label: "Gloves", color: "#3b82f6" },
            ].map((l) => (
              <div key={l.label} className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: l.color }} />
                <span className="text-xs text-stone-500">{l.label}</span>
              </div>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={weekly} barCategoryGap="20%" barGap={2}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" vertical={false} />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ background: "#fff", border: "0.5px solid #d4cfc4", borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="vest"   fill="#4ade80" radius={[3,3,0,0]} maxBarSize={12} />
              <Bar dataKey="helmet" fill="#facc15" radius={[3,3,0,0]} maxBarSize={12} />
              <Bar dataKey="shoes"  fill="#92400e" radius={[3,3,0,0]} maxBarSize={12} />
              <Bar dataKey="gloves" fill="#3b82f6" radius={[3,3,0,0]} maxBarSize={12} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Donut */}
        <div className="bg-white rounded-xl border border-[#d4cfc4] p-4 flex flex-col items-center justify-center">
          <PieChart width={170} height={170}>
            <Pie
              data={donut} cx={85} cy={85}
              innerRadius={50} outerRadius={80}
              paddingAngle={3} dataKey="value"
              startAngle={90} endAngle={-270}
            >
              {donut.map((d) => (
                <Cell key={d.name} fill={d.color} stroke="none" />
              ))}
            </Pie>
            <DonutCenter cx={85} cy={85} total={total} />
          </PieChart>
          <div className="mt-2 space-y-1 w-full px-2">
            {donut.map((d) => (
              <div key={d.name} className="flex items-center gap-2 text-xs text-stone-600">
                <span className="w-2.5 h-2.5 rounded-full shrink-0 inline-block" style={{ background: d.color }} />
                <span className="flex-1">{d.name}</span>
                <span className="font-semibold text-stone-800">{d.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Hourly bar chart */}
      <div className="bg-white rounded-xl border border-[#d4cfc4] p-4">
        <p className="text-sm font-semibold text-stone-700 mb-0.5">Pelanggaran Hari Ini</p>
        <p className="text-xs text-stone-400 mb-3">4 April 2026</p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={hourly} barCategoryGap="25%">
            <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#78716c" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#78716c" }} axisLine={false} tickLine={false} />
            <Tooltip contentStyle={{ background: "#fff", border: "0.5px solid #d4cfc4", borderRadius: 8, fontSize: 12 }} />
            <Bar dataKey="count" radius={[4,4,0,0]} maxBarSize={28}>
              {hourly.map((_, i) => <Cell key={i} fill="#f97316" />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}