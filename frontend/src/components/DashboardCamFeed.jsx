import { useEffect, useRef, useState } from "react";

export default function DashboardCamFeed({ label, deviceId }) {
  const videoRef = useRef(null);
  const captureCanvasRef = useRef(null);  // hidden, for sending frames
  const overlayCanvasRef = useRef(null);  // visible, for drawing boxes
  const wsRef = useRef(null);
  const intervalRef = useRef(null);
  const [timestamp, setTimestamp] = useState('');
  const [violations, setViolations] = useState([]);

  // Start camera
  useEffect(() => {
    if (!navigator.mediaDevices?.getUserMedia) {
      console.warn("Camera unavailable (HTTPS required on non-localhost)");
      return;
    }

    const constraints = deviceId
      ? { video: { deviceId: { exact: deviceId } } }
      : { video: true };

    navigator.mediaDevices.getUserMedia(constraints)
      .then(stream => {
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(() => {
        navigator.mediaDevices.getUserMedia({ video: true })
          .then(stream => {
            if (videoRef.current) videoRef.current.srcObject = stream;
          })
          .catch(err => console.error("Cam error:", err));
      });

    return () => {
      if (videoRef.current?.srcObject)
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = import.meta.env.VITE_WS_URL || `${wsProto}://${window.location.hostname}:8765`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] Connected");
      intervalRef.current = setInterval(() => {
        const video = videoRef.current;
        const canvas = captureCanvasRef.current;
        if (!video || !canvas || video.readyState < 2 || ws.readyState !== WebSocket.OPEN) return;

        canvas.width = 640;
        canvas.height = 480;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, 640, 480);
        const base64 = canvas.toDataURL("image/jpeg", 0.6).split(",")[1];

        ws.send(JSON.stringify({ camera_id: label, frame: base64 }));
      }, 500);
    };

    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      drawBoxes(data.detections || []);

      if (data.violations?.length > 0) {
        setViolations(data.violations);
        setTimeout(() => setViolations([]), 5000);
      }
    };

    ws.onerror = (e) => console.error("[WS] Error:", e);
    ws.onclose = () => clearInterval(intervalRef.current);

    return () => {
      clearInterval(intervalRef.current);
      ws.close();
    };
  }, []);

  const drawBoxes = (detections) => {
    const video = videoRef.current;
    const canvas = overlayCanvasRef.current;
    if (!canvas || !video) return;

    canvas.width = video.clientWidth;
    canvas.height = video.clientHeight;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width / 640;
    const scaleY = canvas.height / 480;

    detections.forEach(det => {
      const [x1, y1, x2, y2] = det.bbox;
      const isViolation = det.class.startsWith("no_");
      let color = isViolation ? "#FF0000" : "#00CC00";
      
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(x1 * scaleX, y1 * scaleY, (x2 - x1) * scaleX, (y2 - y1) * scaleY);

      const labelText = `${det.class} ${det.confidence}`;
      ctx.fillStyle = color;
      ctx.fillRect(x1 * scaleX, y1 * scaleY - 20, labelText.length * 7 + 8, 20);
      ctx.fillStyle = "#ffffff";
      ctx.font = "12px monospace";
      ctx.fillText(labelText, x1 * scaleX + 4, y1 * scaleY - 5);
      // let color;
      if (det.class === "Person") {
        color = "#2196F3";        
      } else if (det.class.startsWith("no_")) {
        color = "#FF0000";        // red for violation
      } else {
        color = "#00CC00";        // green for compliant PPE
      }
    });
  };

  // Clock
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
          autoPlay playsInline muted
          className="w-full h-full object-cover"
        />

        {/* Hidden capture canvas */}
        <canvas ref={captureCanvasRef} className="hidden" />

        {/* Visible overlay canvas for boxes */}
        <canvas
          ref={overlayCanvasRef}
          className="absolute inset-0 w-full h-full"
          style={{ pointerEvents: 'none' }}
        />

        <div className="absolute top-2 left-2 flex flex-col gap-1 z-10">
          <div className="bg-black/50 text-white text-[10px] px-2 py-0.5 rounded font-mono">
            {timestamp}
          </div>
          <div className="bg-red-600 text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase w-fit animate-pulse">
            Live
          </div>
        </div>

        {violations.length > 0 && (
          <div className="absolute bottom-2 left-2 right-2 bg-red-600/90 text-white text-xs px-2 py-1 rounded font-bold z-10">
            ⚠ {violations.map(v => v.type.replace(/_/g, ' ').toUpperCase()).join(', ')}
          </div>
        )}
      </div>
      <div className="p-3">
        <p className="text-sm font-semibold text-gray-800">{label}</p>
      </div>
    </div>
  );
}