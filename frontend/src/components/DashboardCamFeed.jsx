import { useEffect, useRef, useState } from "react";

const WS_URL = "ws://localhost:8765";
const FRAME_INTERVAL_MS = 1000; // 1 fps to keep CPU/network low

export default function DashboardCamFeed({ label, deviceId, cameraIndex = 0, cameraId }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const sendIntervalRef = useRef(null);
  const [timestamp, setTimestamp] = useState("");
  const [error, setError] = useState("");
  const [detections, setDetections] = useState([]);
  const [violationCount, setViolationCount] = useState(0);

  // Camera setup
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
          const devices = await navigator.mediaDevices.enumerateDevices();
          const cams = devices.filter((d) => d.kind === "videoinput");
          if (cams.length === 0) throw new Error("Tidak ada kamera terdeteksi");
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

  // WebSocket connection + frame sending loop
  useEffect(() => {
    const camId = cameraId || `CAM_${label.replace(/\s+/g, "_").toUpperCase()}`;
    let reconnectTimer = null;
    let closed = false;

    const connect = () => {
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onopen = () => {
          console.log(`[${label}] WS connected`);
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            setDetections(data.detections || []);
            if (data.violations && data.violations.length > 0) {
              setViolationCount((c) => c + data.violations.length);
            }
          } catch (e) {
            console.error("[WS] parse error", e);
          }
        };

        ws.onerror = (e) => console.warn(`[${label}] WS error`, e);
        ws.onclose = () => {
          if (closed) return;
          // try reconnect after 3s
          reconnectTimer = setTimeout(connect, 3000);
        };
      } catch (e) {
        console.error("WS connect error", e);
      }
    };

    connect();

    // Frame capture + send loop
    sendIntervalRef.current = setInterval(() => {
      const video = videoRef.current;
      const ws = wsRef.current;
      if (!video || !ws || ws.readyState !== WebSocket.OPEN) return;
      if (video.videoWidth === 0 || video.videoHeight === 0) return;

      let canvas = canvasRef.current;
      if (!canvas) {
        canvas = document.createElement("canvas");
        canvasRef.current = canvas;
      }
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.6);
      const base64 = dataUrl.split(",")[1];

      ws.send(JSON.stringify({ camera_id: camId, frame: base64 }));
    }, FRAME_INTERVAL_MS);

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (sendIntervalRef.current) clearInterval(sendIntervalRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [label, cameraId]);

  // Clock
  useEffect(() => {
    const tick = () =>
      setTimestamp(
        new Date()
          .toLocaleString("id-ID", {
            day: "2-digit", month: "2-digit", year: "numeric",
            hour: "2-digit", minute: "2-digit", second: "2-digit",
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
        <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
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
        {detections.length > 0 && (
          <div className="absolute top-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded font-mono">
            {detections.length} obj
          </div>
        )}
      </div>
      <div className="p-3 flex justify-between items-center">
        <p className="text-sm font-semibold text-gray-800">{label}</p>
        {violationCount > 0 && (
          <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full">
            {violationCount} pelanggaran
          </span>
        )}
      </div>
    </div>
  );
}
