@echo off
chcp 65001 >nul
echo ==============================================================
echo  RunPod ドライランテスト環境 (Local Docker) 起動スクリプト
echo ==============================================================
echo.
echo 1. Dockerイメージをビルドします...
echo (変更がない場合はキャッシュが使われます)
cd /d "C:\AIwork\ImageGeneration\Runpod\Runpod_ComfyUI"
docker build -f docker/Dockerfile -t runpod-comfyui-test .
if %errorlevel% neq 0 (
    echo [ERROR] ビルドに失敗しました。Docker Desktopが起動しているか確認してください。
    pause
    exit /b %errorlevel%
)

echo.
echo 2. コンテナを起動します...
echo 起動後、ブラウザで以下のURLを開いてください。
echo   JupyterLab : http://localhost:8888
echo   ComfyUI    : http://localhost:8188
echo.
echo 終了する場合は、このコンソールで Ctrl+C を2回押してください。
echo --------------------------------------------------------------

docker run --gpus all --rm -it ^
  -p 8888:8888 -p 8188:8188 ^
  -v "%CD%:/workspace/runpod" ^
  runpod-comfyui-test

pause
