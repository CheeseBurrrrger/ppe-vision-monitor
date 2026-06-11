"""
violation_logic.py  [v5.0 — Epson Factory K3 | Model-Aware Detection]
========================================================================
Logika deteksi pelanggaran K3 untuk model YOLOv11 best.pt (11 kelas).

Kelas model best.pt (AKTUAL hasil inspect):
    0: helmet        → APD hadir: helm
    1: gloves        → APD hadir: sarung tangan
    2: vest          → APD hadir: rompi
    3: boots         → APD hadir: sepatu safety
    4: goggles       → APD hadir: kacamata pelindung
    5: none          → Tidak ada APD terdeteksi (area kosong)
    6: Person        → Deteksi orang
    7: no_helmet     → LANGSUNG: orang tanpa helm (negative class)
    8: no_goggle     → LANGSUNG: orang tanpa goggle (negative class)
    9: no_gloves     → LANGSUNG: orang tanpa sarung tangan (negative class)
   10: no_boots      → LANGSUNG: orang tanpa sepatu (negative class)

Strategi Deteksi v5.0 — DUAL MODE (lebih akurat):
  MODE A (PRIMER)  : Kelas negatif (no_helmet, no_goggle, dll) langsung = LANGGAR
  MODE B (SEKUNDER): Kelas positif tidak ditemukan di sekitar Person = LANGGAR
  Jika salah satu mode mendeteksi pelanggaran → status VIOLATION

Standard K3 Epson Factory:
  Wajib: Helm, Rompi, Sepatu Safety, Goggle, Sarung Tangan
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
#  KELAS MODEL — 11 kelas dari best.pt (v5.0)
# ─────────────────────────────────────────────

CLASS_NAMES: Dict[int, str] = {
    0:  "helmet",
    1:  "gloves",
    2:  "vest",
    3:  "boots",
    4:  "goggles",
    5:  "none",
    6:  "Person",
    7:  "no_helmet",
    8:  "no_goggle",
    9:  "no_gloves",
    10: "no_boots",
}

PPE_POSITIVE_CLASSES = {"helmet", "gloves", "vest", "boots", "goggles"}

PPE_NEGATIVE_CLASSES = {"no_helmet", "no_goggle", "no_gloves", "no_boots"}

NEGATIVE_TO_POSITIVE: Dict[str, str] = {
    "no_helmet": "helmet",
    "no_goggle": "goggles",
    "no_gloves": "gloves",
    "no_boots":  "boots",
}

PPE_DISPLAY_NAMES: Dict[str, str] = {
    "helmet":  "Helm",
    "gloves":  "Sarung Tangan",
    "vest":    "Rompi",
    "boots":   "Sepatu Safety",
    "goggles": "Goggle",
}

REQUIRED_PPE = ["helmet", "vest", "boots", "goggles", "gloves"]

# APD yang dikecualikan saat person partial (hanya terlihat sebagian)
PARTIAL_EXEMPT_PPE = {"boots", "gloves"}

ALL_PPE = REQUIRED_PPE


# ─────────────────────────────────────────────
#  PARAMETER SPASIAL
# ─────────────────────────────────────────────

# Zona Y relatif terhadap tinggi bbox Person (top=0.0, bottom=1.0)
Y_ZONES: Dict[str, Tuple[float, float]] = {
    "helmet":  (0.00, 0.40),
    "goggles": (0.00, 0.40),
    "vest":    (0.20, 0.80),
    "gloves":  (0.35, 1.00),
    "boots":   (0.60, 1.00),
    "no_helmet": (0.00, 0.55),
    "no_goggle": (0.00, 0.55),
    "no_gloves": (0.30, 1.00),
    "no_boots":  (0.55, 1.00),
}

MIN_OVERLAP:          float = 0.20   # minimum IoU untuk fallback detection
PARTIAL_PERSON_RATIO: float = 0.40   # bbox person < 40% tinggi frame = partial
MIN_PERSON_CONF:      float = 0.30
MIN_PPE_CONF:         float = 0.25   # lebih rendah untuk negative class
MIN_NEG_CONF:         float = 0.30   # minimum conf untuk negative class trigger

PANEL_LABELS: Dict[str, str] = {
    "helmet":  "Helm    ",
    "vest":    "Rompi   ",
    "boots":   "Sepatu  ",
    "goggles": "Goggle  ",
    "gloves":  "Gloves  ",
}

# ── Warna BGR ──
VIOLATION_COLOR  = (0,   0, 255)     # merah cerah
COMPLIANT_COLOR  = (0, 200,   0)     # hijau
UNKNOWN_COLOR    = (130, 130, 130)   # abu-abu
WARNING_COLOR    = (0,  165, 255)    # oranye (partial)

BACKEND_URL     = "http://localhost:8000"
BACKEND_TIMEOUT = 5


# ─────────────────────────────────────────────
#  VIOLATION RULES — Epson K3 Standard
# ─────────────────────────────────────────────

VIOLATION_RULES: Dict[str, dict] = {
    "no_helmet": {
        "ppe_class":   "helmet",
        "neg_class":   "no_helmet",
        "description": "Pekerja tidak menggunakan helm safety",
        "severity":    "HIGH",
        "cooldown":    12,
    },
    "no_vest": {
        "ppe_class":   "vest",
        "neg_class":   None,
        "description": "Pekerja tidak menggunakan rompi safety (vest)",
        "severity":    "HIGH",
        "cooldown":    12,
    },
    "no_boots": {
        "ppe_class":   "boots",
        "neg_class":   "no_boots",
        "description": "Pekerja tidak menggunakan sepatu safety",
        "severity":    "HIGH",
        "cooldown":    20,
    },
    "no_goggles": {
        "ppe_class":   "goggles",
        "neg_class":   "no_goggle",
        "description": "Pekerja tidak menggunakan kacamata pelindung (goggle)",
        "severity":    "HIGH",
        "cooldown":    12,
    },
    "no_gloves": {
        "ppe_class":   "gloves",
        "neg_class":   "no_gloves",
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
    bbox WAJIB dalam koordinat frame ASLI (sudah di-scale).
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
    detection_mode:  str           # "negative_class" atau "positive_absent"
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
#  VALIDASI SPASIAL — PPE POSITIF
# ─────────────────────────────────────────────

def person_has_ppe_positive(
    person_bbox:    tuple,
    ppe_detections: List[Detection],
    ppe_class:      str,
    frame_height:   Optional[int] = None,
) -> bool:
    """
    Cek apakah ada deteksi APD positif (helmet, vest, dll) yang
    secara spasial valid di dalam bbox person.
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


def person_has_negative_ppe(
    person_bbox:    tuple,
    all_detections: List[Detection],
    neg_class:      str,
) -> bool:
    """
    Cek apakah ada kelas negatif (no_helmet, no_goggle, dll) yang
    secara spasial berada di dalam/dekat bbox person.
    Ini MODE PRIMER — lebih cepat dan akurat.
    """
    if neg_class is None:
        return False

    px1, py1, px2, py2 = person_bbox
    ph = py2 - py1
    if ph <= 0:
        return False

    y_lo, y_hi = Y_ZONES.get(neg_class, (0.0, 1.0))
    zone_y_min = py1 + y_lo * ph
    zone_y_max = py1 + y_hi * ph

    for det in all_detections:
        if det.class_name != neg_class:
            continue
        if det.confidence < MIN_NEG_CONF:
            continue

        cx, cy = bbox_center(det.bbox)

        # Check spasial — center di dalam bbox person
        if px1 <= cx <= px2 and py1 <= cy <= py2:
            if zone_y_min <= cy <= zone_y_max:
                return True

        # Fallback overlap
        if (overlap_ratio(det.bbox, person_bbox) >= MIN_OVERLAP
                and zone_y_min <= cy <= zone_y_max):
            return True

    return False


def get_person_ppe_dict(
    person_det:     Detection,
    all_detections: List[Detection],
    frame_height:   Optional[int] = None,
    required_ppe:   Optional[List[str]] = None,
) -> Dict[str, bool]:
    """
    Status semua APD untuk satu Person.
    Menggunakan dual-mode detection:
      - True jika PPE positif ditemukan DAN tidak ada negatif
      - False jika ada kelas negatif ATAU PPE positif tidak ditemukan
    Partial person: boots dan gloves otomatis True.
    """
    ppe_dets = [d for d in all_detections if d.class_name in PPE_POSITIVE_CLASSES]
    neg_dets = [d for d in all_detections if d.class_name in PPE_NEGATIVE_CLASSES]

    result = {}
    for ppe in required_ppe or ALL_PPE:
        # Cek kelas negatif (primer)
        neg_cls = NEGATIVE_TO_POSITIVE.get(ppe)       # dapatkan neg_class dari mapping
        # Balik mapping: PPE positif → neg class
        neg_for_ppe = None
        for neg_k, pos_v in NEGATIVE_TO_POSITIVE.items():
            if pos_v == ppe:
                neg_for_ppe = neg_k
                break

        has_negative = person_has_negative_ppe(person_det.bbox, neg_dets, neg_for_ppe)
        has_positive = person_has_ppe_positive(person_det.bbox, ppe_dets, ppe, frame_height)

        if has_negative:
            result[ppe] = False      # langgar: kelas negatif terdeteksi
        elif has_positive:
            result[ppe] = True       # patuh: APD ditemukan
        else:
            result[ppe] = False      # tidak ada sinyal positif = anggap tidak pakai

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
        backend_url:      Optional[str] = "https://localhost:8000",
        service_key:      str           = "",
        required_ppe:     Optional[List[str]] = None,
    ):
        self.camera_id        = camera_id
        self.save_screenshots = save_screenshots
        self.log_to_file      = log_to_file
        self.backend_url      = backend_url
        self.service_key      = service_key
        self.required_ppe     = list(required_ppe or REQUIRED_PPE)
        self.output_dir       = Path(output_dir)
        self.screenshot_dir   = self.output_dir / "screenshots"

        if save_screenshots:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        if log_to_file:
            self.output_dir.mkdir(parents=True, exist_ok=True)

        self.log_file             = self.output_dir / "violations.jsonl"
        self._last_event_time: Dict[str, float] = {}
        self.stats = {
            "total_events":     0,
            "per_type":         {k: 0 for k in VIOLATION_RULES},
            "sent_backend":     0,
            "fail_backend":     0,
            "frames_processed": 0,
            "neg_class_hits":   0,   # berapa kali deteksi dari kelas negatif
            "pos_absent_hits":  0,   # berapa kali dari absennya kelas positif
        }
        logger.info(
            f"ViolationLogic v5.0 Epson K3 | cam={camera_id} | "
            f"backend={'ON → ' + backend_url if backend_url else 'OFF'} | "
            f"required_ppe={','.join(self.required_ppe)}"
        )

    def process(
        self,
        detections:   List[Detection],
        frame,
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        """
        Proses satu frame, return list ViolationEvent.
        Dual-mode: negative class PRIMER, positive absent SEKUNDER.
        """
        self.stats["frames_processed"] += 1
        events: List[ViolationEvent] = []

        fh          = frame.shape[0] if hasattr(frame, "shape") else None
        person_dets = [d for d in detections if d.class_name == "Person"]
        all_dets    = [d for d in detections if d.class_name != "Person"]

        if not person_dets:
            return events

        for person in person_dets:
            if person.confidence < MIN_PERSON_CONF:
                continue

            partial = bool(fh and is_partial_person(person.bbox, fh))

            for vtype, rule in VIOLATION_RULES.items():
                if rule["ppe_class"] not in self.required_ppe:
                    continue
                # Skip APD yang dikecualikan saat partial
                if partial and rule["ppe_class"] in PARTIAL_EXEMPT_PPE:
                    continue
                if self._in_cooldown(vtype, rule["cooldown"]):
                    continue

                # ─── MODE A: Deteksi kelas negatif (PRIMER) ───
                neg_cls       = rule.get("neg_class")
                neg_dets_only = [d for d in all_dets if d.class_name in PPE_NEGATIVE_CLASSES]
                has_neg       = person_has_negative_ppe(person.bbox, neg_dets_only, neg_cls)

                # ─── MODE B: Absennya kelas positif (SEKUNDER) ───
                ppe_dets_only = [d for d in all_dets if d.class_name in PPE_POSITIVE_CLASSES]
                has_pos       = person_has_ppe_positive(person.bbox, ppe_dets_only, rule["ppe_class"], fh)

                is_violation  = has_neg or (not has_pos)
                detect_mode   = "negative_class" if has_neg else "positive_absent"

                if is_violation:
                    ev = self._make_event(vtype, rule, person, frame, frame_number, detect_mode)
                    events.append(ev)
                    self._last_event_time[vtype]  = time.time()
                    self.stats["total_events"]    += 1
                    self.stats["per_type"][vtype] += 1
                    if has_neg:
                        self.stats["neg_class_hits"] += 1
                    else:
                        self.stats["pos_absent_hits"] += 1

                    logger.warning(
                        f"PELANGGARAN | {vtype:12s} | {rule['severity']:6s} | "
                        f"mode={detect_mode[:3]} | "
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
            return {k: "UNKNOWN" for k in self.required_ppe}

        valid_persons = [p for p in person_dets if p.confidence >= MIN_PERSON_CONF]
        if not valid_persons:
            return {k: "UNKNOWN" for k in self.required_ppe}

        status: Dict[str, str] = {}
        for ppe_cls in self.required_ppe:
            compliant = False
            violation = False
            for p in valid_persons:
                if ppe_cls in PARTIAL_EXEMPT_PPE and frame_height:
                    if is_partial_person(p.bbox, frame_height):
                        compliant = True
                        continue

                ppe_dict = get_person_ppe_dict(
                    p,
                    detections,
                    frame_height,
                    required_ppe=self.required_ppe,
                )
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

    def _make_event(self, vtype, rule, person, frame, frame_number, detect_mode) -> ViolationEvent:
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
        cv2.putText(shot, f"EPSON K3 VIOLATION: {vtype.upper().replace('_',' ')}",
                    (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(shot, dt.strftime("%Y-%m-%d  %H:%M:%S UTC  |  " + self.camera_id),
                    (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1, cv2.LINE_AA)
        fname = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path  = self.screenshot_dir / fname
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return str(path)

    def _write_log(self, ev: ViolationEvent):
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(ev.to_json() + "\n")

    def _send_backend(self, ev: ViolationEvent):
        try:
            headers = {"Content-Type": "application/json"}
            if self.service_key:
                headers["X-Service-Key"] = self.service_key
            r = requests.post(
                f"{self.backend_url}/violations",
                json    = ev.to_payload(),
                timeout = BACKEND_TIMEOUT,
                headers = headers,
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
        print(f"\n{sep}\n  RINGKASAN SESI  [ViolationLogic v5.0 — Epson K3]")
        print(sep)
        print(f"  Camera          : {self.camera_id}")
        print(f"  Frames diproses : {self.stats['frames_processed']}")
        print(f"  Total pelanggaran: {self.stats['total_events']}")
        print(f"    via neg.class : {self.stats['neg_class_hits']}")
        print(f"    via pos.absent: {self.stats['pos_absent_hits']}")
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
    print("\n=== TEST violation_logic.py v5.0 — Epson K3 ===\n")
    H, W  = 480, 640
    frame = np.zeros((H, W, 3), dtype=np.uint8)
    logic = ViolationLogic(
        camera_id  = "EPSON_TEST",
        output_dir = "test_out_v5",
        backend_url= None,
    )

    print("TEST 1 — bbox_center() benar")
    cx, cy = bbox_center((100, 50, 300, 200))
    assert cx == 200.0 and cy == 125.0, "FAIL"
    print(f"  ✓ bbox_center → ({cx}, {cy})")

    print("\nTEST 2 — Semua APD lengkap (positive class) → 0 event")
    logic._last_event_time = {}
    ev = logic.process([
        Detection("Person",  0.92, (100,  30, 400, 460)),
        Detection("helmet",  0.88, (150,  40, 360, 130)),
        Detection("vest",    0.85, (110, 150, 390, 320)),
        Detection("gloves",  0.82, (110, 210, 230, 300)),
        Detection("boots",   0.80, (120, 360, 380, 455)),
        Detection("goggles", 0.78, (155,  42, 355, 100)),
    ], frame, 1)
    print(f"  Events: {len(ev)}  (expected 0)")
    assert len(ev) == 0, f"FAIL: {[e.violation_type for e in ev]}"
    print("  ✓ PASS")

    print("\nTEST 3 — Kelas negatif no_helmet → langsung violation")
    logic._last_event_time = {}
    ev = logic.process([
        Detection("Person",    0.91, (100, 30, 400, 460)),
        Detection("no_helmet", 0.85, (140, 35, 370, 120)),   # deteksi langsung
        Detection("vest",      0.85, (110,150, 390, 320)),
        Detection("goggles",   0.78, (155, 42, 355, 100)),
    ], frame, 2)
    print(f"  Events: {len(ev)}  (expected ≥1)")
    neg_ev = [e for e in ev if e.violation_type == "no_helmet"]
    assert len(neg_ev) >= 1
    assert neg_ev[0].detection_mode == "negative_class", "Mode harus negative_class"
    print(f"  ✓ PASS — mode={neg_ev[0].detection_mode}")

    print("\nTEST 4 — Partial person → boots & gloves dikecualikan")
    logic._last_event_time = {}
    ev = logic.process([
        Detection("Person",  0.91, (100,  20, 400, 110)),   # h=90 < 40% dari 480
        Detection("helmet",  0.88, (150,  25, 360,  75)),
        Detection("vest",    0.85, (110,  55, 390, 105)),
        Detection("goggles", 0.78, (155,  27, 355,  72)),
    ], frame, 3)
    types = [e.violation_type for e in ev]
    assert "no_boots"  not in types, f"boots tidak boleh ada: {types}"
    assert "no_gloves" not in types, f"gloves tidak boleh ada: {types}"
    print(f"  ✓ PASS — events={types}")

    print("\nTEST 5 — get_frame_status() dengan no_goggle → VIOLATION")
    logic._last_event_time = {}
    status = logic.get_frame_status([
        Detection("Person",    0.91, (100, 30, 400, 460)),
        Detection("no_goggle", 0.82, (150, 35, 360, 120)),
        Detection("helmet",    0.88, (150, 40, 360, 130)),
        Detection("vest",      0.85, (110,150, 390, 320)),
    ], frame_height=H)
    print(f"  goggles : {status.get('goggles')}  (expected VIOLATION)")
    print(f"  helmet  : {status.get('helmet')}  (expected COMPLIANT)")
    print(f"  vest    : {status.get('vest')}  (expected COMPLIANT)")
    assert status["goggles"] == "VIOLATION"
    assert status["helmet"]  == "COMPLIANT"
    print("  ✓ PASS")

    print("\n✅ Semua test PASSED — v5.0 Epson K3")
    logic.print_summary()
