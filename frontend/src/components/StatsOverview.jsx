import { useQuery } from "@tanstack/react-query";
import { fetchStats } from "../api/violationApi";

const StatCard = ({ title, value, isLoading }) => (
  <div className="bg-white px-2 py-3 rounded-xl border border-gray-200 shadow-sm text-center min-w-0">
    <h3 className="text-[9px] font-bold uppercase text-gray-600 mb-1 leading-tight
                   min-h-[2rem] flex items-center justify-center">
      {title}
    </h3>
    {isLoading ? (
      <div className="h-8 w-12 bg-gray-200 animate-pulse rounded mx-auto mb-1" />
    ) : (
      <p className="text-2xl font-bold mb-1 truncate">{value ?? 0}</p>
    )}
  </div>
);

export function StatsOverview() {
  const { data, isLoading } = useQuery({
    queryKey: ["stats"],
    queryFn: fetchStats,
    refetchInterval: 5000,
  });
 
  const byType = data?.by_type ?? {};
 
  return (
    <div className="grid gap-3" style={{
      gridTemplateColumns: "repeat(6, minmax(0, 1fr))",
    }}>
      <StatCard
        title="Total Pelanggaran"
        value={data?.total_violations}
        isLoading={isLoading}
      />
      <StatCard
        title="Tanpa Helm Safety"
        value={byType["no_helmet"]}
        isLoading={isLoading}
      />
      <StatCard
        title="Tanpa Sarung Tangan"
        value={byType["no_gloves"]}
        isLoading={isLoading}
      />
      <StatCard
        title="Tanpa Rompi"
        value={byType["no_vest"]}
        isLoading={isLoading}
      />
      <StatCard
        title="Tanpa Sepatu Safety"
        value={byType["no_boots"]}
        isLoading={isLoading}
      />
      <StatCard
        title="Tanpa Goggle"
        value={byType["no_goggles"]}
        isLoading={isLoading}
      />
    </div>
  );
}