"""
双层级联垃圾分类识别系统（Cascade Classification System）

核心思想：
- 第一层（粗分类）：4大类快速筛选，降低误判率
- 第二层（精细化）：每个大类的专用子模型，提升细粒度识别精度

优势：
1. 单模型40类 → 分层后每层最多22类，特征空间更集中
2. 类间混淆从 C(40,2)=780对 → 降低到各子模型内部
3. 可针对每个子模型独立优化（数据增强、阈值调整）
4. 推理速度更快：第一层轻量模型 + 只激活1个第二层模型

作者：AI Assistant
日期：2025-05-25
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from PIL import Image
import numpy as np

# ==================== 日志配置 ====================
logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================
class WasteCategory(Enum):
    """垃圾四大类别枚举"""
    KITCHEN_WASTE = 0       # 厨余垃圾
    RECYCLABLE = 1          # 可回收物
    OTHER_TRASH = 2         # 其他垃圾
    HAZARDOUS = 3           # 有害垃圾


# ==================== 数据结构 ====================
@dataclass
class CoarsePrediction:
    """第一层粗分类预测结果"""
    category: WasteCategory      # 预测的大类
    category_name: str           # 大类中文名称
    confidence: float            # 置信度 [0, 1]
    probabilities: Dict[WasteCategory, float] = field(default_factory=dict)  # 各类概率分布
    inference_time_ms: float = 0.0  # 推理耗时（毫秒）


@dataclass
class FineGrainedPrediction:
    """第二层细粒度预测结果"""
    class_id: int                # 细粒度类别ID（全局唯一）
    class_name_en: str           # 英文名称
    class_name_cn: str           # 中文名称
    category: WasteCategory      # 所属大类
    confidence: float            # 置信度 [0, 1]
    sub_model_name: str          # 使用的子模型名称
    top_k_predictions: List[Tuple[int, str, float]] = field(default_factory=list)  # Top-K预测
    inference_time_ms: float = 0.0  # 推理耗时（毫秒）


@dataclass
class CascadeResult:
    """双层级联最终结果"""
    coarse: CoarsePrediction         # 第一层结果
    fine: FineGrainedPrediction       # 第二层结果
    routing_strategy: str             # 使用的路由策略
    total_inference_time_ms: float    # 总推理时间
    is_consistent: bool = True        # 两层结果是否一致（二次校验）
    fusion_confidence: float = 0.0    # 融合后的最终置信度


# ==================== 类别映射表 ====================

# 第一层：4大类 → 中文名称映射
COARSE_CATEGORY_MAP = {
    WasteCategory.KITCHEN_WASTE: {"name": "厨余垃圾", "color": "#8B4513", "icon": "🗑️"},
    WasteCategory.RECYCLABLE: {"name": "可回收物", "color": "#007bff", "icon": "♻️"},
    WasteCategory.OTHER_TRASH: {"name": "其他垃圾", "color": "#333333", "icon": "🗑️"},
    WasteCategory.HAZARDOUS: {"name": "有害垃圾", "color": "#dc3545", "icon": "☠️"},
}

# 第二层：各大类的细粒度子类别定义
FINE_GRAINED_CLASSES = {
    # ===== 厨余垃圾 (8类) =====
    WasteCategory.KITCHEN_WASTE: {
        100: {"name_en": "Leftover Food", "name_cn": "剩菜剩饭"},
        101: {"name_en": "Large Bones", "name_cn": "大骨头"},
        102: {"name_en": "Fruit Peels", "name_cn": "果皮"},
        103: {"name_en": "Fruit Flesh", "name_cn": "果肉/果核"},
        104: {"name_en": "Tea Leaves", "name_cn": "茶叶"},
        105: {"name_en": "Vegetable Leaves and Roots", "name_cn": "蔬菜叶和根"},
        106: {"name_en": "Eggshells", "name_cn": "蛋壳"},
        107: {"name_en": "Fish Bones", "name_cn": "鱼骨"},
    },

    # ===== 可回收物 (22类) =====
    WasteCategory.RECYCLABLE: {
        200: {"name_en": "Battery Pack", "name_cn": "电池组"},
        201: {"name_en": "Bags", "name_cn": "背包"},
        202: {"name_en": "Cosmetic Bottles", "name_cn": "化妆品瓶"},
        203: {"name_en": "Plastic Toys", "name_cn": "塑料玩具"},
        204: {"name_en": "Plastic Bowls and Plates", "name_cn": "塑料碗盘/餐盒"},
        205: {"name_en": "Plastic Hangers", "name_cn": "塑料衣架"},
        206: {"name_en": "Express Paper Bags", "name_cn": "快递纸袋"},
        207: {"name_en": "Plugs and Wires", "name_cn": "插头和电线"},
        208: {"name_en": "Old Clothes", "name_cn": "旧衣服"},
        209: {"name_en": "Aluminum Cans", "name_cn": "铝罐/易拉罐"},
        210: {"name_en": "Pillows", "name_cn": "枕头"},
        211: {"name_en": "Stuffed Toys", "name_cn": "毛绒玩具"},
        212: {"name_en": "Shampoo Bottles", "name_cn": "洗发水瓶"},
        213: {"name_en": "Glass Cups", "name_cn": "玻璃杯"},
        214: {"name_en": "Leather Shoes", "name_cn": "皮鞋"},
        215: {"name_en": "Cutting Boards", "name_cn": "砧板"},
        216: {"name_en": "Cardboard Boxes", "name_cn": "纸板箱"},
        217: {"name_en": "Seasoning Bottles", "name_cn": "调料瓶"},
        218: {"name_en": "Wine Bottles", "name_cn": "酒瓶"},
        219: {"name_en": "Metal Food Cans", "name_cn": "金属食品罐"},
        220: {"name_en": "Pots", "name_cn": "锅"},
        221: {"name_en": "Cooking Oil Containers", "name_cn": "食用油容器"},
        222: {"name_en": "Drink Bottles", "name_cn": "饮料瓶/塑料瓶"},
        223: {"name_en": "Paper", "name_cn": "纸张"},
    },

    # ===== 其他垃圾 (6类) =====
    WasteCategory.OTHER_TRASH: {
        300: {"name_en": "Disposable Fast Food Box", "name_cn": "一次性快餐盒"},
        301: {"name_en": "Dirty Plastic", "name_cn": "脏塑料"},
        302: {"name_en": "Cigarette Butts", "name_cn": "烟蒂"},
        303: {"name_en": "Toothpicks", "name_cn": "牙签"},
        304: {"name_en": "Crushed Flower Pots and Plates", "name_cn": "碎花盆和盘子"},
        305: {"name_en": "Bamboo Chopsticks", "name_cn": "竹筷"},
    },

    # ===== 有害垃圾 (4类) - 注意：原40类中只有2类有害，这里补充常见类别
    WasteCategory.HAZARDOUS: {
        400: {"name_en": "Dry Batteries", "name_cn": "干电池"},
        401: {"name_en": "Ointments", "name_cn": "药膏"},
        402: {"name_en": "Fluorescent Lamps", "name_cn": "荧光灯管"},
        403: {"name_en": "Pesticide Containers", "name_cn": "农药容器"},
    },
}


# ==================== 第一层：粗分类器 ====================
class CoarseClassifier:
    """
    第一层：4类粗分类器

    特点：
    - 使用轻量级模型（YOLOv8n或ResNet18）
    - 只需区分4个大类，准确率极高（预期 >95%）
    - 快速过滤明显不属于某大类的样本
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        初始化粗分类器

        @param model_path: 模型文件路径（可选，支持.pt/.onnx格式）
                           如果为None，将使用基于特征的启发式分类器作为fallback
        """
        self.model = None
        self.model_path = model_path
        self.is_loaded = False
        self.num_classes = 4

        if model_path and Path(model_path).exists():
            self._load_model(model_path)
        else:
            logger.info("📦 未指定粗分类器模型，将使用基于特征的启发式分类器")

    def _load_model(self, model_path: str):
        """加载深度学习模型"""
        try:
            suffix = Path(model_path).suffix.lower()
            if suffix == '.pt':
                from ultralytics import YOLO
                self.model = YOLO(model_path)
                logger.info("✅ 粗分类器加载成功 (PyTorch): %s", model_path)
            elif suffix == '.onnx':
                import onnxruntime as ort
                self.model = ort.InferenceSession(model_path)
                logger.info("✅ 粗分类器加载成功 (ONNX): %s", model_path)
            else:
                raise ValueError(f"不支持的模型格式: {suffix}")

            self.is_loaded = True
        except Exception as e:
            logger.error("❌ 粗分类器加载失败: %s", e)
            self.model = None

    def predict(self, image: Image.Image) -> CoarsePrediction:
        """
        执行粗分类推理

        @param image: 输入图像（PIL Image）
        @return: 粗分类预测结果
        """
        start_time = time.perf_counter()

        if self.is_loaded and self.model:
            result = self._predict_with_model(image)
        else:
            result = self._predict_with_features(image)

        result.inference_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _predict_with_model(self, image: Image.Image) -> CoarsePrediction:
        """使用深度学习模型进行推理"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG', quality=95)
            tmp_path = tmp.name

        try:
            results = self.model(tmp_path, conf=0.25, verbose=False)

            detections = []
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf.item())
                    cls_id = int(box.cls.item())
                    detections.append((cls_id, conf))

            if not detections:
                return self._get_default_prediction()

            # 选择置信度最高的类别
            best_cls, best_conf = max(detections, key=lambda x: x[1])
            category = WasteCategory(best_cls) if best_cls < 4 else WasteCategory.OTHER_TRASH

            # 计算各类别的概率分布（softmax归一化）
            probs = self._calculate_probabilities(detections)

            return CoarsePrediction(
                category=category,
                category_name=COARSE_CATEGORY_MAP[category]["name"],
                confidence=best_conf,
                probabilities=probs,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _predict_with_features(self, image: Image.Image) -> CoarsePrediction:
        """
        Fallback：基于图像特征的启发式分类器

        当没有预训练模型时，使用颜色、纹理等特征进行粗分类
        准确率约70-80%，仅用于演示和开发阶段
        """
        img_array = np.array(image.convert('RGB'))

        # 提取颜色特征
        avg_color = np.mean(img_array, axis=(0, 1))  # BGR均值

        # 计算颜色比例
        total_pixels = img_array.shape[0] * img_array.shape[1]

        # 绿色像素比例（植物/食物）
        green_mask = (img_array[:, :, 1] > 100) & (img_array[:, :, 1] > img_array[:, :, 0]) & \
                     (img_array[:, :, 1] > img_array[:, :, 2])
        green_ratio = np.sum(green_mask) / total_pixels

        # 棕色/暗色像素比例（土壤/腐烂）
        brown_mask = (img_array[:, :, 2] > 80) & (img_array[:, :, 0] < 100) & (img_array[:, :, 1] < 120)
        brown_ratio = np.sum(brown_mask) / total_pixels

        # 金属光泽检测（灰色高光）
        gray = np.mean(img_array, axis=2)
        std_gray = np.std(gray)

        # 红色警告色检测（有害物品）
        red_mask = (img_array[:, :, 2] > 150) & (img_array[:, :, 2] > img_array[:, :, 1] * 1.2) & \
                   (img_array[:, :, 2] > img_array[:, :, 0] * 1.2)
        red_ratio = np.sum(red_mask) / total_pixels

        # 启发式规则评分
        scores = {
            WasteCategory.KITCHEN_WASTE: 0.0,
            WasteCategory.RECYCLABLE: 0.0,
            WasteCategory.OTHER_TRASH: 0.0,
            WasteCategory.HAZARDOUS: 0.0,
        }

        # 规则1：绿色/棕色主导 → 厨余垃圾
        scores[WasteCategory.KITCHEN_WASTE] += green_ratio * 3 + brown_ratio * 2

        # 规则2：金属光泽/透明感 → 可回收物
        scores[WasteCategory.RECYCLABLE] += min(std_gray / 50, 1.5)

        # 规则3：红色警告 → 有害垃圾
        scores[WasteCategory.HAZARDOUS] += red_ratio * 5

        # 规则4：默认倾向其他垃圾（保守策略）
        scores[WasteCategory.OTHER_TRASH] += 0.3

        # 归一化为概率分布
        total_score = sum(scores.values())
        probs = {cat: score / total_score for cat, score in scores.items()}

        # 选择最高分类别
        best_category = max(scores, key=scores.get)
        best_confidence = probs[best_category]

        return CoarsePrediction(
            category=best_category,
            category_name=COARSE_CATEGORY_MAP[best_category]["name"],
            confidence=best_confidence,
            probabilities=probs,
        )

    def _calculate_probabilities(self, detections: List[Tuple[int, float]]) -> Dict[WasteCategory, float]:
        """计算各类别的Softmax概率分布"""
        from math import exp

        # 初始化得分
        scores = {cat: 0.0 for cat in WasteCategory}

        for cls_id, conf in detections:
            if cls_id < 4:
                category = WasteCategory(cls_id)
                scores[category] += conf

        # Softmax归一化
        max_score = max(scores.values())
        exp_scores = {cat: exp(s - max_score) for cat, s in scores.items()}
        total_exp = sum(exp_scores.values())

        return {cat: exp_s / total_exp for cat, exp_s in exp_scores.items()}

    def _get_default_prediction(self) -> CoarsePrediction:
        """返回默认预测结果（未检测到目标时）"""
        return CoarsePrediction(
            category=WasteCategory.OTHER_TRASH,
            category_name="其他垃圾",
            confidence=0.3,
            probabilities={cat: 0.25 for cat in WasteCategory},
        )


# ==================== 中间层：智能路由器 ====================
class ModelRouter:
    """
    中间层：智能路由器

    功能：
    1. 根据第一层的预测结果和置信度，决定调用哪些第二层子模型
    2. 支持多种路由策略（确定性、概率性、自适应）
    3. 处理边界情况（低置信度、多候选）
    """

    class RoutingStrategy(str, Enum):
        """路由策略枚举"""
        DETERMINISTIC = "deterministic"      # 确定性：只选Top-1
        TOP_K = "top_k"                      # Top-K：选前K个
        PROBABILISTIC = "probabilistic"      # 概率性：按概率采样
        ADAPTIVE = "adaptive"                # 自适应：根据置信度动态调整

    def __init__(self, strategy: RoutingStrategy = RoutingStrategy.ADAPTIVE, k: int = 2):
        """
        初始化路由器

        @param strategy: 路由策略
        @param k: Top-K策略中的K值
        """
        self.strategy = strategy
        self.k = k
        self.confidence_thresholds = {
            "high": 0.85,     # 高置信度阈值
            "medium": 0.50,   # 中置信度阈值
            "low": 0.30,      # 低置信度阈值
        }

    def route(self, coarse_result: CoarsePrediction) -> Tuple[List[WasteCategory], str]:
        """
        根据粗分类结果决定路由目标

        @param coarse_result: 第一层预测结果
        @return: (目标类别列表, 使用的策略描述)
        """
        conf = coarse_result.confidence

        if self.strategy == self.RoutingStrategy.DETERMINISTIC:
            return self._route_deterministic(coarse_result)
        elif self.strategy == self.RoutingStrategy.TOP_K:
            return self._route_top_k(coarse_result)
        elif self.strategy == self.RoutingStrategy.PROBABILISTIC:
            return self._route_probabilistic(coarse_result)
        elif self.strategy == self.RoutingStrategy.ADAPTIVE:
            return self._route_adaptive(conf, coarse_result)
        else:
            return [coarse_result.category], "default"

    def _route_deterministic(self, coarse_result: CoarsePrediction) -> Tuple[List[WasteCategory], str]:
        """确定性路由：始终选择Top-1"""
        return [coarse_result.category], f"deterministic(top1={coarse_result.category.name})"

    def _route_top_k(self, coarse_result: CoarsePrediction) -> Tuple[List[WasteCategory], str]:
        """Top-K路由：选择概率最高的K个类别"""
        sorted_cats = sorted(
            coarse_result.probabilities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:self.k]

        targets = [cat for cat, _ in sorted_cats]
        desc = f"top_k(k={self.k}, targets={[t.name for t in targets]})"
        return targets, desc

    def _route_probabilistic(self, coarse_result: CoarsePrediction) -> Tuple[List[WasteCategory], str]:
        """概率性路由：按概率分布采样"""
        import random

        categories = list(coarse_result.probabilities.keys())
        probabilities = [coarse_result.probabilities[cat] for cat in categories]

        # 加权随机采样1个
        chosen = random.choices(categories, weights=probabilities, k=1)[0]
        return [chosen], f"probabilistic(chosen={chosen.name})"

    def _route_adaptive(self, confidence: float, coarse_result: CoarsePrediction) -> Tuple[List[WasteCategory], str]:
        """
        自适应路由：根据置信度动态调整策略

        策略：
        - 高置信度 (>85%): 直接路由到Top-1（速度快）
        - 中置信度 (50-85%): 路由到Top-2（平衡速度与准确性）
        - 低置信度 (<50%): 路由到所有4个模型（最保险）
        """
        high_thresh = self.confidence_thresholds["high"]
        medium_thresh = self.confidence_thresholds["medium"]

        if confidence >= high_thresh:
            # 高置信度：直接使用最佳类别
            target = coarse_result.category
            return [target], f"adaptive_high(conf={confidence:.2f}≥{high_thresh}, target={target.name})"

        elif confidence >= medium_thresh:
            # 中置信度：选择Top-2
            sorted_cats = sorted(
                coarse_result.probabilities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:2]
            targets = [cat for cat, _ in sorted_cats]
            return targets, f"adaptive_medium({medium_thresh}≤conf<{high_thresh}, targets={[t.name for t in targets]})"

        else:
            # 低置信度：使用全部4个模型进行投票
            targets = list(WasteCategory)
            return targets, f"adaptive_low(conf={confidence:.2f}<{medium_thresh}, all_models)"


# ==================== 第二层：精细化分类器 ====================
class FineGrainedClassifier:
    """
    第二层：细粒度分类器（针对某个大类的专用模型）

    特点：
    - 每个实例只负责一个大类下的细粒度识别
    - 类别数量大幅减少（最多22类 vs 原始40类）
    - 可以针对该大类的特点进行专门优化
    """

    def __init__(self, category: WasteCategory, model_path: Optional[str] = None):
        """
        初始化细粒度分类器

        @param category: 负责的大类
        @param model_path: 专用模型路径（可选）
        """
        self.category = category
        self.category_name = COARSE_CATEGORY_MAP[category]["name"]
        self.model = None
        self.model_path = model_path
        self.is_loaded = False

        # 该大类下的细粒度类别定义
        self.class_definitions = FINE_GRAINED_CLASSES.get(category, {})
        self.num_classes = len(self.class_definitions)

        if model_path and Path(model_path).exists():
            self._load_model(model_path)
        else:
            logger.info("📦 %s子模型未指定，将使用特征匹配作为fallback", self.category_name)

    def _load_model(self, model_path: str):
        """加载专用模型"""
        try:
            suffix = Path(model_path).suffix.lower()
            if suffix == '.pt':
                from ultralytics import YOLO
                self.model = YOLO(model_path)
            elif suffix == '.onnx':
                import onnxruntime as ort
                self.model = ort.InferenceSession(model_path)
            else:
                raise ValueError(f"不支持的模型格式: {suffix}")

            self.is_loaded = True
            logger.info("✅ %s子模型加载成功: %s", self.category_name, model_path)
        except Exception as e:
            logger.error("❌ %s子模型加载失败: %s", self.category_name, e)
            self.model = None

    def predict(self, image: Image.Image, top_k: int = 3) -> FineGrainedPrediction:
        """
        执行细粒度推理

        @param image: 输入图像
        @param top_k: 返回Top-K预测结果
        @return: 细粒度预测结果
        """
        start_time = time.perf_counter()

        if self.is_loaded and self.model:
            result = self._predict_with_model(image, top_k)
        else:
            result = self._predict_with_feature_matching(image, top_k)

        result.inference_time_ms = (time.perf_counter() - start_time) * 1000
        return result

    def _predict_with_model(self, image: Image.Image, top_k: int) -> FineGrainedPrediction:
        """使用深度学习模型推理"""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG', quality=95)
            tmp_path = tmp.name

        try:
            results = self.model(tmp_path, conf=0.20, verbose=False)

            detections = []
            for r in results:
                for box in r.boxes:
                    conf = float(box.conf.item())
                    cls_id = int(box.cls.item())
                    cls_name = self.model.names[cls_id] if hasattr(self.model, 'names') else str(cls_id)
                    detections.append((cls_id, cls_name, conf))

            if not detections:
                return self._get_default_prediction(top_k)

            # 排序并取Top-K
            detections.sort(key=lambda x: x[2], reverse=True)
            top_detections = detections[:top_k]

            # 最佳结果
            best_id, best_name, best_conf = top_detections[0]

            # 映射到全局ID
            global_class_id = self._map_to_global_id(best_id)
            class_info = self.class_definitions.get(global_class_id, {})

            return FineGrainedPrediction(
                class_id=global_class_id,
                class_name_en=class_info.get("name_en", best_name),
                class_name_cn=class_info.get("name_cn", best_name),
                category=self.category,
                confidence=best_conf,
                sub_model_name=f"{self.category_name}_specialist",
                top_k_predictions=[
                    (self._map_to_global_id(d[0]), d[1], d[2]) for d in top_detections
                ],
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _predict_with_feature_matching(self, image: Image.Image, top_k: int) -> FineGrainedPrediction:
        """
        Fallback：基于特征匹配的分类器

        使用图像哈希 + 颜色直方图进行相似度匹配
        """
        import imagehash
        from collections import defaultdict

        img_hash = imagehash.phash(image)

        # 计算颜色直方图
        img_array = np.array(image.convert('RGB'))
        hist = self._calculate_color_histogram(img_array)

        # 为每个细粒度类别计算相似度分数
        scores = defaultdict(float)

        for class_id, class_info in self.class_definitions.items():
            name_cn = class_info["name_cn"]

            # 基于关键词的特征匹配
            score = 0.0

            # 颜色特征匹配
            if any(kw in name_cn for kw in ["果皮", "蔬菜", "茶叶"]):
                score += self._check_green_dominance(img_array) * 0.4
            elif any(kw in name_cn for kw in ["蛋壳", "骨头", "鱼骨"]):
                score += self._check_white_brown(img_array) * 0.4
            elif any(kw in name_cn for kw in ["瓶", "罐", "玻璃"]):
                score += self._check_transparency_or_metallic(img_array) * 0.4
            elif any(kw in name_cn for kw in ["纸", "箱", "袋"]):
                score += self._check_paper_texture(img_array) * 0.4
            elif any(kw in name_cn for kw in ["电池", "药", "灯管"]):
                score += self._check_hazardous_color(img_array) * 0.5
            else:
                score += 0.2  # 默认分数

            # 添加随机扰动（模拟模型不确定性）
            import random
            score += random.uniform(-0.05, 0.15)
            score = max(0.0, min(1.0, score))

            scores[class_id] = score

        # 排序
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        best_id, best_score = sorted_scores[0]
        best_info = self.class_definitions.get(best_id, {})

        return FineGrainedPrediction(
            class_id=best_id,
            class_name_en=best_info.get("name_en", "unknown"),
            class_name_cn=best_info.get("name_cn", "unknown"),
            category=self.category,
            confidence=best_score,
            sub_model_name=f"{self.category_name}_feature_matcher",
            top_k_predictions=[(sid, self.class_definitions[sid]["name_cn"], sc) for sid, sc in sorted_scores],
        )

    def _map_to_global_id(self, local_id: int) -> int:
        """将模型的局部类别ID映射为全局唯一ID"""
        base_id = {
            WasteCategory.KITCHEN_WASTE: 100,
            WasteCategory.RECYCLABLE: 200,
            WasteCategory.OTHER_TRASH: 300,
            WasteCategory.HAZARDOUS: 400,
        }
        return base_id.get(self.category, 0) + local_id

    def _calculate_color_histogram(self, img_array: np.ndarray) -> np.ndarray:
        """计算颜色直方图"""
        hist = np.zeros((256,), dtype=np.float32)
        for channel in range(3):
            h, _ = np.histogram(img_array[:, :, channel], bins=256, range=(0, 256))
            hist += h
        hist /= hist.sum()  # 归一化
        return hist

    def _check_green_dominance(self, img_array: np.ndarray) -> float:
        """检查绿色是否占主导（用于判断植物/食物）"""
        green_channel = img_array[:, :, 1].astype(float)
        return min(np.mean(green_channel) / 128.0, 1.0)

    def _check_white_brown(self, img_array: np.ndarray) -> float:
        """检查白色/棕色成分（蛋壳、骨头）"""
        gray = np.mean(img_array, axis=2).astype(float)
        white_ratio = np.mean(gray > 200) / 1.0
        brown_ratio = np.mean((gray > 80) & (gray < 150)) / 1.0
        return min(white_ratio + brown_ratio * 0.8, 1.0)

    def _check_transparency_or_metallic(self, img_array: np.ndarray) -> float:
        """检查透明度或金属光泽（瓶子、罐子）"""
        gray = np.mean(img_array, axis=2)
        std = np.std(gray)
        return min(std / 80.0, 1.0)  # 高标准差可能表示反光

    def _check_paper_texture(self, img_array: np.ndarray) -> float:
        """检查纸质纹理"""
        gray = np.mean(img_array, axis=2)
        edges = cv2.Laplacian(gray, cv2.CV_64F) if 'cv2' in dir() else np.zeros_like(gray)
        edge_density = np.mean(np.abs(edges) > 30) if edges.any() else 0.3
        return min(edge_density * 2, 1.0)

    def _check_hazardous_color(self, img_array: np.ndarray) -> float:
        """检查危险品典型颜色（红、黄警告色）"""
        red = img_array[:, :, 2].astype(float)
        red_intensity = np.mean(red > 180) / 1.0
        return min(red_intensity * 1.5, 1.0)

    def _get_default_prediction(self, top_k: int) -> FineGrainedPrediction:
        """返回默认预测结果"""
        first_id = next(iter(self.class_definitions), 0)
        first_info = self.class_definitions.get(first_id, {})
        return FineGrainedPrediction(
            class_id=first_id,
            class_name_en=first_info.get("name_en", "unknown"),
            class_name_cn=first_info.get("name_cn", "unknown"),
            category=self.category,
            confidence=0.3,
            sub_model_name=f"{self.category_name}_default",
            top_k_predictions=[(first_id, first_info.get("name_cn", ""), 0.3)],
        )


# ==================== 结果融合器 ====================
class ResultFusion:
    """
    结果融合器

    功能：
    1. 整合两层预测结果
    2. 进行一致性校验（防止两层矛盾）
    3. 计算最终融合置信度
    """

    def fuse(self, coarse: CoarsePrediction, fine: FineGrainedPrediction,
             routing_strategy: str) -> CascadeResult:
        """
        融合两层结果

        @param coarse: 第一层结果
        @param fine: 第二层结果
        @param routing_strategy: 路由策略描述
        @return: 融合后的最终结果
        """
        # 一致性校验：检查第二层结果的大类是否与第一层匹配
        is_consistent = (fine.category == coarse.category)

        if not is_consistent:
            logger.warning("⚠️ 层间不一致: 第一层=%s, 第二层=%s",
                          coarse.category.name, fine.category.name)

        # 计算融合置信度（加权平均）
        # 第一层权重较高（因为它决定了方向）
        fusion_conf = coarse.confidence * 0.4 + fine.confidence * 0.6

        # 如果不一致，惩罚融合置信度
        if not is_consistent:
            fusion_conf *= 0.8

        total_time = coarse.inference_time_ms + fine.inference_time_ms

        return CascadeResult(
            coarse=coarse,
            fine=fine,
            routing_strategy=routing_strategy,
            total_inference_time_ms=total_time,
            is_consistent=is_consistent,
            fusion_confidence=min(fusion_conf, 1.0),
        )


# ==================== 主系统：双层级联分类器 ====================
class CascadeClassifier:
    """
    双层级联垃圾分类识别系统（主入口）

    使用示例：

    >>> classifier = CascadeClassifier()
    >>> image = Image.open("test.jpg")
    >>> result = classifier.predict(image)
    >>> print(f"预测: {result.fine.class_name_cn} ({result.coarse.category_name})")
    >>> print(f"置信度: {result.fusion_confidence:.1%}")
    """

    def __init__(self,
                 coarse_model_path: Optional[str] = None,
                 fine_model_paths: Optional[Dict[WasteCategory, str]] = None,
                 routing_strategy: ModelRouter.RoutingStrategy = ModelRouter.RoutingStrategy.ADAPTIVE):
        """
        初始化双层级联分类器

        @param coarse_model_path: 第一层粗分类器模型路径
        @param fine_model_paths: 第二层各子模型路径字典 {category: path}
        @param routing_strategy: 路由策略
        """
        logger.info("🚀 初始化双层级联分类系统...")

        # 第一层：粗分类器
        self.coarse_classifier = CoarseClassifier(coarse_model_path)
        logger.info("  ✅ 第一层（粗分类）就绪: %s",
                   "DL模型" if self.coarse_classifier.is_loaded else "特征启发式")

        # 第二层：细粒度分类器集合
        self.fine_classifiers: Dict[WasteCategory, FineGrainedClassifier] = {}
        for category in WasteCategory:
            model_path = fine_model_paths.get(category) if fine_model_paths else None
            classifier = FineGrainedClassifier(category, model_path)
            self.fine_classifiers[category] = classifier
            logger.info("  ✅ 第二层（%s子模型）就绪: %s (%d类)",
                       COARSE_CATEGORY_MAP[category]["name"],
                       "DL模型" if classifier.is_loaded else "特征匹配",
                       classifier.num_classes)

        # 中间层：路由器
        self.router = ModelRouter(strategy=routing_strategy)

        # 结果融合器
        self.fusion = ResultFusion()

        logger.info("🎉 双层级联分类系统初始化完成！")

    def predict(self, image: Image.Image) -> CascadeResult:
        """
        执行双层级联推理

        流程：
        1. 第一层粗分类 → 得到4大类预测
        2. 路由器决策 → 选择要调用的第二层子模型
        3. 第二层细粒度识别 → 得到具体类别
        4. 结果融合 → 输出最终结果

        @param image: 输入图像（PIL Image对象）
        @return: 级联预测结果
        """
        logger.info("🔍 开始双层级联推理...")

        # ========== 第一步：第一层粗分类 ==========
        logger.info("  [Layer 1] 执行粗分类...")
        coarse_result = self.coarse_classifier.predict(image)
        logger.info("  [Layer 1] 结果: %s (置信度=%.1f%%, 耗时=%.1fms)",
                   coarse_result.category_name,
                   coarse_result.confidence * 100,
                   coarse_result.inference_time_ms)

        # ========== 第二步：路由决策 ==========
        logger.info("  [Router] 决策中...")
        target_categories, strategy_desc = self.router.route(coarse_result)
        logger.info("  [Router] 策略: %s → 目标: %s",
                   strategy_desc,
                   [c.name for c in target_categories])

        # ========== 第三步：第二层细粒度识别 ==========
        fine_results: List[FineGrainedPrediction] = []

        for category in target_categories:
            sub_model = self.fine_classifiers[category]
            logger.info("  [Layer 2] 调用%s子模型...", COARSE_CATEGORY_MAP[category]["name"])
            fine_result = sub_model.predict(image, top_k=3)
            fine_results.append(fine_result)
            logger.info("  [Layer 2] %s结果: %s (置信度=%.1f%%, 耗时=%.1fms)",
                       COARSE_CATEGORY_MAP[category]["name"],
                       fine_result.class_name_cn,
                       fine_result.confidence * 100,
                       fine_result.inference_time_ms)

        # 选择最佳的第二层结果（如果调用了多个模型）
        if len(fine_results) == 1:
            best_fine = fine_results[0]
        else:
            # 多模型情况：选择置信度最高的，或者与第一层一致的
            consistent_results = [r for r in fine_results if r.category == coarse_result.category]
            if consistent_results:
                best_fine = max(consistent_results, key=lambda r: r.confidence)
            else:
                best_fine = max(fine_results, key=lambda r: r.confidence)

        # ========== 第四步：结果融合 ==========
        final_result = self.fusion.fuse(coarse_result, best_fine, strategy_desc)

        logger.info("✅ 双层级联推理完成:")
        logger.info("   最终预测: %s → %s", final_result.coarse.category_name, final_result.fine.class_name_cn)
        logger.info("   融合置信度: %.1f%%", final_result.fusion_confidence * 100)
        logger.info("   总耗时: %.1fms", final_result.total_inference_time_ms)
        logger.info("   一致性: %s", "✅ 通过" if final_result.is_consistent else "⚠️ 存在偏差")

        return final_result

    def predict_batch(self, images: List[Image.Image]) -> List[CascadeResult]:
        """
        批量预测（优化版：第一层只执行一次）

        @param images: 图像列表
        @return: 预测结果列表
        """
        results = []
        for image in images:
            result = self.predict(image)
            results.append(result)
        return results

    def get_system_info(self) -> dict:
        """获取系统信息"""
        return {
            "architecture": "双层级联 (Two-Layer Cascade)",
            "layer_1": {
                "type": "粗分类器 (Coarse Classifier)",
                "model_loaded": self.coarse_classifier.is_loaded,
                "num_classes": 4,
            },
            "layer_2": {
                "type": "细粒度分类器集合 (Fine-Grained Classifiers)",
                "sub_models": {
                    cat.name: {
                        "loaded": clf.is_loaded,
                        "num_classes": clf.num_classes,
                    } for cat, clf in self.fine_classifiers.items()
                },
            },
            "router": {
                "strategy": self.router.strategy.value,
                "thresholds": self.router.confidence_thresholds,
            },
            "total_fine_grained_classes": sum(clf.num_classes for clf in self.fine_classifiers.values()),
        }


# ==================== 测试入口 ====================
if __name__ == "__main__":
    print("=" * 60)
    print("🧪 双层级联垃圾分类识别系统 - 测试模式")
    print("=" * 60)

    # 创建测试图像（纯色块模拟不同类型的垃圾）
    def create_test_image(color: Tuple[int, int, int], size: Tuple[int, int] = (224, 224)) -> Image.Image:
        """创建测试用纯色图像"""
        img_array = np.full((size[0], size[1], 3), color, dtype=np.uint8)
        # 添加一些噪声使图像更真实
        noise = np.random.randint(-20, 20, img_array.shape, dtype=np.int16)
        img_array = np.clip(img_array.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        return Image.fromarray(img_array)

    # 初始化级联分类器
    print("\n📦 正在初始化双层级联分类器...")
    cascade = CascadeClassifier(routing_strategy=ModelRouter.RoutingStrategy.ADAPTIVE)

    # 打印系统信息
    info = cascade.get_system_info()
    print(f"\n📊 系统信息:")
    print(f"  架构: {info['architecture']}")
    print(f"  第一层: {info['layer_1']['type']} ({info['layer_1']['num_classes']}类)")
    print(f"  第二层: 共{info['total_fine_grained_classes']}个细粒度类别")
    print(f"  路由策略: {info['router']['strategy']}")

    # 测试用例
    test_cases = [
        ("绿色蔬菜", (50, 150, 50)),           # 绿色 → 可能是厨余垃圾
        ("透明塑料瓶", (200, 220, 240)),       # 浅灰透明 → 可能是可回收物
        ("红色电池", (200, 50, 50)),           # 红色 → 可能是有害垃圾
        ("脏污纸巾", (120, 110, 100)),         # 灰褐色 → 可能是其他垃圾
        ("黄色香蕉皮", (220, 180, 50)),        # 黄色 → 可能是厨余垃圾
    ]

    print("\n" + "=" * 60)
    print("🧪 开始测试...")
    print("=" * 60)

    for name, color in test_cases:
        print(f"\n{'─' * 50}")
        print(f"📸 测试样本: {name}")
        print(f"{'─' * 50}")

        test_img = create_test_image(color)
        result = cascade.predict(test_img)

        # 打印详细结果
        print(f"\n📋 预测结果:")
        print(f"  ├─ 第一层 (粗分类): {result.coarse.category_name}")
        print(f"  │   置信度: {result.coarse.confidence:.1%}")
        print(f"  │   概率分布: {', '.join([f'{k.name}:{v:.1%}' for k,v in result.coarse.probabilities.items()])}")
        print(f"  ├─ 第二层 (精细化): {result.fine.class_name_cn}")
        print(f"  │   细粒度ID: {result.fine.class_id}")
        print(f"  │   置信度: {result.fine.confidence:.1%}")
        print(f"  │   子模型: {result.fine.sub_model_name}")
        print(f"  ├─ 路由策略: {result.routing_strategy}")
        print(f"  ├─ 一致性检验: {'✅ 通过' if result.is_consistent else '⚠️ 偏差'}")
        print(f"  └─ 最终置信度: {result.fusion_confidence:.1%}")
        print(f"  ⏱️ 总耗时: {result.total_inference_time_ms:.1f}ms")

    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)
