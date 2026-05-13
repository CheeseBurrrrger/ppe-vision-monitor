import { useEffect, useRef, useState } from "react";

export default function DashboardCamFeed({ label, deviceId, cameraIndex = 0 }) {
  const videoRef = useRef(null);
  const [timestamp, setTimestamp] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let stream;
    let cancelled = false;

    async function start() {
      try {
        if (deviceId) {
          stream = await navigator.mediaDevices.getUserMedia({
            video: { deviceId: { exact: deviceId } },
          });
        } else {
          // Enumerate available cameras and pick by index (0 = first, 1 = second, etc.)
          const devices = await navigator.mediaDevices.enumerateDevices();
          const cams = devices.filter((d) => d.kind === "videoinput");
          if (cams.length === 0) {
            throw new Error("Tidak ada kamera terdeteksi");
          }
          const cam = cams[Math.min(cameraIndex, cams.length - 1)];
          stream = await navigator.mediaDevices.getUserMedia({
            video: cam.deviceId ? { deviceId: { exact: cam.deviceId } } : true,
          });
        }
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        if (videoRef.current) videoRef.current.srcObject = stream;
      } catch (err) {
        console.error(`[${label}] Cam error:`, err);
        setError(err.message || "Tidak dapat mengakses kamera");
      }
    }

    start();

    return () => {
      cancelled = true;
      if (videoRef.current?.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((t) => t.stop());
      }
      if (stream) stream.getTracks().forEach((t) => t.stop());
    };
  }, [deviceId, cameraIndex, label]);

  useEffect(() => {
    const tick = () =>
      setTimestamp(
        new Date()
          .toLocaleString("id-ID", {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false,
          })
          .replace(/\//g, "-")
      );
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
        {error && (
          <div className="absolute inset-0 flex items-center justify-center text-white text-xs text-center p-4 bg-black/60">
            {error}
          </div>
        )}
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          <div className="bg-black/50 text-white text-[10px] px-2 py-0.5 rounded font-mono">
            {timestamp}
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
