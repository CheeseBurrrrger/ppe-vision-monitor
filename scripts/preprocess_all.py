import os
import shutil

# =========================
# CONFIG
# =========================
DATASET_PATH = "dataset"
SPLITS = ["train", "val", "test"]

# mapping class lama → baru
CLASS_MAPPING = {
    0: 0,  # helmet
    2: 1,  # vest
    3: 2,  # boots
    4: 3   # gloves
}

VALID_CLASSES = [0, 1, 2, 3]

# =========================
# STEP 1: REMOVE MASK + REMAP
# =========================
def process_labels():
    print("\n[STEP 1] Remove Mask + Remap")

    for split in SPLITS:
        label_path = os.path.join(DATASET_PATH, split, "labels")

        if not os.path.exists(label_path):
            print(f"Skip {split}")
            continue

        for file in os.listdir(label_path):
            file_path = os.path.join(label_path, file)

            new_lines = []

            with open(file_path, "r") as f:
                lines = f.readlines()

                for line in lines:
                    parts = line.strip().split()
                    cls = int(parts[0])

                    # hapus mask
                    if cls == 1:
                        continue

                    # remap class
                    if cls in CLASS_MAPPING:
                        parts[0] = str(CLASS_MAPPING[cls])
                        new_lines.append(" ".join(parts) + "\n")

            with open(file_path, "w") as f:
                f.writelines(new_lines)

    print("✔ Mask removed & class remapped")


# =========================
# STEP 2: REMOVE EMPTY FILES
# =========================
def remove_empty():
    print("\n[STEP 2] Remove Empty Labels + Images")

    for split in SPLITS:
        label_path = os.path.join(DATASET_PATH, split, "labels")
        image_path = os.path.join(DATASET_PATH, split, "images")

        if not os.path.exists(label_path):
            continue

        for file in os.listdir(label_path):
            file_path = os.path.join(label_path, file)

            if os.path.getsize(file_path) == 0:
                print(f"Remove empty: {file}")

                os.remove(file_path)

                # handle jpg/png
                base = file.replace(".txt", "")
                for ext in [".jpg", ".png"]:
                    img_path = os.path.join(image_path, base + ext)
                    if os.path.exists(img_path):
                        os.remove(img_path)

    print("✔ Empty files cleaned")


# =========================
# STEP 3: VALIDATION
# =========================
def validate():
    print("\n[STEP 3] Validation Check")

    total = 0

    for split in SPLITS:
        label_path = os.path.join(DATASET_PATH, split, "labels")

        if not os.path.exists(label_path):
            continue

        for file in os.listdir(label_path):
            with open(os.path.join(label_path, file)) as f:
                for line in f:
                    cls = int(line.split()[0])

                    if cls not in VALID_CLASSES:
                        print(f"Invalid class {cls} in {file}")

            total += 1

    print(f"✔ Checked {total} label files")


# =========================
# STEP 4: DATA SUMMARY
# =========================
def summary():
    print("\n[STEP 4] Dataset Summary")

    for split in SPLITS:
        img_path = os.path.join(DATASET_PATH, split, "images")

        if not os.path.exists(img_path):
            continue

        total = len(os.listdir(img_path))
        print(f"{split}: {total} images")


# =========================
# MAIN
# =========================
if __name__ == "__main__":
    process_labels()
    remove_empty()
    validate()
    summary()

    print("\nPREPROCESSING SELESAI")