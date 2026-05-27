"""成就系统"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from repositories.user_repo import UserRepository
from repositories.checkin_repo import CheckinRepository
from app.database import get_db
from routers.auth import _get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/achievements", tags=["成就系统"])

ACHIEVEMENTS_FILE = Path(__file__).parent.parent / "data" / "achievements.json"


def _load_achievements():
    # 从json加载成就数据
    try:
        if ACHIEVEMENTS_FILE.exists():
            with open(ACHIEVEMENTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("achievements", [])
        return []
    except Exception as e:
        logger.error("加载成就数据失败: %s", e)
        return []


def _check_achievements(user_data: dict) -> list:
    # 检查用户已解锁的成就，跟achievements.json的condition字段对齐
    achievements = _load_achievements()
    unlocked = []

    for achievement in achievements:
        cond = achievement.get("condition") or achievement.get("conditions", {})
        cond_type = cond.get("type", "")
        is_unlocked = False

        if cond_type == "count":
            field = cond.get("field", "")
            value = cond.get("value", 0)
            if field == "total_predictions":
                is_unlocked = user_data.get("quiz_total", 0) >= value
            elif field == "quiz_correct":
                is_unlocked = user_data.get("quiz_correct", 0) >= value
            elif field == "checkin_count":
                is_unlocked = user_data.get("checkin_count", 0) >= value
            else:
                is_unlocked = user_data.get(field, 0) >= value

        elif cond_type == "streak":
            field = cond.get("field", "")
            value = cond.get("value", 0)
            if field == "checkin":
                consecutive = CheckinRepository.get_consecutive_days(user_data.get("id", ""), 30)
                is_unlocked = consecutive >= value

        elif cond_type == "total_points":
            value = cond.get("value", 0)
            is_unlocked = user_data.get("points", 0) >= value

        elif cond_type == "unique_categories":
            value = cond.get("value", 4)
            try:
                db = get_db()
                row = db.fetchone(
                    "SELECT COUNT(DISTINCT category) as cnt FROM checkins WHERE user_id = ?",
                    (user_data.get("id", ""),)
                )
                is_unlocked = (row["cnt"] if row else 0) >= value
            except Exception:
                is_unlocked = False

        if is_unlocked:
            unlocked.append(achievement)

    return unlocked


@router.get("")
async def get_achievements(request: Request):
    """获取已解锁成就"""
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
