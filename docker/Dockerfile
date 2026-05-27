# 校园垃圾分类AI助手 - Dockerfile
# 构建: docker build -t ecosort -f docker/Dockerfile .
# 运行: docker run -p 8001:8001 --env-file .env ecosort

# 构建阶段
FROM python:3.11-slim AS builder

WORKDIR /build

# 编译依赖（PostgreSQL客户端库等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 运行阶段
FROM python:3.11-slim

WORKDIR /app

# 运行时系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从builder阶段复制Python依赖
COPY --from=builder /install /usr/local

# 复制应用代码
COPY . .

# 非root用户运行
RUN adduser --disabled-password --gecos '' appuser && \
    mkdir -p data models logs uploads && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/api/health || exit 1

# 生产启动（2 worker）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2", "--log-level", "info"]
