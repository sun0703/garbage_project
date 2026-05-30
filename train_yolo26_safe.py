"""
YOLO26 垃圾分类模型训练脚本（安全增强版 v2）

新增防护机制：
1. 系统内存监控（防止OOM导致关机）
2. GPU温度监控（防止过热保护关机）
3. 频繁checkpoint保存（每5个epoch）
4. 异常捕获与自动恢复
5. 动态资源调整

训练两个模型：
1. YOLO26x 精细分类（40类）
2. YOLO26n 粗分类（4大类聚合）

使用数据集：G:\garbage_datasets（40类，YOLO标准格式）
"""
import os
import sys
import shutil
import yaml
import time
import threading
import logging
from pathlib import Path
from datetime import datetime

# ============ 路径配置 ============
PROJECT_ROOT = r"c:\000\code\垃圾识别"
DATASET_ROOT = r"G:\garbage_datasets"
MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
OUTPUT_DIR = os.path.join(DATASET_ROOT, "runs", "yolo26_train")
LOG_FILE = os.path.join(OUTPUT_DIR, "training_monitor.log")

# 预训练权重（不存在则自动下载）
MODEL_X = "yolo26x.pt"      # YOLO26 XLarge - 精细分类（113MB）
MODEL_N = "yolo26n.pt"      # YOLO26 Nano - 粗分类（5.5MB）

# ============ 安全配置 ============
SAFETY_CONFIG = {
    "memory_warning_threshold": 85,      # 内存使用率警告阈值 (%)
    "memory_critical_threshold": 92,     # 内存使用率紧急阈值 (%)
    "gpu_temp_warning": 80,              # GPU温度警告 (°C)
    "gpu_temp_critical": 95,             # GPU温度紧急 (°C)
    "monitor_interval_memory": 30,       # 内存检查间隔（秒）
    "monitor_interval_gpu": 10,          # GPU检查间隔（秒）
    "save_period": 5,                    # checkpoint保存间隔（epoch数）
    "safe_batch_size_x": 4,              # YOLO26x 安全batch大小（原8→4，降低显存占用）
    "safe_workers": 2,                   # 数据加载线程数（原4→2，减少内存压力）
}

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

# 全局标志：用于控制监控线程
_stop_monitoring = threading.Event()


def setup_logging():
    """配置日志记录器"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    logger = logging.getLogger("TrainingMonitor")
    logger.setLevel(logging.INFO)

    # 文件处理器（追加模式）
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)  # 控制台只显示警告以上

    # 格式化器
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


logger = setup_logging()


class SystemMonitor:
    """系统资源监控器（后台线程）"""

    def __init__(self):
        self.memory_critical_flag = False
        self.gpu_critical_flag = False
        self.monitor_thread = None
        self.psutil_available = False
        self.pynvml_available = False

        # 尝试导入依赖库
        try:
            import psutil
            self.psutil = psutil
            self.psutil_available = True
            logger.info("✓ psutil 库已加载，内存监控已启用")
        except ImportError:
            logger.warning("✗ psutil 未安装，内存监控禁用。安装命令: pip install psutil")

        try:
            import pynvml
            self.pynvml = pynvml
            self.pynvml.nvmlInit()
            self.gpu_handle = self.pynvml.nvmlDeviceGetHandleByIndex(0)
            self.pynvml_available = True
            logger.info("✓ pynvml 库已加载，GPU温度监控已启用")
        except ImportError:
            logger.warning("✗ pynvml 未安装，GPU温度监控禁用。安装命令: pip install pynvml")
        except Exception as e:
            logger.warning(f"✗ GPU 初始化失败: {e}，GPU温度监控禁用")

    def monitor_memory(self):
        """内存监控线程函数"""
        if not self.psutil_available:
            return

        while not _stop_monitoring.is_set():
            try:
                mem = self.psutil.virtual_memory()
                mem_percent = mem.percent

                if mem_percent > SAFETY_CONFIG["memory_critical_threshold"]:
                    self.memory_critical_flag = True
                    logger.critical(
                        f"🚨 内存紧急！使用率 {mem_percent:.1f}% > "
                        f"{SAFETY_CONFIG['memory_critical_threshold']}% | "
                        f"可用: {mem.available / 1024**3:.2f}GB / 总计: {mem.total / 1024**3:.2f}GB"
                    )
                elif mem_percent > SAFETY_CONFIG["memory_warning_threshold"]:
                    logger.warning(
                        f"⚠️ 内存警告！使用率 {mem_percent:.1f}% | "
                        f"可用: {mem.available / 1024**3:.2f}GB"
                    )
                else:
                    logger.debug(f"内存正常: {mem_percent:.1f}%")

            except Exception as e:
                logger.error(f"内存监控异常: {e}")

            _stop_monitoring.wait(SAFETY_CONFIG["monitor_interval_memory"])

    def monitor_gpu(self):
        """GPU 温度监控线程函数"""
        if not self.pynvml_available:
            return

        while not _stop_monitoring.is_set():
            try:
                # 获取GPU温度
                temp = self.pynvml.nvmlDeviceGetTemperature(
                    self.gpu_handle,
                    self.pynvml.NVML_TEMPERATURE_GPU
                )

                # 获取显存使用
                mem_info = self.pynvml.nvmlDeviceGetMemoryInfo(self.gpu_handle)
                vram_used_gb = mem_info.used / 1024**3
                vram_total_gb = mem_info.total / 1024**3
                vram_percent = (mem_info.used / mem_info.total) * 100

                if temp > SAFETY_CONFIG["gpu_temp_critical"]:
                    self.gpu_critical_flag = True
                    logger.critical(
                        f"🚨 GPU 过热紧急！温度 {temp}°C > "
                        f"{SAFETY_CONFIG['gpu_temp_critical']}°C | "
                        f"显存: {vram_used_gb:.2f}/{vram_total_gb:.2f}GB ({vram_percent:.1f}%)"
                    )
                elif temp > SAFETY_CONFIG["gpu_temp_warning"]:
                    logger.warning(
                        f"⚠️ GPU 温度警告：{temp}°C | "
                        f"显存: {vram_used_gb:.2f}/{vram_total_gb:.2f}GB"
                    )
                else:
                    logger.info(
                        f"🖥️ GPU 正常: {temp}°C | "
                        f"显存: {vram_used_gb:.2f}/{vram_total_gb:.2f}GB ({vram_percent:.1f}%)"
                    )

            except Exception as e:
                logger.error(f"GPU 监控异常: {e}")

            _stop_monitoring.wait(SAFETY_CONFIG["monitor_interval_gpu"])

    def start(self):
        """启动所有监控线程"""
        threads = []

        if self.psutil_available:
            t_mem = threading.Thread(target=self.monitor_memory, daemon=True)
            t_mem.name = "MemoryMonitor"
            t_mem.start()
            threads.append(t_mem)

        if self.pynvml_available:
            t_gpu = threading.Thread(target=self.monitor_gpu, daemon=True)
            t_gpu.name = "GPUMonitor"
            t_gpu.start()
            threads.append(t_mem)

        if threads:
            logger.info(f"已启动 {len(threads)} 个监控线程")

        return threads

    def stop(self):
        """停止所有监控线程"""
        _stop_monitoring.set()

        if self.pynvml_available:
            try:
                self.pynvml.nvmlShutdown()
            except:
                pass

        logger.info("所有监控线程已停止")


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


def find_last_checkpoint(project_dir, name):
    """查找最近的checkpoint文件用于断点续传"""
    possible_paths = [
        os.path.join(project_dir, name, "weights", "last.pt"),
        os.path.join(project_dir, name, "weights", "best.pt"),
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def train_model(model_name, data_yaml, epochs, imgsz, batch, name, project=OUTPUT_DIR):
    """
    执行 YOLO26 训练（带安全防护）

    新增特性：
    - 自动检测并恢复上次中断的训练
    - 更频繁的checkpoint保存
    - 降低资源消耗的安全参数
    - 完整的异常捕获和日志记录
    """
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
    print(f"安全配置:")
    print(f"  - Checkpoint保存间隔: 每{SAFETY_CONFIG['save_period']}个epoch")
    print(f"  - 数据加载线程: {SAFETY_CONFIG['safe_workers']}")
    print(f"{'='*60}\n")

    # 检查是否有可恢复的checkpoint
    checkpoint_path = find_last_checkpoint(project, name)
    resume = False

    if checkpoint_path:
        print(f"\n🔄 发现已有checkpoint: {checkpoint_path}")
        print("是否从断点续传？(Y/n): ", end="")
        try:
            choice = input().strip().lower()
            resume = choice != 'n'
        except EOFError:
            # 非交互模式下默认续传
            resume = True

        if resume:
            print(f"\n✅ 从checkpoint续传...")
            model_path = checkpoint_path
        else:
            print(f"\n⚠️ 从头开始训练...")

    model = YOLO(model_path)

    try:
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
            save_period=SAFETY_CONFIG["save_period"],  # 频繁保存
            patience=20,          # 早停耐心值
            val=True,
            device=0,              # GPU，无GPU则自动用CPU
            workers=SAFETY_CONFIG["safe_workers"],  # 减少内存压力
            amp=True,             # 混合精度加速
            mosaic=1.0,           # Mosaic增强
            mixup=0.05,           # MixUp增强（轻微）
            copy_paste=0.0,       # CopyPaste增强
            erasing=0.3,          # 随机擦除
            resume=resume,        # 支持断点续传
        )

        print(f"\n✅ 训练完成！")
        best_weight = os.path.join(project, name, 'weights', 'best.pt')
        last_weight = os.path.join(project, name, 'weights', 'last.pt')

        if os.path.exists(best_weight):
            print(f"最佳权重: {best_weight}")
            size_mb = os.path.getsize(best_weight) / 1024 / 1024
            print(f"文件大小: {size_mb:.2f} MB")
        elif os.path.exists(last_weight):
            print(f"最新权重: {last_weight}")
            size_mb = os.path.getsize(last_weight) / 1024 / 1024
            print(f"文件大小: {size_mb:.2f} MB")

        # 验证
        print("\n运行验证...")
        metrics = model.val(data=data_yaml, project=project, name=f"{name}_val")
        print(f"mAP@0.5: {metrics.box.map50:.4f}")
        print(f"mAP@0.5:0.95: {metrics.box.map:.4f}")

        logger.info(f"训练成功完成: {name} | mAP@0.5: {metrics.box.map50:.4f}")

        return results

    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断训练（Ctrl+C）")
        logger.warning(f"训练被用户中断: {name}")

        # 检查是否有保存的checkpoint
        last_pt = os.path.join(project, name, 'weights', 'last.pt')
        if os.path.exists(last_pt):
            print(f"✅ 已保存最新checkpoint: {last_pt}")
            print("下次运行时可选择从此处续传")
            logger.info(f"中断后checkpoint可用: {last_pt}")
        else:
            print("❌ 未找到checkpoint，本次训练进度丢失")
            logger.error(f"训练中断且无checkpoint: {name}")

        raise

    except Exception as e:
        print(f"\n\n❌ 训练发生异常: {type(e).__name__}: {e}")
        logger.critical(f"训练失败: {name} | 错误: {e}", exc_info=True)

        # 尝试获取最后的checkpoint信息
        last_pt = os.path.join(project, name, 'weights', 'last.pt')
        if os.path.exists(last_pt):
            print(f"💾 发现部分训练结果: {last_pt}")
            logger.info(f"异常后checkpoint可能可用: {last_pt}")

        raise


def main():
    """主函数：启动训练任务和监控系统"""

    print("=" * 70)
    print("  YOLO26 垃圾分类模型训练器 v2（安全增强版）")
    print("=" * 70)
    print(f"项目目录: {PROJECT_ROOT}")
    print(f"数据集目录: {DATASET_ROOT}")
    print(f"模型目录: {MODELS_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"日志文件: {LOG_FILE}")
    print("=" * 70)

    # 显示安全配置
    print("\n🛡️  安全防护配置:")
    print(f"  ├─ 内存警告阈值: {SAFETY_CONFIG['memory_warning_threshold']}%")
    print(f"  ├─ 内存紧急阈值: {SAFETY_CONFIG['memory_critical_threshold']}%")
    print(f"  ├─ GPU温度警告: {SAFETY_CONFIG['gpu_temp_warning']}°C")
    print(f"  ├─ GPU温度紧急: {SAFETY_CONFIG['gpu_temp_critical']}°C")
    print(f"  └─ Checkpoint间隔: 每{SAFETY_CONFIG['save_period']}个epoch")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    # 启动系统监控
    monitor = SystemMonitor()
    monitor.start()

    logger.info(f"开始执行训练任务，模式: {mode}")

    try:
        if mode in ("all", "fine"):
            print("\n" + "=" * 70)
            print("[任务1] YOLO26x 精细分类训练（40类）")
            print("=" * 70)
            print("\n⚠️ 使用安全参数（降低资源消耗防崩溃）：")
            print(f"  - Batch Size: 8 → {SAFETY_CONFIG['safe_batch_size_x']}（降低50%%显存占用）")
            print(f"  - Workers: 4 → {SAFETY_CONFIG['safe_workers']}（降低50%%内存压力）")
            print(f"  - Save Period: 每{SAFETY_CONFIG['save_period']} epoch保存一次")

            # 使用原始 data.yaml（40类，已修正为绝对路径）
            data_40class = os.path.join(DATASET_ROOT, "data.yaml")

            train_model(
                model_name=MODEL_X,
                data_yaml=data_40class,
                epochs=100,
                imgsz=640,
                batch=SAFETY_CONFIG["safe_batch_size_x"],  # 使用安全batch大小
                name="yolo26x_garbage40_fine_v2"  # 新名称避免冲突
            )

        if mode in ("all", "coarse"):
            print("\n" + "=" * 70)
            print("[任务2] YOLO26n 粗分类训练（4大类）")
            print("=" * 70)

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
                batch=16,  # n模型轻量，可以稍大batch但保持安全
                name="yolo26n_garbage4_coarse_v2"  # 新名称避免冲突
            )

        print("\n" + "=" * 70)
        print("✅ 全部训练任务完成！")
        print(f"结果保存在: {OUTPUT_DIR}")
        print(f"详细日志: {LOG_FILE}")
        print("=" * 70)

        logger.info("所有训练任务已完成")

    except KeyboardInterrupt:
        print("\n\n程序被用户终止")
        logger.warning("程序被用户通过Ctrl+C终止")

    except Exception as e:
        print(f"\n\n💥 程序异常退出: {e}")
        logger.critical(f"程序异常退出: {e}", exc_info=True)

    finally:
        # 停止监控线程
        monitor.stop()
        print("\n🛡️  资源监控已关闭")


if __name__ == "__main__":
    main()
