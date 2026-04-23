import argparse
import os
from pathlib import Path

import torch
from ultralytics import YOLO


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT_DIR / "model" / "ppe.yaml"
DEFAULT_OUTPUT_DIR = ROOT_DIR / "runs" / "detect"
DEFAULT_CLASS_NAMES = ["person", "helmet", "vest", "boots", "gloves"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train YOLOv11 for PPE detection with the fastest safe defaults."
    )
    parser.add_argument("--data", default=str(DEFAULT_DATASET), help="Path to dataset YAML")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLOv11 weights or model yaml")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Training image size")
    parser.add_argument(
        "--batch",
        default="auto",
        help="Batch size. Use 'auto' to let the script optimize for available GPU memory.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Training device: 'auto', 'cpu', '0', '0,1', etc.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=-1,
        help="Dataloader workers. -1 chooses a fast automatic value.",
    )
    parser.add_argument(
        "--cache",
        default="disk",
        choices=["ram", "disk", "false"],
        help="Dataset cache mode. 'disk' is a fast and safer default on Windows.",
    )
    parser.add_argument(
        "--name",
        default="train_yolo11_fast",
        help="Run name inside runs/detect",
    )
    parser.add_argument(
        "--project",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory for training results",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=30,
        help="Early stopping patience",
    )
    parser.add_argument(
        "--optimizer",
        default="auto",
        help="Optimizer passed to Ultralytics",
    )
    parser.add_argument(
        "--close-mosaic",
        type=int,
        default=10,
        help="Disable mosaic in the last N epochs for more stable final training",
    )
    parser.add_argument(
        "--compile",
        action="store_true",
        help="Enable torch.compile for extra speed if supported by the environment",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the latest run with the same name",
    )
    parser.add_argument(
        "--exist-ok",
        action="store_true",
        help="Allow overwriting an existing run name",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved training configuration without starting training",
    )
    return parser.parse_args()


def detect_device(device_arg: str) -> str:
    if device_arg != "auto":
        return device_arg
    return "0" if torch.cuda.is_available() else "cpu"


def resolve_workers(workers_arg: int) -> int:
    if workers_arg >= 0:
        return workers_arg
    cpu_count = os.cpu_count() or 4
    return max(2, min(8, cpu_count - 1))


def resolve_batch(batch_arg: str, use_cuda: bool):
    if batch_arg != "auto":
        return int(batch_arg)
    return -1 if use_cuda else 8


def ensure_dataset_yaml(dataset_path: Path):
    if dataset_path.exists() and dataset_path.stat().st_size > 0:
        return

    dataset_root = ROOT_DIR / "dataset"
    yaml_text = "\n".join(
        [
            f"path: {dataset_root.as_posix()}",
            "train: train/images",
            "val: val/images",
            "test: test/images",
            "",
            f"nc: {len(DEFAULT_CLASS_NAMES)}",
            "names:",
            *[f"  {idx}: {name}" for idx, name in enumerate(DEFAULT_CLASS_NAMES)],
            "",
        ]
    )
    dataset_path.write_text(yaml_text, encoding="utf-8")


def main():
    args = parse_args()

    dataset_path = Path(args.data).resolve()
    ensure_dataset_yaml(dataset_path)

    device = detect_device(args.device)
    use_cuda = device != "cpu" and torch.cuda.is_available()
    workers = resolve_workers(args.workers)
    batch = resolve_batch(args.batch, use_cuda)
    cache = False if args.cache == "false" else args.cache
    amp = use_cuda

    train_kwargs = {
        "data": str(dataset_path),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": batch,
        "device": device,
        "workers": workers,
        "cache": cache,
        "project": args.project,
        "name": args.name,
        "patience": args.patience,
        "optimizer": args.optimizer,
        "amp": amp,
        "pretrained": True,
        "cos_lr": False,
        "close_mosaic": args.close_mosaic,
        "plots": True,
        "val": True,
        "exist_ok": args.exist_ok,
        "resume": args.resume,
        "verbose": True,
    }

    if args.compile:
        train_kwargs["compile"] = True

    print("Resolved training configuration:")
    for key, value in train_kwargs.items():
        print(f"- {key}: {value}")

    if use_cuda:
        print(f"- gpu: {torch.cuda.get_device_name(0)}")
    else:
        print("- gpu: not available, using CPU")

    if args.dry_run:
        return

    model = YOLO(args.model)
    model.train(**train_kwargs)


if __name__ == "__main__":
    main()
