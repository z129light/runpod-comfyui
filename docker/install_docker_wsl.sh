#!/bin/bash
# Docker Engine インストールスクリプト (Ubuntu 24.04 / WSL2)
# 実行方法: bash /mnt/c/AIwork/ImageGeneration/docker/install_docker_wsl.sh
set -euo pipefail

echo "=== Step 1: Docker GPG キーの取得 ==="
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor > /tmp/docker-keyring.gpg
sudo cp /tmp/docker-keyring.gpg /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "GPG キー: OK"

echo "=== Step 2: Docker リポジトリの追加 ==="
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
echo "リポジトリ: OK"

echo "=== Step 3: Docker Engine のインストール ==="
sudo apt-get update -qq
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo "インストール: OK"

echo "=== Step 4: ユーザーを docker グループに追加 ==="
sudo usermod -aG docker "$USER"
echo "グループ追加: OK (次のWSL再起動後に有効)"

echo "=== Step 5: Docker サービス起動 ==="
sudo systemctl enable docker
sudo systemctl start docker
echo "サービス起動: OK"

echo ""
echo "=== インストール完了 ==="
docker --version
docker compose version
echo ""
echo "次のステップ:"
echo "  1. WSLを再起動する (Windows側で: wsl --shutdown && wsl)"
echo "  2. docker ps で動作確認"
echo "  3. bash /mnt/c/AIwork/ImageGeneration/docker/test_dryrun.sh でドライランテスト"
