"""
inference.py
============
Pipeline inference YOLOv11 untuk deteksi APD (helm, rompi, sepatu safety).
Terhubung langsung dengan frame_reader.py sebagai sumber frame.

Capstone Project: Sistem Monitoring K3 Berbasis Computer Vision

Cara pakai:
  # Mode 1: Inference langsung dari webcam / video / RTSP
  python inference.py --source 0
  python inference.py --source rekaman.mp4
  python inference.py --source rtsp://admin:pass@192.168.1.100:554/stream

  # Mode 2: Inference dari folder frame hasil frame_reader.py
  python inference.py --source saved_frames/webcam0_20250312_143022/

  # Opsi tambahan
  python inference.py --source rekaman.mp4 --conf 0.45 --model yolo11s.pt
  python inference.py --source rekaman.mp4 --no-preview --save-video output.mp4

  #
  jika pc tidak ada gpu tambahkan --device cpu saat running
  contoh : python inference.py --source 0 --device cpu
"""

import cv2
import time
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

# Import frame_reader dari file yang sama folder
from frame_reader import open_source, get_video_info

# Import YOLOv11
try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError(
        "[ERROR] ultralytics belum terinstall.\n"
        "Jalankan: pip install ultralytics"
    )


# ─────────────────────────────────────────────
#  KONFIGURASI
# ─────────────────────────────────────────────

# Kelas APD — sesuaikan dengan dataset.yaml kamu
CLASS_NAMES = {
    0: "helmet",
    1: "no_helmet",
    2: "vest",
    3: "no_vest",
    4: "safety_boot",
    5: "no_safety_boot",
}

# Warna bounding box per kelas (BGR)
CLASS_COLORS = {
    "helmet":        (0, 200, 0),     # Hijau tua
    "no_helmet":     (0, 0, 220),     # Merah
    "vest":          (0, 200, 0),     # Hijau tua
    "no_vest":       (0, 0, 220),     # Merah
    "safety_boot":   (0, 200, 0),     # Hijau tua
    "no_safety_boot":(0, 0, 220),     # Merah
}

# Kelas yang dianggap PELANGGARAN
VIOLATION_CLASSES = {"no_helmet", "no_vest", "no_safety_boot"}

# Aturan pelanggaran: cooldown supaya tidak spam event
VIOLATION_RULES = {
    "no_helmet":      {"severity": "HIGH",   "cooldown": 15},
    "no_vest":        {"severity": "HIGH",   "cooldown": 15},
    "no_safety_boot": {"severity": "MEDIUM", "cooldown": 30},
}


# ─────────────────────────────────────────────
#  DATA CLASS
# ─────────────────────────────────────────────

@dataclass
class Detection:
    """Satu objek yang terdeteksi dalam satu frame."""
    class_id:   int
    class_name: str
    confidence: float
    bbox:       Tuple[int, int, int, int]   # x1, y1, x2, y2
    is_violation: bool = False

@dataclass
class ViolationEvent:
    """Event pelanggaran yang siap dikirim ke backend."""
    event_id:        str
    timestamp:       str
    camera_id:       str
    violation_type:  str
    severity:        str
    confidence:      float
    bbox:            dict
    frame_number:    int
    screenshot_path: Optional[str] = None


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class APDInferencePipeline:
    """
    Pipeline utama: baca frame → inference YOLO → deteksi pelanggaran → simpan event.
    Terintegrasi dengan frame_reader.py untuk handle berbagai sumber video.
    """

    def __init__(
        self,
        model_path:       str   = "yolo11s.pt",  # auto-download jika belum ada
        confidence:       float = 0.45,
        iou:              float = 0.45,
        camera_id:        str   = "CAM_01",
        output_dir:       str   = "inference_output",
        device:           str   = "0",            # "0"=GPU, "cpu"=CPU
        skip_frames:      int   = 1,              # proses setiap N frame
    ):
        print(f"\n{'='*55}")
        print(f"  APD Inference Pipeline - YOLOv11")
        print(f"{'='*55}")
        print(f"  Model      : {model_path}")
        print(f"  Confidence : {confidence}")
        print(f"  IoU        : {iou}")
        print(f"  Device     : {'GPU' if device != 'cpu' else 'CPU'}")
        print(f"{'='*55}\n")

        # Load model YOLOv11
        print("[INFO] Loading model YOLOv11 ...")
        self.model = YOLO(model_path)
        self.conf  = confidence
        self.iou   = iou
        self.device = device

        self.camera_id   = camera_id
        self.skip_frames = skip_frames

        # Folder output
        self.output_dir = Path(output_dir)
        self.screenshot_dir = self.output_dir / "screenshots"
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

        # File log pelanggaran
        self.log_file = self.output_dir / "violations_log.jsonl"

        # State tracking
        self.frame_count       = 0
        self.violation_count   = 0
        self.last_violation_time = {}   # {class_name: timestamp}

        # Statistik per kelas
        self.class_detection_count = {name: 0 for name in CLASS_NAMES.values()}

        print(f"[INFO] Output folder : {self.output_dir.resolve()}")
        print(f"[INFO] Model siap.\n")

    # ── INFERENCE ──────────────────────────────

    def run_inference(self, frame: np.ndarray) -> List[Detection]:
        """
        Jalankan YOLOv11 pada satu frame.
        Return: list Detection yang terdeteksi.
        """
        results = self.model(
            frame,
            conf=self.conf,
            iou=self.iou,
            device=self.device,
            verbose=False,
        )

        detections = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                cid   = int(box.cls[0].item())
                cname = CLASS_NAMES.get(cid, f"class_{cid}")
                conf  = float(box.conf[0].item())
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

                detections.append(Detection(
                    class_id=cid,
                    class_name=cname,
                    confidence=conf,
                    bbox=(x1, y1, x2, y2),
                    is_violation=(cname in VIOLATION_CLASSES),
                ))

                # Update statistik
                self.class_detection_count[cname] = (
                    self.class_detection_count.get(cname, 0) + 1
                )

        return detections

    # ── VIOLATION LOGIC ─────────────────────────

    def check_violations(
        self,
        detections:   List[Detection],
        frame:        np.ndarray,
    ) -> List[ViolationEvent]:
        """
        Periksa deteksi → buat ViolationEvent jika ada pelanggaran.
        Cooldown diterapkan agar tidak spam event yang sama.
        """
        events       = []
        current_time = time.time()

        for det in detections:
            if not det.is_violation:
                continue

            rule = VIOLATION_RULES.get(det.class_name, {})

            # Cek cooldown
            last_t   = self.last_violation_time.get(det.class_name, 0)
            cooldown = rule.get("cooldown", 15)
            if current_time - last_t < cooldown:
                continue   # masih dalam cooldown, skip

            # Buat event
            dt       = datetime.fromtimestamp(current_time)
            event_id = f"{self.camera_id}_{self.frame_count}_{det.class_name}"

            # Simpan screenshot
            screenshot_path = self._save_screenshot(frame, det, dt, event_id)

            event = ViolationEvent(
                event_id        = event_id,
                timestamp       = dt.isoformat(),
                camera_id       = self.camera_id,
                violation_type  = det.class_name,
                severity        = rule.get("severity", "MEDIUM"),
                confidence      = round(det.confidence, 4),
                bbox            = {"x1": det.bbox[0], "y1": det.bbox[1],
                                   "x2": det.bbox[2], "y2": det.bbox[3]},
                frame_number    = self.frame_count,
                screenshot_path = screenshot_path,
            )

            # Simpan ke log
            self._log_event(event)

            events.append(event)
            self.last_violation_time[det.class_name] = current_time
            self.violation_count += 1

            print(
                f"  🚨 VIOLATION | {det.class_name:20s} | "
                f"conf={det.confidence:.2f} | "
                f"severity={rule.get('severity','?')} | "
                f"frame={self.frame_count}"
            )

        return events

    # ── VISUALISASI ─────────────────────────────

    def draw_detections(
        self,
        frame:      np.ndarray,
        detections: List[Detection],
        events:     List[ViolationEvent],
        fps:        float,
    ) -> np.ndarray:
        """Gambar bounding box, label, dan overlay info pada frame."""
        vis = frame.copy()

        # Gambar setiap detection
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = CLASS_COLORS.get(det.class_name, (255, 255, 0))
            thick = 3 if det.is_violation else 2

            # Box
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thick)

            # Label background
            label = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1
            )
            cv2.rectangle(vis, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)

            # Label text
            cv2.putText(
                vis, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (255, 255, 255), 1, cv2.LINE_AA
            )

        # Overlay info kanan atas
        h, w = vis.shape[:2]
        info_lines = [
            f"FPS: {fps:.1f}",
            f"Frame: {self.frame_count}",
            f"Detections: {len(detections)}",
            f"Violations: {self.violation_count}",
        ]
        for i, line in enumerate(info_lines):
            cv2.putText(
                vis, line,
                (w - 210, 30 + i * 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65,
                (0, 255, 255), 2, cv2.LINE_AA
            )

        # Banner VIOLATION merah jika ada event baru
        if events:
            cv2.rectangle(vis, (0, h - 50), (w, h), (0, 0, 180), -1)
            label_viol = f"⚠ VIOLATION DETECTED: {events[0].violation_type.upper()}"
            cv2.putText(
                vis, label_viol,
                (10, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.75,
                (255, 255, 255), 2, cv2.LINE_AA
            )

        return vis

    # ── MAIN LOOP ───────────────────────────────

    def run(
        self,
        source,
        show_preview: bool = True,
        save_video:   Optional[str] = None,
    ):
        """
        Main loop. Baca frame dari source (webcam/file/RTSP/folder),
        jalankan inference, deteksi pelanggaran, tampilkan hasil.

        source bisa berupa:
          - int / str angka   → webcam
          - str path file     → video .mp4/.avi/dll
          - str "rtsp://..."  → RTSP stream
          - str path folder   → folder hasil frame_reader.py
        """

        # ── Deteksi apakah source adalah folder frame ──
        source_path = Path(str(source))
        if source_path.is_dir():
            return self._run_from_folder(source_path, show_preview, save_video)

        # ── Source adalah video / webcam / RTSP ──
        cap  = open_source(source)
        info = get_video_info(cap)

        print(f"[INFO] Source    : {source}")
        print(f"[INFO] Resolusi  : {info['width']}x{info['height']} @ {info['fps']:.1f}fps")
        if info['total'] > 0:
            print(f"[INFO] Total frame: {info['total']}")

        # Setup VideoWriter jika diminta simpan video
        writer = None
        if save_video:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(
                save_video, fourcc,
                info['fps'], (info['width'], info['height'])
            )
            print(f"[INFO] Simpan video ke: {save_video}")

        t_start  = time.perf_counter()
        fps_display = 0.0

        print(f"\n[INFO] Mulai inference. Tekan Q untuk berhenti.\n")

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("\n[INFO] Stream selesai.")
                    break

                self.frame_count += 1

                # Hitung FPS display
                elapsed     = time.perf_counter() - t_start
                fps_display = self.frame_count / elapsed if elapsed > 0 else 0

                # Skip frame untuk efisiensi
                if self.frame_count % self.skip_frames != 0:
                    if show_preview:
                        cv2.imshow("APD Monitor [Q=quit]", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break
                    continue

                # ── INFERENCE ──
                detections = self.run_inference(frame)

                # ── VIOLATION CHECK ──
                events = self.check_violations(detections, frame)

                # ── VISUALISASI ──
                vis_frame = self.draw_detections(frame, detections, events, fps_display)

                if show_preview:
                    cv2.imshow("APD Monitor [Q=quit]", vis_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        print("\n[INFO] Dihentikan pengguna.")
                        break

                if writer:
                    writer.write(vis_frame)

                # Progress tiap 30 frame
                if self.frame_count % 30 == 0:
                    print(
                        f"\r  Frame={self.frame_count} | "
                        f"FPS={fps_display:.1f} | "
                        f"Violations={self.violation_count}   ",
                        end="", flush=True
                    )

        finally:
            cap.release()
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _run_from_folder(
        self,
        folder: Path,
        show_preview: bool,
        save_video: Optional[str],
    ):
        """
        Inference dari folder frame hasil frame_reader.py.
        Berguna untuk test model tanpa perlu video langsung.
        """
        # Ambil semua file gambar di folder, urut berdasarkan nama
        img_files = sorted(
            list(folder.glob("*.jpg")) +
            list(folder.glob("*.png")) +
            list(folder.glob("*.jpeg"))
        )

        if not img_files:
            raise FileNotFoundError(f"[ERROR] Tidak ada gambar di folder: {folder}")

        print(f"[INFO] Mode: Folder frame")
        print(f"[INFO] Folder  : {folder.resolve()}")
        print(f"[INFO] Total   : {len(img_files)} gambar")
        print(f"\n[INFO] Mulai inference. Tekan Q untuk berhenti.\n")

        writer = None
        t_start = time.perf_counter()

        try:
            for i, img_path in enumerate(img_files):
                frame = cv2.imread(str(img_path))
                if frame is None:
                    print(f"[WARN] Gagal baca: {img_path.name}")
                    continue

                self.frame_count += 1

                # Setup VideoWriter dari dimensi frame pertama
                if save_video and writer is None:
                    h, w = frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(save_video, fourcc, 10, (w, h))

                elapsed     = time.perf_counter() - t_start
                fps_display = self.frame_count / elapsed if elapsed > 0 else 0

                # Inference
                detections = self.run_inference(frame)
                events     = self.check_violations(detections, frame)
                vis_frame  = self.draw_detections(frame, detections, events, fps_display)

                if show_preview:
                    cv2.imshow("APD Monitor - Folder Mode [Q=quit]", vis_frame)
                    if cv2.waitKey(30) & 0xFF == ord('q'):
                        print("\n[INFO] Dihentikan pengguna.")
                        break

                if writer:
                    writer.write(vis_frame)

                # Progress
                print(
                    f"\r  [{i+1}/{len(img_files)}] "
                    f"{img_path.name} | "
                    f"det={len(detections)} | "
                    f"viol={self.violation_count}   ",
                    end="", flush=True
                )

        finally:
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    # ── HELPER ──────────────────────────────────

    def _save_screenshot(
        self,
        frame: np.ndarray,
        det:   Detection,
        dt:    datetime,
        event_id: str,
    ) -> str:
        """Simpan screenshot frame pada saat pelanggaran terjadi."""
        filename = f"{det.class_name}_{dt.strftime('%Y%m%d_%H%M%S')}.jpg"
        path     = self.screenshot_dir / filename

        shot = frame.copy()
        x1, y1, x2, y2 = det.bbox
        cv2.rectangle(shot, (x1, y1), (x2, y2), (0, 0, 255), 3)
        cv2.putText(
            shot,
            f"VIOLATION: {det.class_name.upper()}",
            (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
            (0, 0, 255), 2, cv2.LINE_AA
        )
        cv2.putText(
            shot,
            dt.strftime("%Y-%m-%d %H:%M:%S"),
            (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65,
            (255, 255, 255), 2, cv2.LINE_AA
        )
        cv2.imwrite(str(path), shot)
        return str(path)

    def _log_event(self, event: ViolationEvent):
        """Simpan event ke file .jsonl (1 baris = 1 event JSON)."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(asdict(event)) + "\n")

    def _print_summary(self):
        """Tampilkan ringkasan setelah selesai."""
        print(f"\n\n{'='*55}")
        print(f"  RINGKASAN INFERENCE")
        print(f"{'='*55}")
        print(f"  Total frame diproses : {self.frame_count}")
        print(f"  Total pelanggaran    : {self.violation_count}")
        print(f"\n  Deteksi per kelas:")
        for cls, count in self.class_detection_count.items():
            if count > 0:
                marker = "🚨" if cls in VIOLATION_CLASSES else "✅"
                print(f"    {marker} {cls:20s}: {count}")
        print(f"\n  Log pelanggaran : {self.log_file.resolve()}")
        print(f"  Screenshots     : {self.screenshot_dir.resolve()}")
        print(f"{'='*55}\n")


# ─────────────────────────────────────────────
#  ARGUMEN COMMAND LINE
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Inference YOLOv11 untuk deteksi APD secara real-time.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Contoh:
  python inference.py --source 0
  python inference.py --source rekaman.mp4 --conf 0.45
  python inference.py --source saved_frames/webcam0_20250312/
  python inference.py --source rekaman.mp4 --save-video hasil.mp4 --no-preview
        """
    )
    parser.add_argument("--source",     required=True,
        help="Webcam (0), file video, RTSP URL, atau folder frame")
    parser.add_argument("--model",      default="yolo11s.pt",
        help="Path model .pt (default: yolo11s.pt, auto-download)")
    parser.add_argument("--conf",       type=float, default=0.45,
        help="Confidence threshold (default: 0.45)")
    parser.add_argument("--iou",        type=float, default=0.45,
        help="IoU threshold NMS (default: 0.45)")
    parser.add_argument("--device",     default="0",
        help="Device: '0'=GPU, 'cpu'=CPU (default: 0)")
    parser.add_argument("--camera-id",  default="CAM_01",
        help="ID kamera untuk event log (default: CAM_01)")
    parser.add_argument("--output",     default="inference_output",
        help="Folder output screenshots & log (default: inference_output)")
    parser.add_argument("--skip",       type=int, default=1,
        help="Proses setiap N frame (default: 1=semua)")
    parser.add_argument("--save-video", type=str, default=None,
        help="Simpan hasil visualisasi ke file .mp4")
    parser.add_argument("--no-preview", action="store_true",
        help="Matikan jendela preview (lebih cepat)")
    return parser.parse_args()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    pipeline = APDInferencePipeline(
        model_path  = args.model,
        confidence  = args.conf,
        iou         = args.iou,
        camera_id   = args.camera_id,
        output_dir  = args.output,
        device      = args.device,
        skip_frames = args.skip,
    )

    pipeline.run(
        source       = args.source,
        show_preview = not args.no_preview,
        save_video   = args.save_video,
    )