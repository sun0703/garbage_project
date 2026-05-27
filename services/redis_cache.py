"""Redis缓存服务，不可用时降级为内存缓存"""

import json
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_cache_instance = None


class RedisCacheService:
    """Redis缓存，挂了就降级内存缓存"""

    def __init__(self, redis_url: str, ttl_seconds: int = 86400, max_size: int = 500):
        self.ttl_seconds = ttl_seconds
        self._redis = None
        self._fallback = None
        self._using_redis = False

        try:
            import redis as redis_lib
            self._redis = redis_lib.from_url(
                redis_url,
                socket_connect_timeout=3,
                socket_timeout=3,
                decode_responses=True,
            )
            self._redis.ping()
            self._using_redis = True
            logger.info("Redis 缓存服务已连接: %s", redis_url.split("@")[-1] if "@" in redis_url else redis_url)
        except ImportError:
            logger.warning("redis 库未安装，使用内存缓存降级方案")
            self._init_fallback(max_size)
        except Exception as e:
            logger.warning("Redis 连接失败 (%s)，使用内存缓存降级方案", str(e)[:80])
            self._init_fallback(max_size)

    def _init_fallback(self, max_size: int) -> None:
        """初始化内存缓存降级"""
        from services.inference_cache import InferenceCache
        self._fallback = InferenceCache(max_size=max_size, ttl_seconds=self.ttl_seconds)
        self._using_redis = False

    def get(self, key: str) -> Optional[dict]:
        """读缓存"""
        if self._using_redis and self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.warning("Redis 读取失败，降级到内存缓存: %s", str(e)[:50])
                self._using_redis = False
                if self._fallback is None:
                    self._init_fallback(500)

        if self._fallback:
            return self._fallback.get(key)
        return None

    def set(self, key: str, data: dict, ttl: Optional[int] = None) -> None:
        """写缓存"""
        effective_ttl = ttl or self.ttl_seconds

        if self._using_redis and self._redis:
            try:
                self._redis.setex(key, effective_ttl, json.dumps(data, ensure_ascii=False))
                return
            except Exception as e:
                logger.warning("Redis 写入失败，降级到内存缓存: %s", str(e)[:50])
                self._using_redis = False
                if self._fallback is None:
                    self._init_fallback(500)

        if self._fallback:
            self._fallback.set(key, data)

    def delete(self, key: str) -> None:
        """删缓存"""
        if self._using_redis and self._redis:
            try:
                self._redis.delete(key)
                return
            except Exception:
                pass
        if self._fallback:
            self._fallback.delete(key)

    def clear(self) -> None:
        """清空ecosort:前缀的缓存"""
        if self._using_redis and self._redis:
            try:
                keys = self._redis.keys("ecosort:*")
                if keys:
                    self._redis.delete(*keys)
                logger.info("Redis 缓存已清空: %d 条", len(keys))
                return
            except Exception:
                pass
        if self._fallback:
            self._fallback.clear()

    def stats(self) -> dict:
        """缓存统计"""
        if self._using_redis and self._redis:
            try:
                info = self._redis.info("stats")
                keys_count = len(self._redis.keys("ecosort:*"))
                return {
                    "backend": "redis",
                    "total_keys": keys_count,
                    "hit_rate": info.get("keyspace_hit_rate", 0),
                    "used_memory_human": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                }
            except Exception:
                pass

        if self._fallback:
            fallback_stats = self._fallback.stats()
            fallback_stats["backend"] = "memory_fallback"
            return fallback_stats

        return {"backend": "none", "status": "unavailable"}

    @property
    def is_redis(self) -> bool:
        """当前是否用的Redis"""
        return self._using_redis


def get_cache() -> RedisCacheService:
    """获取全局缓存实例，优先Redis，不行就内存"""
    global _cache_instance
    if _cache_instance is None:
        redis_url = os.getenv("REDIS_URL", "")
        ttl = int(os.getenv("CACHE_TTL_HOURS", "24")) * 3600
        max_size = int(os.getenv("CACHE_MAX_ITEMS", "500"))

        if redis_url:
            _cache_instance = RedisCacheService(
                redis_url=redis_url,
                ttl_seconds=ttl,
                max_size=max_size,
            )
        else:
            # 没配Redis就直接用内存
            from services.inference_cache import InferenceCache
            memory_cache = InferenceCache(max_size=max_size, ttl_seconds=ttl)
            _cache_instance = RedisCacheService.__new__(RedisCacheService)
            _cache_instance._redis = None
            _cache_instance._fallback = memory_cache
            _cache_instance._using_redis = False
            _cache_instance.ttl_seconds = ttl
            logger.info("缓存服务初始化: 内存模式 (容量=%d, TTL=%dh)", max_size, ttl // 3600)

    return _cache_instance
