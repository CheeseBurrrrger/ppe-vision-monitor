export default function Header() {
  return (
    <div className="bg-[#f1eada] rounded-2xl px-8 py-5 flex justify-between items-center 
                    min-w-0 flex-shrink-0 shadow-sm border-l-[10px] border-black mb-6">
      
      {/* Bagian Kiri: Judul dengan font besar dan tebal */}
      <h2 className="font-extrabold text-4xl text-[#373d3f] whitespace-nowrap tracking-tight">
        Live Update
      </h2>

      {/* Bagian Kanan: Informasi Status dengan jarak antar item yang lebar */}
      <div className="flex gap-20 text-lg font-bold text-[#373d3f] min-w-0">
        <span className="whitespace-nowrap">3 Pelanggaran hari ini</span>
        <span className="whitespace-nowrap">07 April 2026</span>
        <span className="whitespace-nowrap italic">Shift 1 07:00 - 15:00</span>
      </div>
    </div>
  );
}