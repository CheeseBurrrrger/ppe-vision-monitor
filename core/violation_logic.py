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
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional

# ─────────────────────────────────────────────
#  LOGGING SETUP
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  ATURAN PELANGGARAN
#  Sesuaikan dengan kebutuhan K3 pabrik kamu
# ─────────────────────────────────────────────

VIOLATION_RULES: Dict[str, dict] = {
    "no_helmet": {
        "description": "Pekerja tidak menggunakan helm safety",
        "severity":    "HIGH",
        "cooldown":    15,      # detik — tunggu 15 detik sebelum buat event baru
        "min_conf":    0.40,    # confidence minimum khusus kelas ini
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
        "cooldown":    30,      # sepatu lebih susah deteksi → cooldown lebih panjang
        "min_conf":    0.35,
    },
}

# Kelas APD yang AMAN (kepatuhan terpenuhi)
COMPLIANT_CLASSES = {"helmet", "vest", "safety_boot"}

# Semua kelas pelanggaran
VIOLATION_CLASSES = set(VIOLATION_RULES.keys())


# ─────────────────────────────────────────────
#  DATA CLASS
# ─────────────────────────────────────────────

@dataclass
class Detection:
    """
    Satu objek hasil deteksi YOLO.
    Diisi oleh inference.py dan dikirim ke ViolationLogic.
    """
    class_name: str
    confidence: float
    bbox: tuple        # (x1, y1, x2, y2)


@dataclass
class ViolationEvent:
    """
    Satu event pelanggaran K3.
    Siap dikirim ke backend API (prodi TI) atau disimpan lokal.
    """
    event_id:        str
    timestamp:       str
    camera_id:       str
    violation_type:  str
    description:     str
    severity:        str           # HIGH / MEDIUM / LOW
    confidence:      float
    bbox:            dict          # {x1, y1, x2, y2}
    frame_number:    int
    screenshot_path: Optional[str] = None
    sent_to_backend: bool          = False

    def to_json(self) -> str:
        """Konversi ke JSON string untuk log / API."""
        return json.dumps(asdict(self), ensure_ascii=False)


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class ViolationLogic:
    """
    Modul logika pelanggaran K3.

    Terima list Detection dari inference.py →
    Tentukan mana pelanggaran →
    Terapkan cooldown →
    Hasilkan ViolationEvent →
    Simpan screenshot + log.

    Contoh integrasi di inference.py:
    ─────────────────────────────────
    from violation_logic import ViolationLogic, Detection

    logic = ViolationLogic(camera_id="CAM_01")

    # Di dalam loop inference:
    detections = [
        Detection("no_helmet", 0.82, (100, 50, 200, 150)),
        Detection("vest",      0.91, (90,  150, 210, 350)),
    ]
    events = logic.process(detections, frame, frame_number=42)
    """

    def __init__(
        self,
        camera_id:        str  = "CAM_01",
        output_dir:       str  = "violation_output",
        save_screenshots: bool = True,
        log_to_file:      bool = True,
    ):
        self.camera_id        = camera_id
        self.save_screenshots = save_screenshots
        self.log_to_file      = log_to_file

        # Folder output
        self.output_dir     = Path(output_dir)
        self.screenshot_dir = self.output_dir / "screenshots"
        if save_screenshots:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # File log
        self.log_file = self.output_dir / "violations.jsonl"
        if log_to_file:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        # ── State cooldown ──
        # Format: { "no_helmet": timestamp_terakhir_event, ... }
        self._last_event_time: Dict[str, float] = {}

        # ── Statistik session ──
        self.stats = {
            "total_events":     0,
            "events_per_type":  {v: 0 for v in VIOLATION_RULES},
            "frames_processed": 0,
        }

        logger.info(f"ViolationLogic aktif | camera={camera_id} | output={self.output_dir.resolve()}")

    # ── PUBLIC API ──────────────────────────────

    def process(
        self,
        detections:   List[Detection],
        frame,                            # np.ndarray dari OpenCV
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        """
        Fungsi utama. Panggil ini setiap frame dari inference.py.

        Parameter:
            detections   : list Detection hasil YOLO
            frame        : frame OpenCV (numpy array) untuk screenshot
            frame_number : nomor frame saat ini

        Return:
            list ViolationEvent (kosong jika tidak ada pelanggaran / masih cooldown)
        """
        self.stats["frames_processed"] += 1
        events = []

        # Kumpulkan semua kelas yang terdeteksi di frame ini
        detected_classes = {d.class_name for d in detections}

        # ── Cek setiap tipe pelanggaran ──
        for vtype, rule in VIOLATION_RULES.items():

            # 1. Apakah kelas ini terdeteksi di frame?
            if vtype not in detected_classes:
                continue

            # 2. Ambil deteksi terbaik (confidence tertinggi)
            candidates = [d for d in detections if d.class_name == vtype]
            best = max(candidates, key=lambda d: d.confidence)

            # 3. Cek minimum confidence khusus kelas ini
            if best.confidence < rule["min_conf"]:
                logger.debug(
                    f"Skip {vtype}: conf={best.confidence:.2f} < min={rule['min_conf']}"
                )
                continue

            # 4. Cek cooldown
            if self._is_in_cooldown(vtype, rule["cooldown"]):
                remaining = self._cooldown_remaining(vtype, rule["cooldown"])
                logger.debug(f"Cooldown {vtype}: {remaining:.1f}s tersisa")
                continue

            # 5. Semua lolos → buat event pelanggaran
            event = self._create_event(
                vtype        = vtype,
                rule         = rule,
                detection    = best,
                frame        = frame,
                frame_number = frame_number,
            )

            events.append(event)

            # Update cooldown timer
            self._last_event_time[vtype] = time.time()

            # Update statistik
            self.stats["total_events"] += 1
            self.stats["events_per_type"][vtype] += 1

            # Log ke terminal
            logger.warning(
                f"🚨 PELANGGARAN | {vtype:20s} | "
                f"severity={rule['severity']:6s} | "
                f"conf={best.confidence:.2f} | "
                f"frame={frame_number}"
            )

            # Simpan ke file log
            if self.log_to_file:
                self._append_log(event)

        return events

    def get_frame_status(self, detections: List[Detection]) -> dict:
        """
        Ringkasan status K3 untuk satu frame.
        Berguna untuk overlay dashboard / UI.

        Return contoh:
        {
            "helmet":       "COMPLIANT",    # terdeteksi helm
            "vest":         "VIOLATION",    # terdeteksi no_vest
            "safety_boot":  "UNKNOWN",      # tidak ada deteksi sama sekali
        }
        """
        detected = {d.class_name for d in detections}
        status   = {}

        apd_map = {
            "helmet":      ("helmet",      "no_helmet"),
            "vest":        ("vest",        "no_vest"),
            "safety_boot": ("safety_boot", "no_safety_boot"),
        }

        for apd, (pos, neg) in apd_map.items():
            if pos in detected:
                status[apd] = "COMPLIANT"
            elif neg in detected:
                status[apd] = "VIOLATION"
            else:
                status[apd] = "UNKNOWN"

        return status

    def print_session_summary(self):
        """Cetak ringkasan statistik session ke terminal."""
        print(f"\n{'='*55}")
        print(f"  RINGKASAN SESI PELANGGARAN")
        print(f"{'='*55}")
        print(f"  Camera ID           : {self.camera_id}")
        print(f"  Frame diproses      : {self.stats['frames_processed']}")
        print(f"  Total event         : {self.stats['total_events']}")
        print(f"\n  Breakdown per tipe:")
        for vtype, count in self.stats["events_per_type"].items():
            rule   = VIOLATION_RULES[vtype]
            marker = "🚨" if count > 0 else "  "
            print(f"    {marker} {vtype:20s}: {count} event  [{rule['severity']}]")
        print(f"\n  Log file  : {self.log_file.resolve()}")
        print(f"  Screenshot: {self.screenshot_dir.resolve()}")
        print(f"{'='*55}\n")

    # ── PRIVATE HELPER ───────────────────────────

    def _is_in_cooldown(self, vtype: str, cooldown_sec: float) -> bool:
        """True jika masih dalam periode cooldown."""
        last = self._last_event_time.get(vtype, 0)
        return (time.time() - last) < cooldown_sec

    def _cooldown_remaining(self, vtype: str, cooldown_sec: float) -> float:
        """Berapa detik cooldown tersisa."""
        last = self._last_event_time.get(vtype, 0)
        return max(0.0, cooldown_sec - (time.time() - last))

    def _create_event(
        self,
        vtype:        str,
        rule:         dict,
        detection:    Detection,
        frame,
        frame_number: int,
    ) -> ViolationEvent:
        """Buat objek ViolationEvent dan simpan screenshot."""
        now      = time.time()
        dt       = datetime.fromtimestamp(now)
        event_id = f"{self.camera_id}_{frame_number}_{vtype}_{int(now)}"

        # Simpan screenshot
        screenshot_path = None
        if self.save_screenshots and frame is not None:
            screenshot_path = self._save_screenshot(frame, detection, dt, vtype)

        return ViolationEvent(
            event_id        = event_id,
            timestamp       = dt.isoformat(),
            camera_id       = self.camera_id,
            violation_type  = vtype,
            description     = rule["description"],
            severity        = rule["severity"],
            confidence      = round(detection.confidence, 4),
            bbox            = {
                "x1": detection.bbox[0], "y1": detection.bbox[1],
                "x2": detection.bbox[2], "y2": detection.bbox[3],
            },
            frame_number    = frame_number,
            screenshot_path = screenshot_path,
        )

    def _save_screenshot(
        self,
        frame,
        detection:  Detection,
        dt:         datetime,
        vtype:      str,
    ) -> str:
        """Simpan frame dengan anotasi pelanggaran sebagai JPG."""
        shot = frame.copy()
        x1, y1, x2, y2 = detection.bbox

        # Kotak merah tebal di area pelanggaran
        cv2.rectangle(shot, (x1, y1), (x2, y2), (0, 0, 220), 3)

        # Banner merah di atas
        banner_h = 60
        cv2.rectangle(shot, (0, 0), (shot.shape[1], banner_h), (0, 0, 180), -1)
        cv2.putText(
            shot,
            f"VIOLATION: {vtype.upper().replace('_', ' ')}",
            (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
            (255, 255, 255), 2, cv2.LINE_AA
        )

        # Timestamp
        cv2.putText(
            shot,
            dt.strftime("%Y-%m-%d %H:%M:%S"),
            (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
            (200, 200, 200), 1, cv2.LINE_AA
        )

        # Confidence
        cv2.putText(
            shot,
            f"conf: {detection.confidence:.2f}",
            (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
            (0, 0, 220), 2, cv2.LINE_AA
        )

        # Simpan file
        filename = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path     = self.screenshot_dir / filename
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])

        return str(path)

    def _append_log(self, event: ViolationEvent):
        """Tambahkan event ke file .jsonl (1 baris = 1 event)."""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")


# ─────────────────────────────────────────────
#  TEST STANDALONE
#  Jalankan: python violation_logic.py
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import numpy as np

    print("\n=== TEST violation_logic.py ===\n")

    # Inisialisasi modul
    logic = ViolationLogic(
        camera_id   = "CAM_TEST",
        output_dir  = "test_violation_output",
    )

    # Buat frame dummy (hitam 640x480)
    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        dummy_frame, "DUMMY FRAME",
        (200, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
        (100, 100, 100), 2
    )

    # ── TEST 1: Deteksi no_helmet ──
    print("--- TEST 1: no_helmet terdeteksi ---")
    dets = [
        Detection("no_helmet", confidence=0.85, bbox=(100, 30, 250, 160)),
        Detection("vest",      confidence=0.90, bbox=(80,  160, 270, 380)),
    ]
    events = logic.process(dets, dummy_frame, frame_number=10)
    print(f"Events dihasilkan: {len(events)}")
    for e in events:
        print(f"  → {e.violation_type} | {e.severity} | conf={e.confidence}")

    # ── TEST 2: Cooldown (langsung panggil lagi) ──
    print("\n--- TEST 2: Cooldown (panggil langsung setelah test 1) ---")
    events2 = logic.process(dets, dummy_frame, frame_number=11)
    print(f"Events dihasilkan: {len(events2)}  ← harusnya 0 (masih cooldown)")

    # ── TEST 3: no_vest + no_helmet bersamaan ──
    print("\n--- TEST 3: no_helmet + no_vest bersamaan ---")
    # Reset cooldown untuk test ini
    logic._last_event_time = {}
    dets3 = [
        Detection("no_helmet", confidence=0.78, bbox=(110, 20, 240, 150)),
        Detection("no_vest",   confidence=0.65, bbox=(90,  155, 260, 370)),
    ]
    events3 = logic.process(dets3, dummy_frame, frame_number=50)
    print(f"Events dihasilkan: {len(events3)}  ← harusnya 2")
    for e in events3:
        print(f"  → {e.violation_type} | {e.severity} | conf={e.confidence}")

    # ── TEST 4: Confidence terlalu rendah ──
    print("\n--- TEST 4: Confidence rendah (di bawah min_conf) ---")
    logic._last_event_time = {}
    dets4 = [
        Detection("no_helmet", confidence=0.25, bbox=(100, 30, 250, 160)),  # di bawah 0.40
    ]
    events4 = logic.process(dets4, dummy_frame, frame_number=80)
    print(f"Events dihasilkan: {len(events4)}  ← harusnya 0 (conf terlalu rendah)")

    # ── TEST 5: Frame Status ──
    print("\n--- TEST 5: Frame Status K3 ---")
    logic._last_event_time = {}
    dets5 = [
        Detection("helmet",   confidence=0.92, bbox=(100, 20, 240, 140)),
        Detection("no_vest",  confidence=0.71, bbox=(90, 145, 255, 360)),
    ]
    status = logic.get_frame_status(dets5)
    print(f"Status K3 frame ini:")
    for apd, s in status.items():
        icon = "✅" if s == "COMPLIANT" else ("🚨" if s == "VIOLATION" else "❓")
        print(f"  {icon} {apd:15s}: {s}")

    # Ringkasan
    logic.print_session_summary()

    print(f"✅ Screenshot tersimpan di: test_violation_output/screenshots/")
    print(f"✅ Log tersimpan di       : test_violation_output/violations.jsonl")