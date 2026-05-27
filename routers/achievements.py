"""
成就系统路由模块
包含用户已解锁成就列表接口
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from repositories.user_repo import UserRepository
from routers.auth import _get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/achievements", tags=["成就系统"])

ACHIEVEMENTS_FILE = Path(__file__).parent.parent / "data" / "achievements.json"


def _load_achievements():
    """加载成就数据"""
    try:
        if ACHIEVEMENTS_FILE.exists():
            with open(ACHIEVEMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("achievements", [])
        return []
    except Exception as e:
        logger.error("加载成就数据失败: %s", e)
        return []


def _check_achievements(user_data: dict) -> list:
    """检查用户已解锁的成就"""
    achievements = _load_achievements()
    unlocked = []

    for achievement in achievements:
        conditions = achievement.get("conditions", {})
        is_unlocked = False

        if conditions.get("min_points"):
            is_unlocked = user_data.get("points", 0) >= conditions["min_points"]
        elif conditions.get("min_checkins"):
            is_unlocked = user_data.get("checkin_count", 0) >= conditions["min_checkins"]
        elif conditions.get("min_quiz_correct"):
            is_unlocked = user_data.get("quiz_correct", 0) >= conditions["min_quiz_correct"]
        elif conditions.get("min_recognitions"):
            is_unlocked = user_data.get("quiz_total", 0) >= conditions["min_recognitions"]
        elif conditions.get("quiz_accuracy"):
            quiz_total = user_data.get("quiz_total", 0)
            quiz_correct = user_data.get("quiz_correct", 0)
            if quiz_total > 0:
                accuracy = quiz_correct / quiz_total * 100
                is_unlocked = accuracy >= conditions["quiz_accuracy"]

        if is_unlocked:
            unlocked.append(achievement)

    return unlocked


@router.get("")
async def get_achievements(request: Request):
    """获取用户已解锁的成就列表"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        user_full = UserRepository.get_user_by_id(user["id"])
        if not user_full:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "用户不存在"}})

        unlocked_achievements = _check_achievements(user_full)
        all_achievements = _load_achievements()

        return JSONResponse(content={
            "success": True,
            "achievements": unlocked_achievements,
            "total": len(unlocked_achievements),
            "total_all": len(all_achievements),
        })
    except Exception as e:
        logger.error("获取成就列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取成就列表失败"}})
