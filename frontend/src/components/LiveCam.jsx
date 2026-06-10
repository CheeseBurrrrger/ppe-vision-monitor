import { Camera, X, RefreshCw } from 'lucide-react';
import { useMemo, useState } from 'react';
import DetectionCameraFeed from './DetectionCameraFeed';
import { useCameraDevices } from '../hooks/useCameraDevices';

const FLOOR_CAMERAS = [
  { id: 'spraying-room', name: 'Spraying Room', top: '40%', left: '35%' },
  { id: 'pipe-store', name: 'Pipe Store', top: '70%', left: '32%' },
  { id: 'console-area', name: 'Console Area', top: '80%', left: '65%' },
];

export default function LiveCam() {
  const [selectedCamId, setSelectedCamId] = useState(null);
  const [streamVersion, setStreamVersion] = useState(0);
  const { cameraSlots, status, error, refresh } = useCameraDevices(3);
  const canRequestDefaultCamera = Boolean(navigator.mediaDevices?.getUserMedia);

  const cameras = useMemo(
    () =>
      FLOOR_CAMERAS.map((camera, index) => ({
        ...camera,
        device: cameraSlots[index],
        allowDefaultCamera: index === 0 && canRequestDefaultCamera && !cameraSlots[index]?.deviceId,
        isOnline: Boolean(cameraSlots[index]?.deviceId) || (
          index === 0 &&
          canRequestDefaultCamera &&
          status !== 'error'
        ),
      })),
    [cameraSlots, canRequestDefaultCamera, status]
  );

  const selectedCam = cameras.find((camera) => camera.id === selectedCamId);
  const onlineCount = cameras.filter((camera) => camera.isOnline).length;

  const handleRefresh = () => {
    refresh();
    setStreamVersion((value) => value + 1);
  };

  return (
    <div className="flex flex-col h-full space-y-4">
      <div className="bg-white p-6 rounded-xl shadow-sm border border-gray-200 flex-1 flex flex-col min-h-0 overflow-hidden">
        <div className="mb-4 flex shrink-0 items-center justify-between gap-3">
          <p className="text-[10px] text-gray-400 font-bold uppercase tracking-widest italic">
            Click CCTV icon to stream camera
          </p>
          <div className="text-right">
            <p className="text-[10px] font-bold uppercase tracking-widest text-gray-500">
              {status === 'loading' ? 'Scanning camera' : `${onlineCount}/3 camera online`}
            </p>
            {error && <p className="text-[10px] font-semibold text-red-500">{error}</p>}
          </div>
        </div>

        <div className="flex-1 flex items-center justify-center overflow-hidden">
          <div className="relative inline-block max-h-full max-w-full">
            <img 
              src="/assets/denah.jpg" 
              alt="Factory Floor Plan" 
              className="max-h-[70vh] w-auto h-auto object-contain rounded-lg shadow-sm border border-gray-100"
            />

            {cameras.map((cam) => (
              <button
                key={cam.id}
                type="button"
              disabled={!cam.isOnline}
                onClick={() => setSelectedCamId(cam.id)}
                aria-label={`${cam.name} ${cam.isOnline ? 'online' : 'offline'}`}
                className={`absolute group transform -translate-x-1/2 -translate-y-1/2 transition-all active:scale-95 ${
                  cam.isOnline ? 'hover:scale-125' : 'cursor-not-allowed opacity-60'
                }`}
                style={{ top: cam.top, left: cam.left }}
              >
                <div className="relative flex items-center justify-center">
                  {cam.isOnline && (
                    <div className="absolute w-16 h-16 bg-yellow-200/40 rounded-full blur-xl animate-pulse" />
                  )}
                  <div className={`${cam.isOnline ? 'bg-[#B98E3B]' : 'bg-gray-400'} p-2 rounded-full border-2 border-white shadow-lg text-white z-10`}>
                    <Camera size={16} />
                  </div>
                  <div className="absolute bottom-full mb-2 hidden group-hover:block bg-black text-white text-[10px] px-2 py-1 rounded whitespace-nowrap z-20 shadow-xl">
                    <p className="font-bold">{cam.name}</p>
                    <p className="text-gray-300">
                      {cam.device?.label || (cam.allowDefaultCamera ? 'Default browser camera' : 'No camera device')}
                    </p>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>

      {selectedCam && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-4xl overflow-hidden animate-in zoom-in duration-300">
            <div className="flex justify-between items-center p-6 border-b">
              <div>
                <h3 className="text-xl font-bold text-gray-800">Stream Camera</h3>
                <p className="text-xs text-gray-500 font-bold uppercase">{selectedCam.name}</p>
                <p className="mt-1 text-[10px] text-gray-400 font-semibold uppercase tracking-wide">
                  {selectedCam.device?.label || (selectedCam.allowDefaultCamera ? 'Default browser camera' : 'No camera device')}
                </p>
              </div>
              <div className="flex gap-4">
                <button
                  type="button"
                  onClick={handleRefresh}
                  className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-600"
                  aria-label="Refresh camera stream"
                >
                  <RefreshCw size={24} />
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedCamId(null)}
                  className="p-2 hover:bg-red-50 text-gray-600 hover:text-red-500 rounded-full transition-colors"
                  aria-label="Close camera stream"
                >
                  <X size={24} />
                </button>
              </div>
            </div>
            <DetectionCameraFeed
              key={`${selectedCam.id}-${selectedCam.device?.deviceId || 'offline'}-${streamVersion}`}
              label={selectedCam.name}
              cameraId={`LIVE_${selectedCam.id}`}
              deviceId={selectedCam.device?.deviceId || ''}
              allowDefaultCamera={selectedCam.allowDefaultCamera}
              disabled={!selectedCam.isOnline}
              disabledMessage="Camera slot ini belum memiliki device."
              onStreamReady={refresh}
            />
          </div>
        </div>
      )}
    </div>
  );
}
