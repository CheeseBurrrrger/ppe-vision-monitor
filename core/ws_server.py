import asyncio
import base64
import cv2
import numpy as np
import sys
import os
import json
import websockets
from ultralytics import YOLO

sys.path.insert(0, os.path.dirname(__file__))
from inference import APDInferencePipeline
from violation_logic import ViolationLogic

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
CV_SERVICE_KEY = os.getenv("CV_SERVICE_KEY", "")
WS_PORT = int(os.getenv("WS_PORT", "8765"))

pipelines = {}

def get_pipeline(camera_id):
    if camera_id not in pipelines:
        pipelines[camera_id] = APDInferencePipeline(
            model_path=os.path.join(os.path.dirname(__file__), '..', 'model', 'best2.pt'),
            camera_id=camera_id,
            output_dir=os.path.join(os.path.dirname(__file__), 'inference_output'),
            backend_url=BACKEND_URL,
            service_key=CV_SERVICE_KEY,
        )
    return pipelines[camera_id]

async def handle(websocket):
    async for message in websocket:
        try:
            data = json.loads(message)
            camera_id = data.get("camera_id", "CAM_UNKNOWN")
            frame_b64 = data.get("frame", "")

            img_bytes = base64.b64decode(frame_b64)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is None:
                continue

            # Get or create pipeline for this camera
            pipeline = get_pipeline(camera_id)

            detections = pipeline.run_inference(frame)
            pipeline.frame_count += 1

            events = pipeline.violation_logic.process(
                detections=detections,
                frame=frame,
                frame_number=pipeline.frame_count,
            )

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
    host = os.getenv("WS_HOST", "0.0.0.0")
    print(f"[WS] Starting server on ws://{host}:{WS_PORT}")
    async with websockets.serve(handle, host, WS_PORT):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())