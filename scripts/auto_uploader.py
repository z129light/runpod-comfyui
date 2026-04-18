import os
import time
import subprocess
import argparse

UPLOAD_DONE_FLAG = '/workspace/upload_done.flag'

IMAGE_INCLUDES = [
    '--include', '*.png',
    '--include', '*.jpg',
    '--include', '*.jpeg',
    '--include', '*.webp',
]


def run_rclone_move(watch_dir, remote_path, transfers):
    cmd = [
        'rclone', 'move',
        watch_dir,
        remote_path,
        '--min-age', '10s',
        '--log-level', 'INFO',
        '--transfers', str(transfers),
    ] + IMAGE_INCLUDES

    result = subprocess.run(cmd, capture_output=True, text=True)
    log_output = (result.stdout + result.stderr).strip()

    if result.returncode != 0:
        print(f'[{time.strftime("%H:%M:%S")}] [ERROR] rclone failed (code {result.returncode}):')
        if log_output:
            print(log_output)
        return False

    if log_output and ('Transferred:' in log_output or 'Deleted:' in log_output):
        print(f'[{time.strftime("%H:%M:%S")}] アップロード完了')
        print(log_output)

    return True


def is_output_empty(watch_dir):
    try:
        entries = [f for f in os.listdir(watch_dir) if not f.startswith('.')]
        return len(entries) == 0
    except OSError:
        return False


def start_uploader(watch_dir, remote_path, check_interval, transfers):
    print(f'[*] 監視開始: {watch_dir}')
    print(f'[*] 転送先: {remote_path}')
    print(f'[*] チェック間隔: {check_interval}秒 / 並列転送数: {transfers}')
    print('------------------------------------------')

    os.makedirs(watch_dir, exist_ok=True)

    # 起動時にフラグをリセット
    if os.path.exists(UPLOAD_DONE_FLAG):
        os.remove(UPLOAD_DONE_FLAG)

    try:
        while True:
            success = run_rclone_move(watch_dir, remote_path, transfers)

            if success and is_output_empty(watch_dir):
                with open(UPLOAD_DONE_FLAG, 'w') as f:
                    f.write(str(time.time()))
                print(f'[{time.strftime("%H:%M:%S")}] 全ファイル転送済み -> {UPLOAD_DONE_FLAG} を作成')
            elif os.path.exists(UPLOAD_DONE_FLAG):
                # 新しいファイルが生成されたらフラグをリセット
                os.remove(UPLOAD_DONE_FLAG)

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print('\n[*] アップローダーを停止しました。')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ComfyUI to Google Drive Auto Uploader')
    parser.add_argument('--watch_dir', type=str, default='/workspace/ComfyUI/output')
    parser.add_argument('--remote_path', type=str, default='gdrive:AI/ImageGeneration/RunPod_Output')
    parser.add_argument('--interval', type=int, default=30)
    parser.add_argument('--transfers', type=int, default=4)

    args = parser.parse_args()
    start_uploader(args.watch_dir, args.remote_path, args.interval, args.transfers)
