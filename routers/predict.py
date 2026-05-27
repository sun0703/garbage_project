"""
预测相关路由模块
图像识别、多模态融合预测、批量预测、健康检查等接口
"""

import logging
import time
import uuid
import traceback
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.constants import GARBAGE_40CLASSES, WASTE_CATEGORIES, INDEX_HTML_PATH
from app import backend_state
from app.models import PredictRequest, BatchPredictRequest
from utils.image import decode_base64_image
from services.image_analyzer import ImageFeatureAnalyzer
from services.garbage_utils import _calibrate_confidence_40class, _get_class_info, _get_disposal_tips

logger = logging.getLogger(__name__)

router = APIRouter(tags=["预测识别"])


@router.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """根路径：返回前端页面"""
    html_path = Path(INDEX_HTML_PATH)
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>前端页面未找到</h1>", status_code=404)


@router.post("/api/predict")
async def predict_waste(request: PredictRequest) -> JSONResponse:
    """图像分类识别接口

    支持智能演示模式、图像特征分析、分阶段耗时记录。
    """
    start_time = time.time()
    timing = {"preprocess_ms": 0, "inference_ms": 0, "postprocess_ms": 0}

    try:
        image, image_data = decode_base64_image(request.image)
        timing["preprocess_ms"] = int((time.time() - start_time) * 1000)
        logger.info("图片解码成功，尺寸: %s (预处理耗时=%dms)", image.size, timing["preprocess_ms"])

        if backend_state.inference_cache:
            try:
                cache_key = backend_state.inference_cache._make_key(image_data)
                cached_result = backend_state.inference_cache.get(cache_key)
                if cached_result:
                    total_ms = int((time.time() - start_time) * 1000)
                    req_id = uuid.uuid4().hex[:12]
                    logger.info("缓存命中: %s (响应时间=%dms)", cache_key[:20], total_ms)
                    return JSONResponse(content={
                        "success": True,
                        "result": cached_result,
                        "inference_time_ms": total_ms,
                        "timing": {"preprocess_ms": timing["preprocess_ms"], "inference_ms": 0, "postprocess_ms": 0, "cache_hit": True},
                        "request_id": req_id,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "cache_hit": True,
                    })
            except Exception as e:
                logger.warning("缓存检查异常，将执行正常推理: %s", e)
    except ValueError as e:
        logger.error("图片格式错误: %s", e)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "图片格式无效"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
    except Exception as e:
        logger.error("图片解码异常: %s", e)
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "图片解码失败，请检查图片数据格式"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    if not backend_state.vision_engine or not backend_state.vision_engine.is_loaded:
        logger.error("模型未就绪")
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E002", "message": "模型未就绪"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    try:
        inference_start = time.time()
        result = backend_state.vision_engine.predict(image)
        timing["inference_ms"] = int((time.time() - inference_start) * 1000)

        postprocess_start = time.time()
        inference_ms = int((time.time() - start_time) * 1000)
        req_id = uuid.uuid4().hex[:12]

        # 40类专用模型直接使用YOLO结果；COCO/通用模型使用混合策略
        if backend_state.vision_engine.is_pt_model and backend_state.vision_engine.num_classes >= 40:
            original_class_id = result.get("original_class_id", -1)

            if original_class_id in GARBAGE_40CLASSES:
                class_mapping = GARBAGE_40CLASSES[original_class_id]
                category_4class = class_mapping["category"]
                class_name_cn = class_mapping["name_cn"]

                # 置信度校准
                raw_confidence = result.get("confidence", 0.0)
                adjusted_confidence = _calibrate_confidence_40class(
                    raw_confidence,
                    original_class_id,
                    len(result.get("detections", [])),
                    result.get("is_demo_mode", False)
                )

                result["class_index"] = category_4class
                result["original_class_name"] = class_name_cn
                result["confidence"] = round(adjusted_confidence, 4)
                result["reasoning"] = f"YOLOv8-40类模型: {class_name_cn} -> {WASTE_CATEGORIES[category_4class]['name']} (原始={raw_confidence:.1%}, 校准后={adjusted_confidence:.1%})"
                result["is_demo_mode"] = False

                logger.info("40类映射: ID=%d -> %s (类别=%d), 原始置信度=%.1f%% -> 校准后=%.1f%%",
                           original_class_id, class_name_cn, category_4class,
                           raw_confidence * 100, adjusted_confidence * 100)
            else:
                # YOLO未检测到有效目标，降级到特征分析模式
                logger.warning("YOLO未检测到有效目标 (ID=%d, 置信度=%.1f%%), 降级到特征分析模式",
                               original_class_id, result.get("confidence", 0) * 100)

                features = ImageFeatureAnalyzer.analyze(image)
                logger.info("特征分析: 亮度=%s, 透明度=%s, 金属=%s, 长宽比=%.2f",
                           features.get('brightness'),
                           features.get('transparency'),
                           features.get('is_metallic'),
                           features.get('aspect_ratio'))

                smart_class_index, reasoning, item_type = ImageFeatureAnalyzer.classify_by_features(features)
                demo_confidence = ImageFeatureAnalyzer.calculate_confidence(features, smart_class_index)

                result["class_index"] = smart_class_index
                result["confidence"] = round(demo_confidence, 4)
                result["feature_analysis"] = features
                result["reasoning"] = reasoning
                result["item_type"] = item_type
                result["is_demo_mode"] = True

                logger.info("特征分析降级完成: 类别=%d, 类型=%s, 置信度=%.1f%%, %s",
                           smart_class_index, item_type, demo_confidence * 100, reasoning)

        else:
            # 旧版COCO/ONNX模型 - 混合策略
            original_class_id = result.get("original_class_id")

            HIGH_CONFIDENCE_CONTAINER_CLASSES = {39, 40, 41, 45}

            use_yolo_result = (
                not result.get("is_demo_mode") and
                original_class_id is not None and
                original_class_id in HIGH_CONFIDENCE_CONTAINER_CLASSES and
                backend_state.vision_engine.num_classes == 80 and
                result.get("confidence", 0) > 0.6
            )

            if not use_yolo_result:
                logger.info("启用增强特征分析模式 (YOLO ID=%s, 置信度=%.1f%%)",
                           original_class_id, result.get("confidence", 0) * 100)

                features = ImageFeatureAnalyzer.analyze(image)
                logger.info("特征: 亮度=%s, 透明度=%s, 金属=%s, 长宽比=%.2f",
                           features.get('brightness'),
                           features.get('transparency'),
                           features.get('is_metallic'),
                           features.get('aspect_ratio'))

                smart_class_index, reasoning, item_type = ImageFeatureAnalyzer.classify_by_features(features)
                demo_confidence = ImageFeatureAnalyzer.calculate_confidence(features, smart_class_index)

                _old_index = result["class_index"]
                result["class_index"] = smart_class_index
                result["confidence"] = round(demo_confidence, 4)
                result["feature_analysis"] = features
                result["reasoning"] = reasoning
                result["item_type"] = item_type
                result["is_demo_mode"] = True

                logger.info("特征分析完成: 类别=%d, 类型=%s, 置信度=%.1f%%, %s",
                           smart_class_index, item_type, demo_confidence * 100, reasoning)
            else:
                logger.info("使用YOLO检测结果 (ID=%s, 名称=%s, 置信度=%.1f%%)",
                           original_class_id, result.get("original_class_name"),
                           result.get("confidence", 0) * 100)

        class_info = _get_class_info(result["class_index"],
                                   result.get("is_demo_mode", False),
                                   result.get("item_type", "unknown"),
                                   result.get("feature_analysis", {}).get("is_metallic", "False") == "True",
                                   result.get("original_class_name"))

        response_data = {
            "success": True,
            "result": {**result, **class_info},
            "inference_time_ms": inference_ms,
            "timing": timing,
            "request_id": req_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        if result.get("is_demo_mode"):
            response_data["demo_notice"] = (
                "当前为智能演示模式（基于图像特征分析），识别准确度低于专用AI模型，仅供参考。"
                "建议拍摄清晰正面照片以提高识别准确性。"
            )

        if backend_state.history_store:
            backend_state.history_store.add({
                "category": class_info.get("category", ""),
                "category_id": class_info.get("category_id", -1),
                "label_cn": class_info.get("label_cn", ""),
                "bin_color": class_info.get("bin_color", ""),
                "confidence": result.get("confidence", 0),
                "guidance": class_info.get("guidance", ""),
                "is_demo_mode": result.get("is_demo_mode", False),
            })

        if backend_state.inference_cache and 'cache_key' in locals():
            try:
                backend_state.inference_cache.set(cache_key, response_data["result"])
            except Exception as e:
                logger.warning("缓存写入异常（不影响主流程）: %s", e)

        timing["postprocess_ms"] = int((time.time() - postprocess_start) * 1000)
        logger.info("耗时统计: 预处理=%dms, 推理=%dms, 后处理=%dms, 总计=%dms [req=%s]",
                    timing["preprocess_ms"], timing["inference_ms"],
                    timing["postprocess_ms"], inference_ms, req_id)

        return JSONResponse(content=response_data)

    except RuntimeError as e:
        logger.error("推理异常: %s", e)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "E003", "message": "AI推理过程出错，请稍后重试"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
    except Exception as e:
        logger.error("未知异常: %s", e)
        logger.error("堆栈:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "E003", "message": "服务器内部错误，请稍后重试"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


@router.post("/api/predict/multimodal")
async def predict_multimodal(request: PredictRequest) -> JSONResponse:
    """多模态融合预测接口（YOLO + SAHI + 双层级联）

    返回各模型独立结果和融合后的最终结果，多模型投票降低误判率。
    """
    start_time = time.time()
    req_id = uuid.uuid4().hex[:12]

    if not backend_state.multimodal_available or not backend_state.multimodal_classifier:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E010", "message": "多模态融合分类器未就绪"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    try:
        image, image_data = decode_base64_image(request.image)
        logger.info("[多模态] 图片解码成功, 尺寸: %s", image.size)

    except ValueError as e:
        return JSONResponse(status_code=400, content={
            "success": False, "error": {"code": "E001", "message": "图片格式无效"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    except Exception as e:
        return JSONResponse(status_code=400, content={
            "success": False, "error": {"code": "E001", "message": f"图片解码失败: {e}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })

    try:
        result = backend_state.multimodal_classifier.predict(image)

        final = result.final_prediction
        fusion_details = result.fusion_details

        response_data = {
            "success": True,
            "result": {
                "class_index": final.category.value,
                "category_name": final.category_name,
                "fine_class_id": final.fine_class_id,
                "fine_class_name_cn": final.fine_class_name_cn,
                "confidence": round(final.confidence, 4),
                "consistency_score": round(result.consistency_score, 3),
                "is_demo_mode": False,
                "source": "multimodal_fusion",
            },
            "multimodal_details": {
                "yolo": {
                    "class_name_cn": result.yolo_result.fine_class_name_cn if result.yolo_result else None,
                    "category_name": result.yolo_result.category_name if result.yolo_result else None,
                    "confidence": round(result.yolo_result.confidence, 4) if result.yolo_result else None,
                } if result.yolo_result else None,
                "sahi": {
                    "class_name_cn": result.sahi_result.fine_class_name_cn if result.sahi_result else None,
                    "category_name": result.sahi_result.category_name if result.sahi_result else None,
                    "confidence": round(result.sahi_result.confidence, 4) if result.sahi_result else None,
                } if result.sahi_result else None,
                "cascade": {
                    "class_name_cn": result.transformer_result.fine_class_name_cn if result.transformer_result else None,
                    "category_name": result.transformer_result.category_name if result.transformer_result else None,
                    "confidence": round(result.transformer_result.confidence, 4) if result.transformer_result else None,
                    "routing_strategy": result.transformer_result.features.get("cascade_routing_strategy") if result.transformer_result and result.transformer_result.features else None,
                } if result.transformer_result else None,
                "fusion": fusion_details,
            },
            "inference_time_ms": int(result.total_inference_time_ms),
            "timing": {"total_ms": int((time.time() - start_time) * 1000)},
            "request_id": req_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        logger.info("[多模态] 预测完成: %s (%s), 置信度=%.1f%%, 一致性=%.0f%%, 耗时=%dms",
                   final.fine_class_name_cn, final.category_name,
                   final.confidence * 100, result.consistency_score * 100,
                   result.total_inference_time_ms)

        return JSONResponse(content=response_data)

    except Exception as e:
        logger.error("[多模态] 推理异常: %s", e)
        logger.error("堆栈:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "E003", "message": f"多模态推理异常: {e}"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


@router.post("/api/batch_predict")
async def batch_predict_waste(request: BatchPredictRequest) -> JSONResponse:
    """批量图像分类识别，单次最多5张图片"""
    start_time = time.time()
    req_id = uuid.uuid4().hex[:12]

    images = request.images
    if len(images) > 5:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "批量识别最多支持5张图片"},
                "request_id": req_id,
            },
        )

    if not backend_state.vision_engine or not backend_state.vision_engine.is_loaded:
        return JSONResponse(
            status_code=503,
            content={
                "success": False,
                "error": {"code": "E002", "message": "模型未就绪"},
                "request_id": req_id,
            },
        )

    results = []
    for idx, img_str in enumerate(images):
        try:
            image, image_data = decode_base64_image(img_str)
        except Exception:
            results.append({"index": idx, "error": "图片解码失败"})
            continue

        # 缓存检查
        current_cache_key = None
        cached_item = None
        if backend_state.inference_cache:
            try:
                current_cache_key = backend_state.inference_cache._make_key(image_data)
                cached_result = backend_state.inference_cache.get(current_cache_key)
                if cached_result:
                    logger.info("批量识别-第%d张 缓存命中: %s", idx + 1, current_cache_key[:20])
                    cached_item = {
                        "index": idx,
                        "category": cached_result.get("category", ""),
                        "category_id": cached_result.get("category_id", -1),
                        "bin_color": cached_result.get("bin_color", ""),
                        "bin_icon": cached_result.get("bin_icon", ""),
                        "label_cn": cached_result.get("label_cn", ""),
                        "confidence": cached_result.get("confidence", 0),
                        "guidance": cached_result.get("guidance", ""),
                        "is_demo_mode": cached_result.get("is_demo_mode", False),
                        "inference_time_ms": 0,
                        "cache_hit": True,
                    }
                    results.append(cached_item)

                    if backend_state.history_store:
                        backend_state.history_store.add({
                            "category": cached_item["category"],
                            "category_id": cached_item["category_id"],
                            "label_cn": cached_item["label_cn"],
                            "bin_color": cached_item["bin_color"],
                            "confidence": cached_item["confidence"],
                            "guidance": cached_item["guidance"],
                            "is_demo_mode": cached_item["is_demo_mode"],
                        })
                    continue
            except Exception as e:
                logger.warning("批量识别-第%d张 缓存检查异常，将执行正常推理: %s", idx + 1, e)

        try:
            img_start = time.time()
            result = backend_state.vision_engine.predict(image)
            img_ms = int((time.time() - img_start) * 1000)

            class_index = result.get("class_index", 2)

            # 40类映射
            if backend_state.vision_engine.is_pt_model and backend_state.vision_engine.num_classes >= 40:
                original_class_id = result.get("original_class_id", -1)
                if original_class_id in GARBAGE_40CLASSES:
                    mapping = GARBAGE_40CLASSES[original_class_id]
                    class_index = mapping["category"]
                    result["original_class_name"] = mapping["name_cn"]
                    result["is_demo_mode"] = False

            class_info = _get_class_info(
                class_index,
                result.get("is_demo_mode", False),
                result.get("item_type", "unknown"),
                result.get("feature_analysis", {}).get("is_metallic", "False") == "True",
                result.get("original_class_name"),
            )

            item = {
                "index": idx,
                "category": class_info.get("category", ""),
                "category_id": class_info.get("category_id", -1),
                "bin_color": class_info.get("bin_color", ""),
                "bin_icon": class_info.get("bin_icon", ""),
                "label_cn": class_info.get("label_cn", ""),
                "confidence": result.get("confidence", 0),
                "guidance": class_info.get("guidance", ""),
                "is_demo_mode": result.get("is_demo_mode", False),
                "inference_time_ms": img_ms,
            }
            results.append(item)

            if backend_state.inference_cache and current_cache_key:
                try:
                    backend_state.inference_cache.set(current_cache_key, item)
                except Exception as e:
                    logger.warning("批量识别-第%d张 缓存写入异常（不影响主流程）: %s", idx + 1, e)

            if backend_state.history_store:
                backend_state.history_store.add({
                    "category": item["category"],
                    "category_id": item["category_id"],
                    "label_cn": item["label_cn"],
                    "bin_color": item["bin_color"],
                    "confidence": item["confidence"],
                    "guidance": item["guidance"],
                    "is_demo_mode": item["is_demo_mode"],
                })

        except Exception as e:
            logger.error("批量推理-第%d张出错: %s", idx, e)
            results.append({"index": idx, "error": str(e)})

    total_ms = int((time.time() - start_time) * 1000)
    return JSONResponse(content={
        "success": True,
        "results": results,
        "total_time_ms": total_ms,
        "request_id": req_id,
    })


@router.post("/api/share/text")
async def generate_share_text(request: Request) -> JSONResponse:
    """生成识别结果的文字分享内容"""
    try:
        body = await request.json()
        category = body.get("category", "未知")
        item_name = body.get("item_name", "物品")
        confidence = body.get("confidence", 0)
        guidance = body.get("guidance", "")

        confidence_pct = int(confidence * 100)
        share_text = (
            f"我用「校园垃圾分类AI助手」识别了一个物品\n"
            f"物品：{item_name}\n"
            f"分类：{category}\n"
            f"置信度：{confidence_pct}%\n"
        )
        if guidance:
            share_text += f"投放指引：{guidance}\n"
        share_text += "\n快来试试吧！"

        return JSONResponse(content={
            "success": True,
            "data": {
                "share_text": share_text,
                "share_url": f"/?shared={category}",
            },
        })
    except Exception as e:
        logger.error("生成分享内容失败: %s", e)
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": {"code": "E500", "message": "生成分享内容失败"},
        })


@router.get("/api/health")
async def health_check() -> JSONResponse:
    """健康检查接口

    检查项：AI模型、数据库、Redis、多模态融合系统、推理缓存
    """
    multimodal_status = None
    if backend_state.multimodal_available and backend_state.multimodal_classifier:
        try:
            system_info = backend_state.multimodal_classifier.get_system_info()
            multimodal_status = {
                "available": True,
                "architecture": system_info.get("architecture", "unknown"),
                "layers": {k: v for k, v in system_info.get("layers", {}).items()},
                "total_classes": system_info.get("total_fine_grained_classes", 0),
            }
        except Exception:
            multimodal_status = {"available": False, "error": "获取状态失败"}
    else:
        multimodal_status = {
            "available": False,
            "reason": "模块未加载" if not backend_state.multimodal_available else "分类器未初始化",
        }

    # 数据库连接检查
    db_status = "unknown"
    try:
        from app.database import get_db
        db = get_db()
        db.fetchone("SELECT 1 as test")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:50]}"

    # Redis 连接检查（可选）
    redis_status = "not_configured"
    try:
        from app.config import settings
        if settings.redis_url and settings.redis_url != "redis://localhost:6379/0":
            import redis as redis_lib
            r = redis_lib.from_url(settings.redis_url, socket_connect_timeout=2)
            r.ping()
            redis_status = "connected"
    except ImportError:
        redis_status = "library_not_installed"
    except Exception as e:
        redis_status = f"error: {str(e)[:50]}"

    # 推理缓存状态
    cache_stats = {}
    if backend_state.inference_cache:
        cache_stats = backend_state.inference_cache.stats()

    is_healthy = (
        (backend_state.vision_engine is not None) and
        db_status == "connected"
    )

    return JSONResponse(
        content={
            "status": "healthy" if is_healthy else "degraded",
            "model_loaded": backend_state.vision_engine.is_loaded if backend_state.vision_engine else False,
            "model_type": "专用垃圾分类模型" if (backend_state.vision_engine and backend_state.vision_engine.is_waste_model) else "智能演示模式（图像特征分析）",
            "vocab_loaded": len(backend_state.search_engine.vocab) > 0 if backend_state.search_engine else False,
            "database": db_status,
            "redis": redis_status,
            "cache": cache_stats,
            "multimodal_fusion": multimodal_status,
        }
    )
