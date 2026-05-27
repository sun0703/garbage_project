"""会话数据访问层 —— 封装 sessions 表的所有数据库操作"""

import uuid
import time
import logging
from typing import Optional, Dict, Any

from app.database import get_db

logger = logging.getLogger(__name__)

SESSION_EXPIRE_SECONDS = 86400 * 7


class SessionRepository:
    """会话表静态仓库"""

    @staticmethod
    def create_session(user_id: str, expires_in: int = SESSION_EXPIRE_SECONDS) -> Optional[str]:
        """创建新会话

        Args:
            user_id:    用户 ID
            expires_in: 过期秒数，默认 7 天

        Returns:
            会话 ID 字符串，失败返回 None
        """
        try:
            db = get_db()
            session_id = uuid.uuid4().hex
            now = time.time()
            db.execute(
                "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                (session_id, user_id, now, now + expires_in),
            )
            db.commit()
            logger.info("会话创建成功: user=%s, session=%s", user_id, session_id[:8])
            return session_id
        except Exception as e:
            logger.error("创建会话失败 [user=%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_session_user_id(session_id: str) -> Optional[str]:
        """根据会话 ID 获取有效会话对应的用户 ID

        Args:
            session_id: 会话 ID

        Returns:
            用户 ID 或 None（过期/不存在）
        """
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT user_id FROM sessions WHERE id = ? AND expires_at > ?",
                (session_id, time.time()),
            )
            return row["user_id"] if row else None
        except Exception as e:
            logger.error("查询会话失败 [%s]: %s", session_id, e)
            return None

    @staticmethod
    def delete_session(session_id: str) -> bool:
        """删除指定会话（登出时调用）

        Args:
            session_id: 会话 ID

        Returns:
            成功返回 True
        """
        try:
            db = get_db()
            db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            db.commit()
            return True
        except Exception as e:
            logger.error("删除会话失败 [%s]: %s", session_id, e)
            return False

    @staticmethod
    def delete_user_sessions(user_id: str) -> bool:
        """删除用户所有会话（强制下线时调用）

        Args:
            user_id: 用户 ID

        Returns:
            成功返回 True
        """
        try:
            db = get_db()
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            db.commit()
            logger.info("用户所有会话已删除: user=%s", user_id)
            return True
        except Exception as e:
            logger.error("删除用户会话失败 [%s]: %s", user_id, e)
            return False
