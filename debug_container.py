"""
调试脚本 - 分析黑色塑料餐盒的特征值
用于找出为什么会被误判为金属
"""

import numpy as np
from PIL import Image, ImageDraw
import cv2


def create_black_plastic_container():
    """创建黑色塑料餐盒（带透明盖子）"""
    width, height = 400, 400
    img = Image.new('RGB', (width, height), color=(245, 245, 250))
    draw = ImageDraw.Draw(img)
    
    # 盒体（深灰/黑色）
    draw.rectangle([100, 150, 300, 320], fill=(45, 45, 48), outline=(30, 30, 32), width=3)
    
    # 盒体内壁（稍浅）
    draw.rectangle([110, 160, 290, 280], fill=(60, 60, 65))
    
    # 透明盖子（半透明白色）
    draw.ellipse([95, 130, 305, 200], fill=(220, 220, 225), outline=(180, 180, 185), width=2)
    
    # 盖子上的高光（模拟透明塑料反光）
    draw.arc([120, 140, 280, 190], start=200, end=340, fill=(255, 255, 255), width=3)
    
    # 盒底（稍微可见的内部）
    draw.ellipse([140, 240, 260, 310], fill=(80, 80, 85), outline=(100, 100, 105))
    
    return img


def analyze_all_features(img):
    """分析所有特征"""
    img_array = np.array(img)
    
    if img_array.shape[-1] == 4:
        img_array = img_array[:, :, :3]
    
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2HSV)
    
    # 基础特征
    brightness = float(np.mean(gray)) / 255.0
    std_dev = np.std(gray)
    super_bright_ratio = np.sum(gray > 240) / gray.size
    
    # 梯度
    gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
    mean_gradient = np.mean(gradient_magnitude)
    
    # 饱和度
    saturation = hsv[:, :, 1]
    mean_saturation = np.mean(saturation)
    
    # 透明度检测
    high_light_ratio = np.sum(gray > 220) / gray.size
    is_transparent = (std_dev > 40 or high_light_ratio > 0.15 or mean_gradient > 30)
    
    # 金属检测
    is_metallic = (
        (std_dev > 50 or super_bright_ratio > 0.03) and
        mean_gradient > 15 and
        mean_saturation < 120
    )
    
    print("=" * 70)
    print("  黑色塑料餐盒特征分析")
    print("=" * 70)
    print(f"📐 图像尺寸: {img.size}, 长宽比: {img.width/img.height:.2f}")
    print(f"\n📊 基础特征:")
    print(f"   平均亮度: {brightness:.3f} (阈值: >0.82高亮, <0.4暗)")
    print(f"   标准差: {std_dev:.1f} (金属阈值: >50)")
    print(f"   超高光比例: {super_bright_ratio:.4f} (金属阈值: >0.03)")
    print(f"   平均梯度: {mean_gradient:.1f} (金属阈值: >15, 透明阈值: >30)")
    print(f"   平均饱和度: {mean_saturation:.1f} (金属阈值: <120)")
    
    print(f"\n⚡ 检测结果:")
    print(f"   透明度检测: {is_transparent}")
    print(f"     - std_dev > 40: {std_dev > 40}")
    print(f"     - high_light > 0.15: {high_light_ratio > 0.15}")
    print(f"     - gradient > 30: {mean_gradient > 30}")
    
    print(f"\n   金属检测: {is_metallic}")
    print(f"     - std_dev > 50: {std_dev > 50}")
    print(f"     - super_bright > 0.03: {super_bright_ratio > 0.03}")
    print(f"     - gradient > 15: {mean_gradient > 15}")
    print(f"     - saturation < 120: {mean_saturation < 120}")
    
    print("\n" + "=" * 70)
    print("  问题诊断:")
    print("=" * 70)
    
    if is_metallic and is_transparent:
        print("❌ 问题：同时触发金属和透明检测！")
        print("   原因：深色物体+透明区域=高对比度")
        print("   解决方案：透明物品不应该是金属")
    
    if brightness < 0.6:
        print(f"💡 提示：亮度偏低({brightness:.2f})，可能是深色塑料")


if __name__ == '__main__':
    container_img = create_black_plastic_container()
    analyze_all_features(container_img)
