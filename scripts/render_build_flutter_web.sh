#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${API_BASE_URL:-}" ]]; then
  echo "API_BASE_URL must be set to your deployed backend URL, for example https://your-api.onrender.com"
  exit 1
fi

FLUTTER_DIR="${RENDER_PROJECT_DIR:-/tmp}/flutter"

if [[ ! -x "$FLUTTER_DIR/bin/flutter" ]]; then
  git clone https://github.com/flutter/flutter.git --branch stable --depth 1 "$FLUTTER_DIR"
fi

export PATH="$FLUTTER_DIR/bin:$PATH"

flutter config --enable-web
flutter --version

cd mobile
flutter pub get
flutter build web --release --dart-define=API_BASE_URL="$API_BASE_URL"
