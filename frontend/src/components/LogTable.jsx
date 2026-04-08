export default function LogTable() {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm">
      <h2 className="font-semibold mb-4 text-lg">Log Pelanggaran</h2>

      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b text-left text-gray-600">
            <th className="py-2">#</th>
            <th>Timestamp</th>
            <th>Jenis</th>
            <th>Confidence</th>
            <th>Shift</th>
            <th>Bukti</th>
            <th>Ruangan</th>
          </tr>
        </thead>

        <tbody>
          <tr className="border-b hover:bg-gray-50">
            <td className="py-2">001</td>
            <td>2026-04-26 08:12:43</td>
            <td>No Helmet</td>
            <td>0.91</td>
            <td>Shift 1</td>
            <td className="text-blue-500">photo_1.jpg</td>
            <td>Spraying Room</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}