"""
调试分析路由模块

提供图片特征分析调试接口，返回详细的图像特征、分类结果和阈值信息。
用于开发调试阶段验证图像分析算法的准确性。
"""

import logging

import cv2
import numpy as np
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from models import PredictRequest
from utils.image import decode_base64_image
from services.image_analyzer import ImageFeatureAnalyzer
from services.garbage_utils import _get_class_info

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/debug/analyze")
async def debug_analyze_image(request: PredictRequest) -> JSONResponse:
    """调试接口：分析图片的详细特征"""

    try:
        image, image_data = decode_base64_image(request.image)

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
