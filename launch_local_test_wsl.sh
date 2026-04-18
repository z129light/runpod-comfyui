#!/bin/bash
set -e

echo "=============================================================="
echo " RunPod ドライランテスト環境 (Local Docker via WSL) 起動スクリプト"
echo "=============================================================="
echo ""
echo "1. Dockerイメージをビルドします..."
cd /mnt/c/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI
sudo docker build -f docker/Dockerfile -t runpod-comfyui-test .

echo ""
echo "2. コンテナを起動します..."
echo "起動後、ブラウザで以下のURLを開いてください。"
echo "  JupyterLab : http://localhost:8888"
echo "  ComfyUI    : http://localhost:8188"
echo ""
echo "終了する場合は、このコンソールで Ctrl+C を押してください。"
echo "--------------------------------------------------------------"

sudo docker run --gpus all --rm -it \
  -p 8888:8888 -p 8188:8188 \
  -v "$(pwd):/workspace/runpod" \
  runpod-comfyui-test
