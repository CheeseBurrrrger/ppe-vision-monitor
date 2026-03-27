import { useQuery } from '@tanstack/react-query';
import { getViolations } from '../api/violationApi';

function ViolationLog() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['violations'],
    queryFn: getViolations,
  });

  if (isLoading) return <div>Memuat data pelanggaran...</div>;
  if (isError) return <div>Terjadi kesalahan koneksi ke server.</div>;

  return (
    <div>
      {/* Gunakan data untuk Slicing Tabel Log Pelanggaran kamu */}
      {data.map((item) => (
        <div key={item.id}>{item.violation_type} - {item.timestamp}</div>
      ))}
    </div>
  );
}