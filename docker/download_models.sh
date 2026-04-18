#!/bin/bash
set -euo pipefail

# hf_transfer は設定されていると自動的にRust製の高速ダウンローダーを使用します。
export HF_HUB_ENABLE_HF_TRANSFER=1

MODEL_NAME="${1:-turbo}"

COMFY_MODELS_DIR="/workspace/ComfyUI/models"

mkdir -p "${COMFY_MODELS_DIR}/diffusion_models"
mkdir -p "${COMFY_MODELS_DIR}/vae"
mkdir -p "${COMFY_MODELS_DIR}/text_encoders"
mkdir -p "${COMFY_MODELS_DIR}/loras"

# UNETはモデル選択に基づく
if [ "$MODEL_NAME" = "zimage" ]; then
    UNET_REPO="Comfy-Org/z_image"
    UNET_FILE="split_files/diffusion_models/z_image_bf16.safetensors"
else  # turbo (default)
    UNET_REPO="Comfy-Org/z_image_turbo"
    UNET_FILE="split_files/diffusion_models/z_image_turbo_bf16.safetensors"
fi

echo "[Start] Downloading models (model=${MODEL_NAME}) in parallel..."
start_time=$(date +%s)

# 各ジョブのPIDを記録して終了コードを個別に確認する
pids=()

hf download "${UNET_REPO}" \
  "${UNET_FILE}" \
  --local-dir "${COMFY_MODELS_DIR}/diffusion_models" &
pids+=($!)

# VAEはturboリポジトリから（両モデル共通）
hf download Comfy-Org/z_image_turbo \
  split_files/vae/ae.safetensors \
  --local-dir "${COMFY_MODELS_DIR}/vae" &
pids+=($!)

# CLIP (Qwen 3.4B): 約7GB。最大のボトルネック。両モデル共通。
hf download Comfy-Org/z_image_turbo \
  split_files/text_encoders/qwen_3_4b.safetensors \
  --local-dir "${COMFY_MODELS_DIR}/text_encoders" &
pids+=($!)

# 全ジョブの終了を待ち、失敗があれば報告して終了
failed=0
for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
        echo "[ERROR] Download job (PID $pid) failed." >&2
        failed=1
    fi
done

if [ "$failed" -ne 0 ]; then
    echo "[FATAL] One or more model downloads failed. Aborting." >&2
    exit 1
fi

end_time=$(date +%s)
elapsed=$(( end_time - start_time ))
echo "[Done] All models downloaded successfully in ${elapsed} seconds."
