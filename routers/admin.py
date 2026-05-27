"""
管理后台路由模块
包含管理员登录、仪表盘统计、用户管理、内容管理、投放点管理、模型管理和活动管理接口
"""

import hashlib
import json
import logging
import os
import secrets
import string
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db import db
from routers.auth import _get_current_user, SESSION_COOKIE_NAME

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["管理后台"])

ADMIN_SESSION_COOKIE_NAME = "admin_session_id"
ADMIN_SESSION_EXPIRE_SECONDS = 86400


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class UserStatusRequest(BaseModel):
    status: str


class UserRoleRequest(BaseModel):
    role: str


class VocabularyItemRequest(BaseModel):
    label: str
    category: str = ""
    category_id: int = 0
    category_name: str = ""
    aliases: list = []
    guidance: str = ""
    yolo_label: str = ""


class VocabularyRequest(BaseModel):
    items: list


class CategoryRequest(BaseModel):
    categories: list


class DisposalPointRequest(BaseModel):
    name: str
    lat: float
    lng: float
    address: str = ""
    categories: list = []
    campus_zone: str = ""
    is_indoor: bool = False


class DisposalPointUpdateRequest(BaseModel):
    name: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None
    categories: Optional[list] = None
    campus_zone: Optional[str] = None
    is_indoor: Optional[bool] = None


class ModelSwitchRequest(BaseModel):
    model_id: str


class ConfusingPairRequest(BaseModel):
    """易错物品对创建请求模型"""
    item_a_name: str
    item_a_category: str
    item_a_reason: str
    item_b_name: str
    item_b_category: str
    item_b_reason: str
    key_difference: str
    frequency: str = "medium"
    scene: str = ""
    tags: list[str] = []


class ActivityUpdateRequest(BaseModel):
    """活动更新请求模型"""
    title: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    max_participants: Optional[int] = None
    points_reward: Optional[int] = None
    status: Optional[str] = None


class ActivityCreateRequest(BaseModel):
    """活动创建请求模型"""
    title: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    max_participants: Optional[int] = None
    points_reward: Optional[int] = None
    status: Optional[str] = "open"


def _hash_admin_password(password: str) -> str:
    """对管理员密码进行 SHA-256 哈希"""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_admin_session(request: Request):
    """从请求 Cookie 中获取当前登录的管理员信息"""
    session_id = request.cookies.get(ADMIN_SESSION_COOKIE_NAME)
    if not session_id:
        return None
    try:
        c = db.conn.cursor()
        c.execute("""
            SELECT session_id, admin_username, created_at, expires_at
            FROM admin_sessions
            WHERE session_id = ? AND expires_at > ?
        """, (session_id, time.time()))
        row = c.fetchone()
        if row:
            return dict(row)
        return None
    except Exception as e:
        logger.error("管理员会话查询失败: %s", e)
        return None


def _create_admin_session(username: str) -> str:
    """创建管理员会话，返回 session_id"""
    try:
        session_id = uuid.uuid4().hex
        now = time.time()
        expires_at = now + ADMIN_SESSION_EXPIRE_SECONDS
        db.conn.execute("""
            INSERT INTO admin_sessions (session_id, admin_username, created_at, expires_at)
            VALUES (?, ?, ?, ?)
        """, (session_id, username, now, expires_at))
        db.conn.commit()
        return session_id
    except Exception as e:
        logger.error("创建管理员会话失败: %s", e)
        return None


def _require_admin(request: Request):
    """验证管理员权限"""
    admin = _get_admin_session(request)
    if not admin:
        return None
    return admin


def _init_admin_tables():
    """初始化管理员相关表"""
    try:
        c = db.conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                display_name TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_sessions (
                session_id TEXT PRIMARY KEY,
                admin_username TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS admin_points_history (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                points_change INTEGER NOT NULL,
                reason TEXT DEFAULT '',
                created_at REAL NOT NULL
            )
        """)
        db.conn.commit()
        _seed_default_admin()
        logger.info("管理员表初始化完成")
    except Exception as e:
        logger.error("初始化管理员表失败: %s", e)


def _generate_strong_password(length=16):
    """生成强随机密码，包含大小写字母、数字和特殊字符"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    return password


def _seed_default_admin():
    """创建默认管理员账户（密码从环境变量读取或自动生成强密码）"""
    try:
        c = db.conn.cursor()
        c.execute("SELECT username FROM admin_users WHERE username = ?", ("admin",))
        if not c.fetchone():
            # 优先从环境变量读取密码，否则生成随机强密码
            default_password = os.environ.get("ADMIN_DEFAULT_PASSWORD")
            if not default_password:
                default_password = _generate_strong_password()
                logger.warning(
                    "未设置环境变量 ADMIN_DEFAULT_PASSWORD，已自动生成默认管理员密码: %s "
                    "请登录后立即修改密码",
                    default_password
                )
            else:
                logger.info("使用环境变量配置的默认管理员密码")

            password_hash = _hash_admin_password(default_password)
            now = time.time()
            db.conn.execute("""
                INSERT INTO admin_users (username, password_hash, display_name, created_at)
                VALUES (?, ?, ?, ?)
            """, ("admin", password_hash, "系统管理员", now))
            db.conn.commit()
            logger.info("默认管理员账户已创建")
    except Exception as e:
        logger.error("创建默认管理员失败: %s", e)


_init_admin_tables()


@router.post("/login")
async def admin_login(req: AdminLoginRequest, response: Response):
    """管理员登录"""
    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM admin_users WHERE username = ?", (req.username,))
        row = c.fetchone()

        if not row or row["password_hash"] != _hash_admin_password(req.password):
            return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "用户名或密码错误"}})

        session_id = _create_admin_session(req.username)
        if not session_id:
            return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "登录失败"}})

        resp = JSONResponse(content={"success": True, "message": "登录成功", "data": {"user": {"username": req.username}}})
        resp.set_cookie(ADMIN_SESSION_COOKIE_NAME, session_id, max_age=ADMIN_SESSION_EXPIRE_SECONDS, httponly=True, samesite="lax")
        return resp
    except Exception as e:
        logger.error("管理员登录失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "登录失败"}})


@router.get("/check")
async def admin_check(request: Request):
    """检查管理员登录状态"""
    admin = _get_admin_session(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "未登录"}})
    return JSONResponse(content={"success": True, "username": admin["admin_username"]})


@router.get("/stats/dashboard")
async def get_dashboard_stats(request: Request):
    """获取仪表盘统计数据（含趋势、分类分布、热门物品）"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()

        c.execute("SELECT COUNT(*) as count FROM users")
        total_users = c.fetchone()["count"]

        c.execute("SELECT COUNT(*) as count FROM checkins")
        total_checkins = c.fetchone()["count"]

        c.execute("SELECT COUNT(*) as count FROM activities WHERE status = 'open'")
        active_activities = c.fetchone()["count"]

        c.execute("SELECT COUNT(*) as count FROM activity_signups")
        total_signups = c.fetchone()["count"]

        c.execute("SELECT SUM(points) as total FROM users")
        total_points = c.fetchone()["total"] or 0

        c.execute("SELECT COUNT(*) as count FROM feedback")
        total_feedback = c.fetchone()["count"]

        c.execute("""
            SELECT COUNT(*) as count FROM checkins
            WHERE created_at > ?
        """, (time.time() - 86400,))
        today_checkins = c.fetchone()["count"]

        c.execute("""
            SELECT COUNT(*) as count FROM users
            WHERE created_at > ?
        """, (time.time() - 86400,))
        today_new_users = c.fetchone()["count"]

        # 今日活跃用户（DAU）
        c.execute("""
            SELECT COUNT(DISTINCT user_id) as count FROM checkins
            WHERE created_at > ?
        """, (time.time() - 86400,))
        dau = c.fetchone()["count"]

        # 近30天活跃趋势
        daily_trend = []
        for i in range(29, -1, -1):
            day_start = time.time() - (i + 1) * 86400
            day_end = time.time() - i * 86400
            c.execute("""
                SELECT COUNT(DISTINCT user_id) as cnt FROM checkins
                WHERE created_at > ? AND created_at <= ?
            """, (day_start, day_end))
            cnt = c.fetchone()["cnt"]
            from datetime import datetime
            date_label = datetime.fromtimestamp(day_start).strftime("%m/%d")
            daily_trend.append({"date": date_label, "count": cnt})

        # 识别分类分布（从打卡记录的 category 字段统计）
        category_distribution = {}
        c.execute("SELECT category, COUNT(*) as cnt FROM checkins WHERE category != '' GROUP BY category")
        for row in c.fetchall():
            category_distribution[row["category"]] = row["cnt"]

        # 热门识别物品 TOP10（从打卡记录统计）
        c.execute("""
            SELECT category, COUNT(*) as cnt FROM checkins
            WHERE category != ''
            GROUP BY category
            ORDER BY cnt DESC
            LIMIT 10
        """)
        hot_items = [{"name": row["category"], "count": row["cnt"]} for row in c.fetchall()]

        dashboard = {
            "total_users": total_users,
            "total_checkins": total_checkins,
            "active_activities": active_activities,
            "total_signups": total_signups,
            "total_points": total_points,
            "total_feedback": total_feedback,
            "today_checkins": today_checkins,
            "today_new_users": today_new_users,
            "dau": dau,
            "active_users": dau,
            "today_recognitions": today_checkins,
            "daily_trend": daily_trend,
            "trend": daily_trend,
            "category_distribution": category_distribution,
            "category_dist": category_distribution,
            "hot_items": hot_items,
            "popular_items": hot_items,
        }

        return JSONResponse(content={"success": True, "dashboard": dashboard})
    except Exception as e:
        logger.error("获取仪表盘数据失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取数据失败"}})


@router.get("/users")
async def get_admin_users(request: Request, page: int = Query(1, ge=1), search: str = "", role: str = ""):
    """获取用户列表（分页）"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        offset = (page - 1) * 20

        where_clauses = []
        params = []

        if search:
            where_clauses.append("(username LIKE ? OR nickname LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        if role:
            where_clauses.append("role = ?")
            params.append(role)

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        c.execute(f"SELECT COUNT(*) as count FROM users {where_sql}", params)
        total = c.fetchone()["count"]

        c.execute(f"""
            SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total, created_at, last_login, status, role
            FROM users
            {where_sql}
            ORDER BY created_at DESC
            LIMIT 20 OFFSET ?
        """, (*params, offset))
        rows = c.fetchall()

        users = [dict(row) for row in rows]

        return JSONResponse(content={"success": True, "users": users, "total": total, "page": page})
    except Exception as e:
        logger.error("获取用户列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取用户列表失败"}})


@router.put("/users/{user_id}/status")
async def update_user_status(request: Request, user_id: str, req: UserStatusRequest):
    """更新用户状态"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "用户不存在"}})

        db.conn.execute("UPDATE users SET status = ? WHERE id = ?", (req.status, user_id))
        db.conn.commit()

        return JSONResponse(content={"success": True, "message": "状态已更新"})
    except Exception as e:
        logger.error("更新用户状态失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新失败"}})


@router.put("/users/{user_id}/role")
async def update_user_role(request: Request, user_id: str, req: UserRoleRequest):
    """更新用户角色"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not c.fetchone():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "用户不存在"}})

        db.conn.execute("UPDATE users SET role = ? WHERE id = ?", (req.role, user_id))
        db.conn.commit()

        return JSONResponse(content={"success": True, "message": "角色已更新"})
    except Exception as e:
        logger.error("更新用户角色失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新失败"}})


@router.get("/content/vocabulary")
async def get_vocabulary(request: Request):
    """获取词汇表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        vocabulary_file = Path(__file__).parent.parent / "data" / "waste.json"
        if vocabulary_file.exists():
            with open(vocabulary_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return JSONResponse(content={"success": True, "vocabulary": data})
        return JSONResponse(content={"success": True, "vocabulary": {}})
    except Exception as e:
        logger.error("获取词汇表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取词汇表失败"}})


@router.put("/content/vocabulary")
async def update_vocabulary(request: Request, req: VocabularyRequest):
    """更新词汇表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        vocabulary_file = Path(__file__).parent.parent / "data" / "waste.json"
        with open(vocabulary_file, "w", encoding="utf-8") as f:
            json.dump(req.items, f, ensure_ascii=False, indent=2)

        return JSONResponse(content={"success": True, "message": "词汇表已更新"})
    except Exception as e:
        logger.error("更新词汇表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新词汇表失败"}})


@router.post("/content/vocabulary/item")
async def add_vocabulary_item(request: Request, req: VocabularyItemRequest):
    """新增词条"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        vocabulary_file = Path(__file__).parent.parent / "data" / "waste.json"
        if vocabulary_file.exists():
            with open(vocabulary_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"items": []}

        items = data.get("items", [])
        # 检查是否已存在同名词条
        for item in items:
            if item.get("label") == req.label:
                return JSONResponse(status_code=409, content={"success": False, "error": {"code": "E409", "message": f"词条 '{req.label}' 已存在"}})

        new_item = {
            "label": req.label,
            "category": req.category,
            "category_id": req.category_id,
            "category_name": req.category_name or req.category,
            "aliases": req.aliases,
            "guidance": req.guidance,
            "yolo_label": req.yolo_label,
        }
        items.append(new_item)
        data["items"] = items

        with open(vocabulary_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return JSONResponse(status_code=201, content={"success": True, "message": "词条已添加", "item": new_item})
    except Exception as e:
        logger.error("新增词条失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "新增词条失败"}})


@router.delete("/content/vocabulary/item/{label}")
async def delete_vocabulary_item(request: Request, label: str):
    """删除词条"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        vocabulary_file = Path(__file__).parent.parent / "data" / "waste.json"
        if not vocabulary_file.exists():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "词库文件不存在"}})

        with open(vocabulary_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        original_count = len(items)
        items = [item for item in items if item.get("label") != label]

        if len(items) == original_count:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": f"词条 '{label}' 不存在"}})

        data["items"] = items
        with open(vocabulary_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return JSONResponse(content={"success": True, "message": f"词条 '{label}' 已删除"})
    except Exception as e:
        logger.error("删除词条失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "删除词条失败"}})


@router.get("/content/categories")
async def get_categories(request: Request):
    """获取分类列表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        categories_file = Path(__file__).parent.parent / "data" / "guide_standard.json"
        if categories_file.exists():
            with open(categories_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return JSONResponse(content={"success": True, "categories": data})
        return JSONResponse(content={"success": True, "categories": []})
    except Exception as e:
        logger.error("获取分类列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取分类列表失败"}})


@router.put("/content/categories")
async def update_categories(request: Request, req: CategoryRequest):
    """更新分类列表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        categories_file = Path(__file__).parent.parent / "data" / "guide_standard.json"
        with open(categories_file, "w", encoding="utf-8") as f:
            json.dump(req.categories, f, ensure_ascii=False, indent=2)

        return JSONResponse(content={"success": True, "message": "分类列表已更新"})
    except Exception as e:
        logger.error("更新分类列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新分类列表失败"}})


@router.get("/content/confusing")
async def get_confusing_pairs(request: Request):
    """获取易错物品对列表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        confusing_file = Path(__file__).parent.parent / "data" / "confusing_pairs.json"
        if confusing_file.exists():
            with open(confusing_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                pairs = data.get("pairs", [])
                return JSONResponse(content={"success": True, "pairs": pairs})
        return JSONResponse(content={"success": True, "pairs": []})
    except Exception as e:
        logger.error("获取易错物品对失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取易错物品对失败"}})


@router.post("/content/confusing")
async def add_confusing_pair(request: Request, req: ConfusingPairRequest):
    """新增易错物品对"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        confusing_file = Path(__file__).parent.parent / "data" / "confusing_pairs.json"
        if confusing_file.exists():
            with open(confusing_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {"version": "1.0", "description": "校园垃圾分类易混淆物品对比数据", "pairs": []}

        pairs = data.get("pairs", [])
        # 生成新ID：取现有最大ID + 1
        new_id = max((p.get("id", 0) for p in pairs), default=0) + 1

        new_pair = {
            "id": new_id,
            "item_a": {
                "name": req.item_a_name,
                "category": req.item_a_category,
                "reason": req.item_a_reason,
            },
            "item_b": {
                "name": req.item_b_name,
                "category": req.item_b_category,
                "reason": req.item_b_reason,
            },
            "key_difference": req.key_difference,
            "frequency": req.frequency,
            "scene": req.scene,
            "tags": req.tags,
        }
        pairs.append(new_pair)
        data["pairs"] = pairs

        with open(confusing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return JSONResponse(status_code=201, content={"success": True, "message": "易错物品对已添加", "pair": new_pair})
    except Exception as e:
        logger.error("新增易错物品对失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "新增易错物品对失败"}})


@router.delete("/content/confusing/{pair_id}")
async def delete_confusing_pair(request: Request, pair_id: int):
    """删除指定ID的易错物品对"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        confusing_file = Path(__file__).parent.parent / "data" / "confusing_pairs.json"
        if not confusing_file.exists():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "易错物品对文件不存在"}})

        with open(confusing_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        pairs = data.get("pairs", [])
        original_count = len(pairs)
        # 按 id 字段过滤删除
        pairs = [p for p in pairs if p.get("id") != pair_id]

        if len(pairs) == original_count:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": f"易错物品对 ID={pair_id} 不存在"}})

        data["pairs"] = pairs
        with open(confusing_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return JSONResponse(content={"success": True, "message": f"易错物品对 ID={pair_id} 已删除"})
    except Exception as e:
        logger.error("删除易错物品对失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "删除易错物品对失败"}})


@router.get("/points")
async def get_admin_points(request: Request):
    """获取投放点列表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM disposal_points ORDER BY created_at DESC")
        rows = c.fetchall()

        points = []
        for row in rows:
            point_dict = dict(row)
            if point_dict.get("categories"):
                point_dict["categories"] = json.loads(point_dict["categories"])
            points.append(point_dict)

        return JSONResponse(content={"success": True, "points": points})
    except Exception as e:
        logger.error("获取投放点列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点列表失败"}})


@router.post("/points")
async def create_point(request: Request, req: DisposalPointRequest):
    """创建投放点"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        point_id = uuid.uuid4().hex[:12]
        now = time.time()

        db.conn.execute("""
            INSERT INTO disposal_points (id, name, lat, lng, address, categories, campus_zone, is_indoor, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (point_id, req.name, req.lat, req.lng, req.address, json.dumps(req.categories, ensure_ascii=False), req.campus_zone, 1 if req.is_indoor else 0, now))
        db.conn.commit()

        return JSONResponse(status_code=201, content={"success": True, "point_id": point_id, "message": "投放点创建成功"})
    except Exception as e:
        logger.error("创建投放点失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "创建投放点失败"}})


@router.put("/points/{point_id}")
async def update_point(request: Request, point_id: str, req: DisposalPointUpdateRequest):
    """更新投放点"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT id FROM disposal_points WHERE id = ?", (point_id,))
        if not c.fetchone():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "投放点不存在"}})

        updates = []
        params = []

        if req.name is not None:
            updates.append("name = ?")
            params.append(req.name)
        if req.lat is not None:
            updates.append("lat = ?")
            params.append(req.lat)
        if req.lng is not None:
            updates.append("lng = ?")
            params.append(req.lng)
        if req.address is not None:
            updates.append("address = ?")
            params.append(req.address)
        if req.categories is not None:
            updates.append("categories = ?")
            params.append(json.dumps(req.categories, ensure_ascii=False))
        if req.campus_zone is not None:
            updates.append("campus_zone = ?")
            params.append(req.campus_zone)
        if req.is_indoor is not None:
            updates.append("is_indoor = ?")
            params.append(1 if req.is_indoor else 0)

        if updates:
            params.append(point_id)
            db.conn.execute(f"UPDATE disposal_points SET {', '.join(updates)} WHERE id = ?", params)
            db.conn.commit()

        return JSONResponse(content={"success": True, "message": "投放点已更新"})
    except Exception as e:
        logger.error("更新投放点失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新投放点失败"}})


@router.delete("/points/{point_id}")
async def delete_point(request: Request, point_id: str):
    """删除投放点"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT id FROM disposal_points WHERE id = ?", (point_id,))
        if not c.fetchone():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "投放点不存在"}})

        db.conn.execute("DELETE FROM disposal_points WHERE id = ?", (point_id,))
        db.conn.commit()

        return JSONResponse(content={"success": True, "message": "投放点已删除"})
    except Exception as e:
        logger.error("删除投放点失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "删除投放点失败"}})


@router.get("/models")
async def get_models(request: Request):
    """获取模型列表（动态扫描模型目录）"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        models_dir = Path(__file__).parent.parent / "models"
        available_models = []

        if models_dir.exists():
            for model_file in sorted(models_dir.glob("*.pt")):
                model_name = model_file.stem
                size_mb = round(model_file.stat().st_size / (1024 * 1024), 1)
                is_active = False
                try:
                    from services.vision_engine import VisionEngine
                    ve = VisionEngine()
                    if ve._model_path and str(model_file) == str(ve._model_path):
                        is_active = True
                except Exception:
                    pass

                available_models.append({
                    "id": model_name,
                    "name": f"YOLOv8-{model_name}",
                    "filename": model_file.name,
                    "size_mb": size_mb,
                    "status": "active" if is_active else "available",
                    "path": str(model_file),
                })

        if not available_models:
            from app import backend_state
            available_models = [
                {"id": "default", "name": "默认模型", "status": "active" if backend_state.multimodal_available else "inactive", "filename": "", "size_mb": 0, "path": ""},
                {"id": "yolov8n", "name": "YOLOv8n", "status": "available", "filename": "yolov8n.pt", "size_mb": 6.2, "path": "models/yolov8n.pt"},
                {"id": "yolov8s", "name": "YOLOv8s", "status": "available", "filename": "yolov8s.pt", "size_mb": 22.5, "path": "models/yolov8s.pt"},
                {"id": "yolov8m", "name": "YOLOv8m", "status": "available", "filename": "yolov8m.pt", "size_mb": 52.0, "path": "models/yolov8m.pt"},
            ]

        return JSONResponse(content={"success": True, "models": available_models})
    except Exception as e:
        logger.error("获取模型列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取模型列表失败"}})


@router.put("/models/{model_id}/switch")
async def switch_model(request: Request, model_id: str, req: ModelSwitchRequest):
    """切换模型（实际加载新模型）"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        models_dir = Path(__file__).parent.parent / "models"
        model_file = models_dir / f"{model_id}.pt"

        if not model_file.exists():
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": f"模型文件 {model_id}.pt 不存在"}})

        from services.vision_engine import VisionEngine
        ve = VisionEngine()
        ve.load_model(str(model_file))

        return JSONResponse(content={"success": True, "message": f"已切换到模型 {model_id}"})
    except Exception as e:
        logger.error("切换模型失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": f"切换模型失败: {str(e)}"}})


@router.get("/models/badcases")
async def get_badcases(request: Request):
    """获取Badcase列表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        badcase_file = Path(__file__).parent.parent / "data" / "badcases.json"
        if badcase_file.exists():
            with open(badcase_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                badcases = data if isinstance(data, list) else data.get("badcases", [])
                return JSONResponse(content={"success": True, "badcases": badcases})
        return JSONResponse(content={"success": True, "badcases": []})
    except Exception as e:
        logger.error("获取Badcase列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取Badcase列表失败"}})


@router.delete("/models/badcases/{badcase_id}")
async def delete_badcase(request: Request, badcase_id: str):
    """删除Badcase"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        badcase_file = Path(__file__).parent.parent / "data" / "badcases.json"

        # 文件不存在时直接返回成功（幂等操作）
        if not badcase_file.exists():
            return JSONResponse(content={"success": True, "message": "Badcase已删除"})

        with open(badcase_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 兼容两种数据格式：列表或字典
        badcases = data if isinstance(data, list) else data.get("badcases", [])

        original_count = len(badcases)
        # 过滤掉指定ID的badcase记录
        badcases = [item for item in badcases if str(item.get("id", "")) != str(badcase_id)]

        # 验证是否实际删除了记录
        if len(badcases) == original_count:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": {"code": "E404", "message": "未找到指定的Badcase记录"}}
            )

        # 保存更新后的数据
        if isinstance(data, list):
            updated_data = badcases
        else:
            updated_data = data
            updated_data["badcases"] = badcases

        with open(badcase_file, "w", encoding="utf-8") as f:
            json.dump(updated_data, f, ensure_ascii=False, indent=2)

        return JSONResponse(content={"success": True, "message": "Badcase已删除"})
    except Exception as e:
        logger.error("删除Badcase失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "删除Badcase失败"}})


@router.post("/activities")
async def admin_create_activity(request: Request, req: ActivityCreateRequest):
    """创建活动"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        from repositories.activity_repo import ActivityRepository

        activity_id = ActivityRepository.create_activity(
            title=req.title,
            description=req.description or "",
            cover_image=req.cover_image or "",
            location=req.location or "",
            start_time=req.start_time or 0,
            end_time=req.end_time or 0,
            max_participants=req.max_participants or 0,
            status=req.status or "open",
            creator_id=admin.get("id", ""),
        )

        return JSONResponse(status_code=201, content={"success": True, "message": "活动已创建", "activity_id": activity_id})
    except Exception as e:
        logger.error("创建活动失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "创建活动失败"}})


@router.get("/activities/{activity_id}/signups")
async def get_activity_signups(request: Request, activity_id: str):
    """获取活动报名列表"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        from repositories.activity_repo import ActivityRepository

        activity = ActivityRepository.get_activity_by_id(activity_id)
        if not activity:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})

        c = db.conn.cursor()
        c.execute("""
            SELECT s.id, s.user_id, s.created_at, u.username, u.nickname, u.avatar
            FROM activity_signups s
            JOIN users u ON s.user_id = u.id
            WHERE s.activity_id = ?
            ORDER BY s.created_at DESC
        """, (activity_id,))
        rows = c.fetchall()

        signups = []
        for row in rows:
            signup_dict = dict(row)
            signup_dict["created_at_iso"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(signup_dict["created_at"]))
            signups.append(signup_dict)

        return JSONResponse(content={"success": True, "signups": signups, "total": len(signups)})
    except Exception as e:
        logger.error("获取活动报名列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取报名列表失败"}})


@router.put("/activities/{activity_id}")
async def admin_update_activity(request: Request, activity_id: str, req: ActivityUpdateRequest):
    """更新活动"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        from repositories.activity_repo import ActivityRepository

        activity = ActivityRepository.get_activity_by_id(activity_id)
        if not activity:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})

        # 使用Pydantic模型提供的字段，未传的字段保持原值
        update_data = {
            "activity_id": activity_id,
            "title": req.title if req.title is not None else activity["title"],
            "description": req.description if req.description is not None else activity.get("description", ""),
            "cover_image": req.cover_image if req.cover_image is not None else activity.get("cover_image", ""),
            "location": req.location if req.location is not None else activity.get("location", ""),
            "start_time": req.start_time if req.start_time is not None else activity["start_time"],
            "end_time": req.end_time if req.end_time is not None else activity["end_time"],
            "max_participants": req.max_participants if req.max_participants is not None else activity["max_participants"],
            "status": req.status if req.status is not None else activity.get("status", "open"),
        }

        ActivityRepository.update_activity(**update_data)

        return JSONResponse(content={"success": True, "message": "活动已更新"})
    except Exception as e:
        logger.error("更新活动失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "更新活动失败"}})


@router.delete("/activities/{activity_id}")
async def admin_delete_activity(request: Request, activity_id: str):
    """删除活动"""
    admin = _require_admin(request)
    if not admin:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        from repositories.activity_repo import ActivityRepository

        activity = ActivityRepository.get_activity_by_id(activity_id)
        if not activity:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})

        ActivityRepository.delete_activity(activity_id)
        return JSONResponse(content={"success": True, "message": "活动已删除"})
    except Exception as e:
        logger.error("删除活动失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "删除活动失败"}})
