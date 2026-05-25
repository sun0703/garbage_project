# ==================== 校园垃圾分类AI助手 - Dockerfile ====================
# 构建: docker build -t waste-classifier -f docker/Dockerfile .
# 运行: docker run -p 8001:8001 --env-file .env waste-classifier

FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY . .

RUN mkdir -p data models logs

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--log-level", "info"]
