import React, { useState } from "react";
import SignInModal from "../components/auth/SignInModal";
import LoginModal from "../components/auth/LoginModal";

export default function AuthLanding({ onSuccess }) { // ← tambah { onSuccess }
  const [activeForm, setActiveForm] = useState(null);

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center px-4 py-10"
      style={{ backgroundColor: "#E5DCC5" }}
    >
      {/* Brand Header */}
      <div className="text-center mb-10">
        <h1 className="text-3xl font-extrabold tracking-tight text-[#1a1a1a]">
          VisionGuard
        </h1>
        <p className="text-sm text-gray-600 mt-1 font-medium">K3 Monitoring</p>
        <p className="text-xs text-gray-400">PT. Epson Indonesia</p>
      </div>

      {/* Cards */}
      <div className="flex flex-col sm:flex-row gap-5 w-full max-w-xl">
        {/* Sign In Card */}
        <div
          className="flex-1 bg-[#F5EFE0] rounded-2xl border border-black/10 p-7 flex flex-col items-center gap-4 cursor-pointer hover:-translate-y-1 transition-transform duration-200"
          onClick={() => setActiveForm("signin")}
        >
          <div className="w-14 h-14 rounded-full bg-green-100 flex items-center justify-center">
            <svg className="w-7 h-7 text-green-700" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M18 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 1 1-6.75 0 3.375 3.375 0 0 1 6.75 0ZM3 19.235v-.11a6.375 6.375 0 0 1 12.75 0v.109A12.318 12.318 0 0 1 9.374 21c-2.331 0-4.512-.645-6.374-1.766Z" />
            </svg>
          </div>
          <div className="text-center">
            <p className="text-base font-bold text-[#1a1a1a]">Sign In</p>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              Daftar akun baru untuk mengakses<br />sistem monitoring K3
            </p>
          </div>
          <button
            className="mt-1 w-full py-2.5 rounded-lg bg-green-700 hover:bg-green-800 text-white text-sm font-semibold transition-colors duration-150"
            onClick={(e) => { e.stopPropagation(); setActiveForm("signin"); }}
          >
            Daftar Sekarang
          </button>
        </div>

        {/* Divider */}
        <div className="flex sm:flex-col items-center justify-center gap-2 py-2">
          <div className="flex-1 h-px sm:h-auto sm:w-px sm:flex-1 bg-black/10" />
          <span className="text-xs text-gray-400 font-medium">atau</span>
          <div className="flex-1 h-px sm:h-auto sm:w-px sm:flex-1 bg-black/10" />
        </div>

        {/* Login Card */}
        <div
          className="flex-1 bg-[#F5EFE0] rounded-2xl border border-black/10 p-7 flex flex-col items-center gap-4 cursor-pointer hover:-translate-y-1 transition-transform duration-200"
          onClick={() => setActiveForm("login")}
        >
          <div className="w-14 h-14 rounded-full bg-orange-100 flex items-center justify-center">
            <svg className="w-7 h-7 text-orange-600" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
            </svg>
          </div>
          <div className="text-center">
            <p className="text-base font-bold text-[#1a1a1a]">Login</p>
            <p className="text-xs text-gray-500 mt-1 leading-relaxed">
              Masuk ke akun yang sudah ada<br />untuk melanjutkan sesi
            </p>
          </div>
          <button
            className="mt-1 w-full py-2.5 rounded-lg bg-[#D85A30] hover:bg-[#bf4f28] text-white text-sm font-semibold transition-colors duration-150"
            onClick={(e) => { e.stopPropagation(); setActiveForm("login"); }}
          >
            Masuk
          </button>
        </div>
      </div>

      {/* Footer */}
      <p className="mt-10 text-xs text-gray-400 text-center">
        07 April 2026 &nbsp;·&nbsp; © PT. Epson Indonesia. All Rights Reserved.
      </p>

      {/* Modals */}
      {activeForm === "signin" && (
        <SignInModal onClose={() => setActiveForm(null)} onSuccess={onSuccess} />
      )}
      {activeForm === "login" && (
        <LoginModal onClose={() => setActiveForm(null)} onSuccess={onSuccess} />
      )}
    </div>
  );
}