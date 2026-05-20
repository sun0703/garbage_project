"""
调试脚本 - 查看图像特征值
用于调优金属检测算法
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import cv2


def create_metal_can_image():
    """创建易拉罐图像"""
    width, height = 400, 400
    img = Image.new('RGB', (width, height), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    
    can_positions = [
        (80, 80, 80, 240),
        (160, 100, 80, 220),
        (240, 90, 80, 235),
    ]
    
    for x, y, w, h in can_positions:
        draw.rectangle([x, y, x+w, y+h], fill=(192, 192, 192))
        
        for i in range(w):
            center_dist = abs(i - w/2) / (w/2)
            brightness = int(255 * (1 - center_dist * 0.7))
            
            if center_dist < 0.3:
                brightness = min(255, brightness + 40)
            elif center_dist > 0.7:
                brightness = max(100, brightness - 50)
            
            color = (brightness, brightness, brightness)
            draw.line([x+i, y, x+i, y+h], fill=color)
        
        for _ in range(5):
            rx = x + np.random.randint(10, w-10)
            ry = y + np.random.randint(20, h-20)
            r_size = np.random.randint(3, 8)
            draw.ellipse([rx-r_size, ry-r_size, rx+r_size, ry+r_size], 
                        fill=(255, 255, 255))
    
    draw.rectangle([85, 120, 155, 180], fill=(255, 182, 193))
    draw.rectangle([165, 140, 235, 200], fill=(50, 50, 50))
    draw.rectangle([245, 130, 315, 190], fill=(245, 245, 220))
    
    img_array = np.array(img)
    img_pil = Image.fromarray(img_array)
    img_pil = img_pil.filter(ImageFilter.GaussianBlur(radius=1))
    
    return img_pil


def analyze_features(img):
    """分析图像特征"""
    img_array = np.array(img)
    
    if img_array.shape[-1] == 4:
        img_array = img_array[:, :, :3]
    
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    
    # 亮度
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    brightness = float(np.mean(gray)) / 255.0
    
    # 标准差
    std_dev = np.std(gray)
    
    # 超高光像素比例
    super_bright_ratio = np.sum(gray > 240) / gray.size
    
    # 梯度
    gradient_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    gradient_magnitude = np.sqrt(gradient_x**2 + gradient_y**2)
    mean_gradient = np.mean(gradient_magnitude)
    
    # 饱和度
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    mean_saturation = np.mean(saturation)
    
    print(f"图像尺寸: {img.size}")
    print(f"长宽比: {img.width/img.height:.2f}")
    print(f"平均亮度: {brightness:.3f} (阈值: >0.82为高亮)")
    print(f"标准差: {std_dev:.1f} (阈值: >50)")
    print(f"超高光比例: {super_bright_ratio:.4f} (阈值: >0.03)")
    print(f"平均梯度: {mean_gradient:.1f} (阈值: >30)")
    print(f"平均饱和度: {mean_saturation:.1f} (阈值: <120)")
    
    # 判断是否金属
    is_metallic = (
        (std_dev > 50 or super_bright_ratio > 0.03) and
        mean_gradient > 30 and
        mean_saturation < 120
    )
    print(f"\n金属检测结果: {is_metallic}")
    print(f"  std_dev > 50: {std_dev > 50}")
    print(f"  super_bright > 0.03: {super_bright_ratio > 0.03}")
    print(f"  gradient > 30: {mean_gradient > 30}")
    print(f"  saturation < 120: {mean_saturation < 120}")


if __name__ == '__main__':
    print("=" * 60)
    print("  特征分析 - 易拉罐图像")
    print("=" * 60)
    can_img = create_metal_can_image()
    analyze_features(can_img)
    
    print("\n" + "=" * 60)
