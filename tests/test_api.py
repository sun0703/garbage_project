"""
测试 /api/predict 接口的脚本
用于调试图片上传失败的问题
"""

import base64
import json
import sys
from pathlib import Path

import requests

# 创建一个简单的测试图片（224x224 红色图片）
from PIL import Image
import numpy as np

def create_test_image():
    """创建一个简单的测试图片"""
    img_array = np.ones((224, 224, 3), dtype=np.uint8) * 255  # 白色背景
    img_array[50:174, 50:174] = [255, 0, 0]  # 中间红色方块
    img = Image.fromarray(img_array)
    return img

def test_predict_api():
    """测试预测接口"""
    # 创建测试图片
    img = create_test_image()

    # 转换为 Base64
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    base64_image = f"data:image/jpeg;base64,{img_str}"

    print(f"生成的 Base64 图片长度: {len(base64_image)} 字符")

    # 构造请求数据
    payload = {"image": base64_image}

    print("\n正在调用 /api/predict 接口...")
    try:
        response = requests.post(
            "http://127.0.0.1:8001/api/predict",
            json=payload,
            timeout=30
        )

        print(f"响应状态码: {response.status_code}")
        print(f"响应内容类型: {response.headers.get('Content-Type', '未知')}")

        if response.status_code == 200:
            result = response.json()
            print("\n✅ 接口调用成功！")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"\n❌ 接口返回错误: {response.status_code}")
            try:
                error_data = response.json()
                print(json.dumps(error_data, ensure_ascii=False, indent=2))
            except:
                print(response.text)

    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 连接失败: {e}")
        print("请确认服务器是否在运行 (端口 8000)")
    except requests.exceptions.Timeout:
        print("\n❌ 请求超时")
    except Exception as e:
        print(f"\n❌ 发生异常: {e}")

if __name__ == "__main__":
    from io import BytesIO
    test_predict_api()
