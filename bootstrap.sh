#!/usr/bin/env bash
# Stellt sicher, dass matplotlib da ist (Cloud-Container oder lokaler PC). Idempotent, leise.
set -u
PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
if "$PY" -c "import matplotlib" 2>/dev/null; then
  echo "OK      matplotlib vorhanden ($("$PY" -c 'import matplotlib;print(matplotlib.__version__)'))"
else
  echo "INSTALL matplotlib ..."
  "$PY" -m pip install -q -r "$(dirname "$0")/requirements.txt" 2>/dev/null \
    || "$PY" -m pip install -q --break-system-packages -r "$(dirname "$0")/requirements.txt" \
    || { echo "FEHLER  pip install fehlgeschlagen"; exit 1; }
  echo "OK      matplotlib installiert"
fi
mkdir -p "$(dirname "$0")/out" "$(dirname "$0")/data/history" "$(dirname "$0")/charts" "$(dirname "$0")/archive"
"$PY" --version
git -C "$(dirname "$0")" rev-parse --abbrev-ref HEAD 2>/dev/null | sed 's/^/BRANCH  /'
