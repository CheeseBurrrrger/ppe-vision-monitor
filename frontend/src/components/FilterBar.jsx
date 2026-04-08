export default function FilterBar() {
  return (
    <div className="bg-white rounded-xl p-4 mb-6 shadow-sm">
      <div className="grid grid-cols-2 gap-4 mb-4">
        <select className="border p-2 rounded-lg w-full">
          <option>Semua Jenis Pelanggaran</option>
        </select>

        <select className="border p-2 rounded-lg w-full">
          <option>Semua Shift</option>
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <input type="date" className="border p-2 rounded-lg w-full" />
        <input type="date" className="border p-2 rounded-lg w-full" />
      </div>

      <div className="flex justify-end">
        <button className="border px-4 py-2 rounded-lg hover:bg-gray-100">
          Export CSV
        </button>
      </div>
    </div>
  );
}