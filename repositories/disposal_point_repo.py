"""投放点数据访问，disposal_points 表"""

import logging
from typing import Optional, List, Dict, Any

from app.database import get_db

logger = logging.getLogger(__name__)


class DisposalPointRepository:
    """投放点表仓库"""

    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        """所有投放点"""
        try:
            db = get_db()
            return db.fetchall("SELECT * FROM disposal_points")
        except Exception as e:
            logger.error("获取投放点列表失败: %s", e)
            return []

    @staticmethod
    def get_by_id(point_id: str) -> Optional[Dict[str, Any]]:
        """按ID查投放点"""
        try:
            db = get_db()
            row = db.fetchone("SELECT * FROM disposal_points WHERE id = ?", (point_id,))
            return dict(row) if row else None
        except Exception as e:
            logger.error("获取投放点详情失败 [%s]: %s", point_id, e)
            return None
