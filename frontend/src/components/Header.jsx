import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/violationApi";

export default function Header() {
  const { data } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 5000,
  });

  const now = new Date();
  const hour = now.getHours();
  const shift = hour >= 6 && hour < 14 ? "Shift 1 07:00 - 15:00"
              : hour >= 14 && hour < 22 ? "Shift 2 15:00 - 23:00"
              : "Shift 3 23:00 - 07:00";

  const todayLabel = now.toLocaleDateString("id-ID", {
    day: "2-digit", month: "long", year: "numeric"
  });

  // Count today's violations from by_hour (hour matching today)
  const todayViolations = data?.total_violations ?? "—";

  return (
    <div className="bg-[#f1eada] rounded-2xl px-8 py-5 flex justify-between items-center 
                    min-w-0 flex-shrink-0 shadow-sm border-l-[10px] border-black mb-6">
      <h2 className="font-extrabold text-4xl text-[#373d3f] whitespace-nowrap tracking-tight">
        Live Update
      </h2>
      <div className="flex gap-20 text-lg font-bold text-[#373d3f] min-w-0">
        <span className="whitespace-nowrap">{todayViolations} Pelanggaran hari ini</span>
        <span className="whitespace-nowrap">{todayLabel}</span>
        <span className="whitespace-nowrap italic">{shift}</span>
      </div>
    </div>
  );
}