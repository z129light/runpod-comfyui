import os
import time
import requests
import runpod
import argparse

def check_comfy_queue(url):
    """ComfyUIのキュー残数を確認する"""
    try:
        response = requests.get(f"{url}/queue", timeout=5)
        data = response.json()
        running = len(data.get('queue_running', []))
        pending = len(data.get('queue_pending', []))
        return running + pending
    except Exception as e:
        # 起動直後などで接続できない場合は、まだ起動中とみなして 1 を返す
        return 1

def terminate_self(pod_id, api_key):
    """RunPod APIを使用して自分自身を終了(Terminate)させる"""
    print(f"[*] Terminating Pod: {pod_id}")
    runpod.api_key = api_key
    try:
        runpod.terminate_pod(pod_id)
        print("[+] Termination request sent successfully.")
    except Exception as e:
        print(f"[-] Failed to terminate pod: {e}")

def monitor_and_shutdown(args):
    start_time = time.time()
    idle_since = None
    
    print(f"[*] Starting Auto-Terminator")
    print(f"[*] Target: {args.comfy_url}")
    print(f"[*] Timeout: {args.timeout_mins} mins")
    print(f"[*] Idle Threshold: {args.idle_mins} mins")
    print("------------------------------------------")

    while True:
        elapsed_mins = (time.time() - start_time) / 60
        
        # 1. タイムアウトチェック (ハードリミット)
        if elapsed_mins >= args.timeout_mins:
            print(f"\n[!] Hard timeout reached ({args.timeout_mins} mins). Shutting down.")
            break
            
        # 2. キュー枯渇チェック
        queue_count = check_comfy_queue(args.comfy_url)
        
        if queue_count == 0:
            if idle_since is None:
                idle_since = time.time()
                print(f"\n[*] Queue is empty. Starting idle timer.")
            
            idle_mins = (time.time() - idle_since) / 60
            if idle_mins >= args.idle_mins:
                print(f"\n[!] Idle threshold reached ({args.idle_mins} mins). Shutting down.")
                break
        else:
            if idle_since is not None:
                print(f"\n[*] Queue activity detected. Resetting idle timer.")
            idle_since = None

        print(f"\rElapsed: {elapsed_mins:.1f}m | Queue: {queue_count} | Idle: {0 if idle_since is None else (time.time()-idle_since)/60:.1f}m", end="", flush=True)
        time.sleep(30)

    # 終了前: upload_done.flag が立つまで待つ（最大5分）
    flag_path = '/workspace/upload_done.flag'
    print('\n[*] Waiting for final Drive sync (upload_done.flag)...')
    wait_start = time.time()
    max_wait_secs = 300
    while not os.path.exists(flag_path):
        if time.time() - wait_start > max_wait_secs:
            print('[!] Upload flag timeout (5 min). Terminating anyway.')
            break
        time.sleep(10)
    else:
        print('[+] All files synced to Drive. Proceeding to terminate.')
    
    # Terminate
    pod_id = os.environ.get('RUNPOD_POD_ID')
    api_key = os.environ.get('MY_RUNPOD_API_KEY')
    
    if pod_id and api_key:
        terminate_self(pod_id, api_key)
    else:
        print("[!] RUNPOD_POD_ID or RUNPOD_API_KEY not set. Cannot terminate automatically.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-shutdown script for RunPod ComfyUI")
    parser.add_argument("--comfy_url", type=str, default="http://localhost:8188", help="ComfyUI API URL")
    parser.add_argument("--timeout_mins", type=int, default=80, help="Hard timeout in minutes")
    parser.add_argument("--idle_mins", type=int, default=2, help="Idle minutes before shutdown")
    
    args = parser.parse_args()
    monitor_and_shutdown(args)
