"""打卡数据访问，checkins 表"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any, Tuple

from app.database import get_db

logger = logging.getLogger(__name__)


class CheckinRepository:
    """打卡表仓库"""

    @staticmethod
    def check_today_exists(user_id: str) -> bool:
        """今天是否已打卡"""
        try:
            db = get_db()
            today_start = time.time() - (time.time() % 86400)
            row = db.fetchone(
                "SELECT id FROM checkins WHERE user_id = ? AND created_at > ?",
                (user_id, today_start),
            )
            return row is not None
        except Exception as e:
            logger.error("检查今日打卡失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def create_checkin(
        user_id: str,
        point_id: str = "",
        lat: float = 0,
        lng: float = 0,
        category: str = "",
        points_earned: int = 5,
        photo_hash: str = "",
    ) -> Optional[str]:
        """创建打卡记录"""
        try:
            db = get_db()
            checkin_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.execute(
                "INSERT INTO checkins (id, user_id, point_id, lat, lng, category, points_earned, photo_hash, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (checkin_id, user_id, point_id, lat, lng, category, points_earned, photo_hash, now),
            )
            db.commit()
            return checkin_id
        except Exception as e:
            logger.error("创建打卡记录失败 [%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_today_checkin(user_id: str) -> Optional[Dict[str, Any]]:
        """获取今日打卡记录"""
        try:
            db = get_db()
            today_start = time.time() - (time.time() % 86400)
            row = db.fetchone(
                "SELECT * FROM checkins WHERE user_id = ? AND created_at > ?",
                (user_id, today_start),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("获取今日打卡状态失败 [%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_history(
        user_id: str, page: int = 1, page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页获取打卡历史"""
        try:
            db = get_db()
            offset = (page - 1) * page_size
            count_row = db.fetchone("SELECT COUNT(*) as cnt FROM checkins WHERE user_id = ?", (user_id,))
            total = int(count_row["cnt"]) if count_row else 0
            records = db.fetchall(
                "SELECT * FROM checkins WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (user_id, page_size, offset),
            )
            return records, total
        except Exception as e:
            logger.error("获取打卡历史失败 [%s]: %s", user_id, e)
            return [], 0

    @staticmethod
    def get_by_id_and_user(checkin_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """按ID+用户查打卡记录"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT * FROM checkins WHERE id = ? AND user_id = ?",
                (checkin_id, user_id),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询打卡记录失败 [%s/%s]: %s", checkin_id, user_id, e)
            return None

    @staticmethod
    def get_consecutive_days(user_id: str, lookback_days: int = 30) -> int:
        """连续打卡天数，从今天往前数，断签就停"""
        try:
            db = get_db()
            consecutive = 0
            now = time.time()
            today_start = now - (now % 86400) + 8 * 3600  # UTC+8

            for i in range(lookback_days):
                day_start = today_start - i * 86400
                day_end = day_start + 86400
                row = db.fetchone(
                    "SELECT COUNT(*) as cnt FROM checkins WHERE user_id = ? AND created_at >= ? AND created_at < ?",
                    (user_id, day_start, day_end),
                )
                if row and row["cnt"] > 0:
                    consecutive += 1
                else:
                    break
            return consecutive
        except Exception as e:
            logger.error("计算连续打卡天数失败 [%s]: %s", user_id, e)
            return 0

    @staticmethod
    def get_user_stats(user_id: str) -> Tuple[int, int]:
        """用户打卡统计：(总次数, 总积分)"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT COUNT(*) as total_cnt, SUM(points_earned) as total_points FROM checkins WHERE user_id = ?",
                (user_id,),
            )
            total_checkins = int(row["total_cnt"]) if row and row["total_cnt"] is not None else 0
            total_points_earned = int(row["total_points"]) if row and row["total_points"] is not None else 0
            return total_checkins, total_points_earned
        except Exception as e:
            logger.error("获取打卡统计失败 [%s]: %s", user_id, e)
            return 0, 0
