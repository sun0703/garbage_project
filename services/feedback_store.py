"""
用户反馈存储模块（内存 + JSON文件追加）
从 main.py 提取为独立模块
"""

import json
import time
import uuid
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FeedbackStore:
    """用户反馈存储（内存 + JSON文件追加）"""

    def __init__(self, backup_path: Path | None = None):
        self._records: list[dict] = []
        self._backup_path = backup_path
        self._load_from_disk()

    def add(self, feedback: dict) -> str:
        feedback["feedback_id"] = f"fb_{uuid.uuid4().hex[:8]}"
        feedback["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._records.append(feedback)
        self._save_to_disk()
        return feedback["feedback_id"]

    def get_all(self) -> list[dict]:
        return list(self._records)

    def _save_to_disk(self) -> None:
        if not self._backup_path:
            return
        try:
            with open(self._backup_path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("反馈记录持久化失败: %s", e)

    def _load_from_disk(self) -> None:
        if not self._backup_path or not self._backup_path.exists():
            return
        try:
            with open(self._backup_path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception as e:
            logger.warning("反馈记录加载失败: %s", e)
