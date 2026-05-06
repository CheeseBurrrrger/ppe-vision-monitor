/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}", // Pastikan baris ini ada agar Tailwind memindai file Anda
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}