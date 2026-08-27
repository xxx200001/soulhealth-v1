import os
import sys
import time
import re
import shutil
import subprocess
import threading
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def free_port(port=8001):
    """清理占用端口的旧残留进程，防止 WinError 10048 端口冲突"""
    try:
        out = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True, errors="ignore")
        pids = set()
        for line in out.splitlines():
            parts = line.strip().split()
            if len(parts) >= 5 and "LISTENING" in parts:
                pids.add(parts[-1])
        for pid in pids:
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def ensure_cloudflared(base_dir):
    """确保 cloudflared.exe 可用；若系统未安装则自动下载到项目根目录"""
    # 1. 检查环境变量 PATH
    cmd = shutil.which("cloudflared")
    if cmd:
        return cmd

    # 2. 检查项目根目录
    local_exe = os.path.join(base_dir, "cloudflared.exe")
    if os.path.exists(local_exe):
        return local_exe

    # 3. 自动从 GitHub / 镜像源下载
    print("[提示] 检测到本机未安装 Cloudflare 穿透工具，正在为您自动下载 cloudflared.exe...")
    urls = [
        "https://ghproxy.net/https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe",
        "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    ]
    for url in urls:
        try:
            print(f"正在从 {url.split('/')[2]} 下载穿透组件...")
            urllib.request.urlretrieve(url, local_exe)
            if os.path.exists(local_exe) and os.path.getsize(local_exe) > 1000000:
                print("穿透组件下载完成！")
                return local_exe
        except Exception as e:
            print(f"下载尝试失败: {e}")

    return None


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    print("=" * 60)
    print("  SOULHEALTH V1 启动 & Cloudflare 穿透工具")
    print("=" * 60)

    # 自动解除 8001 端口占用
    free_port(8001)

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
            pass

    t_server = threading.Thread(target=log_server, daemon=True)
    t_server.start()

    time.sleep(2)

    # 2. 检查并启动 Cloudflare Tunnel
    cloudflared_bin = ensure_cloudflared(base_dir)
    tunnel_proc = None
    tunnel_url = None

    if cloudflared_bin:
        print("[2/3] 启动 Cloudflare 穿透 (指向 http://localhost:8001)...")
        try:
            tunnel_proc = subprocess.Popen(
                [cloudflared_bin, "tunnel", "--url", "http://localhost:8001"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding="utf-8",
                errors="replace"
            )

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
        except Exception as e:
            print(f"[警告] 穿透启动异常: {e}")
    else:
        print("[2/3] 未能加载穿透组件，自动使用纯本地服务模式。")

    print("\n" + "=" * 60, flush=True)
    print("[SUCCESS] SOULHEALTH 服务已就绪！", flush=True)
    if tunnel_url:
        print(f"公网访问地址: {tunnel_url}", flush=True)
        with open("tunnel_url.txt", "w", encoding="utf-8") as f:
            f.write(tunnel_url + "\n")
            f.flush()
    print("本地访问地址: http://localhost:8001", flush=True)
    print("演示账号: demo / demo123456", flush=True)
    print("=" * 60 + "\n", flush=True)

    # 保持常驻运行
    try:
        while True:
            time.sleep(1)
            if server_proc.poll() is not None:
                print("[警告] 后端服务已退出。")
                break
    except KeyboardInterrupt:
        print("\n正在关闭服务...")
    finally:
        if server_proc.poll() is None:
            server_proc.terminate()
        if tunnel_proc and tunnel_proc.poll() is None:
            tunnel_proc.terminate()


if __name__ == "__main__":
    main()
