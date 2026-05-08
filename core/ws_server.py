"""
ws_server.py
Receives frames from frontend via WebSocket, runs YOLO inference,
sends results back to frontend for overlay display.
"""
import asyncio
import base64
import cv2
import numpy as np
import sys
import os
import json
import websockets

sys.path.insert(0, os.path.dirname(__file__))
from inference import APDInferencePipeline
from violation_logic import ViolationLogic

BACKEND_URL = "http://localhost:8000"
WS_PORT = 8765

pipeline = APDInferencePipeline(
    model_path=os.path.join(os.path.dirname(__file__), '..', 'model', 'best.pt'),
    camera_id="FRONTEND_CAM",
    output_dir=os.path.join(os.path.dirname(__file__), 'inference_output'),
    backend_url=None,  # violations handled per-camera below
)

violation_logics = {}

def get_violation_logic(camera_id):
    if camera_id not in violation_logics:
        violation_logics[camera_id] = ViolationLogic(
            camera_id=camera_id,
            output_dir=os.path.join(os.path.dirname(__file__), 'inference_output'),
            backend_url=BACKEND_URL,
        )
    return violation_logics[camera_id]

async def handle(websocket):
    print(f"[WS] Client connected: {websocket.remote_address}")
    async for message in websocket:
        try:
            data = json.loads(message)
            camera_id = data.get("camera_id", "CAM_UNKNOWN")
            frame_b64 = data.get("frame", "")

            print(f"[WS] Frame received from {camera_id}, size: {len(frame_b64)}")

            img_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                continue

            detections = pipeline.run_inference(frame)
            print(f"[WS] Detections from {camera_id}: {[(d.class_name, round(d.confidence,2)) for d in detections]}")

            vlogic = get_violation_logic(camera_id)
            events = vlogic.process(
                detections=detections,
                frame=frame,
                frame_number=pipeline.frame_count,
            )
            pipeline.frame_count += 1

            result = {
                "detections": [
                    {
                        "class": d.class_name,
                        "confidence": round(d.confidence, 3),
                        "bbox": list(d.bbox)
                    }
                    for d in detections
                ],
                "violations": [
                    {
                        "type": e.violation_type,
                        "severity": e.severity,
                        "confidence": e.confidence
                    }
                    for e in events
                ]
            }
            await websocket.send(json.dumps(result))

        except Exception as e:
            print(f"[WS] Error: {e}")

async def main():
    print(f"[WS] Starting server on ws://localhost:{WS_PORT}")
    async with websockets.serve(handle, "localhost", WS_PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())