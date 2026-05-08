FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the project root
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ ./core/
COPY model/ ./model/

WORKDIR /app/core
EXPOSE 8765
CMD ["python", "ws_server.py"]
