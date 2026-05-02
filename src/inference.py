"""
inference.py
============
Pipeline inference YOLOv11 untuk deteksi APD secara real-time.

Model kelas:
    0: person  → orang / pekerja
    1: helmet  → helm safety
    2: vest    → rompi safety
    3: boots   → sepatu safety
    4: gloves  → sarung tangan

Warna bbox per kelas:
    person  → ORANYE  (patuh) / MERAH (melanggar)
    helmet  → HIJAU TERANG
    vest    → BIRU MUDA
    boots   → KUNING
    gloves  → UNGU

Semua bbox APD digambar apa adanya dari output model tanpa filter posisi.
Pelanggaran ditentukan berdasarkan overlap bbox APD dengan bbox person
(minimal 30% area APD harus berada di dalam bbox person).

Cara pakai:
  python inference.py --source 0 --model best.pt --no-backend
  python inference.py --source rekaman.mp4 --model best.pt --skip 2 --no-backend
  python inference.py --source rtsp://ip:port/stream --model best.pt
  python inference.py --source "http://172.10.10.3:8080/video" --model best.pt --skip 3
  python inference.py --source 0 --model best.pt --save-video hasil.mp4 --no-backend
  python inference.py --source 0 --model best.pt --camera-id CAM_AREA_A --no-backend
"""

import cv2
import time
import argparse
import numpy as np
from pathlib import Path
from typing import List, Optional

from frame_reader import open_source, get_video_info

from violation_logic import (
    ViolationLogic,
    Detection,
    ViolationEvent,
    VIOLATION_CLASSES,
    COMPLIANT_CLASSES,
    ALL_PPE_CLASSES,
    REQUIRED_PPE,
    person_has_ppe,
    get_person_ppe_dict,
)

try:
    from ultralytics import YOLO
except ImportError:
    raise ImportError(
        "[ERROR] ultralytics belum terinstall.\n"
        "Jalankan: pip install ultralytics"
    )


# ─────────────────────────────────────────────
#  KONFIGURASI KELAS & WARNA
# ─────────────────────────────────────────────

CLASS_NAMES = {
    0: "person",
    1: "helmet",
    2: "vest",
    3: "boots",
    4: "gloves",
}

# Warna bbox per kelas — format BGR (OpenCV)
# Dipilih kontras satu sama lain agar mudah dibedakan di video
CLASS_COLORS = {
    "person":  (  0, 165, 255),   # oranye       — person patuh
    "helmet":  (  0, 220,   0),   # hijau terang  — helm
    "vest":    (255, 200,   0),   # biru muda     — rompi
    "boots":   (  0, 220, 220),   # kuning        — sepatu
    "gloves":  (220,   0, 220),   # ungu          — sarung tangan
}

# Warna person yang melanggar (merah terang)
PERSON_VIOLATION_COLOR = (0, 0, 255)

# Teks label selalu putih agar kontras di atas semua warna background
LABEL_TEXT_COLOR = (255, 255, 255)

# Label Indonesia untuk panel status kanan atas
APD_PANEL_LABELS = {
    "helmet":      "Helm  ",
    "vest":        "Rompi ",
    "safety_boot": "Sepatu",
}


# ─────────────────────────────────────────────
#  KELAS UTAMA
# ─────────────────────────────────────────────

class APDInferencePipeline:

    def __init__(
        self,
        model_path:   str           = "best.pt",
        confidence:   float         = 0.40,
        iou:          float         = 0.45,
        camera_id:    str           = "CAM_01",
        output_dir:   str           = "inference_output",
        device:       str           = "cpu",
        skip_frames:  int           = 1,
        backend_url:  Optional[str] = None,
    ):
        self._print_banner()

        print(f"[INFO] Loading model  : {model_path}")
        self.model       = YOLO(model_path)
        self.conf        = confidence
        self.iou         = iou
        self.device      = device
        self.skip_frames = skip_frames
        self.camera_id   = camera_id
        self.output_dir  = Path(output_dir)

        # Verifikasi kelas model
        print(f"[INFO] Model classes  : {self.model.names}")
        if len(self.model.names) != 5:
            print(
                f"[WARN] Model punya {len(self.model.names)} kelas, "
                f"expected 5 (person/helmet/vest/boots/gloves)"
            )

        self.violation_logic = ViolationLogic(
            camera_id        = camera_id,
            output_dir       = str(self.output_dir / "violations"),
            save_screenshots = True,
            log_to_file      = True,
            backend_url      = backend_url,
        )

        self.frame_count = 0
        self.fps_display = 0.0
        self.class_count = {name: 0 for name in CLASS_NAMES.values()}

        print(f"[INFO] Confidence     : {confidence}")
        print(f"[INFO] IoU threshold  : {iou}")
        print(f"[INFO] Device         : {device}")
        print(f"[INFO] Skip frames    : setiap {skip_frames} frame")
        print(f"[INFO] Backend        : {backend_url or 'OFF (lokal only)'}")
        print(f"[INFO] Output dir     : {self.output_dir.resolve()}\n")

    # ────────────────────────────────────────────
    #  STEP 1 — INFERENCE
    # ────────────────────────────────────────────

    def run_inference(self, frame: np.ndarray) -> List[Detection]:
        """
        Jalankan YOLO pada satu frame.
        Return semua Detection apa adanya — tidak ada post-filtering di sini.
        """
        results    = self.model(
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
    #  STEP 2 — PROSES FRAME
    # ────────────────────────────────────────────

    def _process_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Jalankan inference → cek violation → visualisasi.
        Return frame yang sudah diberi anotasi bbox + overlay.
        """
        frame_height = frame.shape[0]
        detections   = self.run_inference(frame)

        events = self.violation_logic.process(
            detections   = detections,
            frame        = frame,
            frame_number = self.frame_count,
        )
        apd_status = self.violation_logic.get_frame_status(
            detections   = detections,
            frame_height = frame_height,
        )

        return self.draw_frame(frame, detections, events, apd_status)

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
        Gambar semua bbox + overlay info pada frame.

        Layer (bawah ke atas):
          1. Bbox APD (helmet/vest/boots/gloves) — warna unik per kelas
          2. Bbox person — oranye (patuh) atau merah (langgar) + label APD missing
          3. Panel info kiri atas (camera, frame, fps, jumlah person)
          4. Panel status K3 kanan atas (Helm / Rompi / Sepatu)
          5. Banner pelanggaran bawah (hanya jika ada event di frame ini)
        """
        vis = frame.copy()
        h, w = vis.shape[:2]

        person_dets = [d for d in detections if d.class_name == "person"]
        ppe_dets    = [d for d in detections if d.class_name != "person"]

        # ── Layer 1: Gambar semua bbox APD ───────────────────────────────
        # Digambar SEMUA apa adanya dari model.
        # Warna solid berbeda per kelas:
        #   helmet → hijau | vest → biru muda | boots → kuning | gloves → ungu
        for det in ppe_dets:
            color = CLASS_COLORS.get(det.class_name, (200, 200, 200))
            self._draw_bbox_with_label(vis, det, color, thickness=2)

        # ── Layer 2: Gambar bbox person ──────────────────────────────────
        for det in person_dets:
            x1, y1, x2, y2 = det.bbox

            # Cek APD mana yang ditemukan untuk person ini
            ppe_status = get_person_ppe_dict(det, detections, frame_height=h)

            # Person melanggar jika ada APD WAJIB (helmet/vest/boots) yang tidak ada
            is_violating = any(
                not ppe_status.get(ppe, False)
                for ppe in REQUIRED_PPE
            )

            color = PERSON_VIOLATION_COLOR if is_violating else CLASS_COLORS["person"]
            thick = 3 if is_violating else 2
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, thick)

            # Susun label — cantumkan APD wajib yang TIDAK ditemukan
            missing = []
            if not ppe_status.get("helmet", False):
                missing.append("X helm")
            if not ppe_status.get("vest", False):
                missing.append("X rompi")
            if not ppe_status.get("boots", False):
                missing.append("X boots")

            label = f"person {det.confidence:.2f}"
            if missing:
                label += "  " + " | ".join(missing)

            self._draw_label_above(vis, label, x1, y1, color)

        # ── Layer 3: Panel info kiri atas ────────────────────────────────
        self._draw_info_panel(vis, person_dets)

        # ── Layer 4: Panel status K3 kanan atas ──────────────────────────
        self._draw_status_panel(vis, w, apd_status)

        # ── Layer 5: Banner pelanggaran bawah ────────────────────────────
        if events:
            self._draw_violation_banner(vis, h, w, events)

        return vis

    # ────────────────────────────────────────────
    #  HELPER DRAW
    # ────────────────────────────────────────────

    def _draw_bbox_with_label(
        self,
        vis:       np.ndarray,
        det:       Detection,
        color:     tuple,
        thickness: int = 2,
    ):
        """Gambar satu bbox dengan label confidence di atasnya."""
        fh, fw = vis.shape[:2]
        x1, y1, x2, y2 = det.bbox

        # Clamp koordinat ke batas frame
        x1 = max(0, min(x1, fw - 1))
        y1 = max(0, min(y1, fh - 1))
        x2 = max(0, min(x2, fw - 1))
        y2 = max(0, min(y2, fh - 1))

        if x2 <= x1 or y2 <= y1:
            return  # bbox tidak valid, skip

        cv2.rectangle(vis, (x1, y1), (x2, y2), color, thickness)
        label = f"{det.class_name} {det.confidence:.2f}"
        self._draw_label_above(vis, label, x1, y1, color)

    @staticmethod
    def _draw_label_above(
        vis:        np.ndarray,
        label:      str,
        x:          int,
        y:          int,
        bg_color:   tuple,
        font_scale: float = 0.48,
        thickness:  int   = 1,
    ):
        """Gambar teks label dengan background warna tepat di atas koordinat (x, y)."""
        fh, fw = vis.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        (tw, th), _ = cv2.getTextSize(label, font, font_scale, thickness)

        # Hitung posisi background label — jangan sampai keluar frame atas
        bg_y1 = max(0, y - th - 6)
        bg_y2 = max(0, y)
        bg_x2 = min(fw, x + tw + 4)

        cv2.rectangle(vis, (x, bg_y1), (bg_x2, bg_y2), bg_color, -1)
        cv2.putText(
            vis, label,
            (x + 2, max(th, y - 3)),
            font, font_scale, LABEL_TEXT_COLOR, thickness, cv2.LINE_AA,
        )

    def _draw_info_panel(self, vis: np.ndarray, person_dets: List[Detection]):
        """Panel kiri atas: camera ID, nomor frame, FPS, jumlah person + total violation."""
        overlay = vis.copy()
        cv2.rectangle(overlay, (0, 0), (295, 105), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.65, vis, 0.35, 0, vis)

        total_viol = self.violation_logic.stats["total_events"]
        lines = [
            f"Camera : {self.camera_id}",
            f"Frame  : {self.frame_count}",
            f"FPS    : {self.fps_display:.1f}",
            f"Person : {len(person_dets)} | Viol: {total_viol} event",
        ]
        for i, line in enumerate(lines):
            cv2.putText(
                vis, line, (8, 22 + i * 21),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                (0, 220, 220), 1, cv2.LINE_AA,
            )

    @staticmethod
    def _draw_status_panel(vis: np.ndarray, frame_w: int, apd_status: dict):
        """Panel kanan atas: status Helm / Rompi / Sepatu (COMPLIANT / VIOLATION / UNKNOWN)."""
        STATUS_STYLE = {
            "COMPLIANT": ("Patuh   ", (  0, 200,   0)),
            "VIOLATION": ("LANGGAR!", (  0,  50, 230)),
            "UNKNOWN":   ("Tdk Ada ", (130, 130, 130)),
        }
        panel_w = 195
        px      = frame_w - panel_w - 8

        overlay2 = vis.copy()
        cv2.rectangle(overlay2, (px - 8, 0), (frame_w, 88), (20, 20, 20), -1)
        cv2.addWeighted(overlay2, 0.65, vis, 0.35, 0, vis)

        for i, (key, lbl) in enumerate(APD_PANEL_LABELS.items()):
            s           = apd_status.get(key, "UNKNOWN")
            text, color = STATUS_STYLE[s]
            cv2.putText(
                vis, f"{lbl}: {text}",
                (px, 24 + i * 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.54, color, 1, cv2.LINE_AA,
            )

    @staticmethod
    def _draw_violation_banner(
        vis:    np.ndarray,
        h:      int,
        w:      int,
        events: List[ViolationEvent],
    ):
        """Banner merah di bawah frame saat ada pelanggaran di frame ini."""
        names    = ", ".join(
            e.violation_type.replace("_", " ").upper() for e in events
        )
        overlay3 = vis.copy()
        cv2.rectangle(overlay3, (0, h - 52), (w, h), (0, 0, 175), -1)
        cv2.addWeighted(overlay3, 0.85, vis, 0.15, 0, vis)
        cv2.putText(
            vis,
            f"  PELANGGARAN: {names}",
            (8, h - 14),
            cv2.FONT_HERSHEY_SIMPLEX, 0.72,
            (255, 255, 255), 2, cv2.LINE_AA,
        )

    # ────────────────────────────────────────────
    #  LOOP UTAMA
    # ────────────────────────────────────────────

    def run(
        self,
        source,
        show_preview: bool          = True,
        save_video:   Optional[str] = None,
    ):
        """Entry point: jalankan pipeline dari source apapun."""
        if Path(str(source)).is_dir():
            self._run_from_folder(Path(str(source)), show_preview, save_video)
        else:
            self._run_from_stream(source, show_preview, save_video)

    def _run_from_stream(self, source, show_preview: bool, save_video: Optional[str]):
        """Loop utama: webcam / video file / RTSP / HTTP stream."""
        cap  = open_source(source)
        info = get_video_info(cap)

        print(f"[INFO] Source     : {source}")
        print(f"[INFO] Resolusi   : {info['width']}x{info['height']} @ {info['fps']:.1f}fps")
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
                elapsed           = time.perf_counter() - t_start
                self.fps_display  = self.frame_count / elapsed if elapsed > 0 else 0.0

                # Skip frame sesuai interval — tampilkan frame mentah saat skip
                if self.frame_count % self.skip_frames != 0:
                    if show_preview:
                        cv2.imshow("APD Monitor [Q=quit]", frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
                    continue

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
                        end="", flush=True,
                    )

        finally:
            cap.release()
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _run_from_folder(self, folder: Path, show_preview: bool, save_video: Optional[str]):
        """Loop untuk folder berisi gambar JPG/PNG."""
        img_files = sorted(
            list(folder.glob("*.jpg"))  +
            list(folder.glob("*.jpeg")) +
            list(folder.glob("*.png"))
        )
        if not img_files:
            raise FileNotFoundError(f"[ERROR] Tidak ada gambar JPG/PNG di: {folder}")

        print(f"[INFO] Mode folder  : {folder.resolve()}")
        print(f"[INFO] Total gambar : {len(img_files)}")

        writer  = None
        t_start = time.perf_counter()

        try:
            for i, img_path in enumerate(img_files):
                frame = cv2.imread(str(img_path))
                if frame is None:
                    print(f"\n[WARN] Tidak bisa baca: {img_path.name}")
                    continue

                self.frame_count += 1
                elapsed          = time.perf_counter() - t_start
                self.fps_display = self.frame_count / elapsed if elapsed > 0 else 0.0

                if save_video and writer is None:
                    hh, ww = frame.shape[:2]
                    writer = self._init_writer(save_video, 10.0, ww, hh)

                vis = self._process_frame(frame)

                if show_preview:
                    cv2.imshow("APD Monitor - Folder [Q=quit]", vis)
                    if cv2.waitKey(30) & 0xFF == ord("q"):
                        break

                if writer:
                    writer.write(vis)

                total_viol = self.violation_logic.stats["total_events"]
                print(
                    f"\r  [{i+1}/{len(img_files)}] {img_path.name} | "
                    f"Violations={total_viol}   ",
                    end="", flush=True,
                )

        finally:
            if writer:
                writer.release()
            cv2.destroyAllWindows()
            self._print_summary()

    def _init_writer(
        self,
        path:   Optional[str],
        fps:    float,
        width:  int,
        height: int,
    ) -> Optional[cv2.VideoWriter]:
        if not path:
            return None
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        print(f"[INFO] Simpan video ke: {path}")
        return cv2.VideoWriter(path, fourcc, max(fps, 1.0), (width, height))

    def _print_banner(self):
        print(f"\n{'='*56}")
        print(f"  APD Inference Pipeline — YOLOv11 (5-kelas)")
        print(f"  person | helmet | vest | boots | gloves")
        print(f"{'='*56}")

    def _print_summary(self):
        print(f"\n\n{'='*56}")
        print(f"  RINGKASAN INFERENCE")
        print(f"{'='*56}")
        print(f"  Total frame diproses : {self.frame_count}")
        print(f"\n  Deteksi per kelas:")
        for cname, count in self.class_count.items():
            bar = "█" * min(count // 10, 30)
            print(f"    {cname:<10}: {count:>6}x  {bar}")
        self.violation_logic.print_session_summary()


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="APD Inference YOLOv11 — 5 kelas: person/helmet/vest/boots/gloves",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Contoh:
  python inference.py --source 0 --model best.pt --no-backend
  python inference.py --source rekaman.mp4 --model best.pt --skip 2 --no-backend
  python inference.py --source rtsp://admin:pass@192.168.1.100:554/stream1 --model best.pt
  python inference.py --source "http://172.10.10.3:8080/video" --model best.pt --skip 3
  python inference.py --source 0 --model best.pt --save-video demo.mp4 --no-backend
  python inference.py --source 0 --model best.pt --camera-id CAM_AREA_A --no-backend
        """,
    )
    p.add_argument("--source",      required=True,
                   help="0=webcam | path video | path folder gambar | URL RTSP/HTTP")
    p.add_argument("--model",       default="best.pt",
                   help="Path model .pt  (default: best.pt)")
    p.add_argument("--conf",        type=float, default=0.40,
                   help="Confidence threshold  (default: 0.40)")
    p.add_argument("--iou",         type=float, default=0.45,
                   help="IoU threshold NMS  (default: 0.45)")
    p.add_argument("--device",      default="cpu",
                   help="Device: cpu | cuda | mps  (default: cpu)")
    p.add_argument("--camera-id",   default="CAM_01",
                   help="ID kamera untuk log  (default: CAM_01)")
    p.add_argument("--output",      default="inference_output",
                   help="Folder output screenshot & log  (default: inference_output)")
    p.add_argument("--skip",        type=int, default=1,
                   help="Proses 1 dari N frame  (default: 1)")
    p.add_argument("--save-video",  type=str, default=None,
                   help="Simpan output video ke file ini  (opsional)")
    p.add_argument("--no-preview",  action="store_true",
                   help="Jangan buka jendela preview OpenCV")
    p.add_argument("--backend-url", default="http://localhost:8000",
                   help="URL backend API  (default: http://localhost:8000)")
    p.add_argument("--no-backend",  action="store_true",
                   help="Nonaktifkan pengiriman ke backend")
    return p.parse_args()


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
        backend_url = None if args.no_backend else args.backend_url,
    )

    pipeline.run(
        source       = args.source,
        show_preview = not args.no_preview,
        save_video   = args.save_video,
    )