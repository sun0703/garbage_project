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
import json
import logging
import random
import time
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import cv2
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
INDEX_HTML_PATH = BASE_DIR / "static" / "index.html"

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


# ==================== FastAPI 应用实例 ====================
app = FastAPI(
    title="校园垃圾分类AI助手",
    description="基于YOLOv8n-cls的智能垃圾分类识别系统",
    version="1.1.0",
)


# ==================== 请求/响应模型 ====================
class PredictRequest(BaseModel):
    """图像预测请求体"""
    image: str  # Base64编码的图片数据


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


@app.on_event("startup")
def startup_event() -> None:
    """应用启动时初始化"""
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
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        
        if result.get("is_demo_mode"):
            response_data["demo_notice"] = "🔬 智能演示模式：基于图像特征分析（颜色、透明度、形状等），非专门训练的垃圾分类模型"

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
        
        debug_info = {
            "image_size": image.size,
            "aspect_ratio": round(image.width / image.height, 3),
            "features": features,
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
    获取类别详细信息（增强版 v2.2）
    支持基于物品类型和金属特征智能选择示例名称
    支持显示7类模型的原始检测名称
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

    return info


# ==================== 程序入口 ====================
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True, log_level="info")
