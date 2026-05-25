"""
基于 LRU + TTL 的推理结果缓存模块
从 main.py 提取为独立模块
"""

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
    """
    基于 LRU + TTL 的推理结果缓存

    使用 OrderedDict 实现最近最少使用（LRU）淘汰策略，
    配合时间戳实现自动过期（TTL）机制。
    通过图像感知哈希（phash）识别相同内容的图片，避免重复推理。

    适用场景：
    - 相同图片短时间内多次上传（用户重复操作）
    - 批量处理时包含重复图片
    - 演示/测试环境减少模型调用次数
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 86400):
        """
        初始化缓存实例

        :param max_size: 最大缓存条数（默认500，超过时淘汰最久未使用的）
        :param ttl_seconds: 缓存有效期（默认24小时=86400秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        # 使用 OrderedDict 实现 LRU：访问时移动到末尾，淘汰时移除头部
        self._cache: OrderedDict[str, dict] = OrderedDict()
        logger.info("推理缓存初始化完成 (最大容量=%d, 有效期=%d秒)", max_size, ttl_seconds)

    def _make_key(self, image_data: bytes) -> str:
        """
        使用感知哈希生成缓存键（相同内容的图片命中同一缓存）

        优先使用 imagehash 库的 phash 算法（可识别相似图片），
        若库不可用则降级为 MD5 哈希（仅能识别完全相同的图片）。

        :param image_data: 原始图片字节数据（Base64解码后）
        :return: 格式化的缓存键 "infer:{hash_value}"
        """
        try:
            # 尝试使用感知哈希算法（推荐）
            image = Image.open(BytesIO(image_data)).convert("RGB")
            phash = imagehash.phash(image, hash_size=16)  # 使用16位哈希提高精度
            cache_key = f"infer:{str(phash)}"
            return cache_key
        except Exception:
            # 降级方案：使用 MD5 哈希（无法识别相似图，但至少能缓存完全相同的图片）
            md5_hash = hashlib.md5(image_data).hexdigest()
            cache_key = f"infer:md5_{md5_hash}"
            logger.debug("imagehash 不可用，已降级为 MD5 哈希")
            return cache_key

    def get(self, key: str) -> Optional[dict]:
        """
        获取缓存数据（带TTL检查和LRU更新）

        命中时会将条目移动到末尾（标记为最近使用），
        过期则删除该条目并返回 None。

        :param key: 缓存键（由 _make_key 生成）
        :return: 缓存的推理结果字典，未命中或过期返回 None
        """
        try:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            current_time = time.time()

            # 检查是否过期
            if current_time - entry["timestamp"] > self.ttl_seconds:
                # 过期则删除并记录日志
                del self._cache[key]
                logger.info("🗑️ 缓存淘汰（过期）: %s", key[:20])
                return None

            # 命中：移动到末尾（LRU更新）
            self._cache.move_to_end(key)
            return entry["data"]

        except Exception as e:
            logger.warning("缓存读取异常: %s", e)
            return None

    def set(self, key: str, data: dict) -> None:
        """
        写入缓存数据（带容量控制）

        如果键已存在则更新数据并移动到末尾，
        如果超过最大容量则淘汰最久未使用的条目（OrderedDict 头部）。

        :param key: 缓存键
        :param data: 推理结果数据
        """
        try:
            current_time = time.time()

            if key in self._cache:
                # 已存在：更新数据和时间戳，移动到末尾
                self._cache[key] = {"data": data, "timestamp": current_time}
                self._cache.move_to_end(key)
            else:
                # 新增：检查是否超出容量
                while len(self._cache) >= self.max_size:
                    # 淘汰最久未使用的条目（OrderedDict 的第一个元素）
                    oldest_key, _ = self._cache.popitem(last=False)
                    logger.info("🗑️ 缓存淘汰（容量满）: %s", oldest_key[:20])

                # 写入新条目
                self._cache[key] = {"data": data, "timestamp": current_time}
                logger.info("💾 缓存写入: %s (当前缓存数=%d/%d)",
                           key[:20], len(self._cache), self.max_size)

        except Exception as e:
            logger.warning("缓存写入异常: %s", e)

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        logger.info("🧹 缓存已清空")

    def stats(self) -> dict:
        """获取缓存统计信息（用于监控和调试）"""
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
