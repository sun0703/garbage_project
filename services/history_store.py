"""
识别历史记录存储模块（内存 + JSON文件备份）
从 main.py 提取为独立模块
"""

import json
import time
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class HistoryStore:
    """识别历史记录存储（内存 + JSON文件备份）"""

    def __init__(self, max_items: int = 200, backup_path: Path | None = None):
        self.max_items = max_items
        self._records: list[dict] = []
        self._backup_path = backup_path
        self._load_from_disk()

    def add(self, record: dict) -> str:
        record["id"] = uuid.uuid4().hex[:10]
        record["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._records.insert(0, record)
        if len(self._records) > self.max_items:
            self._records = self._records[:self.max_items]
        self._save_to_disk()
        return record["id"]

    def get_all(self, page: int = 1, page_size: int = 20) -> dict:
        total = len(self._records)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = self._records[start:end]
        return {
            "data": page_data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, (total + page_size - 1) // page_size),
            },
        }

    def delete(self, record_id: str) -> bool:
        for i, r in enumerate(self._records):
            if r.get("id") == record_id:
                self._records.pop(i)
                self._save_to_disk()
                return True
        return False

    def clear(self) -> None:
        self._records.clear()
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        if not self._backup_path:
            return
        try:
            # 只存最近100条到磁盘
            with open(self._backup_path, "w", encoding="utf-8") as f:
                json.dump(self._records[:100], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("历史记录持久化失败: %s", e)

    def _load_from_disk(self) -> None:
        if not self._backup_path or not self._backup_path.exists():
            return
        try:
            with open(self._backup_path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception as e:
            logger.warning("历史记录加载失败: %s", e)
