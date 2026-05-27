"""图像处理工具，Base64解码等"""

import base64
import logging
from io import BytesIO
from typing import Tuple

from PIL import Image

logger = logging.getLogger(__name__)


def decode_base64_image(base64_str: str) -> Tuple[Image.Image, bytes]:
    """Base64解码为PIL Image和原始字节，兼容Data URL格式"""
    if "," in base64_str:
        _, encoded_data = base64_str.split(",", 1)
    else:
        encoded_data = base64_str

    image_data = base64.b64decode(encoded_data)
    image = Image.open(BytesIO(image_data)).convert("RGB")
    return image, image_data
