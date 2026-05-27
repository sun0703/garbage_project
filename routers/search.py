"""搜索接口"""

import time
import logging

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app import backend_state
from services.search_engine import _PINYIN_AVAILABLE

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/search")
async def search_waste(query: str = Query(..., min_length=1, max_length=100)) -> JSONResponse:
    """模糊搜索，支持拼音"""
    if not backend_state.search_engine or not backend_state.search_engine.vocab:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E004", "message": "词库未就绪"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    results = backend_state.search_engine.search(query.strip(), top_k=3)
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
    """增强搜索，带拼音建议"""
    import re
    
    if not backend_state.search_engine or not backend_state.search_engine.vocab:
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
    
    # 输入纯字母时生成拼音搜索建议
    if include_pinyin and re.match(r'^[a-z]+$', query_stripped.lower()):
        for py_key in backend_state.search_engine._pinyin_index:
            if py_key.startswith(query_stripped.lower()) and py_key != query_stripped.lower():
                for item in backend_state.search_engine._pinyin_index[py_key][:2]:
                    suggestion = {
                        "label": item["label"],
                        "pinyin_key": py_key,
                        "category_name": item.get("category_name", ""),
                    }
                    # 去重
                    if not any(s["label"] == suggestion["label"] for s in suggestions):
                        suggestions.append(suggestion)
                    if len(suggestions) >= 8:  # 最多 8 条建议
                        break
                if len(suggestions) >= 8:
                    break
    
    # 执行搜索
    results = backend_state.search_engine.search(query_stripped, top_k=top_k)
    
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
    """获取所有类别"""
    if not backend_state.search_engine or not backend_state.search_engine.vocab:
        return JSONResponse(status_code=503, content={"success": False})

    categories_map: dict[int, dict] = {}
    for item in backend_state.search_engine.vocab:
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
