#!/usr/bin/env bash
set -euo pipefail

FLUTTER_DIR="${FLUTTER_DIR:-/opt/render/project/flutter}"

if [ ! -d "$FLUTTER_DIR" ]; then
  git clone https://github.com/flutter/flutter.git --depth 1 -b stable "$FLUTTER_DIR"
fi

export PATH="$FLUTTER_DIR/bin:$PATH"

flutter config --enable-web
flutter pub get
flutter build web --release \
  --dart-define=API_BASE_URL="${API_BASE_URL:?API_BASE_URL must be set to your HTTPS backend URL}" \
  --dart-define=CAMERA_REDIRECT_URL="${CAMERA_REDIRECT_URL:-}"
