"""
violation_logic.py  [v6.0 — Epson Factory K3 | 5-Class Positive-Only]
=========================================================================
Logika deteksi pelanggaran K3 untuk model bestDevaLatest.pt (5 kelas).

Kelas model AKTUAL (bestDevaLatest.pt):
    0: person        → Deteksi orang
    1: helmet        → APD hadir: helm
    2: safety-vest   → APD hadir: rompi
    3: gloves        → APD hadir: sarung tangan
    4: shoes         → APD hadir: sepatu safety

Normalisasi nama internal:
    "person"       → "Person"
    "safety-vest"  → "vest"
    "shoes"        → "boots"

Strategi Deteksi v6.0 — MODE B ONLY (positive absent):
  Model ini tidak memiliki kelas negatif (no_helmet, dll).
  Deteksi pelanggaran dilakukan dengan mengecek apakah APD positif
  ditemukan secara spasial di sekitar bbox Person.
  Jika APD tidak ditemukan → VIOLATION.

Standard K3 Epson Factory:
  Wajib: Helm, Rompi, Sepatu Safety, Sarung Tangan
  Catatan: Goggle TIDAK ada di model ini — dihapus dari standar
  Partial Person: Sepatu & Sarung Tangan tidak diwajibkan
"""

import cv2
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Tuple

logging.basicConfig(
    level   = logging.INFO,
    format  = "[%(asctime)s] %(levelname)s — %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  NORMALISASI NAMA KELAS MODEL → NAMA INTERNAL
#  Model output name  →  Internal name
# ─────────────────────────────────────────────

# Raw class IDs dari model bestDevaLatest.pt
CLASS_NAMES: Dict[int, str] = {
    0: "Person",   # model: "person"       → normalized
    1: "helmet",   # model: "helmet"       → same
    2: "vest",     # model: "safety-vest"  → normalized
    3: "gloves",   # model: "gloves"       → same
    4: "boots",    # model: "shoes"        → normalized
}

# Mapping dari nama raw model → nama internal
# Digunakan di inference.py saat membaca output YOLO
MODEL_NAME_MAP: Dict[str, str] = {
    "person":      "Person",
    "helmet":      "helmet",
    "safety-vest": "vest",
    "gloves":      "gloves",
    "shoes":       "boots",
}

# Kelas APD positif (internal names)
PPE_POSITIVE_CLASSES = {"helmet", "gloves", "vest", "boots"}

# Tidak ada kelas negatif di model ini
PPE_NEGATIVE_CLASSES: set = set()

# Mapping display untuk UI/log
PPE_DISPLAY_NAMES: Dict[str, str] = {
    "helmet": "Helm",
    "gloves": "Sarung Tangan",
    "vest":   "Rompi",
    "boots":  "Sepatu Safety",
}

# APD wajib sesuai standar Epson Factory K3 (goggle dihapus — tidak ada di model)
REQUIRED_PPE = ["helmet", "vest", "boots", "gloves"]

# APD yang dikecualikan saat person partial (hanya terlihat sebagian)
PARTIAL_EXEMPT_PPE = {"boots", "gloves"}

ALL_PPE = REQUIRED_PPE


# ─────────────────────────────────────────────
#  PARAMETER SPASIAL
# ─────────────────────────────────────────────

# Zona Y relatif terhadap tinggi bbox Person (top=0.0, bottom=1.0)
Y_ZONES: Dict[str, Tuple[float, float]] = {
    "helmet": (0.00, 0.40),   # kepala
    "vest":   (0.20, 0.80),   # badan
    "gloves": (0.35, 1.00),   # tangan ke bawah
    "boots":  (0.60, 1.00),   # kaki
}

MIN_OVERLAP:          float = 0.20   # minimum IoU untuk fallback detection
PARTIAL_PERSON_RATIO: float = 0.40   # bbox person < 40% tinggi frame = partial
MIN_PERSON_CONF:      float = 0.30
MIN_PPE_CONF:         float = 0.25

# Panel labels untuk overlay UI
PANEL_LABELS: Dict[str, str] = {
    "helmet": "Helm    ",
    "vest":   "Rompi   ",
    "boots":  "Sepatu  ",
    "gloves": "Gloves  ",
}

# ── Warna BGR ──
VIOLATION_COLOR = (0,   0, 255)     # merah cerah
COMPLIANT_COLOR = (0, 200,   0)     # hijau
UNKNOWN_COLOR   = (130, 130, 130)   # abu-abu
WARNING_COLOR   = (0,  165, 255)    # oranye (partial)

BACKEND_URL     = "http://localhost:8000"
BACKEND_TIMEOUT = 5


# ─────────────────────────────────────────────
#  VIOLATION RULES — Epson K3 Standard (4 APD)
# ─────────────────────────────────────────────

VIOLATION_RULES: Dict[str, dict] = {
    "no_helmet": {
        "ppe_class":   "helmet",
        "description": "Pekerja tidak menggunakan helm safety",
        "severity":    "HIGH",
        "cooldown":    12,
    },
    "no_vest": {
        "ppe_class":   "vest",
        "description": "Pekerja tidak menggunakan rompi safety (vest)",
        "severity":    "HIGH",
        "cooldown":    12,
    },
    "no_boots": {
        "ppe_class":   "boots",
        "description": "Pekerja tidak menggunakan sepatu safety",
        "severity":    "HIGH",
        "cooldown":    20,
    },
    "no_gloves": {
        "ppe_class":   "gloves",
        "description": "Pekerja tidak menggunakan sarung tangan safety",
        "severity":    "MEDIUM",
        "cooldown":    20,
    },
}


# ─────────────────────────────────────────────
#  DATA CLASSES
# ─────────────────────────────────────────────

@dataclass
class Detection:
    """
    Satu deteksi dari YOLO.
    class_name menggunakan nama INTERNAL (sudah dinormalisasi).
    bbox dalam koordinat frame ASLI (sudah di-scale).
    """
    class_name: str
    confidence: float
    bbox:       tuple   # (x1, y1, x2, y2) koordinat frame asli


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
    detection_mode:  str           # selalu "positive_absent" di v6.0
    sent_to_backend: bool = False

    def to_payload(self) -> dict:
        return {
            "violation_type":  self.violation_type,
            "confidence":      self.confidence,
            "timestamp":       self.timestamp,
            "frame_path":      self.frame_path,
            "camera_id":       self.camera_id,
            "severity":        self.severity,
            "detection_mode":  self.detection_mode,
        }

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ─────────────────────────────────────────────
#  UTILITAS BBOX
# ─────────────────────────────────────────────

def bbox_area(bbox: tuple) -> float:
    x1, y1, x2, y2 = bbox
    return float(max(0, x2 - x1) * max(0, y2 - y1))


def overlap_ratio(bbox_ppe: tuple, bbox_person: tuple) -> float:
    """Rasio: area(ppe ∩ person) / area(ppe)."""
    ax1, ay1, ax2, ay2 = bbox_ppe
    bx1, by1, bx2, by2 = bbox_person
    inter = float(
        max(0, min(ax2, bx2) - max(ax1, bx1)) *
        max(0, min(ay2, by2) - max(ay1, by1))
    )
    area = bbox_area(bbox_ppe)
    return (inter / area) if area > 0 else 0.0


def bbox_center(bbox: tuple) -> Tuple[float, float]:
    """Titik tengah bbox → (cx, cy)."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def is_partial_person(person_bbox: tuple, frame_height: int) -> bool:
    """True jika bbox person < PARTIAL_PERSON_RATIO dari tinggi frame."""
    if frame_height <= 0:
        return False
    _, y1, _, y2 = person_bbox
    return ((y2 - y1) / frame_height) < PARTIAL_PERSON_RATIO


# ─────────────────────────────────────────────
#  VALIDASI SPASIAL — PPE POSITIF (Mode B Only)
# ─────────────────────────────────────────────

def person_has_ppe_positive(
    person_bbox:    tuple,
    ppe_detections: List[Detection],
    ppe_class:      str,
    frame_height:   Optional[int] = None,
) -> bool:
    """
    Cek apakah ada deteksi APD positif yang secara spasial valid
    di dalam bbox person.

    Dua tahap validasi:
      1. Center APD berada dalam bbox person AND dalam zona Y yang sesuai
      2. Fallback: overlap ratio >= MIN_OVERLAP (untuk bbox terpotong tepi frame)
    """
    px1, py1, px2, py2 = person_bbox
    ph = py2 - py1
    if ph <= 0:
        return False

    y_lo, y_hi = Y_ZONES.get(ppe_class, (0.0, 1.0))
    zone_y_min = py1 + y_lo * ph
    zone_y_max = py1 + y_hi * ph

    for det in ppe_detections:
        if det.class_name != ppe_class:
            continue
        if det.confidence < MIN_PPE_CONF:
            continue

        cx, cy = bbox_center(det.bbox)

        # Tahap 1: center berada dalam bbox + zona Y
        if px1 <= cx <= px2 and py1 <= cy <= py2:
            if zone_y_min <= cy <= zone_y_max:
                return True
            continue

        # Tahap 2: overlap fallback (bbox terpotong tepi frame)
        if (overlap_ratio(det.bbox, person_bbox) >= MIN_OVERLAP
                and zone_y_min <= cy <= zone_y_max):
            return True

    return False


def get_person_ppe_dict(
    person_det:     Detection,
    all_detections: List[Detection],
    frame_height:   Optional[int] = None,
) -> Dict[str, bool]:
    """
    Status semua APD untuk satu Person (Mode B: positive absent only).

    Return: {ppe_class: True (patuh) / False (langgar)}
    Partial person: boots dan gloves otomatis True.
    """
    ppe_dets = [d for d in all_detections if d.class_name in PPE_POSITIVE_CLASSES]

    result = {}
    for ppe in ALL_PPE:
        result[ppe] = person_has_ppe_positive(
            person_bbox    = person_det.bbox,
            ppe_detections = ppe_dets,
            ppe_class      = ppe,
            frame_height   = frame_height,
        )

    # Partial person exemption
    if frame_height and is_partial_person(person_det.bbox, frame_height):
        for exempt in PARTIAL_EXEMPT_PPE:
            result[exempt] = True

    return result


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class ViolationLogic:

    def __init__(
        self,
        camera_id:        str           = "EPSON_CAM_01",
        output_dir:       str           = "violation_output",
        save_screenshots: bool          = True,
        log_to_file:      bool          = True,
        backend_url:      Optional[str] = "http://localhost:8000",
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

        self.log_file                     = self.output_dir / "violations.jsonl"
        self._last_event_time: Dict[str, float] = {}
        self.stats = {
            "total_events":     0,
            "per_type":         {k: 0 for k in VIOLATION_RULES},
            "sent_backend":     0,
            "fail_backend":     0,
            "frames_processed": 0,
            "pos_absent_hits":  0,   # semua deteksi via positive absent (Mode B)
        }
        logger.info(
            f"ViolationLogic v6.0 Epson K3 | cam={camera_id} | "
            f"backend={'ON → ' + backend_url if backend_url else 'OFF'} | "
            f"model=5-class positive-only | required_ppe={len(REQUIRED_PPE)}"
        )

    def process(
        self,
        detections:   List[Detection],
        frame,
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        """
        Proses satu frame, return list ViolationEvent.
        Mode B only: cek apakah APD positif absen di sekitar Person.
        """
        self.stats["frames_processed"] += 1
        events: List[ViolationEvent] = []

        fh          = frame.shape[0] if hasattr(frame, "shape") else None
        person_dets = [d for d in detections if d.class_name == "Person"]
        ppe_dets    = [d for d in detections if d.class_name in PPE_POSITIVE_CLASSES]

        if not person_dets:
            return events

        for person in person_dets:
            if person.confidence < MIN_PERSON_CONF:
                continue

            partial = bool(fh and is_partial_person(person.bbox, fh))

            for vtype, rule in VIOLATION_RULES.items():
                # Skip APD yang dikecualikan saat partial
                if partial and rule["ppe_class"] in PARTIAL_EXEMPT_PPE:
                    continue
                if self._in_cooldown(vtype, rule["cooldown"]):
                    continue

                has_pos = person_has_ppe_positive(
                    person_bbox    = person.bbox,
                    ppe_detections = ppe_dets,
                    ppe_class      = rule["ppe_class"],
                    frame_height   = fh,
                )

                if not has_pos:
                    ev = self._make_event(
                        vtype, rule, person, frame, frame_number,
                        detect_mode="positive_absent"
                    )
                    events.append(ev)
                    self._last_event_time[vtype]  = time.time()
                    self.stats["total_events"]    += 1
                    self.stats["per_type"][vtype] += 1
                    self.stats["pos_absent_hits"] += 1

                    logger.warning(
                        f"PELANGGARAN | {vtype:12s} | {rule['severity']:6s} | "
                        f"mode=pos_absent | "
                        f"conf={person.confidence:.2f}"
                        f"{' [partial]' if partial else ''} | fr={frame_number}"
                    )
                    if self.log_to_file:
                        self._write_log(ev)
                    if self.backend_url:
                        self._send_backend(ev)

        return events

    def get_frame_status(
        self,
        detections:   List[Detection],
        frame_height: Optional[int] = None,
    ) -> Dict[str, str]:
        """
        Status panel overlay kanan atas.
        Return: {ppe_class: "COMPLIANT"|"VIOLATION"|"UNKNOWN"}
        """
        person_dets = [d for d in detections if d.class_name == "Person"]

        if not person_dets:
            return {k: "UNKNOWN" for k in REQUIRED_PPE}

        valid_persons = [p for p in person_dets if p.confidence >= MIN_PERSON_CONF]
        if not valid_persons:
            return {k: "UNKNOWN" for k in REQUIRED_PPE}

        status: Dict[str, str] = {}
        for ppe_cls in REQUIRED_PPE:
            compliant = False
            violation = False
            for p in valid_persons:
                if ppe_cls in PARTIAL_EXEMPT_PPE and frame_height:
                    if is_partial_person(p.bbox, frame_height):
                        compliant = True
                        continue

                ppe_dict = get_person_ppe_dict(p, detections, frame_height)
                if ppe_dict.get(ppe_cls, False):
                    compliant = True
                else:
                    violation = True

            status[ppe_cls] = (
                "VIOLATION" if violation else
                "COMPLIANT" if compliant else
                "UNKNOWN"
            )
        return status

    # ── internal ─────────────────────────────

    def _in_cooldown(self, vtype: str, cooldown: float) -> bool:
        return (time.time() - self._last_event_time.get(vtype, 0.0)) < cooldown

    def _make_event(
        self, vtype, rule, person, frame, frame_number, detect_mode
    ) -> ViolationEvent:
        now  = time.time()
        dt   = datetime.fromtimestamp(now, tz=timezone.utc)
        x1, y1, x2, y2 = person.bbox
        fpath = None
        if self.save_screenshots and frame is not None:
            fpath = self._save_screenshot(frame, person.bbox, dt, vtype)
        return ViolationEvent(
            event_id       = f"{self.camera_id}_{frame_number}_{vtype}_{int(now)}",
            timestamp      = dt.isoformat(),
            camera_id      = self.camera_id,
            violation_type = vtype,
            description    = rule["description"],
            severity       = rule["severity"],
            confidence     = round(person.confidence, 4),
            bbox           = {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
            frame_number   = frame_number,
            frame_path     = fpath,
            detection_mode = detect_mode,
        )

    def _save_screenshot(self, frame, bbox, dt, vtype) -> str:
        shot = frame.copy()
        x1, y1, x2, y2 = bbox
        cv2.rectangle(shot, (x1, y1), (x2, y2), VIOLATION_COLOR, 3)
        header_h = 70
        cv2.rectangle(shot, (0, 0), (shot.shape[1], header_h), (0, 0, 140), -1)
        cv2.putText(
            shot,
            f"EPSON K3 VIOLATION: {vtype.upper().replace('_', ' ')}",
            (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA
        )
        cv2.putText(
            shot,
            dt.strftime("%Y-%m-%d  %H:%M:%S UTC  |  " + self.camera_id),
            (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1, cv2.LINE_AA
        )
        fname = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path  = self.screenshot_dir / fname
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return str(path)

    def _write_log(self, ev: ViolationEvent):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(ev.to_json() + "\n")

    def _send_backend(self, ev: ViolationEvent):
        try:
            r = requests.post(
                f"{self.backend_url}/violations",
                json    = ev.to_payload(),
                timeout = BACKEND_TIMEOUT,
                headers = {"Content-Type": "application/json"},
            )
            if r.status_code == 201:
                ev.sent_to_backend = True
                self.stats["sent_backend"] += 1
            else:
                self.stats["fail_backend"] += 1
                logger.warning(f"Backend {r.status_code}: {r.text[:80]}")
        except Exception as e:
            self.stats["fail_backend"] += 1
            logger.warning(f"Backend error: {e}")

    def print_summary(self):
        sep = "=" * 62
        print(f"\n{sep}\n  RINGKASAN SESI  [ViolationLogic v6.0 — Epson K3 | 5-Class]")
        print(sep)
        print(f"  Camera          : {self.camera_id}")
        print(f"  Frames diproses : {self.stats['frames_processed']}")
        print(f"  Total pelanggaran: {self.stats['total_events']}")
        print(f"    via pos.absent : {self.stats['pos_absent_hits']}")
        print(f"\n  Detail per tipe:")
        for vtype, n in self.stats["per_type"].items():
            sev = VIOLATION_RULES[vtype]["severity"]
            bar = "█" * min(n, 20) if n > 0 else "—"
            print(f"    {'!!' if n else '  '} {vtype:12s}: {n:>4}x  [{sev:6s}]  {bar}")
        print(f"\n  Backend terkirim: {self.stats['sent_backend']}")
        print(f"  Backend gagal   : {self.stats['fail_backend']}")
        print(f"  Log file        : {self.log_file.resolve()}")
        print(sep)


# ─────────────────────────────────────────────
#  SELF TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import numpy as np
    print("\n=== TEST violation_logic.py v6.0 — Epson K3 | 5-Class ===\n")
    H, W  = 480, 640
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    logic = ViolationLogic(
        camera_id   = "EPSON_TEST",
        output_dir  = "test_out_v6",
        backend_url = None,
    )

    print("TEST 1 — bbox_center() benar")
    cx, cy = bbox_center((100, 50, 300, 200))
    assert cx == 200.0 and cy == 125.0, "FAIL"
    print(f"  ✓ bbox_center → ({cx}, {cy})")

    print("\nTEST 2 — Semua APD lengkap → 0 event")
    logic._last_event_time = {}
    ev = logic.process([
        Detection("Person", 0.92, (100,  30, 400, 460)),
        Detection("helmet", 0.88, (150,  40, 360, 130)),
        Detection("vest",   0.85, (110, 150, 390, 320)),
        Detection("gloves", 0.82, (110, 210, 230, 300)),
        Detection("boots",  0.80, (120, 360, 380, 455)),
    ], frame, 1)
    print(f"  Events: {len(ev)}  (expected 0)")
    assert len(ev) == 0, f"FAIL: {[e.violation_type for e in ev]}"
    print("  ✓ PASS")

    print("\nTEST 3 — Helm tidak ada → violation no_helmet")
    logic._last_event_time = {}
    ev = logic.process([
        Detection("Person", 0.91, (100, 30, 400, 460)),
        Detection("vest",   0.85, (110, 150, 390, 320)),
        Detection("gloves", 0.82, (110, 210, 230, 300)),
        Detection("boots",  0.80, (120, 360, 380, 455)),
    ], frame, 2)
    types = [e.violation_type for e in ev]
    print(f"  Events: {types}  (expected ['no_helmet'])")
    assert "no_helmet" in types, f"FAIL: {types}"
    assert ev[0].detection_mode == "positive_absent"
    print(f"  ✓ PASS — mode={ev[0].detection_mode}")

    print("\nTEST 4 — Partial person → boots & gloves dikecualikan")
    logic._last_event_time = {}
    ev = logic.process([
        Detection("Person", 0.91, (100,  20, 400, 110)),   # h=90 < 40% dari 480
        Detection("helmet", 0.88, (150,  25, 360,  75)),
        Detection("vest",   0.85, (110,  55, 390, 105)),
    ], frame, 3)
    types = [e.violation_type for e in ev]
    assert "no_boots"  not in types, f"boots tidak boleh ada: {types}"
    assert "no_gloves" not in types, f"gloves tidak boleh ada: {types}"
    print(f"  ✓ PASS — events={types}")

    print("\nTEST 5 — get_frame_status() helm hilang → VIOLATION")
    logic._last_event_time = {}
    status = logic.get_frame_status([
        Detection("Person", 0.91, (100, 30, 400, 460)),
        Detection("vest",   0.85, (110, 150, 390, 320)),
        Detection("gloves", 0.82, (110, 210, 230, 300)),
        Detection("boots",  0.80, (120, 360, 380, 455)),
    ], frame_height=H)
    print(f"  helmet : {status.get('helmet')}  (expected VIOLATION)")
    print(f"  vest   : {status.get('vest')}    (expected COMPLIANT)")
    assert status["helmet"] == "VIOLATION"
    assert status["vest"]   == "COMPLIANT"
    print("  ✓ PASS")

    print("\nTEST 6 — MODEL_NAME_MAP normalisasi")
    raw_names = ["person", "safety-vest", "shoes", "helmet", "gloves"]
    normalized = [MODEL_NAME_MAP[n] for n in raw_names]
    expected   = ["Person", "vest", "boots", "helmet", "gloves"]
    assert normalized == expected, f"FAIL: {normalized}"
    print(f"  ✓ PASS — {dict(zip(raw_names, normalized))}")

    print("\n✅ Semua test PASSED — v6.0 Epson K3 | 5-Class Positive-Only")
    logic.print_summary()