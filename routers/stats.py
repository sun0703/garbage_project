"""用户统计接口"""

import logging
import time

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from repositories.user_repo import UserRepository
from repositories.checkin_repo import CheckinRepository
from routers.auth import _get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stats", tags=["用户统计"])


@router.get("/summary")
async def get_stats_summary(request: Request):
    """用户统计摘要"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        user_full = UserRepository.get_user_by_id(user["id"])
        if not user_full:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "用户不存在"}})

        rank = UserRepository.get_rank_by_points(user_full["points"])
        quiz_accuracy = 0
        if user_full.get("quiz_total", 0) > 0:
            quiz_accuracy = round(user_full["quiz_correct"] / user_full["quiz_total"] * 100, 1)

        summary = {
            "total_recognitions": user_full.get("quiz_total", 0),
            "total_predictions": user_full.get("quiz_total", 0),
            "total_checkins": user_full.get("checkin_count", 0),
            "total_points": user_full.get("points", 0),
            "current_points": user_full.get("points", 0),
            "rank": rank,
            "quiz_correct": user_full.get("quiz_correct", 0),
            "quiz_total": user_full.get("quiz_total", 0),
            "quiz_accuracy": quiz_accuracy,
            "created_at": user_full.get("created_at", 0),
        }

        # 近30天趋势，逐天查有点慢，后面加缓存
        from datetime import datetime
        from app.database import get_db
        db = get_db()
        trend_30d = []
        for i in range(29, -1, -1):
            day_start = time.time() - (i + 1) * 86400
            day_end = time.time() - i * 86400
            checkin_row = db.fetchone(
                "SELECT COUNT(*) as cnt FROM checkins WHERE user_id = ? AND created_at > ? AND created_at <= ?",
                (user["id"], day_start, day_end),
            )
            checkin_cnt = checkin_row["cnt"] if checkin_row else 0
            quiz_row = db.fetchone(
                "SELECT COUNT(*) as cnt FROM quiz_records WHERE user_id = ? AND created_at > ? AND created_at <= ?",
                (user["id"], day_start, day_end),
            )
            quiz_cnt = quiz_row["cnt"] if quiz_row else 0
            date_label = datetime.fromtimestamp(day_start).strftime("%m/%d")
            trend_30d.append({"date": date_label, "checkin": checkin_cnt, "quiz": quiz_cnt})

        summary["trend_30d"] = trend_30d

        # 积分来源分布
        transaction_distribution = {"checkin": 0, "quiz": 0, "prediction": 0}
        row = db.fetchone("SELECT SUM(points_earned) as total FROM checkins WHERE user_id = ?", (user["id"],))
        transaction_distribution["checkin"] = row["total"] if row and row.get("total") else 0
        row = db.fetchone("SELECT SUM(points_earned) as total FROM quiz_records WHERE user_id = ? AND is_correct = 1", (user["id"],))
        transaction_distribution["quiz"] = row["total"] if row and row.get("total") else 0
        summary["transaction_distribution"] = transaction_distribution

        # 识别分类分布
        category_distribution = {}
        cat_rows = db.fetchall("SELECT category, COUNT(*) as cnt FROM checkins WHERE user_id = ? AND category != '' GROUP BY category", (user["id"],))
        for row in cat_rows:
            category_distribution[row["category"]] = row["cnt"]
        summary["category_distribution"] = category_distribution

        return JSONResponse(content={"success": True, "summary": summary})
    except Exception as e:
        logger.error("获取统计数据失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取统计数据失败"}})


@router.get("/leaderboard")
async def get_leaderboard(request: Request, type: str = Query("points", description="排行榜类型：points/checkins/quiz"), limit: int = Query(10, ge=1, le=100)):
    """排行榜"""
    try:
        from app.database import get_db
        db = get_db()

        if type == "points":
            rows = db.fetchall("""
                SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total
                FROM users
                ORDER BY points DESC
                LIMIT ?
            """, (limit,))
        elif type == "checkins":
            rows = db.fetchall("""
                SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total
                FROM users
                ORDER BY checkin_count DESC
                LIMIT ?
            """, (limit,))
        elif type == "quiz":
            rows = db.fetchall("""
                SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total
                FROM users
                WHERE quiz_total > 0
                ORDER BY (CAST(quiz_correct AS REAL) / quiz_total) DESC, quiz_total DESC
                LIMIT ?
            """, (limit,))
        else:
            rows = db.fetchall("""
                SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total
                FROM users
                ORDER BY points DESC
                LIMIT ?
            """, (limit,))
        leaderboard = []
        for rank, row in enumerate(rows, 1):
            user_dict = dict(row)
            user_dict["rank"] = rank
            quiz_accuracy = 0
            if user_dict.get("quiz_total", 0) > 0:
                quiz_accuracy = round(user_dict["quiz_correct"] / user_dict["quiz_total"] * 100, 1)
            user_dict["quiz_accuracy"] = quiz_accuracy
            leaderboard.append(user_dict)

        return JSONResponse(content={"success": True, "leaderboard": leaderboard, "type": type})
    except Exception as e:
        logger.error("获取排行榜失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取排行榜失败"}})
