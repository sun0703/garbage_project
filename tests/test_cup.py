"""
测试智能匹配算法 - 模拟奶茶杯（细长形状）
"""

import base64
import sys
from io import BytesIO

import numpy as np
import requests
from PIL import Image


def create_cup_image():
    """创建一个模拟奶茶杯的测试图片（细长形状）"""
    # 创建一个竖长的白色背景（模拟奶茶杯的高宽比）
    width, height = 200, 400  # 长宽比 = 0.5（细长）
    
    # 白色背景
    img_array = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # 绘制杯身（白色/米色圆柱体效果）
    cup_left, cup_right = 40, 160
    cup_top, cup_bottom = 50, 350
    
    # 杯身渐变效果（从亮到稍暗）
    for y in range(cup_top, cup_bottom):
        shade = int(240 - (y - cup_top) * 0.1)
        img_array[y, cup_left:cup_right] = [shade, shade, shade]
    
    # 黑色杯盖
    img_array[30:55, 35:165] = [30, 30, 30]
    
    # 红色吸管
    img_array[10:45, 95:105] = [200, 50, 50]
    
    img = Image.fromarray(img_array)
    return img


def test_with_cup():
    """使用奶茶杯形状的图片测试"""
    print("=" * 60)
    print("  测试智能匹配算法 v2.0 - 奶茶杯场景")
    print("=" * 60)
    
    # 创建奶茶杯图片
    img = create_cup_image()
    print(f"\n✅ 创建测试图片：尺寸={img.size}, 长宽比={img.width/img.height:.2f}")
    
    # 转换为 Base64
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    base64_image = f"data:image/jpeg;base64,{img_str}"
    
    print(f"Base64 长度: {len(base64_image)} 字符")
    
    # 发送请求
    payload = {"image": base64_image}
    
    print("\n正在调用 /api/predict 接口...")
    try:
        response = requests.post(
            "http://127.0.0.1:8001/api/predict",
            json=payload,
            timeout=30
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n" + "=" * 60)
            print("  🎯 识别结果")
            print("=" * 60)
            
            res = result.get("result", {})
            
            print(f"\n✅ 分类成功:")
            print(f"   类别: {res.get('category')} (ID: {res.get('category_id')})")
            print(f"   物品名称: {res.get('label_cn')}")
            print(f"   置信度: {res.get('confidence')}")
            print(f"   物品类型: {res.get('item_type')}")
            print(f"   推理依据: {res.get('reasoning')}")
            
            if res.get("feature_analysis"):
                feat = res["feature_analysis"]
                print(f"\n📊 图像特征分析:")
                print(f"   主色调: {feat.get('dominant_color')}")
                print(f"   亮度: {feat.get('brightness'):.3f}")
                print(f"   透明度检测: {feat.get('transparency')}")
                print(f"   长宽比: {feat.get('aspect_ratio'):.3f}")
            
            print(f"\n📝 投放指引: {res.get('guidance')}")
            print(f"\n💡 提示: {result.get('demo_notice', '')}")
            
            # 验证是否正确识别为杯子/瓶子类
            label = res.get("label_cn", "")
            item_type = res.get("item_type", "")
            
            print("\n" + "=" * 60)
            print("  ✅ 验证结果")
            print("=" * 60)
            
            if item_type == "container_tall":
                print("   🎉 正确！识别为高形容器（杯/瓶类）")
            else:
                print(f"   ⚠️ 物品类型: {item_type}（预期: container_tall）")
            
            if any(kw in label for kw in ["杯", "瓶", "饮料"]):
                print(f"   🎉 完美！物品名称包含容器关键词: '{label}'")
            else:
                print(f"   ⚠️ 物品名称: '{label}'（未匹配到杯/瓶关键词）")
                
        else:
            print(f"\n❌ 错误响应: {response.text}")
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")


if __name__ == "__main__":
    test_with_cup()
