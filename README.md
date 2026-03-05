# ppe-vision-monitor

> **PPE Compliance Monitoring System** — Computer Vision-based automatic detection of Personal Protective Equipment (PPE) violations in industrial environments.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00BFFF?style=flat)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18+-61DAFB?style=flat&logo=react&logoColor=black)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)
![Status](https://img.shields.io/badge/Status-PoC%200.1-orange?style=flat)

---

## Overview

This project is a **Proof of Concept (PoC)** for an automated PPE compliance monitoring system built using Computer Vision. It detects PPE violations (missing helmet, missing safety vest) from video files or webcam input, logs violations to a local database, and displays analytics through a web dashboard.

Built as a capstone project in collaboration with **PT Epson Indonesia**, with the goal of proving that a lightweight, locally-run CV monitoring system is technically feasible without dedicated GPU infrastructure.

### What it does

- Detects **helmet** and **safety vest** compliance using YOLOv8n (CPU-compatible)
- Generates structured violation events with timestamp and confidence score
- Stores all events in a local SQLite database
- Displays violation analytics via a React dashboard (Review Mode)
- Architecture is designed to support Live Mode (WebSocket) in a future iteration

### What it does NOT do

- No face recognition or individual worker identification
- No cloud deployment or external server dependency
- No integration with company internal systems
- Not validated against real production environment data

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Detection | YOLOv8n (Ultralytics) | Object detection — helmet, vest, safety boot |
| Frame processing | OpenCV | Video/webcam reading, frame extraction |
| Violation logic | Python (rule-based) | Evaluate detections → generate violation events |
| Database | SQLite | Local violation event storage |
| Backend API | FastAPI | REST endpoints + WebSocket skeleton |
| Frontend | React + Tailwind CSS | Dashboard UI |
| Charts | Recharts | Violation analytics visualization |
| Export | Pandas | CSV export from violation data |

---

## Project Structure

```
ppe-vision-monitor/
├── README.md
├── requirements.txt
├── .gitignore
│
├── model/                      # ML/AI — training & export
│   ├── train.py                # YOLOv8n fine-tuning script
│   ├── evaluate.py             # mAP50, confusion matrix evaluation
│   ├── export_onnx.py          # Export best.pt → best.onnx
│   ├── ppe.yaml                # Dataset configuration
│   └── runs/                   # Training outputs (gitignored)
│
├── core/                       # Computer Vision — inference pipeline
│   ├── frame_reader.py         # Read video/webcam, extract frames
│   ├── detector.py             # Load model, run inference per frame
│   ├── violation_logic.py      # Rule-based: no_helmet / no_vest + cooldown
│   └── db_writer.py            # Write violation events to SQLite
│
├── backend/                    # IT/Web — FastAPI backend
│   ├── main.py                 # FastAPI app entry point
│   ├── database.py             # SQLite connection & queries
│   └── routers/
│       └── violations.py       # /violations, /stats, /export-csv endpoints
│
├── frontend/                   # IT/Web — React dashboard
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── ViolationTable.jsx
│           ├── ViolationBarChart.jsx
│           └── ViolationTimeChart.jsx
```

---

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.10+
- Node.js 18+ and npm
- Git

### 1. Clone the repository

```bash
git clone https://github.com/[your-username]/ppe-vision-monitor.git
cd ppe-vision-monitor
```

### 2. Set up Python environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Download model weights

Model weights are not stored in this repository due to file size.  
Download from the shared Google Drive link (ask the team for access):

```
/models/best.pt     ← YOLOv8n fine-tuned weights (PyTorch)
/models/best.onnx   ← Exported ONNX format (for CPU inference)
```

Place the files in a `/models` folder at the project root.

> If you want to train from scratch, see [Training the Model](#training-the-model).

### 4. Initialize the database

```bash
python core/db_writer.py --init
```

This creates `violations.db` in the project root with the required schema.

### 5. Run inference on a video file

```bash
python core/frame_reader.py --source path/to/video.mp4 --model models/best.onnx
```

For webcam input:

```bash
python core/frame_reader.py --source webcam --model models/best.onnx
```

### 6. Start the backend API

```bash
cd backend
uvicorn main:app --reload --port 8000
```

API documentation available at: `http://localhost:8000/docs`

### 7. Start the frontend dashboard

```bash
cd frontend
npm install
npm run dev
```

Dashboard available at: `http://localhost:5173`

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/violations` | List all violation events (supports filter by type, date) |
| GET | `/stats` | Aggregated stats: total, per type, per hour |
| GET | `/export-csv` | Download all violations as CSV file |
| GET | `/health` | Health check |
| WS | `/ws/live` | WebSocket for Live Mode *(PoC 0.2 — skeleton only)* |

---

## Training the Model

If you want to fine-tune the model from scratch:

### 1. Prepare dataset

Download a PPE dataset from [Roboflow Universe](https://universe.roboflow.com) with classes:
`helmet`, `vest`, `safety_boot`, `person`

Export in **YOLOv8 format** and place in:

```
data/
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

Update `model/ppe.yaml` with your dataset path and class names.

### 2. Run training

```bash
# GPU (recommended for training)
python model/train.py --epochs 100 --imgsz 640 --device 0

# CPU only (slow, use only if no GPU available)
python model/train.py --epochs 50 --imgsz 416 --device cpu
```

### 3. Evaluate

```bash
python model/evaluate.py --weights model/runs/train/exp/weights/best.pt
```

### 4. Export to ONNX

```bash
python model/export_onnx.py --weights model/runs/train/exp/weights/best.pt
```

---

## Branching Strategy

This project uses a simplified GitHub Flow with area prefixes.

### Branch naming

```
feature/[area]-[short-description]
fix/[area]-[short-description]

Areas: ml | cv | be | fe | docs
```

Examples:
```
feature/ml-yolov8-finetune
feature/cv-violation-logic
feature/be-violations-endpoint
feature/fe-recharts-integration
fix/cv-fps-drop
docs/update-setup-guide
```

### Rules

1. **Never push directly to `main` or `develop`** — all changes via Pull Request
2. **All PRs require at least 1 reviewer** before merging to `develop`
3. **Feature branches live max 1 sprint** (1 week) — if longer, break it down
4. **`main` is only updated at official checkpoints:**

```
v0.0.1  ← Pre-Sprint complete (repo active)
v0.1.0  ← Checkpoint 1 (Apr 6–10)
v1.0.0  ← Checkpoint 2 (Apr 27–May 1)
v1.0.0-final ← Capstone Expo (May 18–22)
```

### Commit message format

```
[area] verb + short object

Examples:
[ml] add YOLOv8n fine-tuning script
[cv] fix cooldown timer duplication bug
[be] add GET /violations endpoint with date filter
[fe] integrate Recharts bar chart component
[docs] update README setup instructions
```

---

## Violation Logic

The system uses a **rule-based approach** per frame:

```
Frame in
  └─ Person detected?
       ├─ No  → skip frame
       └─ Yes
            ├─ Helmet detected? No  → generate no_helmet event
            └─ Vest detected?   No  → generate no_vest event
                 └─ (any violation generated) → write to SQLite
                                              → set cooldown timer (5s)
```

**Cooldown timer:** prevents duplicate events for the same violation within a 5-second window.

**Confidence threshold:** detections below 0.5 confidence are ignored.

---

## Known Limitations (PoC 0.1)

- Validated on public datasets only — not tested against real factory footage
- CPU inference FPS: ~5–10 FPS depending on laptop spec (not real-time industrial grade)
- No individual worker tracking (by design — privacy)
- `safety_boot` detection is available as a class but accuracy may be low due to small object size and occlusion in public datasets
- Live Mode (WebSocket) is scaffolded but not active in this release

---

## Roadmap

- [x] Project setup & repository structure
- [ ] Dataset preparation & YOLOv8n fine-tuning
- [ ] Frame extraction pipeline (OpenCV)
- [ ] Violation logic engine + SQLite writer
- [ ] FastAPI REST endpoints
- [ ] React dashboard — Review Mode
- [ ] CSV export
- [ ] Model export to ONNX
- [ ] End-to-end demo (CP1)
- [ ] Dashboard filters & polish (CP2)
- [ ] WebSocket Live Mode *(stretch goal)*
- [ ] safety_boot detection *(stretch goal)*

---

## Team

| Role | Area |
|---|---|
| Project Manager | Coordination, UI design, documentation |
| ML/AI Engineer × 2 | Dataset, model training, ONNX export |
| Computer Vision Engineer × 2 | Inference pipeline, violation logic |
| IT / Web Developer × 2 | FastAPI backend, React frontend |

Capstone project — [Universitas Brawijaya]  
Industry partner: **PT Epson Indonesia**

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Bahasa Indonesia

### Tentang Proyek

Sistem ini adalah Proof of Concept (PoC) monitoring kepatuhan APD berbasis Computer Vision. Sistem mendeteksi pelanggaran penggunaan helm dan rompi keselamatan dari input video atau webcam, mencatat pelanggaran ke database lokal, dan menampilkan rekap melalui dashboard web.

Dikembangkan sebagai proyek capstone bekerja sama dengan **PT Epson Indonesia**, dengan tujuan membuktikan bahwa sistem monitoring berbasis CV dapat berjalan secara lokal tanpa GPU eksternal maupun infrastruktur industri tambahan.

### Cara Menjalankan (Ringkas)

```bash
# 1. Clone & install dependencies
git clone https://github.com/CheeseBurrrrger/ppe-vision-monitor.git
cd ppe-vision-monitor
pip install -r requirements.txt

# 2. Init database
python core/db_writer.py --init

# 3. Jalankan inference
python core/frame_reader.py --source path/video.mp4 --model models/best.onnx

# 4. Jalankan backend
cd backend && uvicorn main:app --reload --port 8000

# 5. Jalankan frontend
cd frontend && npm install && npm run dev
```

### Kontribusi

Lihat [branching strategy](#branching-strategy) untuk panduan kontribusi dan naming convention branch.
