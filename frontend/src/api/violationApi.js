import api from './axiosInstance';

// Tidak perlu mendefinisikan API_URL lagi di sini jika sudah ada di axiosInstance
export const getViolations = async () => {
  try {
    const response = await api.get('/violations'); 
    return response.data; 
  } catch (error) {
    console.error("Gagal mengambil data pelanggaran:", error);
    throw error;
  }
};