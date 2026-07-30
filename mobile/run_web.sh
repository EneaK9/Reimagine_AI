#!/bin/bash
# Web dev without the flaky Chrome debugger connection.
#
# The default `flutter run -d chrome` attaches a debugger (DWDS) to the tab;
# our app's iframes (3D viewer/editor) confuse it, producing endless
# "WipError -32000 Cannot find context" noise and broken hot reload.
# `-d web-server` serves the app with NO debugger attachment, so that whole
# error class disappears.
#
# Workflow:
#   1. ./run_web.sh
#   2. open http://127.0.0.1:5555 in your browser
#   3. after code changes: press R in this terminal, then refresh the browser
cd "$(dirname "$0")"
exec flutter run -d web-server --web-hostname 127.0.0.1 --web-port 5555 "$@"
