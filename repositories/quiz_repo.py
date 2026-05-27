"""知识问答数据访问，quiz_questions + quiz_records 表"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any

from app.database import get_db

logger = logging.getLogger(__name__)


class QuizRepository:
    """问答表仓库"""

    @staticmethod
    def get_all_questions() -> List[Dict[str, Any]]:
        """所有题目"""
        try:
            db = get_db()
            return db.fetchall("SELECT * FROM quiz_questions")
        except Exception as e:
            logger.error("获取题库失败: %s", e)
            return []

    @staticmethod
    def get_question_by_id(question_id: str) -> Optional[Dict[str, Any]]:
        """按ID查题目"""
        try:
            db = get_db()
            row = db.fetchone(
                "SELECT * FROM quiz_questions WHERE id = ?",
                (question_id,),
            )
            return dict(row) if row else None
        except Exception as e:
            logger.error("获取题目失败 [%s]: %s", question_id, e)
            return None

    @staticmethod
    def get_today_answered_question_ids(user_id: str) -> List[str]:
        """用户今日已答的题目ID列表"""
        try:
            db = get_db()
            today_start = time.time() - (time.time() % 86400)
            rows = db.fetchall(
                "SELECT question_id FROM quiz_records WHERE user_id = ? AND created_at > ?",
                (user_id, today_start),
            )
            return [row["question_id"] for row in rows]
        except Exception as e:
            logger.error("获取今日已答题失败 [%s]: %s", user_id, e)
            return []

    @staticmethod
    def create_record(
        user_id: str,
        question_id: str,
        selected: int,
        is_correct: bool,
        points_earned: int = 0,
    ) -> Optional[str]:
        """创建答题记录"""
        try:
            db = get_db()
            record_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.execute(
                "INSERT INTO quiz_records (id, user_id, question_id, selected, is_correct, points_earned, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (record_id, user_id, question_id, selected, int(is_correct), points_earned, now),
            )
            db.commit()
            return record_id
        except Exception as e:
            logger.error("创建答题记录失败 [%s]: %s", user_id, e)
            return None
