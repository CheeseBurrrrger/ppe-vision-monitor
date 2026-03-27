/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'k3-primary': '#1e293b', // Warna industrial untuk sidebar
        'k3-danger': '#ef4444',  // Merah untuk pelanggaran APD
        'k3-warning': '#f59e0b', // Kuning untuk disiplin kerja
      }
    },
  },
  plugins: [],
}