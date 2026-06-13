"""
violation_logic.py  [v6.0 — Epson Factory K3 | 11-Class Dual Detection]
=========================================================================
Logika deteksi pelanggaran K3 untuk model YOLOv11 best.pt (11 kelas).

Kelas model:
    0: helmet        -> APD hadir: helm
    1: gloves        -> APD hadir: sarung tangan
    2: vest          -> APD hadir: rompi
    3: boots         -> APD hadir: sepatu safety
    4: goggles       -> APD hadir: kacamata pelindung
    5: none          -> Tidak ada APD terdeteksi (area kosong)
    6: Person        -> Deteksi orang
    7: no_helmet     -> LANGSUNG: orang tanpa helm (negative class)
    8: no_goggle     -> LANGSUNG: orang tanpa goggle (negative class)
    9: no_gloves     -> LANGSUNG: orang tanpa sarung tangan (negative class)
   10: no_boots      -> LANGSUNG: orang tanpa sepatu (negative class)

Strategi Deteksi v6.0 -- DUAL MODE + TEMPORAL SMOOTHING:
  MODE A (PRIMER)  : Kelas negatif (no_helmet, no_goggle, dll) langsung = LANGGAR
  MODE B (SEKUNDER): Kelas positif tidak ditemukan di sekitar Person = LANGGAR
  TEMPORAL MEMORY  : APD dianggap ada jika terdeteksi dalam N frame terakhir
  Jika salah satu mode mendeteksi pelanggaran (setelah temporal check) -> VIOLATION

Standard K3 Epson Factory:
  Wajib: Helm, Rompi, Sepatu Safety, Goggle, Sarung Tangan
  SEMUA 5 APD wajib digunakan -- tidak ada pengecualian partial person.

Perubahan v6.0 vs v5.0:
  - PPE_CONFIG per-kelas menggantikan MIN_OVERLAP global
  - gloves & boots: overlap-only (tanpa zone), robust terhadap perspektif
  - vest: overlap-only (tanpa zone)
  - helmet & goggles: overlap + head zone (tetap)
  - Temporal memory 10 frame -- eliminasi false positive saat APD sesaat hilang
  - POSITIVE_TO_NEGATIVE mapping ditambahkan (dibutuhkan inference.py v6.1)
  - NEG_HEAD_Y_ZONES & NEG_HEAD_X_ZONES diekspor (dibutuhkan inference.py v6.1)
  - bbox_center_inside_zone() diekspor (dibutuhkan inference.py v6.1)
  - reset_memory() sebagai public method
  - temporal_window parameter di __init__
  - temporal_saves counter di stats
"""

import cv2
import json
import time
import logging
import requests
from collections import deque
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from typing import Deque, Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level   = logging.INFO,
    format  = "[%(asctime)s] %(levelname)s -- %(message)s",
    datefmt = "%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------
#  KELAS MODEL -- 11 kelas dari best.pt
# ---------------------------------------------

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

PPE_POSITIVE_CLASSES: Set[str] = {"helmet", "gloves", "vest", "boots", "goggles"}
PPE_NEGATIVE_CLASSES: Set[str] = {"no_helmet", "no_goggle", "no_gloves", "no_boots"}

# Mapping: kelas negatif -> kelas positif pasangannya
NEGATIVE_TO_POSITIVE: Dict[str, str] = {
    "no_helmet": "helmet",
    "no_goggle":  "goggles",
    "no_gloves":  "gloves",
    "no_boots":   "boots",
}

# Mapping: kelas positif -> kelas negatif pasangannya
# DIBUTUHKAN oleh inference.py v6.1
POSITIVE_TO_NEGATIVE: Dict[str, str] = {v: k for k, v in NEGATIVE_TO_POSITIVE.items()}

PPE_DISPLAY_NAMES: Dict[str, str] = {
    "helmet":  "Helm",
    "gloves":  "Sarung Tangan",
    "vest":    "Rompi",
    "boots":   "Sepatu Safety",
    "goggles": "Goggle",
}

# APD wajib sesuai standar Epson Factory K3
REQUIRED_PPE: List[str] = ["helmet", "vest", "boots", "goggles", "gloves"]

# APD yang dikecualikan saat person partial -- TIDAK ADA
# Semua 5 APD wajib digunakan sesuai standar K3 Epson Factory
PARTIAL_EXEMPT_PPE: Set[str] = set()   # kosong: tidak ada pengecualian

# Alias untuk kompatibilitas kode lama
ALL_PPE = REQUIRED_PPE


# ---------------------------------------------
#  PPE CONFIG -- per-kelas (v6.0)
# ---------------------------------------------

PPE_CONFIG: Dict[str, dict] = {
    "helmet": {
        "min_overlap":    0.10,
        "use_zone":       True,       # kepala terletak di zona atas person
        "min_conf":       0.50,       # conf threshold khusus kelas ini
        "min_area_ratio": 0.0,        # tidak ada minimum area
    },
    "goggles": {
        "min_overlap":    0.08,
        "use_zone":       True,
        "min_conf":       0.50,
        "min_area_ratio": 0.0,
    },
    "vest": {
        "min_overlap":    0.25,       # dinaikkan dari 0.10 → 0.25
                                      # rompi safety menutup badan lebih luas dari kaos
        "use_zone":       True,       # aktifkan zone: rompi harus di zona torso
        "min_conf":       0.65,       # conf tinggi — model harus yakin ini rompi, bukan kaos
        "min_area_ratio": 0.04,       # vest bbox harus >= 4% area person (rompi punya luas nyata)
    },
    "gloves": {
        "min_overlap":    0.03,
        "use_zone":       False,
        "min_conf":       0.50,
        "min_area_ratio": 0.0,
    },
    "boots": {
        "min_overlap":    0.03,
        "use_zone":       False,
        "min_conf":       0.50,
        "min_area_ratio": 0.0,
    },
}

# Zone Y/X hanya untuk kelas yang use_zone=True
# helmet & goggles: zona kepala
# vest: zona torso (bahu ke pinggang)
HEAD_Y_ZONES: Dict[str, Tuple[float, float]] = {
    "helmet":  (0.00, 0.35),
    "goggles": (0.00, 0.40),
    "vest":    (0.18, 0.75),   # zona torso: 18%–75% tinggi person
}
HEAD_X_ZONES: Dict[str, Tuple[float, float]] = {
    "helmet":  (0.15, 0.85),
    "goggles": (0.15, 0.85),
    "vest":    (0.05, 0.95),   # hampir selebar person
}

# Zone negatif -- hanya untuk no_helmet dan no_goggle
# DIEKSPOR -- dibutuhkan inference.py v6.1
NEG_HEAD_Y_ZONES: Dict[str, Tuple[float, float]] = {
    "no_helmet": (0.00, 0.40),
    "no_goggle": (0.00, 0.45),
}
NEG_HEAD_X_ZONES: Dict[str, Tuple[float, float]] = {
    "no_helmet": (0.15, 0.85),
    "no_goggle": (0.15, 0.85),
}

# Threshold confidence
MIN_PERSON_CONF: float = 0.45
MIN_PPE_CONF:    float = 0.40
MIN_NEG_CONF:    float = 0.45

# Partial person: bbox person < threshold tinggi frame
PARTIAL_PERSON_RATIO: float = 0.40

# Temporal memory: PPE dianggap ada jika terdeteksi dalam N frame terakhir
TEMPORAL_WINDOW: int = 10

# Warna BGR
VIOLATION_COLOR = (0,   0, 255)
COMPLIANT_COLOR = (0, 200,   0)
UNKNOWN_COLOR   = (130, 130, 130)
WARNING_COLOR   = (0,  165, 255)

# Kompatibilitas v5.0 -- MIN_OVERLAP global (digantikan PPE_CONFIG per-kelas)
MIN_OVERLAP: float = 0.10

# Panel labels untuk overlay
PANEL_LABELS: Dict[str, str] = {
    "helmet":  "Helm    ",
    "vest":    "Rompi   ",
    "boots":   "Sepatu  ",
    "goggles": "Goggle  ",
    "gloves":  "Gloves  ",
}

BACKEND_URL     = "http://localhost:8000"
BACKEND_TIMEOUT = 5


# ---------------------------------------------
#  VIOLATION RULES -- Epson K3 Standard
# ---------------------------------------------

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


# ---------------------------------------------
#  DATA CLASSES
# ---------------------------------------------

@dataclass
class Detection:
    """
    Satu deteksi dari YOLO.
    bbox dalam koordinat frame ASLI (sudah di-scale).
    """
    class_name: str
    confidence: float
    bbox:       tuple   # (x1, y1, x2, y2)


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
    detection_mode:  str           # "negative_class" | "positive_absent"
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


# ---------------------------------------------
#  UTILITAS BBOX
# ---------------------------------------------

def bbox_area(bbox: tuple) -> float:
    x1, y1, x2, y2 = bbox
    return float(max(0, x2 - x1) * max(0, y2 - y1))


def overlap_ratio(bbox_ppe: tuple, bbox_person: tuple) -> float:
    """Rasio: area(ppe intersection person) / area(ppe)."""
    ax1, ay1, ax2, ay2 = bbox_ppe
    bx1, by1, bx2, by2 = bbox_person
    inter = float(
        max(0, min(ax2, bx2) - max(ax1, bx1)) *
        max(0, min(ay2, by2) - max(ay1, by1))
    )
    area = bbox_area(bbox_ppe)
    return (inter / area) if area > 0 else 0.0


def bbox_center(bbox: tuple) -> Tuple[float, float]:
    """Titik tengah bbox -> (cx, cy). Dipertahankan untuk kompatibilitas v5.0."""
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) * 0.5, (y1 + y2) * 0.5)


def bbox_center_inside_zone(
    person_bbox: tuple,
    obj_bbox:    tuple,
    y_zone:      Tuple[float, float],
    x_zone:      Tuple[float, float],
) -> bool:
    """
    True jika titik tengah obj_bbox berada di dalam zona relatif person_bbox.
    Zona diekspresikan sebagai rasio (0.0-1.0) dari lebar/tinggi person.
    DIEKSPOR -- dibutuhkan inference.py v6.1
    """
    px1, py1, px2, py2 = person_bbox
    pw = px2 - px1
    ph = py2 - py1
    if pw <= 0 or ph <= 0:
        return False
    ox1, oy1, ox2, oy2 = obj_bbox
    rel_x = ((ox1 + ox2) * 0.5 - px1) / pw
    rel_y = ((oy1 + oy2) * 0.5 - py1) / ph
    return x_zone[0] <= rel_x <= x_zone[1] and y_zone[0] <= rel_y <= y_zone[1]


def is_partial_person(person_bbox: tuple, frame_height: int) -> bool:
    """True jika bbox person < PARTIAL_PERSON_RATIO dari tinggi frame."""
    if frame_height <= 0:
        return False
    _, y1, _, y2 = person_bbox
    return ((y2 - y1) / frame_height) < PARTIAL_PERSON_RATIO


# ---------------------------------------------
#  SPATIAL VALIDATION V6
# ---------------------------------------------

def _ppe_present(
    person_bbox: tuple,
    detections:  List[Detection],
    ppe_class:   str,
) -> bool:
    """
    Cek apakah APD positif ada pada seorang Person.

    Strategi per-kelas (PPE_CONFIG):
      - helmet/goggles : overlap >= threshold ATAU center dalam head zone
      - vest           : overlap >= threshold DAN dalam torso zone DAN
                         confidence >= min_conf DAN area bbox >= min_area_ratio
                         (mencegah kaos biasa terdeteksi sebagai rompi safety)
      - gloves/boots   : overlap >= threshold saja

    Untuk vest, tiga syarat harus terpenuhi semua:
      1. confidence >= 0.65  (model harus sangat yakin)
      2. overlap >= 0.25     (rompi menutupi area torso yang signifikan)
      3. center dalam zona torso (18%-75% tinggi person)
      4. area vest bbox >= 4% area person bbox (rompi punya luas nyata di frame)
    """
    cfg           = PPE_CONFIG[ppe_class]
    min_ov        = cfg["min_overlap"]
    use_zone      = cfg["use_zone"]
    min_conf      = cfg.get("min_conf", MIN_PPE_CONF)
    min_area_rat  = cfg.get("min_area_ratio", 0.0)

    # Hitung area person untuk perbandingan
    person_area = bbox_area(person_bbox)

    for det in detections:
        if det.class_name != ppe_class:
            continue

        # Cek confidence per-kelas (vest lebih ketat dari default)
        if det.confidence < min_conf:
            continue

        # Cek minimum area relatif terhadap person (khusus vest)
        if min_area_rat > 0.0 and person_area > 0:
            ppe_area = bbox_area(det.bbox)
            if (ppe_area / person_area) < min_area_rat:
                continue   # bbox terlalu kecil untuk jadi rompi asli

        ov = overlap_ratio(det.bbox, person_bbox)

        if use_zone:
            # Vest & helmet/goggles: harus overlap DAN dalam zone
            in_zone = bbox_center_inside_zone(
                person_bbox,
                det.bbox,
                HEAD_Y_ZONES[ppe_class],
                HEAD_X_ZONES[ppe_class],
            )
            if ov >= min_ov and in_zone:
                return True
            # Fallback untuk helmet/goggles: overlap ATAU zone (lebih fleksibel)
            if ppe_class in ("helmet", "goggles"):
                if ov >= min_ov or in_zone:
                    return True
        else:
            # gloves/boots: overlap saja
            if ov >= min_ov:
                return True

    return False


def _neg_present(
    person_bbox: tuple,
    detections:  List[Detection],
    neg_class:   str,
) -> bool:
    """
    Cek apakah kelas negatif APD ada pada seorang Person.
    helmet/goggle neg: overlap >= threshold ATAU center dalam head zone.
    gloves/boots neg : overlap >= threshold saja.
    """
    if neg_class is None:
        return False

    pos_class = NEGATIVE_TO_POSITIVE.get(neg_class)
    min_ov    = PPE_CONFIG[pos_class]["min_overlap"] if pos_class else 0.08
    use_zone  = neg_class in NEG_HEAD_Y_ZONES

    for det in detections:
        if det.class_name != neg_class:
            continue
        if det.confidence < MIN_NEG_CONF:
            continue

        ov = overlap_ratio(det.bbox, person_bbox)
        if ov >= min_ov:
            return True

        if use_zone:
            in_zone = bbox_center_inside_zone(
                person_bbox,
                det.bbox,
                NEG_HEAD_Y_ZONES[neg_class],
                NEG_HEAD_X_ZONES[neg_class],
            )
            if in_zone:
                return True

    return False


# ---------------------------------------------
#  FUNGSI KOMPATIBILITAS V5.0
#  Dipertahankan agar kode lain yang sudah import
#  person_has_ppe_positive / person_has_negative_ppe
#  / get_person_ppe_dict tidak perlu diubah.
# ---------------------------------------------

def person_has_ppe_positive(
    person_bbox:    tuple,
    ppe_detections: List[Detection],
    ppe_class:      str,
    frame_height:   Optional[int] = None,
) -> bool:
    """Wrapper kompatibilitas v5.0 -> _ppe_present() v6.0."""
    return _ppe_present(person_bbox, ppe_detections, ppe_class)


def person_has_negative_ppe(
    person_bbox:    tuple,
    all_detections: List[Detection],
    neg_class:      Optional[str],
) -> bool:
    """Wrapper kompatibilitas v5.0 -> _neg_present() v6.0."""
    if neg_class is None:
        return False
    return _neg_present(person_bbox, all_detections, neg_class)


def get_person_ppe_dict(
    person_det:     Detection,
    all_detections: List[Detection],
    frame_height:   Optional[int] = None,
) -> Dict[str, bool]:
    """
    Status semua APD untuk satu Person.
    Dual-mode: negatif class (primer) + absen positif (sekunder).
    Partial person: boots dan gloves otomatis True.
    Wrapper kompatibilitas v5.0.
    """
    ppe_dets = [d for d in all_detections if d.class_name in PPE_POSITIVE_CLASSES]
    neg_dets = [d for d in all_detections if d.class_name in PPE_NEGATIVE_CLASSES]

    result: Dict[str, bool] = {}
    for ppe in ALL_PPE:
        neg_for_ppe = POSITIVE_TO_NEGATIVE.get(ppe)
        has_negative = _neg_present(person_det.bbox, neg_dets, neg_for_ppe)
        has_positive = _ppe_present(person_det.bbox, ppe_dets, ppe)

        if has_negative:
            result[ppe] = False
        elif has_positive:
            result[ppe] = True
        else:
            result[ppe] = False

    # Semua 5 APD wajib -- tidak ada partial person exemption

    return result


# ---------------------------------------------
#  TEMPORAL MEMORY
# ---------------------------------------------

class PPEMemory:
    """
    Menyimpan status APD beberapa frame terakhir.
    APD dianggap ada jika terdeteksi dalam TEMPORAL_WINDOW frame terakhir.
    """
    def __init__(self, window: int = TEMPORAL_WINDOW):
        self._window = window
        self._history: Dict[str, Deque[bool]] = {
            ppe: deque(maxlen=window) for ppe in REQUIRED_PPE
        }

    def update(self, ppe_class: str, detected: bool) -> None:
        self._history[ppe_class].append(detected)

    def is_present(self, ppe_class: str) -> bool:
        """True jika APD terdeteksi minimal 1x dalam window terakhir."""
        hist = self._history[ppe_class]
        if not hist:
            return False
        return any(hist)

    def reset(self) -> None:
        for q in self._history.values():
            q.clear()


# ---------------------------------------------
#  KELAS UTAMA
# ---------------------------------------------

class ViolationLogic:

    def __init__(
        self,
        camera_id:        str           = "EPSON_CAM_01",
        output_dir:       str           = "violation_output",
        save_screenshots: bool          = True,
        log_to_file:      bool          = True,
        backend_url:      Optional[str] = None,
        temporal_window:  int           = TEMPORAL_WINDOW,
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

        self.log_file              = self.output_dir / "violations.jsonl"
        self._last_event_time: Dict[str, float] = {}

        # Temporal memory (slot tunggal -- satu person dominan per frame)
        self._ppe_memory = PPEMemory(window=temporal_window)

        self.stats = {
            "total_events":     0,
            "per_type":         {k: 0 for k in VIOLATION_RULES},
            "sent_backend":     0,
            "fail_backend":     0,
            "frames_processed": 0,
            "neg_class_hits":   0,
            "pos_absent_hits":  0,
            "temporal_saves":   0,
        }
        logger.info(
            f"ViolationLogic v6.0 Epson K3 | cam={camera_id} | "
            f"backend={'ON -> ' + backend_url if backend_url else 'OFF'} | "
            f"classes=11 | required_ppe={len(REQUIRED_PPE)} | "
            f"temporal_window={temporal_window}"
        )

    # -- API publik -------------------------

    def process(
        self,
        detections:   List[Detection],
        frame,
        frame_number: int = 0,
    ) -> List[ViolationEvent]:
        """
        Proses satu frame, return list ViolationEvent.

        Alur:
          1. Cari semua Person valid.
          2. Untuk setiap Person & setiap violation rule:
             a. Cek kelas negatif (MODE A -- primer).
             b. Cek absennya kelas positif (MODE B -- sekunder).
          3. Update temporal memory.
          4. Buat event hanya jika temporal memory juga menunjukkan absen.
        """
        self.stats["frames_processed"] += 1
        events: List[ViolationEvent] = []

        fh          = frame.shape[0] if hasattr(frame, "shape") else None
        person_dets = [d for d in detections if d.class_name == "Person"]
        ppe_dets    = [d for d in detections if d.class_name in PPE_POSITIVE_CLASSES]
        neg_dets    = [d for d in detections if d.class_name in PPE_NEGATIVE_CLASSES]

        if not person_dets:
            return events

        for person in person_dets:
            if person.confidence < MIN_PERSON_CONF:
                continue

            partial = bool(fh and is_partial_person(person.bbox, fh))

            for vtype, rule in VIOLATION_RULES.items():
                ppe_cls = rule["ppe_class"]
                neg_cls = rule.get("neg_class")

                # Semua APD wajib -- tidak ada partial person exemption

                # MODE A: Deteksi kelas negatif (PRIMER)
                has_neg = _neg_present(person.bbox, neg_dets, neg_cls)

                # MODE B: Absennya kelas positif (SEKUNDER)
                has_pos = _ppe_present(person.bbox, ppe_dets, ppe_cls)

                raw_violation = has_neg or (not has_pos)

                # Update temporal memory
                self._ppe_memory.update(ppe_cls, not raw_violation)

                # Temporal check: jika raw violation tapi memory masih ada
                if raw_violation and self._ppe_memory.is_present(ppe_cls):
                    self.stats["temporal_saves"] += 1
                    continue

                if not raw_violation:
                    continue

                if self._in_cooldown(vtype, rule["cooldown"]):
                    continue

                detect_mode = "negative_class" if has_neg else "positive_absent"
                ev = self._make_event(
                    vtype, rule, person, frame, frame_number, detect_mode
                )
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
                    f"mode={detect_mode[:3]} | conf={person.confidence:.2f}"
                    f" | fr={frame_number}"
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
        Return: {ppe_class: "COMPLIANT" | "VIOLATION" | "UNKNOWN"}
        Dipertahankan untuk kompatibilitas -- inference v6.1 tidak
        memanggilnya langsung, tapi berguna untuk integrasi lain.
        """
        person_dets = [d for d in detections if d.class_name == "Person"]

        if not person_dets:
            return {k: "UNKNOWN" for k in REQUIRED_PPE}

        valid_persons = [p for p in person_dets if p.confidence >= MIN_PERSON_CONF]
        if not valid_persons:
            return {k: "UNKNOWN" for k in REQUIRED_PPE}

        ppe_dets = [d for d in detections if d.class_name in PPE_POSITIVE_CLASSES]
        neg_dets = [d for d in detections if d.class_name in PPE_NEGATIVE_CLASSES]

        status: Dict[str, str] = {}
        for ppe_cls in REQUIRED_PPE:
            compliant = False
            violation = False
            for p in valid_persons:
                neg_cls  = POSITIVE_TO_NEGATIVE.get(ppe_cls)
                has_neg  = _neg_present(p.bbox, neg_dets, neg_cls) if neg_cls else False
                has_pos  = _ppe_present(p.bbox, ppe_dets, ppe_cls)

                raw_viol = has_neg or (not has_pos)

                if raw_viol and self._ppe_memory.is_present(ppe_cls):
                    compliant = True
                elif not raw_viol:
                    compliant = True
                else:
                    violation = True

            status[ppe_cls] = (
                "VIOLATION" if violation else
                "COMPLIANT" if compliant else
                "UNKNOWN"
            )
        return status

    def reset_memory(self) -> None:
        """Reset temporal memory -- panggil saat scene/kamera berubah."""
        self._ppe_memory.reset()
        logger.info(f"[{self.camera_id}] Temporal memory di-reset.")

    # -- internal ---------------------------

    def _in_cooldown(self, vtype: str, cooldown: float) -> bool:
        return (time.time() - self._last_event_time.get(vtype, 0.0)) < cooldown

    def _make_event(
        self,
        vtype:        str,
        rule:         dict,
        person:       Detection,
        frame,
        frame_number: int,
        detect_mode:  str,
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

    def _save_screenshot(
        self,
        frame,
        bbox:  tuple,
        dt:    datetime,
        vtype: str,
    ) -> str:
        shot = frame.copy()
        x1, y1, x2, y2 = bbox
        cv2.rectangle(shot, (x1, y1), (x2, y2), VIOLATION_COLOR, 3)
        header_h = 70
        cv2.rectangle(shot, (0, 0), (shot.shape[1], header_h), (0, 0, 140), -1)
        cv2.putText(
            shot,
            f"EPSON K3 VIOLATION: {vtype.upper().replace('_', ' ')}",
            (10, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.80, (255, 255, 255), 2, cv2.LINE_AA,
        )
        cv2.putText(
            shot,
            dt.strftime("%Y-%m-%d  %H:%M:%S UTC  |  " + self.camera_id),
            (10, 62), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1, cv2.LINE_AA,
        )
        fname = f"{vtype}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path  = self.screenshot_dir / fname
        cv2.imwrite(str(path), shot, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return str(path)

    def _write_log(self, ev: ViolationEvent) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(ev.to_json() + "\n")

    def _send_backend(self, ev: ViolationEvent) -> None:
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

    def print_summary(self) -> None:
        sep = "=" * 62
        print(f"\n{sep}\n  RINGKASAN SESI  [ViolationLogic v6.0 -- Epson K3]")
        print(sep)
        print(f"  Camera          : {self.camera_id}")
        print(f"  Frames diproses : {self.stats['frames_processed']}")
        print(f"  Total pelanggaran: {self.stats['total_events']}")
        print(f"    via neg.class  : {self.stats['neg_class_hits']}")
        print(f"    via pos.absent : {self.stats['pos_absent_hits']}")
        print(f"    temporal saves : {self.stats['temporal_saves']}")
        print(f"\n  Detail per tipe:")
        for vtype, n in self.stats["per_type"].items():
            sev = VIOLATION_RULES[vtype]["severity"]
            bar = "#" * min(n, 20) if n > 0 else "-"
            print(f"    {'!!' if n else '  '} {vtype:12s}: {n:>4}x  [{sev:6s}]  {bar}")
        print(f"\n  Backend terkirim: {self.stats['sent_backend']}")
        print(f"  Backend gagal   : {self.stats['fail_backend']}")
        print(f"  Log file        : {self.log_file.resolve()}")
        print(sep)


# ---------------------------------------------
#  SELF TEST
# ---------------------------------------------

if __name__ == "__main__":
    import numpy as np
    print("\n=== TEST violation_logic.py v6.0 -- Epson K3 ===\n")

    H, W  = 480, 640
    frame = np.zeros((H, W, 3), dtype=np.uint8)

    logic = ViolationLogic(
        camera_id        = "EPSON_TEST",
        output_dir       = "test_out_v6",
        backend_url      = None,
        save_screenshots = False,
    )

    # TEST 1 -- verifikasi POSITIVE_TO_NEGATIVE mapping
    print("TEST 1 -- POSITIVE_TO_NEGATIVE mapping benar")
    assert POSITIVE_TO_NEGATIVE["helmet"]  == "no_helmet",  "FAIL helmet"
    assert POSITIVE_TO_NEGATIVE["goggles"] == "no_goggle",  "FAIL goggles"
    assert POSITIVE_TO_NEGATIVE["gloves"]  == "no_gloves",  "FAIL gloves"
    assert POSITIVE_TO_NEGATIVE["boots"]   == "no_boots",   "FAIL boots"
    print("  v PASS")

    # TEST 2 -- bbox_center_inside_zone diekspor dengan benar
    print("\nTEST 2 -- bbox_center_inside_zone() berfungsi")
    person_bbox = (100, 50, 400, 450)
    helmet_bbox = (150, 60, 350, 160)   # di zona atas
    assert bbox_center_inside_zone(
        person_bbox, helmet_bbox, (0.0, 0.35), (0.15, 0.85)
    ) is True
    print("  v PASS")

    # TEST 3 -- semua APD lengkap -> 0 event
    print("\nTEST 3 -- Semua APD lengkap -> 0 event")
    logic._last_event_time = {}
    logic.reset_memory()
    for _ in range(TEMPORAL_WINDOW):
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
    print("  v PASS")

    # TEST 4 -- kelas negatif no_helmet -> violation
    print("\nTEST 4 -- Kelas negatif no_helmet -> violation")
    logic.reset_memory()
    # Reset cooldown: set semua last_event_time ke masa lalu
    logic._last_event_time = {k: 0.0 for k in VIOLATION_RULES}
    ev = []
    for i in range(TEMPORAL_WINDOW + 1):
        # Reset cooldown setiap iterasi agar tidak terblokir
        logic._last_event_time = {k: 0.0 for k in VIOLATION_RULES}
        ev = logic.process([
            Detection("Person",    0.91, (100,  30, 400, 460)),
            Detection("no_helmet", 0.85, (140,  35, 370, 120)),
            Detection("vest",      0.85, (110, 150, 390, 320)),
            Detection("goggles",   0.78, (155,  42, 355, 100)),
        ], frame, i)
    neg_ev = [e for e in ev if e.violation_type == "no_helmet"]
    print(f"  no_helmet events: {len(neg_ev)}  (expected >=1)")
    assert len(neg_ev) >= 1, "FAIL"
    assert neg_ev[0].detection_mode == "negative_class"
    print(f"  v PASS -- mode={neg_ev[0].detection_mode}")

    # TEST 5 -- temporal memory mencegah false violation
    print("\nTEST 5 -- Temporal memory mencegah false violation (gloves sesaat hilang)")
    logic._last_event_time = {}
    logic.reset_memory()
    for i in range(5):
        logic.process([
            Detection("Person",  0.91, (100,  30, 400, 460)),
            Detection("helmet",  0.88, (150,  40, 360, 130)),
            Detection("vest",    0.85, (110, 150, 390, 320)),
            Detection("gloves",  0.82, (110, 210, 230, 300)),
            Detection("boots",   0.80, (120, 360, 380, 455)),
            Detection("goggles", 0.78, (155,  42, 355, 100)),
        ], frame, i)
    gloves_viol = 0
    for i in range(5, 9):
        ev = logic.process([
            Detection("Person",  0.91, (100,  30, 400, 460)),
            Detection("helmet",  0.88, (150,  40, 360, 130)),
            Detection("vest",    0.85, (110, 150, 390, 320)),
            Detection("boots",   0.80, (120, 360, 380, 455)),
            Detection("goggles", 0.78, (155,  42, 355, 100)),
        ], frame, i)
        gloves_viol += sum(1 for e in ev if e.violation_type == "no_gloves")
    print(f"  no_gloves violations saat sesaat hilang: {gloves_viol}  (expected 0)")
    assert gloves_viol == 0, f"FAIL: temporal memory tidak bekerja"
    print("  v PASS")

    # TEST 6 -- partial person -> boots & gloves TETAP DIPERIKSA (semua wajib)
    print("\nTEST 6 -- Partial person -> boots & gloves TETAP WAJIB")
    logic._last_event_time = {k: 0.0 for k in VIOLATION_RULES}
    logic.reset_memory()
    for _ in range(TEMPORAL_WINDOW + 1):
        logic._last_event_time = {k: 0.0 for k in VIOLATION_RULES}
        ev = logic.process([
            Detection("Person",  0.91, (100,  20, 400, 110)),   # h=90 < 40% dari 480
            Detection("helmet",  0.88, (150,  25, 360,  75)),
            Detection("vest",    0.85, (110,  55, 390, 105)),
            Detection("goggles", 0.78, (155,  27, 355,  72)),
            # boots & gloves sengaja tidak ada
        ], frame, 3)
    types = [e.violation_type for e in ev]
    # Sekarang harus ada pelanggaran no_boots dan no_gloves
    assert "no_boots"  in types, f"boots HARUS langgar: {types}"
    assert "no_gloves" in types, f"gloves HARUS langgar: {types}"
    print(f"  v PASS -- events={types}")

    # TEST 7 -- reset_memory() berfungsi
    print("\nTEST 7 -- reset_memory() public method")
    logic.reset_memory()
    print("  v PASS")

    # TEST 8 -- temporal_window parameter di __init__
    print("\nTEST 8 -- temporal_window parameter di __init__")
    logic2 = ViolationLogic(
        camera_id        = "TEST2",
        output_dir       = "test_out_v6b",
        save_screenshots = False,
        temporal_window  = 5,
    )
    assert logic2._ppe_memory._window == 5
    print("  v PASS")

    print("\n=== Semua test PASSED -- v6.0 Epson K3 ===")
    logic.print_summary()