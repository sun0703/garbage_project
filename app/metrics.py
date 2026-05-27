"""Prometheus监控指标"""

import time
import logging
from typing import Optional

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# HTTP 请求指标
http_requests_total = Counter(
    "ecosort_http_requests_total",
    "HTTP 请求总数",
    ["method", "path", "status"]
)

# 请求延迟直方图
http_request_duration_seconds = Histogram(
    "ecosort_http_request_duration_seconds",
    "HTTP 请求延迟（秒）",
    ["method", "path"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# AI 推理指标
inference_requests_total = Counter(
    "ecosort_inference_requests_total",
    "AI 推理请求总数",
    ["model_type", "status"]  # model_type: yolo/feature_fallback, status: success/error
)

# 推理延迟
inference_duration_seconds = Histogram(
    "ecosort_inference_duration_seconds",
    "AI 推理延迟（秒）",
    ["model_type"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0]
)

# 缓存命中/未命中
cache_operations_total = Counter(
    "ecosort_cache_operations_total",
    "缓存操作计数",
    ["operation"]  # operation: hit, miss, set, evict
)

# 业务指标
predictions_by_category_total = Counter(
    "ecosort_predictions_by_category_total",
    "按类别的识别次数",
    ["category"]  # category: 厨余垃圾/可回收物/其他垃圾/有害垃圾
)

# 搜索请求
search_requests_total = Counter(
    "ecosort_search_requests_total",
    "搜索请求总数"
)

# 打卡次数
checkin_total = Counter(
    "ecosort_checkin_total",
    "环保打卡总次数"
)

# 答题次数
quiz_answers_total = Counter(
    "ecosort_quiz_answers_total",
    "答题总次数",
    ["result"]  # result: correct, wrong
)

# 系统指标
active_users_gauge = Gauge(
    "ecosort_active_users",
    "当前活跃用户数"
)

# 数据库连接状态
db_connection_status = Gauge(
    "ecosort_db_connection_status",
    "数据库连接状态（1=正常, 0=异常）",
    ["db_type"]
)

# 模型加载状态
model_loaded_status = Gauge(
    "ecosort_model_loaded_status",
    "模型加载状态（1=已加载, 0=未加载）",
    ["model_name"]
)


class MetricsMiddleware:
    """自动采集HTTP请求指标的中间件"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")

        # 跳过指标端点自身，避免递归
        if path == "/api/metrics":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        status_code = 200

        async def send_with_status(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            duration = time.time() - start_time
            # 归一化路径（避免高基数标签）
            normalized_path = _normalize_path(path)
            http_requests_total.labels(method=method, path=normalized_path, status=status_code).inc()
            http_request_duration_seconds.labels(method=method, path=normalized_path).observe(duration)


def _normalize_path(path: str) -> str:
    """归一化路径，防止高基数标签把Prometheus搞爆"""
    # 去除查询参数
    path = path.split("?")[0]

    # 归一化动态路径段
    parts = path.strip("/").split("/")
    normalized = []
    api_prefix = parts[0] if parts else ""

    for i, part in enumerate(parts):
        # API 路径中，第3段之后可能是动态 ID
        if i >= 3 and api_prefix == "api":
            normalized.append(":id")
        else:
            normalized.append(part)

    result = "/" + "/".join(normalized) if normalized else "/"
    return result


def get_metrics() -> bytes:
    """获取 Prometheus 格式的指标数据"""
    return generate_latest()


def get_metrics_content_type() -> str:
    """获取指标响应的 Content-Type"""
    return CONTENT_TYPE_LATEST
