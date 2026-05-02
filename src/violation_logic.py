"""
violation_logic.py
==================
Modul logika pelanggaran K3 untuk model 5-kelas YOLOv11.

Model kelas:
    0: person  → orang / pekerja
    1: helmet  → helm safety
    2: vest    → rompi safety
    3: boots   → sepatu safety
    4: gloves  → sarung tangan

Logika pelanggaran:
    Seorang person dinyatakan MELANGGAR jika di dalam area bbox-nya
    TIDAK ditemukan APD yang sesuai (helmet / vest / boots).
    Gloves bersifat opsional — tidak memicu pelanggaran.

    Deteksi APD dianggap "milik" satu person jika minimal 30% area bbox APD
    berada di dalam bbox person. Ini sengaja toleran terhadap model yang
    masih dalam pengembangan / belum sempurna posisi deteksinya.

Capstone Project: Sistem Monitoring K3 Berbasis Computer Vision
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

logging.basicConfig(
    level   = logging.INFO,
    format  = "[%(asctime)s] %(levelname)s - %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  KONSTANTA GLOBAL
# ─────────────────────────────────────────────

BACKEND_URL     = "http://localhost:8000"
BACKEND_TIMEOUT = 5

# Berapa persen (minimal) area bbox APD harus berada di dalam bbox person
# agar APD dianggap "dipakai" oleh person tersebut.
# 0.30 = 30% — toleran, cocok untuk model yang masih belum sempurna.
MIN_OVERLAP = 0.30

# APD wajib — memicu violation jika tidak ada
REQUIRED_PPE = ["helmet", "vest", "boots"]

# APD opsional — dicek dan ditampilkan tapi tidak memicu violation
OPTIONAL_PPE = ["gloves"]

# Semua kelas APD
ALL_PPE_CLASSES = REQUIRED_PPE + OPTIONAL_PPE

COMPLIANT_CLASSES = {"helmet", "vest", "boots", "gloves", "person"}
VIOLATION_CLASSES = {"no_helmet", "no_vest", "no_safety_boot"}

VIOLATION_RULES: Dict[str, dict] = {
    "no_helmet": {
        "description": "Pekerja tidak menggunakan helm safety",
        "severity":    "HIGH",
        "cooldown":    15,
        "min_conf":    0.35,
    },
    "no_vest": {
        "description": "Pekerja tidak menggunakan rompi safety",
        "severity":    "HIGH",
        "cooldown":    15,
        "min_conf":    0.35,
    },
    "no_safety_boot": {
        "description": "Pekerja tidak menggunakan sepatu safety",
        "severity":    "MEDIUM",
        "cooldown":    30,
        "min_conf":    0.35,
    },
}

APD_REQUIREMENTS: Dict[str, str] = {
    "no_helmet":      "helmet",
    "no_vest":        "vest",
    "no_safety_boot": "boots",
}


# ─────────────────────────────────────────────
#  DATA CLASSES
# ─────────────────────────────────────────────

@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox:       tuple   # (x1, y1, x2, y2) piksel integer


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
#  UTILITAS BBOX
# ─────────────────────────────────────────────

def _overlap_ratio(bbox_ppe: tuple, bbox_person: tuple) -> float:
    """
    Hitung rasio: (luas irisan bbox_ppe ∩ bbox_person) / (luas bbox_ppe).

    Menggunakan luas APD sebagai penyebut (bukan union) karena:
    - Bbox person selalu lebih besar dari bbox APD.
    - Kita ingin tahu "berapa persen APD ini ada di dalam person",
      bukan seberapa besar overlap relatif terhadap keduanya.

    Return 0.0 jika tidak ada overlap atau bbox tidak valid.
    """
    ax1, ay1, ax2, ay2 = bbox_ppe
    bx1, by1, bx2, by2 = bbox_person

    ix1 = max(ax1, bx1);  iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2);  iy2 = min(ay2, by2)

    inter_w = max(0, ix2 - ix1)
    inter_h = max(0, iy2 - iy1)
    inter   = float(inter_w * inter_h)

    ppe_area = float(max(0, ax2 - ax1) * max(0, ay2 - ay1))
    if ppe_area <= 0:
        return 0.0

    return inter / ppe_area


# ─────────────────────────────────────────────
#  FUNGSI VALIDASI APD
# ─────────────────────────────────────────────

def person_has_ppe(
    person_bbox:    tuple,
    all_detections: List[Detection],
    ppe_class:      str,
    frame_height:   Optional[int] = None,   # tidak dipakai, untuk kompatibilitas
) -> bool:
    """
    Cek apakah person memiliki APD tertentu berdasarkan overlap bbox.

    APD dianggap "milik" person jika overlap ratio >= MIN_OVERLAP (30%).
    Tidak ada filter posisi anatomis — ini sengaja agar toleran terhadap
    model yang masih dalam pengembangan.

    Args:
        person_bbox    : (x1, y1, x2, y2) bbox orang
        all_detections : semua Detection di frame
        ppe_class      : "helmet", "vest", "boots", atau "gloves"
        frame_height   : tidak dipakai (dipertahankan untuk kompatibilitas API)

    Returns:
        True jika ditemukan APD dengan overlap >= MIN_OVERLAP
    """
    for d in all_detections:
        if d.class_name != ppe_class:
            continue
        if _overlap_ratio(d.bbox, person_bbox) >= MIN_OVERLAP:
            return True
    return False


def get_person_ppe_dict(
    person_det:     Detection,
    all_detections: List[Detection],
    frame_height:   Optional[int] = None,
) -> dict:
    """
    Kembalikan status semua APD untuk satu person sebagai dict.
    Dipakai oleh inference.py untuk visualisasi label dan warna bbox.

    Returns:
        {
            "helmet": True/False,
            "vest":   True/False,
            "boots":  True/False,
            "gloves": True/False,
        }
    """
    ppe_dets = [d for d in all_detections if d.class_name != "person"]
    return {
        ppe: person_has_ppe(person_det.bbox, ppe_dets, ppe, frame_height)
        for ppe in ALL_PPE_CLASSES
    }


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class ViolationLogic:

    def __init__(
        self,
        camera_id:        str           = "CAM_01",
        output_dir:       str           = "violation_output",
        save_screenshots: bool          = True,
        log_to_file:      bool          = True,
        backend_url:      Optional[str] = BACKEND_URL,
    ):
        self.camera_id        = camera_id
        self.save_screenshots = save_screenshots
        self.log_to_file      = log_to_file
        self.backend_url      = backend_url
        self.output_dir       = Path(output_dir)
        self.screenshot_dir   = self.output_dir / "screenshots"

        if save_screenshots:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        if log_to_file:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_file             = self.output_dir / "violations.jsonl"
        self._last_event_time: Dict[str, float] = {}
        self.stats = {
            "total_events":      0,
            "events_per_type":   {v: 0 for v in VIOLATION_RULES},
            "sent_to_backend":   0,
            "failed_to_backend": 0,
            "frames_processed":  0,
        }

        backend_str = f"→ {backend_url}" if backend_url else "→ OFF"
        logger.info(f"ViolationLogic aktif | cam={camera_id} | backend={backend_str}")

    def process(
        self,
        detections:   List[Detection],
        frame,
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        """
        Proses satu frame: deteksi pelanggaran, buat ViolationEvent.
        Return list event yang terjadi di frame ini (bisa kosong).
        """
        self.stats["frames_processed"] += 1
        events = []

        frame_height: Optional[int] = None
        if frame is not None and hasattr(frame, "shape"):
            frame_height = frame.shape[0]

        person_dets = [d for d in detections if d.class_name == "person"]
        ppe_dets    = [d for d in detections if d.class_name != "person"]

        if not person_dets:
            return events

        for vtype, rule in VIOLATION_RULES.items():
            ppe_class = APD_REQUIREMENTS[vtype]

            if self._in_cooldown(vtype, rule["cooldown"]):
                continue

            violating_person = None
            for person in person_dets:
                if person.confidence < rule["min_conf"]:
                    continue
                if not person_has_ppe(person.bbox, ppe_dets, ppe_class, frame_height):
                    violating_person = person
                    break

            if violating_person is None:
                continue

            event = self._create_event(vtype, rule, violating_person, frame, frame_number)
            events.append(event)

            self._last_event_time[vtype] = time.time()
            self.stats["total_events"]            += 1
            self.stats["events_per_type"][vtype]  += 1

            logger.warning(
                f"PELANGGARAN | {vtype:20s} | "
                f"severity={rule['severity']:6s} | "
                f"conf={violating_person.confidence:.2f} | "
                f"frame={frame_number}"
            )

            if self.log_to_file:
                self._write_log(event)
            if self.backend_url:
                self._send_to_backend(event)

        return events

    def get_frame_status(
        self,
        detections:   List[Detection],
        frame_height: Optional[int] = None,
    ) -> dict:
        """
        Status APD level frame untuk panel overlay kanan atas.

        Returns:
            {
                "helmet":      "COMPLIANT" | "VIOLATION" | "UNKNOWN",
                "vest":        "COMPLIANT" | "VIOLATION" | "UNKNOWN",
                "safety_boot": "COMPLIANT" | "VIOLATION" | "UNKNOWN",
            }
        """
        person_dets = [d for d in detections if d.class_name == "person"]
        ppe_dets    = [d for d in detections if d.class_name != "person"]

        apd_map = {
            "helmet":      "helmet",
            "vest":        "vest",
            "safety_boot": "boots",
        }

        if not person_dets:
            return {k: "UNKNOWN" for k in apd_map}

        valid_persons = [p for p in person_dets if p.confidence >= 0.35]
        if not valid_persons:
            return {k: "UNKNOWN" for k in apd_map}

        status = {}
        for panel_key, ppe_class in apd_map.items():
            any_violation = any(
                not person_has_ppe(p.bbox, ppe_dets, ppe_class)
                for p in valid_persons
            )
            any_compliant = any(
                person_has_ppe(p.bbox, ppe_dets, ppe_class)
                for p in valid_persons
            )

            if any_violation:
                status[panel_key] = "VIOLATION"
            elif any_compliant:
                status[panel_key] = "COMPLIANT"
            else:
                status[panel_key] = "UNKNOWN"

        return status

    # ── INTERNAL ──────────────────────────────

    def _in_cooldown(self, vtype: str, cooldown: float) -> bool:
        return (time.time() - self._last_event_time.get(vtype, 0.0)) < cooldown

    def _create_event(self, vtype, rule, person_det, frame, frame_number) -> ViolationEvent:
        now      = time.time()
        dt       = datetime.fromtimestamp(now, tz=timezone.utc)
        event_id = f"{self.camera_id}_{frame_number}_{vtype}_{int(now)}"

        frame_path = None
        if self.save_screenshots and frame is not None:
            frame_path = self._save_screenshot(frame, person_det, dt, vtype)

        return ViolationEvent(
            event_id       = event_id,
            timestamp      = dt.isoformat(),
            camera_id      = self.camera_id,
            violation_type = vtype,
            description    = rule["description"],
            severity       = rule["severity"],
            confidence     = round(person_det.confidence, 4),
            bbox           = {
                "x1": person_det.bbox[0], "y1": person_det.bbox[1],
                "x2": person_det.bbox[2], "y2": person_det.bbox[3],
            },
            frame_number   = frame_number,
            frame_path     = frame_path,
        )

    def _save_screenshot(self, frame, person_det, dt, vtype) -> str:
        shot = frame.copy()
        x1, y1, x2, y2 = person_det.bbox
        cv2.rectangle(shot, (x1, y1), (x2, y2), (0, 0, 220), 3)
        cv2.rectangle(shot, (0, 0), (shot.shape[1], 62), (0, 0, 175), -1)
        cv2.putText(
            shot,
            f"VIOLATION: {vtype.upper().replace('_', ' ')}",
            (10, 38),
            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA,
        )
        cv2.putText(
            shot,
            dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            (10, 58),
            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (200, 200, 200), 1, cv2.LINE_AA,
        )
        cv2.putText(
            shot,
            f"conf: {person_det.confidence:.2f}",
            (x1, max(y1 - 8, 70)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 220), 2, cv2.LINE_AA,
        )
        filename = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path     = self.screenshot_dir / filename
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return str(path)

    def _write_log(self, event: ViolationEvent):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    def _send_to_backend(self, event: ViolationEvent):
        url = f"{self.backend_url}/violations"
        try:
            r = requests.post(
                url,
                json    = event.to_backend_payload(),
                timeout = BACKEND_TIMEOUT,
                headers = {"Content-Type": "application/json"},
            )
            if r.status_code == 201:
                event.sent_to_backend = True
                self.stats["sent_to_backend"] += 1
                logger.info(
                    f"  Backend OK | id={r.json().get('id')} | "
                    f"type={event.violation_type}"
                )
            else:
                self.stats["failed_to_backend"] += 1
                logger.warning(f"  Backend {r.status_code} | {r.text[:100]}")
        except requests.exceptions.ConnectionError:
            self.stats["failed_to_backend"] += 1
            logger.warning(f"  Backend tidak bisa dihubungi ({url}).")
        except requests.exceptions.Timeout:
            self.stats["failed_to_backend"] += 1
            logger.warning(f"  Backend timeout ({BACKEND_TIMEOUT}s).")
        except Exception as e:
            self.stats["failed_to_backend"] += 1
            logger.error(f"  Error kirim backend: {e}")

    def print_session_summary(self):
        sep = "=" * 55
        print(f"\n{sep}")
        print(f"  RINGKASAN SESI PELANGGARAN")
        print(f"{sep}")
        print(f"  Camera ID           : {self.camera_id}")
        print(f"  Frame diproses      : {self.stats['frames_processed']}")
        print(f"  Total event         : {self.stats['total_events']}")
        print(f"  Terkirim ke backend : {self.stats['sent_to_backend']}")
        print(f"  Gagal ke backend    : {self.stats['failed_to_backend']}")
        print(f"\n  Breakdown per tipe:")
        for vtype, count in self.stats["events_per_type"].items():
            rule   = VIOLATION_RULES[vtype]
            marker = "!!" if count > 0 else "  "
            print(f"    {marker} {vtype:20s}: {count} event  [{rule['severity']}]")
        print(f"\n  Log    : {self.log_file.resolve()}")
        print(f"  Foto   : {self.screenshot_dir.resolve()}")
        print(f"  Backend: {self.backend_url or 'OFF'}")
        print(f"{sep}\n")


# ─────────────────────────────────────────────
#  SELF-TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import numpy as np

    print("\n=== TEST violation_logic.py (overlap-based) ===\n")
    logic = ViolationLogic(
        camera_id   = "CAM_TEST",
        output_dir  = "test_violation_output",
        backend_url = None,
    )
    dummy = np.zeros((480, 640, 3), dtype=np.uint8)

    print("--- TEST 1: person tanpa APD → 3 violation ---")
    logic._last_event_time = {}
    e = logic.process([Detection("person", 0.88, (100, 30, 400, 460))], dummy, 1)
    print(f"  Events: {len(e)} (harusnya 3)")
    for ev in e:
        print(f"    → {ev.violation_type}")

    print("\n--- TEST 2: APD semua overlap cukup → 0 violation ---")
    logic._last_event_time = {}
    e = logic.process([
        Detection("person", 0.91, (100,  30, 400, 460)),
        Detection("helmet", 0.87, (150,  40, 350, 160)),
        Detection("vest",   0.82, (110, 150, 390, 350)),
        Detection("boots",  0.79, (120, 350, 380, 455)),
    ], dummy, 2)
    print(f"  Events: {len(e)} (harusnya 0)")

    print("\n--- TEST 3: APD di luar bbox person → 3 violation ---")
    logic._last_event_time = {}
    e = logic.process([
        Detection("person", 0.88, (300, 200, 600, 460)),
        Detection("helmet", 0.87, (  0,   0, 100, 100)),
        Detection("vest",   0.82, (  0, 100, 100, 300)),
        Detection("boots",  0.79, (  0, 350, 100, 460)),
    ], dummy, 3)
    print(f"  Events: {len(e)} (harusnya 3)")
    for ev in e:
        print(f"    → {ev.violation_type}")

    print("\n--- TEST 4: get_frame_status ---")
    logic._last_event_time = {}
    s = logic.get_frame_status([
        Detection("person", 0.90, (100,  30, 400, 460)),
        Detection("helmet", 0.85, (150,  40, 350, 160)),
    ])
    for apd, st in s.items():
        icon = "OK" if st == "COMPLIANT" else ("!!" if st == "VIOLATION" else "??")
        print(f"  [{icon}] {apd:15s}: {st}")
    print("  (harusnya: helmet=COMPLIANT, vest=VIOLATION, safety_boot=VIOLATION)")

    logic.print_session_summary()