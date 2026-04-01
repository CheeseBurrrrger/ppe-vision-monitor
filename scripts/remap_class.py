import os

label_path = "dataset/train/labels"

mapping = {
    0: 0,  # helmet
    2: 1,  # vest
    3: 2,  # boots
    4: 3   # gloves
}

for file in os.listdir(label_path):
    file_path = os.path.join(label_path, file)

    new_lines = []

    with open(file_path, "r") as f:
        lines = f.readlines()

        for line in lines:
            parts = line.split()
            cls = int(parts[0])

            if cls in mapping:
                parts[0] = str(mapping[cls])
                new_lines.append(" ".join(parts) + "\n")

    with open(file_path, "w") as f:
        f.writelines(new_lines)