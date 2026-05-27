"""环保活动接口"""

import logging
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from repositories.activity_repo import ActivityRepository
from app.models import ActivitySignupRequest, ActivityCreateRequest

logger = logging.getLogger(__name__)

router = APIRouter(tags=["环保活动"])

from routers.auth import _get_current_user


@router.get("/api/activities")
async def get_activities(status: str = "", page: int = 1, page_size: int = 10):
    """活动列表"""
    try:
        activities, total = ActivityRepository.list_activities(status, page, page_size)
        for a in activities:
            a["start_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["start_time"]))
            a["end_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["end_time"]))
        return JSONResponse(content={"success": True, "activities": activities, "total": total, "page": page})
    except Exception as e:
        logger.error("获取活动列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取活动列表失败"}})


@router.get("/api/activities/{activity_id}")
async def get_activity(activity_id: str):
    """活动详情"""
    try:
        a = ActivityRepository.get_activity_by_id(activity_id)
        if not a:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})
        a["start_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["start_time"]))
        a["end_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["end_time"]))
        return JSONResponse(content={"success": True, "activity": a})
    except Exception as e:
        logger.error("获取活动详情失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取活动详情失败"}})


@router.post("/api/activities/signup")
async def signup_activity(request: Request, req: ActivitySignupRequest):
    """报名活动"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        activity = ActivityRepository.get_activity_by_id(req.activity_id)
        if not activity:
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})

        if activity["status"] != "open":
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "活动已截止报名"}})

        if activity["max_participants"] > 0 and activity["current_participants"] >= activity["max_participants"]:
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "活动名额已满"}})

        if ActivityRepository.check_user_signed_up(req.activity_id, user["id"]):
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E409", "message": "已报名该活动"}})

        signup_id = ActivityRepository.create_signup(req.activity_id, user["id"])
        if not signup_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "报名失败"}})

        ActivityRepository.increment_participants(req.activity_id)

        return JSONResponse(content={"success": True, "message": "报名成功", "signup_id": signup_id})
    except Exception as e:
        logger.error("活动报名失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "报名失败"}})


@router.get("/api/activities/{activity_id}/signed")
async def check_activity_signup(request: Request, activity_id: str):
    """检查是否已报名"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(content={"success": True, "signed_up": False})

    try:
        is_signed = ActivityRepository.check_user_signed_up(activity_id, user["id"])
        return JSONResponse(content={"success": True, "signed_up": is_signed})
    except Exception:
        return JSONResponse(content={"success": True, "signed_up": False})


@router.post("/api/activities/{activity_id}/checkin/{user_id}")
async def admin_checkin_user(activity_id: str, user_id: str, request: Request):
    """管理员签到核销"""
    current_user = _get_current_user(request)
    if not current_user:
        return JSONResponse(
            status_code=401,
            content={"success": False, "error": {"code": "E401", "message": "请先登录"}}
        )

    try:
        # 只有admin能核销
        if current_user.get("role") != "admin":
            logger.warning("⚠️ 非管理员尝试执行签到核销: user_id=%s, target_user=%s, activity=%s",
                           current_user["id"], user_id, activity_id)
            return JSONResponse(
                status_code=403,
                content={"success": False, "error": {"code": "E403", "message": "仅管理员可执行签到核销操作"}}
            )

        # 活动是否存在
        activity = ActivityRepository.get_activity_by_id(activity_id)
        if not activity:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": {"code": "E404", "message": "活动不存在"}}
            )

        # 是否已报名
        signup = ActivityRepository.get_signup_record(activity_id, user_id)
        if not signup:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": {"code": "E404", "message": "该用户未报名此活动"}}
            )

        # 已签到的不能重复签
        if signup["status"] == "checked_in":
            checkin_time = ActivityRepository.get_signup_checkin_time(signup["id"])

            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": {"code": "E409", "message": "该用户已完成签到"},
                    "checkin_time": checkin_time
                }
            )

        # 执行签到
        checkin_time = ActivityRepository.mark_checked_in(signup["id"])
        if not checkin_time:
            return JSONResponse(
                status_code=500,
                content={"success": False, "error": {"code": "E500", "message": "签到核销失败，请重试"}}
            )

        logger.info(
            "✅ 管理员签到核销成功: admin=%s, activity=%s(%s), user=%s, time=%s",
            current_user["id"],
            activity_id,
            activity["title"],
            user_id,
            checkin_time
        )

        return JSONResponse(content={
            "success": True,
            "checkin_time": checkin_time,
            "message": "签到成功"
        })

    except Exception as e:
        logger.error("❌ 管理员签到核销失败: activity=%s, user=%s, error=%s",
                     activity_id, user_id, e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E500", "message": "签到核销失败，请重试"}}
        )


@router.post("/api/activities")
async def create_activity(request: Request, req: ActivityCreateRequest):
    """管理员创建活动"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})
    try:
        if user.get("role") != "admin":
            return JSONResponse(status_code=403, content={"success": False, "error": {"code": "E403", "message": "仅管理员可发布活动"}})
        activity_id = ActivityRepository.create_activity(
            title=req.title,
            description=req.description,
            cover_image=req.cover_image,
            location=req.location,
            start_time=req.start_time,
            end_time=req.end_time,
            max_participants=req.max_participants,
            creator_id=user["id"],
            status=req.status,
        )
        if not activity_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "创建活动失败"}})
        return JSONResponse(status_code=201, content={"success": True, "activity_id": activity_id, "message": "活动创建成功"})
    except Exception as e:
        logger.error("创建活动失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "创建活动失败"}})


@router.put("/api/activities/{activity_id}")
async def update_activity(activity_id: str, request: Request, req: ActivityCreateRequest):
    """更新活动"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})
    try:
        creator_id = ActivityRepository.get_activity_creator(activity_id)
        if not creator_id:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})
        if creator_id != user["id"] and user.get("role") != "admin":
            return JSONResponse(status_code=403, content={"success": False, "error": {"code": "E403", "message": "无权修改此活动"}})
        ActivityRepository.update_activity(
            activity_id=activity_id,
            title=req.title,
            description=req.description,
            cover_image=req.cover_image,
            location=req.location,
            start_time=req.start_time,
            end_time=req.end_time,
            max_participants=req.max_participants,
            status=req.status,
        )
        return JSONResponse(content={"success": True, "message": "活动更新成功"})
    except Exception as e:
        logger.error("更新活动失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新活动失败"}})


@router.delete("/api/activities/{activity_id}")
async def delete_activity(activity_id: str, request: Request):
    """删除活动"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})
    try:
        creator_id = ActivityRepository.get_activity_creator(activity_id)
        if not creator_id:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})
        if creator_id != user["id"] and user.get("role") != "admin":
            return JSONResponse(status_code=403, content={"success": False, "error": {"code": "E403", "message": "无权删除此活动"}})
        ActivityRepository.delete_activity(activity_id)
        return JSONResponse(content={"success": True, "message": "活动已删除"})
    except Exception as e:
        logger.error("删除活动失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "删除活动失败"}})


@router.post("/api/activities/{activity_id}/cancel")
async def cancel_activity_signup(activity_id: str, request: Request):
    """取消报名"""
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})
    try:
        if not ActivityRepository.check_user_signed_up(activity_id, user["id"]):
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "未报名该活动"}})
        ActivityRepository.delete_signup(activity_id, user["id"])
        ActivityRepository.decrement_participants(activity_id)
        return JSONResponse(content={"success": True, "message": "已取消报名"})
    except Exception as e:
        logger.error("取消报名失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "操作失败"}})
