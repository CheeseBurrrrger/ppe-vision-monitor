import React, { useState } from 'react';
import { Camera, X, RefreshCw } from 'lucide-react';

export default function LiveCam() {
  const [selectedCam, setSelectedCam] = useState(null);

  const cameras = [
    { id: 1, name: 'Spraying Room', top: '40%', left: '35%' },
    { id: 2, name: 'Pipe Store', top: '70%', left: '32%' },
    { id: 3, name: 'Console Area', top: '80%', left: '65%' },
  ];

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Header Statis - Tetap di atas */}
      <div className="bg-[#F2EADA] rounded-xl p-4 flex justify-between items-center border-l-8 border-black shadow-sm shrink-0">
      </div>

      {/* Container Denah - Mengisi sisa layar */}
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex-1 flex flex-col min-h-0 overflow-hidden">
        <p className="text-[10px] text-gray-400 font-bold uppercase mb-4 tracking-widest italic shrink-0">
          ● Click CCTV icon to stream camera
        </p>

        {/* Wrapper Responsif: Membatasi lebar agar tidak melebar (stretch) di layar lebar */}
        <div className="flex-1 flex items-center justify-center overflow-hidden">
          <div className="relative inline-block max-h-full max-w-full">
            {/* img dengan max-h-screen agar tidak overflow vertikal, object-contain menjaga proporsi */}
            <img 
              src="/assets/denah.jpg" 
              alt="Factory Floor Plan" 
              className="max-h-[70vh] w-auto h-auto object-contain rounded-lg shadow-sm border border-gray-100"
            />

            {/* Markers - Menggunakan koordinat persentase agar tetap presisi */}
            {cameras.map((cam) => (
              <button
                key={cam.id}
                onClick={() => setSelectedCam(cam)}
                className="absolute group transform -translate-x-1/2 -translate-y-1/2 transition-all hover:scale-125 active:scale-95"
                style={{ top: cam.top, left: cam.left }}
              >
                <div className="relative flex items-center justify-center">
                  <div className="absolute w-16 h-16 bg-yellow-200/40 rounded-full blur-xl animate-pulse" />
                  <div className="bg-[#B98E3B] p-2 rounded-full border-2 border-white shadow-lg text-white z-10">
                    <Camera size={16} />
                  </div>
                  {/* Tooltip Nama Ruangan */}
                  <div className="absolute bottom-full mb-2 hidden group-hover:block bg-black text-white text-[10px] px-2 py-1 rounded whitespace-nowrap z-20 shadow-xl">
                    {cam.name}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Modal Popup Stream (Sesuai Referensi Gambar) */}
      {selectedCam && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl overflow-hidden animate-in zoom-in duration-300">
            <div className="flex justify-between items-center p-6 border-b">
              <div>
                <h3 className="text-xl font-bold text-gray-800">Stream Camera</h3>
                <p className="text-xs text-gray-500 font-bold uppercase">{selectedCam.name}</p>
              </div>
              <div className="flex gap-4">
                <button className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-600">
                  <RefreshCw size={24} />
                </button>
                <button onClick={() => setSelectedCam(null)} className="p-2 hover:bg-red-50 text-gray-600 hover:text-red-500 rounded-full transition-colors">
                  <X size={24} />
                </button>
              </div>
            </div>
            <div className="bg-black aspect-video relative">
              <div className="absolute top-4 left-4 z-10 flex flex-col gap-1">
                <div className="bg-black/50 text-white text-[10px] px-2 py-1 rounded font-mono">07-04-2026 09:12:43</div>
                <div className="bg-red-600 text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase w-fit animate-pulse">Live</div>
              </div>
              <img src="https://images.unsplash.com/photo-1557597774-9d2739f85a76?w=1200" className="w-full h-full object-cover" alt="stream" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}