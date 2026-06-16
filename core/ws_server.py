import asyncio
import base64
import cv2
import numpy as np
import sys
import os
import json
import time
import websockets

# Disable MKLDNN before importing torch — required for CPUs without AVX/SSE4
# (e.g. older KVM VPS). Harmless on modern CPUs.
import torch
torch.backends.mkldnn.enabled = False
torch.backends.nnpack.set_flags(False)

TORCH_NUM_THREADS = int(os.getenv("TORCH_NUM_THREADS", str(min(2, os.cpu_count() or 1))))
torch.set_num_threads(TORCH_NUM_THREADS)
try:
    torch.set_num_interop_threads(1)
except RuntimeError:
    pass

from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(__file__))
from inference import APDInferencePipeline
from violation_logic import ViolationLogic

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CV_SERVICE_KEY = os.getenv("CV_SERVICE_KEY", "")
WS_PORT = int(os.getenv("WS_PORT", "8765"))
MODEL_INPUT_SIZE = int(os.getenv("MODEL_INPUT_SIZE", "416"))
DEFAULT_MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "model", "best2.pt"
)
MODEL_PATH = os.path.abspath(os.getenv("MODEL_PATH", DEFAULT_MODEL_PATH))

pipelines = {}
inference_lock = asyncio.Lock()
shared_model = None

def get_pipeline(camera_id):
    if camera_id not in pipelines:
        pipelines[camera_id] = APDInferencePipeline(
            model_path=MODEL_PATH,
            camera_id=camera_id,
            output_dir=os.path.join(os.path.dirname(__file__), 'inference_output'),
            backend_url=BACKEND_URL,
            service_key=CV_SERVICE_KEY,
            input_size=MODEL_INPUT_SIZE,
            shared_model=shared_model,
        )
    return pipelines[camera_id]

def process_message(message):
    data = json.loads(message)
    camera_id = data.get("camera_id", "CAM_UNKNOWN")
    frame_b64 = data.get("frame", "")

    img_bytes = base64.b64decode(frame_b64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Invalid camera frame")

    pipeline = get_pipeline(camera_id)
    started_at = time.perf_counter()

    with torch.inference_mode():
        detections = pipeline.run_inference(frame)
    pipeline.frame_count += 1

    live_violations = pipeline.violation_logic.get_live_violations(
        detections=detections,
        frame_height=frame.shape[0],
    )
    events = pipeline.violation_logic.process(
        detections=detections,
        frame=frame,
        frame_number=pipeline.frame_count,
    )
    processing_ms = round((time.perf_counter() - started_at) * 1000, 1)

    return {
        "detections": [
            {
                "class": d.class_name,
                "confidence": round(d.confidence, 3),
                "bbox": list(d.bbox),
            }
            for d in detections
        ],
        "violations": live_violations,
        "logged_events": [
            {
                "type": e.violation_type,
                "severity": e.severity,
                "confidence": e.confidence,
                "bbox": [e.bbox["x1"], e.bbox["y1"], e.bbox["x2"], e.bbox["y2"]],
                "detection_mode": e.detection_mode,
            }
            for e in events
        ],
        "processing_ms": processing_ms,
    }

async def handle(websocket):
    try:
        async for message in websocket:
            try:
                async with inference_lock:
                    result = await asyncio.to_thread(process_message, message)
                await websocket.send(json.dumps(result))
            except Exception as e:
                print(f"[WS] Frame error: {e}", flush=True)
    except websockets.exceptions.ConnectionClosed:
        pass

async def main():
    global shared_model

    host = os.getenv("WS_HOST", "0.0.0.0")
    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
    print(f"[WS] Model: {MODEL_PATH}", flush=True)
    print(
        f"[WS] CPU: threads={TORCH_NUM_THREADS}, mkldnn=off, "
        f"nnpack=off, input={MODEL_INPUT_SIZE}px",
        flush=True,
    )
    shared_model = YOLO(MODEL_PATH)
    warmup_frame = np.zeros(
        (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE, 3),
        dtype=np.uint8,
    )
    with torch.inference_mode():
        shared_model.predict(
            warmup_frame,
            imgsz=MODEL_INPUT_SIZE,
            conf=0.3,
            device="cpu",
            verbose=False,
        )
    print("[WS] Model warm-up complete", flush=True)
    print(f"[WS] Starting server on ws://{host}:{WS_PORT}", flush=True)
    async with websockets.serve(handle, host, WS_PORT, max_queue=1):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
