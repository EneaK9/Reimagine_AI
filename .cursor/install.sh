#!/usr/bin/env bash
# Cloud Agent install: refresh system + Python dependencies for the ReimagineAI
# backend. Idempotent — safe to run repeatedly and against a cached snapshot.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[install] Installing system packages (PostgreSQL, build tools, native libs)..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
# libgl1/libglib2.0-0/libgomp1/libx11-6 are required by opencv-python / open3d / rembg.
sudo apt-get install -y --no-install-recommends \
  postgresql postgresql-contrib \
  python3-venv python3-dev build-essential curl git \
  libgl1 libglib2.0-0 libgomp1 libx11-6

echo "[install] Creating Python virtualenv + installing backend dependencies..."
cd "$REPO_ROOT/backend"
python3 -m venv venv
./venv/bin/python -m pip install --upgrade pip
# Install the CPU build of torch first (matches backend/Dockerfile) so the much
# larger CUDA wheels are never pulled in.
./venv/bin/pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
# Everything else, minus torch/torchvision which are already installed above.
grep -vE '^\s*#|^(torch|torchvision)([=<>]|$)' requirements.txt > /tmp/reimagine_reqs.txt
./venv/bin/pip install -r /tmp/reimagine_reqs.txt

echo "[install] Writing backend/.env if missing (real API keys come from secrets/env)..."
# NOTE: never bake real secret values into this file — it can end up in a build
# snapshot. Real OPENAI_API_KEY / GEMINI_API_KEY / FAL_API_KEY are injected as
# environment variables at runtime (pydantic-settings reads env vars first, so
# an injected secret overrides the placeholder below). The placeholder simply
# lets the server boot for non-AI development (auth, DB, docs) before any key
# is added.
if [ ! -f .env ]; then
  cat > .env <<'EOF'
OPENAI_API_KEY=sk-placeholder-not-a-real-key
GEMINI_API_KEY=
FAL_API_KEY=

DEBUG=true
APP_NAME=ReimagineAI
APP_VERSION=0.1.0
SECRET_KEY=dev-only-insecure-key-change-in-production

GPT_MODEL=gpt-4.1
SCENE_ANALYSIS_PROVIDER=openai
OPENAI_VISION_MODEL=gpt-5-mini
GEMINI_ANALYSIS_MODEL=gemini-flash-latest
GEMINI_MODEL=gemini-3-pro-image-preview
IMAGE_TO_3D_MODEL=fal-ai/trellis-2

DATABASE_URL=postgresql+psycopg://reimagine:reimagine@127.0.0.1:5432/reimagine_ai
POSTGRES_PASSWORD=reimagine
EOF
fi

echo "[install] Done."
