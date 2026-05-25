"""活动数据访问层 —— 封装 activities + activity_signups 表的数据库操作"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any, Tuple

from db import db

logger = logging.getLogger(__name__)


class ActivityRepository:
    """活动表静态仓库 —— 管理 activities 和 activity_signups 两张表"""

    # ==================== 活动 CRUD ====================

    @staticmethod
    def list_activities(
        status: str = "",
        page: int = 1,
        page_size: int = 10,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """分页获取活动列表

        Args:
            status:    活动状态过滤，空字符串表示不过滤
            page:      页码
            page_size: 每页条数

        Returns:
            (活动列表, 总条数)
        """
        try:
            c = db.conn.cursor()
            offset = (page - 1) * page_size
            if status:
                c.execute("SELECT COUNT(*) FROM activities WHERE status = ?", (status,))
                total = c.fetchone()[0]
                c.execute(
                    "SELECT * FROM activities WHERE status = ? ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    (status, page_size, offset),
                )
            else:
                c.execute("SELECT COUNT(*) FROM activities")
                total = c.fetchone()[0]
                c.execute(
                    "SELECT * FROM activities ORDER BY start_time DESC LIMIT ? OFFSET ?",
                    (page_size, offset),
                )
            return [dict(row) for row in c.fetchall()], total
        except Exception as e:
            logger.error("获取活动列表失败: %s", e)
            return [], 0

    @staticmethod
    def get_activity_by_id(activity_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取活动详情

        Args:
            activity_id: 活动 ID

        Returns:
            活动字典或 None
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("获取活动详情失败 [%s]: %s", activity_id, e)
            return None

    @staticmethod
    def get_activity_creator(activity_id: str) -> Optional[str]:
        """获取活动的创建者 ID

        Args:
            activity_id: 活动 ID

        Returns:
            创建者用户 ID 或 None
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT creator_id FROM activities WHERE id = ?", (activity_id,))
            row = c.fetchone()
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
        """创建活动

        Args:
            title:            活动标题
            description:      活动描述
            cover_image:      封面图 URL
            location:         活动地点
            start_time:       开始时间 (Unix 时间戳)
            end_time:         结束时间 (Unix 时间戳)
            max_participants: 最大参与人数
            creator_id:       创建者用户 ID
            status:           活动状态

        Returns:
            活动 ID，失败返回 None
        """
        try:
            activity_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.conn.execute(
                """INSERT INTO activities (id, title, description, cover_image, location,
                   start_time, end_time, max_participants, current_participants, status, creator_id, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (activity_id, title, description, cover_image, location,
                 start_time, end_time, max_participants, 0, status, creator_id, now),
            )
            db.conn.commit()
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
        """更新活动信息

        Args:
            activity_id:      活动 ID
            title:            活动标题
            description:      活动描述
            cover_image:      封面图 URL
            location:         活动地点
            start_time:       开始时间
            end_time:         结束时间
            max_participants: 最大参与人数
            status:           活动状态

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                """UPDATE activities SET title=?, description=?, cover_image=?, location=?,
                   start_time=?, end_time=?, max_participants=?, status=? WHERE id=?""",
                (title, description, cover_image, location,
                 start_time, end_time, max_participants, status, activity_id),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("更新活动失败 [%s]: %s", activity_id, e)
            return False

    @staticmethod
    def delete_activity(activity_id: str) -> bool:
        """删除活动及其所有报名记录

        Args:
            activity_id: 活动 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute("DELETE FROM activity_signups WHERE activity_id = ?", (activity_id,))
            db.conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))
            db.conn.commit()
            logger.info("活动已删除: %s", activity_id)
            return True
        except Exception as e:
            logger.error("删除活动失败 [%s]: %s", activity_id, e)
            return False

    @staticmethod
    def increment_participants(activity_id: str) -> bool:
        """报名成功后，活动参与人数 +1

        Args:
            activity_id: 活动 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE activities SET current_participants = current_participants + 1 WHERE id = ?",
                (activity_id,),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("增加活动参与人数失败 [%s]: %s", activity_id, e)
            return False

    @staticmethod
    def decrement_participants(activity_id: str) -> bool:
        """取消报名后，活动参与人数 -1

        Args:
            activity_id: 活动 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE activities SET current_participants = current_participants - 1 "
                "WHERE id = ? AND current_participants > 0",
                (activity_id,),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("减少活动参与人数失败 [%s]: %s", activity_id, e)
            return False

    # ==================== 报名相关 ====================

    @staticmethod
    def check_user_signed_up(activity_id: str, user_id: str) -> bool:
        """检查用户是否已报名指定活动

        Args:
            activity_id: 活动 ID
            user_id:     用户 ID

        Returns:
            已报名返回 True
        """
        try:
            c = db.conn.cursor()
            c.execute(
                "SELECT id FROM activity_signups WHERE activity_id = ? AND user_id = ?",
                (activity_id, user_id),
            )
            return c.fetchone() is not None
        except Exception as e:
            logger.error("检查报名状态失败 [%s/%s]: %s", activity_id, user_id, e)
            return False

    @staticmethod
    def create_signup(activity_id: str, user_id: str) -> Optional[str]:
        """创建活动报名记录

        Args:
            activity_id: 活动 ID
            user_id:     用户 ID

        Returns:
            报名记录 ID，失败返回 None
        """
        try:
            signup_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.conn.execute(
                "INSERT INTO activity_signups (id, activity_id, user_id, created_at) VALUES (?,?,?,?)",
                (signup_id, activity_id, user_id, now),
            )
            db.conn.commit()
            return signup_id
        except Exception as e:
            logger.error("创建报名记录失败 [%s/%s]: %s", activity_id, user_id, e)
            return None

    @staticmethod
    def delete_signup(activity_id: str, user_id: str) -> bool:
        """取消活动报名

        Args:
            activity_id: 活动 ID
            user_id:     用户 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "DELETE FROM activity_signups WHERE activity_id = ? AND user_id = ?",
                (activity_id, user_id),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("取消报名失败 [%s/%s]: %s", activity_id, user_id, e)
            return False

    # ==================== 签到核销相关 ====================

    @staticmethod
    def get_signup_record(activity_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户对指定活动的报名记录（含 status 和 checked_at）

        Args:
            activity_id: 活动 ID
            user_id:     用户 ID

        Returns:
            报名记录字典（id, status, checked_at）或 None
        """
        try:
            c = db.conn.cursor()
            c.execute(
                "SELECT id, status FROM activity_signups WHERE activity_id = ? AND user_id = ?",
                (activity_id, user_id),
            )
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询报名记录失败 [%s/%s]: %s", activity_id, user_id, e)
            return None

    @staticmethod
    def get_signup_checkin_time(signup_id: str) -> Optional[str]:
        """获取报名记录的签到时间

        Args:
            signup_id: 报名记录 ID

        Returns:
            签到时间字符串或 None
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT checked_at FROM activity_signups WHERE id = ?", (signup_id,))
            row = c.fetchone()
            return row["checked_at"] if row else None
        except Exception as e:
            logger.error("查询签到时间失败 [%s]: %s", signup_id, e)
            return None

    @staticmethod
    def mark_checked_in(signup_id: str) -> Optional[str]:
        """执行签到核销：更新报名状态为 checked_in，记录签到时间

        Args:
            signup_id: 报名记录 ID

        Returns:
            签到时间字符串，失败返回 None
        """
        try:
            checkin_time = time.strftime("%Y-%m-%dT%H:%M:%SZ")
            db.conn.execute(
                "UPDATE activity_signups SET status = 'checked_in', checked_at = ? WHERE id = ?",
                (checkin_time, signup_id),
            )
            db.conn.commit()
            return checkin_time
        except Exception as e:
            logger.error("签到核销失败 [%s]: %s", signup_id, e)
            return None
