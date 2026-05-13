import os

# auto detect root project
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_PATH = os.path.join(BASE_DIR, "dataset")

SPLITS = ["train", "val", "test"]

classes_found = set()

for split in SPLITS:
    label_path = os.path.join(DATASET_PATH, split, "labels")

    if not os.path.exists(label_path):
        print(f"Tidak ada folder: {label_path}")
        continue

    for file in os.listdir(label_path):
        with open(os.path.join(label_path, file)) as f:
            for line in f:
                cls = int(line.split()[0])
                classes_found.add(cls)

print("Classes found:", classes_found)

img = set([f.split('.')[0] for f in os.listdir("../dataset/train/images")])
lbl = set([f.split('.')[0] for f in os.listdir("../dataset/train/labels")])

print("Missing label:", img - lbl)
print("Missing image:", lbl - img)