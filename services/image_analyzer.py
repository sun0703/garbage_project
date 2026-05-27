"""图像特征分析，OpenCV启发式垃圾分类（演示模式降级方案）"""

import cv2
import imagehash
import numpy as np
import logging
from PIL import Image
from typing import Tuple

logger = logging.getLogger(__name__)


class ImageFeatureAnalyzer:
    """基于OpenCV的图像特征分析，演示模式下没模型时用的降级方案"""

    @staticmethod
    def analyze(image: Image.Image) -> dict:
        """提取12维特征，返回特征字典"""
        img_array = np.array(image)

        if img_array.shape[-1] == 4:
            img_array = img_array[:, :, :3]

        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

        dominant_color = ImageFeatureAnalyzer._get_dominant_color_v2(img_hsv)
        brightness = ImageFeatureAnalyzer._get_brightness_v2(img_array, gray)
        transparency = ImageFeatureAnalyzer._detect_transparency_v2(img_array, gray)
        aspect_ratio = image.width / image.height if image.height > 0 else 1.0
        is_metallic = ImageFeatureAnalyzer._detect_metallic_v4(img_array, gray, brightness)

        texture_smoothness = ImageFeatureAnalyzer._analyze_texture(gray)
        edge_density = ImageFeatureAnalyzer._analyze_edge_density(gray)
        color_uniformity = ImageFeatureAnalyzer._analyze_color_uniformity(img_hsv)
        saturation_mean = ImageFeatureAnalyzer._get_saturation_mean(img_hsv)
        contour_complexity = ImageFeatureAnalyzer._analyze_contour_complexity(gray)

        return {
            "dominant_color": dominant_color,
            "brightness": brightness,
            "transparency": str(transparency),
            "aspect_ratio": aspect_ratio,
            "is_metallic": str(is_metallic),
            "texture_smoothness": texture_smoothness,
            "edge_density": edge_density,
            "color_uniformity": color_uniformity,
            "saturation_mean": saturation_mean,
            "contour_complexity": contour_complexity,
        }

    @staticmethod
    def _get_dominant_color_v2(img_hsv: np.ndarray) -> str:
        """K-means聚类找主色调，比直接取均值靠谱"""
        pixels = img_hsv[:, :, 0].reshape(-1, 1).astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

        counts = np.bincount(labels.flatten())
        dominant_hue = int(centers[np.argmax(counts)][0])

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
        """亮度计算，中心区域权重高一点，边缘干扰大"""
        global_brightness = float(np.mean(gray)) / 255.0

        h, w = gray.shape
        center_region = gray[h//4:3*h//4, w//4:3*w//4]
        center_brightness = float(np.mean(center_region)) / 255.0

        return round(0.6 * center_brightness + 0.4 * global_brightness, 4)

    @staticmethod
    def _detect_transparency_v2(img_array: np.ndarray, gray: np.ndarray) -> bool:
        """透明度检测，至少满足2个条件才判定"""
        if len(img_array.shape) != 3:
            return False

        std_dev = np.std(gray)
        super_bright_ratio = np.sum(gray > 220) / gray.size

        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        mean_gradient = np.mean(gradient_magnitude)

        # 高光连通区域数量
        _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY)
        num_labels, _ = cv2.connectedComponents(thresh)
        high_light_regions = num_labels - 1

        score = 0
        if std_dev > 45:
            score += 1
        if super_bright_ratio > 0.12:
            score += 1
        if mean_gradient > 28:
            score += 1
        if 3 <= high_light_regions <= 20:
            score += 1

        return score >= 2

    @staticmethod
    def _detect_metallic_v4(img_array: np.ndarray, gray: np.ndarray, _brightness: float) -> bool:
        """金属检测v4，加了频域和饱和度分析，比之前准一些"""
        if len(img_array.shape) != 3:
            return False

        std_dev = np.std(gray)

        # 局部对比度方差，金属表面反差大
        local_std = cv2.Laplacian(gray, cv2.CV_64F)
        local_contrast_var = np.var(local_std)

        super_bright_ratio = np.sum(gray > 240) / gray.size

        gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
        mean_gradient = np.mean(gradient_magnitude)
        max_gradient = np.max(gradient_magnitude)

        # 金属通常低饱和度
        hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1]
        mean_saturation = np.mean(saturation)
        low_saturation_ratio = np.sum(saturation < 80) / saturation.size

        # 频域能量分布，金属高频成分多
        f_transform = np.fft.fft2(gray)
        f_shift = np.fft.fftshift(f_transform)
        magnitude_spectrum = np.log(np.abs(f_shift) + 1)

        h, w = magnitude_spectrum.shape
        high_freq_region = magnitude_spectrum[h//4:3*h//4, w//4:3*w//4]
        total_energy = np.sum(magnitude_spectrum)
        high_freq_energy = np.sum(high_freq_region) if total_energy > 0 else 0
        high_freq_ratio = high_freq_energy / (total_energy + 1e-6)

        # 加权计分，总分>=4才算金属
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

        # 阈值4.0，比之前严一点，减少误判
        return (total_score >= 4.0)

    @staticmethod
    def _analyze_texture(gray: np.ndarray) -> float:
        """纹理光滑度，越接近1越光滑"""
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        smoothness = max(0, min(1, 1.0 - laplacian_var / 3000))
        return round(smoothness, 3)

    @staticmethod
    def _analyze_edge_density(gray: np.ndarray) -> float:
        """边缘密度，高密度说明轮廓复杂"""
        median = np.median(gray)
        lower = int(max(0, 0.7 * median))
        upper = int(min(255, 1.3 * median))
        edges = cv2.Canny(gray, lower, upper)
        edge_density = np.sum(edges > 0) / edges.size
        return round(edge_density, 4)

    @staticmethod
    def _analyze_color_uniformity(img_hsv: np.ndarray) -> float:
        """颜色均匀度，接近1表示颜色单一"""
        h_channel = img_hsv[:, :, 0]
        h_std = np.std(h_channel)
        uniformity = max(0, min(1, 1.0 - h_std / 90))
        return round(uniformity, 3)

    @staticmethod
    def _get_saturation_mean(img_hsv: np.ndarray) -> float:
        """平均饱和度"""
        s_channel = img_hsv[:, :, 1]
        return round(float(np.mean(s_channel)), 1)

    @staticmethod
    def _analyze_contour_complexity(gray: np.ndarray) -> float:
        """轮廓复杂度，低复杂度=规则形状"""
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
        """加权投票分类，比if-else链靠谱"""
        color = features["dominant_color"]
        brightness = float(features["brightness"])
        transparency = (features["transparency"] == "True")
        aspect_ratio = float(features["aspect_ratio"])
        is_metallic = (features["is_metallic"] == "True")

        texture_smoothness = float(features.get("texture_smoothness", 0.5))
        edge_density = float(features.get("edge_density", 0.1))
        color_uniformity = float(features.get("color_uniformity", 0.5))
        saturation_mean = float(features.get("saturation_mean", 120))
        contour_complexity = float(features.get("contour_complexity", 0.3))

        item_type = "unknown"

        is_tall = (0.25 < aspect_ratio < 0.75) or (1.33 < aspect_ratio < 4.0)
        is_square = (0.75 <= aspect_ratio <= 1.33)
        is_flat = (aspect_ratio < 0.25) or (aspect_ratio >= 4.0)

        # 每个类别累计得分，最后选最高的
        scores = {0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0}
        reasons = {0: [], 1: [], 2: [], 3: []}

        # 形状+纹理+边缘，权重最高
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
                scores[1] += 3.0
                reasons[1].append("光滑规则表面→容器/包装")
                item_type = "container_flat" if brightness < 0.8 else "container_tall"
            elif edge_density > 0.15 and texture_smoothness < 0.4:
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
            else:
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

        # 颜色分析
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

        # 纹理辅助判断
        if texture_smoothness > 0.75:
            scores[1] += 1.5
            reasons[1].append(f"光滑表面(纹理度={texture_smoothness:.2f})")
        elif texture_smoothness < 0.35:
            scores[0] += 1.2
            scores[2] += 0.8
            if edge_density > 0.12:
                scores[0] += 1.0
                reasons[0].append("粗糙高边缘密度→有机物")

        # 颜色均匀性
        if color_uniformity > 0.8:
            scores[1] += 1.0
            reasons[1].append("颜色单一均匀")
        elif color_uniformity < 0.4:
            scores[0] += 0.8
            reasons[0].append("颜色丰富多样")

        # 饱和度
        if saturation_mean < 80:
            scores[1] += 0.8
            reasons[1].append("低饱和度→无机物")
        elif saturation_mean > 160:
            scores[0] += 0.8
            reasons[0].append("高饱和度→有机物")

        # 亮度兜底
        if brightness > 0.7:
            scores[1] += 1.0
            reasons[1].append("整体偏亮")
        elif brightness < 0.35:
            scores[2] += 1.0
            reasons[2].append("整体偏暗")

        # 选得分最高的
        best_class = max(scores, key=scores.get)
        best_score = scores[best_class]
        best_reasons = "; ".join(reasons[best_class][:3])

        reasoning = f"[加权投票] 得分={best_score:.1f} | {best_reasons}"

        if best_score < 2.0:
            reasoning += " | ⚠️ 特征模糊，建议使用专用模型"

        return (best_class, reasoning, item_type)

    @staticmethod
    def calculate_confidence(features: dict, class_index: int) -> float:
        """演示模式模拟置信度，基于多维特征综合评估"""
        confidence = 0.62

        brightness = float(features["brightness"])
        transparency = (features["transparency"] == "True")
        aspect_ratio = float(features["aspect_ratio"])
        color = features["dominant_color"]

        texture_smoothness = float(features.get("texture_smoothness", 0.5))
        edge_density = float(features.get("edge_density", 0.1))
        color_uniformity = float(features.get("color_uniformity", 0.5))

        is_tall = (0.25 < aspect_ratio < 0.75) or (1.33 < aspect_ratio < 4.0)
        is_square = (0.75 <= aspect_ratio <= 1.33)
        is_flat = (aspect_ratio < 0.25) or (aspect_ratio >= 4.0)

        # 形状匹配加分，最可靠
        if is_tall or is_square or is_flat:
            confidence += 0.12
            if is_tall and texture_smoothness > 0.6:
                confidence += 0.03
            elif is_square and texture_smoothness > 0.7:
                confidence += 0.02

        # 纹理
        if texture_smoothness > 0.8:
            confidence += 0.08
        elif texture_smoothness < 0.3:
            confidence += 0.04

        # 边缘密度辅助
        if class_index == 0 and edge_density > 0.15:
            confidence += 0.05
        elif class_index == 1 and edge_density < 0.08:
            confidence += 0.05

        # 颜色均匀性
        if color_uniformity > 0.85:
            confidence += 0.04
        elif color_uniformity < 0.35:
            confidence -= 0.02

        # 亮度
        if 0.55 < brightness < 0.85:
            confidence += 0.08
        elif brightness > 0.7:
            confidence += 0.05
        elif brightness < 0.3 or brightness > 0.95:
            confidence -= 0.03

        # 颜色特征
        distinct_colors = ["red_orange", "green", "blue"]
        if color in distinct_colors:
            confidence += 0.05

        if transparency:
            confidence += 0.04

        # 按类别微调
        if class_index == 1:
            confidence += 0.04
        elif class_index == 0:
            confidence -= 0.01
        elif class_index == 3:
            confidence -= 0.02

        # 多特征一致时奖励
        feature_consistency = 0
        if (is_tall or is_square) and transparency and brightness > 0.5:
            feature_consistency += 1
        if texture_smoothness > 0.7 and color_uniformity > 0.8:
            feature_consistency += 1
        if edge_density < 0.1 and brightness > 0.7:
            feature_consistency += 1

        if feature_consistency >= 2:
            confidence += 0.06

        confidence = max(0.58, min(0.96, confidence))

        return round(confidence, 4)
