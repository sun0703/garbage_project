"""
校园生活垃圾智能分类识别系统 - 后端主程序
技术栈：FastAPI + Uvicorn + ONNX Runtime + FuzzyWuzzy + Pillow
功能：图像分类识别 + 语音/文字模糊搜索
"""

import json
import base64
import time
import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from PIL import Image
import numpy as np
import onnxruntime as ort
from fuzzywuzzy import process as fuzz_process

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# ==================== 配置常量 ====================
BASE_DIR = Path(__file__).parent
MODEL_PATH = BASE_DIR / "models" / "waste_classifier.onnx"
VOCAB_PATH = BASE_DIR / "data" / "waste.json"
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML_PATH = BASE_DIR / "index.html"

INPUT_SIZE = (224, 224)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# ==================== FastAPI 应用实例 ====================
app = FastAPI(
    title="校园垃圾分类AI助手",
    description="基于YOLOv8n-cls的智能垃圾分类识别系统",
    version="1.0.0"
)


# ==================== 请求/响应模型 ====================
class PredictRequest(BaseModel):
    """图像预测请求体"""
    image: str  # Base64编码的图片数据


class SearchResponse(BaseModel):
    """搜索响应项"""
    match_label: str
    category: str
    category_id: int
    similarity_score: int
    bin_color: str
    bin_icon: str
    guidance: str
    yolo_label: Optional[str] = None


# ==================== 视觉推理引擎 ====================
class VisionEngine:
    """基于ONNX Runtime的图像分类推理引擎"""

    def __init__(self, model_path: str):
        self.session: Optional[ort.InferenceSession] = None
        self.input_name: str = ""
        self.output_name: str = ""
        self.is_loaded: bool = False
        self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """加载ONNX模型文件"""
        model_file = Path(model_path)
        if not model_file.exists():
            logger.warning(f"模型文件不存在: {model_path}，视觉推理功能不可用")
            return
        try:
            self.session = ort.InferenceSession(str(model_file))
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            self.is_loaded = True
            logger.info(f"模型加载成功: {model_path}")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")

    def predict(self, image: Image.Image) -> dict:
        """
        执行图像分类推理
        :param image: PIL Image对象
        :return: 包含class_index和confidence的字典
        """
        if not self.is_loaded:
            raise RuntimeError("模型未加载")
        input_tensor = self._preprocess(image)
        output = self.session.run(
            [self.output_name],
            {self.input_name: input_tensor}
        )
        return self._postprocess(output[0])

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """图像预处理：缩放→归一化→ImageNet标准化→CHW格式"""
        resized = image.resize(INPUT_SIZE)
        img_array = np.array(resized).astype(np.float32) / 255.0
        normalized = (img_array - IMAGENET_MEAN) / IMAGENET_STD
        chw = normalized.transpose(2, 0, 1)
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def _postprocess(self, output: np.ndarray) -> dict:
        """后处理：Softmax归一化→取最大概率类别"""
        shifted = output - np.max(output)
        exp_vals = np.exp(shifted)
        probs = exp_vals / exp_vals.sum()
        top_idx = int(np.argmax(probs))
        return {
            "class_index": top_idx,
            "confidence": round(float(probs[top_idx]), 4)
        }

    def dispose(self) -> None:
        """释放推理会话资源"""
        if self.session:
            del self.session
            self.is_loaded = False


# ==================== 模糊搜索引擎 ====================
class SearchEngine:
    """基于FuzzyWuzzy的模糊搜索引擎，支持容错匹配"""

    def __init__(self, vocab_path: str):
        self.vocab: list[dict] = []
        self.vocab_labels: list[str] = []
        self._load_vocab(vocab_path)

    def _load_vocab(self, vocab_path: str) -> None:
        """加载垃圾分类词库JSON文件"""
        vocab_file = Path(vocab_path)
        if not vocab_file.exists():
            logger.warning(f"词库文件不存在: {vocab_path}，搜索功能不可用")
            return
        try:
            with open(vocab_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.vocab = data.get("items", [])
            self.vocab_labels = [item["label"] for item in self.vocab]
            logger.info(f"词库加载成功: {len(self.vocab)} 条记录")
        except Exception as e:
            logger.error(f"词库加载失败: {e}")

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        执行模糊搜索，返回top_k个最匹配的结果
        :param query: 用户输入的搜索关键词
        :param top_k: 返回的最大结果数
        :return: 匹配结果列表
        """
        if not self.vocab_labels:
            return []
        raw_results = fuzz_process.extract(query, self.vocab_labels, limit=top_k)
        matched = []
        for label, score in raw_results:
            item = next((v for v in self.vocab if v["label"] == label), None)
            if item:
                matched.append({
                    **item,
                    "similarity_score": score
                })
        return matched

    def get_by_yolo_label(self, yolo_label: str) -> Optional[dict]:
        """根据YOLO模型输出的英文标签查找对应的中文名称和分类信息"""
        for item in self.vocab:
            if item.get("yolo_label") == yolo_label:
                return item
        return None


# ==================== 全局实例初始化 ====================
vision_engine: Optional[VisionEngine] = None
search_engine: Optional[SearchEngine] = None


@app.on_event("startup")
def startup_event() -> None:
    """应用启动时初始化各引擎"""
    global vision_engine, search_engine
    logger.info("正在初始化服务...")
    vision_engine = VisionEngine(str(MODEL_PATH))
    search_engine = SearchEngine(str(VOCAB_PATH))

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    logger.info("服务初始化完成")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """应用关闭时释放资源"""
    global vision_engine
    if vision_engine:
        vision_engine.dispose()
    logger.info("服务已关闭")


# ==================== API 路由定义 ====================

@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """根路径：返回前端H5页面"""
    html_path = Path(INDEX_HTML_PATH)
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>前端页面未找到，请确保index.html存在</h1>",
        status_code=404
    )


@app.post("/api/predict")
async def predict_waste(request: PredictRequest) -> JSONResponse:
    """
    图像分类识别接口
    接收Base64编码的图片，返回垃圾分类识别结果
    """
    start_time = time.time()

    try:
        header, encoded_data = request.image.split(",", 1)
        image_data = base64.b64decode(encoded_data)
        image = Image.open(BytesIO(image_data)).convert("RGB")
    except Exception as e:
        logger.error(f"图片解码失败: {e}")
        return JSONResponse(status_code=400, content={
            "success": False,
            "error": {"code": "E001", "message": "图片格式无效或解码失败"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    if not vision_engine or not vision_engine.is_loaded:
        return JSONResponse(status_code=503, content={
            "success": False,
            "error": {"code": "E002", "message": "模型未就绪，请稍后重试"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    try:
        result = vision_engine.predict(image)
        inference_ms = int((time.time() - start_time) * 1000)

        class_info = _get_class_info(result["class_index"])

        return JSONResponse(content={
            "success": True,
            "result": {
                **result,
                **class_info
            },
            "inference_time_ms": inference_ms,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    except RuntimeError as e:
        logger.error(f"推理异常: {e}")
        return JSONResponse(status_code=500, content={
            "success": False,
            "error": {"code": "E003", "message": f"推理过程出错: {str(e)}"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })


@app.get("/api/search")
async def search_waste(query: str = Query(..., min_length=1)) -> JSONResponse:
    """
    语音/文字模糊搜索接口
    通过FuzzyWuzzy对用户输入进行容错匹配
    """
    if not search_engine or not search_engine.vocab:
        return JSONResponse(status_code=503, content={
            "success": False,
            "error": {"code": "E004", "message": "词库未就绪"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        })

    results = search_engine.search(query.strip(), top_k=3)
    return JSONResponse(content={
        "success": True,
        "query": query,
        "results": results,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
    })


@app.get("/api/categories")
async def get_categories() -> JSONResponse:
    """获取所有垃圾分类类别信息"""
    if not search_engine or not search_engine.vocab:
        return JSONResponse(status_code=503, content={"success": False})

    categories_map = {}
    for item in search_engine.vocab:
        cat_id = item["category_id"]
        if cat_id not in categories_map:
            categories_map[cat_id] = {
                "id": cat_id,
                "name": item["category_name"],
                "color": item.get("bin_color", ""),
                "icon": item.get("bin_icon", ""),
                "examples": []
            }
        categories_map[cat_id]["examples"].append(item["label"])

    return JSONResponse(content={
        "success": True,
        "categories": sorted(categories_map.values(), key=lambda x: x["id"])
    })


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """健康检查接口，用于监控服务状态"""
    return JSONResponse(content={
        "status": "healthy",
        "model_loaded": vision_engine.is_loaded if vision_engine else False,
        "vocab_loaded": len(search_engine.vocab) > 0 if search_engine else False,
        "uptime_info": "running"
    })


# ==================== 工具函数 ====================

def _get_class_info(class_index: int) -> dict:
    """
    根据类别索引获取完整的分类信息
    如果有词库则从词库获取详细信息，否则返回默认信息
    """
    default_categories = {
        0: {"category": "厨余垃圾", "category_id": 0, "bin_color": "#8B4513",
            "bin_icon": "🗑️", "guidance": "请投入棕色厨余垃圾桶", "label_cn": "未知物品"},
        1: {"category": "可回收物", "category_id": 1, "bin_color": "#007bff",
            "bin_icon": "♻️", "guidance": "请投入蓝色可回收物垃圾桶", "label_cn": "未知物品"},
        2: {"category": "其他垃圾", "category_id": 2, "bin_color": "#333333",
            "bin_icon": "🗑️", "guidance": "请投入灰色其他垃圾桶", "label_cn": "未知物品"},
        3: {"category": "有害垃圾", "category_id": 3, "bin_color": "#dc3545",
            "bin_icon": "☠️", "guidance": "请投入红色有害垃圾桶", "label_cn": "未知物品"},
    }

    info = default_categories.get(class_index, default_categories[2]).copy()

    if search_engine and search_engine.vocab:
        yolo_labels = list(set(item.get("yolo_label", "") for item in search_engine.vocab))
        if class_index < len(yolo_labels) and yolo_labels[class_index]:
            matched = search_engine.get_by_yolo_label(yolo_labels[class_index])
            if matched:
                info.update({
                    "label_cn": matched.get("label", ""),
                    "category": matched.get("category_name", info["category"]),
                    "bin_color": matched.get("bin_color", info["bin_color"]),
                    "bin_icon": matched.get("bin_icon", info["bin_icon"]),
                    "guidance": matched.get("guidance", info["guidance"]),
                    "yolo_label": matched.get("yolo_label", "")
                })

    return info


# ==================== 程序入口 ====================
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
