"""
测试正方形奶茶杯图片（模拟用户真实场景）
"""

import base64
from io import BytesIO

import numpy as np
import requests
from PIL import Image


def create_square_cup_image():
    """创建一个正方形的奶茶杯图片（模拟用户真实上传的 800x800 图片）"""
    size = 800  # 正方形尺寸
    
    # 白色背景（带一些渐变效果）
    img_array = np.ones((size, size, 3), dtype=np.uint8) * 250
    
    # 绘制奶茶杯（居中，占据大部分空间）
    cup_width = int(size * 0.5)  # 杯子宽度：400px
    cup_height = int(size * 0.75)  # 杯子高度：600px
    cup_left = (size - cup_width) // 2  # 居中
    cup_top = (size - cup_height) // 2 + 30  # 稍微偏上
    
    cup_right = cup_left + cup_width
    cup_bottom = cup_top + cup_height
    
    # 绘制杯身（白色/米色，带有轻微渐变）
    for y in range(cup_top, cup_bottom):
        progress = (y - cup_top) / cup_height
        
        # 杯身颜色（从亮白到稍暗）
        base_color = 245 - int(progress * 15)
        
        # 边缘稍微暗一点（圆柱体效果）
        for x in range(cup_left, cup_right):
            edge_dist = min(x - cup_left, cup_right - x) / (cup_width / 2)
            shade = base_color - int(edge_dist * 20)
            img_array[y, x] = [max(220, shade), max(220, shade), max(220, shade)]
    
    # 绘制黑色杯盖
    lid_height = 40
    lid_top = cup_top - 10
    lid_left = cup_left - 10
    lid_right = cup_right + 10
    
    img_array[lid_top:lid_top+lid_height, lid_left:lid_right] = [35, 35, 35]
    
    # 绘制红色吸管
    straw_width = 12
    straw_left = cup_left + cup_width // 2 - straw_width // 2
    straw_top = lid_top - 50
    straw_bottom = lid_top + 5
    
    img_array[straw_top:straw_bottom, straw_left:straw_left+straw_width] = [200, 40, 40]
    
    img = Image.fromarray(img_array)
    return img


def test_square_cup():
    """测试正方形奶茶杯"""
    print("=" * 70)
    print("  测试 v2.2 算法 - 正方形奶茶杯场景（模拟真实用户上传）")
    print("=" * 70)
    
    # 创建正方形奶茶杯图片
    img = create_square_cup_image()
    print(f"\n✅ 创建测试图片：尺寸={img.size}（正方形）")
    print(f"   长宽比: {img.width/img.height:.2f}")
    
    # 转换为 Base64
    buffered = BytesIO()
    img.save(buffered, format="JPEG", quality=95)
    img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
    base64_image = f"data:image/jpeg;base64,{img_str}"
    
    print(f"   Base64 长度: {len(base64_image)} 字符")
    
    # 发送请求
    payload = {"image": base64_image}
    
    print("\n正在调用 API...")
    try:
        response = requests.post(
            "http://127.0.0.1:8001/api/predict",
            json=payload,
            timeout=30
        )
        
        print(f"响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n" + "=" * 70)
            print("  🎯 识别结果")
            print("=" * 70)
            
            res = result.get("result", {})
            
            print(f"\n✅ 分类:")
            print(f"   类别: {res.get('category')} (ID: {res.get('category_id')})")
            print(f"   物品名称: {res.get('label_cn')}")
            print(f"   物品类型: {res.get('item_type')}")
            print(f"   推理依据: {res.get('reasoning')}")
            
            if res.get("feature_analysis"):
                feat = res["feature_analysis"]
                print(f"\n📊 特征分析:")
                print(f"   主色调: {feat.get('dominant_color')}")
                print(f"   亮度: {float(feat.get('brightness', 0)):.3f}")
                print(f"   透明度: {feat.get('transparency')}")
                print(f"   长宽比: {float(feat.get('aspect_ratio', 0)):.3f}")
            
            print(f"\n📝 投放指引: {res.get('guidance')}")
            
            # 验证结果
            print("\n" + "=" * 70)
            print("  ✅ 验证")
            print("=" * 70)
            
            label = res.get("label_cn", "")
            item_type = res.get("item_type", "")
            category = res.get("category", "")
            
            success = True
            
            if category == "可回收物":
                print(f"   ✅ 分类正确: 可回收物")
            else:
                print(f"   ⚠️ 分类: {category}（预期: 可回收物）")
                success = False
            
            if "杯" in label or "瓶" in label or "饮料" in label:
                print(f"   🎉 完美！物品名称正确: '{label}'")
            else:
                print(f"   ⚠️ 物品名称: '{label}'（希望包含'杯/瓶'关键词）")
                success = False
            
            if success:
                print("\n🎉🎉🎉 全部通过！问题已解决！")
            else:
                print("\n⚠️ 还有改进空间")
                
        else:
            print(f"\n❌ 错误: {response.text}")
            
    except Exception as e:
        print(f"\n❌ 异常: {e}")


if __name__ == "__main__":
    test_square_cup()
