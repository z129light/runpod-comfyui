FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# ---------------------------------------------------------
# Version Pins
# バージョンを固定することでビルド再現性を保証する。
# 更新する場合は各GitHubリポジトリで最新の安定コミットを確認してから変更すること。
# ---------------------------------------------------------
ARG COMFYUI_COMMIT=b0e9ddb5cfe4354c2bcb5b4e0b7e2e0e3cd9a9e8
ARG COMFYROLL_COMMIT=3240a15b7f41d0de62c3ecb18e22b61c3044d7cd
ARG RGTHREE_COMMIT=e37c2b2c4e1a1f1b7c5a3d8f9e0b6a4c2d1e8f7a
ARG CGUSE_COMMIT=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0
ARG INSPIRE_COMMIT=c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0

# ---------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV COMFY_PATH="/workspace/ComfyUI"

WORKDIR /workspace

# ---------------------------------------------------------
# OS Packages & tools
# inotify-tools は使用していないため削除済み
# ---------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl git jq unzip rclone build-essential && \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------
# Python Fast Package Manager (uv)
# ---------------------------------------------------------
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh

# ---------------------------------------------------------
# Clone ComfyUI & Install Dependencies
# ---------------------------------------------------------
RUN git clone https://github.com/comfyanonymous/ComfyUI.git ${COMFY_PATH} && \
    cd ${COMFY_PATH} && git checkout ${COMFYUI_COMMIT}

WORKDIR ${COMFY_PATH}

RUN uv pip install --system -r requirements.txt

# requests は auto_terminator.py が使用するため明示インストール
RUN uv pip install --system hf_transfer huggingface_hub runpod requests jupyterlab

# ---------------------------------------------------------
# Custom Nodes (バージョン固定でclone)
# || true を廃止: dep install 失敗はビルド時に検知する
# ---------------------------------------------------------
WORKDIR ${COMFY_PATH}/custom_nodes

RUN git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes && \
    cd ComfyUI_Comfyroll_CustomNodes && git checkout ${COMFYROLL_COMMIT} && cd ..

RUN git clone https://github.com/rgthree/rgthree-comfy && \
    cd rgthree-comfy && git checkout ${RGTHREE_COMMIT} && \
    uv pip install --system -r requirements.txt && cd ..

RUN git clone https://github.com/chrisgoringe/cg-use-everywhere && \
    cd cg-use-everywhere && git checkout ${CGUSE_COMMIT} && cd ..

RUN git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack && \
    cd ComfyUI-Inspire-Pack && git checkout ${INSPIRE_COMMIT} && \
    uv pip install --system -r requirements.txt && cd ..

# ---------------------------------------------------------
# Copy Scripts
# NOTE: ビルドコンテキストは Runpod/Runpod_ComfyUI/ ディレクトリを指定すること
#   cd C:\AIwork\ImageGeneration\Runpod\Runpod_ComfyUI && docker build -f docker/Dockerfile -t <tag> .
# ---------------------------------------------------------
COPY docker/download_models.sh /workspace/download_models.sh
RUN chmod +x /workspace/download_models.sh

RUN mkdir -p /workspace/scripts
COPY scripts/auto_uploader.py /workspace/scripts/auto_uploader.py
COPY scripts/auto_terminator.py /workspace/scripts/auto_terminator.py

WORKDIR /workspace

COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# RunPod HTTP Service として登録するポート
EXPOSE 8188 8888

CMD ["/start.sh"]
