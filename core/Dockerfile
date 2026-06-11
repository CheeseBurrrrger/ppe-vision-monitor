FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Layer 1 — heavy deps (torch, torchvision) cached unless requirements.txt changes
# CPU-only wheels are ~280MB vs ~2GB for CUDA builds
COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout 300 --retries 5 torch torchvision \
    --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --timeout 300 --retries 5 -r requirements.txt

COPY core/ ./core/
COPY model/ ./model/

WORKDIR /app/core
EXPOSE 8765
CMD ["python", "ws_server.py"]
