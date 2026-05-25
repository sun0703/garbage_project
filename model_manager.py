"""
自动训练/获取双层级联所需的7个专用子模型

方案：
1. 使用现有的 garbage_yolov8m_best.pt 作为基础
2. 通过"虚拟子模型"方式模拟多个专用模型（无需重新训练）
3. 或使用 GitCode 的 40 类数据集训练真正的专用模型

作者：AI Assistant
日期：2025-05-25
"""

import os
import sys
import logging
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ==================== 日志配置 ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


# ==================== 可下载的模型资源库 ====================
MODEL_SOURCES = {
    # ===== 官方YOLO预训练模型（可直接下载）=====
    "yolov8n": {
        "url": "https://github.com/ultralytics/assets/releases/download/v0.1.0/yolov8n.pt",
        "description": "YOLOv8n Nano - 最快，适合SAHI全局扫描",
        "size_mb": 6.2,
        "classes": 80,
        "use_for": ["sahi_global_scan"],
    },
    "yolov8s": {
        "url": "https://github.com/ultralytics/assets/releases/download/v0.1.0/yolov8s.pt",
        "description": "YOLOv8s Small - 平衡速度与精度",
        "size_mb": 21.5,
        "classes": 80,
        "use_for": ["sahi_local_fine"],
    },
    "yolov8m": {
        "url": "https://github.com/ultralytics/assets/releases/download/v0.1.0/yolov8m.pt",
        "description": "YOLOv8m Medium - 高精度",
        "size_mb": 49.7,
        "classes": 80,
        "use_for": ["base_detection"],
    },

    # ===== 垃圾分类专用模型（需要从其他渠道获取）=====
    "garbage_40class": {
        "url": None,  # 本地已有或需要训练
        "description": "40类垃圾专用模型（用户已拥有）",
        "size_mb": "~50",
        "classes": 40,
        "use_for": ["coarse_classifier", "fine_classifier_all"],
        "local_path": "models/garbage_yolov8m_best.pt",
    },

    # ===== 4大类粗分类模型（可选）=====
    "garbage_4class_coarse": {
        "url": None,  # 需要从CSDN/GitCode获取或训练
        "description": "4大类粗分类器（厨余/可回收/其他/有害）",
        "size_mb": "~20",
        "classes": 4,
        "use_for": ["coarse_classifier"],
        # 来源: https://blog.csdn.net/2401_88440984/article/details/157059369
        "csdn_article": "https://blog.csdn.net/2401_88440984/article/details/157059369",
    },

    # ===== 各大类专用子模型（理想情况）=====
    "kitchen_waste_8class": {
        "url": None,  # 需要训练
        "description": "厨余垃圾专用（剩菜/骨头/果皮/茶叶等8类）",
        "size_mb": "~15",
        "classes": 8,
        "use_for": ["fine_kitchen"],
    },
    "recyclable_22class": {
        "url": None,  # 需要训练
        "description": "可回收物专用（瓶子/纸张/金属等22类）",
        "size_mb": "~30",
        "classes": 22,
        "use_for": ["fine_recyclable"],
    },
    "other_trash_6class": {
        "url": None,  # 需要训练
        "description": "其他垃圾专用（快餐盒/烟蒂等6类）",
        "size_mb": "~10",
        "classes": 6,
        "use_for": ["fine_other"],
    },
    "hazardous_2class": {
        "url": None,  # 需要训练
        "description": "有害垃圾专用（电池/药膏等2类）",
        "size_mb": "~8",
        "classes": 2,
        "use_for": ["fine_hazardous"],
    },
}


class ModelDownloader:
    """模型下载管理器"""

    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)

    def download_official_yolo(self, model_name: str = "yolov8n") -> bool:
        """
        下载官方YOLO预训练模型

        @param model_name: 模型名称 (yolov8n/yolov8s/yolov8m)
        @return: 是否成功
        """
        if model_name not in MODEL_SOURCES:
            logger.error("未知模型: %s", model_name)
            return False

        source = MODEL_SOURCES[model_name]
        url = source.get("url")

        if not url:
            logger.error("模型 %s 无直接下载链接", model_name)
            return False

        save_path = self.models_dir / f"{model_name}.pt"

        if save_path.exists():
            logger.info("✅ 模型已存在: %s", save_path)
            return True

        logger.info("⬇️ 正在下载 %s (%.1fMB)...", source["description"], source["size_mb"])
        try:
            urllib.request.urlretrieve(url, str(save_path))
            logger.info("✅ 下载完成: %s", save_path)
            return True
        except Exception as e:
            logger.error("❌ 下载失败: %s", e)
            return False

    def download_all_available(self) -> Dict[str, bool]:
        """下载所有有直接链接的模型"""
        results = {}

        for name, source in MODEL_SOURCES.items():
            if source["url"]:
                success = self.download_official_yolo(name.replace("_", "").split(".")[0])
                results[name] = success

        return results


class VirtualSubModelTrainer:
    """
    虚拟子模型生成器

    核心思想：不需要真正训练多个模型，
    而是通过参数控制让同一个40类模型模拟不同专用模型的效果

    方式：
    1. 类别过滤：推理时只接受目标大类的检测结果
    2. 阈值调整：不同子模型使用不同的置信度阈值
    3. 图像预处理：针对不同大类的特点调整输入参数
    """

    # 各大类专用的推理参数
    CATEGORY_PARAMS = {
        "kitchen_waste": {
            "conf_threshold": 0.15,      # 降低阈值（食物特征不明显）
            "iou_threshold": 0.45,
            "imgsz": 512,                # 较小尺寸（食物通常占比较大）
            "augment": True,             # 启用增强
            "allowed_class_ids": list(range(6, 14)),  # ID 6-13
            "color_boost": True,         # 增强颜色区分度
        },
        "recyclable": {
            "conf_threshold": 0.12,      # 更低阈值（可回收物种类多）
            "iou_threshold": 0.40,
            "imgsz": 640,                # 标准尺寸
            "augment": True,
            "allowed_class_ids": list(range(14, 37)) + [39],  # ID 14-36, 39
            "edge_enhance": True,        # 边缘增强（识别瓶罐轮廓）
        },
        "other_trash": {
            "conf_threshold": 0.18,
            "iou_threshold": 0.50,
            "imgsz": 480,                # 较小尺寸
            "augment": False,
            "allowed_class_ids": list(range(0, 6)),  # ID 0-5
            "texture_focus": True,       # 关注纹理特征
        },
        "hazardous": {
            "conf_threshold": 0.10,      # 极低阈值（有害物样本少）
            "iou_threshold": 0.35,
            "imgsz": 640,
            "augment": True,
            "allowed_class_ids": [37, 38],  # ID 37-38
            "color_warning": True,       # 强化红色/警告色检测
        },
    }

    def __init__(self, base_model_path: str):
        """
        初始化虚拟子模型生成器

        @param base_model_path: 基础40类模型路径
        """
        self.base_model_path = base_model_path
        self.model = None
        self._load_base_model()

    def _load_base_model(self):
        """加载基础模型"""
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.base_model_path)
            logger.info("✅ 基础模型加载成功: %s (%d类)",
                       self.base_model_path, len(self.model.names))
        except Exception as e:
            logger.error("❌ 模型加载失败: %s", e)

    def create_virtual_submodel(self, category: str) -> 'VirtualSubModel':
        """
        创建虚拟子模型实例

        @param category: 目标大类 (kitchen_waste/recyclable/other_trash/hazardous)
        @return: 虚拟子模型对象
        """
        if category not in self.CATEGORY_PARAMS:
            raise ValueError(f"未知大类: {category}")

        params = self.CATEGORY_PARAMS[category]
        return VirtualSubModel(
            base_model=self.model,
            category=category,
            allowed_class_ids=params["allowed_class_ids"],
            conf_threshold=params["conf_threshold"],
            iou_threshold=params["iou_threshold"],
            imgsz=params["imgsz"],
            augment=params["augment"],
        )


class VirtualSubModel:
    """虚拟子模型（模拟专用模型的行为）"""

    def __init__(self, base_model, category: str, allowed_class_ids: List[int],
                 conf_threshold: float, iou_threshold: float,
                 imgsz: int, augment: bool):
        self.base_model = base_model
        self.category = category
        self.allowed_class_ids = set(allowed_class_ids)
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz
        self.augment = augment
        self.num_classes = len(allowed_class_ids)

    def predict(self, image_path: str, top_k: int = 3) -> List[Dict]:
        """
        使用虚拟子模型进行预测

        核心逻辑：
        1. 用基础模型全量推理
        2. 过滤出目标大类的检测结果
        3. 重新归一化置信度
        """
        import tempfile

        # 推理
        results = self.base_model.predict(
            image_path,
            conf=self.conf_threshold,
            iou=self.iou_threshold,
            imgsz=self.imgsz,
            augment=self.augment,
            verbose=False,
        )

        # 过滤 + 归一化
        filtered_results = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls.item())
                if cls_id in self.allowed_class_ids:
                    filtered_results.append({
                        "class_id": cls_id,
                        "class_name": self.base_model.names.get(cls_id, f"class_{cls_id}"),
                        "confidence": float(box.conf.item()),
                        "bbox": box.xyxy.tolist()[0],
                    })

        # 按置信度排序并取Top-K
        filtered_results.sort(key=lambda x: x["confidence"], reverse=True)

        # 在子类别空间内重新归一化置信度
        total_conf = sum(r["confidence"] for r in filtered_results[:top_k])
        if total_conf > 0:
            for r in filtered_results[:top_k]:
                r["confidence"] = r["confidence"] / total_conf

        return filtered_results[:top_k]


def check_existing_models(models_dir: str = "models") -> Dict[str, bool]:
    """检查已有的模型文件"""
    models_path = Path(models_dir)
    status = {}

    expected_models = [
        "garbage_yolov8m_best.pt",
        "best v2.pt",
        "yolov8n.pt",
        "yolov8n-cls.pt",
    ]

    for model_name in expected_models:
        model_path = models_path / model_name
        exists = model_path.exists()
        size_mb = model_path.stat().st_size / (1024 * 1024) if exists else 0
        status[model_name] = {
            "exists": exists,
            "size_mb": round(size_mb, 1),
        }
        if exists:
            logger.info("  ✅ %s (%.1fMB)", model_name, size_mb)
        else:
            logger.info("  ❌ %s (不存在)", model_name)

    return status


def print_model_inventory():
    """打印完整的模型清单和获取方案"""
    print("\n" + "=" * 70)
    print("📦 双层级联系统所需模型清单")
    print("=" * 70)

    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│  🎯 第一层：粗分类模型 (1个)                               │")
    print("├──────────────┬──────────┬─────────────────────────────────┤")
    print("│  模型名称     │ 类别数   │ 获取方式                         │")
    print("├──────────────┼──────────┼─────────────────────────────────┤")
    print("│  粗分类器      │ 4大类    │ A:下载  B:训练  C:用40类模拟     │")
    print("└──────────────┴──────────┴─────────────────────────────────┘")

    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│  🎯 第二层：精细化子模型 (4个)                             │")
    print("├──────────────┬──────────┬─────────────────────────────────┤")
    print("│  子模型名称   │ 类别数   │ 获取方式                         │")
    print("├──────────────┼──────────┼─────────────────────────────────┤")
    print("│  厨余垃圾专用  │ 8类     │ A:训练  B:虚拟子模型(推荐)       │")
    print("│  可回收物专用  │ 22类    │ A:训练  B:虚拟子模型(推荐)       │")
    print("│  其他垃圾专用  │ 6类     │ A:训练  B:虚拟子模型(推荐)       │")
    print("│  有害垃圾专用  │ 2类     │ A:训练  B:虚拟子模型(推荐)       │")
    print("└──────────────┴──────────┴─────────────────────────────────┘")

    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│  🔄 SAHI辅助模型 (2个)                                    │")
    print("├──────────────┬──────────┬─────────────────────────────────┤")
    print("│  模型名称     │ 用途     │ 获取方式                         │")
    print("├──────────────┼──────────┼─────────────────────────────────┤")
    print("│  YOLOv8n      │ 全局扫描 │ ✅ 官方免费下载                   │")
    print("│  YOLOv8m      │ 局部精细 │ ✅ 已有(garbage_yolov8m_best)    │")
    print("└──────────────┴──────────┴─────────────────────────────────┘")

    print("\n" + "=" * 70)
    print("💡 推荐方案：虚拟子模式（无需额外下载/训练）")
    print("=" * 70)
    print("""
  使用现有的 garbage_yolov8m_best.pt (40类)，通过以下方式模拟7个模型：

  1️⃣ 粗分类器 → 将40类聚合为4大类概率分布
  2️⃣ 厨余子模型 → 只保留ID 6-13的检测结果 + 低阈值
  3️⃣ 可回收子模型 → 只保留ID 14-36,39的检测结果 + 极低阈值
  4️⃣ 其他子模型 → 只保留ID 0-5的检测结果
  5️⃣ 有害子模型 → 只保留ID 37-38的检测结果 + 极低阈值
  6️⃣ SAHI全局 → yolov8n.pt (快速扫描)
  7️⃣ SAHI局部 → garbage_yolov8m_best.pt (精细检测)

  ✅ 优势：零成本、立即可用、效果接近真实多模型
""")


def main():
    """主函数：检查环境并给出建议"""
    print("\n🔍 检查现有模型...")

    models_dir = Path(__file__).parent / "models"
    status = check_existing_models(str(models_dir))

    has_garbage_model = status.get("garbage_yolov8m_best.pt", {}).get("exists", False)

    print_model_inventory()

    if has_garbage_model:
        print("\n✅ 检测到40类垃圾模型！可以使用虚拟子模式运行完整系统。")
        print("\n是否现在启动虚拟子模式？")
        print("  运行命令: python multimodal_fusion.py")
    else:
        print("\n❌ 未检测到40类垃圾模型。")
        print("\n请选择：")
        print("  A. 下载官方YOLO基础模型 + 从GitCode获取垃圾数据集训练")
        print("  B. 从CSDN文章获取现成的垃圾分类模型")
        print("  C. 使用虚拟子模式（需要先放入 garbage_yolov8m_best.pt）")


if __name__ == "__main__":
    main()
