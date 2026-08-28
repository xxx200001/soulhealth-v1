import os
import sys
import re
import subprocess
import time
import threading

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(base_dir)
    
    # 查找 cloudflared.exe
    cf_exe = os.path.join(base_dir, "cloudflared.exe")
    if not os.path.exists(cf_exe):
        import shutil
        cf_exe = shutil.which("cloudflared")
    
    if not cf_exe:
        print("[ERROR] 找不到 cloudflared.exe")
        return
        
    print(f"[TUNNEL] 使用穿透工具: {cf_exe}")
    
    # 杀掉旧的 cloudflared
    subprocess.run("taskkill /F /IM cloudflared.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    
    target_url = "http://localhost:5173"
    print(f"[TUNNEL] 启动穿透指向: {target_url}")
    
    proc = subprocess.Popen(
        [cf_exe, "tunnel", "--url", target_url],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace"
    )
    
    pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    tunnel_url = None
    
    def reader():
        nonlocal tunnel_url
        for line in iter(proc.stdout.readline, ""):
            if not line:
                break
            if not tunnel_url:
                m = pattern.search(line)
                if m:
                    tunnel_url = m.group(0)
                    print(f"\n========================================================")
                    print(f"[SUCCESS] Cloudflare 公网穿透成功！")
                    print(f"公网访问地址: {tunnel_url}")
                    print(f"直达上传页: {tunnel_url}/upload")
                    print(f"========================================================\n", flush=True)
                    try:
                        with open("tunnel_url.txt", "w", encoding="utf-8") as f:
                            f.write(tunnel_url + "\n")
                    except Exception:
                        pass
                        
    t = threading.Thread(target=reader, daemon=True)
    t.start()
    
    # 等待获取 URL
    start = time.time()
    while not tunnel_url and time.time() - start < 30:
        time.sleep(0.5)
        
    if not tunnel_url:
        print("[WARN] 30秒内未捕获到 trycloudflare.com 链接")
        
    # 保持运行
    try:
        while proc.poll() is None:
            time.sleep(1)
    except KeyboardInterrupt:
        proc.terminate()

if __name__ == "__main__":
    main()
