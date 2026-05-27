"""
历史记录路由模块

提供识别历史的分页查询、单条删除和清空接口。
依赖 history_store 全局单例（通过 backend_state 获取）。
"""

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
import time

from app import backend_state

router = APIRouter()


@router.get("/api/history")
async def get_history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)) -> JSONResponse:
    """获取识别历史记录（分页）"""
    if not backend_state.history_store:
        return JSONResponse(content={
            "success": True,
            "data": [],
            "pagination": {"total": 0, "page": page, "page_size": page_size, "total_pages": 0},
        })

    result = backend_state.history_store.get_all(page=page, page_size=page_size)
    result["success"] = True
    return JSONResponse(content=result)


@router.delete("/api/history/{record_id}")
async def delete_history(record_id: str) -> JSONResponse:
    """删除单条历史记录"""
    if not backend_state.history_store:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "记录不存在"}},
        )

    deleted = backend_state.history_store.delete(record_id)
    if deleted:
        return JSONResponse(content={"success": True, "message": "已删除"})
    return JSONResponse(
        status_code=404,
        content={"success": False, "error": {"code": "E004", "message": "记录不存在"}},
    )


@router.delete("/api/history")
async def clear_history() -> JSONResponse:
    """清空全部历史记录"""
    if not backend_state.history_store:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "无历史记录"}},
        )
    backend_state.history_store.clear()
    return JSONResponse(content={"success": True, "message": "已清空全部历史记录"})


@router.get("/api/points/history")
async def get_points_history(request: Request, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)):
    """获取用户积分变动历史"""
    from routers.auth import _get_current_user

    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        from app.db import db

        c = db.conn.cursor()
        offset = (page - 1) * page_size

        # 统计两个表的联合总记录数（与下方UNION ALL查询保持一致）
        c.execute("""
            SELECT COUNT(*) as count FROM (
                SELECT id FROM checkins WHERE user_id = ?
                UNION ALL
                SELECT id FROM quiz_records WHERE user_id = ? AND is_correct = 1
            ) AS combined
        """, (user["id"], user["id"]))
        total_count = c.fetchone()["count"]

        c.execute("""
            SELECT 'checkin' as type, id, points_earned as points, category as reason, created_at
            FROM checkins
            WHERE user_id = ?
            UNION ALL
            SELECT 'quiz' as type, id, points_earned as points, '答对题目' as reason, created_at
            FROM quiz_records
            WHERE user_id = ? AND is_correct = 1
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (user["id"], user["id"], page_size, offset))
        rows = c.fetchall()

        history = []
        for row in rows:
            item = dict(row)
            item["created_at_iso"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item["created_at"]))
            history.append(item)

        total_pages = (total_count + page_size - 1) // page_size

        return JSONResponse(content={
            "success": True,
            "history": history,
            "pagination": {
                "total": total_count,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        })
    except Exception as e:
        import logging
        logging.error("获取积分历史失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取积分历史失败"}})
