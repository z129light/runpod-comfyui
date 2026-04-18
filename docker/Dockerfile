FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

# ---------------------------------------------------------
# Version Pins (未設定 = 各リポジトリの最新HEADを使用)
# ---------------------------------------------------------

# ---------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV HF_HUB_ENABLE_HF_TRANSFER=1
ENV COMFY_PATH="/workspace/ComfyUI"
ENV TZ=Asia/Tokyo

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
RUN git clone https://github.com/comfyanonymous/ComfyUI.git ${COMFY_PATH}

WORKDIR ${COMFY_PATH}

RUN uv pip install --system -r requirements.txt

# requests は auto_terminator.py が使用するため明示インストール
RUN uv pip install --system hf_transfer huggingface_hub runpod requests jupyterlab

# ---------------------------------------------------------
# Custom Nodes (バージョン固定でclone)
# || true を廃止: dep install 失敗はビルド時に検知する
# ---------------------------------------------------------
WORKDIR ${COMFY_PATH}/custom_nodes

RUN git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes

RUN git clone https://github.com/rgthree/rgthree-comfy && \
    cd rgthree-comfy && uv pip install --system -r requirements.txt && cd ..

RUN git clone https://github.com/chrisgoringe/cg-use-everywhere

RUN git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack && \
    cd ComfyUI-Inspire-Pack && uv pip install --system -r requirements.txt && cd ..

# ---------------------------------------------------------
# Copy Scripts
# NOTE: ビルドコンテキストは Runpod/Runpod_ComfyUI/ ディレクトリを指定すること
#   cd C:\AIwork\ImageGeneration\Runpod\Runpod_ComfyUI && docker build -f docker/Dockerfile -t <tag> .
# ---------------------------------------------------------
COPY docker/download_models.sh /opt/scripts/download_models.sh
RUN chmod +x /opt/scripts/download_models.sh

RUN mkdir -p /opt/scripts
COPY scripts/auto_uploader.py /opt/scripts/auto_uploader.py
COPY scripts/auto_terminator.py /opt/scripts/auto_terminator.py

WORKDIR /workspace

COPY docker/start.sh /start.sh
RUN chmod +x /start.sh

# RunPod HTTP Service として登録するポート
EXPOSE 8188 8888

CMD ["/start.sh"]
