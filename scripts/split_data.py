import argparse
import random
import shutil
from pathlib import Path


IMG_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Split a flat YOLO dataset into train/val/test folders."
    )
    parser.add_argument("--train", type=float, default=0.8, help="Train ratio")
    parser.add_argument("--val", type=float, default=0.1, help="Validation ratio")
    parser.add_argument("--test", type=float, default=0.1, help="Test ratio")
    parser.add_argument("--seed", type=int, default=42, help="Shuffle seed")
    return parser.parse_args()


def clear_split_dirs(dataset_dir: Path):
    for split in ("train", "val", "test"):
        split_dir = dataset_dir / split
        if split_dir.exists():
            shutil.rmtree(split_dir)


def main():
    args = parse_args()
    total_ratio = args.train + args.val + args.test
    if abs(total_ratio - 1.0) > 1e-9:
        raise ValueError("train + val + test must equal 1.0")

    base_dir = Path(__file__).resolve().parents[1]
    dataset_dir = base_dir / "dataset"
    image_dir = dataset_dir / "images"
    label_dir = dataset_dir / "labels"

    if not image_dir.exists() or not label_dir.exists():
        raise FileNotFoundError("Expected dataset/images and dataset/labels to exist")

    images = sorted(
        file for file in image_dir.iterdir() if file.is_file() and file.suffix.lower() in IMG_EXTENSIONS
    )
    if not images:
        raise ValueError("No image files found in dataset/images")

    valid_pairs = []
    missing_labels = []
    for image_path in images:
        label_path = label_dir / f"{image_path.stem}.txt"
        if label_path.exists():
            valid_pairs.append((image_path, label_path))
        else:
            missing_labels.append(image_path.name)

    if not valid_pairs:
        raise ValueError("No matching image/label pairs found")

    rng = random.Random(args.seed)
    rng.shuffle(valid_pairs)

    total = len(valid_pairs)
    train_end = int(total * args.train)
    val_end = train_end + int(total * args.val)

    splits = {
        "train": valid_pairs[:train_end],
        "val": valid_pairs[train_end:val_end],
        "test": valid_pairs[val_end:],
    }

    clear_split_dirs(dataset_dir)

    for split, files in splits.items():
        split_image_dir = dataset_dir / split / "images"
        split_label_dir = dataset_dir / split / "labels"
        split_image_dir.mkdir(parents=True, exist_ok=True)
        split_label_dir.mkdir(parents=True, exist_ok=True)

        for image_path, label_path in files:
            shutil.copy2(image_path, split_image_dir / image_path.name)
            shutil.copy2(label_path, split_label_dir / label_path.name)

    print("Dataset split complete")
    print(f"Seed: {args.seed}")
    print(f"Total valid pairs: {total}")
    for split, files in splits.items():
        print(f"{split}: {len(files)}")

    if missing_labels:
        print(f"Skipped images without labels: {len(missing_labels)}")


if __name__ == "__main__":
    main()
