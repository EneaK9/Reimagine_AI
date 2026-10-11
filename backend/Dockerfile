# ReimagineAI API — CPU image for Hetzner / VPS
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System libs for OpenCV / Open3D / rembg
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libx11-6 \
    && rm -rf /var/lib/apt/lists/*

# CPU PyTorch first (much smaller than CUDA wheels)
RUN pip install --upgrade pip \
    && pip install \
      torch torchvision \
      --index-url https://download.pytorch.org/whl/cpu

# App deps (torch already installed)
COPY requirements.txt .
RUN grep -vE '^(torch|torchvision)([=<]|$)' requirements.txt > /tmp/reqs.txt \
    && pip install -r /tmp/reqs.txt

# Scene geometry model code: MoGe-2 (MIT), pinned to the last release before
# MoGe-3 (which needs CUDA). --no-deps: inference only needs what's above;
# its declared deps pull in a whole demo stack (gradio).
RUN pip install --no-deps \
      "moge @ https://github.com/microsoft/MoGe/archive/07444410f1e33f402353b99d6ccd26bd31e469e8.zip" \
      "utils3d @ https://github.com/EasternJournalist/utils3d/archive/3fab839f0be9931dac7c8488eb0e1600c236e183.zip" \
    && python -c "from moge.model.v2 import MoGeModel"

COPY app ./app
COPY data/catalog ./data/catalog

RUN mkdir -p /app/data/meshes /app/data/generated /app/data/scene_images /app/data/rooms

EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8100/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
