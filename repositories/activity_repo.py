"""活动数据访问，activities + activity_signups 表"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any, Tuple

from app.database import get_db

logger = logging.getLogger(__name__)


class ActivityRepository:
    """活动表仓库"""

    @staticmethod
    def list_activities(
        status: str = "",
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页获取活动列表，返回(列表, 总数)"""
        try:
            db = get_db()
            offset = (page - 1) * page_size
            if status:
                total_row = db.fetchone("SELECT COUNT(*) FROM activities WHERE status = ?", (status,))
                total = total_row[0]
                rows = db.fetchall(
                    "SELECT * FROM activities WHERE status = ? ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    (status, page_size, offset),
                )
            else:
                total_row = db.fetchone("SELECT COUNT(*) FROM activities")
                total = total_row[0]
                rows = db.fetchall(
                    "SELECT * FROM activities ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    (page_size, offset),
                )
            return rows, total
        except Exception as e:
            logger.error("获取活动列表失败: %s", e)
            return [], 0

    @staticmethod
    def get_activity_by_id(activity_id: str) -> Optional[Dict[str, Any]]:
        """按ID查活动详情"""
        try:
            db = get_db()
            row = db.fetchone("SELECT * FROM activities WHERE id = ?", (activity_id,))
            return dict(row) if row else None
        except Exception as e:
            logger.error("获取活动详情失败 [%s]: %s", activity_id, e)
            return None

    @staticmethod
    def get_activity_creator(activity_id: str) -> Optional[str]:
        """获取活动创建者ID"""
        try:
            db = get_db()
            row = db.fetchone("SELECT creator_id FROM activities WHERE id = ?", (activity_id,))
            return row["creator_id"] if row else None
        except Exception as e:
            logger.error("获取活动创建者失败 [%s]: %s", activity_id, e)
            return None

    @staticmethod
    def create_activity(
        title: str,
        description: str,
        cover_image: str,
        location: str,
        start_time: float,
        end_time: float,
        max_participants: int,
        creator_id: str,
        status: str = "draft",
    ) -> Optional[str]:
        """创建活动，返回活动ID"""
        try:
            db = get_db()
            activity_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.execute(
                """INSERT INTO activities (id, title, description, cover_image, location,
                   start_time, end_time, max_participants, current_participants, status, creator_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (activity_id, title, description, cover_image, location,
                 start_time, end_time, max_participants, 0, status, creator_id, now),
            )
            db.commit()
            logger.info("活动创建成功: %s (creator=%s)", activity_id, creator_id)
            return activity_id
        except Exception as e:
            logger.error("创建活动失败: %s", e)
            return None

    @staticmethod
    def update_activity(
        activity_id: str,
        title: str,
        description: str,
        cover_image: str,
        location: str,
        start_time: float,
        end_time: float,
        max_participants: int,
        status: str,
    ) -> bool:
        """更新活动信息"""
        try:
            db = get_db()
            db.execute(
                """UPDATE activities SET title=?, description=?, cover_image=?, location=?,
                   start_time=?, end_time=?, max_participants=?, status=? WHERE id=?""",
                (title, description, cover_image, location,
                 start_time, end_time, max_participants, status, activity_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("更新活动失败 [%s]: %s", activity_id, e)
            return False

    @staticmethod
    def delete_activity(activity_id: str) -> bool:
        """删除活动及其报名记录"""
        try:
            db = get_db()
            db.execute("DELETE FROM activity_signups WHERE activity_id = ?", (activity_id,))
            db.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
            db.commit()
            logger.info("活动已删除: %s", activity_id)
            return True
        except Exception as e:
            logger.error("删除活动失败 [%s]: %s", activity_id, e)
            return False

    @staticmethod
    def increment_participants(activity_id: str) -> bool:
        """参与人数+1"""
        try:
            db = get_db()
            db.execute(
                "UPDATE activities SET current_participants = current_participants + 1 WHERE id = ?",
                (activity_id,),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("增加活动参与人数失败 [%s]: %s", activity_id, e)
            return False

    @staticmethod
    def decrement_participants(activity_id: str) -> bool:
        """参与人数-1，不会减到负数"""
        try:
            db = get_db()
            db.execute(
                "UPDATE activities SET current_participants = current_participants - 1 "
                "WHERE id = ? AND current_participants > 0",
                (activity_id,),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("减少活动参与人数失败 [%s]: %s", activity_id, e)
            return False

    # 报名相关

    @staticmethod
    def check_user_signed_up(activity_id: str, user_id: str) -> bool:
        """检查用户是否已报名"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT id FROM activity_signups WHERE activity_id = ? AND user_id = ?",
                (activity_id, user_id),
            )
            return row is not None
        except Exception as e:
            logger.error("检查报名状态失败 [%s/%s]: %s", activity_id, user_id, e)
            return False

    @staticmethod
    def create_signup(activity_id: str, user_id: str) -> Optional[str]:
        """创建报名记录"""
        try:
            db = get_db()
            signup_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.execute(
                "INSERT INTO activity_signups (id, activity_id, user_id, created_at) VALUES (?,?,?,?)",
                (signup_id, activity_id, user_id, now),
            )
            db.commit()
            return signup_id
        except Exception as e:
            logger.error("创建报名记录失败 [%s/%s]: %s", activity_id, user_id, e)
            return None

    @staticmethod
    def delete_signup(activity_id: str, user_id: str) -> bool:
        """取消报名"""
        try:
            db = get_db()
            db.execute(
                "DELETE FROM activity_signups WHERE activity_id = ? AND user_id = ?",
                (activity_id, user_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("取消报名失败 [%s/%s]: %s", activity_id, user_id, e)
            return False

    # 签到核销

    @staticmethod
    def get_signup_record(activity_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取报名记录"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT id, status FROM activity_signups WHERE activity_id = ? AND user_id = ?",
                (activity_id, user_id),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询报名记录失败 [%s/%s]: %s", activity_id, user_id, e)
            return None

    @staticmethod
    def get_signup_checkin_time(signup_id: str) -> Optional[str]:
        """获取签到时间"""
        try:
            db = get_db()
            row = db.fetchone("SELECT checked_at FROM activity_signups WHERE id = ?", (signup_id,))
            return row["checked_at"] if row else None
        except Exception as e:
            logger.error("查询签到时间失败 [%s]: %s", signup_id, e)
            return None

    @staticmethod
    def mark_checked_in(signup_id: str) -> Optional[str]:
        """签到核销，返回签到时间"""
        try:
            db = get_db()
            checkin_time = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            db.execute(
                "UPDATE activity_signups SET status = 'checked_in', checked_at = ? WHERE id = ?",
                (checkin_time, signup_id),
            )
            db.commit()
            return checkin_time
        except Exception as e:
            logger.error("签到核销失败 [%s]: %s", signup_id, e)
            return None
