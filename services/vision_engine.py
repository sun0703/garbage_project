"""
视觉推理引擎
支持ONNX和PyTorch双引擎的图像分类推理
"""

import cv2
import numpy as np
import onnxruntime as ort
import logging
import time
from pathlib import Path
from PIL import Image
from constants import (
    INPUT_SIZE,
    YOLO_INPUT_SIZE,
    IMAGENET_MEAN,
    IMAGENET_STD,
    GARBAGE_40CLASSES,
    COCO_TO_WASTE,
    WASTE_CATEGORIES,
    YOLOV8_7CLASSES,
)
from services.image_analyzer import ImageFeatureAnalyzer

logger = logging.getLogger(__name__)


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
        _ = predictions[:, :4]  # [cx, cy, w, h] 暂未使用，保留用于后续目标检测扩展
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
    
    def _map_to_waste_category(self, imagenet_index: int, _confidence: float) -> int:
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
