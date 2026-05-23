"""
40类YOLO模型诊断工具
用于分析模型在不同置信度阈值下的检测能力
"""
from ultralytics import YOLO
import os
import warnings

warnings.filterwarnings('ignore')


def diagnose_model():
    """诊断40类模型的检测能力"""
    print("=" * 60)
    print("  40类YOLO模型诊断工具")
    print("=" * 60)

    # 加载模型
    model_path = "models/garbage_yolov8m_best.pt"
    if not os.path.exists(model_path):
        print(f"❌ 模型文件不存在: {model_path}")
        return

    model = YOLO(model_path)
    print(f"✅ 模型加载成功，类别数: {len(model.names)}")

    # 查找测试图片
    img_dir = "datasets/rubbish/images"
    test_images = []
    if os.path.exists(img_dir):
        for f in os.listdir(img_dir)[:5]:
            if f.endswith(('.jpg', '.jpeg', '.png')):
                test_images.append(os.path.join(img_dir, f))

    if not test_images:
        print("❌ 未找到测试图片")
        return

    print(f"\n📷 测试图片: {len(test_images)} 张")
    for img in test_images:
        print(f"   - {os.path.basename(img)}")

    # 测试不同置信度阈值
    print("\n" + "=" * 60)
    print("  不同置信度阈值的检测对比")
    print("=" * 60)

    conf_thresholds = [0.50, 0.40, 0.30, 0.25, 0.20, 0.15, 0.10]

    for img_path in test_images[:1]:
        print(f"\n🖼️  图片: {os.path.basename(img_path)}")
        print("-" * 60)

        for conf in conf_thresholds:
            results = model(img_path, conf=conf, iou=0.45, verbose=False)
            detections = []

            for r in results:
                if len(r.boxes) > 0:
                    for box in r.boxes:
                        cls_id = int(box.cls.item())
                        cls_name = model.names[cls_id]
                        confidence = float(box.conf.item())
                        detections.append({
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "confidence": confidence,
                        })

            if detections:
                best = max(detections, key=lambda x: x["confidence"])
                name = best["class_name"]
                score = best["confidence"]
                count = len(detections)
                print(f"  conf={conf:.2f}: ✅ 检测到{count}个 | 最佳: {name} ({score:.1%})")
            else:
                print(f"  conf={conf:.2f}: ❌ 无检测结果")

    # 测试不同输入尺寸
    print("\n" + "=" * 60)
    print("  不同输入尺寸的检测对比 (conf=0.25)")
    print("=" * 60)

    img_sizes = [320, 416, 640, 1280]

    for img_path in test_images[:1]:
        print(f"\n🖼️  图片: {os.path.basename(img_path)}")
        for size in img_sizes:
            results = model(img_path, conf=0.25, iou=0.45, imgsz=size, verbose=False)
            detections = []

            for r in results:
                if len(r.boxes) > 0:
                    for box in r.boxes:
                        cls_id = int(box.cls.item())
                        cls_name = model.names[cls_id]
                        confidence = float(box.conf.item())
                        detections.append({
                            "class_id": cls_id,
                            "class_name": cls_name,
                            "confidence": confidence,
                        })

            if detections:
                best = max(detections, key=lambda x: x["confidence"])
                name = best["class_name"]
                score = best["confidence"]
                count = len(detections)
                print(f"  imgsz={size:4d}: ✅ 检测到{count}个 | 最佳: {name} ({score:.1%})")
            else:
                print(f"  imgsz={size:4d}: ❌ 无检测结果")

    # 结论与建议
    print("\n" + "=" * 60)
    print("  结论与建议")
    print("=" * 60)
    print("""
  可能的问题：
  1. 置信度阈值过高（当前0.40）→ 建议降低到0.15-0.25
  2. 输入尺寸不合适 → 尝试更大的尺寸（如1280）
  3. 训练数据分布偏差 → 模型对某些类别泛化能力弱
  4. 图片预处理损失 → JPEG压缩导致细节丢失

  推荐优化方案：
  - 将 conf 从 0.40 降低到 0.15-0.20
  - 将 imgsz 从 640 提升到 640-1280
  - 添加数据增强（旋转、缩放、色彩抖动）
""")


if __name__ == "__main__":
    diagnose_model()
