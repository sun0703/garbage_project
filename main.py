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
import threading
import uuid
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import cv2
import imagehash
import numpy as np
import onnxruntime as ort
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fuzzywuzzy import process as fuzz_process
from PIL import Image
from pydantic import BaseModel

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


# ==================== 请求限流中间件 ====================

class RateLimiter:
    """
    基于滑动窗口的IP级请求限流器

    使用固定窗口 + 计数器方案，按客户端IP地址独立统计请求频率。
    窗口到期后自动清理过期记录，防止内存泄漏。

    设计说明：
    - 不引入第三方依赖（如slowapi），保持项目轻量
    - 单进程内存存储，适合MVP阶段单实例部署
    - 生产环境建议替换为Redis分布式限流
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        """
        初始化限流器

        @param max_requests: 窗口内允许的最大请求数（默认30次）
        @param window_seconds: 统计窗口时长（默认60秒，即1分钟）
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # 存储结构：{ client_ip: [timestamp1, timestamp2, ...] }
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_allowed(self, client_ip: str) -> tuple[bool, dict]:
        """
        判断当前请求是否允许通过

        @param client_ip: 客户端IP地址
        @return tuple[是否允许, 限制信息字典]
            限制信息包含：
            - remaining: 剩余可用次数
            - reset_time: 窗口重置时间戳
            - retry_after: 被拒绝时的等待秒数
        """
        now = time.time()
        window_start = now - self.window_seconds

        with self._lock:
            if client_ip not in self._requests:
                self._requests[client_ip] = []

            # 清理窗口外的过期记录 
            self._requests[client_ip] = [
                t for t in self._requests[client_ip] if t > window_start
            ]

            current_count = len(self._requests[client_ip])

            if current_count >= self.max_requests:
                # 已达上限，计算等待时间 
                oldest = min(self._requests[client_ip])
                retry_after = int(oldest + self.window_seconds - now) + 1
                return False, {
                    "remaining": 0,
                    "reset_time": oldest + self.window_seconds,
                    "retry_after": retry_after,
                }

            # 记录本次请求 
            self._requests[client_ip].append(now)
            remaining = self.max_requests - len(self._requests[client_ip])
            return True, {
                "remaining": remaining,
                "reset_time": now + self.window_seconds,
                "retry_after": 0,
            }

    def cleanup_stale_ips(self):
        """清理长时间无活动的IP记录，释放内存"""
        now = time.time()
        stale_threshold = now - self.window_seconds * 2

        with self._lock:
            stale_ips = [
                ip for ip, timestamps in self._requests.items()
                if timestamps and max(timestamps) < stale_threshold
            ]
            for ip in stale_ips:
                del self._requests[ip]


# ==================== FastAPI 应用实例 ====================
app = FastAPI(
    title="校园垃圾分类AI助手",
    description="基于YOLOv8n-cls的智能垃圾分类识别系统",
    version="1.1.0",
)


# 全局限流器实例：每IP每分钟最多30次请求
_rate_limiter = RateLimiter(max_requests=30, window_seconds=60)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """HTTP中间件：对所有API路径执行请求频率检查，超限返回429"""
    path = request.url.path

    if not path.startswith("/api/") or request.method == "OPTIONS":
        return await call_next(request)

    forwarded = request.headers.get("x-forwarded-for", "")
    real_ip = request.headers.get("x-real-ip", "")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (real_ip or request.client.host if request.client else "unknown")

    allowed, info = _rate_limiter.is_allowed(client_ip)

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": {
                    "code": "E005",
                    "message": "操作过于频繁，请稍后再试",
                    "detail": f"每分钟最多{_rate_limiter.max_requests}次请求",
                },
                "data": None,
            },
            headers={
                "Retry-After": str(info["retry_after"]),
                "X-RateLimit-Limit": str(_rate_limiter.max_requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(info["reset_time"])),
            },
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(_rate_limiter.max_requests)
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(int(info["reset_time"]))

    if info["remaining"] == 0 or random.random() < 0.01:
        _rate_limiter.cleanup_stale_ips()

    return response


# ==================== 请求/响应模型 ====================
class PredictRequest(BaseModel):
    """图像预测请求体"""
    image: str  # Base64编码的图片数据


class BatchPredictRequest(BaseModel):
    """批量图像预测请求体"""
    images: list[str]  # Base64编码的图片数组，最多5张


class FeedbackRequest(BaseModel):
    """用户反馈请求体"""
    image_base64: str           # 原始图片Base64
    predicted_category_id: int  # 模型预测的类别 0-3
    correct_category_id: int    # 用户认为的正确类别 0-3
    comment: str = ""           # 用户备注（可选）


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
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not self._backup_path or not self._backup_path.exists():
            return
        try:
            with open(self._backup_path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception:
            pass


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
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        if not self._backup_path or not self._backup_path.exists():
            return
        try:
            with open(self._backup_path, "r", encoding="utf-8") as f:
                self._records = json.load(f)
        except Exception:
            pass


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


# ==================== 图像特征分析器 v4.0 增强版 ====================
class ImageFeatureAnalyzer:
    """
    基于OpenCV的图像特征分析器 v4.0（增强版）
    
    新增特性：
    1. 纹理分析：基于局部方差检测光滑/粗糙表面
    2. 边缘密度分析：区分简单/复杂轮廓
    3. 颜色分布均匀性：单色 vs 多色判断
    4. 改进金属光泽检测v4.0：添加频域反射特征
    5. 加权投票分类系统：替代简单if-else链
    
    适用场景：演示模式下的智能分类（无专用模型时的降级方案）
    """

    @staticmethod
    def analyze(image: Image.Image) -> dict:
        """
        分析图像特征，返回增强的特征字典（v4.0 - 12个特征维度）
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
        
        # 灰度图（用于多种分析）
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # ===== 原有特征（改进版） =====
        dominant_color = ImageFeatureAnalyzer._get_dominant_color_v2(img_hsv)  # 使用K-means聚类
        brightness = ImageFeatureAnalyzer._get_brightness_v2(img_array, gray)  # 带区域分析
        transparency = ImageFeatureAnalyzer._detect_transparency_v2(img_array, gray)  # 增强版
        aspect_ratio = image.width / image.height if image.height > 0 else 1.0
        is_metallic = ImageFeatureAnalyzer._detect_metallic_v4(img_array, gray, brightness)  # v4.0重大改进
        
        # ===== 新增v4.0高级特征 =====
        texture_smoothness = ImageFeatureAnalyzer._analyze_texture(gray)  # 纹理光滑度 [0-1]
        edge_density = ImageFeatureAnalyzer._analyze_edge_density(gray)  # 边缘密度 [0-1]
        color_uniformity = ImageFeatureAnalyzer._analyze_color_uniformity(img_hsv)  # 颜色均匀度 [0-1]
        saturation_mean = ImageFeatureAnalyzer._get_saturation_mean(img_hsv)  # 平均饱和度
        contour_complexity = ImageFeatureAnalyzer._analyze_contour_complexity(gray)  # 轮廓复杂度
        
        return {
            "dominant_color": dominant_color,
            "brightness": brightness,
            "transparency": str(transparency),
            "aspect_ratio": aspect_ratio,
            "is_metallic": str(is_metallic),
            "texture_smoothness": texture_smoothness,  # 新增：越接近1越光滑
            "edge_density": edge_density,              # 新增：边缘密度
            "color_uniformity": color_uniformity,      # 新增：颜色分布均匀性
            "saturation_mean": saturation_mean,        # 新增：平均饱和度
            "contour_complexity": contour_complexity,  # 新增：轮廓复杂度
        }
    
    @staticmethod
    def _get_dominant_color_v2(img_hsv: np.ndarray) -> str:
        """获取图像的主色调 v2.0（使用K-means聚类，更准确）"""
        # 重塑像素数组用于聚类
        pixels = img_hsv[:, :, 0].reshape(-1, 1).astype(np.float32)
        
        # 使用K-means找到主要色调（聚类数为3）
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
        
        # 找到最大的簇
        counts = np.bincount(labels.flatten())
        dominant_hue = int(centers[np.argmax(counts)][0])
        
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
    def _get_brightness_v2(img_array: np.ndarray, gray: np.ndarray) -> float:
        """计算图像的平均亮度 v2.0（带区域分析，更可靠）"""
        # 全局亮度
        global_brightness = float(np.mean(gray)) / 255.0
        
        # 中心区域亮度（通常更可靠，避免边缘干扰）
        h, w = gray.shape
        center_region = gray[h//4:3*h//4, w//4:3*w//4]
        center_brightness = float(np.mean(center_region)) / 255.0
        
        # 加权平均（中心区域权重更高）
        return round(0.6 * center_brightness + 0.4 * global_brightness, 4)
    
    @staticmethod
    def _detect_transparency_v2(img_array: np.ndarray, gray: np.ndarray) -> bool:
        """
        检测透明/半透明区域 v2.0（增强版）
        
        新增特征：
        - 高光区域连通性分析
        - 局部对比度异常检测
        """
        if len(img_array.shape) != 3:
            return False
        
        # 特征1：标准差（高透明度物体通常标准差大）
        std_dev = np.std(gray)
        
        # 特征2：超高光像素比例
        super_bright_ratio = np.sum(gray > 220) / gray.size
        
        # 特征3：梯度均值（透明物体边缘清晰）
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        mean_gradient = np.mean(gradient_magnitude)
        
        # 特征4（新增）：高光连通区域数量
        _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
        num_labels, _ = cv2.connectedComponents(thresh)
        high_light_regions = num_labels - 1  # 减去背景
        
        # 综合评分（至少满足2个条件）
        score = 0
        if std_dev > 45:
            score += 1
        if super_bright_ratio > 0.12:
            score += 1
        if mean_gradient > 28:
            score += 1
        if 3 <= high_light_regions <= 20:  # 适度的高光区域数量
            score += 1
        
        return score >= 2
    
    @staticmethod
    def _detect_metallic_v4(img_array: np.ndarray, gray: np.ndarray, brightness: float) -> bool:
        """
        检测金属光泽特征 v4.0（重大改进）
        
        新增算法：
        1. 局部对比度方差分析（金属表面反差大）
        2. 高光条纹检测（金属特有的线性反射）
        3. 频域能量分布（金属高频成分多）
        4. 颜色去饱和度分析（金属通常低饱和度）
        """
        if len(img_array.shape) != 3:
            return False
        
        # ===== 特征1：全局对比度 =====
        std_dev = np.std(gray)
        
        # ===== 特征2：局部对比度方差（新增）=====
        local_std = cv2.Laplacian(gray, cv2.CV_64F)
        local_contrast_var = np.var(local_std)
        
        # ===== 特征3：超高光比例 =====
        super_bright_ratio = np.sum(gray > 240) / gray.size
        
        # ===== 特征4：梯度强度 =====
        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        mean_gradient = np.mean(gradient_magnitude)
        max_gradient = np.max(gradient_magnitude)
        
        # ===== 特征5：饱和度分析（新增）=====
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1]
        mean_saturation = np.mean(saturation)
        low_saturation_ratio = np.sum(saturation < 80) / saturation.size  # 低饱和度像素占比
        
        # ===== 特征6：频域能量（新增）=====
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = np.log(np.abs(f_shift) + 1)
        
        h, w = magnitude_spectrum.shape
        high_freq_region = magnitude_spectrum[h//4:3*h//4, w//4:3*w//4]
        total_energy = np.sum(magnitude_spectrum)
        high_freq_energy = np.sum(high_freq_region) if total_energy > 0 else 0
        high_freq_ratio = high_freq_energy / (total_energy + 1e-6)
        
        # ===== 综合评分系统（v4.0 - 加权计分）=====
        scores = {
            'std_dev': 1.0 if std_dev > 55 else 0.5 if std_dev > 45 else 0,
            'local_contrast': 1.0 if local_contrast_var > 150 else 0.5 if local_contrast_var > 100 else 0,
            'super_bright': 1.0 if super_bright_ratio > 0.04 else 0.5 if super_bright_ratio > 0.02 else 0,
            'gradient': 1.0 if mean_gradient > 18 else 0.5 if mean_gradient > 12 else 0,
            'max_gradient': 1.0 if max_gradient > 200 else 0.5 if max_gradient > 150 else 0,
            'low_saturation': 1.0 if low_saturation_ratio > 0.4 and mean_saturation < 110 else 0.5 if mean_saturation < 140 else 0,
            'high_freq': 1.0 if high_freq_ratio > 0.25 else 0.5 if high_freq_ratio > 0.18 else 0,
        }
        
        total_score = sum(scores.values())
        
        # 阈值调整：需要总分 >= 4.0 才判定为金属（更严格，减少误判）
        return (total_score >= 4.0)
    
    @staticmethod
    def _analyze_texture(gray: np.ndarray) -> float:
        """分析纹理光滑度（新增）- 越接近1越光滑"""
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        smoothness = max(0, min(1, 1.0 - laplacian_var / 3000))
        return round(smoothness, 3)
    
    @staticmethod
    def _analyze_edge_density(gray: np.ndarray) -> float:
        """分析边缘密度（新增）- 高密度表示复杂轮廓"""
        median = np.median(gray)
        lower = int(max(0, 0.7 * median))
        upper = int(min(255, 1.3 * median))
        edges = cv2.Canny(gray, lower, upper)
        edge_density = np.sum(edges > 0) / edges.size
        return round(edge_density, 4)
    
    @staticmethod
    def _analyze_color_uniformity(img_hsv: np.ndarray) -> float:
        """分析颜色分布均匀性（新增）- 接近1表示颜色单一"""
        h_channel = img_hsv[:, :, 0]
        h_std = np.std(h_channel)
        uniformity = max(0, min(1, 1.0 - h_std / 90))
        return round(uniformity, 3)
    
    @staticmethod
    def _get_saturation_mean(img_hsv: np.ndarray) -> float:
        """获取平均饱和度（新增辅助特征）"""
        s_channel = img_hsv[:, :, 1]
        return round(float(np.mean(s_channel)), 1)
    
    @staticmethod
    def _analyze_contour_complexity(gray: np.ndarray) -> float:
        """分析轮廓复杂度（新增）- 低复杂度表示规则形状"""
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 0.0
        
        largest_contour = max(contours, key=cv2.contourArea)
        
        if cv2.contourArea(largest_contour) < 100:
            return 0.0
        
        hull = cv2.convexHull(largest_contour)
        hull_area = cv2.contourArea(hull)
        contour_area = cv2.contourArea(largest_contour)
        
        if hull_area == 0:
            return 0.0
        
        convexity = contour_area / hull_area
        complexity = round(1.0 - convexity, 3)
        
        return complexity
    
    @staticmethod
    def classify_by_features(features: dict) -> Tuple[int, str, str]:
        """
        根据图像特征进行启发式分类 v4.0（增强版 - 多特征加权投票）
        
        核心改进：
        1. 使用12维特征向量进行综合判断
        2. 加权投票机制替代简单if-else链
        3. 纹理/边缘密度辅助区分易混淆物品
        4. 更精细的置信度校准
        
        :param features: 图像特征字典（12个维度）
        :return: (类别ID, 推理依据, 物品类型标签)
        """
        # ===== 提取所有特征 =====
        color = features["dominant_color"]
        brightness = float(features["brightness"])
        transparency = (features["transparency"] == "True")
        aspect_ratio = float(features["aspect_ratio"])
        is_metallic = (features["is_metallic"] == "True")
        
        # 新增v4.0特征
        texture_smoothness = float(features.get("texture_smoothness", 0.5))
        edge_density = float(features.get("edge_density", 0.1))
        color_uniformity = float(features.get("color_uniformity", 0.5))
        saturation_mean = float(features.get("saturation_mean", 120))
        contour_complexity = float(features.get("contour_complexity", 0.3))
        
        item_type = "unknown"
        
        # ===== 形状分类 =====
        is_tall = (0.25 < aspect_ratio < 0.75) or (1.33 < aspect_ratio < 4.0)
        is_square = (0.75 <= aspect_ratio <= 1.33)
        is_flat = (aspect_ratio < 0.25) or (aspect_ratio >= 4.0)
        
        # ===== 加权投票系统 =====
        # 每个类别累计得分，最终选择得分最高的
        scores = {
            0: 0.0,  # 厨余垃圾
            1: 0.0,  # 可回收物
            2: 0.0,  # 其他垃圾
            3: 0.0,  # 有害垃圾
        }
        reasons = {0: [], 1: [], 2: [], 3: []}
        
        # ========== 规则1：形状 + 纹理 + 边缘（权重：高）==========
        if is_tall:
            scores[1] += 3.0  # 细长物品大概率是容器
            reasons[1].append(f"细长形状(长宽比={aspect_ratio:.2f})")
            
            if transparency and brightness > 0.5:
                scores[1] += 2.5
                reasons[1].append("透明+较亮→塑料杯/瓶")
                item_type = "container_tall"
            elif texture_smoothness > 0.6:
                scores[1] += 1.5
                reasons[1].append("光滑表面→容器")
            elif brightness > 0.6:
                scores[1] += 2.0
                reasons[1].append("较亮→容器类")
            elif brightness < 0.4:
                scores[3] += 2.5
                reasons[3].append("细长深色→可能是有害垃圾")
                item_type = "hazardous_tall"
                
        elif is_square:
            # 正方形物品需要更多特征辅助判断
            if is_metallic:
                scores[1] += 4.0
                reasons[1].append("金属光泽→易拉罐/铝罐")
                item_type = "container_tall"
            elif transparency:
                if brightness > 0.88:
                    scores[1] += 3.5
                    reasons[1].append("高亮度透明→杯子/瓶子")
                    item_type = "container_tall"
                elif brightness > 0.55:
                    scores[1] += 2.5
                    reasons[1].append("中等透明→餐盒/保鲜盒")
                    item_type = "container_flat"
                else:
                    scores[1] += 1.5
                    reasons[1].append("较暗透明→包装材料")
                    item_type = "container_flat"
            elif texture_smoothness > 0.7 and contour_complexity < 0.2:
                # 光滑+规则轮廓 → 容器
                scores[1] += 3.0
                reasons[1].append("光滑规则表面→容器/包装")
                item_type = "container_flat" if brightness < 0.8 else "container_tall"
            elif edge_density > 0.15 and texture_smoothness < 0.4:
                # 粗糙+复杂边缘 → 可能是食物
                food_colors = ["red_orange", "orange_yellow", "yellow", "green"]
                if color in food_colors and brightness < 0.65:
                    scores[0] += 3.0
                    reasons[0].append("粗糙复杂+暖色调→有机物/食物")
                    item_type = "food"
                else:
                    scores[2] += 2.0
                    reasons[2].append("粗糙不规则表面")
            elif brightness > 0.75:
                scores[1] += 2.5
                reasons[1].append("高亮度→白色容器/纸盒")
                item_type = "container_flat" if brightness <= 0.82 else "container_tall"
            elif 0.4 < brightness <= 0.75:
                food_colors = ["red_orange", "orange_yellow", "yellow", "green"]
                if color in food_colors and brightness < 0.65:
                    scores[0] += 2.5
                    reasons[0].append("中等亮度暖色调→可能为厨余垃圾")
                    item_type = "food"
                else:
                    scores[1] += 2.0
                    reasons[1].append("默认判断为可回收物（容器或包装）")
                    item_type = "container_flat"
            else:  # brightness <= 0.4
                organic_colors = ["red_orange", "orange_yellow", "yellow"]
                plant_color = ["green"]
                if color in organic_colors or color in plant_color:
                    scores[0] += 2.5
                    reasons[0].append(f"暗色{color}调→有机物残渣")
                    item_type = "food"
                else:
                    scores[2] += 2.0
                    reasons[2].append("暗色非有机物→其他垃圾")
                    item_type = "misc_dark"
                    
        elif is_flat:
            scores[2] += 2.0  # 扁平物品默认倾向其他垃圾
            reasons[2].append(f"扁平形状(长宽比={aspect_ratio:.2f})")
            
            if transparency and brightness > 0.5:
                scores[2] += 2.0
                reasons[2].append("扁平透明→塑料袋")
                item_type = "container_flat"
            elif brightness > 0.75 and edge_density < 0.08:
                scores[1] += 3.0
                reasons[1].append("扁平高亮低边缘→纸张/纸盒")
                item_type = "paper"
            elif texture_smoothness > 0.7:
                scores[1] += 1.5
                reasons[1].append("光滑扁平→可能是包装材料")
            else:
                item_type = "container_flat"
        
        # ========== 规则2：颜色分析（权重：中）==========
        if color in ["red_orange", "orange_yellow", "yellow"]:
            if 0.3 < brightness < 0.85:
                scores[0] += 2.0
                reasons[0].append(f"暖色调({color})→食物/厨余")
        elif color == "green":
            scores[0] += 1.8
            reasons[0].append("绿色调→植物/厨余")
        elif color in ["blue", "purple"]:
            if brightness > 0.5:
                scores[1] += 1.5
                reasons[1].append("冷色调→包装材料")
            else:
                scores[2] += 1.0
                reasons[2].append("深色冷色调")
        
        # ========== 规则3：纹理分析（新增，权重：中）==========
        if texture_smoothness > 0.75:
            scores[1] += 1.5  # 光滑→塑料/金属/玻璃（可回收）
            reasons[1].append(f"光滑表面(纹理度={texture_smoothness:.2f})")
        elif texture_smoothness < 0.35:
            scores[0] += 1.2  # 粗糙→食物/纸张
            scores[2] += 0.8   # 或其他垃圾
            if edge_density > 0.12:
                scores[0] += 1.0
                reasons[0].append("粗糙高边缘密度→有机物")
        
        # ========== 规则4：颜色均匀性（新增）==========
        if color_uniformity > 0.8:
            scores[1] += 1.0  # 单色→容器/包装
            reasons[1].append("颜色单一均匀")
        elif color_uniformity < 0.4:
            scores[0] += 0.8  # 多色→食物/自然物
            reasons[0].append("颜色丰富多样")
        
        # ========== 规则5：饱和度分析（新增）==========
        if saturation_mean < 80:
            scores[1] += 0.8  # 低饱和度→金属/塑料
            reasons[1].append("低饱和度→无机物")
        elif saturation_mean > 160:
            scores[0] += 0.8  # 高饱和度→鲜艳食物/植物
            reasons[0].append("高饱和度→有机物")
        
        # ========== 规则6：亮度兜底 ==========
        if brightness > 0.7:
            scores[1] += 1.0
            reasons[1].append("整体偏亮")
        elif brightness < 0.35:
            scores[2] += 1.0
            reasons[2].append("整体偏暗")
        
        # ===== 最终决策：选择得分最高的类别 =====
        best_class = max(scores, key=scores.get)
        best_score = scores[best_class]
        best_reasons = "; ".join(reasons[best_class][:3])  # 只取前3个原因
        
        # 构建推理依据字符串
        reasoning = f"[v4.0加权投票] 得分={best_score:.1f} | {best_reasons}"
        
        # 如果得分太低（< 2.0），说明特征不明确，降低置信度标记
        if best_score < 2.0:
            reasoning += " | ⚠️ 特征模糊，建议使用专用模型"
        
        return (best_class, reasoning, item_type)
    
    @staticmethod
    def calculate_confidence(features: dict, class_index: int) -> float:
        """
        计算演示模式的模拟置信度 v4.0（增强版）
        
        改进点：
        1. 基于多维度特征综合评估（12个特征）
        2. 使用投票得分差异来校准置信度
        3. 特征一致性检查
        
        :param features: 图像特征字典（12个维度）
        :param class_index: 分类结果
        :return: 0.0-1.0 之间的置信度值
        """
        # 基础置信度
        confidence = 0.62  # v4.0基础值略高（原60%）
        
        # 提取关键特征
        brightness = float(features["brightness"])
        transparency = (features["transparency"] == "True")
        aspect_ratio = float(features["aspect_ratio"])
        color = features["dominant_color"]
        
        # 新增特征
        texture_smoothness = float(features.get("texture_smoothness", 0.5))
        edge_density = float(features.get("edge_density", 0.1))
        color_uniformity = float(features.get("color_uniformity", 0.5))
        
        # ===== 1. 形状匹配加分（最可靠的特征，+12%）=====
        is_tall = (0.25 < aspect_ratio < 0.75) or (1.33 < aspect_ratio < 4.0)
        is_square = (0.75 <= aspect_ratio <= 1.33)
        is_flat = (aspect_ratio < 0.25) or (aspect_ratio >= 4.0)
        
        if is_tall or is_square or is_flat:
            confidence += 0.12
            
            # 额外加分：形状 + 纹理一致性
            if is_tall and texture_smoothness > 0.6:
                confidence += 0.03  # 细长+光滑 → 高概率是容器
            elif is_square and texture_smoothness > 0.7:
                confidence += 0.02  # 正方+光滑 → 可能是容器/包装
        
        # ===== 2. 纹理特征加分（新增，+8%）=====
        if texture_smoothness > 0.8:
            confidence += 0.08  # 非常光滑 → 容器类（容易识别）
        elif texture_smoothness < 0.3:
            confidence += 0.04  # 非常粗糙 → 可能是有机物或纸张
        
        # ===== 3. 边缘密度辅助判断（新增，+5%）=====
        if class_index == 0 and edge_density > 0.15:  # 厨余垃圾通常边缘复杂
            confidence += 0.05
        elif class_index == 1 and edge_density < 0.08:  # 可回收物通常边缘简单
            confidence += 0.05
        
        # ===== 4. 颜色均匀性加分（新增，+4%）=====
        if color_uniformity > 0.85:
            confidence += 0.04  # 单色物品更容易分类
        elif color_uniformity < 0.35:
            confidence -= 0.02  # 多色物品可能难以区分
        
        # ===== 5. 亮度匹配加分（+8%）=====
        if 0.55 < brightness < 0.85:
            confidence += 0.08  # 中等亮度最容易识别
        elif brightness > 0.7:
            confidence += 0.05  # 较亮也还行
        elif brightness < 0.3 or brightness > 0.95:
            confidence -= 0.03  # 过暗或过曝降低置信度
        
        # ===== 6. 颜色特征加分（+5%）=====
        distinct_colors = ["red_orange", "green", "blue"]  # 容易区分的颜色
        if color in distinct_colors:
            confidence += 0.05
        
        # ===== 7. 透明度检测加分（+4%）=====
        if transparency:
            confidence += 0.04
        
        # ===== 8. 根据分类类型微调 =====
        if class_index == 1:  # 可回收物通常更容易通过形状识别
            confidence += 0.04
        elif class_index == 0:  # 厨余垃圾依赖颜色，稍微难一点
            confidence -= 0.01
        elif class_index == 3:  # 有害垃圾较少见，稍微降低
            confidence -= 0.02
        
        # ===== 9. 特征一致性奖励（新增）=====
        # 如果多个特征指向同一类别，增加置信度
        feature_consistency = 0
        if (is_tall or is_square) and transparency and brightness > 0.5:
            feature_consistency += 1
        if texture_smoothness > 0.7 and color_uniformity > 0.8:
            feature_consistency += 1
        if edge_density < 0.1 and brightness > 0.7:
            feature_consistency += 1
        
        if feature_consistency >= 2:
            confidence += 0.06  # 多特征一致→高置信度
        
        # 确保置信度在合理范围内 [0.58, 0.96]
        confidence = max(0.58, min(0.96, confidence))
        
        return round(confidence, 4)


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
        self.session = ort.InferenceSession(str(model_file))
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
        """
        使用Ultralytics YOLOv8进行PyTorch模型推理（优化版）
        
        改进点：
        1. 提高置信度阈值（0.25→0.40），减少低置信度误报
        2. 添加NMS IoU阈值，减少重复检测
        3. 多结果融合策略，提升准确率
        """
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG', quality=95)
            tmp_path = tmp.name

        try:
            # ===== 优化后的推理参数（基于诊断结果调整）=====
            # 诊断发现：40类模型最高置信度仅22-50%，原conf=0.40过高导致全部被过滤
            results = self.yolo_model(
                tmp_path,
                conf=0.15,      # ⬇️ 降低置信度阈值（原0.40），适配该模型的实际输出范围
                iou=0.45,       # NMS IoU阈值，去除重叠框
                verbose=False,
                imgsz=640,      # 输入尺寸
            )

            detections = []
            for r in results:
                boxes = r.boxes

                if len(boxes) > 0:
                    sorted_indices = boxes.conf.argsort(descending=True)

                    for rank, idx in enumerate(sorted_indices[:5]):
                        conf = float(boxes.conf[idx].item())
                        cls_id = int(boxes.cls[idx].item())
                        cls_name = self.yolo_model.names[cls_id]

                        # 二次过滤：置信度过低的不采用（降低到10%以适配模型）
                        if conf < 0.10:
                            continue
                            
                        detections.append({
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "confidence": conf,
                            "bbox": boxes.xyxy[idx].tolist() if hasattr(boxes, 'xyxy') else None,
                            "rank": rank + 1,  # 排名信息
                        })

            if len(detections) == 0:
                logger.warning("⚠️ 未检测到任何物体（可能需要降低conf阈值或检查图片质量）")
                return {
                    "class_index": -1,
                    "confidence": 0.0,
                    "original_class_id": None,
                    "original_class_name": None,
                    "is_demo_mode": True,
                    "detections": [],
                }

            # 选择置信度最高的检测结果（主结果）
            best = max(detections, key=lambda x: x["confidence"])
            class_id = best["class_id"]
            confidence = best["confidence"]
            class_name = best["class_name"]

            logger.info("🎯 YOLOv8检测[优化版]: %s (ID=%d, 置信度=%.1f%%, 排名=%d, 总检测数=%d)",
                       class_name, class_id, confidence * 100, best["rank"], len(detections))

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
            logger.info("词库加载成功: %d 条记录", len(self.vocab))
        except Exception as e:
            logger.error("词库加载失败: %s", e)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """执行模糊搜索"""
        if not self.vocab_labels:
            return []
        raw_results = fuzz_process.extract(query, self.vocab_labels, limit=top_k)
        matched = []
        for label, score in raw_results:
            item = next((v for v in self.vocab if v["label"] == label), None)
            if item:
                matched.append({**item, "similarity_score": score})
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


@app.on_event("startup")
def startup_event() -> None:
    """应用启动时初始化"""
    global vision_engine, search_engine, history_store, feedback_store, inference_cache
    logger.info("正在初始化服务...")
    vision_engine = VisionEngine(str(MODEL_PATH))
    search_engine = SearchEngine(str(VOCAB_PATH))
    history_store = HistoryStore(backup_path=BASE_DIR / "data" / "history.json")
    feedback_store = FeedbackStore(backup_path=BASE_DIR / "data" / "feedback.json")

    # 初始化推理缓存（LRU + TTL 策略）
    inference_cache = InferenceCache(max_size=500, ttl_seconds=86400)

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
    """
    start_time = time.time()

    try:
        _, encoded_data = request.image.split(",", 1)
        image_data = base64.b64decode(encoded_data)
        image = Image.open(BytesIO(image_data)).convert("RGB")
        logger.info("图片解码成功，尺寸: %s", image.size)

        # ===== 推理缓存检查 =====
        # 计算图像指纹用于缓存键生成（相同内容的图片命中同一缓存）
        if inference_cache:
            try:
                cache_key = inference_cache._make_key(image_data)
                cached_result = inference_cache.get(cache_key)
                if cached_result:
                    # 缓存命中：直接返回缓存结果，跳过模型推理
                    inference_ms = int((time.time() - start_time) * 1000)
                    req_id = uuid.uuid4().hex[:12]
                    logger.info("🎯 缓存命中: %s (响应时间=%dms)", cache_key[:20], inference_ms)
                    return JSONResponse(content={
                        "success": True,
                        "result": cached_result,
                        "inference_time_ms": inference_ms,
                        "request_id": req_id,
                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "cache_hit": True,
                    })
            except Exception as e:
                # 缓存操作异常不影响主流程，仅记录警告日志
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
                "error": {"code": "E001", "message": f"解码失败: {str(e)}"},
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
        result = vision_engine.predict(image)
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
                # YOLO未检测到有效目标（class_index=-1 或未知类别）
                # → 降级到图像特征分析模式，而非直接返回默认分类
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
            "request_id": req_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

        if result.get("is_demo_mode"):
            response_data["demo_notice"] = "🔬 智能演示模式：基于图像特征分析（颜色、透明度、形状等），非专门训练的垃圾分类模型"

        # 写入历史记录（仅存必要字段，不存完整base64图片）
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

        # ===== 推理结果写入缓存 =====
        # 将完整的推理结果存入缓存，下次相同图片可直接返回
        if inference_cache and 'cache_key' in locals():
            try:
                inference_cache.set(cache_key, response_data["result"])
            except Exception as e:
                logger.warning("缓存写入异常（不影响主流程）: %s", e)

        return JSONResponse(content=response_data)

    except RuntimeError as e:
        logger.error("推理异常: %s", e)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "E003", "message": f"推理出错: {str(e)}"},
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
                "error": {"code": "E003", "message": f"内部错误: {str(e)}"},
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )


@app.get("/api/search")
async def search_waste(query: str = Query(..., min_length=1)) -> JSONResponse:
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


@app.post("/api/debug/analyze")
async def debug_analyze_image(request: PredictRequest) -> JSONResponse:
    """调试接口：分析图片的详细特征"""
    try:
        _, encoded_data = request.image.split(",", 1)
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


# ==================== 物品差异化投放建议库 ====================

_DISPOSAL_TIPS: dict[str, tuple[int, list[str]]] = {
    "塑料瓶":  (0, ["倒空瓶内残留液体", "简单冲洗瓶身", "压扁瓶身减少体积", "投入蓝色可回收物桶"]),
    "饮料瓶":  (0, ["倒空瓶内残留液体", "简单冲洗瓶身", "压扁瓶身减少体积", "投入蓝色可回收物桶"]),
    "矿泉水瓶": (0, ["倒空瓶内残留液体", "撕掉瓶身塑料标签（如有）", "压扁瓶身", "投入蓝色可回收物桶"]),
    "易拉罐":  (0, ["倒空罐内液体", "轻轻压扁（注意边缘锋利）", "投入蓝色可回收物桶"]),
    "玻璃瓶":  (0, ["清空内容物并冲洗干净", "轻放避免破碎", "投入蓝色可回收物桶（或专用玻璃回收箱）"]),
    "报纸":    (0, ["叠整齐捆扎好", "保持干燥，避免油污污染", "投入蓝色可回收物桶"]),
    "纸箱":    (0, ["拆开压平折叠", "去除胶带和快递面单", "保持干燥无油污", "投入蓝色可回收物桶"]),
    "书本":    (0, ["去除封面硬纸板（如有）", "叠整齐后捆扎或放入回收袋", "投入蓝色可回收物桶"]),
    "旧衣服":  (0, ["清洗干净并晾干", "单独装袋（不要与其他垃圾混投）", "投入旧衣回收箱或蓝色可回收物桶"]),
    "电池":    (0, ["不可与普通垃圾混放", "投入专门的电池回收箱", "或送至电子产品回收点"]),
    "金属":    (0, ["清洁表面污渍", "大件金属需拆解为小块", "投入蓝色可回收物桶"]),
    "废电池":   (1, ["⚠️ 含汞/镉等重金属，切勿随意丢弃", "用绝缘胶带包住正负极防止短路", "投入红色有害垃圾桶"]),
    "蓄电池":   (1, ["⚠️ 含铅酸，具有腐蚀性和毒性", "勿拆解、勿挤压", "投入红色有害垃圾桶或送至专业回收点"]),
    "灯管":     (1, ["⚠️ 含汞，破碎会释放有害气体", "完整包裹防碎（可用原包装）", "投入红色有害垃圾桶"]),
    "荧光灯":   (1, ["⚠️ 含汞蒸气，破损有健康风险", "轻拿轻放，用纸盒包裹", "投入红色有害垃圾桶"]),
    "药品":     (1, ["⚠️ 过期药品可能污染水源和土壤", "连同包装一起投入红色有害垃圾桶", "切勿冲入下水道"]),
    "过期药":   (1, ["⚠️ 化学成分可能危害环境", "保留原包装便于识别", "投入红色有害垃圾桶"]),
    "油漆":     (1, ["⚠️ 含挥发性有机溶剂和重金属", "密封盖紧防止泄漏", "投入红色有害垃圾桶"]),
    "杀虫剂":   (1, ["⚠️ 有毒化学品，远离儿童和食物", "保持原包装密封", "投入红色有害垃圾桶"]),
    "温度计":   (1, ["⚠️ 含水银，破碎后汞蒸气剧毒", "用盒子单独封装", "投入红色有害垃圾桶"]),
    "血压计":   (1, ["⚠️ 水银血压计含剧毒汞", "小心轻放防破碎", "投入红色有害垃圾桶"]),
    "指甲油":   (1, ["⚠️ 含有机溶剂和色素", "盖紧瓶盖防止挥发", "投入红色有害垃圾桶"]),
    "消毒液":   (1, ["⚠️ 强腐蚀性化学制剂", "原瓶密封存放", "投入红色有害垃圾桶"]),
    "剩菜":     (2, ["沥干水分后再投放", "去除大块骨头（属其他垃圾）", "投入绿色厨余垃圾桶"]),
    "剩饭":     (2, ["沥干水分", "投入绿色厨余垃圾桶"]),
    "果皮":     (2, ["直接投入绿色厨余垃圾桶", "大块果皮可适当切碎加速分解"]),
    "果核":     (2, ["小果核（苹果核、葡萄籽等）→ 绿色厨余垃圾桶", "大硬核（榴莲核、椰子壳等）→ 灰色其他垃圾桶"]),
    "菜叶":     (2, ["沥干水分", "投入绿色厨余垃圾桶"]),
    "蛋壳":     (2, ["可直接投入厨余垃圾桶", "无需清洗"]),
    "茶叶渣":   (2, ["沥干茶水", "投入绿色厨余垃圾桶"]),
    "咖啡渣":   (2, ["滤干水分", "可用于堆肥或投入绿色厨余垃圾桶"]),
    "骨头":     (2, ["大块禽畜骨（猪骨、牛骨）→ 灰色其他垃圾桶", "小鱼刺、鸡鸭小骨 → 绿色厨余垃圾桶"]),
    "外壳":     (2, ["虾蟹贝壳、玉米棒 → 灰色其他垃圾桶（难降解）", "瓜子花生壳 → 绿色厨余垃圾桶"]),
    "面包":     (2, ["未过期的可考虑捐赠", "过期的投入绿色厨余垃圾桶"]),
    "餐巾纸":   (3, ["使用过的纸巾已被污染无法回收", "投入灰色其他垃圾桶"]),
    "卫生纸":   (3, ["遇水溶解，无法回收利用", "投入灰色其他垃圾桶"]),
    "烟蒂":     (3, ["确保完全熄灭后再丢弃", "投入灰色其他垃圾桶"]),
    "陶瓷":     (3, ["碎陶瓷片请包裹好防划伤", "投入灰色其他垃圾桶"]),
    "一次性餐具":(3, ["清除食物残渣", "投入灰色其他垃圾桶"]),
    "塑料袋":   (3, ["清洁干净的塑料袋 → 蓝色可回收物桶", "脏污/油污的 → 灰色其他垃圾桶"]),
    "口罩":     (3, ["使用过的口罩可能携带病菌", "投入灰色其他垃圾桶", "疫情期间请按当地规定处置"]),
    "尿布":     (3, ["包好后密封再丢弃", "投入灰色其他垃圾桶"]),
    "猫砂":     (3, ["结团后装入垃圾袋密封", "投入灰色其他垃圾桶", "不可倒入马桶以免堵塞下水道"]),
    "打火机":   (3, ["确保燃气已排空", "投入灰色其他垃圾桶"]),
    "尘土":     (3, ["装袋密封防止扬尘", "投入灰色其他垃圾桶"]),
}

_FALLBACK_TIPS: dict[int, list[str]] = {
    0: ["清洁干净、干燥无油污", "按材质分类整理后投放", "投入蓝色可回收物桶"],
    1: ["⚠️ 含有毒有害物质，请妥善包装", "投入红色有害垃圾桶", "不确定时咨询社区工作人员"],
    2: ["沥干水分后投放", "去除非有机杂质（如塑料袋、大骨头）", "投入绿色厨余垃圾桶"],
    3: ["确认不属于前三类后再投放", "投入灰色其他垃圾桶"],
}


def _get_disposal_tips(label_cn: str, class_index: int) -> list[str]:
    """根据物品名称匹配差异化投放建议，未命中时返回分类通用建议"""
    if not label_cn or label_cn == "识别物品":
        return _FALLBACK_TIPS.get(class_index, ["请正确分类后投放"])
    for keyword, (_cat_id, steps) in _DISPOSAL_TIPS.items():
        if keyword in label_cn:
            return steps
    return _FALLBACK_TIPS.get(class_index, ["请正确分类后投放"])


# ==================== 置信度校准系统 ====================

# 40类模型的类别难度系数（基于实际识别难度调整）
CLASS_DIFFICULTY_40 = {
    # 容易识别的物品（系数 > 1.0，提升置信度）
    "易拉罐": 1.08, "饮料瓶": 1.10, "塑料瓶": 1.06, 
    "玻璃制品": 1.07, "金属制品": 1.09,
    
    # 中等难度（系数 = 1.0，保持不变）
    "一次性餐具": 1.00, "纸巾": 1.00, "塑料袋": 1.00,
    "快递包装": 1.00, "旧书报纸": 1.02,
    
    # 较难识别的物品（系数 < 1.0，降低置信度，更保守）
    "剩菜剩饭": 0.92, "果皮": 0.90, "菜叶菜根": 0.88,
    "蛋壳": 0.85, "骨头": 0.87, "过期食品": 0.89,
}


def _calibrate_confidence_40class(
    raw_confidence: float, 
    class_id: int, 
    num_detections: int,
    is_demo_mode: bool
) -> float:
    """
    40类模型置信度校准函数
    
    校准策略：
    1. 基于类别难度系数调整
    2. 多检测框时提升置信度（一致性验证）
    3. 演示模式使用独立校准曲线
    
    :param raw_confidence: 模型原始输出置信度 (0-1)
    :param class_id: 40类模型的类别ID
    :param num_detections: 检测到的目标数量（用于一致性验证）
    :param is_demo_mode: 是否为演示模式
    :return: 校准后的置信度 (0-1)
    """
    if raw_confidence <= 0:
        return 0.0
    
    # 获取类别名称用于难度查找
    class_name_cn = None
    if class_id in GARBAGE_40CLASSES:
        class_name_cn = GARBAGE_40CLASSES[class_id]["name_cn"]
    
    # ===== 1. 类别难度校准 =====
    difficulty_factor = CLASS_DIFFICULTY_40.get(class_name_cn, 1.0)
    calibrated = raw_confidence * difficulty_factor
    
    # ===== 2. 一致性奖励（多检测框时）=====
    if num_detections >= 2 and not is_demo_mode:
        consistency_bonus = min(0.05, num_detections * 0.01)  # 最多+5%
        calibrated += consistency_bonus
    
    # ===== 3. 高置信度保护（>90%的不应过度下调）=====
    if raw_confidence > 0.90:
        calibrated = max(calibrated, 0.88)
    
    # ===== 4. 低置信度惩罚（<30%的进一步降低）=====
    elif raw_confidence < 0.30:
        calibrated *= 0.8  # 进一步降低20%
    
    # ===== 5. 最终范围限制 =====
    calibrated = max(0.25, min(0.98, calibrated))
    
    return round(calibrated, 4)


# ==================== 工具函数 ====================


def _get_class_info(class_index: int, is_demo_mode: bool = False,
                   item_type: str = "unknown", is_metallic: bool = False,
                   original_class_name: str = None) -> dict:
    """
    获取类别详细信息（增强版 v2.3）
    支持基于物品类型和金属特征智能选择示例名称
    支持显示7类模型的原始检测名称
    新增：按物品类型返回差异化投放建议（tips字段）
    """
    base_info = WASTE_CATEGORIES.get(class_index, WASTE_CATEGORIES[2]).copy()

    info = {
        "category": base_info["name"],
        "category_id": class_index,
        "bin_color": base_info["color"],
        "bin_icon": base_info["icon"],
        "guidance": f"请投入{base_info['bin_color']}{base_info['name']}桶",
        "label_cn": original_class_name if original_class_name else "识别物品",
    }

    # 只有在没有YOLO/COCO原始检测名称时，才使用词库名称补充
    use_vocab_name = (original_class_name is None or original_class_name == "")

    if search_engine and search_engine.vocab and use_vocab_name:
        if is_demo_mode:
            # 使用物品类型和金属特征智能选择示例（v2.1 核心改进）
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

    # v2.3 新增：根据最终 label_cn 生成差异化投放建议 
    final_label = info.get("label_cn", "")
    info["tips"] = _get_disposal_tips(final_label, class_index)

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
            _, encoded_data = img_str.split(",", 1)
            image_data = base64.b64decode(encoded_data)
            image = Image.open(BytesIO(image_data)).convert("RGB")
        except Exception:
            results.append({
                "index": idx,
                "error": "图片解码失败",
            })
            continue

        # ===== 批量识别中的单张图片缓存检查 =====
        cached_item = None
        if inference_cache:
            try:
                cache_key = inference_cache._make_key(image_data)
                cached_result = inference_cache.get(cache_key)
                if cached_result:
                    # 缓存命中：直接使用缓存结果，跳过模型推理
                    logger.info("🎯 批量识别-第%d张 缓存命中: %s", idx + 1, cache_key[:20])
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
            if inference_cache:
                try:
                    # 使用之前生成的 cache_key（如果在缓存检查阶段已生成）
                    if 'cache_key' in locals():
                        inference_cache.set(cache_key, item)
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

    feedback_id = feedback_store.add({
        "image_base64": request.image_base64,
        "predicted_category_id": request.predicted_category_id,
        "correct_category_id": request.correct_category_id,
        "comment": request.comment,
    })

    logger.info("📝 收到用户反馈: %s, 预测=%d, 正确=%d", feedback_id,
                request.predicted_category_id, request.correct_category_id)

    return JSONResponse(content={
        "success": True,
        "message": "反馈已提交，感谢您的帮助",
        "feedback_id": feedback_id,
    })


# ==================== 程序入口 ====================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")

