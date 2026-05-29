"""
inference.py  [v5.0 — Epson Factory K3 | 11-Class Dual Detection]
==================================================================
Pipeline inference real-time YOLOv11 untuk deteksi APD K3 Epson.

Kelas model best.pt (11 kelas aktual):
    0: helmet        → HIJAU TERANG  (APD hadir)
    1: gloves        → UNGU          (APD hadir)
    2: vest          → BIRU MUDA     (APD hadir)
    3: boots         → KUNING        (APD hadir)
    4: goggles       → CYAN          (APD hadir)
    5: none          → ABU-ABU       (tidak ada APD)
    6: Person        → ORANYE (patuh) / MERAH CERAH (langgar)
    7: no_helmet     → MERAH CERAH   (langsung trigger violation)
    8: no_goggle     → MERAH CERAH   (langsung trigger violation)
    9: no_gloves     → MERAH CERAH   (langsung trigger violation)
   10: no_boots      → MERAH CERAH   (langsung trigger violation)

Strategi Deteksi v5.0 — DUAL MODE:
  Mode A (PRIMER)  : Kelas negatif (no_helmet, dll) langsung = VIOLATION
  Mode B (SEKUNDER): Kelas positif tidak ditemukan di sekitar Person = VIOLATION

Standard K3 Epson: Helm + Rompi + Sepatu + Goggle + Sarung Tangan

Cara pakai:
  python inference.py --source 0 --model best.pt --no-backend
  python inference.py --source video.mp4 --model best.pt --skip 2 --no-backend
  python inference.py --source rtsp://ip:port/stream --model best.pt
  python inference.py --source 0 --model best.pt --save-video out.mp4 --no-backend
  python inference.py --source 0 --model best.onnx --use-onnx --no-backend
"""

import cv2
import time
import argparse
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple

# ── Import violation_logic v5.0 ───────────────────────────────────
from violation_logic import (
    ViolationLogic,
    Detection,
    ViolationEvent,
    CLASS_NAMES,
    REQUIRED_PPE,
    ALL_PPE,
    Y_ZONES,
    MIN_OVERLAP,
    MIN_PERSON_CONF,
    MIN_PPE_CONF,
    PARTIAL_PERSON_RATIO,
    PANEL_LABELS,
    VIOLATION_COLOR,
    COMPLIANT_COLOR,
    UNKNOWN_COLOR,
    WARNING_COLOR,
    PPE_POSITIVE_CLASSES,
    PPE_NEGATIVE_CLASSES,
    PPE_DISPLAY_NAMES,
    get_person_ppe_dict,
    is_partial_person,
    overlap_ratio,
    bbox_center,
)

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError("Install dulu: pip install ultralytics")


# ─────────────────────────────────────────────
#  WARNA PER KELAS (BGR)
# ─────────────────────────────────────────────

CLASS_COLORS = {
    "helmet":   (  0, 210,   0),   # hijau terang
    "gloves":   (210,   0, 210),   # ungu
    "vest":     (255, 185,   0),   # biru muda
    "boots":    (  0, 210, 210),   # kuning
    "goggles":  (210, 210,   0),   # cyan
    "none":     (130, 130, 130),   # abu-abu
    "Person":   (  0, 165, 255),   # oranye
    "no_helmet": (0,  0, 255),
    "no_goggle": (0,  0, 255),
    "no_gloves": (0,  0, 255),
    "no_boots":  (0,  0, 255),
}

PERSON_VIOLATION_COLOR = VIOLATION_COLOR   # (0, 0, 255) merah cerah
LABEL_FG               = (255, 255, 255)   # teks putih

MODEL_INPUT_SIZE  = 640
NMS_IOU_THRESHOLD = 0.45


# ─────────────────────────────────────────────
#  SCALE COORDINATES
# ─────────────────────────────────────────────

def scale_coords(
    bbox:       Tuple,
    orig_w:     int,
    orig_h:     int,
    model_size: int = MODEL_INPUT_SIZE,
) -> Tuple[int, int, int, int]:
    """
    Konversi koordinat dari ruang model (640×640) ke resolusi frame asli.
    WAJIB dipanggil sebelum membuat objek Detection agar posisi bbox akurat.
    """
    scale_x = orig_w / model_size
    scale_y = orig_h / model_size

    x1, y1, x2, y2 = bbox
    x1 = int(x1 * scale_x);  y1 = int(y1 * scale_y)
    x2 = int(x2 * scale_x);  y2 = int(y2 * scale_y)

    x1 = max(0, min(x1, orig_w - 1))
    y1 = max(0, min(y1, orig_h - 1))
    x2 = max(0, min(x2, orig_w - 1))
    y2 = max(0, min(y2, orig_h - 1))

    return (x1, y1, x2, y2)


# ─────────────────────────────────────────────
#  NMS PER KELAS
# ─────────────────────────────────────────────

def _iou(boxA: tuple, boxB: tuple) -> float:
    ax1, ay1, ax2, ay2 = boxA
    bx1, by1, bx2, by2 = boxB
    ix1 = max(ax1, bx1);  iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2);  iy2 = min(ay2, by2)
    inter = float(max(0, ix2 - ix1) * max(0, iy2 - iy1))
    if inter == 0:
        return 0.0
    areaA = float((ax2 - ax1) * (ay2 - ay1))
    areaB = float((bx2 - bx1) * (by2 - by1))
    union = areaA + areaB - inter
    return inter / union if union > 0 else 0.0


def _apply_class_nms(
    detections:    List[Detection],
    iou_threshold: float = NMS_IOU_THRESHOLD,
) -> List[Detection]:
    """NMS per kelas → hilangkan bbox duplikat."""
    result  = []
    classes = list({d.class_name for d in detections})

    for cls in classes:
        cls_dets = [d for d in detections if d.class_name == cls]
        if len(cls_dets) <= 1:
            result.extend(cls_dets)
            continue
        try:
            import torch
            from torchvision.ops import nms as tv_nms
            boxes  = torch.tensor([list(d.bbox) for d in cls_dets], dtype=torch.float32)
            scores = torch.tensor([d.confidence for d in cls_dets], dtype=torch.float32)
            keep   = tv_nms(boxes, scores, iou_threshold).tolist()
            result.extend([cls_dets[i] for i in keep])
        except ImportError:
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
#  STATUS VISUAL APD BBOX
# ─────────────────────────────────────────────

def _get_ppe_visual_status(
    ppe_det:      Detection,
    person_dets:  List[Detection],
    frame_height: int,
) -> str:
    """
    Return "valid" jika APD berada di dalam bbox person,
    "orphan" jika tidak ada person yang cocok.
    """
    if not person_dets:
        return "orphan"

    # Kelas negatif selalu tampil sebagai "valid" jika ada person di dekatnya
    is_negative = ppe_det.class_name in PPE_NEGATIVE_CLASSES

    cx, cy   = bbox_center(ppe_det.bbox)
    y_zone   = Y_ZONES.get(ppe_det.class_name, (0.0, 1.0))

    for person in person_dets:
        px1, py1, px2, py2 = person.bbox
        person_h = py2 - py1
        if person_h <= 0:
            continue

        inside_x  = px1 <= cx <= px2
        inside_y  = py1 <= cy <= py2
        y_min_abs = py1 + y_zone[0] * person_h
        y_max_abs = py1 + y_zone[1] * person_h

        if inside_x and inside_y:
            if is_negative or (y_min_abs <= cy <= y_max_abs):
                return "valid"

        if (overlap_ratio(ppe_det.bbox, person.bbox) >= MIN_OVERLAP):
            if is_negative or (y_min_abs <= cy <= y_max_abs):
                return "valid"

    return "orphan"


# ─────────────────────────────────────────────
#  PIPELINE UTAMA
# ─────────────────────────────────────────────

class APDInferencePipeline:

    def __init__(
        self,
        model_path:   str           = "best.pt",
        confidence:   float         = 0.30,
        iou:          float         = 0.45,
        camera_id:    str           = "EPSON_CAM_01",
        output_dir:   str           = "inference_output",
        device:       str           = "cpu",
        skip_frames:  int           = 1,
        backend_url:  Optional[str] = "https://localhost:8000",
        use_onnx:     bool          = False,
        service_key:  str           = "",
    ):
        self._print_banner()
        self.use_onnx    = use_onnx
        self.conf        = confidence
        self.iou_thresh  = iou
        self.device      = device
        self.skip_frames = skip_frames
        self.camera_id   = camera_id
        self.output_dir  = Path(output_dir)

        print(f"[INFO] Loading model  : {model_path}")
        if use_onnx:
            self._load_onnx(model_path)
        else:
            self.model = YOLO(model_path)
            self._verify_classes()

        self.violation_logic = ViolationLogic(
            camera_id        = camera_id,
            output_dir       = str(self.output_dir / "violations"),
            save_screenshots = True,
            log_to_file      = True,
            backend_url      = backend_url,
            service_key      = service_key,
        )

        self.frame_count = 0
        self.fps_display = 0.0
        self.class_count = {name: 0 for name in CLASS_NAMES.values()}

        print(f"[INFO] Confidence     : {confidence}")
        print(f"[INFO] IoU NMS        : {NMS_IOU_THRESHOLD}")
        print(f"[INFO] Input size     : {MODEL_INPUT_SIZE}px")
        print(f"[INFO] Partial ratio  : {PARTIAL_PERSON_RATIO}")
        print(f"[INFO] Device         : {device}")
        print(f"[INFO] Skip frames    : {skip_frames}")
        print(f"[INFO] Backend        : {backend_url or 'OFF'}")
        print(f"[INFO] Format         : {'ONNX' if use_onnx else 'PyTorch .pt'}")
        print(f"[INFO] Output         : {self.output_dir.resolve()}\n")

    # ─────────────────────────────────────────
    #  LOAD ONNX
    # ─────────────────────────────────────────

    def _load_onnx(self, model_path: str):
        """Load model via ONNX Runtime (lebih cepat di CPU)."""
        try:
            import onnxruntime as ort
        except ImportError:
            raise ImportError("Install dulu: pip install onnxruntime")

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"] \
                    if self.device != "cpu" else ["CPUExecutionProvider"]
        self.ort_session = ort.InferenceSession(model_path, providers=providers)
        self.ort_input_name  = self.ort_session.get_inputs()[0].name
        self.model = None
        print(f"[INFO] ONNX Runtime   : {ort.__version__}")
        print(f"[INFO] Providers      : {self.ort_session.get_providers()}")

    # ─────────────────────────────────────────
    #  VERIFIKASI KELAS
    # ─────────────────────────────────────────

    def _verify_classes(self):
        model_names = self.model.names
        expected    = CLASS_NAMES  # {0:'helmet', 1:'gloves', ... 10:'no_boots'}
        mismatch    = [
            f"  class {cid}: expected '{nm}', got '{model_names.get(cid, '???')}'"
            for cid, nm in expected.items()
            if model_names.get(cid) != nm
        ]
        print(f"[INFO] Model classes  : {model_names}")
        if mismatch:
            print("[WARN] Class mismatch — cek CLASS_NAMES di violation_logic.py:")
            for m in mismatch:
                print(m)
        else:
            print("[INFO] Class names    : ✓ semua 11 kelas sesuai")

    # ─────────────────────────────────────────
    #  INFERENCE + SCALE + NMS
    # ─────────────────────────────────────────

    def run_inference(self, frame: np.ndarray) -> List[Detection]:
        orig_h, orig_w = frame.shape[:2]

        if self.use_onnx:
            return self._run_onnx(frame, orig_w, orig_h)
        else:
            return self._run_yolo(frame, orig_w, orig_h)

    def _run_yolo(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[Detection]:
        """Inference via Ultralytics YOLO (.pt)."""
        if orig_w != MODEL_INPUT_SIZE or orig_h != MODEL_INPUT_SIZE:
            frame_inp = cv2.resize(frame, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
        else:
            frame_inp = frame

        results    = self.model(
            frame_inp,
            conf    = self.conf,
            iou     = self.iou_thresh,
            device  = self.device,
            verbose = False,
        )
        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cid   = int(box.cls[0].item())
                cname = CLASS_NAMES.get(cid, f"class_{cid}")
                conf  = float(box.conf[0].item())

                raw_bbox         = tuple(float(v) for v in box.xyxy[0].tolist())
                x1, y1, x2, y2  = scale_coords(raw_bbox, orig_w, orig_h)

                if x2 <= x1 or y2 <= y1:
                    continue

                detections.append(Detection(
                    class_name = cname,
                    confidence = conf,
                    bbox       = (x1, y1, x2, y2),
                ))
                self.class_count[cname] = self.class_count.get(cname, 0) + 1

        return _apply_class_nms(detections, NMS_IOU_THRESHOLD)

    def _run_onnx(self, frame: np.ndarray, orig_w: int, orig_h: int) -> List[Detection]:
        """Inference via ONNX Runtime (.onnx) — lebih cepat di CPU."""
        img = cv2.resize(frame, (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE))
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        img = np.transpose(img, (2, 0, 1))[np.newaxis, :]  # NCHW

        outputs = self.ort_session.run(None, {self.ort_input_name: img})
        # YOLOv8/v11 ONNX output: [1, num_classes+4, num_anchors]
        preds = outputs[0][0]  # [84, 8400] atau [15, 8400] tergantung model

        detections = []
        num_classes = preds.shape[0] - 4
        preds_t     = preds.T  # [8400, 84]

        for row in preds_t:
            boxes  = row[:4]
            scores = row[4:]
            cid    = int(np.argmax(scores))
            conf   = float(scores[cid])

            if conf < self.conf:
                continue

            cx, cy, bw, bh = boxes
            x1 = float(cx - bw / 2)
            y1 = float(cy - bh / 2)
            x2 = float(cx + bw / 2)
            y2 = float(cy + bh / 2)

            cname           = CLASS_NAMES.get(cid, f"class_{cid}")
            x1, y1, x2, y2 = scale_coords((x1, y1, x2, y2), orig_w, orig_h)

            if x2 <= x1 or y2 <= y1:
                continue

            detections.append(Detection(
                class_name = cname,
                confidence = conf,
                bbox       = (x1, y1, x2, y2),
            ))
            self.class_count[cname] = self.class_count.get(cname, 0) + 1

        return _apply_class_nms(detections, NMS_IOU_THRESHOLD)

    # ─────────────────────────────────────────
    #  PROSES FRAME
    # ─────────────────────────────────────────

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        detections = self.run_inference(frame)
        events     = self.violation_logic.process(
            detections   = detections,
            frame        = frame,
            frame_number = self.frame_count,
        )
        apd_status = self.violation_logic.get_frame_status(
            detections   = detections,
            frame_height = frame.shape[0],
        )
        return self.draw_frame(frame, detections, events, apd_status)

    # ─────────────────────────────────────────
    #  VISUALISASI
    # ─────────────────────────────────────────

    def draw_frame(
        self,
        frame:      np.ndarray,
        detections: List[Detection],
        events:     List[ViolationEvent],
        apd_status: dict,
    ) -> np.ndarray:
        """
        Layer render (bawah → atas):
          1. Bbox APD positif  — warna kelas
          2. Bbox APD negatif  — merah + label
          3. Bbox Person       — oranye/merah + label APD missing
          4. Panel info kiri atas
          5. Panel status K3 kanan atas  (5 APD Epson)
          6. Banner pelanggaran bawah
        """
        vis = frame.copy()
        h, w = vis.shape[:2]

        person_dets  = [d for d in detections if d.class_name == "Person"]
        ppe_pos_dets = [d for d in detections if d.class_name in PPE_POSITIVE_CLASSES]
        ppe_neg_dets = [d for d in detections if d.class_name in PPE_NEGATIVE_CLASSES]
        none_dets    = [d for d in detections if d.class_name == "none"]

        # ── Layer 1: Bbox APD positif ─────────────────────────────────────
        for det in ppe_pos_dets:
            color  = CLASS_COLORS.get(det.class_name, (180, 180, 180))
            status = _get_ppe_visual_status(det, person_dets, h)

            if status == "valid":
                self._draw_bbox(vis, det, color, thickness=2)
            else:
                # Orphan: tetap berwarna tapi outline tipis
                x1, y1, x2, y2 = det.bbox
                cv2.rectangle(vis, (x1, y1), (x2, y2), color, 1)
                lbl = f"{det.class_name} {det.confidence:.2f}"
                self._draw_label(vis, lbl, x1, y1, color, scale=0.38)

        # ── Layer 2: Bbox APD negatif (MERAH) ────────────────────────────
        for det in ppe_neg_dets:
            x1, y1, x2, y2 = det.bbox
            # Garis putus-putus merah untuk kelas negatif (lebih tebal)
            cv2.rectangle(vis, (x1, y1), (x2, y2), VIOLATION_COLOR, 2)
            lbl = f"!{det.class_name.upper()} {det.confidence:.2f}"
            self._draw_label(vis, lbl, x1, y1, VIOLATION_COLOR, scale=0.42)

        # ── Layer 3: Bbox Person ──────────────────────────────────────────
        for det in person_dets:
            x1, y1, x2, y2 = det.bbox
            ppe_status   = get_person_ppe_dict(det, detections, frame_height=h)
            is_violating = any(not ppe_status.get(ppe, False) for ppe in REQUIRED_PPE)
            partial      = is_partial_person(det.bbox, h)

            color = PERSON_VIOLATION_COLOR if is_violating else CLASS_COLORS["Person"]
            thick = 3 if is_violating else 2
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thick)

            # Label APD yang hilang
            missing = []
            if not ppe_status.get("helmet",  False): missing.append("X Helm")
            if not ppe_status.get("vest",    False): missing.append("X Rompi")
            if not ppe_status.get("boots",   False): missing.append("X Boots")
            if not ppe_status.get("goggles", False): missing.append("X Goggle")
            if not ppe_status.get("gloves",  False): missing.append("X Gloves")

            label = f"Person {det.confidence:.2f}"
            if partial:
                label += " [partial]"
            if missing:
                label += "  " + " | ".join(missing)

            self._draw_label(vis, label, x1, y1, color)

        # ── Layer 4: Panel info kiri atas ─────────────────────────────────
        ov = vis.copy()
        cv2.rectangle(ov, (0, 0), (330, 130), (15, 15, 15), -1)
        cv2.addWeighted(ov, 0.70, vis, 0.30, 0, vis)

        total_viol  = self.violation_logic.stats["total_events"]
        neg_hits    = self.violation_logic.stats.get("neg_class_hits", 0)
        pos_hits    = self.violation_logic.stats.get("pos_absent_hits", 0)
        lines = [
            f"Camera  : {self.camera_id}",
            f"Frame   : {self.frame_count}  |  FPS: {self.fps_display:.1f}",
            f"Person  : {len(person_dets)}  |  Total Viol: {total_viol}",
            f"NegCls  : {neg_hits}  |  PosAbs: {pos_hits}",
            f"Conf    : {self.conf}  |  NMS: {NMS_IOU_THRESHOLD}",
            f"Model   : {'ONNX' if self.use_onnx else 'PT'} | Epson K3 v5.0",
        ]
        for i, ln in enumerate(lines):
            cv2.putText(vis, ln, (8, 20 + i * 19),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.46, (0, 220, 220), 1, cv2.LINE_AA)

        # ── Layer 5: Panel status K3 kanan atas (5 APD Epson) ───────────
        STATUS_STYLE = {
            "COMPLIANT": ("Patuh   ", COMPLIANT_COLOR),
            "VIOLATION": ("LANGGAR!", VIOLATION_COLOR),
            "UNKNOWN":   ("Tdk Ada ", UNKNOWN_COLOR),
        }
        panel_w = 230
        px      = w - panel_w - 8

        ov2 = vis.copy()
        panel_h = 26 + len(REQUIRED_PPE) * 26 + 6
        cv2.rectangle(ov2, (px - 8, 0), (w, panel_h), (15, 15, 15), -1)
        cv2.addWeighted(ov2, 0.70, vis, 0.30, 0, vis)

        cv2.putText(vis, "STATUS APD — EPSON K3", (px, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, (200, 200, 200), 1, cv2.LINE_AA)
        for i, ppe_cls in enumerate(REQUIRED_PPE):
            lbl         = PANEL_LABELS.get(ppe_cls, ppe_cls)
            s           = apd_status.get(ppe_cls, "UNKNOWN")
            text, color = STATUS_STYLE[s]
            cv2.putText(vis, f"{lbl}: {text}", (px, 36 + i * 26),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.56, color, 2, cv2.LINE_AA)

        # ── Layer 6: Banner pelanggaran bawah ─────────────────────────────
        if events:
            # Tampilkan semua tipe pelanggaran unik
            unique_types = list({e.violation_type for e in events})
            names = ", ".join(t.replace("_", " ").upper() for t in unique_types)
            modes = list({e.detection_mode[:3].upper() for e in events})

            ov3 = vis.copy()
            cv2.rectangle(ov3, (0, h - 60), (w, h), (0, 0, 140), -1)
            cv2.addWeighted(ov3, 0.85, vis, 0.15, 0, vis)
            cv2.putText(vis, f"  PELANGGARAN: {names}",
                        (8, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.68,
                        (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(vis, f"  Deteksi via: {' + '.join(modes)} mode  |  {len(events)} event(s)",
                        (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                        (180, 180, 180), 1, cv2.LINE_AA)

        return vis

    # ─────────────────────────────────────────
    #  HELPER DRAW
    # ─────────────────────────────────────────

    def _draw_bbox(self, vis: np.ndarray, det: Detection,
                   color: tuple, thickness: int = 2):
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)
        self._draw_label(vis, f"{det.class_name} {det.confidence:.2f}", x1, y1, color)

    @staticmethod
    def _draw_label(vis: np.ndarray, label: str, x: int, y: int,
                    bg: tuple, scale: float = 0.46, thick: int = 1):
        fh, fw = vis.shape[:2]
        font   = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(label, font, scale, thick)
        bg_y1  = max(0, y - th - 6)
        bg_x2  = min(fw, x + tw + 4)
        cv2.rectangle(vis, (x, bg_y1), (bg_x2, y), bg, -1)
        cv2.putText(vis, label, (x + 2, max(th, y - 3)),
                    font, scale, LABEL_FG, thick, cv2.LINE_AA)

    # ─────────────────────────────────────────
    #  MAIN LOOP
    # ─────────────────────────────────────────

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
        print(f"[INFO] Resolusi   : {w_src}×{h_src} @ {fps_src:.1f}fps")
        if total > 0:
            print(f"[INFO] Total frame: {total}")
        print("[INFO] Tekan Q untuk berhenti.\n")

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
                        cv2.imshow("APD Monitor Epson K3 v5.0 [Q=quit]", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    continue

                vis = self._process_frame(frame)

                if show_preview:
                    cv2.imshow("APD Monitor Epson K3 v5.0 [Q=quit]", vis)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        print("\n[INFO] Dihentikan pengguna.")
                        break

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
                    cv2.imshow("APD Monitor Epson K3 v5.0 - Folder [Q=quit]", vis)
                    if cv2.waitKey(30) & 0xFF == ord("q"):
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
        print(f"\n{'='*65}")
        print(f"  APD Inference Pipeline v5.0 — YOLOv11 | Epson Factory K3")
        print(f"  11 Classes: helmet|gloves|vest|boots|goggles|none|Person")
        print(f"              no_helmet|no_goggle|no_gloves|no_boots")
        print(f"  Detection: DUAL MODE (negative class + positive absent)")
        print(f"  Standard : Epson K3 — 5 APD Wajib")
        print(f"{'='*65}")

    def _print_summary(self):
        print(f"\n\n{'='*65}")
        print(f"  RINGKASAN INFERENCE  [v5.0 Epson K3]")
        print(f"{'='*65}")
        print(f"  Total frame diproses : {self.frame_count}")
        print(f"\n  Deteksi per kelas:")
        for cname, count in self.class_count.items():
            if count > 0:
                bar = "█" * min(count // 10, 28)
                print(f"    {cname:<15}: {count:>6}  {bar}")
        self.violation_logic.print_summary()


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="APD Inference v5.0 — Epson Factory K3 | 11-Class Dual Detection",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Contoh:
  python inference.py --source 0 --model best.pt --no-backend
  python inference.py --source video.mp4 --model best.pt --skip 2 --no-backend
  python inference.py --source rtsp://192.168.1.100:554/stream --model best.pt
  python inference.py --source 0 --model best.pt --conf 0.35 --no-backend
  python inference.py --source 0 --model best.pt --save-video out.mp4 --no-backend
  python inference.py --source 0 --model best.onnx --use-onnx --no-backend
  python inference.py --source video.mp4 --model best.pt --camera-id EPSON_LINE_A
        """,
    )
    p.add_argument("--source",      required=True,
                   help="Sumber: 0=webcam, path video, RTSP URL")
    p.add_argument("--model",       default="bestArbi.pt",
                   help="Path model (.pt atau .onnx)")
    p.add_argument("--conf",        type=float, default=0.30,
                   help="Minimum confidence (default: 0.30)")
    p.add_argument("--iou",         type=float, default=0.45,
                   help="IoU threshold NMS (default: 0.45)")
    p.add_argument("--device",      default="cpu",
                   help="Device: cpu atau cuda:0")
    p.add_argument("--camera-id",   default="EPSON_CAM_01",
                   help="ID kamera untuk logging (default: EPSON_CAM_01)")
    p.add_argument("--output",      default="inference_output",
                   help="Folder output (default: inference_output)")
    p.add_argument("--skip",        type=int, default=1,
                   help="Proses setiap N frame (default: 1=semua)")
    p.add_argument("--save-video",  default=None,
                   help="Simpan output video ke file .mp4")
    p.add_argument("--no-preview",  action="store_true",
                   help="Nonaktifkan jendela preview OpenCV")
    p.add_argument("--backend-url", default="http://localhost:8000",
                   help="URL backend API (default: http://localhost:8000)")
    p.add_argument("--no-backend",  action="store_true",
                   help="Nonaktifkan pengiriman ke backend")
    p.add_argument("--use-onnx",    action="store_true",
                   help="Gunakan ONNX Runtime (lebih cepat di CPU)")
    return p.parse_args()


if __name__ == "__main__":
    args     = parse_args()
    pipeline = APDInferencePipeline(
        model_path  = args.model,
        confidence  = args.conf,
        iou         = args.iou,
        camera_id   = args.camera_id,
        output_dir  = args.output,
        device      = args.device,
        skip_frames = args.skip,
        backend_url = None if args.no_backend else args.backend_url,
        use_onnx    = args.use_onnx,
    )
    pipeline.run(
        source       = args.source,
        show_preview = not args.no_preview,
        save_video   = args.save_video,
    )