"""
校园生活垃圾智能分类识别系统 - 后端主程序（增强版）
技术栈：FastAPI + Uvicorn + ONNX Runtime + FuzzyWuzzy + Pillow + OpenCV
功能：图像分类识别 + 语音/文字模糊搜索 + 智能演示模式

增强内容：
1. 智能演示模式 - 基于图像特征的颜色/形状分析
2. 改进的垃圾分类启发式算法
3. 更合理的示例物品选择
"""

import base64
import hashlib
import json
import logging
import random
import time
import uuid
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, List

import cv2
import imagehash
import numpy as np
import onnxruntime as ort
import uvicorn
from fastapi import FastAPI, Query, Request, Cookie, Response
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from fuzzywuzzy import process as fuzz_process

from db import db
from PIL import Image

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ==================== 配置常量 ====================
BASE_DIR = Path(__file__).parent

# 新的40类垃圾分类专用YOLOv8m模型（2025年最新，mAP@0.5: 91%）
MODEL_PATH = BASE_DIR / "models" / "garbage_yolov8m_best.pt"
USE_YOLO_PT_MODEL = True  # 使用PyTorch格式模型（推荐）

# 备用：旧版ONNX模型
# MODEL_PATH = BASE_DIR / "models" / "yolov8_coco.onnx"
# USE_YOLO_PT_MODEL = False
VOCAB_PATH = BASE_DIR / "data" / "waste.json"
STATIC_DIR = BASE_DIR / "static"
INDEX_HTML_PATH = BASE_DIR / "index.html"

INPUT_SIZE = (224, 224)
YOLO_INPUT_SIZE = (640, 640)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

# 垃圾分类的4个类别定义（中国标准）
WASTE_CATEGORIES = {
    0: {"name": "厨余垃圾", "color": "#8B4513", "icon": "🗑️", "bin_color": "棕色"},
    1: {"name": "可回收物", "color": "#007bff", "icon": "♻️", "bin_color": "蓝色"},
    2: {"name": "其他垃圾", "color": "#333333", "icon": "🗑️", "bin_color": "灰色/黑色"},
    3: {"name": "有害垃圾", "color": "#dc3545", "icon": "☠️", "bin_color": "红色"},
}

# YOLOv8 7类模型的类别定义（英文原始标签）
YOLOV8_7CLASSES = {
    0: {"name": "banana-peel", "name_cn": "香蕉皮", "category": 0},  # → 厨余垃圾
    1: {"name": "glass", "name_cn": "玻璃", "category": 1},        # → 可回收物
    2: {"name": "metal", "name_cn": "金属", "category": 1},        # → 可回收物
    3: {"name": "orange-peel", "name_cn": "橘子皮", "category": 0}, # → 厨余垃圾
    4: {"name": "paper", "name_cn": "纸张", "category": 1},        # → 可回收物
    5: {"name": "plastic", "name_cn": "塑料", "category": 1},      # → 可回收物
    6: {"name": "styrofoam", "name_cn": "泡沫塑料", "category": 2}, # → 其他垃圾
}

# 40类细粒度垃圾分类专用映射（garbage_detect YOLOv8m模型）
# 来源: https://github.com/liangxi2004/garbage_detect (2025年最新)
GARBAGE_40CLASSES = {
    # ===== 其他垃圾 (Other Trash) - category 2 =====
    0: {"name": "Other Trash/Disposable Fast Food Box", "name_cn": "一次性快餐盒", "category": 2},
    1: {"name": "Other Trash/Dirty Plastic", "name_cn": "脏塑料", "category": 2},
    2: {"name": "Other Trash/Cigarette Butts", "name_cn": "烟蒂", "category": 2},
    3: {"name": "Other Trash/toothpicks", "name_cn": "牙签", "category": 2},
    4: {"name": "Other Trash/Crushed Flower Pots and Plates", "name_cn": "碎花盆和盘子", "category": 2},
    5: {"name": "Other Trash/Bamboo Chopsticks", "name_cn": "竹筷", "category": 2},

    # ===== 厨余垃圾 (Kitchen Waste) - category 0 =====
    6: {"name": "Kitchen Waste/Leftover Food", "name_cn": "剩菜剩饭", "category": 0},
    7: {"name": "Kitchen Waste/Large Bones", "name_cn": "大骨头", "category": 0},
    8: {"name": "Kitchen Waste/Fruit Peels", "name_cn": "果皮", "category": 0},
    9: {"name": "Kitchen Waste/Fruit Flesh", "name_cn": "果肉/果核", "category": 0},
    10: {"name": "Kitchen Waste/Tea Leaves", "name_cn": "茶叶", "category": 0},
    11: {"name": "Kitchen Waste/Vegetable Leaves and Roots", "name_cn": "蔬菜叶和根", "category": 0},
    12: {"name": "Kitchen Waste/Eggshells", "name_cn": "蛋壳", "category": 0},
    13: {"name": "Kitchen Waste/Fish Bones", "name_cn": "鱼骨", "category": 0},

    # ===== 可回收物 (Recyclable) - category 1 =====
    14: {"name": "Recyclable/Battery Pack", "name_cn": "电池组", "category": 1},
    15: {"name": "Recyclable/Bags", "name_cn": "背包", "category": 1},
    16: {"name": "Recyclable/Cosmetic Bottles", "name_cn": "化妆品瓶", "category": 1},
    17: {"name": "Recyclable/Plastic Toys", "name_cn": "塑料玩具", "category": 1},
    18: {"name": "Recyclable/Plastic Bowls and Plates", "name_cn": "塑料碗盘/餐盒", "category": 1},
    19: {"name": "Recyclable/Plastic Hangers", "name_cn": "塑料衣架", "category": 1},
    20: {"name": "Recyclable/Express Paper Bags", "name_cn": "快递纸袋", "category": 1},
    21: {"name": "Recyclable/Plugs and Wires", "name_cn": "插头和电线", "category": 1},
    22: {"name": "Recyclable/Old Clothes", "name_cn": "旧衣服", "category": 1},
    23: {"name": "Recyclable/Aluminum Cans", "name_cn": "铝罐/易拉罐", "category": 1},  # ⭐ 关键类别
    24: {"name": "Recyclable/Pillows", "name_cn": "枕头", "category": 1},
    25: {"name": "Recyclable/Stuffed Toys", "name_cn": "毛绒玩具", "category": 1},
    26: {"name": "Recyclable/Shampoo Bottles", "name_cn": "洗发水瓶", "category": 1},
    27: {"name": "Recyclable/Glass Cups", "name_cn": "玻璃杯", "category": 1},
    28: {"name": "Recyclable/Leather Shoes", "name_cn": "皮鞋", "category": 1},
    29: {"name": "Recyclable/Cutting Boards", "name_cn": "砧板", "category": 1},
    30: {"name": "Recyclable/Cardboard Boxes", "name_cn": "纸板箱", "category": 1},
    31: {"name": "Recyclable/Seasoning Bottles", "name_cn": "调料瓶", "category": 1},
    32: {"name": "Recyclable/Wine Bottles", "name_cn": "酒瓶", "category": 1},
    33: {"name": "Recyclable/Metal Food Cans", "name_cn": "金属食品罐", "category": 1},
    34: {"name": "Recyclable/Pots", "name_cn": "锅", "category": 1},
    35: {"name": "Recyclable/Cooking Oil Containers", "name_cn": "食用油容器", "category": 1},
    36: {"name": "Recyclable/Drink Bottles", "name_cn": "饮料瓶/塑料瓶", "category": 1},  # ⭐ 关键类别
    37: {"name": "Hazardous Waste/Dry Batteries", "name_cn": "干电池", "category": 3},
    38: {"name": "Hazardous Waste/Ointments", "name_cn": "药膏", "category": 3},
    39: {"name": "Recyclable/Paper", "name_cn": "纸张", "category": 1},
}

# COCO 80类 → 中国4类垃圾映射（使用官方COCO预训练模型时）
# COCO类别: https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/coco.yaml
COCO_TO_WASTE = {
    # ===== 可回收物 - 容器类 (Recyclable) =====
    39: {"name": "bottle", "name_cn": "塑料瓶/饮料瓶", "category": 1},
    40: {"name": "wine glass", "name_cn": "玻璃杯", "category": 1},
    41: {"name": "cup", "name_cn": "杯子/塑料杯", "category": 1},

    # 可回收物 - 餐具类
    42: {"name": "fork", "name_cn": "叉子（金属）", "category": 1},
    43: {"name": "knife", "name_cn": "刀具（金属）", "category": 1},
    44: {"name": "spoon", "name_cn": "勺子（金属/塑料）", "category": 1},
    45: {"name": "bowl", "name_cn": "碗/塑料餐盒", "category": 1},

    # 厨余垃圾 - 食物类 (Kitchen/Food Waste)
    46: {"name": "banana", "name_cn": "香蕉/果皮", "category": 0},
    47: {"name": "apple", "name_cn": "苹果/果核", "category": 0},
    48: {"name": "sandwich", "name_cn": "三明治/食物残渣", "category": 0},
    49: {"name": "orange", "name_cn": "橙子/水果", "category": 0},
    50: {"name": "broccoli", "name_cn": "西兰花/蔬菜", "category": 0},
    51: {"name": "carrot", "name_cn": "胡萝卜/蔬菜", "category": 0},
    52: {"name": "hot dog", "name_cn": "热狗/食物残渣", "category": 0},
    53: {"name": "pizza", "name_cn": "披萨/食物残渣", "category": 0},
    54: {"name": "donut", "name_cn": "甜甜圈/食物残渣", "category": 0},
    55: {"name": "cake", "name_cn": "蛋糕/食物残渣", "category": 0},

    # 可回收物 - 纸张书籍类
    73: {"name": "book", "name_cn": "书本/纸张", "category": 1},
    75: {"name": "vase", "name_cn": "花瓶（玻璃/陶瓷）", "category": 1},
    76: {"name": "scissors", "name_cn": "剪刀（金属）", "category": 1},

    # ===== 扩展：更多COCO类别映射 =====

    # 可回收物 - 电子设备类
    63: {"name": "laptop", "name_cn": "笔记本电脑（可回收）", "category": 1},
    64: {"name": "mouse", "name_cn": "鼠标（电子垃圾）", "category": 3},  # 有害/可回收
    65: {"name": "remote", "name_cn": "遥控器（电子垃圾）", "category": 3},
    66: {"name": "keyboard", "name_cn": "键盘（电子垃圾）", "category": 3},
    67: {"name": "cell phone", "name_cn": "手机（有害垃圾）", "category": 3},
    70: {"name": "toilet", "name_cn": "马桶（其他垃圾）", "category": 2},
    72: {"name": "clock", "name_cn": "时钟（其他垃圾）", "category": 2},

    # 可回收物 - 家具类（大件）
    56: {"name": "chair", "name_cn": "椅子（大件垃圾）", "category": 2},
    57: {"name": "couch", "name_cn": "沙发（大件垃圾）", "category": 2},
    59: {"name": "bed", "name_cn": "床（大件垃圾）", "category": 2},
    60: {"name": "dining table", "name_cn": "餐桌（大件垃圾）", "category": 2},

    # 其他常见COCO类别 → 默认分类
    0: {"name": "person", "name_cn": "非垃圾物品", "category": 2},
    1: {"name": "bicycle", "name_cn": "自行车（大件可回收）", "category": 1},
    2: {"name": "car", "name_cn": "汽车（非生活垃圾）", "category": 2},
    3: {"name": "motorcycle", "name_cn": "摩托车（非生活垃圾）", "category": 2},
    4: {"name": "airplane", "name_cn": "飞机（非生活垃圾）", "category": 2},
    5: {"name": "bus", "name_cn": "公交车（非生活垃圾）", "category": 2},
    6: {"name": "train", "name_cn": "火车（非生活垃圾）", "category": 2},
    7: {"name": "truck", "name_cn": "卡车（非生活垃圾）", "category": 2},
    8: {"name": "boat", "name_cn": "船（非生活垃圾）", "category": 2},
    9: {"name": "traffic light", "name_cn": "交通灯（非生活垃圾）", "category": 2},
    10: {"name": "fire hydrant", "name_cn": "消防栓（非生活垃圾）", "category": 2},
    11: {"name": "stop sign", "name_cn": "停止标志（非生活垃圾）", "category": 2},
    12: {"name": "parking meter", "name_cn": "停车计费器（非生活垃圾）", "category": 2},
    13: {"name": "bench", "name_cn": "长椅（大件垃圾）", "category": 2},
    14: {"name": "bird", "name_cn": "鸟类（非垃圾）", "category": 2},
    15: {"name": "cat", "name_cn": "猫（非垃圾）", "category": 2},
    16: {"name": "dog", "name_cn": "狗（非垃圾）", "category": 2},
    17: {"name": "horse", "name_cn": "马（非垃圾）", "category": 2},
    18: {"name": "sheep", "name_cn": "羊（非垃圾）", "category": 2},
    19: {"name": "cow", "name_cn": "牛（非垃圾）", "category": 2},
    20: {"name": "elephant", "name_cn": "大象（非垃圾）", "category": 2},
    21: {"name": "bear", "name_cn": "熊（非垃圾）", "category": 2},
    22: {"name": "zebra", "name_cn": "斑马（非垃圾）", "category": 2},
    23: {"name": "giraffe", "name_cn": "长颈鹿（非垃圾）", "category": 2},
    24: {"name": "backpack", "name_cn": "背包（旧衣物）", "category": 1},
    25: {"name": "umbrella", "name_cn": "雨伞（其他垃圾）", "category": 2},
    26: {"name": "handbag", "name_cn": "手提包（旧衣物）", "category": 1},
    27: {"name": "tie", "name_cn": "领带（旧衣物）", "category": 1},
    28: {"name": "suitcase", "name_cn": "行李箱（其他垃圾）", "category": 2},
    29: {"name": "frisbee", "name_cn": "飞盘（塑料可回收）", "category": 1},
    30: {"name": "skis", "name_cn": "滑雪板（其他垃圾）", "category": 2},
    31: {"name": "snowboard", "name_cn": "滑雪板（其他垃圾）", "category": 2},
    32: {"name": "sports ball", "name_cn": "球类（其他垃圾）", "category": 2},
    33: {"name": "kite", "name_cn": "风筝（其他垃圾）", "category": 2},
    34: {"name": "baseball bat", "name_cn": "棒球棒（其他垃圾）", "category": 2},
    35: {"name": "baseball glove", "name_cn": "棒球手套（其他垃圾）", "category": 2},
    36: {"name": "skateboard", "name_cn": "滑板（其他垃圾）", "category": 2},
    37: {"name": "surfboard", "name_cn": "冲浪板（其他垃圾）", "category": 2},
    38: {"name": "tennis racket", "name_cn": "网球拍（其他垃圾）", "category": 2},
    58: {"name": "potted plant", "name_cn": "盆栽（厨余+其他）", "category": 0},
    61: {"name": "tv", "name_cn": "电视（电子垃圾）", "category": 3},
    62: {"name": "laptop", "name_cn": "笔记本电脑（电子垃圾）", "category": 3},
    68: {"name": "microwave", "name_cn": "微波炉（电子垃圾）", "category": 3},
    69: {"name": "oven", "name_cn": "烤箱（大件垃圾）", "category": 2},
    71: {"name": "sink", "name_cn": "水槽（建筑垃圾）", "category": 2},
    74: {"name": "teddy bear", "name_cn": "泰迪熊（旧衣物）", "category": 1},
    77: {"name": "hair drier", "name_cn": "吹风机（电子垃圾）", "category": 3},
    78: {"name": "toothbrush", "name_cn": "牙刷（其他垃圾）", "category": 2},
    79: {"name": "hair brush", "name_cn": "梳子（其他垃圾）", "category": 2},
}

# 可回收物的典型特征关键词
RECYCLABLE_KEYWORDS = ["塑料", "瓶", "罐", "纸", "纸箱", "书", "报纸", "玻璃", "金属", "铝", "易拉罐", "饮料瓶", "矿泉水瓶", "洗发水", "沐浴露"]
# 厨余垃圾的典型特征关键词
FOOD_WASTE_KEYWORDS = ["果皮", "菜叶", "剩饭", "剩菜", "骨头", "蛋壳", "茶叶", "咖啡渣", "果核", "食物残渣", "厨余", "腐烂"]
# 有害垃圾的典型特征关键词
HAZARDOUS_KEYWORDS = ["电池", "灯管", "药品", "油漆", "农药", "化学品", "温度计", "血压计", "充电宝", "荧光灯"]


# ==================== 请求限流（滑动窗口） ====================

RATE_LIMIT_MAX_REQUESTS = 30
RATE_LIMIT_WINDOW_SECONDS = 60

_rate_limit_store: dict[str, list[float]] = {}


def _check_rate_limit(client_ip: str) -> Tuple[bool, int]:
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = [now]
        return True, RATE_LIMIT_MAX_REQUESTS - 1

    timestamps = _rate_limit_store[client_ip]
    timestamps[:] = [t for t in timestamps if t > window_start]

    if len(timestamps) >= RATE_LIMIT_MAX_REQUESTS:
        oldest = timestamps[0]
        retry_after = int(oldest + RATE_LIMIT_WINDOW_SECONDS - now) + 1
        return False, max(retry_after, 1)

    timestamps.append(now)
    return True, RATE_LIMIT_MAX_REQUESTS - len(timestamps)


# ==================== FastAPI 应用实例 ====================
app = FastAPI(
    title="校园垃圾分类AI助手",
    description="基于YOLOv8n-cls的智能垃圾分类识别系统",
    version="1.1.0",
)

# CORS 中间件配置（开发环境允许所有来源，生产环境应限制具体域名）
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应替换为具体前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    from starlette.requests import Request
    if not isinstance(request, Request):
        return await call_next(request)

    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        allowed, remaining = _check_rate_limit(client_ip)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "E429",
                        "message": "请求过于频繁，请稍后再试",
                    },
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                headers={"Retry-After": str(remaining)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_MAX_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    return await call_next(request)


# ==================== 请求/响应模型 ====================
class PredictRequest(BaseModel):
    """图像预测请求体"""
    image: str  # Base64编码的图片数据


class BatchPredictRequest(BaseModel):
    """批量图像预测请求体"""
    images: list[str]  # Base64编码的图片数组，最多5张


class FeedbackRequest(BaseModel):
    """用户反馈请求体"""
    image_base64: str                          # 原始图片Base64
    predicted_category_id: int                 # 模型预测的类别 0-3
    correct_category_id: int                   # 用户认为的正确类别 0-3
    comment: str = ""                          # 用户备注（可选，最长500字）

    class Config:
        json_schema_extra = {
            "example": {
                "image_base64": "data:image/jpeg;base64,...",
                "predicted_category_id": 1,
                "correct_category_id": 0,
                "comment": "应该是厨余垃圾"
            }
        }


# ==================== 内存存储层 ====================

class HistoryStore:
    """识别历史记录存储（内存 + JSON文件备份）"""

    def __init__(self, max_items: int = 200, backup_path: Path | None = None):
        self.max_items = max_items
        self._records: list[dict] = []
        self._backup_path = backup_path
        self._load_from_disk()

    def add(self, record: dict) -> str:
        record["id"] = uuid.uuid4().hex[:10]
        record["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._records.insert(0, record)
        if len(self._records) > self.max_items:
            self._records = self._records[:self.max_items]
        self._save_to_disk()
        return record["id"]

    def get_all(self, page: int = 1, page_size: int = 20) -> dict:
        total = len(self._records)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = self._records[start:end]
        return {
            "data": page_data,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, (total + page_size - 1) // page_size),
            },
        }

    def delete(self, record_id: str) -> bool:
        for i, r in enumerate(self._records):
            if r.get("id") == record_id:
                self._records.pop(i)
                self._save_to_disk()
                return True
        return False

    def clear(self) -> None:
        self._records.clear()
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        if not self._backup_path:
            return
        try:
            # 只存最近100条到磁盘
            with open(self._backup_path, "w", encoding="utf-8") as f:
                json.dump(self._records[:100], f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("历史记录持久化失败: %s", e)

    def _load_from_disk(self) -> None:
        if not self._backup_path or not self._backup_path.exists():
            return
        try:
            with open(self._backup_path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception as e:
            logger.warning("历史记录加载失败: %s", e)


class FeedbackStore:
    """用户反馈存储（内存 + JSON文件追加）"""

    def __init__(self, backup_path: Path | None = None):
        self._records: list[dict] = []
        self._backup_path = backup_path
        self._load_from_disk()

    def add(self, feedback: dict) -> str:
        feedback["feedback_id"] = f"fb_{uuid.uuid4().hex[:8]}"
        feedback["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        self._records.append(feedback)
        self._save_to_disk()
        return feedback["feedback_id"]

    def get_all(self) -> list[dict]:
        return list(self._records)

    def _save_to_disk(self) -> None:
        if not self._backup_path:
            return
        try:
            with open(self._backup_path, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("反馈记录持久化失败: %s", e)

    def _load_from_disk(self) -> None:
        if not self._backup_path or not self._backup_path.exists():
            return
        try:
            with open(self._backup_path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception as e:
            logger.warning("反馈记录加载失败: %s", e)


class InferenceCache:
    """
    基于 LRU + TTL 的推理结果缓存

    使用 OrderedDict 实现最近最少使用（LRU）淘汰策略，
    配合时间戳实现自动过期（TTL）机制。
    通过图像感知哈希（phash）识别相同内容的图片，避免重复推理。

    适用场景：
    - 相同图片短时间内多次上传（用户重复操作）
    - 批量处理时包含重复图片
    - 演示/测试环境减少模型调用次数
    """

    def __init__(self, max_size: int = 500, ttl_seconds: int = 86400):
        """
        初始化缓存实例

        :param max_size: 最大缓存条数（默认500，超过时淘汰最久未使用的）
        :param ttl_seconds: 缓存有效期（默认24小时=86400秒）
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        # 使用 OrderedDict 实现 LRU：访问时移动到末尾，淘汰时移除头部
        self._cache: OrderedDict[str, dict] = OrderedDict()
        logger.info("推理缓存初始化完成 (最大容量=%d, 有效期=%d秒)", max_size, ttl_seconds)

    def _make_key(self, image_data: bytes) -> str:
        """
        使用感知哈希生成缓存键（相同内容的图片命中同一缓存）

        优先使用 imagehash 库的 phash 算法（可识别相似图片），
        若库不可用则降级为 MD5 哈希（仅能识别完全相同的图片）。

        :param image_data: 原始图片字节数据（Base64解码后）
        :return: 格式化的缓存键 "infer:{hash_value}"
        """
        try:
            # 尝试使用感知哈希算法（推荐）
            image = Image.open(BytesIO(image_data)).convert("RGB")
            phash = imagehash.phash(image, hash_size=16)  # 使用16位哈希提高精度
            cache_key = f"infer:{str(phash)}"
            return cache_key
        except Exception:
            # 降级方案：使用 MD5 哈希（无法识别相似图，但至少能缓存完全相同的图片）
            md5_hash = hashlib.md5(image_data).hexdigest()
            cache_key = f"infer:md5_{md5_hash}"
            logger.debug("imagehash 不可用，已降级为 MD5 哈希")
            return cache_key

    def get(self, key: str) -> Optional[dict]:
        """
        获取缓存数据（带TTL检查和LRU更新）

        命中时会将条目移动到末尾（标记为最近使用），
        过期则删除该条目并返回 None。

        :param key: 缓存键（由 _make_key 生成）
        :return: 缓存的推理结果字典，未命中或过期返回 None
        """
        try:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            current_time = time.time()

            # 检查是否过期
            if current_time - entry["timestamp"] > self.ttl_seconds:
                # 过期则删除并记录日志
                del self._cache[key]
                logger.info("🗑️ 缓存淘汰（过期）: %s", key[:20])
                return None

            # 命中：移动到末尾（LRU更新）
            self._cache.move_to_end(key)
            return entry["data"]

        except Exception as e:
            logger.warning("缓存读取异常: %s", e)
            return None

    def set(self, key: str, data: dict) -> None:
        """
        写入缓存数据（带容量控制）

        如果键已存在则更新数据并移动到末尾，
        如果超过最大容量则淘汰最久未使用的条目（OrderedDict 头部）。

        :param key: 缓存键
        :param data: 推理结果数据
        """
        try:
            current_time = time.time()

            if key in self._cache:
                # 已存在：更新数据和时间戳，移动到末尾
                self._cache[key] = {"data": data, "timestamp": current_time}
                self._cache.move_to_end(key)
            else:
                # 新增：检查是否超出容量
                while len(self._cache) >= self.max_size:
                    # 淘汰最久未使用的条目（OrderedDict 的第一个元素）
                    oldest_key, _ = self._cache.popitem(last=False)
                    logger.info("🗑️ 缓存淘汰（容量满）: %s", oldest_key[:20])

                # 写入新条目
                self._cache[key] = {"data": data, "timestamp": current_time}
                logger.info("💾 缓存写入: %s (当前缓存数=%d/%d)",
                           key[:20], len(self._cache), self.max_size)

        except Exception as e:
            logger.warning("缓存写入异常: %s", e)

    def clear(self) -> None:
        """清空所有缓存"""
        self._cache.clear()
        logger.info("🧹 缓存已清空")

    def stats(self) -> dict:
        """获取缓存统计信息（用于监控和调试）"""
        current_time = time.time()
        valid_count = sum(
            1 for entry in self._cache.values()
            if current_time - entry["timestamp"] <= self.ttl_seconds
        )
        expired_count = len(self._cache) - valid_count

        return {
            "total_entries": len(self._cache),
            "valid_entries": valid_count,
            "expired_entries": expired_count,
            "max_size": self.max_size,
            "utilization": round(len(self._cache) / self.max_size * 100, 2) if self.max_size > 0 else 0,
        }


# ==================== 图像特征分析器 ====================
class ImageFeatureAnalyzer:
    """基于OpenCV的图像特征分析器，用于演示模式下的智能分类"""

    @staticmethod
    def analyze(image: Image.Image) -> dict:
        """
        分析图像特征，返回颜色、形状等信息
        :param image: PIL Image对象
        :return: 特征字典
        """
        # 转换为numpy数组
        img_array = np.array(image)
        
        # 如果是RGBA，转换为RGB
        if img_array.shape[-1] == 4:
            img_array = img_array[:, :, :3]
        
        # 转换为BGR格式（OpenCV默认）
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # 转换为HSV色彩空间
        img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # 分析主色调
        dominant_color = ImageFeatureAnalyzer._get_dominant_color(img_hsv)
        
        # 分析亮度
        brightness = ImageFeatureAnalyzer._get_brightness(img_array)
        
        # 分析是否有透明/半透明区域
        transparency = ImageFeatureAnalyzer._detect_transparency(img_array)
        
        # 分析形状特征（长宽比）
        aspect_ratio = image.width / image.height if image.height > 0 else 1.0
        
        return {
            "dominant_color": dominant_color,
            "brightness": brightness,
            "transparency": str(transparency),
            "aspect_ratio": aspect_ratio,
            "is_metallic": str(ImageFeatureAnalyzer._detect_metallic(img_array, brightness)),
        }
    
    @staticmethod
    def _get_dominant_color(img_hsv: np.ndarray) -> str:
        """获取图像的主色调"""
        # 计算色调直方图
        h_hist = cv2.calcHist([img_hsv], [0], None, [180], [0, 180])
        dominant_hue = np.argmax(h_hist)
        
        # 根据色调判断颜色
        if 0 <= dominant_hue <= 10 or 170 <= dominant_hue <= 180:
            return "red_orange"
        elif 10 < dominant_hue <= 25:
            return "orange_yellow"
        elif 25 < dominant_hue <= 35:
            return "yellow"
        elif 35 < dominant_hue <= 85:
            return "green"
        elif 85 < dominant_hue <= 130:
            return "blue"
        elif 130 < dominant_hue <= 160:
            return "purple"
        else:
            return "red"
    
    @staticmethod
    def _get_brightness(img_array: np.ndarray) -> float:
        """计算图像的平均亮度"""
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        return float(np.mean(gray)) / 255.0
    
    @staticmethod
    def _detect_transparency(img_array: np.ndarray) -> bool:
        """
        检测图像中是否有半透明或高光区域（可能是塑料、玻璃等）
        
        改进版：使用多种方法综合判断透明度
        """
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            std_dev = np.std(gray)
            high_light_ratio = np.sum(gray > 220) / gray.size
            
            gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
            mean_gradient = np.mean(gradient_magnitude)
            
            is_transparent = (
                std_dev > 40 or 
                high_light_ratio > 0.15 or 
                mean_gradient > 30
            )
            
            return is_transparent
        return False

    @staticmethod
    def _detect_metallic(img_array: np.ndarray, brightness: float = 0.5) -> bool:
        """
        检测图像中是否有金属光泽特征（易拉罐、铝罐等）
        
        平衡版 v3.0：能检测真实金属，同时尽量减少误判
        
        核心思路：使用OR逻辑而非AND逻辑，只要满足多个条件中的部分即可
        """
        if len(img_array.shape) != 3:
            return False
        
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # 特征1：高对比度（标准差大）
        std_dev = np.std(gray)
        
        # 特征2：超高光像素比例
        super_bright_ratio = np.sum(gray > 240) / gray.size
        
        # 特征3：亮度梯度变化
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        mean_gradient = np.mean(gradient_magnitude)
        
        # 特征4：颜色饱和度低
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1]
        mean_saturation = np.mean(saturation)
        
        # 综合判断（平衡版 - 使用计分制）：
        # 满足以下条件中的2个以上即为金属：
        score = 0
        if std_dev > 50:
            score += 1
        if super_bright_ratio > 0.03:
            score += 1
        if mean_gradient > 15:
            score += 1
        if mean_saturation < 120:
            score += 1
        
        is_metallic = (score >= 2)
        
        return is_metallic
    
    @staticmethod
    def classify_by_features(features: dict) -> Tuple[int, str, str]:
        """
        根据图像特征进行启发式分类（v2.1 - 形状优先）
        :param features: 图像特征字典
        :return: (类别ID, 推理依据, 物品类型标签)
        
        改进策略：形状（长宽比）优先于颜色和亮度
        解决奶茶杯识别问题
        """
        color = features["dominant_color"]
        brightness = float(features["brightness"])
        transparency = (features["transparency"] == "True")
        aspect_ratio = float(features["aspect_ratio"])
        is_metallic = (features.get("is_metallic", "False") == "True")
        
        # 判断物品类型（用于智能匹配示例名称）
        item_type = "unknown"
        
        # ========== 第一优先级：形状分析（最可靠的特征）==========
        
        # 细长物品（明显的高 > 宽 或 宽 > 高）：杯子、瓶子、笔等
        is_tall = (0.25 < aspect_ratio < 0.75) or (1.33 < aspect_ratio < 4.0)
        
        # 接近正方形的物品：可能是杯子、盒子、碗等（需要结合其他特征）
        is_square = (0.75 <= aspect_ratio <= 1.33)
        
        # 明显扁平的物品：袋子、纸张、卡片等
        is_flat = (aspect_ratio < 0.25) or (aspect_ratio >= 4.0)
        
        if is_tall:
            item_type = "container_tall"  # 高形容器
            
            # 细长 + 透明/半透明 → 塑料杯/瓶（可回收物）
            if brightness > 0.5 and transparency:
                return (1, f"检测到细长透明物品（长宽比={aspect_ratio:.2f}），判断为可回收物（塑料杯/饮料瓶）", item_type)
            
            # 细长 + 较亮 → 可能是杯子、瓶子（可回收物）
            if brightness > 0.6:
                return (1, f"检测到细长物品（长宽比={aspect_ratio:.2f}），可能是容器类，判断为可回收物", item_type)
            
            # 细长 + 较暗 → 可能是有害垃圾（电池、温度计等）
            if brightness < 0.4:
                return (3, f"检测到细长深色物品，可能为有害垃圾（电池/灯管）", "hazardous_tall")
            
            # 其他细长物品
            return (1, f"检测到细长物品（长宽比={aspect_ratio:.2f}），判断为可回收物", item_type)
        
        # 处理接近正方形的物品（关键改进！区分杯子 vs 盒子 vs 食物 vs 易拉罐）
        if is_square:
            # ⭐⭐⭐ 最高优先级：透明度检测
            if transparency:
                # ⭐ 核心逻辑：透明 + 金属 → 易拉罐/铝罐
                # 原因：塑料餐盒虽然有透明盖子，但不会触发金属检测
                # （计分制：需要满足2个以上金属特征才会触发）
                if is_metallic:
                    item_type = "container_tall"
                    return (1, f"检测到金属光泽特征（长宽比={aspect_ratio:.2f}），判断为可回收物（易拉罐/铝罐）", item_type)
                
                # 高亮透明非金属物品（亮度>0.88）→ 杯子/瓶子
                if brightness > 0.88:
                    item_type = "container_tall"
                    return (1, f"检测到高亮度透明物品（长宽比={aspect_ratio:.2f}），判断为可回收物（塑料杯/饮料瓶）", item_type)
                
                # 中等亮度透明物品（0.55-0.88）→ 餐盒/保鲜盒
                elif brightness > 0.55:
                    item_type = "container_flat"
                    return (1, f"检测到中等亮度透明正方形物品（长宽比={aspect_ratio:.2f}），可能是餐盒/保鲜盒，判断为可回收物", item_type)
                
                # 较暗透明物品 → 深色包装
                else:
                    item_type = "container_flat"
                    return (1, f"检测到较暗透明正方形物品（长宽比={aspect_ratio:.2f}），可能是深色包装，判断为可回收物", item_type)
            
            # ⭐⭐ 第二优先级：金属光泽检测（仅当非透明时）
            if is_metallic:
                item_type = "container_tall"
                return (1, f"检测到金属光泽特征（长宽比={aspect_ratio:.2f}），判断为可回收物（易拉罐/铝罐）", item_type)
            
            # 第二优先级：高亮度非透明物品 → 可能是白色容器（杯子、碗、纸盒）
            if brightness > 0.75:
                if brightness > 0.82:
                    item_type = "container_tall"
                    return (1, f"检测到高亮度正方形物品（长宽比={aspect_ratio:.2f}），可能是白色容器类，判断为可回收物", item_type)
                else:
                    item_type = "container_flat"
                    return (1, f"检测到中等偏高亮度正方形物品（长宽比={aspect_ratio:.2f}），可能是餐盒或纸盒，判断为可回收物", item_type)
            
            # 第三优先级：中等亮度（且无透明）→ 大概率是容器，小概率是食物
            # ⚠️ 重要改进：校园场景中，正方形物品更多是容器（餐盒、杯子）而不是食物残渣
            # 只有满足以下条件才判断为食物：
            #   1. 明显的暖色调（红、橙、黄、绿）
            #   2. 且亮度偏低（< 0.65）
            if 0.4 < brightness <= 0.75:
                # 检查是否是明显的食物颜色
                food_colors = ["red_orange", "orange_yellow", "yellow", "green"]
                
                if color in food_colors and brightness < 0.65:
                    item_type = "food"
                    return (0, f"检测到接近正方形的中等亮度暖色调物品（长宽比={aspect_ratio:.2f}），可能为有机物/食物，判断为厨余垃圾", item_type)
                else:
                    # 默认情况：判断为可回收物（容器或包装）
                    item_type = "container_flat"
                    return (1, f"检测到接近正方形的中等亮度物品（长宽比={aspect_ratio:.2f}），可能是餐盒或包装材料，判断为可回收物", item_type)
            
            # 正方形 + 较暗 → 区分：有机物（厨余）vs 无机物（其他垃圾）
            if brightness <= 0.4:
                # ⭐ 关键改进：根据颜色区分暗色物品的类型
                # 暖色调暗色（褐、红、橙、黄）→ 可能是有机物/腐烂物 → 厨余垃圾
                # 冷色调或中性色暗色（灰、黑、蓝）→ 无机物 → 其他垃圾
                
                organic_colors = ["red_orange", "orange_yellow", "yellow"]  # 褐色、土黄色等
                plant_color = ["green"]  # 绿色（枯叶等）
                
                if color in organic_colors or color in plant_color:
                    item_type = "food"
                    return (0, f"检测到接近正方形的暗色{color}调物品（长宽比={aspect_ratio:.2f}），可能为有机物残渣/果核，判断为厨余垃圾", item_type)
                else:
                    item_type = "misc_dark"
                    return (2, f"检测到接近正方形的暗色物品（长宽比={aspect_ratio:.2f}），判断为其他垃圾", item_type)
        
        if is_flat:
            item_type = "container_flat"  # 扁平容器
            
            # 扁平 + 透明 → 塑料袋（其他垃圾）
            if transparency and brightness > 0.5:
                return (2, f"检测到扁平透明物品，判断为其他垃圾（受污染塑料袋/包装）", item_type)
            
            # 扁平 + 很亮 → 纸张、纸盒（可回收物）
            if brightness > 0.75:
                return (1, f"检测到扁平高亮物品，可能是纸张/纸盒，判断为可回收物", "paper")
            
            # 其他扁平物品
            return (2, f"检测到扁平物品，判断为其他垃圾", item_type)
        
        # ========== 第二优先级：颜色分析 ==========
        
        # 暖色调（红橙黄）→ 食物/厨余垃圾
        if color in ["red_orange", "orange_yellow", "yellow"] and 0.3 < brightness < 0.85:
            return (0, f"检测到暖色调（{color}），可能为有机物/食物，判断为厨余垃圾", "food")
        
        # 绿色调 → 植物/厨余垃圾
        if color == "green":
            return (0, f"检测到绿色调，可能为植物类，判断为厨余垃圾", "plant")
        
        # 蓝色/紫色调 → 包装材料
        if color in ["blue", "purple"]:
            if brightness > 0.5:
                return (1, f"检测到冷色调包装材料，判断为可回收物", "packaging")
            else:
                return (2, f"检测到深色物品，判断为其他垃圾", "misc")
        
        # ========== 第三优先级：亮度兜底 ==========
        
        if brightness > 0.7:
            return (1, f"图像整体偏亮，判断为可回收物", "misc_bright")
        elif brightness < 0.35:
            return (2, f"图像整体偏暗，判断为其他垃圾", "misc_dark")
        else:
            return (2, f"无法确定具体类型，默认归类为其他垃圾", "misc")
    
    @staticmethod
    def calculate_confidence(features: dict, class_index: int) -> float:
        """
        计算演示模式的模拟置信度
        基于特征匹配的强度给出合理的置信度值（60%-95%）
        
        :param features: 图像特征字典
        :param class_index: 分类结果
        :return: 0.0-1.0 之间的置信度值
        """
        confidence = 0.6  # 基础置信度 60%
        
        color = features["dominant_color"]
        brightness = float(features["brightness"])
        transparency = (features["transparency"] == "True")
        aspect_ratio = float(features["aspect_ratio"])
        
        # 1. 形状匹配加分（最可靠的特征，+15%）
        is_tall = (0.25 < aspect_ratio < 0.75) or (1.33 < aspect_ratio < 4.0)
        is_square = (0.75 <= aspect_ratio <= 1.33)
        is_flat = (aspect_ratio < 0.25) or (aspect_ratio >= 4.0)
        
        if is_tall or is_square or is_flat:
            confidence += 0.15
        
        # 2. 亮度匹配加分（+10%）
        if 0.5 < brightness < 0.9:
            confidence += 0.10  # 中等高亮度最容易识别
        elif brightness > 0.7:
            confidence += 0.05  # 很亮也还行
        
        # 3. 颜色匹配加分（+5%）
        distinct_colors = ["red_orange", "green", "blue"]  # 容易区分的颜色
        if color in distinct_colors:
            confidence += 0.05
        
        # 4. 透明度检测加分（+5%）
        if transparency:
            confidence += 0.05
        
        # 5. 根据分类类型微调
        if class_index == 1:  # 可回收物通常更容易通过形状识别
            confidence += 0.05
        elif class_index == 0:  # 厨余垃圾依赖颜色，稍微难一点
            confidence -= 0.02
        
        # 确保置信度在合理范围内
        confidence = max(0.60, min(0.95, confidence))
        
        return confidence


# ==================== 视觉推理引擎 ====================
class VisionEngine:
    """
    图像分类推理引擎（支持ONNX和PyTorch格式）
    - ONNX格式: 使用onnxruntime推理
    - .pt格式: 使用ultralytics YOLOv8推理
    """

    def __init__(self, model_path: str):
        self.session = None  # ONNX session
        self.yolo_model = None  # Ultralytics YOLO model
        self.input_name: str = ""
        self.output_name: str = ""
        self.is_loaded: bool = False
        self.num_classes: int = 0
        self.is_waste_model: bool = False
        self.is_yolo_model: bool = False
        self.is_pt_model: bool = False  # 新增：是否为.pt格式模型
        self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """加载模型文件（自动检测格式）"""
        model_file = Path(model_path)
        if not model_file.exists():
            logger.warning("模型文件不存在: %s，视觉推理功能不可用", model_path)
            return

        try:
            # 判断文件格式
            if model_file.suffix == '.pt':
                self._load_pytorch_model(model_path)
            else:
                self._load_onnx_model(model_path)

            self.is_loaded = True
            logger.info("✅ 模型加载成功: %s (格式: %s, 类别数: %d)",
                       model_path, "PyTorch" if self.is_pt_model else "ONNX",
                       self.num_classes)
        except Exception as e:
            logger.error("❌ 模型加载失败: %s", e)

    def _load_pytorch_model(self, model_path: str) -> None:
        """加载PyTorch格式的YOLOv8模型"""
        from ultralytics import YOLO

        logger.info("📦 加载YOLOv8 PyTorch模型: %s", model_path)
        self.yolo_model = YOLO(str(model_path))
        self.is_pt_model = True
        self.is_yolo_model = True
        self.is_waste_model = True
        self.num_classes = len(self.yolo_model.names)

        logger.info("🎯 YOLOv8类别列表:")
        for idx, name in self.yolo_model.names.items():
            logger.info("   %d: %s", idx, name)

    def _load_onnx_model(self, model_path: str) -> None:
        """加载ONNX格式模型"""
        self.session = ort.InferenceSession(str(model_path))
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        output_shape = self.session.get_outputs()[0].shape

        # 判断模型类型（原有逻辑）
        if len(output_shape) == 3:
            last_dim = output_shape[-1] if output_shape[-1] is not None else 8400
            mid_dim = output_shape[1] if output_shape[1] is not None else 84

            if mid_dim >= 5 and last_dim > 100:
                self.num_classes = mid_dim - 4
                self.is_waste_model = (self.num_classes in [4, 7, 80])
                self.is_yolo_model = True
            elif mid_dim in [84, 80, 56]:
                self.num_classes = mid_dim - 4 - 1
                if self.num_classes <= 0:
                    self.num_classes = 4
                self.is_waste_model = (self.num_classes in [4, 7])
                self.is_yolo_model = True
            else:
                self.num_classes = last_dim
                self.is_waste_model = False
                self.is_yolo_model = False
        elif len(output_shape) == 2:
            self.num_classes = output_shape[-1]
            self.is_waste_model = (self.num_classes == 4)
            self.is_yolo_model = False
        else:
            self.num_classes = 4
            self.is_waste_model = True
            self.is_yolo_model = False

    def predict(self, image: Image.Image) -> dict:
        """执行图像分类推理（自动选择推理引擎）"""
        if not self.is_loaded:
            raise RuntimeError("模型未加载")

        # 根据模型格式选择推理方式
        if self.is_pt_model and self.yolo_model:
            return self._predict_pytorch(image)
        else:
            return self._predict_onnx(image)

    def _predict_pytorch(self, image: Image.Image) -> dict:
        """使用Ultralytics YOLOv8进行PyTorch模型推理"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG')
            tmp_path = tmp.name

        try:
            results = self.yolo_model(
                tmp_path,
                conf=0.25,  # 置信度阈值
                verbose=False,
                imgsz=640
            )

            detections = []
            for r in results:
                boxes = r.boxes

                if len(boxes) > 0:
                    for box in boxes:
                        conf = float(box.conf[0].item())
                        cls_id = int(box.cls[0].item())
                        cls_name = self.yolo_model.names[cls_id]

                        detections.append({
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "confidence": conf,
                            "bbox": box.xyxy[0].tolist() if hasattr(box, 'xyxy') else None,
                        })

            if len(detections) == 0:
                return {
                    "class_index": -1,
                    "confidence": 0.0,
                    "original_class_id": None,
                    "original_class_name": None,
                    "is_demo_mode": True,
                    "detections": [],
                }

            # 选择置信度最高的检测结果
            best = max(detections, key=lambda x: x["confidence"])
            class_id = best["class_id"]
            confidence = best["confidence"]
            class_name = best["class_name"]

            logger.info("🎯 YOLOv8检测: %s (ID=%d, 置信度=%.1f%%)",
                       class_name, class_id, confidence * 100)

            return {
                "class_index": class_id,
                "confidence": round(confidence, 4),
                "original_class_id": class_id,
                "original_class_name": class_name,
                "is_demo_mode": False,
                "detections": detections,
                "num_classes": self.num_classes,
            }

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _predict_onnx(self, image: Image.Image) -> dict:
        """使用ONNX Runtime进行推理"""
        input_tensor = self._preprocess(image)
        output = self.session.run(
            [self.output_name],
            {self.input_name: input_tensor},
        )
        return self._postprocess(output[0])

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """图像预处理 - 根据模型类型选择不同的预处理方式"""
        if self.is_yolo_model:
            # YOLOv8 预处理: 640x640, 简单归一化
            resized = image.resize(YOLO_INPUT_SIZE)
            img_array = np.array(resized).astype(np.float32) / 255.0
            chw = img_array.transpose(2, 0, 1)
            return np.expand_dims(chw, axis=0).astype(np.float32)
        else:
            # ImageNet/分类模型预处理: 224x224, ImageNet归一化
            resized = image.resize(INPUT_SIZE)
            img_array = np.array(resized).astype(np.float32) / 255.0
            normalized = (img_array - IMAGENET_MEAN) / IMAGENET_STD
            chw = normalized.transpose(2, 0, 1)
            return np.expand_dims(chw, axis=0).astype(np.float32)

    def _postprocess(self, output: np.ndarray) -> dict:
        """后处理 - 根据模型类型选择不同的后处理方式"""
        if self.is_yolo_model and self.is_waste_model:
            return self._postprocess_yolo(output)
        else:
            return self._postprocess_classification(output)
    
    def _postprocess_yolo(self, output: np.ndarray) -> dict:
        """YOLOv8 检测模型后处理 - 支持4类和7类模型（修复版）"""
        # YOLOv8 输出格式: [batch, channels, detections]
        # channels = 4(bbox) + num_classes
        # 需要转置为 [batch, detections, channels]

        predictions = output[0].transpose(1, 0)  # [8400, channels]

        # 提取边界框和类别概率（原始logits）
        boxes = predictions[:, :4]  # [cx, cy, w, h]
        class_logits = predictions[:, 4:]  # [class_0, class_1, ..., class_N] (原始logits)

        # ⭐ 关键修复：对类别logits应用sigmoid激活，转换为概率
        # YOLOv8的类别输出是未归一化的logits，需要sigmoid才能得到真正的概率
        class_probs = 1 / (1 + np.exp(-class_logits))  # sigmoid激活

        # 计算每个检测的最大置信度
        class_confidences = np.max(class_probs, axis=1)

        # 找到最高置信度的检测
        conf_threshold = 0.25

        valid_mask = class_confidences > conf_threshold
        if not np.any(valid_mask):
            # 如果没有有效检测，返回最高置信度的那个
            best_idx = np.argmax(class_confidences)
        else:
            # 在有效检测中找最高的
            valid_indices = np.where(valid_mask)[0]
            best_idx = valid_indices[np.argmax(class_confidences[valid_indices])]

        # 获取最佳结果
        confidence = float(class_confidences[best_idx])
        class_id = int(np.argmax(class_probs[best_idx]))

        # 如果是7类模型，映射到中国的4类标准
        if self.num_classes == 7 and class_id in YOLOV8_7CLASSES:
            mapped_category = YOLOV8_7CLASSES[class_id]["category"]
            original_name = YOLOV8_7CLASSES[class_id]["name_cn"]
            return {
                "class_index": mapped_category,
                "confidence": round(confidence, 4),
                "is_demo_mode": False,
                "original_class_id": class_id,
                "original_class_name": original_name,
            }

        # 如果是COCO 80类模型，直接使用映射结果（不触发演示模式）
        if self.num_classes == 80:
            if class_id in COCO_TO_WASTE:
                mapped_category = COCO_TO_WASTE[class_id]["category"]
                original_name = COCO_TO_WASTE[class_id]["name_cn"]
                return {
                    "class_index": mapped_category,
                    "confidence": round(confidence, 4),
                    "is_demo_mode": False,  # COCO模型永远不触发演示模式
                    "original_class_id": class_id,
                    "original_class_name": original_name,
                }
            else:
                # 理论上不会走到这里（已覆盖80类），但保险起见
                return {
                    "class_index": 2,  # 默认其他垃圾
                    "confidence": round(confidence, 4),
                    "is_demo_mode": False,
                    "original_class_id": class_id,
                    "original_class_name": f"COCO_{class_id}",
                }

        return {
            "class_index": class_id,
            "confidence": round(confidence, 4),
            "is_demo_mode": False,
        }
    
    def _postprocess_classification(self, output: np.ndarray) -> dict:
        """普通分类模型后处理"""
        flat_output = output.flatten()
        shifted = flat_output - np.max(flat_output)
        exp_vals = np.exp(shifted)
        probs = exp_vals / exp_vals.sum()
        top_idx = int(np.argmax(probs))
        confidence = round(float(probs[top_idx]), 4)
        
        if self.is_waste_model:
            return {
                "class_index": top_idx,
                "confidence": confidence,
                "is_demo_mode": False,
            }
        
        mapped_index = self._map_to_waste_category(top_idx, confidence)
        
        return {
            "class_index": mapped_index,
            "confidence": confidence,
            "original_index": top_idx,
            "is_demo_mode": True,
        }
    
    def _map_to_waste_category(self, imagenet_index: int, confidence: float) -> int:
        """将ImageNet类别映射到垃圾类别（保留作为后备方案）"""
        if 700 <= imagenet_index <= 999:
            return 0
        elif 100 <= imagenet_index <= 399:
            return 1
        elif (0 <= imagenet_index <= 99) or (400 <= imagenet_index <= 499):
            return 3
        else:
            return 2

    def dispose(self) -> None:
        """释放资源"""
        if self.session:
            del self.session
            self.is_loaded = False


# ==================== 模糊搜索引擎 ====================
class SearchEngine:
    """基于FuzzyWuzzy的模糊搜索引擎"""

    def __init__(self, vocab_path: str):
        self.vocab: list[dict] = []
        self.vocab_labels: list[str] = []
        self._load_vocab(vocab_path)

    def _load_vocab(self, vocab_path: str) -> None:
        """加载词库"""
        vocab_file = Path(vocab_path)
        if not vocab_file.exists():
            logger.warning("词库文件不存在: %s", vocab_path)
            return
        try:
            with open(vocab_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.vocab = data.get("items", [])
            self.vocab_labels = [item["label"] for item in self.vocab]
            # 构建别名到主标签的映射，提升搜索覆盖率
            self._alias_to_label: dict[str, str] = {}
            for item in self.vocab:
                for alias in item.get("aliases", []):
                    if alias and alias not in self._alias_to_label:
                        self._alias_to_label[alias] = item["label"]
            logger.info("词库加载成功: %d 条记录, %d 个别名索引", len(self.vocab), len(self._alias_to_label))
        except Exception as e:
            logger.error("词库加载失败: %s", e)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """执行模糊搜索（同时搜索主标签和别名）"""
        if not self.vocab_labels:
            return []

        # 构建合并搜索池：主标签 + 别名
        all_searchable = list(self.vocab_labels)
        alias_list = list(self._alias_to_label.keys())
        all_searchable.extend(alias_list)

        raw_results = fuzz_process.extract(query, all_searchable, limit=top_k * 2)
        matched = []
        seen_labels = set()

        for match_text, score in raw_results:
            # 如果匹配到的是别名，映射回主标签
            if match_text in self._alias_to_label:
                main_label = self._alias_to_label[match_text]
            else:
                main_label = match_text

            # 去重：同一主标签只保留最高分
            if main_label in seen_labels:
                continue
            seen_labels.add(main_label)

            item = next((v for v in self.vocab if v["label"] == main_label), None)
            if item:
                matched.append({**item, "similarity_score": score})
            if len(matched) >= top_k:
                break

        return matched

    def get_by_yolo_label(self, yolo_label: str) -> Optional[dict]:
        """根据标签查找"""
        for item in self.vocab:
            if item.get("yolo_label") == yolo_label:
                return item
        return None
    
    def get_items_by_category(self, category_id: int) -> list[dict]:
        """获取指定类别的所有物品"""
        return [item for item in self.vocab if item.get("category_id") == category_id]
    
    def get_smart_item(self, category_id: int, item_type: str = "unknown", 
                      is_metallic: bool = False) -> Optional[dict]:
        """
        智能选择物品示例（增强版 v2.1）
        根据类别、物品类型和金属特征选择最合适的示例物品
        解决易拉罐被识别成餐盒的问题
        """
        items_in_category = self.get_items_by_category(category_id)
        if not items_in_category:
            return None
        
        # 物品类型与关键词的映射关系
        type_keyword_map = {
            # 高形容器（杯子、瓶子）→ 优先匹配杯、瓶、饮料相关
            "container_tall": ["塑料杯", "饮料瓶", "矿泉水瓶", "易拉罐", "洗发水瓶", "沐浴露瓶", "保温杯", "水杯"],
            # 扁平容器（袋子、盒子）→ 优先匹配袋、盒、包装相关
            "container_flat": ["塑料袋", "快递纸箱", "包装盒", "泡沫箱", "牛奶盒", "餐盒", "方便面桶"],
            # 食物类 → 优先匹配食物残渣相关
            "food": ["剩饭剩菜", "苹果核", "香蕉皮", "橙子皮", "西瓜皮", "面包渣"],
            # 植物类 → 优先匹配植物相关
            "plant": ["菜叶菜根", "枯枝落叶", "杂草"],
            # 包装材料 → 优先匹配可回收包装
            "packaging": ["报纸", "书本", "旧衣服", "玻璃瓶", "铝罐"],
            # 纸张类 → 优先匹配纸张
            "paper": ["报纸", "书本", "作业本", "打印纸", "用过的纸巾"],
            # 其他情况 → 使用默认匹配
            "misc": None,
            "misc_bright": ["旧衣服", "玩具", "电器"],
            "misc_dark": ["烟蒂", "一次性餐具", "破碎陶瓷", "灰尘"],
            "unknown": None,
        }
        
        # 获取当前类型的关键词列表
        keywords = type_keyword_map.get(item_type)
        
        if keywords:
            # 根据关键词过滤匹配的物品
            matched_items = []
            for item in items_in_category:
                label = item.get("label", "")
                for kw in keywords:
                    if kw in label:
                        matched_items.append(item)
                        break
            
            if matched_items:
                # 从匹配项中优先选择最合适的（而非完全随机）
                # 对于容器类，根据是否有金属特征选择不同的优先级
                if is_metallic and item_type == "container_tall":
                    # 有金属特征 → 优先返回易拉罐/铝罐
                    preferred_order = {
                        "container_tall": ["易拉罐", "铝罐", "饮料瓶", "矿泉水瓶"],
                    }
                else:
                    # 无金属特征 → 使用默认优先级
                    preferred_order = {
                        "container_tall": ["塑料杯", "饮料瓶", "矿泉水瓶"],  # 普通容器
                        "container_flat": ["包装盒", "餐盒", "牛奶盒", "方便面桶", "泡沫箱"],
                        "food": ["剩饭剩菜", "苹果核", "香蕉皮"],
                    }
                
                pref_list = preferred_order.get(item_type, [])
                
                # 优先按顺序返回
                for pref_name in pref_list:
                    for item in matched_items:
                        if item.get("label") == pref_name:
                            logger.info("优先匹配: 类型=%s → %s", item_type, pref_name)
                            return item
                
                # 如果没有优先匹配，返回第一个匹配项（稳定但不是完全随机）
                return matched_items[0]
        
        # 如果没有匹配到，返回该类别中的随机物品
        return random.choice(items_in_category)


# ==================== 全局实例初始化 ====================
vision_engine: Optional[VisionEngine] = None
search_engine: Optional[SearchEngine] = None
history_store: Optional[HistoryStore] = None
feedback_store: Optional[FeedbackStore] = None
inference_cache: Optional[InferenceCache] = None
disposal_steps_data: dict = {}


@app.on_event("startup")
def startup_event() -> None:
    """应用启动时初始化"""
    global vision_engine, search_engine, history_store, feedback_store, inference_cache, disposal_steps_data
    logger.info("正在初始化服务...")
    vision_engine = VisionEngine(str(MODEL_PATH))
    search_engine = SearchEngine(str(VOCAB_PATH))
    history_store = HistoryStore(backup_path=BASE_DIR / "data" / "history.json")
    feedback_store = FeedbackStore(backup_path=BASE_DIR / "data" / "feedback.json")

    inference_cache = InferenceCache(max_size=500, ttl_seconds=86400)

    steps_file = BASE_DIR / "data" / "disposal_steps.json"
    if steps_file.exists():
        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                disposal_steps_data = json.load(f).get("steps", {})
            logger.info("处理步骤数据加载完成: %d 条", len(disposal_steps_data))
        except Exception as e:
            logger.warning("处理步骤数据加载失败: %s", e)

    db.connect()
    db.init_tables()
    db.seed_disposal_points()
    db.seed_quiz_questions()
    db.seed_activities()

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    logger.info("服务初始化完成")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """应用关闭时释放资源"""
    global vision_engine
    if vision_engine:
        vision_engine.dispose()
        vision_engine = None
    logger.info("服务已关闭")


# ==================== API 路由定义 ====================


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    """根路径：返回前端页面"""
    html_path = Path(INDEX_HTML_PATH)
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(
        content="<h1>前端页面未找到</h1>",
        status_code=404,
    )


@app.post("/api/predict")
async def predict_waste(request: PredictRequest) -> JSONResponse:
    """
    图像分类识别接口（增强版）
    支持智能演示模式，基于图像特征分析提高分类准确性
    支持分阶段耗时记录（预处理/推理/后处理）
    """
    start_time = time.time()
    timing = {"preprocess_ms": 0, "inference_ms": 0, "postprocess_ms": 0}

    try:
        if "," in request.image:
            _, encoded_data = request.image.split(",", 1)
        else:
            encoded_data = request.image
        image_data = base64.b64decode(encoded_data)
        image = Image.open(BytesIO(image_data)).convert("RGB")
        timing["preprocess_ms"] = int((time.time() - start_time) * 1000)
        logger.info("图片解码成功，尺寸: %s (预处理耗时=%dms)", image.size, timing["preprocess_ms"])

        if inference_cache:
            try:
                cache_key = inference_cache._make_key(image_data)
                cached_result = inference_cache.get(cache_key)
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

    if not vision_engine or not vision_engine.is_loaded:
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
        result = vision_engine.predict(image)
        timing["inference_ms"] = int((time.time() - inference_start) * 1000)

        postprocess_start = time.time()
        inference_ms = int((time.time() - start_time) * 1000)
        req_id = uuid.uuid4().hex[:12]

        # ===== 智能策略选择 =====
        # 40类专用模型：直接使用YOLO检测结果（无需特征分析）
        # COCO/通用模型：使用混合策略（YOLO + 特征分析）

        if vision_engine.is_pt_model and vision_engine.num_classes >= 40:
            # 40类专用垃圾分类模型 - 直接使用结果
            logger.info("🎯 使用40类专用模型结果 (ID=%s, 名称=%s, 置信度=%.1f%%)",
                       result.get("original_class_id"),
                       result.get("original_class_name"),
                       result.get("confidence", 0) * 100)

            original_class_id = result.get("original_class_id", -1)

            # 将40类ID映射到中国4类垃圾系统
            if original_class_id in GARBAGE_40CLASSES:
                class_mapping = GARBAGE_40CLASSES[original_class_id]
                category_4class = class_mapping["category"]  # 0-3 对应4类
                class_name_cn = class_mapping["name_cn"]

                result["class_index"] = category_4class
                result["original_class_name"] = class_name_cn
                result["reasoning"] = f"40类模型检测: {class_name_cn}"
                result["is_demo_mode"] = False

                logger.info("✅ 40类映射: ID=%d → %s (类别=%d)",
                           original_class_id, class_name_cn, category_4class)
            else:
                logger.warning("⚠️ 未知类别ID: %d", original_class_id)
                result["is_demo_mode"] = True

        else:
            # 旧版COCO/ONNX模型 - 使用混合策略v3.1
            original_class_id = result.get("original_class_id")

            HIGH_CONFIDENCE_CONTAINER_CLASSES = {39, 40, 41, 45}

            use_yolo_result = (
                not result.get("is_demo_mode") and
                original_class_id is not None and
                original_class_id in HIGH_CONFIDENCE_CONTAINER_CLASSES and
                vision_engine.num_classes == 80 and
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

                old_index = result["class_index"]
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
            response_data["demo_notice"] = "🔬 智能演示模式：基于图像特征分析（颜色、透明度、形状等），非专门训练的垃圾分类模型"

        if history_store:
            history_store.add({
                "category": class_info.get("category", ""),
                "category_id": class_info.get("category_id", -1),
                "label_cn": class_info.get("label_cn", ""),
                "bin_color": class_info.get("bin_color", ""),
                "confidence": result.get("confidence", 0),
                "guidance": class_info.get("guidance", ""),
                "is_demo_mode": result.get("is_demo_mode", False),
            })

        if inference_cache and 'cache_key' in locals():
            try:
                inference_cache.set(cache_key, response_data["result"])
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
        import traceback
        logger.error("堆栈:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "E003", "message": "服务器内部错误，请稍后重试"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


@app.get("/api/search")
async def search_waste(query: str = Query(..., min_length=1, max_length=100)) -> JSONResponse:
    """模糊搜索接口"""
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


@app.get("/api/categories")
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


@app.get("/api/guide/standard")
async def get_guide_standard() -> JSONResponse:
    """获取完整的校园垃圾分类标准数据"""
    guide_file = BASE_DIR / "data" / "guide_standard.json"
    if not guide_file.exists():
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "分类标准数据文件不存在"}}
        )

    try:
        with open(guide_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(
            content={
                "success": True,
                "categories": data.get("categories", []),
                "version": data.get("version", "1.0"),
            }
        )
    except Exception as e:
        logger.error("[GuideAPI] 读取分类标准数据失败: %s", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E003", "message": "读取分类标准数据失败"}}
        )


@app.get("/api/guide/category/{category_id}")
async def get_guide_category(category_id: int) -> JSONResponse:
    """获取单个类别的详细分类标准"""
    if category_id not in (0, 1, 2, 3):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": {"code": "E001", "message": "类别ID必须为0-3"}}
        )

    guide_file = BASE_DIR / "data" / "guide_standard.json"
    if not guide_file.exists():
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "分类标准数据文件不存在"}}
        )

    try:
        with open(guide_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for cat in data.get("categories", []):
            if cat.get("id") == category_id:
                items_in_category = search_engine.get_items_by_category(category_id) if search_engine else []
                cat["vocab_items"] = [
                    {"label": item["label"], "aliases": item.get("aliases", []), "guidance": item.get("guidance", "")}
                    for item in items_in_category
                ]
                return JSONResponse(content={"success": True, "category": cat})

        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": f"未找到类别 {category_id}"}}
        )
    except Exception as e:
        logger.error("[GuideAPI] 读取分类标准数据失败: %s", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E003", "message": "读取分类标准数据失败"}}
        )


@app.get("/api/guide/confusing")
async def get_confusing_pairs(limit: int = 10, frequency: str = "") -> JSONResponse:
    """获取易混淆物品对比列表"""
    pairs_file = BASE_DIR / "data" / "confusing_pairs.json"
    if not pairs_file.exists():
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "易混淆数据文件不存在"}}
        )

    try:
        with open(pairs_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        pairs = data.get("pairs", [])

        if frequency:
            pairs = [p for p in pairs if p.get("frequency") == frequency]

        pairs = sorted(pairs, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("frequency", "medium"), 2))

        total = len(pairs)
        pairs = pairs[:limit]

        return JSONResponse(content={
            "success": True,
            "pairs": pairs,
            "total": total,
        })
    except Exception as e:
        logger.error("[GuideAPI] 读取易混淆数据失败: %s", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E003", "message": "读取易混淆数据失败"}}
        )


@app.get("/api/guide/confusing/{pair_id}")
async def get_confusing_pair(pair_id: int) -> JSONResponse:
    """获取单个易混淆物品对比详情"""
    pairs_file = BASE_DIR / "data" / "confusing_pairs.json"
    if not pairs_file.exists():
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "易混淆数据文件不存在"}}
        )

    try:
        with open(pairs_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        for pair in data.get("pairs", []):
            if pair.get("id") == pair_id:
                return JSONResponse(content={"success": True, "pair": pair})

        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": f"未找到对比组 {pair_id}"}}
        )
    except Exception as e:
        logger.error("[GuideAPI] 读取易混淆数据失败: %s", e)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E003", "message": "读取易混淆数据失败"}}
        )


@app.get("/api/guide/item/{keyword}")
async def get_guide_item(keyword: str) -> JSONResponse:
    """获取物品详情（含处理步骤+相关物品+易错对比）"""
    if not search_engine:
        return JSONResponse(status_code=503, content={"success": False})

    results = search_engine.search(keyword, top_k=1)
    if not results:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": f"未找到物品 '{keyword}'"}}
        )

    item = results[0]

    disposal_steps = []
    disposal_tips = []
    steps_file = BASE_DIR / "data" / "disposal_steps.json"
    if steps_file.exists():
        try:
            with open(steps_file, "r", encoding="utf-8") as f:
                steps_data = json.load(f)
            label = item.get("label", "")
            label_steps = steps_data.get("steps", {}).get(label)
            if label_steps:
                disposal_steps = label_steps.get("disposal_steps", [])
                disposal_tips = label_steps.get("tips", [])
        except Exception:
            pass

    same_category = [
        {"label": i["label"], "guidance": i.get("guidance", "")}
        for i in search_engine.vocab
        if i.get("category_id") == item.get("category_id") and i["label"] != item["label"]
    ][:6]

    confusing_pairs = []
    pairs_file = BASE_DIR / "data" / "confusing_pairs.json"
    if pairs_file.exists():
        try:
            with open(pairs_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            keyword_lower = keyword.lower()
            for pair in data.get("pairs", []):
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


@app.post("/api/debug/analyze")
async def debug_analyze_image(request: PredictRequest) -> JSONResponse:
    """调试接口：分析图片的详细特征"""
    try:
        # 兼容 Data URL 格式和纯 Base64 格式
        if "," in request.image:
            _, encoded_data = request.image.split(",", 1)
        else:
            encoded_data = request.image
        image_data = base64.b64decode(encoded_data)
        image = Image.open(BytesIO(image_data)).convert("RGB")
        
        # 分析特征
        features = ImageFeatureAnalyzer.analyze(image)
        
        # 添加额外调试信息
        img_array = np.array(image)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
        
        # 基于特征运行分类（降级模式）
        smart_class_index, reasoning, item_type = ImageFeatureAnalyzer.classify_by_features(features)
        confidence = ImageFeatureAnalyzer.calculate_confidence(features, smart_class_index)
        class_info = _get_class_info(smart_class_index, is_demo_mode=True,
                                    item_type=item_type,
                                    is_metallic=(features.get("is_metallic", "False") == "True"))

        debug_info = {
            "image_size": image.size,
            "aspect_ratio": round(image.width / image.height, 3),
            "features": features,
            "result": {**class_info, "confidence": confidence, "reasoning": reasoning,
                      "is_demo_mode": True},
            "debug_details": {
                "std_dev": round(float(np.std(gray)), 2),
                "mean_brightness": round(float(np.mean(gray)) / 255.0, 4),
                "super_bright_ratio": round(float(np.sum(gray > 240)) / gray.size, 6),
                "gradient_mean": round(float(np.mean(cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)**2 + cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)**2)**0.5), 2),
                "saturation_mean": round(float(np.mean(cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)[:, :, 1])), 1) if len(img_array.shape) == 3 else 0,
            },
            "thresholds": {
                "metallic_std_dev": 50,
                "metallic_super_bright": 0.03,
                "metallic_gradient": 15,
                "metallic_saturation": 120,
                "transparency_std_dev": 40,
                "transparency_high_light": 0.15,
                "transparency_gradient": 30,
            }
        }

        return JSONResponse(content={"success": True, **debug_info})
    
    except Exception as e:
        return JSONResponse(content={"success": False, "error": str(e)})


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """健康检查接口"""
    return JSONResponse(
        content={
            "status": "healthy",
            "model_loaded": vision_engine.is_loaded if vision_engine else False,
            "model_type": "专用垃圾分类模型" if (vision_engine and vision_engine.is_waste_model) else "智能演示模式（图像特征分析）",
            "vocab_loaded": len(search_engine.vocab) > 0 if search_engine else False,
            "uptime_info": "running",
        }
    )


# ==================== 工具函数 ====================


def _get_class_info(class_index: int, is_demo_mode: bool = False,
                   item_type: str = "unknown", is_metallic: bool = False,
                   original_class_name: str = None) -> dict:
    """
    获取类别详细信息（增强版 v2.3）
    支持基于物品类型和金属特征智能选择示例名称
    支持显示7类模型的原始检测名称
    支持从 disposal_steps.json 获取处理建议
    """
    base_info = WASTE_CATEGORIES.get(class_index, WASTE_CATEGORIES[2]).copy()

    info = {
        "category": base_info["name"],
        "category_id": class_index,
        "bin_color": base_info["color"],
        "bin_icon": base_info["icon"],
        "guidance": f"请投入{base_info['bin_color']}{base_info['name']}桶",
        "label_cn": original_class_name if original_class_name else "识别物品",
        "tips": None,
    }

    use_vocab_name = (original_class_name is None or original_class_name == "")

    if search_engine and search_engine.vocab and use_vocab_name:
        if is_demo_mode:
            sample_item = search_engine.get_smart_item(class_index, item_type, is_metallic)
            if sample_item:
                info.update({
                    "label_cn": sample_item.get("label", "示例物品"),
                    "category": sample_item.get("category_name", info["category"]),
                    "bin_color": sample_item.get("bin_color", info["bin_color"]),
                    "bin_icon": sample_item.get("bin_icon", info["bin_icon"]),
                    "guidance": sample_item.get("guidance", info["guidance"]),
                    "yolo_label": sample_item.get("yolo_label", ""),
                })
                logger.info("智能匹配示例: 类别=%d, 类型=%s, 名称=%s", 
                           class_index, item_type, sample_item.get("label"))
        else:
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
                        "yolo_label": matched.get("yolo_label", ""),
                    })

    label = info.get("label_cn", "")
    if disposal_steps_data and label:
        label_steps = disposal_steps_data.get(label)
        if not label_steps:
            for key in disposal_steps_data:
                if key in label or label in key:
                    label_steps = disposal_steps_data[key]
                    break
        if label_steps:
            tips_list = label_steps.get("tips", [])
            if tips_list:
                info["tips"] = "；".join(tips_list)

    return info



# ==================== batch_predict 批量识别 ====================

@app.post("/api/batch_predict")
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

    if not vision_engine or not vision_engine.is_loaded:
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
            # 兼容 Data URL 格式和纯 Base64 格式
            if "," in img_str:
                _, encoded_data = img_str.split(",", 1)
            else:
                encoded_data = img_str
            image_data = base64.b64decode(encoded_data)
            image = Image.open(BytesIO(image_data)).convert("RGB")
        except Exception:
            results.append({
                "index": idx,
                "error": "图片解码失败",
            })
            continue

        # ===== 批量识别中的单张图片缓存检查 =====
        current_cache_key = None
        cached_item = None
        if inference_cache:
            try:
                current_cache_key = inference_cache._make_key(image_data)
                cached_result = inference_cache.get(current_cache_key)
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
                    if history_store:
                        history_store.add({
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
            result = vision_engine.predict(image)
            img_ms = int((time.time() - img_start) * 1000)

            class_index = result.get("class_index", 2)

            # 40类映射
            if vision_engine.is_pt_model and vision_engine.num_classes >= 40:
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
            if inference_cache and current_cache_key:
                try:
                    inference_cache.set(current_cache_key, item)
                except Exception as e:
                    logger.warning("批量识别-第%d张 缓存写入异常（不影响主流程）: %s", idx + 1, e)

            # 写入历史
            if history_store:
                history_store.add({
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


# ==================== history 历史记录 ====================

@app.get("/api/history")
async def get_history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)) -> JSONResponse:
    """获取识别历史记录（分页）"""
    if not history_store:
        return JSONResponse(content={
            "success": True,
            "data": [],
            "pagination": {"total": 0, "page": page, "page_size": page_size, "total_pages": 0},
        })

    result = history_store.get_all(page=page, page_size=page_size)
    result["success"] = True
    return JSONResponse(content=result)


@app.delete("/api/history/{record_id}")
async def delete_history(record_id: str) -> JSONResponse:
    """删除单条历史记录"""
    if not history_store:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "记录不存在"}},
        )

    deleted = history_store.delete(record_id)
    if deleted:
        return JSONResponse(content={"success": True, "message": "已删除"})
    return JSONResponse(
        status_code=404,
        content={"success": False, "error": {"code": "E004", "message": "记录不存在"}},
    )


@app.delete("/api/history")
async def clear_history() -> JSONResponse:
    """清空全部历史记录"""
    if not history_store:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "E004", "message": "无历史记录"}},
        )
    history_store.clear()
    return JSONResponse(content={"success": True, "message": "已清空全部历史记录"})


# ==================== feedback 用户反馈 ====================

@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest) -> JSONResponse:
    """提交识别结果反馈"""
    if request.predicted_category_id not in (0, 1, 2, 3):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "predicted_category_id 必须为 0-3"},
            },
        )
    if request.correct_category_id not in (0, 1, 2, 3):
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {"code": "E001", "message": "correct_category_id 必须为 0-3"},
            },
        )

    if not feedback_store:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": {"code": "E006", "message": "反馈服务未就绪"}},
        )

    # 仅存储图片哈希摘要，避免大量 Base64 数据撑爆内存
    image_hash = hashlib.sha256(request.image_base64.encode("utf-8")).hexdigest()[:16]
    feedback_id = feedback_store.add({
        "image_hash": image_hash,
        "predicted_category_id": request.predicted_category_id,
        "correct_category_id": request.correct_category_id,
        "comment": request.comment[:500],  # 限制评论长度
    })

    logger.info("📝 收到用户反馈: %s, 预测=%d, 正确=%d", feedback_id,
                request.predicted_category_id, request.correct_category_id)

    return JSONResponse(content={
        "success": True,
        "message": "反馈已提交，感谢您的帮助",
        "feedback_id": feedback_id,
    })


# ==================== 第三阶段：用户系统 + 地图 + 打卡 + 问答 + 活动 ====================

SESSION_COOKIE_NAME = "session_id"
SESSION_EXPIRE_SECONDS = 86400 * 7


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    password: str = Field(..., min_length=6, max_length=32)
    nickname: str = Field("", max_length=20)


class LoginRequest(BaseModel):
    username: str
    password: str


class CheckinRequest(BaseModel):
    point_id: str = ""
    lat: float = 0
    lng: float = 0
    category: str = ""


class QuizAnswerRequest(BaseModel):
    question_id: str
    selected: int = Field(..., ge=0, le=3)


class ActivitySignupRequest(BaseModel):
    activity_id: str


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_current_user(request: Request) -> Optional[dict]:
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        return None
    try:
        c = db.conn.cursor()
        c.execute("SELECT user_id FROM sessions WHERE id = ? AND expires_at > ?", (session_id, time.time()))
        row = c.fetchone()
        if not row:
            return None
        c.execute("SELECT id, username, nickname, avatar, points, checkin_count, quiz_correct, quiz_total FROM users WHERE id = ?", (row["user_id"],))
        user = c.fetchone()
        return dict(user) if user else None
    except Exception:
        return None


def _create_session(user_id: str) -> str:
    session_id = uuid.uuid4().hex
    now = time.time()
    db.conn.execute(
        "INSERT INTO sessions (id, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (session_id, user_id, now, now + SESSION_EXPIRE_SECONDS)
    )
    db.conn.commit()
    return session_id


# ---------- F-3.2 用户系统 ----------

@app.post("/api/auth/register")
async def register(req: RegisterRequest, response: Response):
    try:
        c = db.conn.cursor()
        c.execute("SELECT id FROM users WHERE username = ?", (req.username,))
        if c.fetchone():
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E409", "message": "用户名已存在"}})

        user_id = uuid.uuid4().hex[:12]
        now = time.time()
        db.conn.execute(
            "INSERT INTO users (id, username, password_hash, nickname, created_at, last_login) VALUES (?,?,?,?,?,?)",
            (user_id, req.username, _hash_password(req.password), req.nickname or req.username, now, now)
        )
        db.conn.commit()

        session_id = _create_session(user_id)
        response = JSONResponse(content={
            "success": True,
            "user": {"id": user_id, "username": req.username, "nickname": req.nickname or req.username, "points": 0}
        })
        response.set_cookie(SESSION_COOKIE_NAME, session_id, max_age=SESSION_EXPIRE_SECONDS, httponly=True, samesite="lax")
        return response
    except Exception as e:
        logger.error("注册失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "注册失败，请稍后重试"}})


@app.post("/api/auth/login")
async def login(req: LoginRequest, response: Response):
    try:
        c = db.conn.cursor()
        c.execute("SELECT id, username, password_hash, nickname, points FROM users WHERE username = ?", (req.username,))
        user = c.fetchone()
        if not user or user["password_hash"] != _hash_password(req.password):
            return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "用户名或密码错误"}})

        db.conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (time.time(), user["id"]))
        db.conn.commit()

        session_id = _create_session(user["id"])
        resp = JSONResponse(content={
            "success": True,
            "user": {"id": user["id"], "username": user["username"], "nickname": user["nickname"], "points": user["points"]}
        })
        resp.set_cookie(SESSION_COOKIE_NAME, session_id, max_age=SESSION_EXPIRE_SECONDS, httponly=True, samesite="lax")
        return resp
    except Exception as e:
        logger.error("登录失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "登录失败"}})


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        try:
            db.conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            db.conn.commit()
        except Exception:
            pass
    resp = JSONResponse(content={"success": True, "message": "已退出登录"})
    resp.delete_cookie(SESSION_COOKIE_NAME)
    return resp


@app.get("/api/auth/me")
async def get_current_user(request: Request):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "未登录"}})
    return JSONResponse(content={"success": True, "user": user})


# ---------- F-3.1 投放点地图 ----------

@app.get("/api/map/points")
async def get_disposal_points(zone: str = "", category: str = ""):
    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM disposal_points")
        rows = c.fetchall()
        points = []
        for row in rows:
            p = dict(row)
            p["categories"] = json.loads(p["categories"]) if isinstance(p["categories"], str) else p["categories"]
            if zone and p.get("campus_zone") != zone:
                continue
            if category and category not in p.get("categories", []):
                continue
            points.append(p)
        return JSONResponse(content={"success": True, "points": points, "total": len(points)})
    except Exception as e:
        logger.error("获取投放点失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点失败"}})


@app.get("/api/map/point/{point_id}")
async def get_disposal_point(point_id: str):
    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM disposal_points WHERE id = ?", (point_id,))
        row = c.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "投放点不存在"}})
        p = dict(row)
        p["categories"] = json.loads(p["categories"]) if isinstance(p["categories"], str) else p["categories"]
        return JSONResponse(content={"success": True, "point": p})
    except Exception as e:
        logger.error("获取投放点详情失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取投放点详情失败"}})


# ---------- F-3.3 环保打卡 ----------

@app.post("/api/checkin")
async def create_checkin(request: Request, req: CheckinRequest):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        today_start = time.time() - (time.time() % 86400)
        c.execute("SELECT id FROM checkins WHERE user_id = ? AND created_at > ?", (user["id"], today_start))
        if c.fetchone():
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "今日已打卡"}})

        checkin_id = uuid.uuid4().hex[:12]
        points_earned = 5
        now = time.time()
        db.conn.execute(
            "INSERT INTO checkins (id, user_id, point_id, lat, lng, category, points_earned, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (checkin_id, user["id"], req.point_id, req.lat, req.lng, req.category, points_earned, now)
        )
        db.conn.execute("UPDATE users SET points = points + ?, checkin_count = checkin_count + 1 WHERE id = ?",
                        (points_earned, user["id"]))
        db.conn.commit()

        return JSONResponse(content={
            "success": True,
            "checkin": {"id": checkin_id, "points_earned": points_earned},
            "message": f"打卡成功！获得 {points_earned} 积分"
        })
    except Exception as e:
        logger.error("打卡失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "打卡失败"}})


@app.get("/api/checkin/today")
async def get_today_checkin(request: Request):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        today_start = time.time() - (time.time() % 86400)
        c.execute("SELECT * FROM checkins WHERE user_id = ? AND created_at > ?", (user["id"], today_start))
        row = c.fetchone()
        return JSONResponse(content={"success": True, "checked_in": row is not None, "checkin": dict(row) if row else None})
    except Exception as e:
        logger.error("获取打卡状态失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取打卡状态失败"}})


@app.get("/api/checkin/history")
async def get_checkin_history(request: Request, page: int = 1, page_size: int = 20):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        offset = (page - 1) * page_size
        c.execute("SELECT COUNT(*) FROM checkins WHERE user_id = ?", (user["id"],))
        total = c.fetchone()[0]
        c.execute("SELECT * FROM checkins WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                  (user["id"], page_size, offset))
        records = [dict(row) for row in c.fetchall()]
        return JSONResponse(content={"success": True, "records": records, "total": total, "page": page})
    except Exception as e:
        logger.error("获取打卡历史失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取打卡历史失败"}})


# ---------- F-3.4 知识问答 ----------

@app.get("/api/quiz/daily")
async def get_daily_quiz(request: Request):
    user = _get_current_user(request)

    try:
        c = db.conn.cursor()
        today_start = time.time() - (time.time() % 86400)

        if user:
            c.execute("SELECT question_id FROM quiz_records WHERE user_id = ? AND created_at > ?", (user["id"], today_start))
            answered = [row["question_id"] for row in c.fetchall()]
        else:
            answered = []

        c.execute("SELECT * FROM quiz_questions")
        all_questions = [dict(row) for row in c.fetchall()]

        unanswered = [q for q in all_questions if q["id"] not in answered]
        if not unanswered:
            return JSONResponse(content={"success": True, "quiz": None, "message": "今日题目已全部完成"})

        quiz = random.choice(unanswered)
        quiz["options"] = json.loads(quiz["options"]) if isinstance(quiz["options"], str) else quiz["options"]
        return JSONResponse(content={"success": True, "quiz": quiz})
    except Exception as e:
        logger.error("获取每日问答失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取问答失败"}})


@app.post("/api/quiz/answer")
async def answer_quiz(request: Request, req: QuizAnswerRequest):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM quiz_questions WHERE id = ?", (req.question_id,))
        question = c.fetchone()
        if not question:
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E404", "message": "题目不存在"}})

        is_correct = req.selected == question["answer"]
        points_earned = 3 if is_correct else 0
        record_id = uuid.uuid4().hex[:12]
        now = time.time()

        db.conn.execute(
            "INSERT INTO quiz_records (id, user_id, question_id, selected, is_correct, points_earned, created_at) VALUES (?,?,?,?,?,?,?)",
            (record_id, user["id"], req.question_id, req.selected, int(is_correct), points_earned, now)
        )
        if is_correct:
            db.conn.execute("UPDATE users SET points = points + ?, quiz_correct = quiz_correct + 1, quiz_total = quiz_total + 1 WHERE id = ?",
                            (points_earned, user["id"]))
        else:
            db.conn.execute("UPDATE users SET quiz_total = quiz_total + 1 WHERE id = ?", (user["id"],))
        db.conn.commit()

        options = json.loads(question["options"]) if isinstance(question["options"], str) else question["options"]
        return JSONResponse(content={
            "success": True,
            "result": {
                "is_correct": is_correct,
                "correct_answer": question["answer"],
                "explanation": question["explanation"],
                "points_earned": points_earned,
                "options": options
            }
        })
    except Exception as e:
        logger.error("回答问答失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "提交答案失败"}})


# ---------- F-3.5 环保活动 ----------

@app.get("/api/activities")
async def get_activities(status: str = "", page: int = 1, page_size: int = 10):
    try:
        c = db.conn.cursor()
        offset = (page - 1) * page_size
        if status:
            c.execute("SELECT COUNT(*) FROM activities WHERE status = ?", (status,))
            total = c.fetchone()[0]
            c.execute("SELECT * FROM activities WHERE status = ? ORDER BY start_time DESC LIMIT ? OFFSET ?",
                      (status, page_size, offset))
        else:
            c.execute("SELECT COUNT(*) FROM activities")
            total = c.fetchone()[0]
            c.execute("SELECT * FROM activities ORDER BY start_time DESC LIMIT ? OFFSET ?", (page_size, offset))

        activities = []
        for row in c.fetchall():
            a = dict(row)
            a["start_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["start_time"]))
            a["end_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["end_time"]))
            activities.append(a)
        return JSONResponse(content={"success": True, "activities": activities, "total": total, "page": page})
    except Exception as e:
        logger.error("获取活动列表失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取活动列表失败"}})


@app.get("/api/activities/{activity_id}")
async def get_activity(activity_id: str):
    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM activities WHERE id = ?", (activity_id,))
        row = c.fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})
        a = dict(row)
        a["start_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["start_time"]))
        a["end_time_iso"] = time.strftime("%Y-%m-%dT%H:%M", time.localtime(a["end_time"]))
        return JSONResponse(content={"success": True, "activity": a})
    except Exception as e:
        logger.error("获取活动详情失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "获取活动详情失败"}})


@app.post("/api/activities/signup")
async def signup_activity(request: Request, req: ActivitySignupRequest):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(status_code=401, content={"success": False, "error": {"code": "E401", "message": "请先登录"}})

    try:
        c = db.conn.cursor()
        c.execute("SELECT * FROM activities WHERE id = ?", (req.activity_id,))
        activity = c.fetchone()
        if not activity:
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E404", "message": "活动不存在"}})

        if activity["status"] != "open":
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "活动已截止报名"}})

        if activity["max_participants"] > 0 and activity["current_participants"] >= activity["max_participants"]:
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E400", "message": "活动名额已满"}})

        c.execute("SELECT id FROM activity_signups WHERE activity_id = ? AND user_id = ?", (req.activity_id, user["id"]))
        if c.fetchone():
            return JSONResponse(status_code=400, content={"success": False, "error": {"code": "E409", "message": "已报名该活动"}})

        signup_id = uuid.uuid4().hex[:12]
        now = time.time()
        db.conn.execute(
            "INSERT INTO activity_signups (id, activity_id, user_id, created_at) VALUES (?,?,?,?)",
            (signup_id, req.activity_id, user["id"], now)
        )
        db.conn.execute("UPDATE activities SET current_participants = current_participants + 1 WHERE id = ?", (req.activity_id,))
        db.conn.commit()

        return JSONResponse(content={"success": True, "message": "报名成功", "signup_id": signup_id})
    except Exception as e:
        logger.error("活动报名失败: %s", e)
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "E500", "message": "报名失败"}})


@app.get("/api/activities/{activity_id}/signed")
async def check_activity_signup(request: Request, activity_id: str):
    user = _get_current_user(request)
    if not user:
        return JSONResponse(content={"success": True, "signed_up": False})

    try:
        c = db.conn.cursor()
        c.execute("SELECT id FROM activity_signups WHERE activity_id = ? AND user_id = ?", (activity_id, user["id"]))
        return JSONResponse(content={"success": True, "signed_up": c.fetchone() is not None})
    except Exception:
        return JSONResponse(content={"success": True, "signed_up": False})


# ==================== 程序入口 ====================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
