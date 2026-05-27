"""视觉推理引擎，支持ONNX和PyTorch双引擎"""

import cv2
import numpy as np
import onnxruntime as ort
import logging
import time
from pathlib import Path
from PIL import Image
from app.constants import (
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


class VisionEngine:
    """图像分类推理引擎，自动检测模型格式"""

    def __init__(self, model_path: str):
        self.session = None
        self.yolo_model = None
        self.input_name: str = ""
        self.output_name: str = ""
        self.is_loaded: bool = False
        self.num_classes: int = 0
        self.is_waste_model: bool = False
        self.is_yolo_model: bool = False
        self.is_pt_model: bool = False
        self._load_model(model_path)

    def _load_model(self, model_path: str) -> None:
        """加载模型，自动检测格式"""
        model_file = Path(model_path)
        if not model_file.exists():
            logger.warning("模型文件不存在: %s，视觉推理功能不可用", model_path)
            return

        try:
            if model_file.suffix == '.pt':
                self._load_pytorch_model(model_path)
            else:
                self._load_onnx_model(model_path)

            self.is_loaded = True
            logger.info("模型加载成功: %s (格式: %s, 类别数: %d)",
                       model_path, "PyTorch" if self.is_pt_model else "ONNX",
                       self.num_classes)
        except Exception as e:
            logger.error("模型加载失败: %s", e)

    def _load_pytorch_model(self, model_path: str) -> None:
        """加载PyTorch格式的YOLOv8模型"""
        from ultralytics import YOLO

        logger.info("加载YOLOv8 PyTorch模型: %s", model_path)
        self.yolo_model = YOLO(str(model_path))
        self.is_pt_model = True
        self.is_yolo_model = True
        self.is_waste_model = True
        self.num_classes = len(self.yolo_model.names)

        logger.info("YOLOv8类别列表:")
        for idx, name in self.yolo_model.names.items():
            logger.info("   %d: %s", idx, name)

    def _load_onnx_model(self, model_path: str) -> None:
        """加载ONNX格式模型"""
        self.session = ort.InferenceSession(str(model_path))
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        output_shape = self.session.get_outputs()[0].shape

        # 根据输出shape推断模型类型，这块逻辑比较绕
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
        """推理入口，自动选引擎"""
        if not self.is_loaded:
            raise RuntimeError("模型未加载")

        if self.is_pt_model and self.yolo_model:
            return self._predict_pytorch(image)
        else:
            return self._predict_onnx(image)

    def _predict_pytorch(self, image: Image.Image) -> dict:
        """YOLOv8 PyTorch推理
        conf=0.15是因为40类模型实际输出置信度偏低(22-50%)，
        原来conf=0.40会把所有结果都过滤掉
        """
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            image.save(tmp.name, 'JPEG', quality=95)
            tmp_path = tmp.name

        try:
            results = self.yolo_model(
                tmp_path,
                conf=0.15,
                iou=0.45,
                verbose=False,
                imgsz=640,
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

                        if conf < 0.10:
                            continue

                        detections.append({
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "confidence": conf,
                            "bbox": boxes.xyxy[idx].tolist() if hasattr(boxes, 'xyxy') else None,
                            "rank": rank + 1,
                        })

            if len(detections) == 0:
                logger.warning("未检测到任何物体（可能需要降低conf阈值或检查图片质量）")
                return {
                    "class_index": -1,
                    "confidence": 0.0,
                    "original_class_id": None,
                    "original_class_name": None,
                    "is_demo_mode": True,
                    "detections": [],
                }

            best = max(detections, key=lambda x: x["confidence"])
            class_id = best["class_id"]
            confidence = best["confidence"]
            class_name = best["class_name"]

            logger.info("YOLOv8检测: %s (ID=%d, 置信度=%.1f%%, 排名=%d, 总检测数=%d)",
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
        """ONNX Runtime推理"""
        input_tensor = self._preprocess(image)
        output = self.session.run(
            [self.output_name],
            {self.input_name: input_tensor},
        )
        return self._postprocess(output[0])

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        """图像预处理，YOLO和ImageNet走不同流程"""
        if self.is_yolo_model:
            resized = image.resize(YOLO_INPUT_SIZE)
            img_array = np.array(resized).astype(np.float32) / 255.0
            chw = img_array.transpose(2, 0, 1)
            return np.expand_dims(chw, axis=0).astype(np.float32)
        else:
            resized = image.resize(INPUT_SIZE)
            img_array = np.array(resized).astype(np.float32) / 255.0
            normalized = (img_array - IMAGENET_MEAN) / IMAGENET_STD
            chw = normalized.transpose(2, 0, 1)
            return np.expand_dims(chw, axis=0).astype(np.float32)

    def _postprocess(self, output: np.ndarray) -> dict:
        """后处理分发"""
        if self.is_yolo_model and self.is_waste_model:
            return self._postprocess_yolo(output)
        else:
            return self._postprocess_classification(output)

    def _postprocess_yolo(self, output: np.ndarray) -> dict:
        """YOLOv8检测后处理，支持4类和7类模型"""
        predictions = output[0].transpose(1, 0)

        _ = predictions[:, :4]  # bbox，暂未使用
        class_logits = predictions[:, 4:]

        # sigmoid转概率
        class_probs = 1 / (1 + np.exp(-class_logits))
        class_confidences = np.max(class_probs, axis=1)

        conf_threshold = 0.25
        valid_mask = class_confidences > conf_threshold
        if not np.any(valid_mask):
            best_idx = np.argmax(class_confidences)
        else:
            valid_indices = np.where(valid_mask)[0]
            best_idx = valid_indices[np.argmax(class_confidences[valid_indices])]

        confidence = float(class_confidences[best_idx])
        class_id = int(np.argmax(class_probs[best_idx]))

        # 7类→4类映射
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

        # COCO 80类→4类映射
        if self.num_classes == 80:
            if class_id in COCO_TO_WASTE:
                mapped_category = COCO_TO_WASTE[class_id]["category"]
                original_name = COCO_TO_WASTE[class_id]["name_cn"]
                return {
                    "class_index": mapped_category,
                    "confidence": round(confidence, 4),
                    "is_demo_mode": False,
                    "original_class_id": class_id,
                    "original_class_name": original_name,
                }
            else:
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
        """普通分类模型后处理，softmax"""
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
        """ImageNet类别→垃圾类别的粗略映射，不太准但聊胜于无"""
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
