import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

const API_BASE = "http://localhost:8000";

export default function LoginModal({ onClose, onSuccess }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const overlayRef = useRef(null);

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  const handleOverlayClick = (e) => {
    if (e.target === overlayRef.current) onClose();
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await axios.post(`${API_BASE}/auth/login`, {
        username,
        password,
      });
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("username", data.username);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.detail || "Login gagal");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm px-4"
    >
      {/* Modal — stopPropagation agar klik di dalam tidak nutup overlay */}
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-[#F5EFE0] rounded-2xl overflow-hidden shadow-xl border border-black/10"
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-black/10">
          <p className="text-sm font-bold text-[#1a1a1a]">VisionGuard</p>
          <p className="text-xs text-gray-500">K3 Monitoring</p>
          <p className="text-xs text-gray-400">PT. Epson Indonesia</p>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="px-6 py-6 space-y-4">
          <h2 className="text-3xl font-light text-[#1a1a1a] tracking-tight">Login</h2>

          {error && (
            <div className="px-3 py-2 rounded-md bg-red-50 border border-red-200 text-xs text-red-600">
              {error}
            </div>
          )}

          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-600">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="w-full px-3 py-2 rounded-md border-2 border-[#D85A30] bg-white text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#D85A30]/20 transition"
            />
          </div>

          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-600">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 pr-10 rounded-md border-2 border-[#D85A30] bg-white text-sm text-[#1a1a1a] outline-none focus:ring-2 focus:ring-[#D85A30]/20 transition"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showPassword ? (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.98 8.223A10.477 10.477 0 0 0 1.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.451 10.451 0 0 1 12 4.5c4.756 0 8.773 3.162 10.065 7.498a10.522 10.522 0 0 1-4.293 5.774M6.228 6.228 3 3m3.228 3.228 3.65 3.65m7.894 7.894L21 21m-3.228-3.228-3.65-3.65m0 0a3 3 0 1 0-4.243-4.243m4.242 4.242L9.88 9.88" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-[#D85A30] hover:bg-[#bf4f28] active:scale-[0.98] disabled:opacity-60 text-white text-sm font-semibold transition-all duration-150 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                </svg>
                Memproses...
              </>
            ) : "Login"}
          </button>

          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
              </svg>
              Kembali
            </button>
            <button type="button" className="text-xs text-gray-500 hover:text-gray-700 transition-colors">
              Forgot Password?
            </button>
          </div>
        </form>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-black/10">
          <p className="text-[11px] text-gray-400">©team sembilan</p>
        </div>
      </div>
    </div>
  );
}
