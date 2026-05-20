"""
直接测试模型推理过程
用于定位具体的错误原因
"""

import numpy as np
from PIL import Image
import onnxruntime as ort

def test_model_inference():
    """直接测试模型推理"""
    print("正在加载 ONNX 模型...")
    model_path = "models/waste_classifier.onnx"

    try:
        session = ort.InferenceSession(model_path)
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name

        print(f"✅ 模型加载成功")
        print(f"输入名称: {input_name}")
        print(f"输出名称: {output_name}")

        # 打印输入输出信息
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]

        print(f"\n输入形状: {input_info.shape}")
        print(f"输入类型: {input_info.type}")
        print(f"输出形状: {output_info.shape}")
        print(f"输出类型: {output_info.type}")

        # 创建测试图片
        print("\n正在创建测试图片...")
        img_array = np.ones((224, 224, 3), dtype=np.uint8) * 255
        img_array[50:174, 50:174] = [255, 0, 0]
        img = Image.fromarray(img_array)

        # 预处理
        print("正在进行图像预处理...")
        INPUT_SIZE = (224, 224)
        IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

        resized = img.resize(INPUT_SIZE)
        img_array_float = np.array(resized).astype(np.float32) / 255.0
        normalized = (img_array_float - IMAGENET_MEAN) / IMAGENET_STD
        chw = normalized.transpose(2, 0, 1)
        input_tensor = np.expand_dims(chw, axis=0).astype(np.float32)

        print(f"输入张量形状: {input_tensor.shape}")
        print(f"输入张量数据类型: {input_tensor.dtype}")

        # 推理
        print("\n正在进行模型推理...")
        output = session.run(
            [output_name],
            {input_name: input_tensor},
        )

        print(f"✅ 推理成功")
        print(f"输出数量: {len(output)}")
        print(f"输出[0] 类型: {type(output[0])}")
        print(f"输出[0] 形状: {output[0].shape}")
        print(f"输出[0] 数据类型: {output[0].dtype}")

        # 后处理
        print("\n正在进行后处理...")
        flat_output = output[0].flatten()
        print(f"展平后长度: {len(flat_output)}")

        shifted = flat_output - np.max(flat_output)
        exp_vals = np.exp(shifted)
        probs = exp_vals / exp_vals.sum()
        top_idx = int(np.argmax(probs))

        print(f"✅ 后处理成功")
        print(f"预测类别索引: {top_idx}")
        print(f"置信度: {probs[top_idx]:.4f}")

        return True

    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_model_inference()
