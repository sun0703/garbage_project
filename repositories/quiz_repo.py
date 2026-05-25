"""知识问答数据访问层 —— 封装 quiz_questions + quiz_records 表的数据库操作"""

import uuid
import time
import logging
from typing import Optional, List, Dict, Any

from app.db import db

logger = logging.getLogger(__name__)


class QuizRepository:
    """问答表静态仓库"""

    # ==================== 题目相关 ====================

    @staticmethod
    def get_all_questions() -> List[Dict[str, Any]]:
        """获取所有题库题目

        Returns:
            题目列表
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT * FROM quiz_questions")
            return [dict(row) for row in c.fetchall()]
        except Exception as e:
            logger.error("获取题库失败: %s", e)
            return []

    @staticmethod
    def get_question_by_id(question_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取单个题目

        Args:
            question_id: 题目 ID

        Returns:
            题目字典或 None
        """
        try:
            c = db.conn.cursor()
            c.execute("SELECT * FROM quiz_questions WHERE id = ?", (question_id,))
            row = c.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error("获取题目失败 [%s]: %s", question_id, e)
            return None

    # ==================== 答题记录相关 ====================

    @staticmethod
    def get_today_answered_question_ids(user_id: str) -> List[str]:
        """获取用户今日已答题的题目 ID 列表

        Args:
            user_id: 用户 ID

        Returns:
            题目 ID 列表
        """
        try:
            c = db.conn.cursor()
            today_start = time.time() - (time.time() % 86400)
            c.execute(
                "SELECT question_id FROM quiz_records WHERE user_id = ? AND created_at > ?",
                (user_id, today_start),
            )
            return [row["question_id"] for row in c.fetchall()]
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
        """创建答题记录

        Args:
            user_id:      用户 ID
            question_id:  题目 ID
            selected:     选择的选项索引
            is_correct:   是否正确
            points_earned: 获得积分

        Returns:
            记录 ID，失败返回 None
        """
        try:
            record_id = uuid.uuid4().hex[:12]
            now = time.time()
            db.conn.execute(
                "INSERT INTO quiz_records (id, user_id, question_id, selected, is_correct, points_earned, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (record_id, user_id, question_id, selected, int(is_correct), points_earned, now),
            )
            db.conn.commit()
            return record_id
        except Exception as e:
            logger.error("创建答题记录失败 [%s]: %s", user_id, e)
            return None
