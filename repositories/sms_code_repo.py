"""短信验证码数据访问，sms_codes 表"""

import time
import logging
from typing import Optional, Tuple

from app.database import get_db

logger = logging.getLogger(__name__)


class SmsCodeRepository:
    """验证码表仓库"""

    @staticmethod
    def save_code(phone: str, code: str, expire_seconds: int = 300) -> bool:
        """保存验证码，同一手机号覆盖旧码"""
        try:
            db = get_db()
            expire_time = time.time() + expire_seconds
            db.execute(
                "INSERT OR REPLACE INTO sms_codes (phone, code, expire_time) VALUES (?,?,?)",
                (phone, code, expire_time),
            )
            db.commit()
            return True
        except Exception as e:
            logger.error("保存验证码失败 [phone=%s]: %s", phone, e)
            return False

    @staticmethod
    def get_code(phone: str) -> Optional[Tuple[str, float]]:
        """获取验证码，过期自动清除"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT code, expire_time FROM sms_codes WHERE phone = ?",
                (phone,),
            )
            if not row:
                return None
            if time.time() > row["expire_time"]:
                SmsCodeRepository.delete_code(phone)
                return None
            return (row["code"], row["expire_time"])
        except Exception as e:
            logger.error("查询验证码失败 [phone=%s]: %s", phone, e)
            return None

    @staticmethod
    def delete_code(phone: str) -> bool:
        """删除验证码"""
        try:
            db = get_db()
            db.execute("DELETE FROM sms_codes WHERE phone = ?", (phone,))
            db.commit()
            return True
        except Exception as e:
            logger.error("删除验证码失败 [phone=%s]: %s", phone, e)
            return False

    @staticmethod
    def clean_expired() -> int:
        """清理过期验证码，返回清理条数"""
        try:
            db = get_db()
            cursor = db.execute("DELETE FROM sms_codes WHERE expire_time < ?", (time.time(),))
            db.commit()
            return cursor.rowcount if hasattr(cursor, 'rowcount') else 0
        except Exception as e:
            logger.error("清理过期验证码失败: %s", e)
            return 0
