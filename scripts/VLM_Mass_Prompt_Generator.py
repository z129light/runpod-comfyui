import base64
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import requests
import glob

_NO_WIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ==============================================================================
# Configuration
# ==============================================================================
SYSTEM_PROMPT_TURBO = """\
あなたは写真のテクニカル・ディレクターです。
画像を以下の8つのカテゴリで詳細に記述してください。

1. COMPOSITION: ショットタイプ（full-body / wide / environmental portrait 等を優先）、
   フレーム内での被写体の占有率（%）、被写体の配置（三分割法等）、
   カメラアングル、被写体とカメラの推定距離（メートル単位）。
   ★足元が接地している地面の質感や、被写体の頭上・左右にある「余白（Negative Space）」の状況を必ず含めてください。
2. SUBJECT: 被写体の正確な記述（年齢、民族推定、体型、服装の詳細、表情の微細なニュアンス）
3. MATERIAL: 各表面の材質（肌の質感、衣服の繊維、地面の素材、背景の建物の質感を詳細に）
4. LIGHTING: 光源の数・方向・色温度・硬さ、環境全体を包む光（Ambient Light）の状況
5. PHYSICS: 反射、屈折、影の落ち方（特に被写体が地面に落とす影の長さと形状、地面への接地感）
6. LENS: 推定焦点距離 (mm)、被写界深度、広角レンズ特有の周辺パースの歪みや写り込み
7. IMPERFECTION: 自然な不完全さ（衣服のシワ、地面の汚れ、背景のダスト、レンズフレア等）
8. ATMOSPHERE: 奥行き感、遠景の空気遠近法、被写体と背景の間の空間密度・湿度感

出力は英語のプロンプトのみで、各カテゴリのヘッダを付けて記述してください。
数値で表現できるものは数値（x meters, 35mm, 20% area 等）を使ってください。

★ 最重要ルール:
プロンプトの冒頭には必ず「ショットタイプ」と「空間の広がり（Wide perspective / Environmental context 等）」を配置してください。
"""

SYSTEM_PROMPT_BASE = """\
あなたは写真のテクニカル・ディレクターです。画像を詳細に解析し、プロンプトを生成してください。

以下の形式に従って、必ず「POSITIVE:」と「NEGATIVE:」のセクションを分けて英語で出力してください。

POSITIVE:
(ここに画像に写っている被写体、構図、照明、背景、カメラ設定などの詳細な説明を記載してください)

NEGATIVE:
(ここにこの画像を生成する上で避けるべき要素や、画質低下を防ぐためのネガティブプロンプトを記載してください。例: bad quality, deformed, blurry ...等)
"""

USER_PROMPT = "Analyze this image and generate the prompt."

# ==============================================================================
# Model — VLM Client
# ==============================================================================
class VLMClient:
    def __init__(self) -> None:
        self.url = "http://localhost:1234/v1/chat/completions"
        self.model = ""

    def list_models(self) -> list:
        base = self._base_url()
        try:
            res = requests.get(f"{base}/api/v1/models", timeout=5)
            res.raise_for_status()
            return [m["id"] if "id" in m else m["key"] for m in res.json().get("data", res.json().get("models", []))]
        except Exception:
            return []

    def load_model(self, model_id: str, context_length: int = 8192) -> float:
        base = self._base_url()
        t0 = time.monotonic()
        requests.post(f"{base}/api/v1/models/load",
                        json={"model": model_id, "context_length": context_length},
                        timeout=300).raise_for_status()
        self.model = model_id
        return time.monotonic() - t0

    def generate_prompt(self, image_path: str, system_prompt: str, user_prompt: str) -> str:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    ],
                },
            ],
            "stream": False,
        }
        res = requests.post(self.url, json=payload, timeout=180)
        res.raise_for_status()
        msg = res.json()["choices"][0]["message"]
        return msg.get("content") or msg.get("reasoning_content") or ""

    def unload_all(self) -> str:
        try:
            res = subprocess.run(["lms", "unload", "--all"], shell=True, capture_output=True, timeout=15, creationflags=_NO_WIN)
            return "success" if res.returncode == 0 else "error"
        except Exception:
            return "error"

    def _base_url(self) -> str:
        if "/v1/" in self.url:
            return self.url.rsplit("/v1/", 1)[0]
        parts = self.url.split("/")
        return "/".join(parts[:3])

# ==============================================================================
# App GUI
# ==============================================================================
class MassPromptGeneratorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Mass Prompt Generator (LM Studio)")
        self.minsize(800, 850)
        self.client = VLMClient()
        self.is_running = False
        self.cancel_requested = False
        
        self.image_files = []
        
        self._setup_ui()

    def _setup_ui(self) -> None:
        PAD = {"padx": 8, "pady": 4}

        # ── フォルダと出力先 ──────────────────────────────────
        file_frame = ttk.LabelFrame(self, text=" 入出力設定 ", padding=6)
        file_frame.pack(fill=tk.X, **PAD)

        # Image Folder
        row_in = ttk.Frame(file_frame)
        row_in.pack(fill=tk.X, pady=2)
        ttk.Label(row_in, text="入力フォルダ (画像):", width=18).pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(value=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "input_images")))
        ttk.Entry(row_in, textvariable=self.folder_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row_in, text="一覧取得", command=self._browse_folder).pack(side=tk.LEFT)

        # Output Target
        row_out = ttk.Frame(file_frame)
        row_out.pack(fill=tk.X, pady=2)
        ttk.Label(row_out, text="出力テキストファイル:", width=18).pack(side=tk.LEFT)
        default_out = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "generated_prompts.txt"))
        self.out_var = tk.StringVar(value=default_out)
        ttk.Entry(row_out, textvariable=self.out_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row_out, text="Save As...", command=self._browse_output).pack(side=tk.LEFT)

        # ── サーバー起動/終了 (LM Studio専用) ───────────────────────────
        backend_frame = ttk.LabelFrame(self, text=" LM Studio Server ", padding=6)
        backend_frame.pack(fill=tk.X, **PAD)

        ttk.Label(backend_frame, text="Local Server:").pack(side=tk.LEFT, padx=(0, 10))
        self.start_backend_btn = ttk.Button(backend_frame, text="✅ 起動 (Start)", width=16, command=self._start_backend)
        self.start_backend_btn.pack(side=tk.LEFT, padx=(0, 4))
        self.stop_backend_btn = ttk.Button(backend_frame, text="🛑 終了 (Stop)", width=16, command=self._stop_backend)
        self.stop_backend_btn.pack(side=tk.LEFT)


        # ── モデル選択 + ロード ────────────────────────────────────
        model_frame = ttk.LabelFrame(self, text=" Model ", padding=6)
        model_frame.pack(fill=tk.X, **PAD)

        # 1行目: モデル選択
        row1 = ttk.Frame(model_frame)
        row1.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(row1, text="Model:").pack(side=tk.LEFT)
        self.model_combo = ttk.Combobox(row1, state="readonly", width=42)
        self.model_combo.pack(side=tk.LEFT, padx=(4, 6))
        ttk.Button(row1, text="リスト更新", width=10, command=self._refresh_models).pack(side=tk.LEFT, padx=(0, 8))
        self.load_btn = ttk.Button(row1, text="モデルをロード", width=14, command=self._load_model)
        self.load_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.unload_btn = ttk.Button(row1, text="アンロード", width=12, command=self._unload_model)
        self.unload_btn.pack(side=tk.LEFT, padx=(0, 6))
        self._load_time_var = tk.StringVar(value="")
        ttk.Label(row1, textvariable=self._load_time_var, foreground="steelblue").pack(side=tk.LEFT)

        # 2行目: コンテキスト長
        row2 = ttk.Frame(model_frame)
        row2.pack(fill=tk.X)
        ttk.Label(row2, text="Context Length:").pack(side=tk.LEFT)
        self.ctx_combo = ttk.Combobox(row2, values=["2048", "4096", "6144", "8192", "10240", "12288", "16000"], state="readonly", width=10)
        self.ctx_combo.set("8192")
        self.ctx_combo.pack(side=tk.LEFT, padx=(4, 0))

        # ── モード切替 ──────────────────────────────────
        mode_frame = ttk.LabelFrame(self, text=" プロンプトモード ", padding=6)
        mode_frame.pack(fill=tk.X, **PAD)
        
        self.mode_var = tk.StringVar(value="turbo")
        r1 = ttk.Radiobutton(mode_frame, text="zimageturbo (Positiveのみ出力)", variable=self.mode_var, value="turbo", command=self._on_mode_change)
        r1.pack(side=tk.LEFT, padx=10)
        r2 = ttk.Radiobutton(mode_frame, text="zimagebase (Positive & Negative出力)", variable=self.mode_var, value="base", command=self._on_mode_change)
        r2.pack(side=tk.LEFT, padx=10)

        # ── System Prompt ───────────────────────────────────────────
        sys_frame = ttk.LabelFrame(self, text=" System Prompt ", padding=6)
        sys_frame.pack(fill=tk.BOTH, expand=True, **PAD)

        self.sys_prompt_text = scrolledtext.ScrolledText(sys_frame, height=8, wrap=tk.WORD, font=("Consolas", 9))
        self.sys_prompt_text.pack(fill=tk.BOTH, expand=True)
        self.sys_prompt_text.insert("1.0", SYSTEM_PROMPT_TURBO)
        
        # ── User Prompt ────────────────────────────────────────────
        user_frame = ttk.LabelFrame(self, text=" User Prompt ", padding=6)
        user_frame.pack(fill=tk.X, **PAD)

        self.user_prompt_text = tk.Text(user_frame, height=2, wrap=tk.WORD, font=("Consolas", 9))
        self.user_prompt_text.pack(fill=tk.X, expand=True)
        self.user_prompt_text.insert("1.0", USER_PROMPT)

        # ── コントロール & プログレス ───────────────────────────
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=tk.X, **PAD)

        self.start_btn = ttk.Button(ctrl_frame, text="▶ 一括生成スタート", style="Accent.TButton", command=self._toggle_run)
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.status_var = tk.StringVar(value="待機中 - サーバーを起動してください")
        ttk.Label(ctrl_frame, textvariable=self.status_var, font=("Meiryo", 9, "bold")).pack(side=tk.LEFT, padx=10)

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(ctrl_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=10)

        # ── ログエリア ───────────────────────────
        log_frame = ttk.LabelFrame(self, text=" 生成ログ ", padding=6)
        log_frame.pack(fill=tk.BOTH, expand=True, **PAD)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, wrap=tk.WORD, font=("Consolas", 9), state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 起動時に自動で読み込みを実行
        self.after(500, self._refresh_models)

    # ------------------------------------------------------------------
    # Backend Management (LM Studio 専用)
    # ------------------------------------------------------------------
    def _start_backend(self) -> None:
        self.start_backend_btn.configure(state=tk.DISABLED)
        self.status_var.set("LM Studio: サーバー起動中...")
        threading.Thread(target=self._start_lmstudio_worker, daemon=True).start()

    def _start_lmstudio_worker(self) -> None:
        try:
            proc = subprocess.run(["lms", "server", "start"], shell=True, capture_output=True, text=True, creationflags=_NO_WIN)
            if proc.returncode == 0:
                self.after(0, lambda: self.status_var.set("LM Studio サーバー起動完了"))
                self._log("[OK] LM Studio サーバー起動完了")
                # サーバー起動後、自動でリスト更新を走らせる
                self.after(1000, self._refresh_models)
            else:
                self.after(0, lambda: self.status_var.set("LM Studio 起動失敗"))
                self._log(f"[Error] LM Studio 起動失敗/あるいは既に起動している可能性があります: {proc.stderr}")
        except Exception as e:
            self.after(0, lambda: self.status_var.set("LM Studio 起動失敗"))
            self._log(f"[Error] LM Studio 起動失敗: {e}")
        self.after(0, lambda: self.start_backend_btn.configure(state=tk.NORMAL))

    def _stop_backend(self) -> None:
        threading.Thread(target=self._stop_lmstudio_worker, daemon=True).start()

    def _stop_lmstudio_worker(self) -> None:
        subprocess.run(["lms", "server", "stop"], shell=True, capture_output=True, creationflags=_NO_WIN)
        self.after(0, lambda: self.status_var.set("LM Studio サーバー停止しました"))
        self._log("[OK] LM Studio サーバー停止完了")


    # ------------------------------------------------------------------
    # Model Management
    # ------------------------------------------------------------------
    def _refresh_models(self) -> None:
        self.status_var.set("モデルリスト取得中...")
        threading.Thread(target=self._refresh_models_worker, daemon=True).start()

    def _refresh_models_worker(self) -> None:
        models = self.client.list_models()
        self.after(0, lambda: self._update_combo(models))

    def _update_combo(self, models):
        if models:
            self.model_combo.configure(values=models)
            if not self.model_combo.get():
                self.model_combo.set(models[0])
            self.status_var.set(f"モデル {len(models)} 件取得完了")
            self._log(f"[OK] モデルリスト取得完了。対象モデルを選択してください。")
        else:
            self.status_var.set("モデルリスト取得失敗（サーバー未起動？）")
            self._log("[WARN] モデルが取得できません。バックエンドサーバーが起動しているか確認してください。")

    def _load_model(self) -> None:
        model_id = self.model_combo.get().strip()
        if not model_id:
            messagebox.showwarning("Warning", "モデルを選択してください。")
            return
        ctx_len = int(self.ctx_combo.get())
        self.load_btn.configure(state=tk.DISABLED)
        self._load_time_var.set("ロード中...")
        self.status_var.set(f"モデルをロード中: {model_id} (ctx={ctx_len})")
        threading.Thread(target=self._load_model_worker, args=(model_id, ctx_len), daemon=True).start()

    def _load_model_worker(self, model_id: str, ctx_len: int) -> None:
        try:
            elapsed = self.client.load_model(model_id, ctx_len)
            self.after(0, lambda e=elapsed: self._load_time_var.set(f"ロード: {e:.1f}s"))
            self.after(0, lambda: self.status_var.set(f"{model_id} ロード完了"))
            self._log(f"[システム] {model_id} をロードしました (コンテキスト長: {ctx_len})")
        except Exception as ex:
            self.after(0, lambda: self._load_time_var.set("ロード失敗"))
            self.after(0, lambda e=ex: messagebox.showerror("ロードエラー", str(e)))
            self.after(0, lambda: self.status_var.set("モデルロード失敗"))
        finally:
            self.after(0, lambda: self.load_btn.configure(state=tk.NORMAL))

    def _unload_model(self) -> None:
        self.unload_btn.configure(state=tk.DISABLED)
        self.status_var.set("アンロード中...")
        threading.Thread(target=self._unload_model_worker, daemon=True).start()

    def _unload_model_worker(self) -> None:
        res = self.client.unload_all()
        def _done():
            if res == "success":
                self._load_time_var.set("")
                self.status_var.set("アンロード完了 / VRAM解放済み")
                self._log("[システム] 全モデルをアンロードし、VRAMを解放しました。")
            else:
                self.status_var.set("アンロード失敗")
            self.unload_btn.configure(state=tk.NORMAL)
        self.after(0, _done)

    # ------------------------------------------------------------------
    # Handlers & Logic
    # ------------------------------------------------------------------
    def _on_mode_change(self):
        mode = self.mode_var.get()
        self.sys_prompt_text.delete("1.0", tk.END)
        if mode == "turbo":
            self.sys_prompt_text.insert("1.0", SYSTEM_PROMPT_TURBO)
        else:
            self.sys_prompt_text.insert("1.0", SYSTEM_PROMPT_BASE)

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder_var.set(folder)
            self._scan_folder()

    def _browse_output(self):
        file = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text file", "*.txt")])
        if file:
            self.out_var.set(file)

    def _scan_folder(self):
        folder = self.folder_var.get()
        if not os.path.exists(folder):
            self.status_var.set("エラー: フォルダが存在しません")
            return
        
        exts = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]
        self.image_files = []
        for ext in exts:
            self.image_files.extend(glob.glob(os.path.join(folder, ext)))
            self.image_files.extend(glob.glob(os.path.join(folder, ext.upper())))
        
        self.status_var.set(f"準備完了: {len(self.image_files)}枚の画像を見つけました")
        self.progress_var.set(0)

    def _log(self, text: str):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _toggle_run(self):
        if not self.is_running:
            self._scan_folder()
            if not self.image_files:
                messagebox.showwarning("警告", "指定フォルダに画像がありません。")
                return
                
            selected_model = self.model_combo.get().strip()
            if selected_model:
                self.client.model = selected_model
            
            self.is_running = True
            self.cancel_requested = False
            self.start_btn.configure(text="■ 停止 (Stop)")
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.delete("1.0", tk.END)
            self.log_text.configure(state=tk.DISABLED)
            
            threading.Thread(target=self._generation_worker, daemon=True).start()
        else:
            self.cancel_requested = True
            self.start_btn.configure(state=tk.DISABLED, text="停止中...")

    def _generation_worker(self):
        out_path = self.out_var.get()
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        
        sys_prompt = self.sys_prompt_text.get("1.0", tk.END).strip()
        user_prompt = self.user_prompt_text.get("1.0", tk.END).strip()
        mode = self.mode_var.get()
        total = len(self.image_files)
        
        self._log(f"--- 処理開始 ({total} ファイル) ---")
        self._log(f"使用モデル: {self.client.model}")
        self._log(f"出力先: {out_path}")
        
        success_count = 0
        with open(out_path, "a", encoding="utf-8") as f:
            for idx, img_path in enumerate(self.image_files):
                if self.cancel_requested:
                    self._log(f"--- ユーザーにより中断されました ---")
                    break
                
                filename = os.path.basename(img_path)
                self.status_var.set(f"処理中 ({idx+1}/{total}): {filename}")
                self._log(f"[{idx+1}/{total}] 解析中: {filename} ...")
                
                try:
                    result = self.client.generate_prompt(img_path, sys_prompt, user_prompt)
                    
                    if mode == "turbo":
                        f.write(f"positive: {result.strip()}\n")
                        f.write(f"negative: \n")
                        f.write("\n")
                    else:
                        pos_text = ""
                        neg_text = ""
                        if "POSITIVE:" in result.upper() and ("NEGATIVE:" in result.upper() or "NEGATIVE PROMPT:" in result.upper()):
                            parts = result.split("NEGATIVE:")
                            if len(parts) < 2:
                                parts = result.upper().split("NEGATIVE PROMPT:")
                                
                            pos_text = parts[0].replace("POSITIVE:", "").strip()
                            if len(parts) > 1:
                                neg_text = parts[1].strip()
                        else:
                            pos_text = result.strip()
                        
                        f.write(f"positive: {pos_text}\n")
                        f.write(f"negative: {neg_text}\n")
                        f.write("\n")
                    
                    f.flush()
                    success_count += 1
                    self._log(f"  -> 成功")
                    
                except Exception as e:
                    self._log(f"  -> エラー: {e}")
                
                progress = ((idx + 1) / total) * 100
                self.after(0, lambda p=progress: self.progress_var.set(p))
                
        self._log(f"--- 全処理終了 (書き込み数: {success_count}) ---")
        self.status_var.set(f"完了！ VRAMを解放中です...")
        
        self.client.unload_all()
        self._log("[System] VRAMを開放しました (lms unload --all)")
        
        self.is_running = False
        self.cancel_requested = False
        self.after(0, self._finalize_ui)

    def _finalize_ui(self):
        self.status_var.set("待機中 - 処理が完了しました")
        self.start_btn.configure(state=tk.NORMAL, text="▶ 一括生成スタート")
        self.progress_var.set(0)

if __name__ == "__main__":
    app = MassPromptGeneratorApp()
    app.mainloop()
