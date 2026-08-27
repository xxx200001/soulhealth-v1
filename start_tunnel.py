import os
import sys
import time
import re
import subprocess
import threading

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    print("=" * 60)
    print("  SOULHEALTH V1 启动 & Cloudflare 穿透工具")
    print("=" * 60)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    # 1. 启动后端服务 (端口 8001)
    print("[1/3] 启动 SOULHEALTH 服务 (FastAPI 端口 8001)...")
    server_proc = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=base_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    def log_server():
        for line in server_proc.stdout:
            # print("[Server]", line.strip())
            pass

    t_server = threading.Thread(target=log_server, daemon=True)
    t_server.start()

    time.sleep(2)

    # 2. 启动 Cloudflare Tunnel
    print("[2/3] 启动 Cloudflare 穿透 (指向 http://localhost:8001)...")
    tunnel_proc = subprocess.Popen(
        ["cloudflared", "tunnel", "--url", "http://localhost:8001"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )

    tunnel_url = None
    pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

    def read_tunnel():
        nonlocal tunnel_url
        for line in iter(tunnel_proc.stdout.readline, ""):
            if not line:
                break
            if not tunnel_url:
                m = pattern.search(line)
                if m:
                    tunnel_url = m.group(0)

    t_tunnel = threading.Thread(target=read_tunnel, daemon=True)
    t_tunnel.start()

    start_time = time.time()
    while not tunnel_url and (time.time() - start_time < 30):
        time.sleep(0.3)

    if tunnel_url:
        print("\n" + "=" * 60, flush=True)
        print("[SUCCESS] 穿透启动成功！", flush=True)
        print(f"公网访问地址: {tunnel_url}", flush=True)
        print(f"本地访问地址: http://localhost:8001", flush=True)
        print(f"演示账号: demo / demo123456", flush=True)
        print("=" * 60 + "\n", flush=True)

        with open("tunnel_url.txt", "w", encoding="utf-8") as f:
            f.write(tunnel_url + "\n")
            f.flush()
    else:
        print("\n[ERROR] 未能在 30 秒内获取到 Cloudflare 穿透链接。", flush=True)

    # 保持常驻运行
    try:
        while True:
            time.sleep(1)
            if server_proc.poll() is not None:
                print("[警告] 后端服务已退出。")
                break
            if tunnel_proc.poll() is not None:
                print("[警告] 穿透进程已退出。")
                break
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
        if tunnel_proc.poll() is None:
            tunnel_proc.terminate()

if __name__ == "__main__":
    main()
