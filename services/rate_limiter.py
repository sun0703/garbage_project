"""
基于滑动窗口算法的 IP 级请求限流器（增强版）
从 main.py 提取为独立模块
"""

import time
import threading
import random
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    基于滑动窗口算法的 IP 级请求限流器（增强版）

    特性：
    - 支持按 API 路径设置不同的限流策略
    - 使用滑动时间窗口确保精确的速率控制
    - 自动清理过期记录防止内存泄漏
    - 支持白名单 IP 跳过限流
    - 提供详细的限流状态信息用于响应头

    生产环境建议替换为 Redis 分布式限流
    """

    # 不同路径的限流配置：{路径前缀: (最大请求数, 时间窗口秒数)}
    PATH_LIMITS = {
        "/api/predict": (20, 60),        # 预测接口：每分钟20次（计算密集型）
        "/api/batch_predict": (10, 60),   # 批量预测：每分钟10次
        "/api/search": (30, 60),          # 搜索接口：每分钟30次
        "/api/auth/": (10, 60),           # 认证接口：每分钟10次（防暴力破解）
        "default": (30, 60),              # 默认：每分钟30次
    }

    def __init__(self, default_max_requests: int = 30, default_window_seconds: int = 60):
        """
        初始化限流器

        @param default_max_requests: 默认窗口内允许的最大请求数
        @param default_window_seconds: 默认统计窗口时长（秒）
        """
        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        # 存储结构：{ client_ip: { path_prefix: [timestamp1, timestamp2, ...] } }
        self._requests: dict[str, dict[str, list[float]]] = {}
        self._lock = threading.Lock()
        # 白名单 IP 集合（如本地开发、测试服务器）
        self._whitelist: set[str] = {"127.0.0.1", "::1", "localhost"}

    def add_whitelist(self, ip: str):
        """添加白名单 IP"""
        self._whitelist.add(ip)

    def remove_whitelist(self, ip: str):
        """移除白名单 IP"""
        self._whitelist.discard(ip)

    def _get_limit_for_path(self, path: str) -> tuple[int, int]:
        """根据路径获取对应的限流配置"""
        for prefix, limit in self.PATH_LIMITS.items():
            if prefix != "default" and path.startswith(prefix):
                return limit
        return (self.default_max_requests, self.default_window_seconds)

    def is_allowed(self, client_ip: str, path: str = "") -> tuple[bool, dict]:
        """
        判断当前请求是否允许通过

        @param client_ip: 客户端 IP 地址
        @param path: 请求路径（用于分级限流）
        @return tuple[是否允许, 限制信息字典]
        """
        # 白名单 IP 直接放行
        if client_ip in self._whitelist:
            return True, {
                "remaining": 999,
                "reset_time": 0,
                "retry_after": 0,
                "whitelisted": True,
            }

        now = time.time()
        max_req, window_sec = self._get_limit_for_path(path)
        window_start = now - window_sec

        with self._lock:
            if client_ip not in self._requests:
                self._requests[client_ip] = {}

            # 获取或创建该路径的记录列表
            path_key = path or "default"
            if path_key not in self._requests[client_ip]:
                self._requests[client_ip][path_key] = []

            timestamps = self._requests[client_ip][path_key]

            # 清理窗口外的过期记录（滑动窗口核心）
            timestamps[:] = [t for t in timestamps if t > window_start]

            current_count = len(timestamps)

            if current_count >= max_req:
                # 已达上限，计算等待时间
                oldest = min(timestamps)
                retry_after = int(oldest + window_sec - now) + 1
                return False, {
                    "remaining": 0,
                    "reset_time": oldest + window_sec,
                    "retry_after": retry_after,
                    "limit": max_req,
                    "window": window_sec,
                    "current": current_count,
                }

            # 记录本次请求时间戳
            timestamps.append(now)
            remaining = max_req - len(timestamps)
            return True, {
                "remaining": remaining,
                "reset_time": now + window_sec,
                "retry_after": 0,
                "limit": max_req,
                "window": window_sec,
                "current": len(timestamps),
            }

    def cleanup_stale_ips(self):
        """清理长时间无活动的 IP 记录，释放内存"""
        now = time.time()
        max_window = max(w for _, (_, w) in self.PATH_LIMITS.items())
        stale_threshold = now - max_window * 2

        with self._lock:
            stale_ips = [
                ip for ip, paths in self._requests.items()
                if ip not in self._whitelist and
                   all(
                       not ts or max(ts) < stale_threshold
                       for ts in paths.values()
                   )
            ]
            for ip in stale_ips:
                del self._requests[ip]

    def get_stats(self) -> dict:
        """获取限流器统计信息（用于监控）"""
        with self._lock:
            return {
                "total_tracked_ips": len(self._requests),
                "whitelisted_ips": list(self._whitelist),
                "path_limits": self.PATH_LIMITS,
            }
