import os
import shutil

BASE = "dataset"

splits = ["train", "val", "test"]

for split in splits:
    print(f"\nProcessing {split}...")

    # path lama (nested)
    old_img = f"{BASE}/images/{split}/images"
    old_lbl = f"{BASE}/images/{split}/labels"

    # path tujuan
    new_img = f"{BASE}/{split}/images"
    new_lbl = f"{BASE}/{split}/labels"

    os.makedirs(new_img, exist_ok=True)
    os.makedirs(new_lbl, exist_ok=True)

    # pindah images
    if os.path.exists(old_img):
        for file in os.listdir(old_img):
            shutil.move(os.path.join(old_img, file),
                        os.path.join(new_img, file))

    # pindah labels
    if os.path.exists(old_lbl):
        for file in os.listdir(old_lbl):
            shutil.move(os.path.join(old_lbl, file),
                        os.path.join(new_lbl, file))

print("\nDONE FIX STRUCTURE")