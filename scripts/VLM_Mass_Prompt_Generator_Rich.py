import base64
import os
import subprocess
import sys
import threading
import time
import glob
import requests
import tkinter as tk
from tkinter import filedialog, messagebox

try:
    import customtkinter as ctk
except ImportError:
    messagebox.showerror("Error", "customtkinterがインストールされていません。\npip install customtkinter を実行してください。")
    sys.exit(1)

_NO_WIN = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# ==============================================================================
# Configuration
# ==============================================================================
SYSTEM_PROMPT_TURBO = """\
あなたは写真のテクニカル・ディレクターです。
画像を以下の8つのカテゴリで詳細に記述してください。

1. COMPOSITION: ショットタイプ（full-body / wide 等を優先）、
   フレーム内での被写体の占有率（%）、被写体の配置（三分割法等）、
   カメラアングル、被写体とカメラの推定距離（メートル単位）。
   ★足元が接地している地面の質感や、被写体の頭上・左右にある「余白（Negative Space）」の状況を必ず含めてください。
2. SUBJECT: 被写体の正確な記述（年齢、民族推定、体型、服装、表情の微細なニュアンス）
3. MATERIAL: 各表面の材質（肌の質感、衣服の繊維、地面の素材、背景の建物の質感等）
4. LIGHTING: 光源の数・方向・色温度・硬さ、環境全体を包む光（Ambient Light）の状況
5. PHYSICS: 反射、屈折、影の落ち方（特に被写体が落とす影の長さと形状、接地感）
6. LENS: 推定焦点距離 (mm)、被写界深度、周辺パースの歪み等
7. IMPERFECTION: 自然な不完全さ（衣服のシワ、汚れ、背景のダスト、フレア等）
8. ATMOSPHERE: 奥行き感、遠景の空気遠近法、被写体と背景の間の空間密度・湿度感

出力は英語のプロンプトのみで、1行で出力すること。出力は必ずポジティブ内容のみとすること。

出力例
COMPOSITION: medium shot, subject occupies 40% of the frame...
"""

SYSTEM_PROMPT_BASE = SYSTEM_PROMPT_TURBO

USER_PROMPT = "Analyze this image and generate the prompt."

# ==============================================================================
# Backend Client
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
# UI Structure (Rich)
# ==============================================================================
class MassPromptGeneratorAppRich(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # UI Theme
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        
        self.title("Mass Prompt Generator - Pro Edition")
        self.geometry("900x950")
        self.minsize(800, 900)
        
        self.client = VLMClient()
        self.is_running = False
        self.cancel_requested = False
        self.image_files = []
        
        self._setup_ui()
        self.after(500, self._refresh_models)

    def _setup_ui(self):
        # メインコンテナ
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # ── 1. Settings Section (Server & Model) ───────────────────
        settings_frame = ctk.CTkFrame(main_frame)
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Server Control Row
        srv_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        srv_row.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        ctk.CTkLabel(srv_row, text="LM Studio Server:", font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT)
        self.start_srv_btn = ctk.CTkButton(srv_row, text="起動 (Start)", width=120, command=self._start_backend, fg_color="#2E8B57", hover_color="#3CB371")
        self.start_srv_btn.pack(side=tk.LEFT, padx=(15, 5))
        self.stop_srv_btn = ctk.CTkButton(srv_row, text="停止 (Stop)", width=120, command=self._stop_backend, fg_color="#C0392B", hover_color="#E74C3C")
        self.stop_srv_btn.pack(side=tk.LEFT, padx=5)
        
        # Model Control Row
        mod_row = ctk.CTkFrame(settings_frame, fg_color="transparent")
        mod_row.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        ctk.CTkLabel(mod_row, text="Model Select:", font=ctk.CTkFont(weight="bold")).pack(side=tk.LEFT)
        self.model_combo = ctk.CTkComboBox(mod_row, values=[], width=250, state="readonly")
        self.model_combo.pack(side=tk.LEFT, padx=(15, 5))
        
        self.refresh_btn = ctk.CTkButton(mod_row, text="↻ 再取得", width=80, fg_color="gray30", command=self._refresh_models)
        self.refresh_btn.pack(side=tk.LEFT, padx=5)
        
        ctk.CTkLabel(mod_row, text="Ctx Length:").pack(side=tk.LEFT, padx=(10, 5))
        self.ctx_combo = ctk.CTkComboBox(mod_row, values=["4096", "8192", "12288", "16000", "24000"], width=90, state="readonly")
        self.ctx_combo.set("8192")
        self.ctx_combo.pack(side=tk.LEFT, padx=5)
        
        self.load_btn = ctk.CTkButton(mod_row, text="ロード", width=80, command=self._load_model)
        self.load_btn.pack(side=tk.LEFT, padx=5)
        self.unload_btn = ctk.CTkButton(mod_row, text="アンロード", width=80, fg_color="#8E44AD", hover_color="#9B59B6", command=self._unload_model)
        self.unload_btn.pack(side=tk.LEFT, padx=5)

        # ── 2. Input / Output Paths ──────────────────────────────────
        path_frame = ctk.CTkFrame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Input
        in_row = ctk.CTkFrame(path_frame, fg_color="transparent")
        in_row.pack(fill=tk.X, padx=15, pady=(15, 5))
        ctk.CTkLabel(in_row, text="読込フォルダ:", width=100, anchor="w").pack(side=tk.LEFT)
        self.folder_var = tk.StringVar(value=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "input_images")))
        ctk.CTkEntry(in_row, textvariable=self.folder_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        ctk.CTkButton(in_row, text="参照", width=80, fg_color="gray30", command=self._browse_folder).pack(side=tk.LEFT)
        
        # Output
        out_row = ctk.CTkFrame(path_frame, fg_color="transparent")
        out_row.pack(fill=tk.X, padx=15, pady=(5, 15))
        ctk.CTkLabel(out_row, text="保存先(txt):", width=100, anchor="w").pack(side=tk.LEFT)
        self.out_var = tk.StringVar(value=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "prompts", "generated_prompts.txt")))
        ctk.CTkEntry(out_row, textvariable=self.out_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)
        ctk.CTkButton(out_row, text="変更", width=80, fg_color="gray30", command=self._browse_output).pack(side=tk.LEFT)

        # ── 3. Prompt Configuration (Tabs) ───────────────────────────
        self.mode_var = tk.StringVar(value="turbo")
        
        mode_radio_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        mode_radio_row.pack(fill=tk.X, pady=(0, 5))
        ctk.CTkRadioButton(mode_radio_row, text="1. zimageturbo (Positiveのみ)", variable=self.mode_var, value="turbo", command=self._on_mode_change).pack(side=tk.LEFT, padx=(0, 20))
        ctk.CTkRadioButton(mode_radio_row, text="2. zimagebase (Pos & Neg分析)", variable=self.mode_var, value="base", command=self._on_mode_change).pack(side=tk.LEFT)
        
        prompt_tabs = ctk.CTkTabview(main_frame, height=220)
        prompt_tabs.pack(fill=tk.X, pady=(0, 15))
        tab_sys = prompt_tabs.add("System Prompt")
        tab_usr = prompt_tabs.add("User Prompt")
        tab_neg = prompt_tabs.add("Negative Prompt (Base Only)")
        
        self.sys_text = ctk.CTkTextbox(tab_sys, wrap="word", font=ctk.CTkFont(family="Consolas", size=13))
        self.sys_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.sys_text.insert("1.0", SYSTEM_PROMPT_TURBO)
        
        self.usr_text = ctk.CTkTextbox(tab_usr, wrap="word", font=ctk.CTkFont(family="Consolas", size=13))
        self.usr_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.usr_text.insert("1.0", USER_PROMPT)

        self.neg_text = ctk.CTkTextbox(tab_neg, wrap="word", font=ctk.CTkFont(family="Consolas", size=13))
        self.neg_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.neg_text.insert("1.0", "deformed limbs, blurry face, distorted fingers, messy hair, cartoonish textures, overexposed highlights, asymmetrical eyes")

        # ── 4. Main Control & Progress ─────────────────────────────
        run_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        run_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.run_btn = ctk.CTkButton(run_frame, text="▶ START GENERATION", height=45, font=ctk.CTkFont(size=16, weight="bold"), fg_color="#1E90FF", hover_color="#4169E1", command=self._toggle_run)
        self.run_btn.pack(side=tk.LEFT, padx=(0, 15))
        
        progress_container = ctk.CTkFrame(run_frame, fg_color="transparent")
        progress_container.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.status_var = tk.StringVar(value="Ready - Waiting for connection...")
        ctk.CTkLabel(progress_container, textvariable=self.status_var, font=ctk.CTkFont(weight="bold"), text_color="#A9DFBF").pack(anchor="w", pady=(0, 5))
        
        self.progress_bar = ctk.CTkProgressBar(progress_container, mode="determinate", height=12)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill=tk.X)

        # ── 5. Logs ────────────────────────────────────────────────
        log_label = ctk.CTkLabel(main_frame, text="Execution Logs", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w")
        self.log_text = ctk.CTkTextbox(main_frame, wrap="word", font=ctk.CTkFont(family="Consolas", size=12), fg_color="#1C1C1C", text_color="#E0E0E0")
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.log_text.configure(state="disabled")


    # ------------------------------------------------------------------
    # Handlers & Logic (Adapting previous functions to CTk)
    # ------------------------------------------------------------------
    def _log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _start_backend(self):
        self.start_srv_btn.configure(state="disabled")
        self.status_var.set("LM Studio サーバー起動中...")
        threading.Thread(target=self._start_lmstudio_worker, daemon=True).start()

    def _start_lmstudio_worker(self):
        try:
            proc = subprocess.run(["lms", "server", "start"], shell=True, capture_output=True, text=True, creationflags=_NO_WIN)
            if proc.returncode == 0:
                self.after(0, lambda: self.status_var.set("LM Studio サーバー起動完了"))
                self._log("[SERVER] サーバーの起動に成功しました。")
                self.after(1000, self._refresh_models)
            else:
                self.after(0, lambda: self.status_var.set("LM Studio 起動失敗"))
                self._log(f"[ERROR] サーバー起動エラー: {proc.stderr}")
        except Exception as e:
            self.after(0, lambda: self.status_var.set("起動失敗"))
            self._log(f"[ERROR] {e}")
        self.after(0, lambda: self.start_srv_btn.configure(state="normal"))

    def _stop_backend(self):
        threading.Thread(target=self._stop_lmstudio_worker, daemon=True).start()

    def _stop_lmstudio_worker(self):
        subprocess.run(["lms", "server", "stop"], shell=True, capture_output=True, creationflags=_NO_WIN)
        self.after(0, lambda: self.status_var.set("LM Studio サーバー停止済"))
        self._log("[SERVER] サーバーを停止しました。")

    def _refresh_models(self):
        self.status_var.set("モデルリスト取得中...")
        threading.Thread(target=self._refresh_models_worker, daemon=True).start()

    def _refresh_models_worker(self):
        models = self.client.list_models()
        self.after(0, lambda: self._update_combo(models))

    def _update_combo(self, models):
        if models:
            # ユーザーの要望通り「gemma4」または「gemma」を含むモデルを優先して一番上に持ってくる
            models = sorted(models, key=lambda x: (
                "gemma4" not in x.lower(),
                "gemma" not in x.lower(),
                x.lower()
            ))
            
            self.model_combo.configure(values=models)
            self.model_combo.set(models[0])
            self.status_var.set(f"準備完了: モデル {len(models)} 件")
            self._log("[SYSTEM] モデルリストを正常に取得しました。")
        else:
            self.status_var.set("リスト取得失敗（サーバー未起動）")
            self._log("[WARN] モデルリストが空です。サーバーを起動してください。")

    def _load_model(self):
        model_id = self.model_combo.get()
        if not model_id: return
        ctx_len = int(self.ctx_combo.get())
        self.load_btn.configure(state="disabled")
        self.status_var.set(f"モデルロード中: {model_id} ...")
        threading.Thread(target=self._load_model_worker, args=(model_id, ctx_len), daemon=True).start()

    def _load_model_worker(self, model_id, ctx_len):
        try:
            elapsed = self.client.load_model(model_id, ctx_len)
            self.after(0, lambda: self.status_var.set(f"ロード完了 ({elapsed:.1f}s)"))
            self._log(f"[SYSTEM] '{model_id}' ロード完了 (Ctx: {ctx_len})")
        except Exception as ex:
            self.after(0, lambda: self.status_var.set("ロード失敗"))
            self._log(f"[ERROR] モデルロード失敗: {ex}")
        finally:
            self.after(0, lambda: self.load_btn.configure(state="normal"))

    def _unload_model(self):
        self.unload_btn.configure(state="disabled")
        self.status_var.set("VRAMアンロード中...")
        threading.Thread(target=self._unload_model_worker, daemon=True).start()

    def _unload_model_worker(self):
        res = self.client.unload_all()
        if res == "success":
            self.after(0, lambda: self.status_var.set("アンロード完了"))
            self._log("[SYSTEM] VRAM上のモデルを解放しました。")
        else:
            self.after(0, lambda: self.status_var.set("アンロード失敗"))
        self.after(0, lambda: self.unload_btn.configure(state="normal"))

    def _on_mode_change(self):
        mode = self.mode_var.get()
        self.sys_text.delete("1.0", "end")
        if mode == "turbo":
            self.sys_text.insert("1.0", SYSTEM_PROMPT_TURBO)
        else:
            self.sys_text.insert("1.0", SYSTEM_PROMPT_BASE)

    def _browse_folder(self):
        folder = filedialog.askdirectory()
        if folder: self.folder_var.set(folder)

    def _browse_output(self):
        f = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text file", "*.txt")])
        if f: self.out_var.set(f)

    def _toggle_run(self):
        if not self.is_running:
            folder = self.folder_var.get()
            exts = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp"]
            self.image_files = set()
            for ext in exts:
                self.image_files.update(glob.glob(os.path.join(folder, ext)))
                self.image_files.update(glob.glob(os.path.join(folder, ext.upper())))
            self.image_files = sorted(list(self.image_files))
                
            if not self.image_files:
                messagebox.showwarning("警告", "指定フォルダに画像がありません。")
                return
            
            selected_model = self.model_combo.get()
            if selected_model: self.client.model = selected_model
            
            self.is_running = True
            self.cancel_requested = False
            self.run_btn.configure(text="■ STOP GENERATION", fg_color="#C0392B", hover_color="#E74C3C")
            
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
            
            threading.Thread(target=self._generation_worker, daemon=True).start()
        else:
            self.cancel_requested = True
            self.run_btn.configure(state="disabled", text="Stopping...")

    def _generation_worker(self):
        out_path = self.out_var.get()
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        
        sys_prompt = self.sys_text.get("1.0", "end").strip()
        user_prompt = self.usr_text.get("1.0", "end").strip()
        user_neg_prompt = self.neg_text.get("1.0", "end").strip().replace("\n", " ")
        mode = self.mode_var.get()
        total = len(self.image_files)
        
        # モードがターミナルに表示されるように追加
        self._log(f"--- BATCH START ({total} items) ---")
        self._log(f"Mode  : {mode.upper()}")
        self._log(f"Model : {self.client.model}")
        self._log(f"Output: {out_path}")
        
        success_count = 0
        for idx, img_path in enumerate(self.image_files):
            if self.cancel_requested:
                self._log(f"--- ユーザーにより中断されました ---")
                break
            
            filename = os.path.basename(img_path)
            self.status_var.set(f"処理中 ({idx+1}/{total}): {filename}")
            self._log(f"▶ [{idx+1}/{total}] {filename}")
            
            try:
                result = self.client.generate_prompt(img_path, sys_prompt, user_prompt)
                result = result.strip()
                
                # 万が一AIが 'positive:' などをつけてきたら除去する
                if result.lower().startswith("positive:"):
                    result = result[9:].strip()
                if "negative:" in result.lower():
                    result = result[:result.lower().index("negative:")].strip()
                    
                # 1ファイル処理終了ごとに追記でのオープン＆クローズを行い、即座に保存・更新されるようにする
                with open(out_path, "a", encoding="utf-8") as f:
                    f.write(f"positive: {result}\n")
                    if mode == "turbo":
                        f.write(f"negative: \n")
                    else:
                        f.write(f"negative: {user_neg_prompt}\n")
                    f.write(f"---\n")
                
                success_count += 1
            except Exception as e:
                self._log(f"  [ERROR] {e}")
            
            self.after(0, lambda p=((idx+1)/total): self.progress_bar.set(p))
                
        self._log(f"--- FINISHED (Wrote {success_count} Prompts) ---")
        self.status_var.set("完了！")
        
        self.is_running = False
        self.cancel_requested = False
        self.after(0, self._finalize_ui)

    def _finalize_ui(self):
        self.status_var.set("Standby - Ready for next batch.")
        self.progress_bar.set(0)
        self.run_btn.configure(state="normal", text="▶ START GENERATION", fg_color="#1E90FF", hover_color="#4169E1")

if __name__ == "__main__":
    app = MassPromptGeneratorAppRich()
    app.mainloop()
