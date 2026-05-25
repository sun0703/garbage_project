"""
知识问答路由模块
包含每日问答题目获取、答题提交等接口
"""

import json
import logging
import random
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from repositories.quiz_repo import QuizRepository
from repositories.user_repo import UserRepository
from models import QuizAnswerRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["知识问答"])

from routers.auth import _get_current_user


@router.get("/api/quiz/daily")
async def get_daily_quiz(request: Request):
    """获取每日问答题目（未答过的题目中随机一题）"""
    user = _get_current_user(request)

    try:
        all_questions = QuizRepository.get_all_questions()

        if user:
            answered = QuizRepository.get_today_answered_question_ids(user["id"])
        else:
            answered = []

        unanswered = [q for q in all_questions if q["id"] not in answered]
        if not unanswered:
            return JSONResponse(content={"success": True, "quiz": None, "message": "今日题目已全部完成"})

        quiz = random.choice(unanswered)
        quiz["options"] = json.loads(quiz["options"]) if isinstance(quiz["options"], str) else quiz["options"]
        return JSONResponse(content={"success": True, "quiz": quiz})
    except Exception as e:
        logger.error("获取每日问答失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取问答失败"}})


@router.post("/api/quiz/answer")
async def answer_quiz(request: Request, req: QuizAnswerRequest):
    """提交答题答案"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        question = QuizRepository.get_question_by_id(req.question_id)
        if not question:
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E404", "message": "题目不存在"}})

        is_correct = req.selected == question["answer"]
        points_earned = 3 if is_correct else 0

        QuizRepository.create_record(
            user_id=user["id"],
            question_id=req.question_id,
            selected=req.selected,
            is_correct=is_correct,
            points_earned=points_earned,
        )

        if is_correct:
            UserRepository.increment_quiz_correct(user["id"], points_earned)
        else:
            UserRepository.increment_quiz_wrong(user["id"])

        options = json.loads(question["options"]) if isinstance(question["options"], str) else question["options"]
        return JSONResponse(content={
            "success": True,
            "result": {
                "is_correct": is_correct,
                "correct_answer": question["answer"],
                "explanation": question["explanation"],
                "points_earned": points_earned,
                "options": options
            }
        })
    except Exception as e:
        logger.error("回答问答失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "提交答案失败"}})
