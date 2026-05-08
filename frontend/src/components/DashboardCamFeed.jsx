import { useEffect, useRef, useState } from "react";

export default function DashboardCamFeed({ label, deviceId }) {
  const videoRef = useRef(null);
  const [timestamp, setTimestamp] = useState('');
  

  useEffect(() => {
      navigator.mediaDevices.getUserMedia({
        video: deviceId ? { deviceId: { exact: deviceId } } : true
      })
            .then(stream => {
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(err => console.error("Cam error:", err));

    return () => {
      if (videoRef.current?.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
    };
  }, []);
  useEffect(() => {
    const tick = () => setTimestamp(new Date().toLocaleString('id-ID', {
        day: '2-digit', month: '2-digit', year: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false
    }).replace(/\//g, '-'));
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
    }, []);

  return (
    <div className="bg-white rounded-xl overflow-hidden shadow-sm border border-gray-200">
      <div className="relative bg-black aspect-video">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          <div className="bg-black/50 text-white text-[10px] px-2 py-0.5 rounded font-mono">
          {timestamp}
            {/* {new Date().toLocaleString('id-ID', {
              day: '2-digit', month: '2-digit', year: 'numeric',
              hour: '2-digit', minute: '2-digit', second: '2-digit',
              hour12: false
            }).replace(/\//g, '-')} */}
          </div>
          
          <div className="bg-red-600 text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase w-fit animate-pulse">
            Live
          </div>
        </div>
      </div>
      <div className="p-3">
        <p className="text-sm font-semibold text-gray-800">{label}</p>
      </div>
    </div>
  );
}