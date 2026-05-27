"""YOLOv8模型导出工具，pt转onnx"""

import sys
from pathlib import Path


def export_yolov8_cls_to_onnx():
    """导出YOLOv8分类模型为ONNX格式"""
    from ultralytics import YOLO

    base_dir = Path(__file__).parent.parent
    models_dir = base_dir / "models"
    output_path = models_dir / "waste_classifier.onnx"

    models_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  YOLOv8n-cls → ONNX 导出工具")
    print("=" * 50)

    print("\n[步骤1] 加载YOLOv8n-cls预训练模型...")
    try:
        model = YOLO("yolov8n-cls.pt")
        print("  ✅ 预训练模型加载成功")
    except Exception as e:
        print(f"  ❌ 预训练模型加载失败: {e}")
        print("  提示: 首次运行会自动从网络下载模型(约6MB)")
        return False

    # 如果有自己微调过的模型，取消下面注释
    # custom_model_path = "runs/classify/train/weights/best.pt"
    # if Path(custom_model_path).exists():
    #     model = YOLO(custom_model_path)
    #     print(f"  ✅ 自定义模型加载成功: {custom_model_path}")

    print("\n[步骤2] 导出ONNX格式...")
    try:
        result = model.export(
            format="onnx",
            imgsz=224,
            simplify=True,
            opset=12,
            dynamic=False,
            half=False,
        )
        print(f"  ✅ ONNX导出成功: {result}")

        exported_file = Path(result)
        if exported_file.exists() and str(exported_file) != str(output_path):
            import shutil

            shutil.move(str(exported_file), str(output_path))
            print(f"  ✅ 模型已复制到: {output_path}")
    except Exception as e:
        print(f"  ❌ ONNX导出失败: {e}")
        return False

    print("\n[步骤3] 验证ONNX模型...")
    try:
        import onnxruntime as ort

        session = ort.InferenceSession(str(output_path))
        inputs = session.get_inputs()
        outputs = session.get_outputs()
        print("  ✅ 模型验证通过")
        print(f"     输入: {inputs[0].name} {inputs[0].shape} {inputs[0].type}")
        print(f"     输出: {outputs[0].name} {outputs[0].shape} {outputs[0].type}")
        print(f"     文件大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    except Exception as e:
        print(f"  ⚠️ 验证跳过(需要安装onnxruntime): {e}")

    print("\n" + "=" * 50)
    print("  🎉 导出完成！现在可以启动服务了:")
    print("     uvicorn main:app --host 0.0.0.0 --port 8000 --reload")
    print("=" * 50)

    return True


if __name__ == "__main__":
    success = export_yolov8_cls_to_onnx()
    sys.exit(0 if success else 1)
