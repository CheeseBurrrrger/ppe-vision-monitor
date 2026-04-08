export default function Header() {
  return (
    <div className="bg-[#d6cbb7] rounded-xl px-6 py-4 flex justify-between items-center mb-6">
      <h2 className="font-semibold text-lg">Live Update</h2>

      <div className="flex gap-6 text-sm text-gray-700">
        <span>3 Pelanggaran hari ini</span>
        <span>07 April 2026</span>
        <span>Shift 1 07:00 - 15:00</span>
      </div>
    </div>
  );
}