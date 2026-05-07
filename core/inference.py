"""
inference.py
============
Pipeline inference YOLOv11 untuk deteksi APD secara real-time.
Terintegrasi penuh dengan:
  - frame_reader.py    → handle berbagai sumber video
  - violation_logic.py → logika pelanggaran + cooldown + screenshot + log

Capstone Project: Sistem Monitoring K3 Berbasis Computer Vision

Cara pakai:
  python inference.py --source 0                          # webcam
  python inference.py --source rekaman.mp4                # file video
  python inference.py --source rtsp://ip:port/stream      # kamera IP
  python inference.py --source saved_frames/folder/       # folder frame
  python inference.py --source rekaman.mp4 --conf 0.45 --skip 2
  python inference.py --source rekaman.mp4 --save-video hasil.mp4 --no-preview

# Catatan: Mode CPU lebih lambat dari GPU. Kalau terasa lag, tambahkan --skip 3 supaya inference hanya tiap 3 frame:
"""

import cv2
import time
import argparse
import numpy as np
from pathlib import Path
from typing import List, Optional

# ── Import modul project ──────────────────────
from frame_reader import open_source, get_video_info
from violation_logic import ViolationLogic, Detection, ViolationEvent, VIOLATION_CLASSES

# ── Import YOLOv11 ────────────────────────────
try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError(
        "[ERROR] ultralytics belum terinstall.\n"
        "Jalankan: pip install ultralytics"
    )


# ─────────────────────────────────────────────
#  KONFIGURASI KELAS
#  Sesuaikan dengan dataset.yaml tim kamu
# ─────────────────────────────────────────────

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
    "helmet":         (0, 210, 0),    # hijau
    "no_helmet":      (0, 0, 220),    # merah
    "vest":           (0, 210, 0),    # hijau
    "no_vest":        (0, 0, 220),    # merah
    "safety_boot":    (0, 210, 0),    # hijau
    "no_safety_boot": (0, 0, 220),    # merah
}


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class APDInferencePipeline:
    """
    Pipeline utama deteksi APD.

    Alur kerja per frame:
    ┌──────────────┐   ┌───────────────┐   ┌─────────────────┐   ┌──────────┐
    │ frame_reader │ → │  YOLOv11      │ → │ violation_logic │ → │  Output  │
    │ (sumber vid) │   │  inference    │   │ cooldown+event  │   │ vis+log  │
    └──────────────┘   └───────────────┘   └─────────────────┘   └──────────┘
    """

    def __init__(
        self,
        model_path:  str          = "yolo11s.pt",
        confidence:  float        = 0.45,
        iou:         float        = 0.45,
        camera_id:   str          = "CAM_01",
        output_dir:  str          = "inference_output",
        device:      str          = "cpu",
        skip_frames: int          = 1,
        backend_url: Optional[str] = "http://localhost:8000",
    ):
        self._print_banner()

        # ── Load model YOLOv11 ──
        print(f"[INFO] Loading model : {model_path}")
        self.model       = YOLO(model_path)
        self.conf        = confidence
        self.iou         = iou
        self.device      = device
        self.skip_frames = skip_frames
        self.camera_id   = camera_id
        self.output_dir  = Path(output_dir)

        # ── Inisialisasi ViolationLogic ──────────
        # violation_logic.py menangani semua logika pelanggaran:
        # cooldown, screenshot, log .jsonl, statistik
        self.violation_logic = ViolationLogic(
            camera_id        = camera_id,
            output_dir       = str(self.output_dir / "violations"),
            save_screenshots = True,
            log_to_file      = True,
            backend_url      = backend_url,
        )

        # ── State tracking ──
        self.frame_count = 0
        self.fps_display = 0.0
        self.class_count = {name: 0 for name in CLASS_NAMES.values()}

        print(f"[INFO] Confidence    : {confidence}")
        print(f"[INFO] IoU           : {iou}")
        print(f"[INFO] Device        : {device}")
        print(f"[INFO] Skip frames   : setiap {skip_frames} frame")
        backend_info = backend_url if backend_url else "OFF (lokal only)"
        print(f"[INFO] Backend       : {backend_info}")
        print(f"[INFO] Output        : {self.output_dir.resolve()}\n")

    # ────────────────────────────────────────────
    #  STEP 1 — INFERENCE YOLO
    # ────────────────────────────────────────────

    def run_inference(self, frame: np.ndarray) -> List[Detection]:
        """
        Jalankan YOLOv11 pada satu frame.
        Hasil YOLO dikonversi ke list Detection
        (format yang dipakai violation_logic.py).
        """
        results = self.model(
            frame,
            conf    = self.conf,
            iou     = self.iou,
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
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]

                detections.append(Detection(
                    class_name = cname,
                    confidence = conf,
                    bbox       = (x1, y1, x2, y2),
                ))

                self.class_count[cname] = self.class_count.get(cname, 0) + 1

        return detections

    # ────────────────────────────────────────────
    #  STEP 2 — PROSES SATU FRAME PENUH
    # ────────────────────────────────────────────

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Satu siklus penuh per frame:
          1. Inference YOLO → list Detection
          2. violation_logic.process() → list ViolationEvent + cooldown + log
          3. get_frame_status() → status APD (COMPLIANT/VIOLATION/UNKNOWN)
          4. draw_frame() → frame dengan semua overlay visual
        """
        # Step 1: Inference
        detections = self.run_inference(frame)

        # Step 2: Cek pelanggaran via violation_logic.py
        #   - Cooldown otomatis ditangani di dalam ViolationLogic
        #   - Screenshot + log .jsonl disimpan otomatis
        #   - Return hanya event yang lolos cooldown
        events = self.violation_logic.process(
            detections   = detections,
            frame        = frame,
            frame_number = self.frame_count,
        )

        # Step 3: Status APD per frame (untuk panel overlay)
        apd_status = self.violation_logic.get_frame_status(detections)

        # Step 4: Gambar visualisasi
        vis = self.draw_frame(frame, detections, events, apd_status)

        return vis

    # ────────────────────────────────────────────
    #  STEP 3 — VISUALISASI
    # ────────────────────────────────────────────

    def draw_frame(
        self,
        frame:      np.ndarray,
        detections: List[Detection],
        events:     List[ViolationEvent],
        apd_status: dict,
    ) -> np.ndarray:
        """
        Gambar semua elemen visual pada frame:
          - Bounding box + label per deteksi
          - Info panel kiri atas (frame, FPS, total violations)
          - Status K3 panel kanan atas (Helm/Rompi/Sepatu)
          - Banner merah bawah jika ada pelanggaran baru di frame ini
        """
        vis = frame.copy()
        h, w = vis.shape[:2]

        # ── Bounding box + label ──
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            is_viol = det.class_name in VIOLATION_CLASSES
            color   = CLASS_COLORS.get(det.class_name, (200, 200, 0))
            thick   = 3 if is_viol else 2

            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thick)

            label = f"{det.class_name} {det.confidence:.2f}"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
            cv2.rectangle(vis, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
            cv2.putText(
                vis, label, (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                (255, 255, 255), 1, cv2.LINE_AA
            )

        # ── Info panel kiri atas ──
        overlay = vis.copy()
        cv2.rectangle(overlay, (0, 0), (265, 98), (25, 25, 25), -1)
        cv2.addWeighted(overlay, 0.6, vis, 0.4, 0, vis)

        total_viol = self.violation_logic.stats["total_events"]
        info_lines = [
            f"Camera : {self.camera_id}",
            f"Frame  : {self.frame_count}",
            f"FPS    : {self.fps_display:.1f}",
            f"Viol   : {total_viol} event",
        ]
        for i, line in enumerate(info_lines):
            cv2.putText(
                vis, line, (8, 20 + i * 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                (0, 220, 220), 1, cv2.LINE_AA
            )

        # ── Status K3 panel kanan atas ──
        status_style = {
            "COMPLIANT": ("Patuh   ", (0, 200, 0)),
            "VIOLATION": ("LANGGAR!", (0, 0, 220)),
            "UNKNOWN":   ("Tdk Ada ", (130, 130, 130)),
        }
        panel_w = 185
        px      = w - panel_w - 8

        overlay2 = vis.copy()
        cv2.rectangle(overlay2, (px - 6, 0), (w, 82), (25, 25, 25), -1)
        cv2.addWeighted(overlay2, 0.6, vis, 0.4, 0, vis)

        apd_labels = {
            "helmet":      "Helm  ",
            "vest":        "Rompi ",
            "safety_boot": "Sepatu",
        }
        for i, (key, label) in enumerate(apd_labels.items()):
            s           = apd_status.get(key, "UNKNOWN")
            text, color = status_style[s]
            cv2.putText(
                vis,
                f"{label}: {text}",
                (px, 22 + i * 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.54,
                color, 1, cv2.LINE_AA
            )

        # ── Banner pelanggaran bawah layar ──
        if events:
            names = ", ".join(
                e.violation_type.replace("_", " ").upper() for e in events
            )
            overlay3 = vis.copy()
            cv2.rectangle(overlay3, (0, h - 50), (w, h), (0, 0, 175), -1)
            cv2.addWeighted(overlay3, 0.85, vis, 0.15, 0, vis)
            cv2.putText(
                vis,
                f"  PELANGGARAN: {names}",
                (8, h - 13),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72,
                (255, 255, 255), 2, cv2.LINE_AA
            )

        return vis

    # ────────────────────────────────────────────
    #  MAIN RUN
    # ────────────────────────────────────────────

    def run(
        self,
        source,
        show_preview: bool          = True,
        save_video:   Optional[str] = None,
    ):
        """
        Entry point. Deteksi otomatis tipe source:
          - Folder gambar → _run_from_folder()
          - Webcam / file / RTSP → _run_from_stream()
        """
        if Path(str(source)).is_dir():
            self._run_from_folder(Path(str(source)), show_preview, save_video)
        else:
            self._run_from_stream(source, show_preview, save_video)

    def _run_from_stream(self, source, show_preview, save_video):
        """Loop dari webcam / file video / RTSP."""
        cap  = open_source(source)
        info = get_video_info(cap)

        print(f"[INFO] Source    : {source}")
        print(f"[INFO] Resolusi  : {info['width']}x{info['height']} @ {info['fps']:.1f}fps")
        if info["total"] > 0:
            print(f"[INFO] Total frame: {info['total']}")
        print(f"[INFO] Tekan Q untuk berhenti.\n")

        writer  = self._init_writer(save_video, info["fps"], info["width"], info["height"])
        t_start = time.perf_counter()

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("\n[INFO] Stream selesai / koneksi putus.")
                    break

                self.frame_count += 1
                elapsed          = time.perf_counter() - t_start
                self.fps_display = self.frame_count / elapsed if elapsed > 0 else 0

                # Skip frame untuk efisiensi CPU
                if self.frame_count % self.skip_frames != 0:
                    if show_preview:
                        cv2.imshow("APD Monitor [Q=quit]", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    continue

                # Proses frame (inference + violation + visualisasi)
                vis = self._process_frame(frame)

                if show_preview:
                    cv2.imshow("APD Monitor [Q=quit]", vis)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        print("\n[INFO] Dihentikan pengguna.")
                        break

                if writer:
                    writer.write(vis)

                if self.frame_count % 30 == 0:
                    total_viol = self.violation_logic.stats["total_events"]
                    print(
                        f"\r  Frame={self.frame_count} | "
                        f"FPS={self.fps_display:.1f} | "
                        f"Violations={total_viol}   ",
                        end="", flush=True
                    )

        finally:
            cap.release()
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _run_from_folder(self, folder, show_preview, save_video):
        """Loop dari folder frame hasil frame_reader.py."""
        img_files = sorted(
            list(folder.glob("*.jpg")) +
            list(folder.glob("*.png")) +
            list(folder.glob("*.jpeg"))
        )
        if not img_files:
            raise FileNotFoundError(f"[ERROR] Tidak ada gambar di: {folder}")

        print(f"[INFO] Mode folder : {folder.resolve()}")
        print(f"[INFO] Total gambar: {len(img_files)}")
        print(f"[INFO] Tekan Q untuk berhenti.\n")

        writer  = None
        t_start = time.perf_counter()

        try:
            for i, img_path in enumerate(img_files):
                frame = cv2.imread(str(img_path))
                if frame is None:
                    print(f"[WARN] Gagal baca: {img_path.name}")
                    continue

                self.frame_count += 1
                elapsed          = time.perf_counter() - t_start
                self.fps_display = self.frame_count / elapsed if elapsed > 0 else 0

                if save_video and writer is None:
                    hh, ww = frame.shape[:2]
                    writer = self._init_writer(save_video, 10, ww, hh)

                vis = self._process_frame(frame)

                if show_preview:
                    cv2.imshow("APD Monitor - Folder [Q=quit]", vis)
                    if cv2.waitKey(30) & 0xFF == ord("q"):
                        print("\n[INFO] Dihentikan pengguna.")
                        break

                if writer:
                    writer.write(vis)

                total_viol = self.violation_logic.stats["total_events"]
                print(
                    f"\r  [{i+1}/{len(img_files)}] {img_path.name} | "
                    f"Violations={total_viol}   ",
                    end="", flush=True
                )

        finally:
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    # ────────────────────────────────────────────
    #  HELPER
    # ────────────────────────────────────────────

    def _init_writer(self, path, fps, w, h):
        if not path:
            return None
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        print(f"[INFO] Simpan video ke: {path}")
        return cv2.VideoWriter(path, fourcc, fps, (w, h))

    def _print_banner(self):
        print(f"\n{'='*55}")
        print(f"  APD Inference Pipeline — YOLOv11 + ViolationLogic")
        print(f"{'='*55}")

    def _print_summary(self):
        print(f"\n\n{'='*55}")
        print(f"  RINGKASAN INFERENCE")
        print(f"{'='*55}")
        print(f"  Total frame diproses : {self.frame_count}")
        print(f"\n  Deteksi per kelas:")
        for cname, count in self.class_count.items():
            if count > 0:
                icon = "🚨" if cname in VIOLATION_CLASSES else "✅"
                print(f"    {icon} {cname:20s}: {count}x")
        # Ringkasan violation dari violation_logic.py
        self.violation_logic.print_session_summary()


# ─────────────────────────────────────────────
#  ARGUMEN COMMAND LINE
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Inference YOLOv11 APD — terintegrasi violation_logic.py",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Contoh:
  python inference.py --source 0
  python inference.py --source rekaman.mp4 --conf 0.45 --skip 2
  python inference.py --source saved_frames/webcam0_20250312/
  python inference.py --source rekaman.mp4 --save-video hasil.mp4 --no-preview
  python inference.py --source 0 --model models/best.pt --camera-id CAM_AREA_A
        """
    )
    parser.add_argument("--source",     required=True,
        help="0=webcam, file.mp4, rtsp://..., atau folder frame")
    parser.add_argument("--model",      default="yolo11s.pt",
        help="Path model .pt (default: yolo11s.pt, auto-download)")
    parser.add_argument("--conf",       type=float, default=0.45,
        help="Confidence threshold (default: 0.45)")
    parser.add_argument("--iou",        type=float, default=0.45,
        help="IoU threshold NMS (default: 0.45)")
    parser.add_argument("--device",     default="cpu",
        help="'cpu' atau '0' untuk GPU (default: cpu)")
    parser.add_argument("--camera-id",  default="CAM_01",
        help="ID kamera untuk log event (default: CAM_01)")
    parser.add_argument("--output",     default="inference_output",
        help="Folder output violations (default: inference_output)")
    parser.add_argument("--skip",       type=int, default=1,
        help="Proses setiap N frame (default: 1=semua)")
    parser.add_argument("--save-video", type=str, default=None,
        help="Simpan output visualisasi ke file .mp4")
    parser.add_argument("--no-preview", action="store_true",
        help="Matikan jendela preview (lebih cepat)")
    parser.add_argument("--backend-url", default="http://localhost:8000",
        help="URL backend API (default: http://localhost:8000)")
    parser.add_argument("--no-backend", action="store_true",
        help="Matikan pengiriman ke backend, simpan lokal saja")
    return parser.parse_args()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    backend_url = None if args.no_backend else args.backend_url

    pipeline = APDInferencePipeline(
        model_path  = args.model,
        confidence  = args.conf,
        iou         = args.iou,
        camera_id   = args.camera_id,
        output_dir  = args.output,
        device      = args.device,
        skip_frames = args.skip,
        backend_url = backend_url,
    )

    pipeline.run(
        source       = args.source,
        show_preview = not args.no_preview,
        save_video   = args.save_video,
    )