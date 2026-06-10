import DetectionCameraFeed from "./DetectionCameraFeed";

export default function DashboardCamFeed({
  label,
  device,
  deviceId,
  allowDefaultCamera = false,
  onStreamReady,
}) {
  const resolvedDeviceId = device?.deviceId || deviceId || "";
  const deviceLabel = device?.label || "No camera device";

  return (
    <div className="bg-white rounded-xl overflow-hidden shadow-sm border border-gray-200">
      <DetectionCameraFeed
        label={label}
        cameraId={label}
        deviceId={resolvedDeviceId}
        allowDefaultCamera={allowDefaultCamera}
        disabled={!resolvedDeviceId && !allowDefaultCamera}
        disabledMessage="Camera slot ini belum memiliki device."
        onStreamReady={onStreamReady}
      />
      <div className="p-3">
        <p className="text-sm font-semibold text-gray-800">{label}</p>
        <p className="mt-1 truncate text-[10px] font-semibold uppercase tracking-wide text-gray-400">
          {deviceLabel}
        </p>
      </div>
    </div>
  );
}
