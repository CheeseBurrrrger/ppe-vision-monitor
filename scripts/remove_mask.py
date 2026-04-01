import os

label_path = "dataset/train/labels"

for file in os.listdir(label_path):
    file_path = os.path.join(label_path, file)

    new_lines = []

    with open(file_path, "r") as f:
        lines = f.readlines()

        for line in lines:
            cls = int(line.split()[0])

            if cls == 1:
                continue  # hapus mask

            new_lines.append(line)

    with open(file_path, "w") as f:
        f.writelines(new_lines)