"""
校园生活垃圾智能分类识别系统 - 后端主程序
技术栈：FastAPI + Uvicorn + ONNX Runtime + FuzzyWuzzy + Pillow + OpenCV
架构：routers/ + services/ + repositories/ 三层分离
"""

import json
import logging
import logging.handlers
import random
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

# ==================== 配置管理导入 ====================
from app.config import settings
from app.constants import BASE_DIR, MODEL_PATH, VOCAB_PATH, STATIC_DIR, INDEX_HTML_PATH
from app.db import db

# ==================== 日志配置（同时输出到控制台和文件） ====================
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

# ==================== 多模态融合分类器导入 ====================
try:
    from app.multimodal_fusion import MultiModalFusionClassifier
    _MULTIMODAL_AVAILABLE = True
    logger.info("多模态融合模块加载成功 (YOLO + SAHI + 双层级联)")
except ImportError as e:
    _MULTIMODAL_AVAILABLE = False
    MultiModalFusionClassifier = None
    logger.warning("多模态融合模块不可用 (%s)，将使用单模型模式", e)

# 尝试导入最优双层架构 (v2.0)
_OPTIMAL_DUAL_LAYER_AVAILABLE = False
OptimalDualLayerFusion = None
try:
    from app.optimal_dual_layer import OptimalDualLayerFusion, create_optimal_classifier
    _OPTIMAL_DUAL_LAYER_AVAILABLE = True
    logger.info("✅ 最优双层架构模块加载成功 (V2 + Main 双层融合)")
except ImportError as e:
    logger.info("ℹ️ 最优双层架构不可用，将使用标准架构: %s", e)

# ==================== 服务层导入 ====================
from services.rate_limiter import RateLimiter
from services.vision_engine import VisionEngine
from services.search_engine import SearchEngine
from services.history_store import HistoryStore
from services.feedback_store import FeedbackStore
from services.inference_cache import InferenceCache
from services.asr_correction import set_search_engine

# ==================== 全局状态注入 ====================
from app import backend_state

# ==================== FastAPI 应用实例 ====================
app = FastAPI(
    title="校园垃圾分类AI助手",
    description="基于YOLOv8n-cls的智能垃圾分类识别系统",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局限流器实例：每IP每分钟最多30次请求
_rate_limiter = RateLimiter(default_max_requests=30, default_window_seconds=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """HTTP 中间件：对所有 API 路径执行请求频率检查（增强版）

    特性：
    - 按路径分级限流（预测接口更严格）
    - 白名单 IP 自动跳过
    - 响应头包含完整的限流状态信息
    - 支持 X-Forwarded-For 代理头
    """
    path = request.url.path

    if not path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)

    forwarded = request.headers.get("x-forwarded-for", "")
    real_ip = request.headers.get("x-real-ip", "")
    client_ip = (
        forwarded.split(",")[0].strip()
        if forwarded
        else (real_ip or request.client.host if request.client else "unknown")
    )

    allowed, info = _rate_limiter.is_allowed(client_ip, path)

    if not allowed:
        logger.warning(
            "⚠️ 限流触发: IP=%s, 路径=%s, 窗口内请求=%d/%d, 等待%ds",
            client_ip, path, info.get("current", 0), info.get("limit", 0),
            info.get("retry_after", 0)
        )
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": {
                    "code": "E005",
                    "message": "操作过于频繁，请稍后再试",
                    "detail": f"每{info.get('window', 60)}秒最多{info.get('limit', 30)}次请求",
                },
                "data": None,
            },
            headers={
                "Retry-After": str(info["retry_after"]),
                "X-RateLimit-Limit": str(info.get("limit", 30)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(info["reset_time"])),
                "X-RateLimit-Policy": f"{info.get('limit', 30)};w={info.get('window', 60)}",
            },
        )

    response = await call_next(request)

    response.headers["X-RateLimit-Limit"] = str(info.get("limit", 30))
    response.headers["X-RateLimit-Remaining"] = str(info.get("remaining", 0))
    response.headers["X-RateLimit-Reset"] = str(int(info["reset_time"]))
    response.headers["X-RateLimit-Policy"] = f"{info.get('limit', 30)};w={info.get('window', 60)}"

    if info.get("remaining", 0) == 0 or random.random() < 0.01:
        _rate_limiter.cleanup_stale_ips()

    return response


@app.middleware("http")
async def no_cache_static_middleware(request: Request, call_next):
    """对所有 /static 响应添加禁用缓存头，确保前端代码修改立即生效"""
    response = await call_next(request)
    if request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# ==================== Vite 开发客户端请求兜底 ====================
@app.get("/@vite/{path:path}")
async def vite_client_fallback(path: str):
    """Vite 开发客户端请求兜底 — 项目未使用 Vite，返回空 JS 以避免 404 控制台噪音"""
    return Response(content="/* EcoSort: not using Vite */", media_type="application/javascript")


# ==================== 启动事件：初始化所有全局服务 ====================
@app.on_event("startup")
def startup_event() -> None:
    """应用启动时初始化"""
    logger.info("正在初始化服务...")

    backend_state.vision_engine = VisionEngine(str(MODEL_PATH))
    backend_state.search_engine = SearchEngine(str(VOCAB_PATH))
    backend_state.history_store = HistoryStore(backup_path=BASE_DIR / "data" / "history.json")
    backend_state.feedback_store = FeedbackStore(backup_path=BASE_DIR / "data" / "feedback.json")
    backend_state.inference_cache = InferenceCache(max_size=500, ttl_seconds=86400)
    backend_state.rate_limiter = _rate_limiter

    set_search_engine(backend_state.search_engine)

    # ========== 初始化多模态融合分类器 ==========
    # 优先级: 最优双层架构 (V2+Main) > 标准三层架构 > 单模型

    optimal_init_success = False
    if _OPTIMAL_DUAL_LAYER_AVAILABLE:
        # 尝试创建最优双层架构
        try:
            optimal_classifier = create_optimal_classifier(auto_mode=True)
            if optimal_classifier is not None:
                backend_state.multimodal_classifier = optimal_classifier
                backend_state.multimodal_available = True
                backend_state.architecture_mode = "optimal_dual_layer_v2"
                optimal_init_success = True
                logger.info("🎯 最优双层架构初始化完成 (V2粗分类 + Main精细)")
        except Exception as e:
            logger.warning("⚠️ 最优双层架构初始化失败: %s", e)

    # 如果最优架构不可用或失败，使用标准架构
    if not optimal_init_success and not backend_state.multimodal_available and _MULTIMODAL_AVAILABLE and MultiModalFusionClassifier is not None:
        try:
            backend_state.multimodal_classifier = MultiModalFusionClassifier(
                yolo_model_path=str(BASE_DIR / "models" / "garbage_yolov8m_best.pt"),
                enable_sahi=True,
                sahi_slice_size=(320, 320),
            )
            backend_state.multimodal_available = True
            backend_state.architecture_mode = "standard_triple_layer"
            logger.info("✅ 标准三层架构初始化完成")
        except Exception as e:
            logger.warning("⚠️ 多模态融合分类器初始化失败: %s", e)
            backend_state.multimodal_classifier = None
            backend_state.multimodal_available = False

    steps_file = BASE_DIR / "data" / "disposal_steps.json"
    if steps_file.exists():
        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                backend_state.disposal_steps_data = json.load(f).get("steps", {})
            logger.info("处理步骤数据加载完成: %d 条", len(backend_state.disposal_steps_data))
        except Exception as e:
            logger.warning("处理步骤数据加载失败: %s", e)

    db.connect()
    db.init_tables()
    db.migrate()
    db.add_indexes()
    db.seed_disposal_points()
    db.seed_quiz_questions()
    db.seed_activities()

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    logger.info("服务初始化完成")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """应用关闭时释放资源"""
    if backend_state.vision_engine:
        backend_state.vision_engine.dispose()
        backend_state.vision_engine = None
    backend_state.multimodal_classifier = None
    logger.info("服务已关闭")


# ==================== 路由注册 ====================
from routers.predict import router as predict_router
from routers.search import router as search_router
from routers.guide import router as guide_router
from routers.history import router as history_router
from routers.voice import router as voice_router
from routers.feedback import router as feedback_router
from routers.debug import router as debug_router
from routers.auth import router as auth_router
from routers.map import router as map_router
from routers.quiz import router as quiz_router
from routers.activities import router as activities_router
from routers.stats import router as stats_router
from routers.achievements import router as achievements_router
from routers.admin import router as admin_router

app.include_router(predict_router)
app.include_router(search_router)
app.include_router(guide_router)
app.include_router(history_router)
app.include_router(voice_router)
app.include_router(feedback_router)
app.include_router(debug_router)
app.include_router(auth_router)
app.include_router(map_router)
app.include_router(quiz_router)
app.include_router(activities_router)
app.include_router(stats_router)
app.include_router(achievements_router)
app.include_router(admin_router)


# ==================== 程序入口 ====================
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
    )
