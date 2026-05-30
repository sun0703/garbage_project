"""
YOLO26 垃圾分类模型训练脚本
训练两个模型：
1. YOLO26x 精细分类（40类）
2. YOLO26n 粗分类（4大类聚合）

使用数据集：G:\garbage_datasets（40类，YOLO标准格式）
"""
import os
import sys
import shutil
import yaml
from pathlib import Path

# ============ 路径配置 ============
PROJECT_ROOT = r"c:\000\code\垃圾识别"
DATASET_ROOT = r"G:\garbage_datasets"
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
OUTPUT_DIR = os.path.join(DATASET_ROOT, "runs", "yolo26_train")

# 预训练权重（不存在则自动下载）
MODEL_X = "yolo26x.pt"      # YOLO26 XLarge - 精细分类（113MB）
MODEL_N = "yolo26n.pt"      # YOLO26 Nano - 粗分类（5.5MB）

# 40类 → 4大类映射关系（基于 data.yaml 的 category_mapping）
CLASS_TO_CATEGORY = {
    # 可回收物 Recyclables (0)
    "Powerbank": 0, "Bag": 0, "CosmeticBottles": 0, "Toys": 0,
    "PlasticBowl": 0, "PlasticHanger": 0, "PaperBags": 0, "PlugWire": 0,
    "OldClothes": 0, "Can": 0, "Pillow": 0, "PlushToys": 0,
    "ShampooBottle": 0, "GlassCup": 0, "Shoes": 0, "Anvil": 0,
    "Cardboard": 0, "SeasoningBottle": 0, "Bottle": 0,
    "MetalFoodCans": 0, "Pot": 0, "EdibleOilBarrel": 0, "DrinkBottle": 0,
    # 厨余垃圾 KitchenWaste (1)
    "Meal": 1, "Bone": 1, "FruitPeel": 1, "Pulp": 1,
    "Tea": 1, "Vegetable": 1, "Eggshell": 1, "FishBone": 1,
    # 有害垃圾 HazardousWaste (2)
    "DryBattery": 2, "Ointment": 2, "ExpiredDrugs": 2,
    # 其他垃圾 OtherGarbage (3)
    "FastFoodBox": 3, "SoiledPlastic": 3, "Cigarette": 3,
    "Toothpick": 3, "Flowerpot": 3, "BambooChopstics": 3,
}

CATEGORY_NAMES = ["Recyclables", "KitchenWaste", "HazardousWaste", "OtherGarbage"]
CATEGORY_NAMES_CN = ["可回收物", "厨余垃圾", "有害垃圾", "其他垃圾"]


def generate_4class_yaml():
    """生成4大类粗分类的 data.yaml 配置文件"""
    yaml_path = os.path.join(DATASET_ROOT, "data_4class.yaml")

    config = {
        "path": DATASET_ROOT.replace("\\", "/"),
        "train": "datasets/images/train",
        "val": "datasets/images/val",
        "nc": 4,
        "names": CATEGORY_NAMES,
        "_category_names_cn": CATEGORY_NAMES_CN,
    }

    with open(yaml_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

    print(f"已生成4大类配置文件: {yaml_path}")
    return yaml_path


def convert_labels_to_4class():
    """将40类标签转换为4大类标签，创建新的标签目录结构"""
    src_train_labels = os.path.join(DATASET_ROOT, "datasets", "labels", "train")
    src_val_labels = os.path.join(DATASET_ROOT, "datasets", "labels", "val")

    dst_train_labels = os.path.join(DATASET_ROOT, "datasets_4class", "labels", "train")
    dst_val_labels = os.path.join(DATASET_ROOT, "datasets_4class", "labels", "val")

    # 创建目标目录
    os.makedirs(dst_train_labels, exist_ok=True)
    os.makedirs(dst_val_labels, exist_ok=True)

    # 复制图片目录（符号链接或直接引用原图）
    dst_train_imgs = os.path.join(DATASET_ROOT, "datasets_4class", "images", "train")
    dst_val_imgs = os.path.join(DATASET_ROOT, "datasets_4class", "images", "val")
    os.makedirs(dst_train_imgs, exist_ok=True)
    os.makedirs(dst_val_imgs, exist_ok=True)

    converted = 0
    for split_name, src_lbl_dir, dst_lbl_dir, src_img_dir, dst_img_dir in [
        ("train", src_train_labels, dst_train_labels,
         os.path.join(DATASET_ROOT, "datasets", "images", "train"), dst_train_imgs),
        ("val", src_val_labels, dst_val_labels,
         os.path.join(DATASET_ROOT, "datasets", "images", "val"), dst_val_imgs),
    ]:
        if not os.path.exists(src_lbl_dir):
            print(f"警告: {src_lbl_dir} 不存在，跳过")
            continue

        # 符号链接图片目录（节省空间）
        if not os.path.exists(dst_img_dir) or os.listdir(dst_img_dir) == []:
            try:
                if os.name == 'nt':
                    # Windows 用 junction
                    import subprocess
                    subprocess.run(["mklink", "/J", dst_img_dir, src_img_dir],
                                   check=True, capture_output=True)
                else:
                    os.symlink(src_img_dir, dst_img_dir)
            except Exception:
                # 如果链接失败，跳过（图片可以共用）
                pass

        label_files = [f for f in os.listdir(src_lbl_dir) if f.endswith('.txt')]
        print(f"转换 {split_name} 标签: {len(label_files)} 个文件...")

        for lf in label_files:
            src_path = os.path.join(src_lbl_dir, lf)
            dst_path = os.path.join(dst_lbl_dir, lf)

            new_lines = []
            with open(src_path, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        class_name = None
                        # 通过 class_id 查找类别名
                        for i, name in enumerate([
                            "FastFoodBox","SoiledPlastic","Cigarette","Toothpick",
                            "Flowerpot","BambooChopstics","Meal","Bone","FruitPeel",
                            "Pulp","Tea","Vegetable","Eggshell","FishBone","Powerbank",
                            "Bag","CosmeticBottles","Toys","PlasticBowl","PlasticHanger",
                            "PaperBags","PlugWire","OldClothes","Can","Pillow",
                            "PlushToys","ShampooBottle","GlassCup","Shoes","Anvil",
                            "Cardboard","SeasoningBottle","Bottle","MetalFoodCans",
                            "Pot","EdibleOilBarrel","DrinkBottle","DryBattery",
                            "Ointment","ExpiredDrugs"
                        ]):
                            if i == class_id:
                                class_name = name
                                break

                        if class_name and class_name in CLASS_TO_CATEGORY:
                            cat_id = CLASS_TO_CATEGORY[class_name]
                            parts[0] = str(cat_id)
                            new_lines.append(" ".join(parts))

            if new_lines:
                with open(dst_path, 'w', encoding='utf-8') as f:
                    f.write("\n".join(new_lines))
                converted += 1

    print(f"标签转换完成，共转换 {converted} 个标签文件")
    return os.path.join(DATASET_ROOT, "datasets_4class")


def train_model(model_name, data_yaml, epochs, imgsz, batch, name, project=OUTPUT_DIR):
    """执行 YOLO26 训练"""
    from ultralytics import YOLO

    model_path = os.path.join(MODELS_DIR, model_name)
    if not os.path.exists(model_path):
        print(f"预训练权重不存在: {model_path}")
        print("将自动从 Ultralytics Hub 下载...")
        model_path = model_name

    print(f"\n{'='*60}")
    print(f"开始训练: {name}")
    print(f"模型: {model_name}")
    print(f"数据集: {data_yaml}")
    print(f"Epochs: {epochs} | 图片大小: {imgsz} | Batch: {batch}")
    print(f"输出目录: {project}/{name}")
    print(f"{'='*60}\n")

    model = YOLO(model_path)

    results = model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        name=name,
        project=project,
        verbose=True,
        plots=True,
        save=True,
        patience=20,          # 早停耐心值
        val=True,
        device=0,              # GPU，无GPU则自动用CPU
        workers=4,
        amp=True,             # 混合精度加速
        mosaic=1.0,           # Mosaic增强
        mixup=0.05,           # MixUp增强（轻微）
        copy_paste=0.0,       # CopyPaste增强
        erasing=0.3,          # 随机擦除
    )

    print(f"\n训练完成！")
    print(f"最佳权重: {os.path.join(project, name, 'weights', 'best.pt')}")

    # 验证
    print("\n运行验证...")
    metrics = model.val(data=data_yaml, project=project, name=f"{name}_val")
    print(f"mAP@0.5: {metrics.box.map50:.4f}")
    print(f"mAP@0.5:0.95: {metrics.box.map:.4f}")

    return results


def main():
    print("=" * 60)
    print("YOLO26 垃圾分类模型训练器")
    print("=" * 60)
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"数据集目录: {DATASET_ROOT}")
    print(f"模型目录: {MODELS_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode in ("all", "fine"):
        print("\n" + "=" * 60)
        print("[任务1] YOLO26x 精细分类训练（40类）")
        print("=" * 60)

        # 使用原始 data.yaml（40类，已修正为绝对路径）
        data_40class = os.path.join(DATASET_ROOT, "data.yaml")

        train_model(
            model_name=MODEL_X,
            data_yaml=data_40class,
            epochs=100,
            imgsz=640,
            batch=8,              # x 模型较大，减小 batch
            name="yolo26x_garbage40_fine"
        )

    if mode in ("all", "coarse"):
        print("\n" + "=" * 60)
        print("[任务2] YOLO26n 粗分类训练（4大类）")
        print("=" * 60)

        # 生成4大类配置和转换标签
        data_4class = generate_4class_yaml()
        datasets_4class = convert_labels_to_4class()

        # 更新 data.yaml 的路径指向 4 类数据集
        data_4class_content = {
            "path": datasets_4class.replace("\\", "/"),
            "train": "images/train",
            "val": "images/val",
            "nc": 4,
            "names": CATEGORY_NAMES,
        }
        with open(data_4class, 'w', encoding='utf-8') as f:
            yaml.dump(data_4class_content, f, allow_unicode=True, default_flow_style=False)

        train_model(
            model_name=MODEL_N,
            data_yaml=data_4class,
            epochs=80,
            imgsz=640,
            batch=32,             # n 模型轻量，大 batch
            name="yolo26n_garbage4_coarse"
        )

    print("\n" + "=" * 60)
    print("全部训练任务完成！")
    print(f"结果保存在: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
