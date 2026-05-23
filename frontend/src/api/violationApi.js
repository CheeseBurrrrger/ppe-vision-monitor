import api from './axiosInstance';

// // Tidak perlu mendefinisikan API_URL lagi di sini jika sudah ada di axiosInstance
// export const getViolations = async () => {
//   try {
//     const response = await api.get('/violations'); 
//     return response.data; 
//   } catch (error) {
//     console.error("Gagal mengambil data pelanggaran:", error);
//     throw error;
//   }
// };

const API_BASE = import.meta.env.VITE_API_BASE_URL;
console.log("API_BASE:", import.meta.env.VITE_API_BASE_URL);
console.log("All env:", import.meta.env);
export const fetchStats = async () => {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
};

export const fetchViolations = async ({ type, dateFrom, dateTo, limit, offset }) => {
  const params = new URLSearchParams();
  if (type && type !== "All") params.append("violation_type", type);
  if (dateFrom) params.append("date_from", dateFrom);
  if (dateTo) params.append("date_to", dateTo);
  if (limit) params.append("limit", limit);
  if (offset) params.append("offset", offset);
  const res = await fetch(`${API_BASE}/violations?${params.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch violations");
  return res.json();
};