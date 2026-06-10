import { useCallback, useEffect, useRef, useState } from "react";

const CAPTURE_WIDTH = 640;
const CAPTURE_HEIGHT = 480;
const FRAME_INTERVAL_MS = 500;

function formatTimestamp() {
  return new Date()
    .toLocaleString("id-ID", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    })
    .replace(/\//g, "-");
}

function getDetectionColor(className) {
  if (className === "Person") return "#2196F3";
  if (className.startsWith("no_")) return "#FF0000";
  return "#00CC00";
}

function formatConfidence(value) {
  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) return value;
  return numberValue.toFixed(2);
}

export default function DetectionCameraFeed({
  label,
  cameraId,
  deviceId,
  allowDefaultCamera = false,
  disabled = false,
  disabledMessage = "Camera tidak tersedia",
  onStreamReady,
  onStreamError,
}) {
  const videoRef = useRef(null);
  const captureCanvasRef = useRef(null);
  const overlayCanvasRef = useRef(null);
  const wsRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const violationTimeoutRef = useRef(null);

  const [timestamp, setTimestamp] = useState(formatTimestamp);
  const [streamReady, setStreamReady] = useState(false);
  const [wsReady, setWsReady] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [detectionError, setDetectionError] = useState("");
  const [violations, setViolations] = useState([]);

  const resolvedCameraId = cameraId || label || "CAM_UNKNOWN";

  const clearOverlay = useCallback(() => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }, []);

  const drawBoxes = useCallback((detections) => {
    const video = videoRef.current;
    const canvas = overlayCanvasRef.current;
    if (!canvas || !video) return;

    const width = video.clientWidth || CAPTURE_WIDTH;
    const height = video.clientHeight || CAPTURE_HEIGHT;
    canvas.width = width;
    canvas.height = height;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);

    const scaleX = width / CAPTURE_WIDTH;
    const scaleY = height / CAPTURE_HEIGHT;

    detections.forEach((det) => {
      const [x1, y1, x2, y2] = det.bbox;
      const color = getDetectionColor(det.class);
      const boxX = x1 * scaleX;
      const boxY = y1 * scaleY;
      const boxWidth = (x2 - x1) * scaleX;
      const boxHeight = (y2 - y1) * scaleY;
      const labelText = `${det.class} ${formatConfidence(det.confidence)}`;
      const labelWidth = Math.max(labelText.length * 7 + 8, 54);
      const labelY = Math.max(boxY - 20, 0);

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.strokeRect(boxX, boxY, boxWidth, boxHeight);

      ctx.fillStyle = color;
      ctx.fillRect(boxX, labelY, labelWidth, 20);
      ctx.fillStyle = "#ffffff";
      ctx.font = "12px monospace";
      ctx.fillText(labelText, boxX + 4, labelY + 14);
    });
  }, []);

  useEffect(() => {
    const interval = setInterval(() => setTimestamp(formatTimestamp()), 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let active = true;
    let stream = null;
    let videoElement = null;

    clearOverlay();

    const cleanup = () => {
      active = false;
      stream?.getTracks().forEach((track) => track.stop());
      if (videoElement) videoElement.srcObject = null;
      clearOverlay();
    };

    const updateCameraState = (nextState) => {
      queueMicrotask(() => {
        if (!active) return;
        if (nextState.streamReady !== undefined) setStreamReady(nextState.streamReady);
        if (nextState.cameraError !== undefined) setCameraError(nextState.cameraError);
        if (nextState.detectionError !== undefined) setDetectionError(nextState.detectionError);
        if (nextState.violations !== undefined) setViolations(nextState.violations);
      });
    };

    updateCameraState({
      streamReady: false,
      cameraError: "",
      detectionError: "",
      violations: [],
    });

    if (disabled || (!deviceId && !allowDefaultCamera)) {
      updateCameraState({ cameraError: disabledMessage });
      return cleanup;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      updateCameraState({ cameraError: "Browser tidak mendukung akses kamera." });
      return cleanup;
    }

    const constraints = {
      audio: false,
      video: deviceId
        ? {
            deviceId: { exact: deviceId },
            width: { ideal: CAPTURE_WIDTH },
            height: { ideal: CAPTURE_HEIGHT },
          }
        : {
            width: { ideal: CAPTURE_WIDTH },
            height: { ideal: CAPTURE_HEIGHT },
          },
    };

    navigator.mediaDevices
      .getUserMedia(constraints)
      .then((nextStream) => {
        if (!active) {
          nextStream.getTracks().forEach((track) => track.stop());
          return;
        }

        stream = nextStream;
        videoElement = videoRef.current;
        if (videoElement) videoElement.srcObject = nextStream;
        setStreamReady(true);
        onStreamReady?.();
      })
      .catch((err) => {
        if (!active) return;
        setCameraError("Camera tidak bisa dibuka.");
        onStreamError?.(err);
      });

    return cleanup;
  }, [
    allowDefaultCamera,
    clearOverlay,
    deviceId,
    disabled,
    disabledMessage,
    onStreamError,
    onStreamReady,
  ]);

  useEffect(() => {
    if (!streamReady || disabled || cameraError) return undefined;

    const wsProto = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = import.meta.env.VITE_WS_URL || `${wsProto}://${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsReady(true);
      setDetectionError("");
      frameIntervalRef.current = setInterval(() => {
        const video = videoRef.current;
        const canvas = captureCanvasRef.current;

        if (!video || !canvas || video.readyState < 2 || ws.readyState !== WebSocket.OPEN) {
          return;
        }

        canvas.width = CAPTURE_WIDTH;
        canvas.height = CAPTURE_HEIGHT;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        ctx.drawImage(video, 0, 0, CAPTURE_WIDTH, CAPTURE_HEIGHT);
        const frame = canvas.toDataURL("image/jpeg", 0.6).split(",")[1];

        ws.send(JSON.stringify({ camera_id: resolvedCameraId, frame }));
      }, FRAME_INTERVAL_MS);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        drawBoxes(data.detections || []);

        if (data.violations?.length > 0) {
          setViolations(data.violations);
          clearTimeout(violationTimeoutRef.current);
          violationTimeoutRef.current = setTimeout(() => setViolations([]), 5000);
        }
      } catch (err) {
        console.error("[WS] Invalid detection response:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("[WS] Error:", err);
      setWsReady(false);
      setDetectionError("AI detection tidak tersambung.");
    };

    ws.onclose = () => {
      setWsReady(false);
      clearInterval(frameIntervalRef.current);
    };

    return () => {
      clearInterval(frameIntervalRef.current);
      clearTimeout(violationTimeoutRef.current);
      setWsReady(false);
      ws.close();
    };
  }, [cameraError, disabled, drawBoxes, resolvedCameraId, streamReady]);

  const statusText = cameraError ? "Offline" : wsReady ? "Detecting" : "Connecting";
  const statusClass = cameraError
    ? "bg-gray-600"
    : wsReady
      ? "bg-red-600 animate-pulse"
      : "bg-yellow-600";

  return (
    <div className="bg-black aspect-video relative overflow-hidden">
      {!cameraError && (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />
      )}

      <canvas ref={captureCanvasRef} className="hidden" />
      <canvas
        ref={overlayCanvasRef}
        className="absolute inset-0 w-full h-full"
        style={{ pointerEvents: "none" }}
      />

      <div className="absolute top-3 left-3 z-10 flex flex-col gap-1">
        <div className="bg-black/50 text-white text-[10px] px-2 py-1 rounded font-mono">
          {timestamp}
        </div>
        <div className={`${statusClass} text-white text-[10px] px-2 py-0.5 rounded font-bold uppercase w-fit`}>
          {statusText}
        </div>
      </div>

      {cameraError && (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center">
          <div>
            <p className="text-sm font-bold text-white">{cameraError}</p>
            <p className="mt-1 text-xs text-gray-400">{label}</p>
          </div>
        </div>
      )}

      {!cameraError && detectionError && (
        <div className="absolute bottom-3 left-3 right-3 bg-yellow-600/90 text-white text-xs px-2 py-1 rounded font-bold z-10">
          {detectionError}
        </div>
      )}

      {violations.length > 0 && (
        <div className="absolute bottom-3 left-3 right-3 bg-red-600/90 text-white text-xs px-2 py-1 rounded font-bold z-10">
          ALERT: {violations.map((v) => v.type.replace(/_/g, " ").toUpperCase()).join(", ")}
        </div>
      )}
    </div>
  );
}
