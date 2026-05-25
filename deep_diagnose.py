"""
YOLO模型深度诊断 - 直接查看原始输出
"""
from ultralytics import YOLO
import os
import json

def deep_diagnose():
    print("=" * 70)
    print("  40类YOLO模型深度诊断 - 查看原始推理输出")
    print("=" * 70)

    model_path = "models/garbage_yolov8m_best.pt"
    model = YOLO(model_path)
    print(f"\n✅ 模型加载成功: {model_path}")
    print(f"   类别数: {len(model.names)}")
    print(f"   任务类型: {model.task}")

    # 测试图片
    img_dir = "datasets/rubbish/images"
    test_imgs = []
    if os.path.exists(img_dir):
        for f in sorted(os.listdir(img_dir))[:10]:
            if f.endswith(('.jpg', '.jpeg', '.png')):
                test_imgs.append(os.path.join(img_dir, f))

    print(f"\n📷 使用数据集前10张图片进行测试")

    # ===== 核心诊断：verbose=True 查看完整原始输出 =====
    print("\n" + "=" * 70)
    print("  【核心】YOLO原始输出 (conf=0.01, 几乎不过滤)")
    print("=" * 70)

    all_detections = []

    for i, img_path in enumerate(test_imgs[:5]):
        print(f"\n--- 图片{i+1}: {os.path.basename(img_path)} ---")

        # 用极低阈值，看模型到底能输出什么
        results = model(
            img_path,
            conf=0.01,      # 极低阈值，几乎不过滤
            iou=0.45,
            imgsz=640,
            verbose=True,   # 显示详细输出
        )

        img_detections = []
        for r in results:
            boxes = r.boxes
            print(f"  原始检测框数量: {len(boxes)}")

            if len(boxes) > 0:
                # 打印所有检测结果（按置信度排序）
                confs = boxes.conf.numpy()
                cls_ids = boxes.cls.numpy().astype(int)

                # 按置信度降序排列
                sorted_idx = confs.argsort()[::-1]

                print(f"  检测详情:")
                for rank, idx in enumerate(sorted_idx):
                    c = float(confs[idx])
                    cid = int(cls_ids[idx])
                    cname = model.names[cid]
                    img_detections.append({
                        "rank": rank + 1,
                        "class_id": cid,
                        "class_name": cname,
                        "confidence": round(c, 4),
                    })
                    marker = " ★" if rank == 0 else ""
                    print(f"    #{rank+1}: {cname:45s} 置信度={c:.4f} ({c*100:.1f}%){marker}")

            else:
                print(f"  ⚠️ 完全没有检测到任何目标！")

        all_detections.append({
            "image": os.path.basename(img_path),
            "detections": img_detections,
            "total": len(img_detections),
        })

    # ===== 统计分析 =====
    print("\n" + "=" * 70)
    print("  统计分析")
    print("=" * 70)

    total_imgs = len(all_detections)
    imgs_with_detection = sum(1 for d in all_detections if d["total"] > 0)
    total_dets = sum(d["total"] for d in all_detections)

    print(f"  测试图片总数: {total_imgs}")
    print(f"  有检测结果的图片: {imgs_with_detection}/{total_imgs} ({imgs_with_detection/total_imgs*100:.0f}%)")
    print(f"  总检测框数: {total_dets}")

    if total_dets > 0:
        # 收集所有置信度
        all_confs = []
        all_classes = {}
        for d in all_detections:
            for det in d["detections"]:
                all_confs.append(det["confidence"])
                cname = det["class_name"]
                if cname not in all_classes:
                    all_classes[cname] = 0
                all_classes[cname] += 1

        print(f"\n  置信度统计:")
        print(f"    最高: {max(all_confs):.4f} ({max(all_confs)*100:.1f}%)")
        print(f"    最低: {min(all_confs):.4f} ({min(all_confs)*100:.1f}%)")
        print(f"    平均: {sum(all_confs)/len(all_confs):.4f} ({sum(all_confs)/len(all_confs)*100:.1f}%)")

        # 高于各阈值的比例
        for thresh in [0.50, 0.40, 0.30, 0.25, 0.20, 0.15, 0.10]:
            above = sum(1 for c in all_confs if c >= thresh)
            print(f"    >= {thresh:.2f}: {above}/{len(all_confs)} ({above/len(all_confs)*100:.0f}%)")

        print(f"\n  检测到的类别分布:")
        for cname, count in sorted(all_classes.items(), key=lambda x: -x[1]):
            print(f"    {cname}: {count}次")

    # ===== 结论 =====
    print("\n" + "=" * 70)
    print("  诊断结论")
    print("=" * 70)

    if total_dets == 0:
        print("""
  ❌ 严重问题：模型完全无法检测到任何目标！

  可能原因：
  1. 模型文件损坏或不匹配
  2. 模型是用不同的数据集训练的（类别定义不同）
  3. 图片预处理有问题
  4. 模型实际上是一个分类模型而非检测模型

  建议：
  - 检查模型来源是否正确
  - 尝试使用官方预训练模型 yolo8n.pt 测试
  - 重新训练或下载正确的模型文件
""")
    elif max(all_confs) < 0.20:
        print(f"""
  ⚠️ 模型能检测到目标，但置信度极低（最高仅{max(all_confs)*100:.1f}%）

  这说明：
  1. 模型对当前图片的泛化能力很弱
  2. 训练数据和测试图片差异较大
  3. 模型可能欠拟合

  当前参数建议：
  - conf 应设为 0.05-0.10（极低）
  - 即使这样也可能有较多误检
""")
    elif max(all_confs) < 0.40:
        print(f"""
  ⚠️ 模型能检测到目标，但置信度偏低（最高{max(all_confs)*100:.1f}%）

  这说明模型质量一般，需要降低阈值使用。

  推荐参数：conf=0.10~0.15
""")
    else:
        print(f"""
  ✅ 模型工作正常！最高置信度可达{max(all_confs)*100:.1f}%

  可以使用标准参数：conf=0.25~0.40
""")


if __name__ == "__main__":
    deep_diagnose()
