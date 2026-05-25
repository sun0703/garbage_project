"""用户数据访问层 —— 封装 users 表的所有数据库操作"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any

from app.db import db

logger = logging.getLogger(__name__)


class UserRepository:
    """用户表静态仓库 —— 所有方法通过 db.conn 直接操作 sqlite3"""

    @staticmethod
    def create_user(
        username: str,
        password_hash: str,
        nickname: str = "",
        avatar: str = "",
        oauth_provider: str = "",
        oauth_id: str = "",
    ) -> Optional[str]:
        """创建普通用户，返回 user_id；失败返回 None

        Args:
            username:     用户名
            password_hash: SHA-256 哈希后的密码
            nickname:     昵称
            avatar:       头像 URL
            oauth_provider: OAuth 提供商
            oauth_id:      OAuth 用户 ID

        Returns:
            成功返回 user_id(str)，失败返回 None
        """
        try:
            user_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.conn.execute(
                "INSERT INTO users (id, username, password_hash, nickname, avatar, "
                "points, checkin_count, quiz_correct, quiz_total, oauth_provider, oauth_id, created_at, last_login) "
                "VALUES (?,?,?,?,?,0,0,0,0,?,?,?,?)",
                (user_id, username, password_hash, nickname, avatar,
                 oauth_provider, oauth_id, now, now),
            )
            db.conn.commit()
            logger.info("用户创建成功: %s", username)
            return user_id
        except Exception as e:
            logger.error("创建用户失败 [%s]: %s", username, e)
            return None

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """根据用户 ID 查询用户（不含 password_hash）

        Args:
            user_id: 用户 ID

        Returns:
            用户字典或 None
        """
        try:
            c = db.conn.cursor()
            c.execute(
                "SELECT id, username, nickname, avatar, points, checkin_count, "
                "quiz_correct, quiz_total, oauth_provider, oauth_id, "
                "created_at, last_login FROM users WHERE id = ?",
                (user_id,),
            )
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [id=%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_user_by_id_with_password(user_id: str) -> Optional[Dict[str, Any]]:
        """根据用户 ID 查询用户（含 password_hash，仅用于登录校验）

        Args:
            user_id: 用户 ID

        Returns:
            用户字典（含 password_hash）或 None
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [id=%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """根据用户名查询用户（含 password_hash）

        Args:
            username: 用户名

        Returns:
            用户字典或 None
        """
        try:
            c = db.conn.cursor()
            c.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            )
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [username=%s]: %s", username, e)
            return None

    @staticmethod
    def check_username_exists(username: str) -> bool:
        """检查用户名是否已存在

        Args:
            username: 用户名

        Returns:
            存在返回 True，否则 False
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT id FROM users WHERE username = ?", (username,))
            return c.fetchone() is not None
        except Exception as e:
            logger.error("检查用户名存在性失败 [%s]: %s", username, e)
            return False

    @staticmethod
    def get_user_by_oauth(provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
        """根据 OAuth 提供商和 ID 查询用户

        Args:
            provider: OAuth 提供商（如 'github'）
            oauth_id: OAuth 用户唯一标识

        Returns:
            用户字典或 None
        """
        try:
            c = db.conn.cursor()
            c.execute(
                "SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ?",
                (provider, oauth_id),
            )
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("OAuth 查询用户失败 [%s/%s]: %s", provider, oauth_id, e)
            return None

    @staticmethod
    def update_last_login(user_id: str) -> bool:
        """更新用户最后登录时间

        Args:
            user_id: 用户 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (time.time(), user_id),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("更新最后登录时间失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def update_last_login_and_avatar(user_id: str, avatar: str) -> bool:
        """更新用户最后登录时间与头像

        Args:
            user_id: 用户 ID
            avatar:  头像 URL

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE users SET last_login = ?, avatar = ? WHERE id = ?",
                (time.time(), avatar, user_id),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("更新用户登录信息失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def add_points(user_id: str, points: int) -> bool:
        """为用户增加积分

        Args:
            user_id: 用户 ID
            points:  增加的积分数

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE users SET points = points + ? WHERE id = ?",
                (points, user_id),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("增加用户积分失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def add_checkin_count(user_id: str) -> bool:
        """用户打卡计数 +1，积分 +5

        Args:
            user_id: 用户 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE users SET points = points + 5, checkin_count = checkin_count + 1 WHERE id = ?",
                (user_id,),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("增加打卡计数失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def increment_quiz_correct(user_id: str, points: int = 3) -> bool:
        """问答答对：正确数 +1、总数 +1、积分增加

        Args:
            user_id: 用户 ID
            points:  增加积分数

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE users SET points = points + ?, quiz_correct = quiz_correct + 1, quiz_total = quiz_total + 1 WHERE id = ?",
                (points, user_id),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("增加问答正确计数失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def increment_quiz_wrong(user_id: str) -> bool:
        """问答答错：仅总数 +1

        Args:
            user_id: 用户 ID

        Returns:
            成功返回 True
        """
        try:
            db.conn.execute(
                "UPDATE users SET quiz_total = quiz_total + 1 WHERE id = ?",
                (user_id,),
            )
            db.conn.commit()
            return True
        except Exception as e:
            logger.error("增加问答总数失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def get_rank_by_points(user_points: int) -> int:
        """根据积分计算排名（积分高于当前值的用户数 + 1）

        Args:
            user_points: 当前用户积分

        Returns:
            排名（从 1 开始）
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT COUNT(*) + 1 FROM users WHERE points > ?", (user_points,))
            row = c.fetchone()
            return row[0] if row else 1
        except Exception as e:
            logger.error("查询排名失败: %s", e)
            return 1

    @staticmethod
    def get_user_for_session(user_id: str) -> Optional[Dict[str, Any]]:
        """会话验证时查询用户简要信息（不含敏感字段）

        Args:
            user_id: 用户 ID

        Returns:
            用户字典（id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total）或 None
        """
        try:
            c = db.conn.cursor()
            c.execute(
                "SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total "
                "FROM users WHERE id = ?",
                (user_id,),
            )
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("会话查询用户失败 [%s]: %s", user_id, e)
            return None
