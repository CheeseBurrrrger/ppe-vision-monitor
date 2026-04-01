import os

label_path = "dataset/train/labels"
image_path = "dataset/train/images"

for file in os.listdir(label_path):
    if os.path.getsize(os.path.join(label_path, file)) == 0:
        print("Removing:", file)

        os.remove(os.path.join(label_path, file))

        img_file = file.replace(".txt", ".jpg")
        img_path = os.path.join(image_path, img_file)

        if os.path.exists(img_path):
            os.remove(img_path)