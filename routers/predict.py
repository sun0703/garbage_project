"""
预测相关路由模块
包含图像识别、多模态融合预测、批量预测、健康检查等接口
"""

import logging
import time
import uuid
import traceback
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse

from constants import GARBAGE_40CLASSES, WASTE_CATEGORIES, INDEX_HTML_PATH
import backend_state
from models import PredictRequest, BatchPredictRequest
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
    return HTMLResponse(
        content="<h1>前端页面未找到</h1>",
        status_code=404,
    )


@router.post("/api/predict")
async def predict_waste(request: PredictRequest) -> JSONResponse:
    """
    图像分类识别接口（增强版）
    支持智能演示模式，基于图像特征分析提高分类准确性
    支持分阶段耗时记录（预处理/推理/后处理）
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
                    logger.info("🎯 缓存命中: %s (响应时间=%dms)", cache_key[:20], total_ms)
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

        # ===== 智能策略选择 =====
        # 40类专用模型：直接使用YOLO检测结果（无需特征分析）
        # COCO/通用模型：使用混合策略（YOLO + 特征分析）

        if backend_state.vision_engine.is_pt_model and backend_state.vision_engine.num_classes >= 40:
            # 40类专用垃圾分类模型 - 直接使用结果
            logger.info("🎯 使用40类专用模型结果 (ID=%s, 名称=%s, 置信度=%.1f%%)",
                       result.get("original_class_id"),
                       result.get("original_class_name"),
                       result.get("confidence", 0) * 100)

            original_class_id = result.get("original_class_id", -1)

            # 将40类ID映射到中国4类垃圾系统（优化版 - 添加置信度校准）
            if original_class_id in GARBAGE_40CLASSES:
                class_mapping = GARBAGE_40CLASSES[original_class_id]
                category_4class = class_mapping["category"]  # 0-3 对应4类
                class_name_cn = class_mapping["name_cn"]

                # ⭐ 置信度校准（新增）：基于类别难度和检测质量调整
                raw_confidence = result.get("confidence", 0.0)
                adjusted_confidence = _calibrate_confidence_40class(
                    raw_confidence,
                    original_class_id,
                    len(result.get("detections", [])),
                    result.get("is_demo_mode", False)
                )

                result["class_index"] = category_4class
                result["original_class_name"] = class_name_cn
                result["confidence"] = round(adjusted_confidence, 4)  # 使用校准后的置信度
                result["reasoning"] = f"YOLOv8-40类模型[优化]: {class_name_cn} → {WASTE_CATEGORIES[category_4class]['name']} (原始={raw_confidence:.1%}, 校准后={adjusted_confidence:.1%})"
                result["is_demo_mode"] = False

                logger.info("✅ 40类映射[优化]: ID=%d → %s (类别=%d), 原始置信度=%.1f%% → 校准后=%.1f%%",
                           original_class_id, class_name_cn, category_4class,
                           raw_confidence * 100, adjusted_confidence * 100)
            else:
                # ============================================================
                # YOLO未检测到有效目标（class_index=-1 或未知类别）
                # → 进入降级模式处理流程
                #
                # 【当前降级策略 - 阶段五】
                # 使用 ImageFeatureAnalyzer 进行图像特征分析，基于颜色、透明度、
                # 金属光泽、长宽比等视觉特征进行启发式分类。
                # 此模式标记为 is_demo_mode=True，向前端明确标识为非模型推理结果。
                #
                # 【未来技术方向 - 阶段六预留】ONNX Runtime Web (WASM) 前端本地推理
                # ┌─────────────────────────────────────────────────────────────┐
                # │ 技术方案概述:                                                │
                # │   将 ONNX 格式的轻量级垃圾分类模型部署到浏览器端运行          │
                # │   使用 onnxruntime-web 库（基于 WebAssembly / WebGL 加速）    │
                # │                                                             │
                # │ 核心优势:                                                    │
                # │   1. 完全离线运行 - 无需后端 GPU/服务器资源                   │
                # │   2. 低延迟推理 - 消除网络传输开销（<100ms 本地推理）           │
                # │   3. 隐私保护 - 图像数据不上传服务器                          │
                # │   4. 可扩展性 - 支持多模型并行加载（分类+检测）                 │
                # │                                                             │
                # │ 实现架构:                                                    │
                # │   前端 (static/js/)                                          │
                # │     ├── models/waste-classifier.onnx   # 轻量分类模型 (~5MB) │
                # │     ├── utils/onnx-engine.js         # ONNX 推理引擎封装      │
                # │     └── components/wasm-predictor.js  # WASM 推理组件         │
                # │                                                             │
                # │   后端 (main.py)                                             │
                # │     ├── GET  /api/models/latest       # 模型版本检查接口      │
                # │     └── POST /api/models/upload       # 模型热更新接口        │
                # │                                                             │
                # │ 降级链路设计:                                                │
                # │   YOLOv8 服务端推理 → 特征分析(当前) → WASM 本地推理(未来)    │
                # │   每层降级都记录 reasoning 字段，便于前端展示和日志追踪        │
                # └─────────────────────────────────────────────────────────────┘
                #
                # 【框架预留说明】
                # 以下代码块已预留 WASM 推理入口点注释，后续实现时只需：
                # 1. 在此分支前增加 WASM 可用性检测（navigator.onnxruntime）
                # 2. 调用 WasmPredictor.predict(imageBlob) 获取结果
                # 3. 将 WASM 结果合并到 result 字典中，设置 is_demo_mode=False, source='wasm'
                # ============================================================
                logger.warning("⚠️ YOLO未检测到有效目标 (ID=%d, 置信度=%.1f%%), 降级到特征分析模式",
                               original_class_id, result.get("confidence", 0) * 100)

                features = ImageFeatureAnalyzer.analyze(image)
                logger.info("📊 特征分析: 亮度=%s, 透明度=%s, 金属=%s, 长宽比=%.2f",
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

                logger.info("✅ 特征分析降级完成: 类别=%d, 类型=%s, 置信度=%.1f%%, %s",
                           smart_class_index, item_type, demo_confidence * 100, reasoning)

        else:
            # 旧版COCO/ONNX模型 - 使用混合策略v3.1
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
                logger.info("🔬 启用增强特征分析模式 (YOLO ID=%s, 置信度=%.1f%%)",
                           original_class_id, result.get("confidence", 0) * 100)

                features = ImageFeatureAnalyzer.analyze(image)
                logger.info("📊 特征: 亮度=%s, 透明度=%s, 金属=%s, 长宽比=%.2f",
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

                logger.info("✅ 特征分析完成: 类别=%d, 类型=%s, 置信度=%.1f%%, %s",
                           smart_class_index, item_type, demo_confidence * 100, reasoning)
            else:
                logger.info("✅ 使用YOLO检测结果 (ID=%s, 名称=%s, 置信度=%.1f%%)",
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
            # 降级模式提示：明确告知用户当前使用的是特征分析模式，并说明未来优化方向
            # 包含：当前模式说明、准确度预期、改进建议、WASM 本地推理预告
            response_data["demo_notice"] = (
                "🔬 智能演示模式（基于图像特征分析）\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "• 当前采用颜色/透明度/形状等视觉特征进行启发式分类\n"
                "• 识别准确度低于专用 AI 模型，仅供参考\n"
                "• 复杂物品（如多层包装）可能存在误判\n"
                "• 建议：拍摄清晰正面照片可提高识别准确性\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🚀 即将支持：浏览器本地 AI 推理（ONNX WASM），无需网络即可获得专业级识别精度"
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
        logger.info("⏱️ 耗时统计: 预处理=%dms, 推理=%dms, 后处理=%dms, 总计=%dms [req=%s]",
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


# ==================== 多模态融合预测接口 ====================
@router.post("/api/predict/multimodal")
async def predict_multimodal(request: PredictRequest) -> JSONResponse:
    """
    多模态融合预测接口（YOLO + SAHI + 双层级联）

    与 /api/predict 的区别：
    - 使用三模型融合决策（YOLO检测 + SAHI切片增强 + 级联精细化）
    - 返回各模型的独立结果和融合后的最终结果
    - 一致性校验：多模型投票，降低误判率
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
        logger.info("🔍 [多模态] 图片解码成功, 尺寸: %s", image.size)

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

        # 构建响应数据
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

        logger.info("✅ [多模态] 预测完成: %s (%s), 置信度=%.1f%%, 一致性=%.0f%%, 耗时=%dms",
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


# ==================== 批量识别接口 ====================

@router.post("/api/batch_predict")
async def batch_predict_waste(request: BatchPredictRequest) -> JSONResponse:
    """
    批量图像分类识别接口
    支持单次最多5张图片并行推理
    """
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
            results.append({
                "index": idx,
                "error": "图片解码失败",
            })
            continue

        # ===== 批量识别中的单张图片缓存检查 =====
        current_cache_key = None
        cached_item = None
        if backend_state.inference_cache:
            try:
                current_cache_key = backend_state.inference_cache._make_key(image_data)
                cached_result = backend_state.inference_cache.get(current_cache_key)
                if cached_result:
                    # 缓存命中：直接使用缓存结果，跳过模型推理
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
                        "inference_time_ms": 0,  # 缓存命中，推理时间为0
                        "cache_hit": True,
                    }
                    results.append(cached_item)

                    # 写入历史记录（缓存命中的图片也记录）
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
                    continue  # 跳过后续的模型推理逻辑
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

            # ===== 推理结果写入缓存（批量识别） =====
            if backend_state.inference_cache and current_cache_key:
                try:
                    backend_state.inference_cache.set(current_cache_key, item)
                except Exception as e:
                    logger.warning("批量识别-第%d张 缓存写入异常（不影响主流程）: %s", idx + 1, e)

            # 写入历史
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
            results.append({
                "index": idx,
                "error": str(e),
            })

    total_ms = int((time.time() - start_time) * 1000)
    return JSONResponse(content={
        "success": True,
        "results": results,
        "total_time_ms": total_ms,
        "request_id": req_id,
    })


# ==================== 健康检查接口 ====================

@router.get("/api/health")
async def health_check() -> JSONResponse:
    """健康检查接口（含多模态融合系统状态）"""
    # 获取多模态融合系统信息
    multimodal_status = None
    if backend_state.multimodal_available and backend_state.multimodal_classifier:
        try:
            system_info = backend_state.multimodal_classifier.get_system_info()
            multimodal_status = {
                "available": True,
                "architecture": system_info.get("architecture", "unknown"),
                "layers": {
                    k: v for k, v in system_info.get("layers", {}).items()
                },
                "total_classes": system_info.get("total_fine_grained_classes", 0),
            }
        except Exception:
            multimodal_status = {"available": False, "error": "获取状态失败"}
    else:
        multimodal_status = {
            "available": False,
            "reason": "模块未加载" if not backend_state.multimodal_available else "分类器未初始化",
        }

    return JSONResponse(
        content={
            "status": "healthy",
            "model_loaded": backend_state.vision_engine.is_loaded if backend_state.vision_engine else False,
            "model_type": "专用垃圾分类模型" if (backend_state.vision_engine and backend_state.vision_engine.is_waste_model) else "智能演示模式（图像特征分析）",
            "vocab_loaded": len(backend_state.search_engine.vocab) > 0 if backend_state.search_engine else False,
            "uptime_info": "running",
            "multimodal_fusion": multimodal_status,
        }
    )
