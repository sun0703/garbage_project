"""
测试易拉罐识别 - 验证金属检测算法
目标：确保易拉罐不再被误识别为餐盒
"""

import base64
import io
import requests
from PIL import Image, ImageDraw, ImageFilter
import numpy as np


def create_metal_can_image():
    """
    创建一个模拟易拉罐的图像（带金属光泽）
    特征：
    1. 圆柱形外观（多个竖条）
    2. 高对比度（明暗交替）
    3. 金属反光点
    4. 低饱和度颜色（银色、灰色）
    """
    width, height = 400, 400
    img = Image.new('RGB', (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    
    # 绘制3个易拉罐形状（圆柱体）
    can_positions = [
        (80, 80, 80, 240),   # (x, y, w, h)
        (160, 100, 80, 220),
        (240, 90, 80, 235),
    ]
    
    for x, y, w, h in can_positions:
        # 罐体底色（银灰色）
        draw.rectangle([x, y, x+w, y+h], fill=(192, 192, 192))
        
        # 添加金属光泽条纹（垂直渐变）
        for i in range(w):
            # 创建高光效果（中间亮，两边暗）
            center_dist = abs(i - w/2) / (w/2)
            brightness = int(255 * (1 - center_dist * 0.7))
            
            if center_dist < 0.3:  # 中间区域很亮（高光）
                brightness = min(255, brightness + 40)
            elif center_dist > 0.7:  # 边缘较暗
                brightness = max(100, brightness - 50)
            
            color = (brightness, brightness, brightness)
            draw.line([x+i, y, x+i, y+h], fill=color)
        
        # 添加金属反光点（随机高亮点）
        for _ in range(5):
            rx = x + np.random.randint(10, w-10)
            ry = y + np.random.randint(20, h-20)
            r_size = np.random.randint(3, 8)
            draw.ellipse([rx-r_size, ry-r_size, rx+r_size, ry+r_size], 
                        fill=(255, 255, 255))
    
    # 添加一些彩色标签（模拟真实易拉罐）
    draw.rectangle([85, 120, 155, 180], fill=(255, 182, 193))  # 粉色标签
    draw.rectangle([165, 140, 235, 200], fill=(50, 50, 50))     # 黑色标签
    draw.rectangle([245, 130, 315, 190], fill=(245, 245, 220))  # 米白色标签
    
    # 转换为数组添加噪声和模糊
    img_array = np.array(img)
    
    # 添加轻微的高斯模糊（模拟照片效果）
    img_pil = Image.fromarray(img_array)
    img_pil = img_pil.filter(ImageFilter.GaussianBlur(radius=1))
    
    return img_pil


def create_normal_container_image():
    """创建普通塑料餐盒图像（模拟真实深色餐盒）"""
    width, height = 400, 400
    img = Image.new('RGB', (width, height), color=(240, 240, 245))
    draw = ImageDraw.Draw(img)
    
    # 盒体（深灰/黑色，模拟真实塑料餐盒）
    draw.rectangle([100, 130, 300, 310], fill=(50, 50, 55), outline=(35, 35, 40), width=3)
    
    # 盒体内壁（稍浅）
    draw.rectangle([110, 145, 290, 275], fill=(65, 65, 70))
    
    # 透明盖子（半透明白色，有高光边缘）
    draw.ellipse([90, 110, 310, 185], fill=(215, 215, 225), outline=(175, 175, 185), width=2)
    
    # 盖子上的文字区域（模拟印刷）
    draw.arc([130, 125, 270, 170], start=180, end=360, fill=(120, 120, 130), width=2)
    
    return img


def test_can_recognition():
    """测试易拉罐识别"""
    print("=" * 70)
    print("  测试 v2.6 - 金属/易拉罐检测算法")
    print("  目标：解决易拉罐被识别成餐盒的问题")
    print("=" * 70)
    
    scenarios = [
        ("易拉罐（金属光泽）", create_metal_can_image(), "可回收物/易拉罐", True),
        ("塑料餐盒（对比）", create_normal_container_image(), "可回收物/餐盒", False),
    ]
    
    for name, img, expected, should_be_metallic in scenarios:
        print(f"\n{'─'*70}")
        print(f"📸 测试: {name}")
        print(f"   尺寸: {img.size}, 长宽比: {img.width/img.height:.2f}")
        print(f"   预期: {expected}")
        
        # 转换为 Base64
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=95)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # 发送请求
        try:
            response = requests.post(
                'http://localhost:8001/api/predict',
                json={'image': f'data:image/jpeg;base64,{img_base64}'},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    result = data['result']
                    label = result.get('label_cn', '未知')
                    category = result.get('category', '未知')
                    confidence = result.get('confidence', 0) * 100
                    reasoning = result.get('reasoning', '')
                    item_type = result.get('item_type', 'unknown')
                    
                    # 检查是否检测到金属特征
                    features = result.get('feature_analysis', {})
                    is_metallic = features.get('is_metallic', 'False')
                    
                    print(f"   ✅ 识别结果: {label} ({category})")
                    print(f"   📊 置信度: {confidence:.1f}%")
                    print(f"   🔍 物品类型: {item_type}")
                    print(f"   ⚡ 金属检测: {is_metallic}")
                    print(f"   💡 推理: {reasoning[:80]}...")
                    
                    # 验证结果
                    expected_label = expected.split('/')[1] if '/' in expected else expected
                    is_correct = expected_label in label
                    
                    if should_be_metallic and is_metallic == 'True':
                        print("   ✅ 金属检测成功！")
                    elif should_be_metallic and is_metallic == 'False':
                        print("   ❌ 金属检测失败！")
                    
                    if is_correct:
                        print("   ✅ 识别正确！")
                    else:
                        print(f"   ❌ 识别错误！预期: {expected_label}, 实际: {label}")
                else:
                    print(f"   ❌ API返回错误: {data.get('error', {})}")
            else:
                print(f"   ❌ HTTP错误: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("   ❌ 连接失败：请确保服务已启动 (python main.py)")
        except Exception as e:
            print(f"   ❌ 测试异常: {e}")
    
    print("\n" + "=" * 70)
    print("  测试完成")
    print("=" * 70)


if __name__ == '__main__':
    test_can_recognition()
