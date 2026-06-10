import { useCallback, useEffect, useMemo, useState } from "react";

const DEFAULT_CAMERA_LIMIT = 3;

function mapVideoDevice(device, index) {
  return {
    id: device.deviceId || `camera-${index + 1}`,
    deviceId: device.deviceId,
    groupId: device.groupId || "",
    label: device.label || `Camera ${index + 1}`,
    index,
  };
}

function getUniqueVideoInputs(mediaDevices) {
  const videoInputs = mediaDevices.filter((device) => device.kind === "videoinput");
  const concreteInputs = videoInputs.filter((device) => device.deviceId && device.deviceId !== "default");
  const candidates = concreteInputs.length > 0 ? concreteInputs : videoInputs;
  const seenKeys = new Set();

  return candidates.filter((device, index) => {
    const key = device.groupId || device.label || device.deviceId || `camera-${index + 1}`;
    if (seenKeys.has(key)) return false;
    seenKeys.add(key);
    return true;
  });
}

export function useCameraDevices(maxSlots = DEFAULT_CAMERA_LIMIT) {
  const [devices, setDevices] = useState([]);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  const enumerateCameraDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      throw new Error("Browser tidak mendukung akses kamera.");
    }

    const mediaDevices = await navigator.mediaDevices.enumerateDevices();
    return getUniqueVideoInputs(mediaDevices)
      .slice(0, maxSlots)
      .map(mapVideoDevice);
  }, [maxSlots]);

  const refresh = useCallback(async () => {
    setStatus("loading");
    setError("");

    try {
      const nextDevices = await enumerateCameraDevices();
      setDevices(nextDevices);
      setStatus("ready");
      return nextDevices;
    } catch (err) {
      setDevices([]);
      setError(err.message || "Gagal membaca daftar kamera.");
      setStatus("error");
      return [];
    }
  }, [enumerateCameraDevices]);

  useEffect(() => {
    let active = true;

    const loadDevices = async () => {
      setStatus("loading");
      setError("");

      try {
        const nextDevices = await enumerateCameraDevices();
        if (!active) return;
        setDevices(nextDevices);
        setStatus("ready");
      } catch (err) {
        if (!active) return;
        setDevices([]);
        setError(err.message || "Gagal membaca daftar kamera.");
        setStatus("error");
      }
    };

    loadDevices();

    navigator.mediaDevices?.addEventListener?.("devicechange", loadDevices);
    return () => {
      active = false;
      navigator.mediaDevices?.removeEventListener?.("devicechange", loadDevices);
    };
  }, [enumerateCameraDevices]);

  const cameraSlots = useMemo(
    () => Array.from({ length: maxSlots }, (_, index) => devices[index] || null),
    [devices, maxSlots]
  );

  return {
    devices,
    cameraSlots,
    status,
    error,
    refresh,
  };
}
