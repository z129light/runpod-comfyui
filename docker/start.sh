#!/bin/bash
set -e

echo "[start.sh] /workspace にスクリプトをコピー中..."
mkdir -p /workspace/scripts
mkdir -p /workspace/logs
cp /opt/scripts/auto_uploader.py /workspace/scripts/auto_uploader.py
cp /opt/scripts/auto_terminator.py /workspace/scripts/auto_terminator.py
cp /opt/scripts/download_models.sh /workspace/download_models.sh
chmod +x /workspace/download_models.sh

echo "[start.sh] JupyterLab を起動中 (port 8888)..."
jupyter lab \
  --ip=0.0.0.0 \
  --port=8888 \
  --no-browser \
  --allow-root \
  --ServerApp.token='' \
  --ServerApp.password='' \
  --ServerApp.allow_origin='*' \
  --ServerApp.root_dir=/workspace &

echo "[start.sh] 起動完了。コンテナを維持します。"
exec tail -f /dev/null
