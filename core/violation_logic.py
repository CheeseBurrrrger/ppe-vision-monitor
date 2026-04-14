"""
violation_logic.py
==================
Modul logika pelanggaran K3 — deteksi no_helmet, no_vest, no_safety_boot
dengan sistem cooldown agar tidak spam event.

Terintegrasi dengan inference.py sebagai modul terpisah.

Capstone Project: Sistem Monitoring K3 Berbasis Computer Vision

Cara pakai (standalone test):
  python violation_logic.py

Cara import di inference.py:
  from violation_logic import ViolationLogic, ViolationEvent
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
 
 
# ─────────────────────────────────────────────
#  KONFIGURASI BACKEND
#
#  Sesuaikan BACKEND_URL dengan IP server backend
#  saat integrasi. Jika backend belum jalan,
#  set BACKEND_URL = None → hanya simpan lokal.
# ─────────────────────────────────────────────
 
BACKEND_URL = "http://localhost:8000"   # ganti IP jika backend di server lain
BACKEND_TIMEOUT = 5                      # detik timeout per request
 
 
# ─────────────────────────────────────────────
#  ATURAN PELANGGARAN
# ─────────────────────────────────────────────
 
VIOLATION_RULES: Dict[str, dict] = {
    "no_helmet": {
        "description": "Pekerja tidak menggunakan helm safety",
        "severity":    "HIGH",
        "cooldown":    15,
        "min_conf":    0.40,
    },
    "no_vest": {
        "description": "Pekerja tidak menggunakan rompi safety",
        "severity":    "HIGH",
        "cooldown":    15,
        "min_conf":    0.40,
    },
    "no_safety_boot": {
        "description": "Pekerja tidak menggunakan sepatu safety",
        "severity":    "MEDIUM",
        "cooldown":    30,
        "min_conf":    0.35,
    },
}
 
COMPLIANT_CLASSES  = {"helmet", "vest", "safety_boot"}
VIOLATION_CLASSES  = set(VIOLATION_RULES.keys())
 
 
# ─────────────────────────────────────────────
#  DATA CLASS
# ─────────────────────────────────────────────
 
@dataclass
class Detection:
    """Satu objek hasil deteksi YOLO. Dibuat oleh inference.py."""
    class_name: str
    confidence: float
    bbox:       tuple    # (x1, y1, x2, y2)
 
 
@dataclass
class ViolationEvent:
    """
    Satu event pelanggaran K3.
    Field disesuaikan dengan ViolationCreate schema backend:
      violation_type, confidence, timestamp, frame_path, camera_id
    """
    event_id:        str
    timestamp:       str            # ISO format — diterima backend sebagai datetime
    camera_id:       str
    violation_type:  str
    description:     str
    severity:        str
    confidence:      float
    bbox:            dict
    frame_number:    int
    frame_path:      Optional[str]  # nama field sesuai schema backend (frame_path)
    sent_to_backend: bool = False
 
    def to_backend_payload(self) -> dict:
        """
        Bentuk payload yang dikirim ke POST /violations.
        Field disesuaikan persis dengan ViolationCreate di schemas.py:
          - violation_type : str
          - confidence     : float (0.0 - 1.0)
          - timestamp      : datetime (ISO string)
          - frame_path     : str | None
          - camera_id      : str
        """
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
    """
    Logika pelanggaran K3:
      1. Terima list Detection dari inference.py
      2. Filter berdasarkan min_conf dan cooldown
      3. Buat ViolationEvent
      4. Simpan screenshot lokal
      5. Simpan log .jsonl lokal
      6. Kirim ke backend → POST /violations
 
    Integrasi backend:
    ───────────────────────────
    Backend menerima:
      POST http://localhost:8000/violations
      Content-Type: application/json
      Body: {
        "violation_type": "no_helmet",
        "confidence": 0.85,
        "timestamp": "2025-03-18T14:30:00",
        "frame_path": "violations/screenshots/no_helmet_xxx.jpg",
        "camera_id": "CAM_01"
      }
 
    Response sukses: HTTP 201 + ViolationResponse JSON
    """
 
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
 
        # Folder output
        self.output_dir     = Path(output_dir)
        self.screenshot_dir = self.output_dir / "screenshots"
        if save_screenshots:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        if log_to_file:
            self.output_dir.mkdir(parents=True, exist_ok=True)
 
        self.log_file = self.output_dir / "violations.jsonl"
 
        # Cooldown tracker
        self._last_event_time: Dict[str, float] = {}
 
        # Statistik session
        self.stats = {
            "total_events":       0,
            "events_per_type":    {v: 0 for v in VIOLATION_RULES},
            "sent_to_backend":    0,
            "failed_to_backend":  0,
            "frames_processed":   0,
        }
 
        backend_status = f"→ {backend_url}" if backend_url else "→ OFF (lokal only)"
        logger.info(
            f"ViolationLogic aktif | cam={camera_id} | "
            f"backend={backend_status}"
        )
 
    # ── PUBLIC API ──────────────────────────────
 
    def process(
        self,
        detections:   List[Detection],
        frame,
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        """
        Panggil setiap frame dari inference.py.
        Return: list ViolationEvent yang lolos cooldown (bisa kosong).
        """
        self.stats["frames_processed"] += 1
        events = []
 
        detected_classes = {d.class_name for d in detections}
 
        for vtype, rule in VIOLATION_RULES.items():
            if vtype not in detected_classes:
                continue
 
            # Ambil deteksi confidence tertinggi
            best = max(
                (d for d in detections if d.class_name == vtype),
                key=lambda d: d.confidence
            )
 
            # Filter minimum confidence
            if best.confidence < rule["min_conf"]:
                logger.debug(
                    f"Skip {vtype}: conf={best.confidence:.2f} "
                    f"< min={rule['min_conf']}"
                )
                continue
 
            # Filter cooldown
            if self._in_cooldown(vtype, rule["cooldown"]):
                sisa = self._cooldown_remaining(vtype, rule["cooldown"])
                logger.debug(f"Cooldown {vtype}: {sisa:.1f}s tersisa")
                continue
 
            # Buat event
            event = self._create_event(vtype, rule, best, frame, frame_number)
            events.append(event)
 
            # Update cooldown + statistik
            self._last_event_time[vtype] = time.time()
            self.stats["total_events"] += 1
            self.stats["events_per_type"][vtype] += 1
 
            logger.warning(
                f"🚨 PELANGGARAN | {vtype:20s} | "
                f"severity={rule['severity']:6s} | "
                f"conf={best.confidence:.2f} | frame={frame_number}"
            )
 
            # Simpan log lokal
            if self.log_to_file:
                self._write_log(event)
 
            # Kirim ke backend
            if self.backend_url:
                self._send_to_backend(event)
 
        return events
 
    def get_frame_status(self, detections: List[Detection]) -> dict:
        """
        Status K3 per APD untuk satu frame.
        Return: {"helmet": "COMPLIANT"/"VIOLATION"/"UNKNOWN", ...}
        """
        detected = {d.class_name for d in detections}
        apd_map  = {
            "helmet":      ("helmet",      "no_helmet"),
            "vest":        ("vest",        "no_vest"),
            "safety_boot": ("safety_boot", "no_safety_boot"),
        }
        status = {}
        for apd, (pos, neg) in apd_map.items():
            if pos in detected:
                status[apd] = "COMPLIANT"
            elif neg in detected:
                status[apd] = "VIOLATION"
            else:
                status[apd] = "UNKNOWN"
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
            print(
                f"    {marker} {vtype:20s}: {count} event  "
                f"[{rule['severity']}]"
            )
        print(f"\n  Log    : {self.log_file.resolve()}")
        print(f"  Foto   : {self.screenshot_dir.resolve()}")
        print(f"  Backend: {self.backend_url or 'OFF'}")
        print(f"{'='*55}\n")
 
    # ── BACKEND INTEGRATION ─────────────────────
 
    def _send_to_backend(self, event: ViolationEvent):
        """
        Kirim event ke backend.
        Endpoint : POST /violations
        Schema   : ViolationCreate (schemas.py)
        Fields   : violation_type, confidence, timestamp,
                   frame_path, camera_id
        """
        url     = f"{self.backend_url}/violations"
        payload = event.to_backend_payload()
 
        try:
            response = requests.post(
                url,
                json    = payload,
                timeout = BACKEND_TIMEOUT,
                headers = {"Content-Type": "application/json"},
            )
 
            if response.status_code == 201:
                # Sukses — backend return ViolationResponse dengan id
                data = response.json()
                event.sent_to_backend = True
                self.stats["sent_to_backend"] += 1
                logger.info(
                    f"  ✅ Backend OK | id={data.get('id')} | "
                    f"type={event.violation_type}"
                )
            else:
                self.stats["failed_to_backend"] += 1
                logger.warning(
                    f"  ⚠️  Backend {response.status_code} | "
                    f"{response.text[:100]}"
                )
 
        except requests.exceptions.ConnectionError:
            self.stats["failed_to_backend"] += 1
            logger.warning(
                f"  ❌ Backend tidak bisa dihubungi ({url}). "
                f"Event disimpan lokal."
            )
        except requests.exceptions.Timeout:
            self.stats["failed_to_backend"] += 1
            logger.warning(
                f"  ❌ Backend timeout ({BACKEND_TIMEOUT}s). "
                f"Event disimpan lokal."
            )
        except Exception as e:
            self.stats["failed_to_backend"] += 1
            logger.error(f"  ❌ Error kirim backend: {e}")
 
    # ── HELPER ──────────────────────────────────
 
    def _in_cooldown(self, vtype: str, cooldown: float) -> bool:
        return (time.time() - self._last_event_time.get(vtype, 0)) < cooldown
 
    def _cooldown_remaining(self, vtype: str, cooldown: float) -> float:
        return max(0.0, cooldown - (time.time() - self._last_event_time.get(vtype, 0)))
 
    def _create_event(
        self,
        vtype:        str,
        rule:         dict,
        detection:    Detection,
        frame,
        frame_number: int,
    ) -> ViolationEvent:
        now      = time.time()
        dt       = datetime.fromtimestamp(now, tz=timezone.utc)
        event_id = f"{self.camera_id}_{frame_number}_{vtype}_{int(now)}"
 
        # Simpan screenshot
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
            frame_path     = frame_path,   # field sesuai schema backend (frame_path)
        )
 
    def _save_screenshot(
        self,
        frame,
        detection:  Detection,
        dt:         datetime,
        vtype:      str,
    ) -> str:
        shot        = frame.copy()
        x1, y1, x2, y2 = detection.bbox
 
        # Kotak merah pelanggaran
        cv2.rectangle(shot, (x1, y1), (x2, y2), (0, 0, 220), 3)
 
        # Banner atas
        cv2.rectangle(shot, (0, 0), (shot.shape[1], 62), (0, 0, 175), -1)
        cv2.putText(
            shot,
            f"VIOLATION: {vtype.upper().replace('_', ' ')}",
            (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
            (255, 255, 255), 2, cv2.LINE_AA
        )
        cv2.putText(
            shot,
            dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.48,
            (200, 200, 200), 1, cv2.LINE_AA
        )
 
        # Label confidence
        cv2.putText(
            shot,
            f"conf: {detection.confidence:.2f}",
            (x1, max(y1 - 8, 70)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            (0, 0, 220), 2, cv2.LINE_AA
        )
 
        filename = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path     = self.screenshot_dir / filename
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return str(path)
 
    def _write_log(self, event: ViolationEvent):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")
 
 
# ─────────────────────────────────────────────
#  TEST STANDALONE
#  python violation_logic.py
# ─────────────────────────────────────────────
 
if __name__ == "__main__":
    import numpy as np
 
    print("\n=== TEST violation_logic.py + backend ===\n")
 
    # Ganti backend_url=None jika backend belum jalan
    logic = ViolationLogic(
        camera_id   = "CAM_TEST",
        output_dir  = "test_violation_output",
        backend_url = None,   # ← ganti ke "http://localhost:8000" jika backend ON
    )
 
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        dummy_frame, "DUMMY FRAME",
        (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
        (100, 100, 100), 2
    )
 
    # TEST 1: no_helmet
    print("--- TEST 1: no_helmet ---")
    logic._last_event_time = {}
    events = logic.process(
        [Detection("no_helmet", 0.85, (100, 30, 250, 160))],
        dummy_frame, frame_number=10
    )
    print(f"Events: {len(events)} | payload: {events[0].to_backend_payload() if events else '-'}")
 
    # TEST 2: Cooldown
    print("\n--- TEST 2: Cooldown ---")
    events2 = logic.process(
        [Detection("no_helmet", 0.85, (100, 30, 250, 160))],
        dummy_frame, frame_number=11
    )
    print(f"Events: {len(events2)} ← harusnya 0 (cooldown)")
 
    # TEST 3: no_helmet + no_vest bersamaan
    print("\n--- TEST 3: no_helmet + no_vest ---")
    logic._last_event_time = {}
    events3 = logic.process(
        [
            Detection("no_helmet", 0.78, (110, 20,  240, 150)),
            Detection("no_vest",   0.65, (90,  155, 260, 370)),
        ],
        dummy_frame, frame_number=50
    )
    print(f"Events: {len(events3)} ← harusnya 2")
    for e in events3:
        print(f"  → payload: {e.to_backend_payload()}")
 
    # TEST 4: Conf terlalu rendah
    print("\n--- TEST 4: Confidence rendah ---")
    logic._last_event_time = {}
    events4 = logic.process(
        [Detection("no_helmet", 0.22, (100, 30, 250, 160))],
        dummy_frame, frame_number=80
    )
    print(f"Events: {len(events4)} ← harusnya 0 (conf < min_conf)")
 
    # TEST 5: Frame status
    print("\n--- TEST 5: Frame Status ---")
    logic._last_event_time = {}
    status = logic.get_frame_status([
        Detection("helmet",  0.92, (100, 20, 240, 140)),
        Detection("no_vest", 0.71, (90, 145, 255, 360)),
    ])
    for apd, s in status.items():
        icon = "✅" if s == "COMPLIANT" else ("🚨" if s == "VIOLATION" else "❓")
        print(f"  {icon} {apd:15s}: {s}")
 
    logic.print_session_summary()
 