"""地图打卡接口"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from repositories.disposal_point_repo import DisposalPointRepository
from repositories.checkin_repo import CheckinRepository
from repositories.user_repo import UserRepository
from app.models import CheckinRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["地图打卡"])

# 复用 auth 模块的认证辅助函数
from routers.auth import _get_current_user


# 投放点地图

@router.get("/api/map/points")
async def get_disposal_points(zone: str = "", category: str = ""):
    """获取投放点列表，支持按校区和类别过滤"""
    try:
        all_points = DisposalPointRepository.list_all()
        points = []
        for p in all_points:
            p["categories"] = json.loads(p["categories"]) if isinstance(p["categories"], str) else p["categories"]
            if zone and p.get("campus_zone") != zone:
                continue
            if category and category not in p.get("categories", []):
                continue
            points.append(p)
        return JSONResponse(content={"success": True, "points": points, "total": len(points)})
    except Exception as e:
        logger.error("获取投放点失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点失败"}})


@router.get("/api/map/point/{point_id}")
async def get_disposal_point(point_id: str):
    """获取单个投放点详情"""
    try:
        p = DisposalPointRepository.get_by_id(point_id)
        if not p:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "投放点不存在"}})
        p["categories"] = json.loads(p["categories"]) if isinstance(p["categories"], str) else p["categories"]
        return JSONResponse(content={"success": True, "point": p})
    except Exception as e:
        logger.error("获取投放点详情失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点详情失败"}})


# 环保打卡

@router.post("/api/checkin")
async def create_checkin(request: Request, req: CheckinRequest):
    """打卡，含位置校验和连续签到翻倍"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        if CheckinRepository.check_today_exists(user["id"]):
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "今日已打卡"}})

        # 位置校验：有投放点ID且提供了经纬度，检查500米内
        if req.point_id and req.lat and req.lng:
            point = DisposalPointRepository.get_by_id(req.point_id)
            if point:
                import math
                lat1, lng1 = math.radians(req.lat), math.radians(req.lng)
                lat2, lng2 = math.radians(point["lat"]), math.radians(point["lng"])
                dlat = lat2 - lat1
                dlng = lng2 - lng1
                a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlng/2)**2
                distance = 6371000 * 2 * math.asin(math.sqrt(a))
                if distance > 500:
                    return JSONResponse(status_code=400, content={
                        "success": False,
                        "error": {"code": "E400", "message": f"距离投放点{int(distance)}米，需在500米内才能打卡"}
                    })

        # 连续签到翻倍：基础5分，3天+2，7天+5，30天+10
        consecutive_days = CheckinRepository.get_consecutive_days(user["id"], 30)
        bonus_map = {3: 2, 7: 5, 30: 10}
        bonus = 0
        for threshold, extra in sorted(bonus_map.items()):
            if consecutive_days >= threshold:
                bonus = extra
        points_earned = 5 + bonus

        checkin_id = CheckinRepository.create_checkin(
            user_id=user["id"],
            point_id=req.point_id,
            lat=req.lat,
            lng=req.lng,
            category=req.category,
            photo_hash=req.photo_hash,
            points_earned=points_earned,
        )
        if not checkin_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "打卡失败"}})

        UserRepository.add_checkin_count(user["id"], points_earned)

        streak_msg = ""
        if consecutive_days > 0:
            streak_msg = f"（连续{consecutive_days + 1}天，额外+{bonus}分）"

        return JSONResponse(content={
            "success": True,
            "checkin": {"id": checkin_id, "points_earned": points_earned, "consecutive_days": consecutive_days + 1},
            "message": f"打卡成功！获得 {points_earned} 积分{streak_msg}"
        })
    except Exception as e:
        logger.error("打卡失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "打卡失败"}})


@router.get("/api/checkin/today")
async def get_today_checkin(request: Request):
    """今日打卡状态"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        row = CheckinRepository.get_today_checkin(user["id"])
        return JSONResponse(content={"success": True, "checked_in": row is not None, "checkin": row})
    except Exception as e:
        logger.error("获取打卡状态失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取打卡状态失败"}})


@router.get("/api/checkin/history")
async def get_checkin_history(request: Request, page: int = 1, page_size: int = 20):
    """打卡历史"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        records, total = CheckinRepository.get_history(user["id"], page, page_size)
        return JSONResponse(content={"success": True, "records": records, "total": total, "page": page})
    except Exception as e:
        logger.error("获取打卡历史失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取打卡历史失败"}})


# 打卡海报

@router.get("/api/checkin/poster")
async def generate_checkin_poster(request: Request, checkin_id: str = Query(...)):
    """生成打卡分享海报数据，前端用Canvas绘制"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        # 查询打卡记录
        row = CheckinRepository.get_by_id_and_user(checkin_id, user["id"])
        if not row:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "打卡记录不存在"}})

        checkin = row

        # 连续打卡天数
        consecutive_days = CheckinRepository.get_consecutive_days(user["id"], 30)

        # 总统计
        total_checkins, total_points_earned = CheckinRepository.get_user_stats(user["id"])

        # 排名
        rank = UserRepository.get_rank_by_points(user.get("points", 0))

        # 日期
        from datetime import datetime
        date_text = datetime.now().strftime("%Y年%m月%d日")

        # 根据连续天数选择不同的鼓励语
        slogans = {
            1: "🌱 环保第一步，从今天开始！",
            3: "🔥 连续3天，保持住！",
            7: "⭐ 坚持一周，你是环保达人！",
            14: "💪 半个月，习惯已成自然！",
            21: "🏆 21天养成一个环保好习惯！",
            30: "🎖️ 整月坚持，校园环保大使就是你！",
            100: "💯 百天打卡传奇！致敬你的坚持！",
        }
        closest_day = min(slogans.keys(), key=lambda d: abs(d - consecutive_days))
        slogan = slogans[closest_day]

        # 等级
        level_thresholds = [0, 50, 200, 500, 1000]
        level_names = ["环保新人", "分类达人", "绿色先锋", "环保卫士", "校园大使"]
        level_icons = ["🌱", "🌿", "🌳", "🏆", "👑"]
        user_level = 0
        for i, threshold in enumerate(level_thresholds):
            if user["points"] >= threshold:
                user_level = i

        poster_data = {
            "user": {
                "nickname": user.get("nickname") or "环保达人",
                "avatar": user.get("avatar") or "/static/images/default-avatar.png",
                "points": user.get("points", 0),
                "level": user_level,
                "level_name": level_names[user_level],
                "level_icon": level_icons[user_level],
            },
            "checkin": {
                "id": checkin["id"],
                "created_at": checkin["created_at"],
                "category": checkin.get("category", ""),
                "consecutive_days": consecutive_days,
                "points_earned": checkin.get("points_earned", 5),
            },
            "stats": {
                "total_checkins": total_checkins,
                "total_points_earned": total_points_earned,
                "rank": min(rank, 999),
                "user_points": user.get("points", 0),
            },
            "poster_config": {
                "slogan": slogan,
                "date_text": date_text,
                "app_name": "校园垃圾分类AI助手",
                "background_gradient": ["#2D9B5E", "#1a7343"],
                "accent_color": "#FFD700",
            },
        }

        return JSONResponse(content={
            "success": True,
            "poster_data": poster_data,
        })

    except Exception as e:
        logger.error("生成海报数据失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "海报生成失败"}})
