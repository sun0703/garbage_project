"""
测试置信度系统 - 验证完整API响应
"""

import base64
from io import BytesIO

import numpy as np
import requests
from PIL import Image


def create_test_images():
    """创建多种测试图片"""
    images = {}
    
    # 1. 正方形奶茶杯（高亮度）
    size = 800
    img = np.ones((size, size, 3), dtype=np.uint8) * 245
    
    # 绘制奶茶杯轮廓
    cup_w, cup_h = int(size*0.5), int(size*0.7)
    cup_l, cup_t = (size-cup_w)//2, (size-cup_h)//2 + 50
    img[cup_t:cup_t+cup_h, cup_l:cup_l+cup_w] = [240, 240, 240]
    
    # 杯盖（黑色）
    img[cup_t-15:cup_t+25, cup_l-10:cup_l+cup_w+10] = [35, 35, 35]
    
    # 吸管（红色）
    straw_x = cup_l + cup_w//2
    img[cup_t-45:cup_t+5, straw_x-6:straw_x+6] = [200, 40, 40]
    
    images["正方形奶茶杯"] = (Image.fromarray(img), "预期: 可回收物/塑料杯, 置信度: 85-92%")
    
    # 2. 细长饮料瓶（中等亮度）
    img2 = np.ones((400, 200, 3), dtype=np.uint8) * 230
    # 瓶身
    img2[50:350, 40:160] = [200, 220, 240]
    # 瓶盖
    img2[30:55, 35:165] = [80, 80, 80]
    images["细长饮料瓶"] = (Image.fromarray(img2), "预期: 可回收物/塑料瓶, 置信度: 88-95%")
    
    # 3. 扁平塑料袋（高亮度）
    img3 = np.ones((300, 500, 3), dtype=np.uint8) * 250
    # 袋子形状
    img3[50:250, 50:450] = [235, 235, 235]
    images["扁平塑料袋"] = (Image.fromarray(img3), "预期: 其他垃圾/塑料袋, 置信度: 82-90%")
    
    return images


def test_confidence():
    """测试不同场景的置信度"""
    print("=" * 70)
    print("  测试 v2.4 - 智能置信度系统")
    print("=" * 70)
    
    images = create_test_images()
    
    for name, (img, expected) in images.items():
        print(f"\n{'─'*70}")
        print(f"📸 测试场景: {name}")
        print(f"   图片尺寸: {img.size}, 长宽比: {img.width/img.height:.2f}")
        print(f"   {expected}")
        
        # 转换为 Base64
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=95)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        base64_image = f"data:image/jpeg;base64,{img_str}"
        
        # 发送请求
        try:
            response = requests.post(
                "http://127.0.0.1:8001/api/predict",
                json={"image": base64_image},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get("result", {})
                
                print(f"\n✅ 识别结果:")
                print(f"   类别: {result.get('category')}")
                print(f"   名称: {result.get('label_cn')}")
                print(f"   类型: {result.get('item_type')}")
                print(f"   🔥 置信度: {result.get('confidence', 0)*100:.1f}%")  # 关键指标！
                print(f"   推理: {result.get('reasoning')[:60]}...")
                
                # 验证置信度是否合理
                conf = result.get('confidence', 0)
                if conf >= 0.75:
                    print(f"   ✅ 置信度合理 ({conf*100:.1f}% ≥ 75%)")
                elif conf >= 0.60:
                    print(f"   ⚠️ 置信度偏低 ({conf*100:.1f}%)")
                else:
                    print(f"   ❌ 置信度过低 ({conf*100:.1f}%)")
                    
            else:
                print(f"❌ 错误: {response.text}")
                
        except Exception as e:
            print(f"❌ 异常: {e}")
    
    print(f"\n{'='*70}")
    print("  🎉 测试完成！")
    print("="*70)


if __name__ == "__main__":
    test_confidence()
