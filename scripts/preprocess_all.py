import os


DATASET_PATH = "dataset"
RAW_LABELS_PATH = os.path.join(DATASET_PATH, "labels")
SPLITS = ["train", "val", "test"]
IMAGE_EXTENSIONS = [".jpg", ".jpeg", ".png"]

# Assumption based on raw labels in dataset/labels:
# 0=person, 2=helmet, 3=vest, 4=boots, 5=gloves.
CLASS_MAPPING = {
    0: 0,  # person
    2: 1,  # helmet
    3: 2,  # vest
    4: 3,  # boots
    5: 4,  # gloves
}

VALID_CLASSES = list(range(5))


def process_labels():
    print("\n[STEP 1] Rebuild Labels From Raw + Remap")

    for split in SPLITS:
        image_path = os.path.join(DATASET_PATH, split, "images")
        label_path = os.path.join(DATASET_PATH, split, "labels")

        if not os.path.exists(image_path) or not os.path.exists(label_path):
            print(f"Skip {split}")
            continue

        for image_name in os.listdir(image_path):
            base, _ = os.path.splitext(image_name)
            raw_label_path = os.path.join(RAW_LABELS_PATH, base + ".txt")
            output_label_path = os.path.join(label_path, base + ".txt")
            new_lines = []

            if os.path.exists(raw_label_path):
                with open(raw_label_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) != 5:
                            continue

                        cls = int(parts[0])
                        if cls in CLASS_MAPPING:
                            parts[0] = str(CLASS_MAPPING[cls])
                            new_lines.append(" ".join(parts) + "\n")

            with open(output_label_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

    print("✔ Raw labels rebuilt and remapped")


def remove_empty():
    print("\n[STEP 2] Remove Empty Labels + Images")

    for split in SPLITS:
        label_path = os.path.join(DATASET_PATH, split, "labels")
        image_path = os.path.join(DATASET_PATH, split, "images")

        if not os.path.exists(label_path) or not os.path.exists(image_path):
            continue

        for file in os.listdir(label_path):
            file_path = os.path.join(label_path, file)

            if os.path.getsize(file_path) == 0:
                print(f"Remove empty: {file}")
                os.remove(file_path)

                base = file.replace(".txt", "")
                for ext in IMAGE_EXTENSIONS:
                    img_path = os.path.join(image_path, base + ext)
                    if os.path.exists(img_path):
                        os.remove(img_path)

    print("✔ Empty files cleaned")


def validate():
    print("\n[STEP 3] Validation Check")

    total = 0

    for split in SPLITS:
        label_path = os.path.join(DATASET_PATH, split, "labels")

        if not os.path.exists(label_path):
            continue

        for file in os.listdir(label_path):
            with open(os.path.join(label_path, file), "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.split()
                    if not parts:
                        continue

                    cls = int(parts[0])
                    if cls not in VALID_CLASSES:
                        print(f"Invalid class {cls} in {file}")

            total += 1

    print(f"✔ Checked {total} label files")


def summary():
    print("\n[STEP 4] Dataset Summary")

    for split in SPLITS:
        img_path = os.path.join(DATASET_PATH, split, "images")
        lbl_path = os.path.join(DATASET_PATH, split, "labels")

        if not os.path.exists(img_path) or not os.path.exists(lbl_path):
            continue

        print(f"{split}: {len(os.listdir(img_path))} images, {len(os.listdir(lbl_path))} labels")


if __name__ == "__main__":
    process_labels()
    remove_empty()
    validate()
    summary()
    print("\nPREPROCESSING SELESAI")
