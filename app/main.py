"""垃圾分类后端主程序"""

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

from app.config import settings
from app.constants import BASE_DIR, MODEL_PATH, VOCAB_PATH, STATIC_DIR, INDEX_HTML_PATH
from app.database import init_database, get_db

# 日志配置
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

from app.logging_config import setup_logging
setup_logging(log_level=settings.log_level, log_format=settings.log_format)

# 文件日志
import logging.handlers
_file_handler = logging.handlers.RotatingFileHandler(
    log_dir / "app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.getLogger().handlers[0].formatter if logging.getLogger().handlers else None)
logging.getLogger().addHandler(_file_handler)

logger = logging.getLogger(__name__)

# 多模态融合分类器
# 先用简单方案，后续再上多模型融合
try:
    from app.multimodal_fusion import MultiModalFusionClassifier
    _MULTIMODAL_AVAILABLE = True
    logger.info("多模态融合模块加载成功 (YOLO + SAHI + 双层级联)")
except ImportError as e:
    _MULTIMODAL_AVAILABLE = False
    MultiModalFusionClassifier = None
    logger.warning("多模态融合模块不可用 (%s)，将使用单模型模式", e)

# 最优双层架构 (v2.0)
# TODO: 后面重构这块，目前先这么凑合用
_OPTIMAL_DUAL_LAYER_AVAILABLE = False
OptimalDualLayerFusion = None
try:
    from app.optimal_dual_layer import OptimalDualLayerFusion, create_optimal_classifier
    _OPTIMAL_DUAL_LAYER_AVAILABLE = True
    logger.info("最优双层架构模块加载成功 (V2 + Main 双层融合)")
except ImportError as e:
    logger.info("最优双层架构不可用，将使用标准架构: %s", e)

from services.rate_limiter import RateLimiter
from services.vision_engine import VisionEngine
from services.search_engine import SearchEngine
from services.history_store import HistoryStore
from services.feedback_store import FeedbackStore
from services.inference_cache import InferenceCache
from services.asr_correction import set_search_engine

from app import backend_state

app = FastAPI(
    title="垃圾分类AI助手",
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

# Prometheus 监控
if settings.enable_metrics:
    try:
        from app.metrics import MetricsMiddleware, get_metrics, get_metrics_content_type
        from app.metrics import model_loaded_status, db_connection_status

        app.add_middleware(MetricsMiddleware)

        @app.get("/api/metrics", include_in_schema=False)
        async def metrics_endpoint():
            """Prometheus 指标采集端点"""
            return Response(content=get_metrics(), media_type=get_metrics_content_type())

        logger.info("Prometheus 监控指标已启用 (/api/metrics)")
    except ImportError:
        logger.warning("prometheus_client 未安装，监控指标不可用")

# 限流器：每IP每分钟最多30次请求
_rate_limiter = RateLimiter(default_max_requests=30, default_window_seconds=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """限流中间件，防刷"""
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
            "限流触发: IP=%s, 路径=%s, 窗口内请求=%d/%d, 等待%ds",
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
async def static_cache_middleware(request: Request, call_next):
    """静态资源缓存，开发环境禁用缓存方便调试"""
    response = await call_next(request)
    path = request.url.path

    if path.startswith("/static/"):
        if settings.reload:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            if path.endswith((".css", ".js")):
                response.headers["Cache-Control"] = "public, max-age=604800"
            elif path.endswith((".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp")):
                response.headers["Cache-Control"] = "public, max-age=2592000"
            elif path.endswith((".woff", ".woff2", ".ttf", ".eot")):
                response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            else:
                response.headers["Cache-Control"] = "public, max-age=86400"
    return response


# Vite 开发客户端请求兜底，项目没用到Vite，避免404噪音
@app.get("/@vite/{path:path}")
async def vite_client_fallback(path: str):
    return Response(content="/* EcoSort: not using Vite */", media_type="application/javascript")


@app.on_event("startup")
def startup_event() -> None:
    """启动时初始化所有服务"""
    logger.info("正在初始化服务...")

    backend_state.vision_engine = VisionEngine(str(MODEL_PATH))
    backend_state.search_engine = SearchEngine(str(VOCAB_PATH))
    backend_state.history_store = HistoryStore(backup_path=BASE_DIR / "data" / "history.json")
    backend_state.feedback_store = FeedbackStore(backup_path=BASE_DIR / "data" / "feedback.json")
    backend_state.inference_cache = InferenceCache(max_size=500, ttl_seconds=86400)
    backend_state.rate_limiter = _rate_limiter

    set_search_engine(backend_state.search_engine)

    # 初始化分类器，优先级: 最优双层架构 > 标准三层架构 > 单模型
    # 临时处理，线上暂未遇到问题
    optimal_init_success = False
    if _OPTIMAL_DUAL_LAYER_AVAILABLE:
        try:
            optimal_classifier = create_optimal_classifier(auto_mode=True)
            if optimal_classifier is not None:
                backend_state.multimodal_classifier = optimal_classifier
                backend_state.multimodal_available = True
                backend_state.architecture_mode = "optimal_dual_layer_v2"
                optimal_init_success = True
                logger.info("最优双层架构初始化完成 (V2粗分类 + Main精细)")
        except Exception as e:
            logger.warning("最优双层架构初始化失败: %s", e)

    if not optimal_init_success and not backend_state.multimodal_available and _MULTIMODAL_AVAILABLE and MultiModalFusionClassifier is not None:
        try:
            backend_state.multimodal_classifier = MultiModalFusionClassifier(
                yolo_model_path=str(BASE_DIR / "models" / "garbage_yolov8m_best.pt"),
                enable_sahi=True,
                sahi_slice_size=(320, 320),
            )
            backend_state.multimodal_available = True
            backend_state.architecture_mode = "standard_triple_layer"
            logger.info("标准三层架构初始化完成")
        except Exception as e:
            logger.warning("多模态融合分类器初始化失败: %s", e)
            backend_state.multimodal_classifier = None
            backend_state.multimodal_available = False

    # 加载处理步骤数据
    steps_file = BASE_DIR / "data" / "disposal_steps.json"
    if steps_file.exists():
        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                backend_state.disposal_steps_data = json.load(f).get("steps", {})
            logger.info("处理步骤数据加载完成: %d 条", len(backend_state.disposal_steps_data))
        except Exception as e:
            logger.warning("处理步骤数据加载失败: %s", e)

    # 初始化数据库（自动选择 SQLite/PostgreSQL）
    init_database()

    # 桥接旧 db 全局对象到新数据库抽象层
    from app.db import _bridge_to_new_database
    _bridge_to_new_database()

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    logger.info("服务初始化完成")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """关闭时释放资源"""
    if backend_state.vision_engine:
        backend_state.vision_engine.dispose()
        backend_state.vision_engine = None
    backend_state.multimodal_classifier = None
    logger.info("服务已关闭")


# 路由注册
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


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level,
    )
