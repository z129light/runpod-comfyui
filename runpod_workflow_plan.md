# RunPod環境向けComfyUI高速生成ワークフロー計画書

## 変更履歴 (Revision History)
| バージョン | 日付 | 変更内容 |
| :--- | :--- | :--- |
| v1.0.0 | 2026-04-17 | 新規作成。RunPod高速1時間生成ワークフローの要件整理およびTODOリスト策定。 |
| v1.1.0 | 2026-04-17 | インフラ設計観点でブラッシュアップ。モデルURLの確定・Network Volume戦略追加・コスト試算・自動シャットダウン詳細化・見落とし7項目を新規タスクとして追加。 |
| v1.2.0 | 2026-04-17 | 方針変更：Network Volume（永続ストレージ）を使用しない設計に変更。毎回起動時にhf_transfer高速DLで環境を完全構築し、未使用時の課金を完全ゼロにする方針を確定。 |
| v1.3.0 | 2026-04-18 | フェーズ1（プロンプト生成GUIツール）、フェーズ2（Docker/モデルDLスクリプト）の実装完了を反映。作成ファイル一覧を追記。 |
| v1.4.0 | 2026-04-18 | フェーズ3（setup.ipynbの実装）を開始。並列ダウンロード・自動転送・自動停止を統合したAll-in-oneノートブックの設計を確定。 |
| v1.5.0 | 2026-04-18 | フェーズ4（自動停止スクリプト）の実装完了。タイムアウト・キュー監視の二段構えをauto_terminator.pyとして独立化。 |
| v1.6.0 | 2026-04-18 | フェーズ0設計レビューによる修正。スクリプトパス不一致修正（Dockerfile COPYパス更新・/workspace/scripts/へ統一）・LoRADLセル追加・rclone.conf Secret連携をbase64方式で実装・uv再インストール削除。 |
| v1.7.0 | 2026-04-18 | フェーズ1レビューによる修正。auto_uploader.py: rcloneエラー検知・画像フィルタ（png/jpg/webp）・--transfers引数化・upload_done.flag実装。auto_terminator.py: 固定sleep(60)廃止→flag待ち方式に変更し最終同期を保証。 |
| v1.8.0 | 2026-04-18 | フェーズ2レビュー・修正。Dockerfile: requestsを明示インストール・ComfyUI/カスタムノードをARGでバージョン固定・||true廃止・inotify-tools削除。download_models.sh: set -euo pipefail追加・PID追跡で並列DL失敗を個別検知。 |
| v1.9.0 | 2026-04-18 | フェーズ3レビュー・修正。run関数をCell 1に移動（Cell間依存バグ解消）・フォールバックDLのエラーチェック修正・rclone認証テスト追加・ComfyUI起動確認（HTTPポーリング最大3分）を追加。 |
| v1.10.0 | 2026-04-18 | ドキュメントの構成調整。フェーズ2とフェーズ3のレビューログの順序を修正。 |

---

## 概要 (Overview)

**目標**: RunPodのRTX 4090 / 5090インスタンスを使用し、セットアップ時間を最小化。60分間で事前に用意した大量のプロンプトを高速バッチ生成し、完了後即座にインスタンスを破棄して課金を最低限に抑えるワークフローを確立する。

**基本方針**:
- **永続ストレージ（Network Volume）は使用しない** — 未使用時の課金を完全ゼロにすることを最優先とする
- 毎回起動時に `hf_transfer` + `uv` で高速環境構築（目標: 15分以内）
- ComfyUIは **APIモード**（ヘッドレス）でバッチ処理を最大効率化
- 自動シャットダウンで **セッション超過課金ゼロ** を保証

---

## 1. ワークフロー分析 (`01_ZIT_baseflow_v2.json`)

### 使用アーキテクチャ
- **ベースモデル**: Lumina2 (Z-Image Turbo) — AuraFlowアーキテクチャ
- **サンプラー**: `dpmpp_2m` / `sgm_uniform` / **8 steps** / CFG=1（超高速Turboモデル）
- **デコード**: VAEDecodeTiledによる高品質タイルデコード
- **アップスケール**: `ImageScaleBy` で **3倍拡大**（出力は最終的に大サイズ）

> **推定スループット（RTX 4090）**: 1枚あたり約10〜20秒（3x upscale含む） → 60分で約180〜360枚

### 必要なカスタムノード（確定）
| ノード名 | 用途 | インストールコマンド |
| :--- | :--- | :--- |
| `ComfyUI-Comfyroll-CustomNodes` | `CR Aspect Ratio Social Media` | `git clone https://github.com/Suzie1/ComfyUI_Comfyroll_CustomNodes` |
| `rgthree-comfy` | `Power Lora Loader (rgthree)` | `git clone https://github.com/rgthree/rgthree-comfy` |
| `cg-use-everywhere` | `Anything Everywhere` | `git clone https://github.com/chrisgoringe/cg-use-everywhere` |
| `ComfyUI-Inspire-Pack` | `LoadPromptsFromFile`, `UnzipPrompt` | `git clone https://github.com/ltdrdata/ComfyUI-Inspire-Pack` |

### 必要なモデル一覧（HuggingFaceダウンロードURL確定済み）
| 種別 | ファイル名 | HuggingFace URL | 配置先 |
| :--- | :--- | :--- | :--- |
| UNET | `z_image_turbo_bf16.safetensors` | `https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors` | `models/diffusion_models/` |
| VAE | `ae.safetensors` | `https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors` | `models/vae/` |
| CLIP | `qwen_3_4b.safetensors` | `https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors` | `models/text_encoders/` |
| LoRA | `zbase_[jehyon]_v1.safetensors` | **Google Driveから直接ダウンロード** (自作モデルのため) | `models/loras/` |
| LoRA | `hairdetailer.safetensors` | **Google Driveから直接ダウンロード** (自作モデルのため) | `models/loras/` |

> **注意**: `qwen_3_4b.safetensors` はQwen CLIPモデル（約7GB）。ダウンロード時間が最大のボトルネック。`hf_transfer` での並列高速化必須。

---

## 2. インフラ設計方針

### 起動〜生成〜終了のタイムライン
```
[起動] Pod開始
  ├─ 0〜5分:   uv + hf_transfer インストール、ComfyUI依存関係
  ├─ 5〜15分:  モデル並列ダウンロード（hf_transfer、目標10分以内）
  ├─ 15〜20分: ComfyUI起動・ウォームアップ、Driveアップローダー起動
  ├─ 20〜80分: バッチ生成（目標60分フル稼働）
  └─ 80分:     全画像をGoogleDriveに同期 → Pod即時Terminate
```

> **ダウンロード時間短縮の鍵**: `hf_transfer`（Rustベース並列DL）+ モデルを全て並列で同時ダウンロード。5〜10分での完了を目指す。

### コスト試算（永続ストレージなし）
| GPU | オンデマンド | スポット | 推奨 |
| :--- | :--- | :--- | :--- |
| RTX 4090 | ~$0.74/hr | ~$0.44/hr | **オンデマンド推奨（中断リスク回避）** |
| RTX 5090 | ~$1.20/hr | ~$0.75/hr | 生成枚数重視なら有効 |

**1セッション予算目安**: 約80〜90分 × $0.74 = **約$1.0〜$1.1**（毎回同額）
**未使用時課金**: **$0**（完全ゼロ）

### ComfyUI起動オプション（最大パフォーマンス）
```bash
python main.py \
  --listen 0.0.0.0 \      # APIモード（ヘッドレスバッチ処理）
  --highvram \             # VRAMオフロードを無効化
  --bf16-vae \             # VAEをbf16で高速化
  --fast \                 # 実験的高速化（Turboモデルと相性良）
  --preview-method none \  # プレビュー無効（バッチ処理時の無駄排除）
  --output-directory /workspace/output
```

### プロンプトファイル形式（Inspire Pack仕様）
```
# 1枚ごとにポジティブ/ネガティブをセットで記述（TXT形式）
positive: a beautiful woman in a park
negative: nsfw, bad quality
```

---

## 3. やることリスト (TODO)

### フェーズ 0: 【最優先】前提確認・準備
* [x] **タスク 0.1: 自作LoRAのGoogle Drive配置とダウンロード設計**
  * `zbase_jehyon_v1.safetensors` 等の自作LoRAをGoogle Driveの特定フォルダに事前配置する。
  * `setup.ipynb` 実行時に `rclone` または `gdown` などのツールを用いてGoogle Driveからコンテナの `models/loras/` にダウンロードする仕組みを構築する。
* [x] **タスク 0.2: Google Drive OAuth2トークンを事前生成する**
  * `rclone config` でOAuth2認証を完了し、`rclone.conf` を生成しておく。RunPod上での認証はブラウザが不要な形（`--no-browser` + `authorization_code`方式）にする。
  * 生成した `rclone.conf` はRunPod Secret環境変数として登録しておき、setup時に自動配置する。

### フェーズ 1: ツール構築（ローカル作業）
* [x] **タスク 1.1: プロンプト量産ツールの作成**
  * `ComfyUI-Inspire-Pack` の `LoadPromptsFromFile` 仕様（`positive: / negative:` 形式のTXT）に準拠したプロンプト生成スクリプトを作成する。Claude API等を使って数百〜数千パターンを自動生成。
* [x] **タスク 1.2: Google Drive自動アップローダーの設定**
  * ComfyUI出力フォルダ (`/workspace/output`) を `rclone sync` でGoogle Driveへ転送するスクリプトを作成する。`inotifywait` またはポーリング間隔（30秒）でバックグラウンド常時実行。
  * 転送後ローカルファイルを削除してストレージ節約も検討。

### フェーズ 2: RunPod向けデプロイ設計
* [x] **タスク 2.1: Dockerイメージの選定・設計**
  * RunPod公式 `runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04` 等をベースとして選定。
  * ComfyUI本体 + カスタムノード4種 + `uv` + `hf_transfer` をイメージに焼き込み、DockerHubに登録する。
  * **モデルはイメージに含めない**（容量が大きすぎるため）。起動時に毎回HuggingFaceからDLする。
* [x] **タスク 2.2: モデル並列高速ダウンロードスクリプトの作成**
  * `hf_transfer` を使い、5ファイルを**並列同時ダウンロード**するbashスクリプトを作成する。直列DLより大幅に時間短縮できる。
  ```bash
  uv pip install hf_transfer huggingface_hub
  export HF_HUB_ENABLE_HF_TRANSFER=1
  # 5ファイルをバックグラウンドジョブで並列DL
  huggingface-cli download Comfy-Org/z_image_turbo \
    split_files/diffusion_models/z_image_turbo_bf16.safetensors \
    --local-dir /comfyui/models/diffusion_models &
  huggingface-cli download Comfy-Org/z_image_turbo \
    split_files/vae/ae.safetensors \
    --local-dir /comfyui/models/vae &
  huggingface-cli download Comfy-Org/z_image_turbo \
    split_files/text_encoders/qwen_3_4b.safetensors \
    --local-dir /comfyui/models/text_encoders &
  wait  # 全ジョブ完了を待機
  ```

### フェーズ 3: Jupyter Notebook（`setup.ipynb`）の作成
* [x] **タスク 3.1: オールインワン `runpod_setup.ipynb` の実装**
  * RunPod上でのJupyterLabから「Run All」で以下が完了するように実装:
    1. 環境変数の設定（HF_TOKEN, RunPod APIキー, Google Drive設定等）
    2. Python依存関係・`hf_transfer`のインストール
    3. モデルの並列高速ダウンロード（毎回実行、目標10分以内）
    4. カスタムノードはDockerイメージ焼き込み済みのため不要
    5. `rclone.conf` の配置とGoogleドライブアップローダーのバックグラウンド起動
    6. ComfyUIを最適化オプション付きでバックグラウンド起動
    7. 自動シャットダウンスクリプトの起動

### フェーズ 4: 自動シャットダウン（Self-Destruct）の実装
* [x] **タスク 4.1: 二段構えの自動停止スクリプト**
  * 以下の**どちらか早い方**でインスタンスをTerminateする:
    1. **タイムアウト**: 起動から60分経過（ハードリミット）
    2. **キュー枯渇**: ComfyUI APIの `/queue` エンドポイントをポーリングし、`queue_remaining=0` かつ `queue_running=0` が2分間継続
  ```python
  # RunPod APIでTerminate
  import runpod
  runpod.terminate_pod(os.environ["RUNPOD_POD_ID"])
  ```
  * `runpod` SDK (`pip install runpod`) で実装。APIキーは環境変数から取得。
  * **Google Driveへの最終同期が完了してからTerminate**することを必ず担保する。

### フェーズ 5: 結合テスト
* [x] **タスク 5.1: ドライランテスト（課金前）**
  * 実際にRunPodを起動する前に、`setup.ipynb` の各セルをローカルのDockerコンテナで動作検証する（モデル無しで起動確認のみ）。
  * 2026-04-18 完了。全5項目クリア（スクリプト配置・パッケージ・ComfyUI CPU起動9秒確認）。
* [ ] **タスク 5.2: 本番テスト（10枚限定）**
  * 本番RunPodインスタンスで10枚のみ生成し、Google Driveへの転送・自動停止までのフルフローを確認する。成功後に大量バッチを実行する。

---

## 4. 推奨追加TODOと検討事項

### セキュリティ
- [x] HuggingFace Token, RunPod APIキー, Google Drive認証情報を **RunPod Secret** または `.env` ファイルで管理し、Notebookにハードコードしない *(v1.6.0で対応済み: RCLONE_CONF_B64/HF_TOKEN/RUNPOD_API_KEY をRunPod Secret経由で注入)*

### 効率化
- [ ] **バッチサイズ最適化**: `batch_size=1` か `batch_size=2〜4` どちらが4090のVRAM効率が良いかをテストで確認（Turboモデルは8stepで高速なためバッチ化の恩恵大）
- [ ] **生成ログの記録**: 何枚生成できたか、1枚あたりの時間、エラー率をCSVに記録して次回セッション改善に活かす

### 将来対応
- [ ] プロンプトファイルをRunPod実行前にGoogle Driveから自動取得するフローを追加（プロンプト量産ツールとの連携）
- [ ] モデルが更新された場合はDockerイメージ内のDLスクリプトのURLを更新するだけで対応できる設計を維持する

---

## 5. 現在の進捗と作成済みファイル一覧

**フェーズ1からフェーズ4までの主要タスクが完了し、環境構築および自動化スクリプトが全て揃いました。次回は「フェーズ5：結合テスト」を実施します。**

### 作成済みファイル

> すべてのファイルは `C:\AIwork\ImageGeneration\Runpod\Runpod_ComfyUI\` 以下に統合済み（2026-04-18 整理）

* **フェーズ1: ツール構築**
  * `scripts\VLM_Mass_Prompt_Generator.py` (通常版)
  * `scripts\launch_mass_prompt_generator.bat` (通常版起動バッチ)
  * `scripts\VLM_Mass_Prompt_Generator_Rich.py` (リッチUI版)
  * `scripts\launch_mass_prompt_generator_rich.bat` (リッチUI起動バッチ)
  * `scripts\auto_uploader.py` (Google Drive自動転送スクリプト)
  * `scripts\generate_prompts.py` (プロンプト生成スクリプト)
  * `prompts\runpod_prompts.txt` (生成済みプロンプト)
* **フェーズ2: RunPodデプロイ設計**
  * `docker\Dockerfile` (ComfyUI環境構築用イメージ)
  * `docker\download_models.sh` (並列モデル高速DLスクリプト)
  * `docker\install_docker_wsl.sh` (WSL向けDockerインストールスクリプト)
  * `docker\test_dryrun.sh` (ドライランテストスクリプト)
* **フェーズ3: Jupyter Notebookの作成**
  * `runpod_setup.ipynb` (All-in-one環境構築・実行用ノートブック)
  * `launch_local_test.bat` (Windows向けローカルDockerテスト起動スクリプト)
  * `launch_local_test_wsl.sh` (WSL向けローカルDockerテスト起動スクリプト)
* **フェーズ4: 自動シャットダウンの実装**
  * `scripts\auto_terminator.py` (キュー監視・自動破棄スクリプト)

---

## 6. レビューログ

### フェーズ0 レビュー（2026-04-18 / v1.6.0）

| 重要度 | 問題 | 対応 |
|---|---|---|
| 🔴 Critical | スクリプトパス不一致（`/docker/`・`/scripts/`が存在しない） | Dockerfile COPY修正・パスを`/workspace/scripts/`に統一 |
| 🔴 Critical | LoRAのDLコードがsetup.ipynbに未実装 | Cell 3にrclone copyブロックを追加 |
| 🟠 High | rclone.conf Secret連携が未完成（`token = {}`のハードコード） | `RCLONE_CONF_B64`環境変数からbase64デコードする方式に変更 |
| 🟡 Medium | Cell 2でuvを再インストール（Dockerイメージ焼き込み済み） | 再インストールブロックを削除 |
| 🟡 Medium | タスク0.2→0.1の依存順序が未明示 | 計画書に順序依存を明記 |

### フェーズ1 レビュー（2026-04-18 / v1.7.0）

対象ファイル: `auto_uploader.py`, `auto_terminator.py`

| 重要度 | 問題 | 対応 |
|---|---|---|
| 🔴 Critical | rclone失敗がサイレント（returncode未確認） | エラー時ログ出力・ループ継続に修正 |
| 🟠 High | Terminate前の最終同期が固定sleep(60)で不確実 | `upload_done.flag`ファイルベースの連携に変更（最大5分待機） |
| 🟠 High | `result.stderr`のみ確認（stdout未参照） | `stdout + stderr`を結合して確認 |
| 🟡 Medium | 画像以外のファイルも転送対象（jsonなど） | `--include *.png/jpg/jpeg/webp`フィルタを追加 |
| 🟡 Medium | `--transfers 4`がハードコード | argparseで上書き可能な引数に変更 |

### フェーズ2 レビュー（2026-04-18 / v1.8.0）

対象ファイル: `Dockerfile`, `download_models.sh`

| 重要度 | 問題 | 状態 |
|---|---|---|
| 🔴 Critical | `requests`パッケージ未インストール（auto_terminatorが起動時クラッシュ） | ✅ `uv pip install --system ... requests` を追加 |
| 🟠 High | ComfyUI・カスタムノードのバージョン未固定（HEADのままclone） | ✅ `ARG *_COMMIT` でビルド引数化・`git checkout`でpin |
| 🟠 High | `\|\| true`でcustom node依存関係インストール失敗を握りつぶし | ✅ `\|\| true`を削除、ビルド時に失敗を検知する構成に変更 |
| 🟡 Medium | `download_models.sh`に`set -e`なし（DL失敗を検知できない） | ✅ `set -euo pipefail` + PID追跡で各ジョブの終了コードを確認 |
| 🟡 Medium | `inotify-tools`がインストールされているが使用していない | ✅ apt installから削除 |

### フェーズ3 レビュー（2026-04-18 / v1.9.0）

対象ファイル: `runpod_setup.ipynb`

| 重要度 | 問題 | 対応 |
|---|---|---|
| 🔴 Critical | `run` 関数がCell 2に定義されCell 3で参照（Cell間依存バグ） | Cell 1に移動し全セルから安全に呼び出せるよう修正 |
| 🟠 High | ComfyUI起動確認なし（起動失敗のままterminatorが動作し80分浪費） | `http://localhost:8188` をHTTPポーリング（最大3分）で確認 |
| 🟠 High | フォールバックDLで `p.wait()` 二重呼び出し・エラー検知ロジック不正 | `results = [(c, p.wait()) ...] / errors = [...if rc != 0]` に修正 |
| 🟡 Medium | rclone認証テストなし（トークン失効をLoRA DL失敗で初めて気づく） | `rclone lsd gdrive:` で接続確認 → 失敗時に明確なエラーメッセージを表示 |

---

*作成: Gemini初版（v1.0.0） | インフラ設計レビュー・ブラッシュアップ: Claude Sonnet 4.6（v1.1.0）*
