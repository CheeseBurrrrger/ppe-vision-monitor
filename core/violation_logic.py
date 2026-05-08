"""
violation_logic.py
==================
Modul logika pelanggaran K3 — deteksi absence of helmet, vest, boots
dengan sistem cooldown agar tidak spam event.
"""

import cv2
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional

# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

BACKEND_URL = "http://localhost:8000"
BACKEND_TIMEOUT = 5

# ─────────────────────────────────────────────
#  ATURAN PELANGGARAN
#  violation = required PPE not detected in frame
# ─────────────────────────────────────────────

VIOLATION_RULES: Dict[str, dict] = {
    "no_helmet": {
        "required_class": "helmet",
        "description":    "Pekerja tidak menggunakan helm safety",
        "severity":       "HIGH",
        "cooldown":       15,
    },
    "no_vest": {
        "required_class": "vest",
        "description":    "Pekerja tidak menggunakan rompi safety",
        "severity":       "HIGH",
        "cooldown":       15,
    },
    "no_boots": {
        "required_class": "boots",
        "description":    "Pekerja tidak menggunakan sepatu safety",
        "severity":       "MEDIUM",
        "cooldown":       30,
    },
}

COMPLIANT_CLASSES = {"helmet", "vest", "boots", "gloves"}
VIOLATION_CLASSES = set(VIOLATION_RULES.keys())


# ─────────────────────────────────────────────
#  DATA CLASS
# ─────────────────────────────────────────────

@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox:       tuple

@dataclass
class ViolationEvent:
    event_id:        str
    timestamp:       str
    camera_id:       str
    violation_type:  str
    description:     str
    severity:        str
    confidence:      float
    bbox:            dict
    frame_number:    int
    frame_path:      Optional[str]
    sent_to_backend: bool = False

    def to_backend_payload(self) -> dict:
        return {
            "violation_type": self.violation_type,
            "confidence":     self.confidence,
            "timestamp":      self.timestamp,
            "frame_path":     self.frame_path,
            "camera_id":      self.camera_id,
        }

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class ViolationLogic:

    def __init__(
        self,
        camera_id:        str  = "CAM_01",
        output_dir:       str  = "violation_output",
        save_screenshots: bool = True,
        log_to_file:      bool = True,
        backend_url:      Optional[str] = BACKEND_URL,
    ):
        self.camera_id        = camera_id
        self.save_screenshots = save_screenshots
        self.log_to_file      = log_to_file
        self.backend_url      = backend_url

        self.output_dir     = Path(output_dir)
        self.screenshot_dir = self.output_dir / "screenshots"
        if save_screenshots:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        if log_to_file:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_file = self.output_dir / "violations.jsonl"
        self._last_event_time: Dict[str, float] = {}

        self.stats = {
            "total_events":      0,
            "events_per_type":   {v: 0 for v in VIOLATION_RULES},
            "sent_to_backend":   0,
            "failed_to_backend": 0,
            "frames_processed":  0,
        }

        backend_status = f"→ {backend_url}" if backend_url else "→ OFF (lokal only)"
        logger.info(f"ViolationLogic aktif | cam={camera_id} | backend={backend_status}")

    def process(
        self,
        detections:   List[Detection],
        frame,
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        self.stats["frames_processed"] += 1
        events = []

        # No detections = no person in frame, skip
        if len(detections) == 0:
            return events

        detected_classes = {d.class_name for d in detections}

        for vtype, rule in VIOLATION_RULES.items():
            required = rule["required_class"]

            # PPE is present — no violation
            if required in detected_classes:
                continue

            # Still in cooldown
            if self._in_cooldown(vtype, rule["cooldown"]):
                sisa = self._cooldown_remaining(vtype, rule["cooldown"])
                logger.debug(f"Cooldown {vtype}: {sisa:.1f}s tersisa")
                continue

            # Use highest confidence detection as reference for bbox/screenshot
            best = max(detections, key=lambda d: d.confidence)

            event = self._create_event(vtype, rule, best, frame, frame_number)
            events.append(event)

            self._last_event_time[vtype] = time.time()
            self.stats["total_events"] += 1
            self.stats["events_per_type"][vtype] += 1

            logger.warning(
                f"🚨 PELANGGARAN | {vtype:20s} | "
                f"severity={rule['severity']:6s} | frame={frame_number}"
            )

            if self.log_to_file:
                self._write_log(event)
            if self.backend_url:
                self._send_to_backend(event)

        return events

    def get_frame_status(self, detections: List[Detection]) -> dict:
        detected = {d.class_name for d in detections}
        apd_map  = {
            "helmet": "helmet",
            "vest":   "vest",
            "boots":  "boots",
        }
        status = {}
        for apd, required in apd_map.items():
            if required in detected:
                status[apd] = "COMPLIANT"
            else:
                status[apd] = "VIOLATION" if len(detections) > 0 else "UNKNOWN"
        return status

    def print_session_summary(self):
        print(f"\n{'='*55}")
        print(f"  RINGKASAN SESI PELANGGARAN")
        print(f"{'='*55}")
        print(f"  Camera ID           : {self.camera_id}")
        print(f"  Frame diproses      : {self.stats['frames_processed']}")
        print(f"  Total event         : {self.stats['total_events']}")
        print(f"  Terkirim ke backend : {self.stats['sent_to_backend']}")
        print(f"  Gagal ke backend    : {self.stats['failed_to_backend']}")
        print(f"\n  Breakdown per tipe:")
        for vtype, count in self.stats["events_per_type"].items():
            rule   = VIOLATION_RULES[vtype]
            marker = "🚨" if count > 0 else "  "
            print(f"    {marker} {vtype:20s}: {count} event  [{rule['severity']}]")
        print(f"\n  Log    : {self.log_file.resolve()}")
        print(f"  Foto   : {self.screenshot_dir.resolve()}")
        print(f"  Backend: {self.backend_url or 'OFF'}")
        print(f"{'='*55}\n")

    def _send_to_backend(self, event: ViolationEvent):
        url     = f"{self.backend_url}/violations"
        payload = event.to_backend_payload()
        try:
            response = requests.post(
                url, json=payload, timeout=BACKEND_TIMEOUT,
                headers={"Content-Type": "application/json"},
            )
            if response.status_code == 201:
                data = response.json()
                event.sent_to_backend = True
                self.stats["sent_to_backend"] += 1
                logger.info(f"  ✅ Backend OK | id={data.get('id')} | type={event.violation_type}")
            else:
                self.stats["failed_to_backend"] += 1
                logger.warning(f"  ⚠️  Backend {response.status_code} | {response.text[:100]}")
        except requests.exceptions.ConnectionError:
            self.stats["failed_to_backend"] += 1
            logger.warning(f"  ❌ Backend tidak bisa dihubungi ({url}).")
        except requests.exceptions.Timeout:
            self.stats["failed_to_backend"] += 1
            logger.warning(f"  ❌ Backend timeout ({BACKEND_TIMEOUT}s).")
        except Exception as e:
            self.stats["failed_to_backend"] += 1
            logger.error(f"  ❌ Error kirim backend: {e}")

    def _in_cooldown(self, vtype: str, cooldown: float) -> bool:
        return (time.time() - self._last_event_time.get(vtype, 0)) < cooldown

    def _cooldown_remaining(self, vtype: str, cooldown: float) -> float:
        return max(0.0, cooldown - (time.time() - self._last_event_time.get(vtype, 0)))

    def _create_event(self, vtype, rule, detection, frame, frame_number):
        now      = time.time()
        dt       = datetime.fromtimestamp(now, tz=timezone.utc)
        event_id = f"{self.camera_id}_{frame_number}_{vtype}_{int(now)}"

        frame_path = None
        if self.save_screenshots and frame is not None:
            frame_path = self._save_screenshot(frame, detection, dt, vtype)

        return ViolationEvent(
            event_id       = event_id,
            timestamp      = dt.isoformat(),
            camera_id      = self.camera_id,
            violation_type = vtype,
            description    = rule["description"],
            severity       = rule["severity"],
            confidence     = round(detection.confidence, 4),
            bbox           = {
                "x1": detection.bbox[0], "y1": detection.bbox[1],
                "x2": detection.bbox[2], "y2": detection.bbox[3],
            },
            frame_number   = frame_number,
            frame_path     = frame_path,
        )

    def _save_screenshot(self, frame, detection, dt, vtype):
        shot        = frame.copy()
        x1, y1, x2, y2 = detection.bbox
        cv2.rectangle(shot, (x1, y1), (x2, y2), (0, 0, 220), 3)
        cv2.rectangle(shot, (0, 0), (shot.shape[1], 62), (0, 0, 175), -1)
        cv2.putText(shot, f"VIOLATION: {vtype.upper().replace('_', ' ')}",
            (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(shot, dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA)
        filename = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path     = self.screenshot_dir / filename
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return str(path)

    def _write_log(self, event: ViolationEvent):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")