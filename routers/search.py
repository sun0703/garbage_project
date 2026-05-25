"""
搜索相关路由模块

提供模糊搜索、增强搜索和类别查询接口。
依赖 search_engine 全局单例（通过 backend_state 获取）。
"""

import time
import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend_state import search_engine
from services.search_engine import _PINYIN_AVAILABLE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/search")
async def search_waste(query: str = Query(..., min_length=1, max_length=100)) -> JSONResponse:
    """模糊搜索接口（支持拼音首字母搜索）"""
    if not search_engine or not search_engine.vocab:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E004", "message": "词库未就绪"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    results = search_engine.search(query.strip(), top_k=3)
    return JSONResponse(
        content={
            "success": True,
            "query": query,
            "results": results,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )


@router.get("/api/search/enhanced")
async def search_enhanced(
    query: str = Query(..., min_length=1, max_length=100),
    include_pinyin: bool = Query(True, description="是否启用拼音搜索"),
    top_k: int = Query(5, ge=1, le=20, description="返回结果数量")
) -> JSONResponse:
    """
    增强搜索接口（需求 F-2.2.1 扩展）
    
    相比标准 /api/search 接口，增强版提供：
    - 可控的拼音搜索开关
    - 搜索建议（基于拼音前缀的候选词）
    - 更丰富的结果元数据
    
    Args:
        query: 搜索关键词
        include_pinyin: 是否启用拼音首字母搜索（默认 True）
        top_k: 返回结果数量上限（默认 5）
        
    Returns:
        JSON 格式的搜索结果和建议列表
    """
    import re
    
    if not search_engine or not search_engine.vocab:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E004", "message": "词库未就绪"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
    
    query_stripped = query.strip()
    suggestions = []
    
    # 生成拼音搜索建议（当输入为纯字母时）
    if include_pinyin and re.match(r'^[a-z]+$', query_stripped.lower()):
        # 收集所有以查询为前缀的拼音键对应的标签作为建议
        for py_key in search_engine._pinyin_index:
            if py_key.startswith(query_stripped.lower()) and py_key != query_stripped.lower():
                for item in search_engine._pinyin_index[py_key][:2]:  # 每个键最多取 2 个建议
                    suggestion = {
                        "label": item["label"],
                        "pinyin_key": py_key,
                        "category_name": item.get("category_name", ""),
                    }
                    # 建议去重
                    if not any(s["label"] == suggestion["label"] for s in suggestions):
                        suggestions.append(suggestion)
                    if len(suggestions) >= 8:  # 最多 8 条建议
                        break
                if len(suggestions) >= 8:
                    break
    
    # 执行搜索
    results = search_engine.search(query_stripped, top_k=top_k)
    
    return JSONResponse(
        content={
            "success": True,
            "query": query,
            "results": results,
            "suggestions": suggestions[:8],
            "pinyin_enabled": include_pinyin and _PINYIN_AVAILABLE,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
    )


@router.get("/api/categories")
async def get_categories() -> JSONResponse:
    """获取所有类别信息"""
    if not search_engine or not search_engine.vocab:
        return JSONResponse(status_code=503, content={"success": False})

    categories_map: dict[int, dict] = {}
    for item in search_engine.vocab:
        cat_id = item["category_id"]
        if cat_id not in categories_map:
            categories_map[cat_id] = {
                "id": cat_id,
                "name": item["category_name"],
                "color": item.get("bin_color", ""),
                "icon": item.get("bin_icon", ""),
                "examples": [],
            }
        categories_map[cat_id]["examples"].append(item["label"])

    return JSONResponse(
        content={
            "success": True,
            "categories": sorted(categories_map.values(), key=lambda x: x["id"]),
        }
    )
