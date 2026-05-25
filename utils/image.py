"""
图像处理工具函数模块
提供 Base64 解码、图片预处理等公共方法
"""

import base64
import logging
from io import BytesIO
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def decode_base64_image(base64_str: str) -> Tuple[Image.Image, bytes]:
    """
    将 Base64 编码字符串解码为 PIL Image 和原始字节

    兼容 Data URL 格式（`data:image/jpeg;base64,...`）和纯 Base64 格式

    :param base64_str: Base64 编码的图片字符串
    :return: (PIL.Image对象, 原始图片字节)
    :raises ValueError: Base64 解码失败或图片格式无效
    :raises Exception: 其他解码异常
    """
    if "," in base64_str:
        _, encoded_data = base64_str.split(",", 1)
    else:
        encoded_data = base64_str

    image_data = base64.b64decode(encoded_data)
    image = Image.open(BytesIO(image_data)).convert("RGB")
    return image, image_data
