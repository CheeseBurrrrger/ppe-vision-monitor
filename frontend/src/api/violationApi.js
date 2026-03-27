import api from './axiosInstance';

export const getViolations = async () => {
  try {
    // Menghubungi endpoint yang telah disiapkan di FastAPI
    const response = await api.get('/violations'); 
    return response.data; 
  } catch (error) {
    console.error("Gagal mengambil data pelanggaran:", error);
    throw error;
  }
};