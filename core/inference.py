"""
inference.py  [v6.1 — Epson Factory K3 | Smart Violation BBox]
================================================================
Pipeline inference real-time YOLOv11 untuk deteksi APD K3 Epson.

PERUBAHAN UTAMA v6.1 vs v5.0:
  BBOX HANYA MUNCUL SAAT PELANGGARAN
    - Orang patuh sempurna → tidak ada bbox apapun di frame (clean)
    - Orang melanggar → bbox HANYA di zona body-part yang bermasalah

  SEMUA 5 APD WAJIB (tidak ada pengecualian):
    - Helm hilang    → bbox di zona kepala   (0–35% tinggi person)
    - Goggle hilang  → bbox di zona mata     (5–38%)
    - Vest hilang    → bbox di zona dada     (28–72%)
    - Gloves hilang  → bbox di zona tangan   (52–95%)
    - Boots hilang   → bbox di zona kaki     (72–100%)

  REFERENSI ILMIAH:
    "Automated PPE compliance monitoring using deep learning-based
     detection and pose estimation" — ScienceDirect 2025.
    Kepala (telinga/mata) → helmet, pergelangan tangan → gloves,
    pergelangan kaki → boots, bahu+pinggul → vest.

  PRIORITAS BBOX (tertinggi ke terendah akurasi):
    1. Bbox kelas negatif langsung dari model (no_helmet, no_goggle, dst.)
       → akurasi model itu sendiri, paling akurat
    2. Kalkulasi body-part zone dari bbox Person
       → fallback robust saat kelas negatif tidak ada

  FITUR LAIN:
    - Dual-mode detection: negatif class (primer) + absen positif (sekunder)
    - Temporal smoothing 10 frame: menghilangkan flicker
    - Conflict resolution: helmet↔no_helmet, goggles↔no_goggle, dst.
    - ONNX auto-detect Format A (4+C) dan Format B (5+C/YOLOv5)
    - Class-wise NMS untuk performa CPU

Kelas model (11 kelas):
    0:helmet 1:gloves 2:vest 3:boots 4:goggles
    5:none   6:Person 7:no_helmet 8:no_goggle 9:no_gloves 10:no_boots

Cara pakai:
  python inference.py --source 0 --model best.pt --no-backend
  python inference.py --source video.mp4 --model best.onnx --use-onnx
  python inference.py --source 0 --model best.pt --save-video out.mp4
  python inference.py --source images/ --model best.pt --no-backend
"""

import cv2
import time
import argparse
import numpy as np
from collections import deque
from pathlib import Path
from typing import Deque, Dict, List, Optional, Set, Tuple

# ── Import violation_logic v6.0 ───────────────────────────────────
from violation_logic import (
    ViolationLogic,
    Detection,
    ViolationEvent,
    CLASS_NAMES,
    REQUIRED_PPE,
    PPE_POSITIVE_CLASSES,
    PPE_NEGATIVE_CLASSES,
    PPE_DISPLAY_NAMES,
    NEGATIVE_TO_POSITIVE,
    POSITIVE_TO_NEGATIVE,
    NEG_HEAD_Y_ZONES,
    NEG_HEAD_X_ZONES,
    HEAD_Y_ZONES,
    HEAD_X_ZONES,
    PPE_CONFIG,
    MIN_PERSON_CONF,
    MIN_PPE_CONF,
    MIN_NEG_CONF,
    TEMPORAL_WINDOW,
    VIOLATION_COLOR,
    COMPLIANT_COLOR,
    UNKNOWN_COLOR,
    bbox_center_inside_zone,
    overlap_ratio,
)

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    HAS_ULTRALYTICS = False

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False


# ─────────────────────────────────────────────
#  KONSTANTA
# ─────────────────────────────────────────────

MODEL_INPUT_SIZE    = 640
NMS_IOU_THRESHOLD   = 0.45
CONFLICT_IOU_THRESH = 0.50   # IoU ≥ ini → konflik pos vs neg

# Warna violation bbox per APD (BGR)
VIOL_COLORS: Dict[str, Tuple[int, int, int]] = {
    "helmet":  (  0,   0, 255),   # merah
    "goggles": (  0,  80, 255),   # merah-oranye
    "vest":    (  0, 160, 255),   # oranye
    "gloves":  (  0, 200, 255),   # kuning-oranye
    "boots":   ( 80,   0, 255),   # merah-ungu
}

# Label pendek untuk bbox violation
PPE_SHORT: Dict[str, str] = {
    "helmet":  "NO HELM",
    "goggles": "NO GOGGLE",
    "vest":    "NO ROMPI",
    "gloves":  "NO GLOVES",
    "boots":   "NO BOOTS",
}

# Label panel kanan atas
PANEL_LABELS: Dict[str, str] = {
    "helmet":  "Helm     ",
    "vest":    "Rompi    ",
    "boots":   "Sepatu   ",
    "goggles": "Goggle   ",
    "gloves":  "Gloves   ",
}


# ─────────────────────────────────────────────
#  BODY-PART ANCHOR ZONES
#
#  Referensi: "Automated PPE compliance monitoring in industrial
#  environments using deep learning-based detection and pose estimation"
#  (ScienceDirect, Automation in Construction, 2025)
#
#  Zona Y (vertikal) dan X (horizontal) RELATIF terhadap bbox Person
#  0.0 = tepi atas, 1.0 = tepi bawah (Y)
#  0.0 = tepi kiri, 1.0 = tepi kanan (X)
#
#  Dasar anatomi standar manusia berdiri tegak:
#    kepala   ≈ 0–15% tinggi tubuh
#    mata     ≈ 5–12%
#    bahu     ≈ 18–25%
#    pinggul  ≈ 45–55%
#    lutut    ≈ 65–75%
#    kaki     ≈ 80–100%
# ─────────────────────────────────────────────

BODY_ZONE_Y: Dict[str, Tuple[float, float]] = {
    "helmet":  (0.00, 0.35),   # kepala atas
    "goggles": (0.05, 0.38),   # mata/kacamata
    "vest":    (0.18, 0.75),   # torso: bahu sampai pinggang (sinkron dengan HEAD_Y_ZONES vest)
    "gloves":  (0.52, 0.95),   # lengan dan tangan
    "boots":   (0.72, 1.00),   # tungkai kaki hingga bawah
}
BODY_ZONE_X: Dict[str, Tuple[float, float]] = {
    "helmet":  (0.10, 0.90),
    "goggles": (0.10, 0.90),
    "vest":    (0.05, 0.95),
    "gloves":  (0.00, 1.00),   # selebar mungkin, tangan bisa ke samping
    "boots":   (0.05, 0.95),
}

# Padding piksel untuk memperluas violation bbox agar lebih mudah dilihat
ZONE_PADDING: Dict[str, int] = {
    "helmet":  5,
    "goggles": 5,
    "vest":    8,
    "gloves":  10,
    "boots":   8,
}


# ─────────────────────────────────────────────
#  TEMPORAL VISUAL MEMORY
# ─────────────────────────────────────────────

class PPEVisualTracker:
    """
    Menyimpan status visual APD dalam N frame terakhir.
    Digunakan khusus untuk overlay rendering (mencegah flicker bbox).
    Terpisah dari PPEMemory di violation_logic yang dipakai untuk event.
    """
    def __init__(self, window: int = TEMPORAL_WINDOW):
        self._window  = window
        self._history: Dict[str, Deque[bool]] = {
            ppe: deque(maxlen=window) for ppe in REQUIRED_PPE
        }

    def update(self, ppe_status: Dict[str, bool]) -> None:
        for ppe, present in ppe_status.items():
            if ppe in self._history:
                self._history[ppe].append(present)

    def is_present(self, ppe_cls: str) -> bool:
        hist = self._history.get(ppe_cls)
        return any(hist) if hist else False

    def reset(self) -> None:
        for q in self._history.values():
            q.clear()


# ─────────────────────────────────────────────
#  HELPER GEOMETRI
# ─────────────────────────────────────────────

def _iou(a: tuple, b: tuple) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    inter_w = max(0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0, min(ay2, by2) - max(ay1, by1))
    inter   = inter_w * inter_h
    if inter == 0:
        return 0.0
    union = (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter
    return inter / union if union > 0 else 0.0


def scale_coords(
    bbox:       tuple,
    orig_w:     int,
    orig_h:     int,
    model_size: int = MODEL_INPUT_SIZE,
) -> Tuple[int, int, int, int]:
    sx = orig_w / model_size
    sy = orig_h / model_size
    x1, y1, x2, y2 = bbox
    x1 = max(0, min(int(x1*sx), orig_w-1))
    y1 = max(0, min(int(y1*sy), orig_h-1))
    x2 = max(0, min(int(x2*sx), orig_w-1))
    y2 = max(0, min(int(y2*sy), orig_h-1))
    return (x1, y1, x2, y2)


# ─────────────────────────────────────────────
#  CLASS-WISE NMS
# ─────────────────────────────────────────────

def _apply_class_nms(
    detections:    List[Detection],
    iou_threshold: float = NMS_IOU_THRESHOLD,
) -> List[Detection]:
    result  = []
    classes = list({d.class_name for d in detections})
    for cls in classes:
        cls_dets = [d for d in detections if d.class_name == cls]
        if len(cls_dets) <= 1:
            result.extend(cls_dets)
            continue
        sorted_dets = sorted(cls_dets, key=lambda d: d.confidence, reverse=True)
        keep = []
        while sorted_dets:
            best = sorted_dets.pop(0)
            keep.append(best)
            sorted_dets = [d for d in sorted_dets
                           if _iou(best.bbox, d.bbox) < iou_threshold]
        result.extend(keep)
    return result


# ─────────────────────────────────────────────
#  CONFLICT RESOLUTION
#  Satu bbox helmet + satu no_helmet bertumpuk →
#  buang yang confidence-nya lebih rendah
# ─────────────────────────────────────────────

_CONFLICT_PAIRS: List[Tuple[str, str]] = [
    ("helmet",  "no_helmet"),
    ("goggles", "no_goggle"),
    ("gloves",  "no_gloves"),
    ("boots",   "no_boots"),
]

def resolve_conflicts(detections: List[Detection]) -> List[Detection]:
    to_remove: Set[int] = set()
    for pos_cls, neg_cls in _CONFLICT_PAIRS:
        pos_list = [(i, d) for i, d in enumerate(detections) if d.class_name == pos_cls]
        neg_list = [(j, d) for j, d in enumerate(detections) if d.class_name == neg_cls]
        for (i, pd) in pos_list:
            for (j, nd) in neg_list:
                if _iou(pd.bbox, nd.bbox) >= CONFLICT_IOU_THRESH:
                    if pd.confidence >= nd.confidence:
                        to_remove.add(j)
                    else:
                        to_remove.add(i)
    return [d for i, d in enumerate(detections) if i not in to_remove]


# ─────────────────────────────────────────────
#  VALIDASI APD: POSITIF & NEGATIF
# ─────────────────────────────────────────────

def _check_positive(
    person_bbox: tuple,
    ppe_dets:    List[Detection],
    ppe_cls:     str,
) -> bool:
    """Apakah APD positif ada di sekitar person (overlap + zone)."""
    cfg      = PPE_CONFIG.get(ppe_cls, {"min_overlap": 0.05, "use_zone": False})
    min_ov   = cfg["min_overlap"]
    use_zone = cfg["use_zone"]
    for det in ppe_dets:
        if det.class_name != ppe_cls or det.confidence < MIN_PPE_CONF:
            continue
        if overlap_ratio(det.bbox, person_bbox) >= min_ov:
            return True
        if use_zone and bbox_center_inside_zone(
            person_bbox, det.bbox,
            HEAD_Y_ZONES[ppe_cls], HEAD_X_ZONES[ppe_cls],
        ):
            return True
    return False


def _check_negative(
    person_bbox: tuple,
    neg_dets:    List[Detection],
    neg_cls:     Optional[str],
) -> bool:
    """Apakah kelas negatif APD terdeteksi di sekitar person."""
    if neg_cls is None:
        return False
    pos_cls  = NEGATIVE_TO_POSITIVE.get(neg_cls)
    min_ov   = PPE_CONFIG.get(pos_cls, {"min_overlap": 0.08})["min_overlap"] if pos_cls else 0.08
    use_zone = neg_cls in ("no_helmet", "no_goggle")
    for det in neg_dets:
        if det.class_name != neg_cls or det.confidence < MIN_NEG_CONF:
            continue
        if overlap_ratio(det.bbox, person_bbox) >= min_ov:
            return True
        if use_zone and bbox_center_inside_zone(
            person_bbox, det.bbox,
            NEG_HEAD_Y_ZONES.get(neg_cls, (0.0, 0.45)),
            NEG_HEAD_X_ZONES.get(neg_cls, (0.15, 0.85)),
        ):
            return True
    return False


# ─────────────────────────────────────────────
#  STATUS APD PER PERSON — DENGAN TEMPORAL SMOOTHING
# ─────────────────────────────────────────────

def get_person_ppe_status(
    person_det:   Detection,
    all_dets:     List[Detection],
    frame_height: int,
    tracker:      PPEVisualTracker,
) -> Dict[str, bool]:
    """
    Dual-mode detection:
      Mode A (primer) : kelas negatif terdeteksi -> langgar
      Mode B (sekunder): kelas positif tidak ada -> langgar
    Semua 5 APD wajib -- tidak ada pengecualian.
    Temporal smoothing: jika raw=langgar tapi memory ada -> tetap patuh.

    Return: {ppe_cls: True=patuh / False=langgar}
    """
    ppe_dets = [d for d in all_dets if d.class_name in PPE_POSITIVE_CLASSES]
    neg_dets = [d for d in all_dets if d.class_name in PPE_NEGATIVE_CLASSES]

    raw: Dict[str, bool] = {}
    for ppe_cls in REQUIRED_PPE:
        neg_cls  = POSITIVE_TO_NEGATIVE.get(ppe_cls)
        has_neg  = _check_negative(person_det.bbox, neg_dets, neg_cls) if neg_cls else False
        has_pos  = _check_positive(person_det.bbox, ppe_dets, ppe_cls)
        raw[ppe_cls] = not (has_neg or (not has_pos))

    # Update tracker dengan status raw
    tracker.update(raw)

    # Gabung raw + temporal: APD yang sesaat hilang masih dianggap ada
    final: Dict[str, bool] = {}
    for ppe_cls in REQUIRED_PPE:
        if raw[ppe_cls]:
            final[ppe_cls] = True
        elif tracker.is_present(ppe_cls):
            final[ppe_cls] = True   # temporal save
        else:
            final[ppe_cls] = False
    return final


# ─────────────────────────────────────────────
#  HITUNG VIOLATION BBOX PER BODY-PART
#
#  INTI FITUR v6.1 — bbox violation ditempatkan di zona tubuh
#  yang sebenarnya kurang APD, bukan seluruh person bbox.
#
#  Prioritas sumber bbox (akurasi tertinggi → terendah):
#    1. Bbox kelas negatif dari model (no_helmet, no_goggle, dst.)
#       → Langsung dari deteksi model, akurasi ~mAP model itu sendiri
#    2. Body-part zone kalkulasi dari person bbox
#       → Fallback deterministik berdasarkan anatomi
# ─────────────────────────────────────────────

def compute_violation_bboxes(
    person_det:  Detection,
    all_dets:    List[Detection],
    missing_ppe: List[str],
    frame_w:     int,
    frame_h:     int,
) -> Dict[str, Tuple[int, int, int, int]]:
    """
    Hitung bbox pelanggaran untuk setiap APD yang hilang.
    Return: {ppe_cls: (x1, y1, x2, y2)} koordinat frame asli.
    """
    px1, py1, px2, py2 = person_det.bbox
    pw  = max(px2 - px1, 1)
    ph  = max(py2 - py1, 1)
    result: Dict[str, Tuple[int, int, int, int]] = {}
    neg_dets = [d for d in all_dets if d.class_name in PPE_NEGATIVE_CLASSES]

    for ppe_cls in missing_ppe:
        pad     = ZONE_PADDING.get(ppe_cls, 6)
        neg_cls = POSITIVE_TO_NEGATIVE.get(ppe_cls)

        # ── Prioritas 1: bbox kelas negatif dari model ──────────────────
        best_neg = None
        best_ov  = -1.0
        if neg_cls:
            for nd in neg_dets:
                if nd.class_name != neg_cls or nd.confidence < MIN_NEG_CONF:
                    continue
                ov = overlap_ratio(nd.bbox, person_det.bbox)
                pos_cls = NEGATIVE_TO_POSITIVE.get(neg_cls, "helmet")
                min_ov  = PPE_CONFIG.get(pos_cls, {"min_overlap": 0.05})["min_overlap"]
                if ov > best_ov and ov >= min_ov:
                    best_ov  = ov
                    best_neg = nd

        if best_neg is not None:
            nx1, ny1, nx2, ny2 = best_neg.bbox
            result[ppe_cls] = (
                max(0,       nx1 - pad),
                max(0,       ny1 - pad),
                min(frame_w, nx2 + pad),
                min(frame_h, ny2 + pad),
            )
            continue

        # ── Prioritas 2: kalkulasi body-part zone ───────────────────────
        zy0, zy1 = BODY_ZONE_Y.get(ppe_cls, (0.0, 1.0))
        zx0, zx1 = BODY_ZONE_X.get(ppe_cls, (0.0, 1.0))

        bx1 = max(0,       int(px1 + zx0 * pw) - pad)
        by1 = max(0,       int(py1 + zy0 * ph) - pad)
        bx2 = min(frame_w, int(px1 + zx1 * pw) + pad)
        by2 = min(frame_h, int(py1 + zy1 * ph) + pad)

        if bx2 > bx1 and by2 > by1:
            result[ppe_cls] = (bx1, by1, bx2, by2)

    return result


# ─────────────────────────────────────────────
#  ONNX DECODER — FORMAT A & B AUTO-DETECT
# ─────────────────────────────────────────────

def _decode_onnx_output(
    raw:         np.ndarray,
    num_classes: int,
    conf_thresh: float,
    orig_w:      int,
    orig_h:      int,
    model_size:  int = MODEL_INPUT_SIZE,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Decode raw ONNX output ke boxes/scores/labels.
    Auto-detect Format A (4+C kolom) dan Format B (5+C, YOLOv5-style).
    """
    out = raw[0] if raw.ndim == 3 else raw
    if out.shape[0] < out.shape[1]:
        out = out.T   # (C,N) → (N,C)

    n_cols = out.shape[1]
    if n_cols == 4 + num_classes:
        cls_start = 4;  obj_col = None
    elif n_cols == 5 + num_classes:
        cls_start = 5;  obj_col = 4
    else:
        cls_start = 4;  obj_col = None   # fallback

    cls_scores = out[:, cls_start:cls_start+num_classes]
    if obj_col is not None:
        cls_scores = cls_scores * out[:, obj_col:obj_col+1]

    scores = cls_scores.max(axis=1)
    labels = cls_scores.argmax(axis=1).astype(np.int32)
    mask   = scores >= conf_thresh
    out    = out[mask];  scores = scores[mask];  labels = labels[mask]

    if len(scores) == 0:
        return (np.zeros((0,4),dtype=np.float32),
                np.zeros(0,dtype=np.float32),
                np.zeros(0,dtype=np.int32))

    cx = out[:,0];  cy = out[:,1];  bw = out[:,2];  bh = out[:,3]
    sx = orig_w / model_size;  sy = orig_h / model_size
    x1 = np.clip((cx - bw*0.5)*sx, 0, orig_w)
    y1 = np.clip((cy - bh*0.5)*sy, 0, orig_h)
    x2 = np.clip((cx + bw*0.5)*sx, 0, orig_w)
    y2 = np.clip((cy + bh*0.5)*sy, 0, orig_h)
    boxes = np.stack([x1, y1, x2, y2], axis=1).astype(np.float32)
    return boxes, scores.astype(np.float32), labels


# ─────────────────────────────────────────────
#  PIPELINE UTAMA
# ─────────────────────────────────────────────

class APDInferencePipeline:

    def __init__(
        self,
        model_path:      str           = "best.pt",
        confidence:      float         = 0.30,
        iou:             float         = 0.45,
        camera_id:       str           = "EPSON_CAM_01",
        output_dir:      str           = "inference_output",
        device:          str           = "cpu",
        skip_frames:     int           = 1,
        backend_url:     Optional[str] = None,
        use_onnx:        bool          = False,
        temporal_window: int           = TEMPORAL_WINDOW,
    ):
        self._print_banner()
        self.use_onnx        = use_onnx
        self.conf            = confidence
        self.iou_thresh      = iou
        self.device          = device
        self.skip_frames     = skip_frames
        self.camera_id       = camera_id
        self.output_dir      = Path(output_dir)
        self.temporal_window = temporal_window

        print(f"[INFO] Loading model  : {model_path}")
        if use_onnx:
            self._load_onnx(model_path)
        else:
            if not HAS_ULTRALYTICS:
                raise ImportError("pip install ultralytics")
            self.model = YOLO(model_path)
            self._verify_classes()

        self.violation_logic = ViolationLogic(
            camera_id        = camera_id,
            output_dir       = str(self.output_dir / "violations"),
            save_screenshots = True,
            log_to_file      = True,
            backend_url      = backend_url,
            temporal_window  = temporal_window,
        )
        self.ppe_tracker = PPEVisualTracker(window=temporal_window)
        self.frame_count = 0
        self.fps_display = 0.0
        self.class_count = {name: 0 for name in CLASS_NAMES.values()}

        print(f"[INFO] Confidence     : {confidence}")
        print(f"[INFO] IoU NMS        : {NMS_IOU_THRESHOLD}")
        print(f"[INFO] Temporal window: {temporal_window} frame")
        print(f"[INFO] Device         : {device}")
        print(f"[INFO] Skip frames    : {skip_frames}")
        print(f"[INFO] Backend        : {backend_url or 'OFF'}")
        print(f"[INFO] Format         : {'ONNX' if use_onnx else 'PyTorch .pt'}")
        print(f"[INFO] Output         : {self.output_dir.resolve()}\n")

    # ── LOAD ─────────────────────────────────

    def _load_onnx(self, model_path: str):
        if not HAS_ONNX:
            raise ImportError("pip install onnxruntime")
        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if self.device != "cpu" else ["CPUExecutionProvider"]
        )
        self.ort_session    = ort.InferenceSession(model_path, providers=providers)
        self.ort_input_name = self.ort_session.get_inputs()[0].name
        self.model          = None
        print(f"[INFO] ONNX providers : {self.ort_session.get_providers()}")

    def _verify_classes(self):
        mismatch = [
            f"  class {cid}: expected '{nm}', got '{self.model.names.get(cid,'???')}'"
            for cid, nm in CLASS_NAMES.items()
            if self.model.names.get(cid) != nm
        ]
        if mismatch:
            print("[WARN] Class mismatch:")
            for m in mismatch:
                print(m)
        else:
            print("[INFO] Class names    : ✓ semua 11 kelas sesuai")

    # ── INFERENCE ────────────────────────────

    def run_inference(self, frame: np.ndarray) -> List[Detection]:
        orig_h, orig_w = frame.shape[:2]
        if self.use_onnx:
            return self._run_onnx(frame, orig_w, orig_h)
        else:
            return self._run_yolo(frame, orig_w, orig_h)

    def _run_yolo(self, frame, orig_w, orig_h) -> List[Detection]:
        inp = (cv2.resize(frame, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
               if (orig_w != MODEL_INPUT_SIZE or orig_h != MODEL_INPUT_SIZE)
               else frame)
        results    = self.model(inp, conf=self.conf, iou=self.iou_thresh,
                                device=self.device, verbose=False)
        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cid   = int(box.cls[0].item())
                cname = CLASS_NAMES.get(cid, f"class_{cid}")
                conf  = float(box.conf[0].item())
                raw   = tuple(float(v) for v in box.xyxy[0].tolist())
                x1, y1, x2, y2 = scale_coords(raw, orig_w, orig_h)
                if x2 <= x1 or y2 <= y1:
                    continue
                detections.append(Detection(cname, conf, (x1, y1, x2, y2)))
                self.class_count[cname] = self.class_count.get(cname, 0) + 1
        return _apply_class_nms(detections, NMS_IOU_THRESHOLD)

    def _run_onnx(self, frame, orig_w, orig_h) -> List[Detection]:
        img = cv2.resize(frame, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))[np.newaxis, :]
        raw_out = self.ort_session.run(None, {self.ort_input_name: img})[0]
        boxes, scores, labels = _decode_onnx_output(
            raw_out, num_classes=len(CLASS_NAMES),
            conf_thresh=self.conf, orig_w=orig_w, orig_h=orig_h,
        )
        detections = []
        for i in range(len(scores)):
            cid = int(labels[i])
            cname = CLASS_NAMES.get(cid, f"class_{cid}")
            x1, y1, x2, y2 = (int(v) for v in boxes[i])
            if x2 <= x1 or y2 <= y1:
                continue
            detections.append(Detection(cname, float(scores[i]), (x1, y1, x2, y2)))
            self.class_count[cname] = self.class_count.get(cname, 0) + 1
        return _apply_class_nms(detections, NMS_IOU_THRESHOLD)

    # ── PROSES FRAME ─────────────────────────

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        raw_dets = self.run_inference(frame)
        dets     = resolve_conflicts(raw_dets)
        events   = self.violation_logic.process(
            detections   = dets,
            frame        = frame,
            frame_number = self.frame_count,
        )
        return self.draw_frame(frame, dets, events)

    # ── VISUALISASI ──────────────────────────

    def draw_frame(
        self,
        frame:      np.ndarray,
        detections: List[Detection],
        events:     List[ViolationEvent],
    ) -> np.ndarray:
        """
        LOGIKA RENDERING v6.1:

        Patuh sempurna  → tidak ada bbox apapun di tubuhnya (frame bersih)
        Melanggar       → hanya bbox violation di body-part yang bermasalah

        Contoh: pakai helm+rompi tapi tanpa sarung tangan
          → Hanya bbox 'NO GLOVES' di zona lengan/tangan yang muncul
          → Tidak ada bbox lain di orang itu

        Panel status APD tetap di kanan atas.
        Banner pelanggaran muncul di bawah saat ada event aktif.
        """
        vis = frame.copy()
        fh, fw = vis.shape[:2]

        person_dets = [d for d in detections if d.class_name == "Person"]

        # Hitung status APD per person
        person_statuses: Dict[int, Dict[str, bool]] = {}
        for pi, person in enumerate(person_dets):
            if person.confidence < MIN_PERSON_CONF:
                continue
            person_statuses[pi] = get_person_ppe_status(
                person, detections, fh, self.ppe_tracker
            )

        any_violation = False

        for pi, person in enumerate(person_dets):
            if pi not in person_statuses:
                continue

            status  = person_statuses[pi]
            missing = [ppe for ppe, ok in status.items() if not ok]

            if not missing:
                # ── Orang PATUH: tidak ada bbox, frame bersih ───────────
                continue

            # ── Orang MELANGGAR ─────────────────────────────────────────
            any_violation = True

            # Hitung bbox per body-part yang melanggar
            viol_bboxes = compute_violation_bboxes(
                person_det  = person,
                all_dets    = detections,
                missing_ppe = missing,
                frame_w     = fw,
                frame_h     = fh,
            )

            # Gambar setiap violation bbox
            for ppe_cls, vbbox in viol_bboxes.items():
                color = VIOL_COLORS.get(ppe_cls, VIOLATION_COLOR)
                label = PPE_SHORT.get(ppe_cls, f"NO {ppe_cls.upper()}")
                vx1, vy1, vx2, vy2 = vbbox

                # Efek glow halus di tepi luar (transparan)
                glow = vis.copy()
                cv2.rectangle(glow, (vx1-3, vy1-3), (vx2+3, vy2+3), color, -1)
                cv2.addWeighted(glow, 0.08, vis, 0.92, 0, vis)

                # Bbox utama
                cv2.rectangle(vis, (vx1, vy1), (vx2, vy2), color, 2)

                # Label di atas (atau di bawah jika tidak ada ruang)
                self._draw_viol_label(vis, label, vx1, vy1, vx2, color, fw, fh)

            # Tanda merah kecil di pojok kiri atas bbox person
            # (sebagai penanda "ada pelanggaran di sini" — minimalis)
            px1, py1, px2, py2 = person.bbox
            ms = max(10, min(20, int((py2 - py1) * 0.04)))
            cv2.rectangle(vis, (px1, py1), (px1+ms, py1+ms), VIOLATION_COLOR, -1)
            cv2.putText(
                vis, "!",
                (px1 + 3, py1 + ms - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.36,
                (255, 255, 255), 1, cv2.LINE_AA,
            )

        # ── Panel status APD kanan atas ─────────────────────────────────
        self._draw_status_panel(vis, person_statuses, fw, fh)

        # ── HUD info kiri atas ──────────────────────────────────────────
        self._draw_hud(vis, fw, fh, len(person_dets), any_violation)

        # ── Banner pelanggaran bawah ─────────────────────────────────────
        if events:
            unique = list({e.violation_type for e in events})
            names  = ", ".join(t.replace("_", " ").upper() for t in unique)
            modes  = list({e.detection_mode[:3].upper() for e in events})
            ov3    = vis.copy()
            cv2.rectangle(ov3, (0, fh-58), (fw, fh), (0, 0, 120), -1)
            cv2.addWeighted(ov3, 0.82, vis, 0.18, 0, vis)
            cv2.putText(
                vis, f"  ⚠  PELANGGARAN K3: {names}",
                (8, fh-30), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (255, 255, 255), 2, cv2.LINE_AA,
            )
            cv2.putText(
                vis, f"  Deteksi via: {' + '.join(modes)} mode  |  {len(events)} event(s)",
                (8, fh-10), cv2.FONT_HERSHEY_SIMPLEX, 0.40,
                (180, 180, 180), 1, cv2.LINE_AA,
            )

        return vis

    # ── HELPER DRAW ──────────────────────────

    @staticmethod
    def _draw_viol_label(
        vis:   np.ndarray,
        label: str,
        x:     int,
        y:     int,
        x2:    int,
        color: tuple,
        fw:    int,
        fh:    int,
        scale: float = 0.50,
        thick: int   = 1,
    ):
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
        # Jika ada ruang di atas → taruh di atas, jika tidak → di bawah bbox
        if y - th - 8 >= 0:
            lx  = max(0, min(x, fw - tw - 6))
            ly1 = y - th - 8
            ly2 = y - 2
            ty  = y - 4
        else:
            lx  = max(0, min(x, fw - tw - 6))
            ly1 = y + 2
            ly2 = y + th + 8
            ty  = y + th + 4
        cv2.rectangle(vis, (lx, ly1), (lx + tw + 4, ly2), color, -1)
        cv2.putText(vis, label, (lx + 2, ty),
                    font, scale, (255, 255, 255), thick, cv2.LINE_AA)

    def _draw_status_panel(
        self,
        vis:             np.ndarray,
        person_statuses: Dict[int, Dict[str, bool]],
        fw:              int,
        fh:              int,
    ):
        # Agregasi status dari semua person
        agg: Dict[str, str] = {}
        for ppe_cls in REQUIRED_PPE:
            if not person_statuses:
                agg[ppe_cls] = "UNKNOWN"
            elif all(st.get(ppe_cls, True) for st in person_statuses.values()):
                agg[ppe_cls] = "COMPLIANT"
            else:
                agg[ppe_cls] = "VIOLATION"

        panel_w = 222
        n_rows  = len(REQUIRED_PPE) + 1
        panel_h = n_rows * 24 + 14
        px      = fw - panel_w - 6
        py      = 6

        ov = vis.copy()
        cv2.rectangle(ov, (px-4, py), (px+panel_w, py+panel_h), (18, 18, 18), -1)
        cv2.addWeighted(ov, 0.72, vis, 0.28, 0, vis)

        cv2.putText(vis, "STATUS APD — EPSON K3",
                    (px, py+16), cv2.FONT_HERSHEY_SIMPLEX, 0.44,
                    (200, 200, 200), 1, cv2.LINE_AA)

        STATUS_MAP = {
            "COMPLIANT": ("Patuh   ", COMPLIANT_COLOR),
            "VIOLATION": ("LANGGAR!", VIOLATION_COLOR),
            "UNKNOWN":   ("Tdk Ada ", UNKNOWN_COLOR),
        }
        for i, ppe_cls in enumerate(REQUIRED_PPE):
            s        = agg.get(ppe_cls, "UNKNOWN")
            txt, col = STATUS_MAP[s]
            lbl      = PANEL_LABELS.get(ppe_cls, ppe_cls)
            cv2.putText(
                vis, f"{lbl}: {txt}",
                (px, py + 16 + (i+1) * 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 2, cv2.LINE_AA,
            )

    def _draw_hud(
        self,
        vis:           np.ndarray,
        fw:            int,
        fh:            int,
        n_persons:     int,
        any_violation: bool,
    ):
        ov = vis.copy()
        cv2.rectangle(ov, (0, 0), (318, 114), (12, 12, 12), -1)
        cv2.addWeighted(ov, 0.68, vis, 0.32, 0, vis)

        total_v  = self.violation_logic.stats["total_events"]
        neg_hits = self.violation_logic.stats.get("neg_class_hits", 0)
        pos_hits = self.violation_logic.stats.get("pos_absent_hits", 0)
        temp_sv  = self.violation_logic.stats.get("temporal_saves", 0)

        lines = [
            f"Camera  : {self.camera_id}",
            f"Frame   : {self.frame_count}  |  FPS: {self.fps_display:.1f}",
            f"Person  : {n_persons}  |  Total Viol: {total_v}",
            f"NegCls  : {neg_hits}  |  PosAbs: {pos_hits}",
            f"TempSave: {temp_sv}  |  Conf: {self.conf}",
            f"Model   : {'ONNX' if self.use_onnx else 'PT'} | K3 v6.1",
        ]
        for i, ln in enumerate(lines):
            cv2.putText(vis, ln, (8, 18 + i*18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 220), 1, cv2.LINE_AA)

        if any_violation:
            cv2.rectangle(vis, (0, 0), (fw, fh), VIOLATION_COLOR, 3)

    # ── MAIN LOOP ────────────────────────────

    def run(self, source, show_preview: bool = True, save_video: Optional[str] = None):
        if Path(str(source)).is_dir():
            self._run_folder(Path(str(source)), show_preview, save_video)
        else:
            self._run_stream(source, show_preview, save_video)

    def _run_stream(self, source, show_preview: bool, save_video: Optional[str]):
        try:
            src = int(source)
        except (ValueError, TypeError):
            src = str(source)

        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            print(f"[ERROR] Tidak bisa buka source: {source}")
            return

        fps_src = cap.get(cv2.CAP_PROP_FPS) or 25.0
        w_src   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h_src   = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total   = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"[INFO] Source     : {source}")
        print(f"[INFO] Resolusi   : {w_src}x{h_src} @ {fps_src:.1f}fps")
        if total > 0:
            print(f"[INFO] Total frame: {total}")
        print("[INFO] Tekan Q/Esc untuk berhenti, R untuk reset memory.\n")

        writer  = self._init_writer(save_video, fps_src, w_src, h_src)
        t_start = time.perf_counter()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("\n[INFO] Stream selesai.")
                    break

                self.frame_count += 1
                elapsed          = time.perf_counter() - t_start
                self.fps_display = self.frame_count / elapsed if elapsed > 0 else 0.0

                if self.frame_count % self.skip_frames != 0:
                    if show_preview:
                        cv2.imshow("APD Monitor Epson K3 v6.1 [Q=quit]", frame)
                        if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                            break
                    continue

                vis = self._process_frame(frame)

                if show_preview:
                    cv2.imshow("APD Monitor Epson K3 v6.1 [Q=quit]", vis)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (ord("q"), 27):
                        print("\n[INFO] Dihentikan pengguna.")
                        break
                    elif key == ord("r"):
                        self.ppe_tracker.reset()
                        self.violation_logic.reset_memory()
                        print("[INFO] Memory di-reset.")

                if writer:
                    writer.write(vis)

                if self.frame_count % 30 == 0:
                    print(
                        f"\r  Frame={self.frame_count} | FPS={self.fps_display:.1f} | "
                        f"Violations={self.violation_logic.stats['total_events']}   ",
                        end="", flush=True,
                    )
        finally:
            cap.release()
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _run_folder(self, folder: Path, show_preview: bool, save_video: Optional[str]):
        exts      = {".jpg", ".jpeg", ".png", ".bmp"}
        img_files = sorted(p for p in folder.iterdir() if p.suffix.lower() in exts)
        if not img_files:
            print(f"[ERROR] Tidak ada gambar di: {folder}")
            return

        writer  = None
        t_start = time.perf_counter()
        try:
            for i, img_path in enumerate(img_files):
                frame = cv2.imread(str(img_path))
                if frame is None:
                    continue
                self.frame_count += 1
                elapsed          = time.perf_counter() - t_start
                self.fps_display = self.frame_count / elapsed if elapsed > 0 else 0.0

                if save_video and writer is None:
                    hh, ww = frame.shape[:2]
                    writer = self._init_writer(save_video, 10.0, ww, hh)

                vis = self._process_frame(frame)

                if show_preview:
                    cv2.imshow("APD Monitor Epson K3 v6.1 - Folder [Q=quit]", vis)
                    if cv2.waitKey(30) & 0xFF in (ord("q"), 27):
                        break

                if writer:
                    writer.write(vis)

                print(
                    f"\r  [{i+1}/{len(img_files)}] {img_path.name} | "
                    f"Violations={self.violation_logic.stats['total_events']}   ",
                    end="", flush=True,
                )
        finally:
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _init_writer(self, path, fps, w, h) -> Optional[cv2.VideoWriter]:
        if not path:
            return None
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        print(f"[INFO] Simpan video : {path}")
        return cv2.VideoWriter(path, fourcc, max(fps, 1.0), (w, h))

    def _print_banner(self):
        print(f"\n{'='*66}")
        print(f"  APD Inference Pipeline v6.1 — YOLOv11 | Epson Factory K3")
        print(f"  11 Classes: helmet|gloves|vest|boots|goggles|none|Person")
        print(f"              no_helmet|no_goggle|no_gloves|no_boots")
        print(f"  Detection: DUAL MODE + Temporal Smoothing + Conflict Resolve")
        print(f"  BBox     : VIOLATION-ONLY — body-part anchor zone per APD")
        print(f"  Standard : Epson K3 — 5 APD Wajib")
        print(f"{'='*66}")

    def _print_summary(self):
        print(f"\n\n{'='*66}")
        print(f"  RINGKASAN INFERENCE  [v6.1 Epson K3]")
        print(f"{'='*66}")
        print(f"  Total frame diproses : {self.frame_count}")
        print(f"\n  Deteksi per kelas:")
        for cname, count in self.class_count.items():
            if count > 0:
                bar = "x" * min(count // 10, 28)
                print(f"    {cname:<15}: {count:>6}  {bar}")
        self.violation_logic.print_summary()


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="APD Inference v6.1 — Epson Factory K3 | Smart Violation BBox",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Contoh:
  python inference.py --source 0 --model best.pt --no-backend
  python inference.py --source video.mp4 --model best.pt --skip 2 --no-backend
  python inference.py --source rtsp://192.168.1.100:554/stream --model best.pt
  python inference.py --source 0 --model best.pt --conf 0.35 --no-backend
  python inference.py --source 0 --model best.pt --save-video out.mp4 --no-backend
  python inference.py --source 0 --model best.onnx --use-onnx --no-backend
  python inference.py --source images/ --model best.pt --no-backend
        """,
    )
    p.add_argument("--source",           required=True,
                   help="Sumber: 0=webcam, path video/folder, RTSP URL")
    p.add_argument("--model",            default="best.pt")
    p.add_argument("--conf",             type=float, default=0.30)
    p.add_argument("--iou",              type=float, default=0.45)
    p.add_argument("--device",           default="cpu", help="cpu / cuda:0")
    p.add_argument("--camera-id",        default="EPSON_CAM_01")
    p.add_argument("--output",           default="inference_output")
    p.add_argument("--skip",             type=int, default=1,
                   help="Proses setiap N frame (default: 1)")
    p.add_argument("--save-video",       default=None)
    p.add_argument("--no-preview",       action="store_true")
    p.add_argument("--backend-url",      default="http://localhost:8000")
    p.add_argument("--no-backend",       action="store_true")
    p.add_argument("--use-onnx",         action="store_true")
    p.add_argument("--temporal-window",  type=int, default=TEMPORAL_WINDOW,
                   help=f"Temporal smoothing window frame (default: {TEMPORAL_WINDOW})")
    return p.parse_args()


if __name__ == "__main__":
    args     = parse_args()
    pipeline = APDInferencePipeline(
        model_path      = args.model,
        confidence      = args.conf,
        iou             = args.iou,
        camera_id       = args.camera_id,
        output_dir      = args.output,
        device          = args.device,
        skip_frames     = args.skip,
        backend_url     = None if args.no_backend else args.backend_url,
        use_onnx        = args.use_onnx,
        temporal_window = args.temporal_window,
    )
    pipeline.run(
        source       = args.source,
        show_preview = not args.no_preview,
        save_video   = args.save_video,
    )