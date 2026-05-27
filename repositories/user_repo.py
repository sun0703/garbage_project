"""用户数据访问，users 表"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any

from app.database import get_db

logger = logging.getLogger(__name__)


class UserRepository:
    """用户表仓库"""

    @staticmethod
    def create_user(
        username: str,
        password_hash: str,
        nickname: str = "",
        avatar: str = "",
        oauth_provider: str = "",
        oauth_id: str = "",
        phone: str = "",
    ) -> Optional[str]:
        """创建用户，返回user_id"""
        try:
            db = get_db()
            user_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.execute(
                "INSERT INTO users (id, username, password_hash, nickname, avatar, "
                "points, checkin_count, quiz_correct, quiz_total, oauth_provider, oauth_id, phone, created_at, last_login) "
                "VALUES (?,?,?,?,?,0,0,0,0,?,?,?,?,?)",
                (user_id, username, password_hash, nickname, avatar,
                 oauth_provider, oauth_id, phone, now, now),
            )
            db.commit()
            logger.info("用户创建成功: %s", username)
            return user_id
        except Exception as e:
            logger.error("创建用户失败 [%s]: %s", username, e)
            return None

    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """按ID查用户（不含密码）"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT id, username, nickname, avatar, points, checkin_count, "
                "quiz_correct, quiz_total, oauth_provider, oauth_id, "
                "created_at, last_login FROM users WHERE id = ?",
                (user_id,),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [id=%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_user_by_id_with_password(user_id: str) -> Optional[Dict[str, Any]]:
        """按ID查用户（含密码，仅登录校验用）"""
        try:
            db = get_db()
            row = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [id=%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
        """按用户名查用户"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT * FROM users WHERE username = ?",
                (username,),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [username=%s]: %s", username, e)
            return None

    @staticmethod
    def check_username_exists(username: str) -> bool:
        """用户名是否已存在"""
        try:
            db = get_db()
            return db.fetchone("SELECT id FROM users WHERE username = ?", (username,)) is not None
        except Exception as e:
            logger.error("检查用户名存在性失败 [%s]: %s", username, e)
            return False

    @staticmethod
    def get_user_by_oauth(provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
        """按OAuth查用户"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ?",
                (provider, oauth_id),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("OAuth 查询用户失败 [%s/%s]: %s", provider, oauth_id, e)
            return None

    @staticmethod
    def update_last_login(user_id: str) -> bool:
        """更新最后登录时间"""
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (time.time(), user_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("更新最后登录时间失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def update_last_login_and_avatar(user_id: str, avatar: str) -> bool:
        """更新登录时间和头像"""
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET last_login = ?, avatar = ? WHERE id = ?",
                (time.time(), avatar, user_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("更新用户登录信息失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def add_points(user_id: str, points: int) -> bool:
        """加积分"""
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET points = points + ? WHERE id = ?",
                (points, user_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("增加用户积分失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def add_checkin_count(user_id: str, points: int = 5) -> bool:
        """打卡计数+1，积分也加"""
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET points = points + ?, checkin_count = checkin_count + 1 WHERE id = ?",
                (points, user_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("增加打卡计数失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def increment_quiz_correct(user_id: str, points: int = 3) -> bool:
        """答对：正确数+1、总数+1、加积分"""
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET points = points + ?, quiz_correct = quiz_correct + 1, quiz_total = quiz_total + 1 WHERE id = ?",
                (points, user_id),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("增加问答正确计数失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def increment_quiz_wrong(user_id: str) -> bool:
        """答错：仅总数+1"""
        try:
            db = get_db()
            db.execute(
                "UPDATE users SET quiz_total = quiz_total + 1 WHERE id = ?",
                (user_id,),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("增加问答总数失败 [%s]: %s", user_id, e)
            return False

    @staticmethod
    def get_rank_by_points(user_points: int) -> int:
        """根据积分算排名"""
        try:
            db = get_db()
            row = db.fetchone("SELECT COUNT(*) + 1 FROM users WHERE points > ?", (user_points,))
            return row["COUNT(*) + 1"] if row else 1
        except Exception as e:
            logger.error("查询排名失败: %s", e)
            return 1

    @staticmethod
    def get_user_for_session(user_id: str) -> Optional[Dict[str, Any]]:
        """会话验证时查用户简要信息"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total "
                "FROM users WHERE id = ?",
                (user_id,),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("会话查询用户失败 [%s]: %s", user_id, e)
            return None

    @staticmethod
    def get_user_by_phone(phone: str) -> Optional[Dict[str, Any]]:
        """按手机号查用户"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT id, username, nickname, avatar, points, checkin_count, "
                "quiz_correct, quiz_total, status, role, phone FROM users WHERE phone = ?",
                (phone,),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("查询用户失败 [phone=%s]: %s", phone, e)
            return None

    @staticmethod
    def check_phone_exists(phone: str) -> bool:
        """手机号是否已注册"""
        try:
            db = get_db()
            row = db.fetchone("SELECT COUNT(*) FROM users WHERE phone = ? AND phone != ''", (phone,))
            return (row["COUNT(*)"] or 0) > 0 if row else False
        except Exception as e:
            logger.error("检查手机号存在性失败 [%s]: %s", phone, e)
            return False
