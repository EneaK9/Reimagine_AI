#!/bin/bash
# Start the ReimagineAI backend.
# --reload-dir app: watch ONLY our code — never venv/ (installing packages
# or .pyc writes there would otherwise restart the server in a loop).
cd "$(dirname "$0")"
# Silence the harmless "unauthenticated requests to the HF Hub" notice
# (models are cached locally after first download).
export HF_HUB_VERBOSITY=error
exec venv/bin/python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8100 \
  --reload \
  --reload-dir app
