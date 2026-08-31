import urllib.request
import traceback

urls = [
    "http://127.0.0.1:8002/",
    "http://127.0.0.1:8002/api/health",
    "http://127.0.0.1:8002/favicon.ico",
    "http://127.0.0.1:8002/assets/index-B6bAUTX8.js",
    "http://127.0.0.1:8002/assets/index-D6jg1XNi.css",
]

for url in urls:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as res:
            print(f"URL: {url} -> {res.status} (Length: {len(res.read())})")
    except Exception as e:
        print(f"URL: {url} -> ERROR: {e}")
