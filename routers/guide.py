"""分类指南接口"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.constants import BASE_DIR
from utils.json_loader import load_json_data
from utils.response import success_response, error_response
from app import backend_state

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/guide/standard")
async def get_guide_standard() -> JSONResponse:
    """获取校园垃圾分类标准"""
    data = load_json_data(BASE_DIR / "data" / "guide_standard.json")
    if data is None:
        return error_response("E004", "分类标准数据文件不存在", 404)

    try:
        return JSONResponse(content={
            "success": True,
            "categories": data.get("categories", []),
            "version": data.get("version", "1.0"),
        })
    except Exception as e:
        logger.error("[GuideAPI] 读取分类标准数据失败: %s", e)
        return error_response("E003", "读取分类标准数据失败", 500)


@router.get("/api/guide/category/{category_id}")
async def get_guide_category(category_id: int) -> JSONResponse:
    """获取单个类别详情"""
    if category_id not in (0, 1, 2, 3):
        return error_response("E001", "类别ID必须为0-3", 400)

    data = load_json_data(BASE_DIR / "data" / "guide_standard.json")
    if data is None:
        return error_response("E004", "分类标准数据文件不存在", 404)

    try:
        for cat in data.get("categories", []):
            if cat.get("id") == category_id:
                items_in_category = backend_state.search_engine.get_items_by_category(category_id) if backend_state.search_engine else []
                cat["vocab_items"] = [
                    {"label": item["label"], "aliases": item.get("aliases", []), "guidance": item.get("guidance", "")}
                    for item in items_in_category
                ]
                return JSONResponse(content={"success": True, "category": cat})

        return error_response("E004", f"未找到类别 {category_id}", 404)
    except Exception as e:
        logger.error("[GuideAPI] 读取分类标准数据失败: %s", e)
        return error_response("E003", "读取分类标准数据失败", 500)


@router.get("/api/guide/confusing")
async def get_confusing_pairs(limit: int = 10, frequency: str = "") -> JSONResponse:
    """易混淆物品对比"""
    data = load_json_data(BASE_DIR / "data" / "confusing_pairs.json")
    if data is None:
        return error_response("E004", "易混淆数据文件不存在", 404)

    try:
        pairs = data.get("pairs", [])
        if frequency:
            pairs = [p for p in pairs if p.get("frequency") == frequency]
        pairs = sorted(pairs, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("frequency", "medium"), 2))
        total = len(pairs)
        pairs = pairs[:limit]
        return JSONResponse(content={"success": True, "pairs": pairs, "total": total})
    except Exception as e:
        logger.error("[GuideAPI] 读取易混淆数据失败: %s", e)
        return error_response("E003", "读取易混淆数据失败", 500)


@router.get("/api/guide/confusing/{pair_id}")
async def get_confusing_pair(pair_id: int) -> JSONResponse:
    # 单个易混淆对比详情
    data = load_json_data(BASE_DIR / "data" / "confusing_pairs.json")
    if data is None:
        return error_response("E004", "易混淆数据文件不存在", 404)

    try:
        for pair in data.get("pairs", []):
            if pair.get("id") == pair_id:
                return JSONResponse(content={"success": True, "pair": pair})

        return error_response("E004", f"未找到对比组 {pair_id}", 404)
    except Exception as e:
        logger.error("[GuideAPI] 读取易混淆数据失败: %s", e)
        return error_response("E003", "读取易混淆数据失败", 500)


@router.get("/api/guide/item/{keyword}")
async def get_guide_item(keyword: str) -> JSONResponse:
    """物品详情，含处理步骤、相关物品、易错对比"""
    if not backend_state.search_engine:
        return JSONResponse(status_code=503, content={"success": False})

    results = backend_state.search_engine.search(keyword, top_k=1)
    if not results:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": f"未找到物品 '{keyword}'"}}
        )

    item = results[0]

    # 处理步骤和提示
    disposal_steps = []
    disposal_tips = []
    steps_data = load_json_data(BASE_DIR / "data" / "disposal_steps.json")
    if steps_data:
        try:
            label = item.get("label", "")
            label_steps = steps_data.get("steps", {}).get(label)
            if label_steps:
                disposal_steps = label_steps.get("disposal_steps", [])
                disposal_tips = label_steps.get("tips", [])
        except Exception:
            pass

    # 同类物品，最多6个
    same_category = [
        {"label": i["label"], "guidance": i.get("guidance", "")}
        for i in backend_state.search_engine.vocab
        if i.get("category_id") == item.get("category_id") and i["label"] != item["label"]
    ][:6]

    confusing_pairs = []
    pairs_data = load_json_data(BASE_DIR / "data" / "confusing_pairs.json")
    if pairs_data:
        try:
            keyword_lower = keyword.lower()
            for pair in pairs_data.get("pairs", []):
                tags = [t.lower() for t in pair.get("tags", [])]
                item_names = [pair["item_a"]["name"].lower(), pair["item_b"]["name"].lower()]
                if keyword_lower in item_names or any(keyword_lower in t for t in tags):
                    confusing_pairs.append(pair)
        except Exception:
            pass

    return JSONResponse(content={
        "success": True,
        "item": item,
        "disposal_steps": disposal_steps,
        "disposal_tips": disposal_tips,
        "related_items": same_category,
        "confusing_pairs": confusing_pairs,
    })
