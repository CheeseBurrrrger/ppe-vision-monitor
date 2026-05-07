"""
frame_reader.py
===============
Script untuk membaca video (webcam / file / RTSP) dan menyimpan frame.
Bagian dari Capstone Project: Sistem Monitoring K3 Berbasis Computer Vision

Fitur:
  - Baca dari webcam, file video (.mp4/.avi/dll), atau RTSP stream
  - Simpan frame sebagai gambar .jpg dengan nama terurut
  - Filter berdasarkan interval (simpan tiap N frame, bukan semua)
  - Preview live di jendela OpenCV (bisa dimatikan)
  - Progress bar di terminal
  - Laporan ringkasan di akhir

Cara pakai:
  python frame_reader.py --source 0                         # webcam
  python frame_reader.py --source video.mp4                 # file video
  python frame_reader.py --source rtsp://ip:port/stream     # kamera IP
  python frame_reader.py --source video.mp4 --interval 5   # simpan tiap 5 frame
  python frame_reader.py --source video.mp4 --max 200      # simpan max 200 frame
"""

import cv2
import os
import time
import argparse
from pathlib import Path
from datetime import datetime


# ─────────────────────────────────────────────
#  KONFIGURASI DEFAULT
# ─────────────────────────────────────────────
DEFAULT_OUTPUT_DIR  = "saved_frames"   # folder tujuan simpan frame
DEFAULT_INTERVAL    = 1                # simpan setiap N frame (1 = semua frame)
DEFAULT_MAX_FRAMES  = 0                # 0 = tidak ada batas
DEFAULT_IMG_QUALITY = 95               # kualitas JPEG (0-100)
DEFAULT_RESIZE      = None             # None = ukuran asli. Contoh: (640, 480)


# ─────────────────────────────────────────────
#  FUNGSI UTAMA
# ─────────────────────────────────────────────

def open_source(source):
    """
    Buka sumber video. Otomatis deteksi tipe:
      - Integer (0, 1, 2) → webcam
      - String angka ("0") → webcam
      - Path file          → file video lokal
      - String rtsp://...  → kamera IP / RTSP
    """
    # Konversi ke int jika source adalah angka (webcam index)
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    if isinstance(source, int):
        print(f"[INFO] Membuka webcam index {source} ...")
        cap = cv2.VideoCapture(source)
    elif isinstance(source, str) and source.lower().startswith("rtsp://"):
        print(f"[INFO] Membuka RTSP stream: {source}")
        # CAP_FFMPEG lebih stabil untuk RTSP
        cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # buffer kecil = latency rendah
    else:
        print(f"[INFO] Membuka file video: {source}")
        cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        raise RuntimeError(
            f"[ERROR] Tidak bisa membuka sumber: {source}\n"
            "Pastikan:\n"
            "  - Index webcam benar (coba 0, 1, 2)\n"
            "  - Path file video ada dan tidak typo\n"
            "  - URL RTSP benar dan kamera online\n"
            "  - Driver kamera / codec video terinstall"
        )

    return cap


def get_video_info(cap):
    """Ambil metadata video dari objek VideoCapture."""
    fps    = cap.get(cv2.CAP_PROP_FPS)
    width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))  # 0 untuk webcam/RTSP

    return {
        "fps":    fps if fps > 0 else 30.0,
        "width":  width,
        "height": height,
        "total":  total,  # total frame di file video; 0 jika live stream
    }


def make_output_dir(base_dir: str, source) -> Path:
    """
    Buat folder output dengan nama unik berdasarkan timestamp.
    Contoh: saved_frames/video_20250312_143022/
    """
    # Tentukan prefix nama folder
    if isinstance(source, int):
        prefix = f"webcam{source}"
    elif isinstance(source, str) and source.lower().startswith("rtsp://"):
        prefix = "rtsp"
    else:
        # Ambil nama file tanpa ekstensi
        prefix = Path(source).stem

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = Path(base_dir) / f"{prefix}_{timestamp}"
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"[INFO] Folder output: {output_path.resolve()}")
    return output_path


def print_progress(saved: int, read: int, total: int, fps_actual: float):
    """Tampilkan progress sederhana di terminal (overwrite baris yang sama)."""
    if total > 0:
        pct = read / total * 100
        bar_len = 30
        filled  = int(bar_len * read / total)
        bar     = "█" * filled + "░" * (bar_len - filled)
        print(
            f"\r  [{bar}] {pct:5.1f}%  "
            f"dibaca={read}/{total}  disimpan={saved}  "
            f"{fps_actual:.1f}fps",
            end="", flush=True
        )
    else:
        # Live stream: tidak tahu total frame
        print(
            f"\r  Dibaca={read}  Disimpan={saved}  {fps_actual:.1f}fps   ",
            end="", flush=True
        )


def read_and_save_frames(
    source,
    output_dir:  str   = DEFAULT_OUTPUT_DIR,
    interval:    int   = DEFAULT_INTERVAL,
    max_frames:  int   = DEFAULT_MAX_FRAMES,
    img_quality: int   = DEFAULT_IMG_QUALITY,
    resize                    = DEFAULT_RESIZE,
    show_preview: bool = True,
):
    """
    Fungsi utama: baca video frame-by-frame dan simpan ke disk.

    Parameter:
        source       : sumber video (int webcam / str file / str rtsp)
        output_dir   : folder tempat menyimpan frame
        interval     : simpan 1 frame setiap N frame dibaca
        max_frames   : batas maksimal frame yang disimpan (0 = tidak terbatas)
        img_quality  : kualitas JPEG (1-100)
        resize       : tuple (w, h) atau None untuk ukuran asli
        show_preview : tampilkan jendela preview (True/False)

    Return:
        dict berisi statistik: total_read, total_saved, output_path, dll
    """

    # 1. Buka sumber video
    cap  = open_source(source)
    info = get_video_info(cap)

    print(f"[INFO] Resolusi  : {info['width']}x{info['height']}")
    print(f"[INFO] FPS video : {info['fps']:.2f}")
    if info['total'] > 0:
        durasi = info['total'] / info['fps']
        print(f"[INFO] Total frame: {info['total']} (~{durasi:.1f} detik)")
    else:
        print(f"[INFO] Total frame: (live stream, tidak diketahui)")

    # 2. Buat folder output
    out_path = make_output_dir(output_dir, source)

    # 3. Siapkan variabel tracking
    frame_read  = 0   # jumlah frame yang sudah dibaca dari sumber
    frame_saved = 0   # jumlah frame yang berhasil disimpan
    t_start     = time.perf_counter()
    t_last      = t_start

    print(f"\n[INFO] Mulai membaca. Tekan 'q' di jendela preview untuk berhenti.\n")

    # 4. Loop baca frame
    while True:
        ret, frame = cap.read()

        # --- Handle end-of-stream atau error baca ---
        if not ret:
            if isinstance(source, str) and not source.startswith("rtsp://"):
                # File video habis → normal, selesai
                print(f"\n[INFO] Akhir file video tercapai.")
            else:
                print(f"\n[WARN] Frame tidak terbaca (stream putus atau selesai).")
            break

        frame_read += 1

        # --- Hitung FPS aktual setiap detik ---
        now = time.perf_counter()
        if now - t_last >= 1.0:
            elapsed   = now - t_start
            fps_actual = frame_read / elapsed if elapsed > 0 else 0
            t_last    = now
        else:
            elapsed   = now - t_start
            fps_actual = frame_read / elapsed if elapsed > 0 else 0

        # --- Filter interval: simpan hanya tiap N frame ---
        if frame_read % interval != 0:
            # Tampilkan preview meski tidak disimpan
            if show_preview:
                cv2.imshow("Frame Reader - Preview [q=quit]", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print(f"\n[INFO] Dihentikan oleh pengguna (tekan q).")
                    break
            continue

        # --- Resize frame jika diminta ---
        if resize is not None:
            frame = cv2.resize(frame, resize, interpolation=cv2.INTER_AREA)

        # --- Buat nama file: frame_000001.jpg ---
        filename   = f"frame_{frame_saved:06d}.jpg"
        save_path  = out_path / filename

        # --- Simpan frame ke disk ---
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, img_quality]
        success = cv2.imwrite(str(save_path), frame, encode_params)

        if not success:
            print(f"\n[ERROR] Gagal menyimpan {filename}. Disk penuh?")
            break

        frame_saved += 1

        # --- Update progress bar di terminal ---
        print_progress(frame_saved, frame_read, info['total'], fps_actual)

        # --- Tampilkan preview ---
        if show_preview:
            # Tambahkan teks info pada preview (tidak mempengaruhi gambar tersimpan)
            preview = frame.copy()
            cv2.putText(
                preview,
                f"Saved: {frame_saved}  |  Read: {frame_read}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                (0, 255, 0), 2
            )
            cv2.imshow("Frame Reader - Preview [q=quit]", preview)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print(f"\n[INFO] Dihentikan oleh pengguna (tekan q).")
                break

        # --- Cek batas maksimal frame ---
        if max_frames > 0 and frame_saved >= max_frames:
            print(f"\n[INFO] Batas maksimal frame tercapai ({max_frames}).")
            break

    # 5. Cleanup
    cap.release()
    cv2.destroyAllWindows()

    # 6. Laporan akhir
    total_time = time.perf_counter() - t_start
    print(f"\n")
    print("=" * 55)
    print("  LAPORAN SELESAI")
    print("=" * 55)
    print(f"  Total frame dibaca   : {frame_read}")
    print(f"  Total frame disimpan : {frame_saved}")
    print(f"  Interval simpan      : setiap {interval} frame")
    print(f"  Waktu proses         : {total_time:.2f} detik")
    print(f"  Lokasi frame         : {out_path.resolve()}")
    print("=" * 55)

    return {
        "total_read":   frame_read,
        "total_saved":  frame_saved,
        "output_path":  str(out_path.resolve()),
        "elapsed_sec":  total_time,
    }


# ─────────────────────────────────────────────
#  ARGUMEN COMMAND LINE
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Baca video dan simpan frame sebagai gambar JPG.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""
Contoh pemakaian:
  python frame_reader.py --source 0
  python frame_reader.py --source rekaman.mp4
  python frame_reader.py --source rekaman.mp4 --interval 10 --max 500
  python frame_reader.py --source rtsp://admin:pass@192.168.1.100:554/stream1
  python frame_reader.py --source rekaman.mp4 --output dataset_apd --no-preview
        """
    )

    parser.add_argument(
        "--source", required=True,
        help="Sumber video:\n"
             "  0         → webcam pertama\n"
             "  1         → webcam kedua\n"
             "  file.mp4  → file video lokal\n"
             "  rtsp://.. → kamera IP / RTSP stream"
    )
    parser.add_argument(
        "--output", default=DEFAULT_OUTPUT_DIR,
        help=f"Folder output untuk menyimpan frame (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL,
        help="Simpan 1 frame setiap N frame dibaca (default: 1 = semua frame)\n"
             "Contoh: --interval 5 = simpan frame ke-5, 10, 15, 20, ..."
    )
    parser.add_argument(
        "--max", type=int, dest="max_frames", default=DEFAULT_MAX_FRAMES,
        help="Batas maksimal frame yang disimpan (default: 0 = tidak terbatas)"
    )
    parser.add_argument(
        "--quality", type=int, default=DEFAULT_IMG_QUALITY,
        help=f"Kualitas JPEG 1-100 (default: {DEFAULT_IMG_QUALITY})"
    )
    parser.add_argument(
        "--resize", type=str, default=None,
        help="Resize frame sebelum disimpan. Format: WIDTHxHEIGHT\n"
             "Contoh: --resize 640x480"
    )
    parser.add_argument(
        "--no-preview", action="store_true",
        help="Matikan jendela preview OpenCV (lebih cepat)"
    )

    return parser.parse_args()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()

    # Parse resize jika ada
    resize = None
    if args.resize:
        try:
            w, h   = args.resize.lower().split("x")
            resize = (int(w), int(h))
        except ValueError:
            print(f"[ERROR] Format --resize salah: '{args.resize}'. Gunakan format WxH, contoh: 640x480")
            exit(1)

    # Jalankan!
    result = read_and_save_frames(
        source       = args.source,
        output_dir   = args.output,
        interval     = args.interval,
        max_frames   = args.max_frames,
        img_quality  = args.quality,
        resize       = resize,
        show_preview = not args.no_preview,
    )
