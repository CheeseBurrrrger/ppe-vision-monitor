import { useEffect, useRef, useState } from "react";

export default function DashboardCamFeed({ label, deviceId }) {
  const videoRef         = useRef(null);
  const captureCanvasRef = useRef(null);
  const overlayCanvasRef = useRef(null);
  const wsRef            = useRef(null);
  const waitingRef       = useRef(false);   // prevents frame queue buildup
  const intervalRef      = useRef(null);
  const [timestamp, setTimestamp]   = useState('');
  const [violations, setViolations] = useState([]);

  // Start camera
  useEffect(() => {
    navigator.mediaDevices.getUserMedia({
      video: deviceId ? { deviceId: { exact: deviceId } } : true
    })
      .then(stream => {
        if (videoRef.current) videoRef.current.srcObject = stream;
      })
      .catch(err => console.error("Cam error:", err));

    return () => {
      if (videoRef.current?.srcObject)
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8765");
    wsRef.current = ws;

    ws.onopen = () => {
      console.log(`[WS] Connected — ${label}`);

      intervalRef.current = setInterval(() => {
        const video  = videoRef.current;
        const canvas = captureCanvasRef.current;

        // Skip if server hasn't responded to last frame yet
        if (waitingRef.current) return;
        if (!video || !canvas || video.readyState < 2) return;
        if (ws.readyState !== WebSocket.OPEN) return;

        canvas.width  = 640;
        canvas.height = 480;
        const ctx    = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, 640, 480);
        const base64 = canvas.toDataURL("image/jpeg", 0.6).split(",")[1];

        waitingRef.current = true;   // block next send until response arrives
        ws.send(JSON.stringify({ camera_id: label, frame: base64 }));
      }, 100);  // poll frequently, but waitingRef gates the actual sends
    };

    ws.onmessage = (e) => {
      waitingRef.current = false;   // unblock next frame send

      const data = JSON.parse(e.data);
      drawBoxes(data.detections || []);

      if (data.violations?.length > 0) {
        setViolations(data.violations);
        setTimeout(() => setViolations([]), 5000);
      }
    };

    ws.onerror = (e) => console.error("[WS] Error:", e);
    ws.onclose = () => {
      clearInterval(intervalRef.current);
      waitingRef.current = false;
    };

    return () => {
      clearInterval(intervalRef.current);
      ws.close();
    };
  }, []);

  const drawBoxes = (detections) => {
    const video  = videoRef.current;
    const canvas = overlayCanvasRef.current;
    if (!canvas || !video) return;

    canvas.width  = video.clientWidth;
    canvas.height = video.clientHeight;
    const ctx    = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width  / 640;
    const scaleY = canvas.height / 480;

    detections.forEach(det => {
      const [x1, y1, x2, y2] = det.bbox;

      // Determine color by class
      let color;
      if (det.class === "Person") {
        color = "#2196F3";   // blue
      } else {
        color = "#00CC00";   // green for all PPE (no negative classes anymore)
      }

      ctx.strokeStyle = color;
      ctx.lineWidth   = 2;
      ctx.strokeRect(
        x1 * scaleX,
        y1 * scaleY,
        (x2 - x1) * scaleX,
        (y2 - y1) * scaleY
      );

      const labelText = `${det.class} ${det.confidence}`;
      ctx.fillStyle = color;
      ctx.fillRect(x1 * scaleX, y1 * scaleY - 20, labelText.length * 7 + 8, 20);
      ctx.fillStyle = "#ffffff";
      ctx.font      = "12px monospace";
      ctx.fillText(labelText, x1 * scaleX + 4, y1 * scaleY - 5);
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
        <canvas ref={captureCanvasRef} className="hidden" />
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