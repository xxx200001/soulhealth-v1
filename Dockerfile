# ---- SOULHEALTH V1 · 微信云托管 Dockerfile ----
# 微信云托管要求容器监听 80 端口

FROM python:3.12-slim

# 系统依赖（PyMuPDF / Pillow 可能需要）
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libjpeg62-turbo libpng16-16 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，改代码不用重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 前端已构建好在 web/dist，后端会自动托管

# 微信云托管要求监听 80 端口
ENV SOULHEALTH_PORT=80
ENV SOULHEALTH_HOST=0.0.0.0

EXPOSE 80

CMD ["python", "run.py"]
