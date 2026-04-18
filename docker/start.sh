#!/bin/bash
set -e

echo "[start.sh] JupyterLab を起動中 (port 8888)..."
jupyter lab \
  --ip=0.0.0.0 \
  --port=8888 \
  --no-browser \
  --allow-root \
  --NotebookApp.token='' \
  --NotebookApp.password='' \
  --notebook-dir=/workspace &

echo "[start.sh] 起動完了。コンテナを維持します。"
exec tail -f /dev/null
