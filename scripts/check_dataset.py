import os

# auto detect root project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "dataset")

SPLITS = ["train", "val", "test"]
IMG_EXT = [".jpg", ".png", ".jpeg"]

def get_base_names(files):
    return set(os.path.splitext(f)[0] for f in files)

def check_split(split):
    print(f"\n===== CHECKING {split.upper()} =====")

    img_path = os.path.join(DATASET_PATH, split, "images")
    lbl_path = os.path.join(DATASET_PATH, split, "labels")

    if not os.path.exists(img_path) or not os.path.exists(lbl_path):
        print("Folder tidak lengkap")
        return

    images = [f for f in os.listdir(img_path) if os.path.splitext(f)[1] in IMG_EXT]
    labels = [f for f in os.listdir(lbl_path) if f.endswith(".txt")]

    img_set = get_base_names(images)
    lbl_set = get_base_names(labels)

    # =========================
    # CHECK 1: MISSING
    # =========================
    missing_labels = img_set - lbl_set
    missing_images = lbl_set - img_set

    print(f"Total Images : {len(images)}")
    print(f"Total Labels : {len(labels)}")

    print("\n[Missing Labels]")
    print(missing_labels if missing_labels else "✔ Tidak ada")

    print("\n[Missing Images]")
    print(missing_images if missing_images else "✔ Tidak ada")

    # =========================
    # CHECK 2: EMPTY LABEL
    # =========================
    empty_labels = []
    for f in labels:
        path = os.path.join(lbl_path, f)
        if os.path.getsize(path) == 0:
            empty_labels.append(f)

    print("\n[Empty Labels]")
    print(empty_labels if empty_labels else "✔ Tidak ada")

    # =========================
    # CHECK 3: INVALID FORMAT
    # =========================
    invalid = []
    for f in labels:
        path = os.path.join(lbl_path, f)
        with open(path) as file:
            for line in file:
                parts = line.strip().split()
                if len(parts) != 5:
                    invalid.append(f)
                    break

    print("\n[Invalid Format Labels]")
    print(invalid if invalid else "✔ Tidak ada")

    # =========================
    # SUMMARY
    # =========================
    if not missing_labels and not missing_images and not empty_labels and not invalid:
        print("\nDATASET BAGUS (AMAN)")
    else:
        print("\nDATASET PERLU DIPERBAIKI")


def main():
    print("DATASET CHECK START")
    for split in SPLITS:
        check_split(split)
    print("\nDONE")


if __name__ == "__main__":
    main()