"""IP级请求限流，滑动窗口算法"""

import time
import threading
import random
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """滑动窗口限流，按路径分级，白名单IP直接放行
    生产环境建议换Redis分布式限流
    """

    # 不同路径的限流配置：{路径前缀: (最大请求数, 时间窗口秒数)}
    PATH_LIMITS = {
        "/api/predict": (20, 60),        # 预测接口，计算密集
        "/api/batch_predict": (10, 60),   # 批量预测
        "/api/search": (30, 60),          # 搜索
        "/api/auth/": (10, 60),           # 认证，防暴力破解
        "default": (30, 60),
    }

    def __init__(self, default_max_requests: int = 30, default_window_seconds: int = 60):
        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        # { client_ip: { path_prefix: [timestamp1, timestamp2, ...] } }
        self._requests: dict[str, dict[str, list[float]]] = {}
        self._lock = threading.Lock()
        self._whitelist: set[str] = {"127.0.0.1", "::1", "localhost"}

    def add_whitelist(self, ip: str):
        self._whitelist.add(ip)

    def remove_whitelist(self, ip: str):
        self._whitelist.discard(ip)

    def _get_limit_for_path(self, path: str) -> tuple[int, int]:
        """根据路径找限流配置"""
        for prefix, limit in self.PATH_LIMITS.items():
            if prefix != "default" and path.startswith(prefix):
                return limit
        return (self.default_max_requests, self.default_window_seconds)

    def is_allowed(self, client_ip: str, path: str = "") -> tuple[bool, dict]:
        """判断请求是否放行，返回(是否允许, 限制信息)"""
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

            path_key = path or "default"
            if path_key not in self._requests[client_ip]:
                self._requests[client_ip][path_key] = []

            timestamps = self._requests[client_ip][path_key]

            # 滑动窗口核心：清掉窗口外的记录
            timestamps[:] = [t for t in timestamps if t > window_start]

            current_count = len(timestamps)

            if current_count >= max_req:
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
        """清理长时间没活动的IP记录，防内存泄漏"""
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
        """限流器统计"""
        with self._lock:
            return {
                "total_tracked_ips": len(self._requests),
                "whitelisted_ips": list(self._whitelist),
                "path_limits": self.PATH_LIMITS,
            }
