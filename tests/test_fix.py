"""
测试 v2.5 - 验证塑料盒识别修复
模拟用户真实场景：透明塑料盒 vs 奶茶杯 vs 苹果核
"""

import base64
from io import BytesIO

import numpy as np
import requests
from PIL import Image, ImageDraw


def create_transparent_container():
    """创建透明塑料盒（模拟用户的 500ML 餐盒）"""
    size = 800
    
    # 灰色背景（类似产品展示图）
    img_array = np.ones((size, size, 3), dtype=np.uint8) * 180
    
    # 绘制透明塑料盒（半透明白色，有高光）
    box_w, box_h = int(size * 0.7), int(size * 0.45)
    box_l, box_t = (size - box_w) // 2, (size - box_h) // 2
    
    # 盒身（半透明白色）
    for y in range(box_t, box_t + box_h):
        for x in range(box_l, box_l + box_w):
            # 边缘稍微暗一点（3D效果）
            edge_x = min(x - box_l, box_l + box_w - x) / (box_w / 2)
            edge_y = min(y - box_t, box_t + box_h - y) / (box_h / 2)
            edge_factor = max(edge_x, edge_y)
            
            base = 230 - int(edge_factor * 40)
            
            # 添加高光效果（左上角更亮）
            highlight = 1.0
            if x < box_l + box_w * 0.4 and y < box_t + box_h * 0.4:
                highlight = 1.15
            
            val = min(255, int(base * highlight))
            img_array[y, x] = [val, val, val]
    
    # 盒盖边缘（稍深的线条）
    img_array[box_t+5:box_t+8, box_l:box_l+box_w] = [150, 150, 150]
    
    return Image.fromarray(img_array)


def create_milk_tea_cup():
    """创建奶茶杯（高亮度白色）"""
    size = 800
    img_array = np.ones((size, size, 3), dtype=np.uint8) * 250  # 很亮的背景
    
    # 杯身
    cup_w, cup_h = int(size * 0.45), int(size * 0.7)
    cup_l, cup_t = (size - cup_w) // 2, (size - cup_h) // 2 + 30
    
    img_array[cup_t:cup_t+cup_h, cup_l:cup_l+cup_w] = [245, 245, 245]
    
    # 黑色杯盖
    img_array[cup_t-10:cup_t+30, cup_l-10:cup_l+cup_w+10] = [35, 35, 35]
    
    # 红色吸管
    straw_x = cup_l + cup_w // 2
    img_array[cup_t-50:cup_t+5, straw_x-6:straw_x+6] = [200, 40, 40]
    
    return Image.fromarray(img_array)


def create_apple_core():
    """创建苹果核（中等亮度、不透明、褐色）"""
    size = 400
    img_array = np.full((size, size, 3), [139, 90, 43], dtype=np.uint8)  # 褐色背景
    
    # 绘制苹果核形状（不规则椭圆形）
    center_x, center_y = size // 2, size // 2
    
    for y in range(size):
        for x in range(size):
            dist = ((x - center_x) ** 2 + (y - center_y) ** 2) ** 0.5
            if dist < size * 0.35:
                # 核心部分（深褐色）
                shade = int(100 + dist * 0.3)
                img_array[y, x] = [shade, int(shade*0.65), int(shade*0.25)]
    
    return Image.fromarray(img_array)


def test_all_scenarios():
    """测试所有场景"""
    print("=" * 70)
    print("  测试 v2.5 - 透明度优先算法")
    print("  目标：解决塑料盒被识别成苹果核的问题")
    print("=" * 70)
    
    scenarios = [
        ("透明塑料盒", create_transparent_container(), "可回收物/餐盒", True),
        ("奶茶杯", create_milk_tea_cup(), "可回收物/塑料杯", False),
        ("苹果核", create_apple_core(), "厨余垃圾/苹果核", False),
    ]
    
    for name, img, expected, is_transparent in scenarios:
        print(f"\n{'─'*70}")
        print(f"📸 测试: {name}")
        print(f"   尺寸: {img.size}, 长宽比: {img.width/img.height:.2f}")
        print(f"   预期: {expected}")
        
        # 转换为 Base64
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        base64_image = f"data:image/jpeg;base64,{img_str}"
        
        try:
            response = requests.post(
                "http://127.0.0.1:8001/api/predict",
                json={"image": base64_image},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get("result", {})
                
                category = result.get('category', '')
                label = result.get('label_cn', '')
                confidence = result.get('confidence', 0) * 100
                item_type = result.get('item_type', '')
                reasoning = result.get('reasoning', '')[:70]
                feat = result.get('feature_analysis', {})
                
                print(f"\n✅ 结果:")
                print(f"   类别: {category}")
                print(f"   名称: {label}")
                print(f"   类型: {item_type}")
                print(f"   置信度: {confidence:.1f}%")
                print(f"   推理: {reasoning}...")
                
                if feat:
                    print(f"   特征: 透明={feat.get('transparency')}, 亮度={float(feat.get('brightness',0)):.3f}")
                
                # 验证关键点
                print(f"\n🔍 验证:")
                
                if name == "透明塑料盒":
                    if category == "可回收物" and "餐盒" in label or "盒" in label:
                        print(f"   🎉 完美！塑料盒正确识别为可回收物/{label}")
                    elif category == "可回收物":
                        print(f"   ✅ 分类正确（可回收物），但名称: {label}（希望包含'盒'）")
                    else:
                        print(f"   ❌ 错误！应该是可回收物，实际是: {category}/{label}")
                        
                elif name == "奶茶杯":
                    if "杯" in label or "瓶" in label:
                        print(f"   ✅ 正确识别为容器类: {label}")
                    else:
                        print(f"   ⚠️ 名称: {label}（希望是杯子/瓶子）")
                        
                elif name == "苹果核":
                    if category == "厨余垃圾":
                        print(f"   ✅ 正确识别为厨余垃圾: {label}")
                    else:
                        print(f"   ❌ 错误！应该是厨余垃圾，实际是: {category}")
                        
            else:
                print(f"❌ API错误: {response.text}")
                
        except Exception as e:
            print(f"❌ 异常: {e}")
    
    print(f"\n{'='*70}")
    print("  🎉 测试完成！请用真实图片再次验证")
    print("="*70)


if __name__ == "__main__":
    test_all_scenarios()
