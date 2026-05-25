"""
图像特征分析器 v4.0 增强版
基于OpenCV的多维度图像特征提取与启发式垃圾分类
"""

import cv2
import imagehash
import numpy as np
import logging
from PIL import Image
from typing import Tuple

logger = logging.getLogger(__name__)


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
    def _get_brightness_v2(_img_array: np.ndarray, gray: np.ndarray) -> float:
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
    def _detect_metallic_v4(img_array: np.ndarray, gray: np.ndarray, _brightness: float) -> bool:
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
