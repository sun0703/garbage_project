"""推理结果缓存，LRU+TTL，用感知哈希去重相同图片"""

import hashlib
import time
import logging
from collections import OrderedDict
from io import BytesIO
from typing import Optional

import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


class InferenceCache:
    """LRU+TTL缓存，相同内容的图片命中同一缓存"""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 86400):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, dict] = OrderedDict()
        logger.info("推理缓存初始化完成 (最大容量=%d, 有效期=%d秒)", max_size, ttl_seconds)

    def _make_key(self, image_data: bytes) -> str:
        """用感知哈希生成缓存键，相同图片命中同一缓存；不行就降级MD5"""
        try:
            image = Image.open(BytesIO(image_data)).convert("RGB")
            phash = imagehash.phash(image, hash_size=16)
            cache_key = f"infer:{str(phash)}"
            return cache_key
        except Exception:
            # imagehash挂了就用MD5兜底，虽然不能识别相似图但至少能缓存完全相同的
            md5_hash = hashlib.md5(image_data).hexdigest()
            cache_key = f"infer:md5_{md5_hash}"
            logger.debug("imagehash 不可用，已降级为 MD5 哈希")
            return cache_key

    def get(self, key: str) -> Optional[dict]:
        """读缓存，命中时更新LRU，过期就删"""
        try:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            current_time = time.time()

            if current_time - entry["timestamp"] > self.ttl_seconds:
                del self._cache[key]
                logger.info("🗑️ 缓存淘汰（过期）: %s", key[:20])
                return None

            self._cache.move_to_end(key)
            return entry["data"]

        except Exception as e:
            logger.warning("缓存读取异常: %s", e)
            return None

    def set(self, key: str, data: dict) -> None:
        """写缓存，超容量时淘汰最久未用的"""
        try:
            current_time = time.time()

            if key in self._cache:
                self._cache[key] = {"data": data, "timestamp": current_time}
                self._cache.move_to_end(key)
            else:
                while len(self._cache) >= self.max_size:
                    oldest_key, _ = self._cache.popitem(last=False)
                    logger.info("🗑️ 缓存淘汰（容量满）: %s", oldest_key[:20])

                self._cache[key] = {"data": data, "timestamp": current_time}
                logger.info("💾 缓存写入: %s (当前缓存数=%d/%d)",
                           key[:20], len(self._cache), self.max_size)

        except Exception as e:
            logger.warning("缓存写入异常: %s", e)

    def delete(self, key: str) -> bool:
        """删除指定缓存键，存在则删除并返回True，不存在返回False"""
        if key in self._cache:
            del self._cache[key]
            logger.info("🗑️ 缓存删除: %s", key[:20])
            return True
        return False

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        logger.info("🧹 缓存已清空")

    def stats(self) -> dict:
        """缓存统计"""
        current_time = time.time()
        valid_count = sum(
            1 for entry in self._cache.values()
            if current_time - entry["timestamp"] <= self.ttl_seconds
        )
        expired_count = len(self._cache) - valid_count

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "expired_entries": expired_count,
            "max_size": self.max_size,
            "utilization": round(len(self._cache) / self.max_size * 100, 2) if self.max_size > 0 else 0,
        }
