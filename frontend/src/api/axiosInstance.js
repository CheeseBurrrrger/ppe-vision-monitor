import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000', // Sesuaikan dengan URL FastAPI kamu
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;