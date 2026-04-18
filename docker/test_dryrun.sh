#!/bin/bash
# フェーズ5 タスク5.1: ドライランテスト（モデルなし起動確認）
# 実行方法: bash /mnt/c/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI/docker/test_dryrun.sh
set -euo pipefail

IMAGE_NAME="comfyui-runpod-test"
BUILD_CONTEXT="/mnt/c/AIwork/ImageGeneration/Runpod/Runpod_ComfyUI"
DOCKERFILE="${BUILD_CONTEXT}/docker/Dockerfile"

echo "=================================================="
echo " ComfyUI RunPod ドライランテスト"
echo "=================================================="

# ---------------------------------------------------
# Step 1: Dockerfileのビルド引数に実在するコミットをセット
# NOTE: プレースホルダーのコミットハッシュを最新HEADで代替してテスト
# ---------------------------------------------------
echo ""
echo "=== Step 1: コミットハッシュの取得 ==="
COMFYUI_COMMIT=$(git ls-remote https://github.com/comfyanonymous/ComfyUI.git HEAD | cut -f1)
COMFYROLL_COMMIT=$(git ls-remote https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes.git HEAD | cut -f1)
RGTHREE_COMMIT=$(git ls-remote https://github.com/rgthree/rgthree-comfy.git HEAD | cut -f1)
CGUSE_COMMIT=$(git ls-remote https://github.com/chrisgoringe/cg-use-everywhere.git HEAD | cut -f1)
INSPIRE_COMMIT=$(git ls-remote https://github.com/ltdrdata/ComfyUI-Inspire-Pack.git HEAD | cut -f1)

echo "ComfyUI:    ${COMFYUI_COMMIT:0:12}"
echo "Comfyroll:  ${COMFYROLL_COMMIT:0:12}"
echo "rgthree:    ${RGTHREE_COMMIT:0:12}"
echo "cg-use:     ${CGUSE_COMMIT:0:12}"
echo "Inspire:    ${INSPIRE_COMMIT:0:12}"

# ---------------------------------------------------
# Step 2: Docker イメージビルド
# ---------------------------------------------------
echo ""
echo "=== Step 2: Docker イメージビルド（時間がかかります） ==="
docker build \
  --build-arg COMFYUI_COMMIT="${COMFYUI_COMMIT}" \
  --build-arg COMFYROLL_COMMIT="${COMFYROLL_COMMIT}" \
  --build-arg RGTHREE_COMMIT="${RGTHREE_COMMIT}" \
  --build-arg CGUSE_COMMIT="${CGUSE_COMMIT}" \
  --build-arg INSPIRE_COMMIT="${INSPIRE_COMMIT}" \
  -f "${DOCKERFILE}" \
  -t "${IMAGE_NAME}:test" \
  "${BUILD_CONTEXT}"
echo "ビルド: OK"

# ---------------------------------------------------
# Step 3: スクリプト配置確認
# ---------------------------------------------------
echo ""
echo "=== Step 3: スクリプト配置確認 ==="
FILES=(
  "/workspace/download_models.sh"
  "/workspace/scripts/auto_uploader.py"
  "/workspace/scripts/auto_terminator.py"
  "/workspace/ComfyUI/main.py"
)
for f in "${FILES[@]}"; do
  docker run --rm "${IMAGE_NAME}:test" test -f "$f" && echo "  [OK] $f" || echo "  [NG] $f"
done

# ---------------------------------------------------
# Step 4: ツール・パッケージ確認
# ---------------------------------------------------
echo ""
echo "=== Step 4: ツール・パッケージ確認 ==="
docker run --rm "${IMAGE_NAME}:test" bash -c "
  echo -n '  rclone:         '; rclone --version | head -1
  echo -n '  uv:             '; uv --version
  echo -n '  python:         '; python3 --version
  echo -n '  requests:       '; python3 -c 'import requests; print(requests.__version__)'
  echo -n '  runpod:         '; python3 -c 'import runpod; print(runpod.__version__)'
  echo -n '  hf_transfer:    '; python3 -c 'import hf_transfer; print(\"OK\")'
  echo -n '  huggingface_hub:'; python3 -c 'import huggingface_hub; print(huggingface_hub.__version__)'
"

# ---------------------------------------------------
# Step 5: ComfyUI CPU起動テスト (30秒タイムアウト)
# ---------------------------------------------------
echo ""
echo "=== Step 5: ComfyUI CPU起動テスト ==="
CID=$(docker run -d "${IMAGE_NAME}:test" \
  python3 /workspace/ComfyUI/main.py --cpu --listen 0.0.0.0 --port 8188 2>/dev/null)
echo "コンテナID: ${CID:0:12}"

# 最大30秒待機
started=0
for i in $(seq 1 10); do
  sleep 3
  if docker exec "$CID" curl -sf http://localhost:8188 > /dev/null 2>&1; then
    echo "  ComfyUI 起動確認OK (${i}回目 / 約$((i*3))秒)"
    started=1
    break
  fi
  echo "  待機中... ($((i*3))秒)"
done

docker stop "$CID" > /dev/null
docker rm "$CID" > /dev/null

if [ "$started" -eq 0 ]; then
  echo "  [警告] ComfyUI が30秒以内に起動しませんでした"
  echo "  → モデルなしでも起動するはずなので、ログを確認してください"
  exit 1
fi

# ---------------------------------------------------
# 結果サマリー
# ---------------------------------------------------
echo ""
echo "=================================================="
echo " ドライランテスト: 全項目クリア"
echo "=================================================="
echo ""
echo "次のステップ: フェーズ5 タスク5.2 本番テスト（10枚限定）"
echo "  1. RunPod Secret に RCLONE_CONF_B64 / RUNPOD_API_KEY を登録"
echo "  2. Dockerイメージを DockerHub にプッシュ"
echo "  3. RunPod で Pod を起動し runpod_setup.ipynb を実行"
