"""
多模态融合垃圾分类，YOLO检测+SAHI切片+双层级联精细化
"""

import logging
import time
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw
import cv2

logger = logging.getLogger(__name__)


# 枚举与常量
class WasteCategory(Enum):
    """垃圾四大类别"""
    KITCHEN_WASTE = 0
    RECYCLABLE = 1
    OTHER_TRASH = 2
    HAZARDOUS = 3


class ModelType(Enum):
    """模型类型枚举"""
    YOLO_DETECTOR = "yolo_detector"
    SAHI_SLICER = "sahi_slicer"
    CASCADE_CLASSIFIER = "cascade_classifier"
    FEATURE_BASED = "feature_based"


@dataclass
class BoundingBox:
    """边界框数据结构"""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float = 1.0
    class_id: int = -1
    class_name: str = ""

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def iou(self, other: 'BoundingBox') -> float:
        """计算与另一个边界框的IoU"""
        xi1 = max(self.x1, other.x1)
        yi1 = max(self.y1, other.y1)
        xi2 = min(self.x2, other.x2)
        yi2 = min(self.y2, other.y2)

        inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
        union_area = self.area + other.area - inter_area

        return inter_area / union_area if union_area > 0 else 0


@dataclass
class DetectionResult:
    """检测结果数据结构"""
    bbox: BoundingBox
    category: WasteCategory
    category_name: str
    fine_class_id: int
    fine_class_name_cn: str
    confidence: float
    source_model: ModelType
    features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MultiModalResult:
    """多模态融合最终结果"""
    final_prediction: DetectionResult
    yolo_result: Optional[DetectionResult] = None
    sahi_result: Optional[DetectionResult] = None
    transformer_result: Optional[DetectionResult] = None
    fusion_details: Dict[str, Any] = field(default_factory=dict)
    total_inference_time_ms: float = 0.0
    consistency_score: float = 1.0


# 类别映射
CATEGORY_MAP = {
    WasteCategory.KITCHEN_WASTE: {"name": "厨余垃圾", "color": "#8B4513", "icon": "🗑️"},
    WasteCategory.RECYCLABLE: {"name": "可回收物", "color": "#007bff", "icon": "♻️"},
    WasteCategory.OTHER_TRASH: {"name": "其他垃圾", "color": "#333333", "icon": "🗑️"},
    WasteCategory.HAZARDOUS: {"name": "有害垃圾", "color": "#dc3545", "icon": "☠️"},
}

# 40类垃圾专用模型的精确映射表（与garbage_yolov8m_best.pt完全对齐）
YOLO_40CLASS_MAP = {
    # 其他垃圾 (Other Trash) - category 2
    0: {"name_cn": "一次性快餐盒", "category": WasteCategory.OTHER_TRASH},
    1: {"name_cn": "脏塑料", "category": WasteCategory.OTHER_TRASH},
    2: {"name_cn": "烟蒂", "category": WasteCategory.OTHER_TRASH},
    3: {"name_cn": "牙签", "category": WasteCategory.OTHER_TRASH},
    4: {"name_cn": "碎花盆和盘子", "category": WasteCategory.OTHER_TRASH},
    5: {"name_cn": "竹筷", "category": WasteCategory.OTHER_TRASH},
    # 厨余垃圾 (Kitchen Waste) - category 0
    6: {"name_cn": "剩菜剩饭", "category": WasteCategory.KITCHEN_WASTE},
    7: {"name_cn": "大骨头", "category": WasteCategory.KITCHEN_WASTE},
    8: {"name_cn": "果皮", "category": WasteCategory.KITCHEN_WASTE},
    9: {"name_cn": "果肉/果核", "category": WasteCategory.KITCHEN_WASTE},
    10: {"name_cn": "茶叶", "category": WasteCategory.KITCHEN_WASTE},
    11: {"name_cn": "蔬菜叶和根", "category": WasteCategory.KITCHEN_WASTE},
    12: {"name_cn": "蛋壳", "category": WasteCategory.KITCHEN_WASTE},
    13: {"name_cn": "鱼骨", "category": WasteCategory.KITCHEN_WASTE},
    # 可回收物 (Recyclable) - category 1
    14: {"name_cn": "电池组", "category": WasteCategory.RECYCLABLE},
    15: {"name_cn": "背包", "category": WasteCategory.RECYCLABLE},
    16: {"name_cn": "化妆品瓶", "category": WasteCategory.RECYCLABLE},
    17: {"name_cn": "塑料玩具", "category": WasteCategory.RECYCLABLE},
    18: {"name_cn": "塑料碗盘/餐盒", "category": WasteCategory.RECYCLABLE},
    19: {"name_cn": "塑料衣架", "category": WasteCategory.RECYCLABLE},
    20: {"name_cn": "快递纸袋", "category": WasteCategory.RECYCLABLE},
    21: {"name_cn": "插头和电线", "category": WasteCategory.RECYCLABLE},
    22: {"name_cn": "旧衣服", "category": WasteCategory.RECYCLABLE},
    23: {"name_cn": "铝罐/易拉罐", "category": WasteCategory.RECYCLABLE},
    24: {"name_cn": "枕头", "category": WasteCategory.RECYCLABLE},
    25: {"name_cn": "毛绒玩具", "category": WasteCategory.RECYCLABLE},
    26: {"name_cn": "洗发水瓶", "category": WasteCategory.RECYCLABLE},
    27: {"name_cn": "玻璃杯", "category": WasteCategory.RECYCLABLE},
    28: {"name_cn": "皮鞋", "category": WasteCategory.RECYCLABLE},
    29: {"name_cn": "砧板", "category": WasteCategory.RECYCLABLE},
    30: {"name_cn": "纸板箱", "category": WasteCategory.RECYCLABLE},
    31: {"name_cn": "调料瓶", "category": WasteCategory.RECYCLABLE},
    32: {"name_cn": "酒瓶", "category": WasteCategory.RECYCLABLE},
    33: {"name_cn": "金属食品罐", "category": WasteCategory.RECYCLABLE},
    34: {"name_cn": "锅", "category": WasteCategory.RECYCLABLE},
    35: {"name_cn": "食用油容器", "category": WasteCategory.RECYCLABLE},
    36: {"name_cn": "饮料瓶/塑料瓶", "category": WasteCategory.RECYCLABLE},
    # 有害垃圾 (Hazardous) - category 3
    37: {"name_cn": "干电池", "category": WasteCategory.HAZARDOUS},
    38: {"name_cn": "药膏", "category": WasteCategory.HAZARDOUS},
    # 可回收物续
    39: {"name_cn": "纸张", "category": WasteCategory.RECYCLABLE},
}

# 细粒度类别定义（全局唯一ID体系）
FINE_CLASSES = {
    WasteCategory.KITCHEN_WASTE: {
        6: ("Leftover Food", "剩菜剩饭"), 7: ("Large Bones", "大骨头"),
        8: ("Fruit Peels", "果皮"), 9: ("Fruit Flesh", "果肉/果核"),
        10: ("Tea Leaves", "茶叶"), 11: ("Vegetable Leaves", "蔬菜叶和根"),
        12: ("Eggshells", "蛋壳"), 13: ("Fish Bones", "鱼骨"),
    },
    WasteCategory.RECYCLABLE: {
        14: ("Battery Pack", "电池组"), 15: ("Bags", "背包"),
        16: ("Cosmetic Bottles", "化妆品瓶"), 17: ("Plastic Toys", "塑料玩具"),
        18: ("Plastic Bowls", "塑料碗盘/餐盒"), 19: ("Plastic Hangers", "塑料衣架"),
        20: ("Express Bags", "快递纸袋"), 21: ("Plugs and Wires", "插头和电线"),
        22: ("Old Clothes", "旧衣服"), 23: ("Aluminum Cans", "铝罐/易拉罐"),
        24: ("Pillows", "枕头"), 25: ("Stuffed Toys", "毛绒玩具"),
        26: ("Shampoo Bottles", "洗发水瓶"), 27: ("Glass Cups", "玻璃杯"),
        28: ("Leather Shoes", "皮鞋"), 29: ("Cutting Boards", "砧板"),
        30: ("Cardboard Boxes", "纸板箱"), 31: ("Seasoning Bottles", "调料瓶"),
        32: ("Wine Bottles", "酒瓶"), 33: ("Metal Cans", "金属食品罐"),
        34: ("Pots", "锅"), 35: ("Cooking Oil Containers", "食用油容器"),
        36: ("Drink Bottles", "饮料瓶/塑料瓶"), 39: ("Paper", "纸张"),
    },
    WasteCategory.OTHER_TRASH: {
        0: ("Disposable Box", "一次性快餐盒"), 1: ("Dirty Plastic", "脏塑料"),
        2: ("Cigarette Butts", "烟蒂"), 3: ("Toothpicks", "牙签"),
        4: ("Crushed Pots", "碎花盆和盘子"), 5: ("Bamboo Chopsticks", "竹筷"),
    },
    WasteCategory.HAZARDOUS: {
        37: ("Dry Batteries", "干电池"), 38: ("Ointments", "药膏"),
    },
}


# 第一层：YOLO检测器
class YOLODetector:
    """YOLOv8目标检测器，第一层快速检测+粗分类"""

    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.25):
        """
        初始化YOLO检测器

        @param model_path: 模型路径（支持.pt/.onnx）
        @param conf_threshold: 置信度阈值
        """
        self.model = None
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.is_loaded = False
        self.is_waste_model = False  # 是否为40类垃圾专用模型
        self.input_size = (640, 640)

        if model_path and Path(model_path).exists():
            self._load_model(model_path)

    def _load_model(self, model_path: str):
        """加载YOLO模型"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.is_loaded = True

            # 检测是否为40类垃圾专用模型
            num_classes = len(self.model.names)
            self.is_waste_model = (num_classes == 40)

            logger.info("✅ YOLO检测器加载成功: %s (%d类, %s)",
                       model_path, num_classes,
                       "垃圾专用" if self.is_waste_model else "通用模型")
        except Exception as e:
            logger.error("❌ YOLO加载失败: %s", e)

    def detect(self, image: Image.Image, top_k: int = 5) -> List[DetectionResult]:
        """
        执行目标检测

        @param image: 输入图像
        @param top_k: 返回Top-K检测结果
        @return: 检测结果列表
        """
        if not self.is_loaded:
            return self._fallback_detect(image, top_k)

        start_time = time.perf_counter()
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG', quality=95)
            tmp_path = tmp.name

        try:
            results = self.model(
                tmp_path,
                conf=self.conf_threshold,
                iou=0.45,
                imgsz=self.input_size[0],
                verbose=False,
            )

            detections = []
            for r in results:
                boxes = r.boxes
                if len(boxes) == 0:
                    continue

                sorted_indices = boxes.conf.argsort(descending=True)[:top_k]

                for rank, idx in enumerate(sorted_indices):
                    conf = float(boxes.conf[idx].item())
                    cls_id = int(boxes.cls[idx].item())
                    cls_name = self.model.names.get(cls_id, f"class_{cls_id}")

                    xyxy = boxes.xyxy[idx].tolist() if hasattr(boxes, 'xyxy') else [0, 0, 100, 100]

                    # 使用精确映射表
                    category, fine_class_id, fine_name_cn = self._map_class(cls_id, cls_name)

                    bbox = BoundingBox(
                        x1=xyxy[0], y1=xyxy[1], x2=xyxy[2], y2=xyxy[3],
                        confidence=conf, class_id=cls_id, class_name=cls_name,
                    )

                    detections.append(DetectionResult(
                        bbox=bbox,
                        category=category,
                        category_name=CATEGORY_MAP[category]["name"],
                        fine_class_id=fine_class_id,
                        fine_class_name_cn=fine_name_cn,
                        confidence=conf,
                        source_model=ModelType.YOLO_DETECTOR,
                        features={"rank": rank + 1, "raw_confidence": conf},
                    ))

            inference_time = (time.perf_counter() - start_time) * 1000
            logger.info("🎯 YOLO检测完成: %d个目标, 耗时=%.1fms", len(detections), inference_time)

            return detections

        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _map_class(self, cls_id: int, cls_name: str) -> Tuple[WasteCategory, int, str]:
        """
        将YOLO类别ID映射为垃圾类别

        优先使用精确映射表（40类专用模型），回退到关键词映射
        """
        # 优先：40类垃圾专用模型的精确映射
        if self.is_waste_model and cls_id in YOLO_40CLASS_MAP:
            info = YOLO_40CLASS_MAP[cls_id]
            return info["category"], cls_id, info["name_cn"]

        # 回退：基于名称关键词的智能映射
        name_lower = cls_name.lower()

        if any(kw in name_lower for kw in ["kitchen", "food", "fruit", "vegetable", "egg", "tea", "bone", "peel", "leftover"]):
            cat = WasteCategory.KITCHEN_WASTE
        elif any(kw in name_lower for kw in ["recyclable", "bottle", "glass", "can", "paper", "cardboard", "plastic", "metal", "cloth", "pot"]):
            cat = WasteCategory.RECYCLABLE
        elif any(kw in name_lower for kw in ["other", "trash", "disposable", "dirty", "cigarette", "toothpick", "chopstick"]):
            cat = WasteCategory.OTHER_TRASH
        elif any(kw in name_lower for kw in ["hazardous", "battery", "ointment", "lamp", "pesticide"]):
            cat = WasteCategory.HAZARDOUS
        else:
            cat = WasteCategory.OTHER_TRASH

        # 在对应大类中查找匹配的细粒度类别
        fine_classes = FINE_CLASSES.get(cat, {})
        fine_id = next(iter(fine_classes), cls_id)
        fine_name = fine_classes.get(fine_id, ("unknown", cls_name))[1]

        return cat, fine_id, fine_name

    def _fallback_detect(self, image: Image.Image, top_k: int) -> List[DetectionResult]:
        """模型没加载时的土办法，靠颜色特征猜一猜"""
        img_array = np.array(image.convert('RGB'))
        h, w = img_array.shape[:2]

        # 提取多维度颜色特征
        avg_color = np.mean(img_array, axis=(0, 1))
        gray = np.mean(img_array, axis=2)
        std_color = np.std(img_array, axis=(0, 1))

        # 计算各颜色通道的比例
        total_pixels = img_array.shape[0] * img_array.shape[1]
        r_ch, g_ch, b_ch = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]

        # 绿色像素比例（植物/食物特征）
        green_ratio = np.sum((g_ch > 100) & (g_ch > r_ch) & (g_ch > b_ch)) / total_pixels
        # 红色像素比例（危险品/食物特征）
        red_ratio = np.sum((r_ch > 150) & (r_ch > g_ch * 1.2) & (r_ch > b_ch * 1.2)) / total_pixels
        # 棕色像素比例（土壤/腐烂特征）
        brown_ratio = np.sum((r_ch > 80) & (r_ch < 150) & (g_ch > 50) & (g_ch < 120) & (b_ch < 80)) / total_pixels
        # 高亮像素比例（透明/金属特征）
        bright_ratio = np.sum(gray > 180) / total_pixels
        # 灰暗像素比例（脏污/其他特征）
        dark_ratio = np.sum((gray < 120) & (np.std(img_array, axis=2) < 40)) / total_pixels

        # 多特征综合评分（修复：更合理的权重分配）
        scores = {
            WasteCategory.KITCHEN_WASTE: green_ratio * 4.0 + brown_ratio * 3.0 + 0.05,
            WasteCategory.RECYCLABLE: bright_ratio * 3.0 + (std_color.mean() / 80.0) + 0.05,
            WasteCategory.OTHER_TRASH: dark_ratio * 2.5 + 0.1,
            WasteCategory.HAZARDOUS: red_ratio * 5.0 + 0.02,
        }

        # Softmax归一化（避免极端概率）
        max_score = max(scores.values())
        exp_scores = {cat: math.exp(s - max_score) for cat, s in scores.items()}
        total_exp = sum(exp_scores.values())
        probs = {cat: exp_s / total_exp for cat, exp_s in exp_scores.items()}

        # 按概率排序，取Top-K
        sorted_cats = sorted(probs.items(), key=lambda x: x[1], reverse=True)

        detections = []
        for rank, (cat, prob) in enumerate(sorted_cats[:top_k]):
            fine_classes = FINE_CLASSES.get(cat, {})
            # 根据颜色特征选择最匹配的细粒度类别
            best_fine_id = self._select_best_fine_class(img_array, fine_classes)
            fine_name = fine_classes.get(best_fine_id, ("unknown", "未知"))[1]

            detections.append(DetectionResult(
                bbox=BoundingBox(x1=0, y1=0, x2=w, y2=h, confidence=prob),
                category=cat,
                category_name=CATEGORY_MAP[cat]["name"],
                fine_class_id=best_fine_id,
                fine_class_name_cn=fine_name,
                confidence=prob,
                source_model=ModelType.YOLO_DETECTOR,
                features={"method": "enhanced_color_heuristic", "rank": rank + 1},
            ))

        return detections

    def _select_best_fine_class(self, img_array: np.ndarray,
                                 fine_classes: Dict[int, Tuple[str, str]]) -> int:
        """根据颜色挑个最像的细类，凑合用"""
        if not fine_classes:
            return 0

        avg_color = np.mean(img_array, axis=(0, 1))
        r, g, b = avg_color

        best_id = next(iter(fine_classes))
        best_score = -1.0

        for class_id, (_, name_cn) in fine_classes.items():
            score = 0.0

            # 绿色系 → 果皮、蔬菜、茶叶
            if any(kw in name_cn for kw in ["果皮", "蔬菜", "茶叶"]):
                score += g / 255.0 * 0.5
            # 白色/浅色 → 蛋壳、骨头
            elif any(kw in name_cn for kw in ["蛋壳", "骨头", "鱼骨"]):
                score += np.mean([r, g, b]) / 255.0 * 0.4
            # 黄色 → 果肉
            elif "果肉" in name_cn:
                score += (g / 255.0 + r / 255.0) * 0.25
            # 剩饭 → 混合色
            elif "剩菜" in name_cn:
                score += 0.3
            # 瓶/罐/玻璃 → 高对比度
            elif any(kw in name_cn for kw in ["瓶", "罐", "玻璃"]):
                score += np.std(img_array) / 128.0 * 0.4
            # 纸/箱 → 中性
            elif any(kw in name_cn for kw in ["纸", "箱", "袋"]):
                score += 0.25
            # 电池/药 → 红色
            elif any(kw in name_cn for kw in ["电池", "药"]):
                score += r / 255.0 * 0.5
            # 其他 → 低分
            else:
                score += 0.15

            if score > best_score:
                best_score = score
                best_id = class_id

        return best_id


# 第二层：SAHI切片推理引擎
class SAHIEngine:
    """SAHI切片推理引擎，把大图切成小块分别检测再合并"""

    def __init__(self,
                 base_detector: Optional[YOLODetector] = None,
                 slice_size: Tuple[int, int] = (320, 320),
                 overlap_ratio: float = 0.25,
                 conf_threshold: float = 0.20):
        """
        初始化SAHI引擎

        @param base_detector: 基础YOLO检测器（复用第一层的模型）
        @param slice_size: 切片尺寸 (height, width)
        @param overlap_ratio: 切片间重叠比例 (0-0.5)
        @param conf_threshold: 置信度阈值
        """
        self.base_detector = base_detector
        self.slice_size = slice_size
        self.overlap_ratio = overlap_ratio
        self.conf_threshold = conf_threshold
        self.slice_height, self.slice_width = slice_size

    def detect_with_slicing(self, image: Image.Image, top_k: int = 5) -> List[DetectionResult]:
        """
        使用切片推理进行检测

        @param image: 输入图像
        @param top_k: 返回Top-K结果
        @return: 合并后的检测结果列表
        """
        start_time = time.perf_counter()
        img_array = np.array(image.convert('RGB'))
        img_h, img_w = img_array.shape[:2]

        logger.info("🔪 SAHI切片推理开始: 原始尺寸=%dx%d, 切片尺寸=%dx%d",
                   img_w, img_h, self.slice_width, self.slice_height)

        # 计算切片参数
        stride_h = int(self.slice_height * (1 - self.overlap_ratio))
        stride_w = int(self.slice_width * (1 - self.overlap_ratio))

        # 生成切片坐标
        slices = self._generate_slices(img_w, img_h, stride_w, stride_h)
        logger.info("   共生成 %d 个切片", len(slices))

        # 对每个切片进行推理
        all_slice_detections: List[DetectionResult] = []

        for idx, (sx, sy, ex, ey) in enumerate(slices):
            # 裁剪切片
            slice_img = image.crop((sx, sy, ex, ey))

            # 推理（使用基础检测器或特征匹配）
            if self.base_detector and self.base_detector.is_loaded:
                slice_results = self.base_detector.detect(slice_img, top_k=3)
            else:
                slice_results = self._slice_feature_match(slice_img)

            # 坐标映射回原图
            for det in slice_results:
                mapped_det = self._map_detection_to_original(det, sx, sy, img_w, img_h, slice_img.size)
                mapped_det.features["slice_index"] = idx
                mapped_det.source_model = ModelType.SAHI_SLICER
                all_slice_detections.append(mapped_det)

        # NMS合并重叠检测
        merged_detections = self._nms_merge(all_slice_detections, iou_threshold=0.4)

        # 取Top-K
        final_detections = sorted(merged_detections, key=lambda d: d.confidence, reverse=True)[:top_k]

        inference_time = (time.perf_counter() - start_time) * 1000
        logger.info("✅ SAHI推理完成: %d个有效检测 (从%d个切片), 耗时=%.1fms",
                   len(final_detections), len(slices), inference_time)

        return final_detections

    def _generate_slices(self, img_w: int, img_h: int, stride_w: int, stride_h: int) -> List[Tuple[int, int, int, int]]:
        """生成切片坐标列表"""
        slices = []

        for y in range(0, img_h - self.slice_height + 1, stride_h):
            for x in range(0, img_w - self.slice_width + 1, stride_w):
                ex = min(x + self.slice_width, img_w)
                ey = min(y + self.slice_height, img_h)
                slices.append((x, y, ex, ey))

        # 处理边缘情况
        if not slices or slices[-1][2] < img_w or slices[-1][3] < img_h:
            last_x = max(0, img_w - self.slice_width)
            last_y = max(0, img_h - self.slice_height)
            slices.append((last_x, last_y, img_w, img_h))

        return slices

    def _map_detection_to_original(self, det: DetectionResult,
                                    offset_x: int, offset_y: int,
                                    orig_w: int, orig_h: int,
                                    slice_size: Tuple[int, int]) -> DetectionResult:
        """将切片坐标系映射回原图坐标系"""
        # 切片裁剪后坐标已归零，直接加偏移即可映射回原图
        orig_bbox = BoundingBox(
            x1=det.bbox.x1 + offset_x,
            y1=det.bbox.y1 + offset_y,
            x2=det.bbox.x2 + offset_x,
            y2=det.bbox.y2 + offset_y,
            confidence=det.bbox.confidence,
            class_id=det.bbox.class_id,
            class_name=det.bbox.class_name,
        )

        return DetectionResult(
            bbox=orig_bbox,
            category=det.category,
            category_name=det.category_name,
            fine_class_id=det.fine_class_id,
            fine_class_name_cn=det.fine_class_name_cn,
            confidence=det.confidence * 0.95,  # 切片推理略微降权
            source_model=det.source_model,
            features={**det.features},
        )

    def _nms_merge(self, detections: List[DetectionResult], iou_threshold: float = 0.4) -> List[DetectionResult]:
        """NMS去重，切片推理后重叠区域会有重复检测"""
        if not detections:
            return []

        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)

        keep: List[DetectionResult] = []
        suppressed = set()

        for i, current in enumerate(sorted_dets):
            if i in suppressed:
                continue

            keep.append(current)

            for j in range(i + 1, len(sorted_dets)):
                if j in suppressed:
                    continue

                other = sorted_dets[j]
                iou_val = current.bbox.iou(other.bbox)

                if iou_val > iou_threshold:
                    suppressed.add(j)

        return keep

    def _slice_feature_match(self, slice_img: Image.Image) -> List[DetectionResult]:
        """切片级别的特征匹配，复用YOLODetector的fallback"""
        temp_detector = YOLODetector()
        return temp_detector._fallback_detect(slice_img, top_k=1)


# 第三层：双层级联精细化分类器
class CascadeFineClassifier:
    """双层级联分类器：先分4大类再精细识别，类别越少准确率越高"""

    # 路由策略的置信度阈值
    CONF_HIGH = 0.70    # 高置信度：直接路由到1个子模型
    CONF_MEDIUM = 0.40  # 中置信度：路由到Top-2子模型
    # 低置信度(<0.40): 路由到全部4个子模型

    def __init__(self, yolo_detector: Optional[YOLODetector] = None):
        """
        初始化级联精细化分类器

        @param yolo_detector: 复用第一层的YOLO检测器（共享模型权重）
        """
        self.yolo_detector = yolo_detector
        self.is_loaded = yolo_detector is not None and yolo_detector.is_loaded

        # 各大类的细粒度类别ID列表（用于子模型过滤）
        self.category_class_ids: Dict[WasteCategory, List[int]] = {}
        for cat in WasteCategory:
            self.category_class_ids[cat] = list(FINE_CLASSES.get(cat, {}).keys())

        logger.info("📦 双层级联分类器初始化: %s",
                   "复用YOLO模型" if self.is_loaded else "特征匹配模式")

    def classify(self, image: Image.Image,
                 yolo_results: Optional[List[DetectionResult]] = None,
                 top_k: int = 3) -> List[DetectionResult]:
        """
        执行双层级联推理

        @param image: 输入图像
        @param yolo_results: 第一层YOLO的检测结果（复用，避免重复推理）
        @param top_k: 返回Top-K结果
        @return: 级联分类结果
        """
        start_time = time.perf_counter()

        # Step 1: 粗分类（4大类）
        coarse_category, coarse_confidence, category_probs = self._coarse_classify(yolo_results, image)

        logger.info("  [Cascade Step1] 粗分类: %s (%.1f%%)",
                   CATEGORY_MAP[coarse_category]["name"], coarse_confidence * 100)

        # Step 2: 路由决策
        target_categories, strategy_desc = self._route(coarse_category, coarse_confidence, category_probs)

        logger.info("  [Cascade Step2] 路由: %s → %s", strategy_desc,
                   [CATEGORY_MAP[c]["name"] for c in target_categories])

        # Step 3: 精细化子模型推理
        fine_results = self._fine_classify(image, target_categories, yolo_results, top_k)

        inference_time = (time.perf_counter() - start_time) * 1000

        # 包装结果
        results = []
        for rank, det in enumerate(fine_results[:top_k]):
            det.source_model = ModelType.CASCADE_CLASSIFIER
            det.features.update({
                "cascade_step1_category": coarse_category.name,
                "cascade_step1_confidence": coarse_confidence,
                "cascade_routing_strategy": strategy_desc,
                "rank": rank + 1,
                "inference_time_ms": inference_time,
            })
            results.append(det)

        logger.info("  [Cascade Step3] 精细化完成: %s (%.1f%%), 耗时=%.1fms",
                   results[0].fine_class_name_cn if results else "无",
                   results[0].confidence * 100 if results else 0,
                   inference_time)

        return results

    def _coarse_classify(self,
                         yolo_results: Optional[List[DetectionResult]],
                         image: Image.Image) -> Tuple[WasteCategory, float, Dict[WasteCategory, float]]:
        """
        Step 1: 粗分类 → 将YOLO的40类结果聚合为4大类概率

        @return: (最可能的大类, 置信度, 各大类概率分布)
        """
        category_probs: Dict[WasteCategory, float] = {cat: 0.0 for cat in WasteCategory}

        if yolo_results:
            # 从YOLO结果聚合：同一大类的置信度累加
            for det in yolo_results:
                category_probs[det.category] += det.confidence
        else:
            # 无YOLO结果时用特征匹配
            category_probs = self._feature_coarse_classify(image)

        # Softmax归一化
        total = sum(category_probs.values())
        if total > 0:
            category_probs = {cat: p / total for cat, p in category_probs.items()}

        # 选择最高概率的大类
        best_category = max(category_probs, key=category_probs.get)
        best_confidence = category_probs[best_category]

        return best_category, best_confidence, category_probs

    def _feature_coarse_classify(self, image: Image.Image) -> Dict[WasteCategory, float]:
        """Fallback：基于颜色特征的粗分类"""
        img_array = np.array(image.convert('RGB'))
        total_pixels = img_array.shape[0] * img_array.shape[1]
        r_ch, g_ch, b_ch = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]
        gray = np.mean(img_array, axis=2)

        green_ratio = np.sum((g_ch > 100) & (g_ch > r_ch) & (g_ch > b_ch)) / total_pixels
        red_ratio = np.sum((r_ch > 150) & (r_ch > g_ch * 1.2) & (r_ch > b_ch * 1.2)) / total_pixels
        bright_ratio = np.sum(gray > 180) / total_pixels
        dark_ratio = np.sum((gray < 100) & (np.std(img_array, axis=2) < 40)) / total_pixels

        scores = {
            WasteCategory.KITCHEN_WASTE: green_ratio * 4.0 + 0.05,
            WasteCategory.RECYCLABLE: bright_ratio * 3.0 + np.std(img_array).mean() / 80.0 + 0.05,
            WasteCategory.OTHER_TRASH: dark_ratio * 2.5 + 0.1,
            WasteCategory.HAZARDOUS: red_ratio * 5.0 + 0.02,
        }

        # Softmax
        max_s = max(scores.values())
        exp_s = {cat: math.exp(s - max_s) for cat, s in scores.items()}
        total_exp = sum(exp_s.values())
        return {cat: e / total_exp for cat, e in exp_s.items()}

    def _route(self, coarse_category: WasteCategory, coarse_confidence: float,
               category_probs: Dict[WasteCategory, float]) -> Tuple[List[WasteCategory], str]:
        """
        Step 2: 路由决策

        策略：
        - 高置信度(≥70%): 只调用1个子模型（最快）
        - 中置信度(40-70%): 调用Top-2子模型（平衡）
        - 低置信度(<40%): 调用全部4个子模型（最保险）
        """
        if coarse_confidence >= self.CONF_HIGH:
            return [coarse_category], f"high_conf({coarse_confidence:.0%}≥{self.CONF_HIGH:.0%})"

        elif coarse_confidence >= self.CONF_MEDIUM:
            sorted_cats = sorted(category_probs.items(), key=lambda x: x[1], reverse=True)[:2]
            targets = [cat for cat, _ in sorted_cats]
            return targets, f"medium_conf({self.CONF_MEDIUM:.0%}≤{coarse_confidence:.0%}<{self.CONF_HIGH:.0%})"

        else:
            return list(WasteCategory), f"low_conf({coarse_confidence:.0%}<{self.CONF_MEDIUM:.0%})"

    def _fine_classify(self, image: Image.Image,
                       target_categories: List[WasteCategory],
                       yolo_results: Optional[List[DetectionResult]],
                       top_k: int) -> List[DetectionResult]:
        """
        Step 3: 在目标大类内进行精细化分类

        核心逻辑：
        - 如果有YOLO结果：过滤出目标大类的检测结果，重新排序
        - 如果YOLO无结果或目标大类内无结果：用YOLO二次推理（降低阈值）
        - 最终Fallback：特征匹配
        """
        # 尝试从已有YOLO结果中过滤
        if yolo_results:
            filtered = [det for det in yolo_results if det.category in target_categories]
            if filtered:
                # 按置信度重新排序
                filtered.sort(key=lambda d: d.confidence, reverse=True)
                # 重新归一化置信度（在子类别空间内）
                total_conf = sum(d.confidence for d in filtered)
                if total_conf > 0:
                    for det in filtered:
                        det.confidence = det.confidence / total_conf
                return filtered[:top_k]

        # YOLO二次推理：降低阈值，只接受目标大类的结果
        if self.is_loaded and self.yolo_detector:
            logger.info("  [Cascade] YOLO二次推理（降低阈值）...")
            # 临时降低置信度阈值
            original_conf = self.yolo_detector.conf_threshold
            self.yolo_detector.conf_threshold = 0.05  # 大幅降低
            try:
                second_results = self.yolo_detector.detect(image, top_k=10)
                # 只保留目标大类的结果
                filtered = [det for det in second_results if det.category in target_categories]
                if filtered:
                    filtered.sort(key=lambda d: d.confidence, reverse=True)
                    return filtered[:top_k]
            finally:
                self.yolo_detector.conf_threshold = original_conf

        # 最终Fallback：特征匹配
        return self._feature_fine_classify(image, target_categories, top_k)

    def _feature_fine_classify(self, image: Image.Image,
                                target_categories: List[WasteCategory],
                                top_k: int) -> List[DetectionResult]:
        """Fallback：基于特征匹配的精细化分类"""
        img_array = np.array(image.convert('RGB'))
        avg_color = np.mean(img_array, axis=(0, 1))
        std_color = np.std(img_array, axis=(0, 1))
        gray = np.mean(img_array, axis=2)
        total_pixels = img_array.shape[0] * img_array.shape[1]
        r_ch, g_ch, b_ch = img_array[:, :, 0], img_array[:, :, 1], img_array[:, :, 2]

        green_ratio = np.sum((g_ch > 100) & (g_ch > r_ch) & (g_ch > b_ch)) / total_pixels
        red_ratio = np.sum((r_ch > 150) & (r_ch > g_ch * 1.2) & (r_ch > b_ch * 1.2)) / total_pixels
        bright_ratio = np.sum(gray > 180) / total_pixels
        dark_ratio = np.sum(gray < 100) / total_pixels

        # 只在目标大类内计算分数（类别少→准确率高）
        class_scores: Dict[int, float] = {}
        for cat in target_categories:
            fine_classes = FINE_CLASSES.get(cat, {})
            for class_id, (_, name_cn) in fine_classes.items():
                score = self._compute_feature_score(
                    avg_color, std_color, green_ratio, red_ratio,
                    bright_ratio, dark_ratio, name_cn
                )
                class_scores[class_id] = score

        if not class_scores:
            return [DetectionResult(
                bbox=BoundingBox(0, 0, image.width, image.height, confidence=0.3),
                category=WasteCategory.OTHER_TRASH,
                category_name="其他垃圾",
                fine_class_id=0,
                fine_class_name_cn="一次性快餐盒",
                confidence=0.3,
                source_model=ModelType.CASCADE_CLASSIFIER,
            )]

        # Softmax归一化（温度参数平滑分布）
        temperature = 1.5
        max_score = max(class_scores.values())
        exp_scores = {cid: math.exp((s - max_score) / temperature) for cid, s in class_scores.items()}
        total_exp = sum(exp_scores.values())
        normalized = {cid: e / total_exp for cid, e in exp_scores.items()}

        # 取Top-K
        sorted_scores = sorted(normalized.items(), key=lambda x: x[1], reverse=True)[:top_k]

        results = []
        for class_id, score in sorted_scores:
            cat = self._id_to_category(class_id)
            class_info = FINE_CLASSES.get(cat, {}).get(class_id, ("unknown", "未知"))
            results.append(DetectionResult(
                bbox=BoundingBox(0, 0, image.width, image.height, confidence=score),
                category=cat,
                category_name=CATEGORY_MAP[cat]["name"],
                fine_class_id=class_id,
                fine_class_name_cn=class_info[1],
                confidence=score,
                source_model=ModelType.CASCADE_CLASSIFIER,
            ))

        return results

    def _compute_feature_score(self, avg_color, std_color,
                                green_ratio, red_ratio,
                                bright_ratio, dark_ratio,
                                target_name: str) -> float:
        """计算特征匹配分数"""
        r, g, b = avg_color
        score = 0.0

        # 厨余垃圾
        if any(kw in target_name for kw in ["果皮", "蔬菜", "茶叶"]):
            score += green_ratio * 3.0 + (g / 255.0) * 0.5
        elif any(kw in target_name for kw in ["蛋壳", "骨头", "鱼骨"]):
            score += bright_ratio * 2.0 + (np.mean([r, g, b]) / 255.0) * 0.3
        elif "果肉" in target_name:
            score += (g / 255.0 + r / 255.0) * 0.4
        elif "剩菜" in target_name:
            score += green_ratio * 1.5 + dark_ratio * 0.5 + 0.2
        elif "大骨头" in target_name:
            score += bright_ratio * 1.5 + 0.15

        # 可回收物
        elif any(kw in target_name for kw in ["瓶", "罐", "玻璃"]):
            score += bright_ratio * 2.5 + (std_color.mean() / 80.0) * 0.5
        elif any(kw in target_name for kw in ["纸", "箱", "袋"]):
            score += 0.3 + bright_ratio * 0.5
        elif any(kw in target_name for kw in ["衣服", "鞋", "玩具"]):
            score += 0.25
        elif any(kw in target_name for kw in ["电线", "插头"]):
            score += (std_color.mean() / 80.0) * 0.4

        # 有害垃圾
        elif any(kw in target_name for kw in ["电池", "药膏"]):
            score += red_ratio * 4.0 + (r / 255.0) * 0.5

        # 其他垃圾
        elif any(kw in target_name for kw in ["快餐盒", "脏", "烟蒂", "牙签", "竹筷"]):
            score += dark_ratio * 2.0 + 0.2
        elif "花盆" in target_name:
            score += dark_ratio * 1.5 + 0.15

        if score < 0.01:
            score = 0.1

        return score

    def _id_to_category(self, class_id: int) -> WasteCategory:
        """根据细粒度ID判断所属大类"""
        if class_id in YOLO_40CLASS_MAP:
            return YOLO_40CLASS_MAP[class_id]["category"]
        if 6 <= class_id <= 13:
            return WasteCategory.KITCHEN_WASTE
        elif (14 <= class_id <= 36) or class_id == 39:
            return WasteCategory.RECYCLABLE
        elif 0 <= class_id <= 5:
            return WasteCategory.OTHER_TRASH
        elif class_id in (37, 38):
            return WasteCategory.HAZARDOUS
        return WasteCategory.OTHER_TRASH


# 融合决策系统
class FusionDecisionMaker:
    """多模型融合决策：加权投票+置信度校准+一致性加成"""

    # 各模型的可靠性权重
    MODEL_RELIABILITY = {
        ModelType.YOLO_DETECTOR: {"weight": 0.35, "calibration": 0.90},
        ModelType.SAHI_SLICER: {"weight": 0.25, "calibration": 0.85},
        ModelType.CASCADE_CLASSIFIER: {"weight": 0.40, "calibration": 0.92},
    }

    def fuse_predictions(self,
                         yolo_results: List[DetectionResult],
                         sahi_results: List[DetectionResult],
                         cascade_results: List[DetectionResult]) -> MultiModalResult:
        """
        融合三个模型的预测结果

        @param yolo_results: YOLO检测结果
        @param sahi_results: SAHI检测结果
        @param cascade_results: 级联精细化分类结果
        @return: 融合后的最终结果
        """
        start_time = time.perf_counter()

        # 收集所有最佳预测
        best_yolo = yolo_results[0] if yolo_results else None
        best_sahi = sahi_results[0] if sahi_results else None
        best_cascade = cascade_results[0] if cascade_results else None

        # 构建投票池（按大类投票）
        category_votes: Dict[WasteCategory, List[Tuple[float, ModelType, DetectionResult]]] = defaultdict(list)

        if best_yolo:
            calib_conf = best_yolo.confidence * self.MODEL_RELIABILITY[ModelType.YOLO_DETECTOR]["calibration"]
            category_votes[best_yolo.category].append((calib_conf, ModelType.YOLO_DETECTOR, best_yolo))

        if best_sahi:
            calib_conf = best_sahi.confidence * self.MODEL_RELIABILITY[ModelType.SAHI_SLICER]["calibration"]
            category_votes[best_sahi.category].append((calib_conf, ModelType.SAHI_SLICER, best_sahi))

        if best_cascade:
            calib_conf = best_cascade.confidence * self.MODEL_RELIABILITY[ModelType.CASCADE_CLASSIFIER]["calibration"]
            category_votes[best_cascade.category].append((calib_conf, ModelType.CASCADE_CLASSIFIER, best_cascade))

        if not category_votes:
            return self._create_default_result()

        # 计算每个大类的加权得分
        category_scores: List[Tuple[WasteCategory, float, int, DetectionResult]] = []
        for cat, vote_list in category_votes.items():
            weighted_sum = sum(
                conf * self.MODEL_RELIABILITY[model]["weight"]
                for conf, model, _ in vote_list
            )
            # 选择该大类中置信度最高的结果作为代表
            best_det = max(vote_list, key=lambda x: x[0])[2]
            category_scores.append((cat, weighted_sum, len(vote_list), best_det))

        # 选择最佳大类（优先得票数，其次加权分）
        category_scores.sort(key=lambda x: (x[2], x[1]), reverse=True)
        best_cat, best_score, vote_count, best_det = category_scores[0]

        # 计算一致性得分
        total_models = sum(1 for x in [best_yolo, best_sahi, best_cascade] if x is not None)
        consistency = vote_count / total_models if total_models > 0 else 0

        # 确定最终细粒度类别（在获胜大类内，选择置信度最高的）
        final_fine_id = best_det.fine_class_id
        final_fine_name = best_det.fine_class_name_cn
        final_confidence = min(best_score, 1.0)

        # 一致性加成：多模型一致时提升置信度
        if vote_count >= 2:
            consistency_bonus = 1.0 + (vote_count - 1) * 0.1  # 每多一个一致模型+10%
            final_confidence = min(final_confidence * consistency_bonus, 1.0)

        # 构建最终检测结果
        final_detection = DetectionResult(
            bbox=best_det.bbox,
            category=best_cat,
            category_name=CATEGORY_MAP[best_cat]["name"],
            fine_class_id=final_fine_id,
            fine_class_name_cn=final_fine_name,
            confidence=final_confidence,
            source_model=ModelType.FEATURE_BASED,
            features={
                "vote_count": vote_count,
                "total_models": total_models,
                "consistency": consistency,
                "weighted_score": best_score,
            },
        )

        inference_time = (time.perf_counter() - start_time) * 1000

        result = MultiModalResult(
            final_prediction=final_detection,
            yolo_result=best_yolo,
            sahi_result=best_sahi,
            transformer_result=best_cascade,
            fusion_details={
                "strategy": "weighted_voting",
                "vote_count": vote_count,
                "total_models": total_models,
                "category_votes": {cat.name: len(v) for cat, v in category_votes.items()},
                "consistency_score": consistency,
                "models_used": {
                    "yolo": best_yolo is not None,
                    "sahi": best_sahi is not None,
                    "cascade": best_cascade is not None,
                },
            },
            total_inference_time_ms=inference_time,
            consistency_score=consistency,
        )

        logger.info("🔄 融合决策完成:")
        logger.info("   最终: %s → %s (置信度=%.1f%%)",
                   CATEGORY_MAP[best_cat]["name"], final_fine_name, final_confidence * 100)
        logger.info("   一致性: %.0f%% (%d/%d模型一致)", consistency * 100, vote_count, total_models)

        return result

    def _get_class_info(self, class_id: int) -> Tuple[str, str]:
        """获取类别信息"""
        for _, classes_dict in FINE_CLASSES.items():
            if class_id in classes_dict:
                return classes_dict[class_id]
        return ("Unknown", "未知")

    def _create_default_result(self) -> MultiModalResult:
        """创建默认结果"""
        default_det = DetectionResult(
            bbox=BoundingBox(0, 0, 100, 100, confidence=0.3),
            category=WasteCategory.OTHER_TRASH,
            category_name="其他垃圾",
            fine_class_id=0,
            fine_class_name_cn="一次性快餐盒",
            confidence=0.3,
            source_model=ModelType.FEATURE_BASED,
        )
        return MultiModalResult(
            final_prediction=default_det,
            fusion_details={"strategy": "default_fallback", "vote_count": 0, "total_models": 0},
            consistency_score=0.0,
        )


# 主系统：多模态融合分类器
class MultiModalFusionClassifier:
    """多模态融合分类主入口，三层推理+融合决策"""

    def __init__(self,
                 yolo_model_path: Optional[str] = None,
                 sahi_model_path: Optional[str] = None,
                 enable_sahi: bool = True,
                 sahi_slice_size: Tuple[int, int] = (320, 320)):
        """
        初始化多模态融合分类器

        @param yolo_model_path: Layer 1 & 3 主模型路径 (40类垃圾专用)
        @param sahi_model_path: Layer 2 SAHI专用模型路径 (可选，默认用yolov8n快速扫描)
        @param enable_sahi: 是否启用SAHI切片推理
        @param sahi_slice_size: SAHI切片尺寸
        """
        logger.info("🚀 初始化多模态融合分类系统...")

        # 自动检测模型路径（项目根目录为 app/ 的上级目录）
        project_root = Path(__file__).parent.parent

        if not yolo_model_path:
            default_yolo = str(project_root / "models" / "garbage_yolov8m_best.pt")
            if Path(default_yolo).exists():
                yolo_model_path = default_yolo

        if not sahi_model_path:
            default_sahi = str(project_root / "models" / "garbage_yolov8m_best.pt")
            if Path(default_sahi).exists():
                sahi_model_path = default_sahi
            else:
                sahi_model_path = yolo_model_path  # 回退：复用主模型

        # 第一层：YOLO检测器（40类垃圾专用 - 高精度）
        self.yolo_detector = YOLODetector(model_path=yolo_model_path, conf_threshold=0.15)
        logger.info("  ✅ Layer 1 (YOLO): %s", "已加载" if self.yolo_detector.is_loaded else "特征模式")

        # 第二层：SAHI引擎（使用独立模型 - 快速全局扫描）
        self.sahi_engine = None
        if enable_sahi:
            # 创建SAHI专用的轻量级检测器
            sahi_detector = YOLODetector(model_path=sahi_model_path, conf_threshold=0.10)
            self.sahi_engine = SAHIEngine(
                base_detector=sahi_detector,
                slice_size=sahi_slice_size,
                overlap_ratio=0.25,
                conf_threshold=0.05,
            )
            logger.info("  ✅ Layer 2 (SAHI): 切片尺寸=%dx%d, 模型=%s",
                       *sahi_slice_size, Path(sahi_model_path).name)

        # 第三层：双层级联精细化分类器（复用YOLO模型）
        self.cascade_classifier = CascadeFineClassifier(yolo_detector=self.yolo_detector)
        logger.info("  ✅ Layer 3 (双层级联): %s", "复用YOLO模型" if self.cascade_classifier.is_loaded else "特征匹配模式")

        # 融合决策器
        self.fusion_maker = FusionDecisionMaker()

        logger.info("🎉 多模态融合分类系统初始化完成！")

    def predict(self, image: Image.Image) -> MultiModalResult:
        """
        执行多模态融合推理

        @param image: PIL Image对象
        @return: 融合后的预测结果
        """
        total_start = time.perf_counter()
        logger.info("🔍 开始多模态融合推理...")

        # Layer 1: YOLO检测
        logger.info("  [Layer 1/YOLO] 检测中...")
        yolo_results = self.yolo_detector.detect(image, top_k=3)

        # Layer 2: SAHI切片推理
        sahi_results: List[DetectionResult] = []
        if self.sahi_engine:
            logger.info("  [Layer 2/SAHI] 切片推理中...")
            sahi_results = self.sahi_engine.detect_with_slicing(image, top_k=3)

        # Layer 3: 双层级联精细化分类
        logger.info("  [Layer 3/Cascade] 级联分类中...")
        cascade_results = self.cascade_classifier.classify(
            image, yolo_results=yolo_results, top_k=3
        )

        # 融合决策
        final_result = self.fusion_maker.fuse_predictions(
            yolo_results=yolo_results,
            sahi_results=sahi_results,
            cascade_results=cascade_results,
        )

        final_result.total_inference_time_ms = (time.perf_counter() - total_start) * 1000

        logger.info("=" * 50)
        logger.info("✅ 多模态融合推理完成")
        logger.info("   最终结果: %s (%s)",
                   final_result.final_prediction.fine_class_name_cn,
                   final_result.final_prediction.category_name)
        logger.info("   融合置信度: %.1f%%", final_result.final_prediction.confidence * 100)
        logger.info("   一致性: %.0f%%", final_result.consistency_score * 100)
        logger.info("   总耗时: %.1fms", final_result.total_inference_time_ms)
        logger.info("=" * 50)

        return final_result

    def predict_with_visualization(self, image: Image.Image,
                                    save_path: Optional[str] = None) -> Tuple[MultiModalResult, Image.Image]:
        """
        带可视化的预测（绘制各模型的检测结果）

        @param image: 输入图像
        @param save_path: 可视化结果保存路径
        @return: (预测结果, 可视化图像)
        """
        result = self.predict(image)

        vis_image = image.copy().convert('RGB')
        draw = ImageDraw.Draw(vis_image)

        colors = {
            ModelType.YOLO_DETECTOR: (255, 0, 0),
            ModelType.SAHI_SLICER: (0, 255, 0),
            ModelType.CASCADE_CLASSIFIER: (0, 0, 255),
        }

        labels = {
            ModelType.YOLO_DETECTOR: "YOLO",
            ModelType.SAHI_SLICER: "SAHI",
            ModelType.CASCADE_CLASSIFIER: "Cascade",
        }

        for model_type, res in [
            (ModelType.YOLO_DETECTOR, result.yolo_result),
            (ModelType.SAHI_SLICER, result.sahi_result),
            (ModelType.CASCADE_CLASSIFIER, result.transformer_result),
        ]:
            if res is None:
                continue

            bbox = res.bbox
            color = colors.get(model_type, (128, 128, 128))
            label = labels.get(model_type, "?")

            draw.rectangle([bbox.x1, bbox.y1, bbox.x2, bbox.y2], outline=color, width=3)
            text = f"{label}: {res.fine_class_name_cn} ({res.confidence:.0%})"
            draw.text((bbox.x1, bbox.y1 - 15), text, fill=color)

        # 最终结果（黄色粗框）
        final_bbox = result.final_prediction.bbox
        draw.rectangle([final_bbox.x1, final_bbox.y1, final_bbox.x2, final_bbox.y2],
                       outline=(255, 255, 0), width=5)
        final_text = f"FINAL: {result.final_prediction.fine_class_name_cn} ({result.final_prediction.confidence:.0%})"
        draw.text((final_bbox.x1, final_bbox.y1 - 30), final_text, fill=(255, 255, 0))

        if save_path:
            vis_image.save(save_path)
            logger.info("💾 可视化结果已保存: %s", save_path)

        return result, vis_image

    def get_system_info(self) -> dict:
        """获取系统详细信息"""
        return {
            "architecture": "YOLO + SAHI + 双层级联 (三模态融合)",
            "layers": {
                "layer_1_yolo": {
                    "status": "loaded" if self.yolo_detector.is_loaded else "fallback",
                    "is_waste_model": self.yolo_detector.is_waste_model,
                    "conf_threshold": self.yolo_detector.conf_threshold,
                },
                "layer_2_sahi": {
                    "enabled": self.sahi_engine is not None,
                    "slice_size": self.sahi_engine.slice_size if self.sahi_engine else None,
                    "overlap_ratio": self.sahi_engine.overlap_ratio if self.sahi_engine else None,
                },
                "layer_3_cascade": {
                    "status": "loaded" if self.cascade_classifier.is_loaded else "feature_matcher",
                    "routing_thresholds": {
                        "high": CascadeFineClassifier.CONF_HIGH,
                        "medium": CascadeFineClassifier.CONF_MEDIUM,
                    },
                },
            },
            "fusion": {
                "strategy": "weighted_voting_with_calibration",
                "model_reliability": {
                    model.value: info["weight"]
                    for model, info in FusionDecisionMaker.MODEL_RELIABILITY.items()
                },
            },
            "total_fine_grained_classes": sum(len(classes) for classes in FINE_CLASSES.values()),
        }


# 测试入口
if __name__ == "__main__":
    print("=" * 70)
    print("🧪 多模态融合垃圾分类识别系统 - 测试模式")
    print("   技术栈: YOLOv8 + SAHI + 双层级联精细化分类")
    print("=" * 70)

    def create_test_image(color: Tuple[int, int, int], size: Tuple[int, int] = (640, 480)) -> Image.Image:
        """创建测试用图像"""
        img_array = np.full((size[1], size[0], 3), color, dtype=np.uint8)
        noise = np.random.randint(-15, 15, img_array.shape, dtype=np.int16)
        img_array = np.clip(img_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        # 添加形状模拟真实物体
        img_pil = Image.fromarray(img_array)
        draw = ImageDraw.Draw(img_pil)

        cx, cy = size[0] // 2, size[1] // 2
        r = min(size) // 4
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=tuple(min(c+30, 255) for c in color))

        return img_pil

    # 初始化系统（自动检测模型）
    BASE_DIR = Path(__file__).parent.parent
    yolo_model = str(BASE_DIR / "models" / "garbage_yolov8m_best.pt")

    print(f"\n📦 正在初始化多模态融合分类器...")
    print(f"   YOLO模型: {yolo_model} ({'存在' if Path(yolo_model).exists() else '不存在'})")

    classifier = MultiModalFusionClassifier(
        yolo_model_path=yolo_model if Path(yolo_model).exists() else None,
        enable_sahi=True,
        sahi_slice_size=(320, 320),
    )

    # 打印系统信息
    info = classifier.get_system_info()
    print(f"\n📊 系统配置:")
    print(f"  架构: {info['architecture']}")
    print(f"  Layer 1 (YOLO): {info['layers']['layer_1_yolo']['status']}"
          f" {'(垃圾专用40类)' if info['layers']['layer_1_yolo']['is_waste_model'] else ''}")
    print(f"  Layer 2 (SAHI): {'启用' if info['layers']['layer_2_sahi']['enabled'] else '禁用'}")
    print(f"  Layer 3 (双层级联): {info['layers']['layer_3_cascade']['status']}")
    print(f"  总类别数: {info['total_fine_grained_classes']}")

    # 测试用例
    test_cases = [
        ("🥬 绿叶蔬菜 (厨余)", (40, 130, 40)),
        ("♻️ 透明塑料瓶 (可回收)", (220, 235, 245)),
        ("☠️ 红色干电池 (有害)", (200, 40, 40)),
        ("🗑️ 灰色烟蒂 (其他)", (100, 95, 90)),
        ("🍌 黄色香蕉皮 (厨余)", (240, 200, 40)),
        ("🫙 玻璃酒瓶 (可回收)", (200, 210, 230)),
    ]

    print("\n" + "=" * 70)
    print("🧪 开始测试...")
    print("=" * 70)

    for name, color in test_cases:
        print(f"\n{'━' * 60}")
        print(f"📸 测试样本: {name}")
        print(f"{'━' * 60}")

        test_img = create_test_image(color, size=(640, 480))
        result = classifier.predict(test_img)

        print(f"\n📋 三模态预测结果:")

        if result.yolo_result:
            print(f"  ├─ [YOLO] {result.yolo_result.fine_class_name_cn} "
                  f"({result.yolo_result.category_name}) - {result.yolo_result.confidence:.1%}")

        if result.sahi_result:
            print(f"  ├─ [SAHI] {result.sahi_result.fine_class_name_cn} "
                  f"({result.sahi_result.category_name}) - {result.sahi_result.confidence:.1%}")

        if result.transformer_result:
            print(f"  ├─ [Cascade] {result.transformer_result.fine_class_name_cn} "
                  f"({result.transformer_result.category_name}) - {result.transformer_result.confidence:.1%}")

        print(f"  ├─ {'─' * 45}")
        print(f"  └─ ⭐ 最终: {result.final_prediction.fine_class_name_cn} "
              f"({result.final_prediction.category_name})")
        print(f"      置信度: {result.final_prediction.confidence:.1%}")
        vc = result.fusion_details.get("vote_count", 0)
        tm = result.fusion_details.get("total_models", 0)
        print(f"      一致性: {result.consistency_score:.0%} ({vc}/{tm}模型)")
        print(f"      总耗时: {result.total_inference_time_ms:.1f}ms")

    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)
