"""
历史记录路由模块

提供识别历史的分页查询、单条删除和清空接口。
依赖 history_store 全局单例（通过 backend_state 获取）。
"""

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

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
