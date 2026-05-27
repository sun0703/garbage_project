"""
最优双层架构融合分类器，V2粗分类+主模型精细化+智能融合
"""

import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# 导入基础组件（延迟导入避免循环依赖）
def _get_base_classes():
    """获取基础类定义"""
    from app.multimodal_fusion import (
        YOLODetector, SAHIEngine, CascadeFineClassifier,
        FusionDecisionMaker, DetectionResult, MultiModalResult,
        BoundingBox, WasteCategory, ModelType,
        YOLO_40CLASS_MAP, FINE_CLASSES, CATEGORY_MAP
    )
    return {
        'YOLODetector': YOLODetector,
        'SAHIEngine': SAHIEngine,
        'CascadeFineClassifier': CascadeFineClassifier,
        'FusionDecisionMaker': FusionDecisionMaker,
        'DetectionResult': DetectionResult,
        'MultiModalResult': MultiModalResult,
        'BoundingBox': BoundingBox,
        'WasteCategory': WasteCategory,
        'ModelType': ModelType,
        'YOLO_40CLASS_MAP': YOLO_40CLASS_MAP,
        'FINE_CLASSES': FINE_CLASSES,
        'CATEGORY_MAP': CATEGORY_MAP,
    }


class OptimalDualLayerFusion:
    """
    最优双层架构融合分类器 v2.0

    架构设计：
    ┌─────────────────────────────────────────────────────────────┐
    │  Layer 1 (粗分类)              Layer 2 (精细化)               │
    │  ┌──────────────┐             ┌──────────────┐              │
    │  │ best v2.pt   │   路由      │ garbage_      │              │
    │  │ (12类→4大类) │────────────▶│ yolov8m_      │              │
    │  │ 78% mAP      │  候选ID列表 │ best.pt       │              │
    │  │ 高置信度     │             │ (40类完整)    │              │
    │  └──────┬───────┘             └──────┬───────┘              │
    │         │                           │                      │
    │         ▼                           ▼                      │
    │  ┌──────────────────────────────────────────┐                │
    │  │         Smart Fusion Engine v2.0        │                │
    │  │  • V2→40类映射 (CategoryMapper)          │                │
    │  │  • 置信度加权 (0.45 + 0.55)              │                │
    │  │  • 一致性交叉验证                       │                │
    │  │  • 冲突解决策略                         │                │
    │  └──────────────────┬───────────────────────┘                │
    │                     ▼                                        │
    │           Final Prediction (40类 + 4大类标签)                 │
    └─────────────────────────────────────────────────────────────┘
    """

    # V2模型的12类别 → 4大类的映射表
    V2_TO_4CATEGORY = {
        0: ("Hazardous", "有害垃圾"),      # battery → 有害
        1: ("Kitchen", "厨余垃圾"),        # biological → 厨余
        2: ("Recyclable", "可回收物"),      # brown-glass → 可回收(玻璃)
        3: ("Recyclable", "可回收物"),      # cardboard → 可回收(纸类)
        4: ("Recyclable", "可回收物"),      # clothes → 可回收(织物)
        5: ("Recyclable", "可回收物"),      # green-glass → 可回收(玻璃)
        6: ("Recyclable", "可回收物"),      # metal → 可回收(金属)
        7: ("Recyclable", "可回收物"),      # paper → 可回收(纸张)
        8: ("Recyclable", "可回收物"),      # plastic → 可回收(塑料)
        9: ("Recyclable", "可回收物"),      # shoes → 可回收(皮革)
        10: ("Other", "其他垃圾"),          # trash → 其他垃圾
        11: ("Recyclable", "可回收物"),      # white-glass → 可回收(玻璃)
    }

    # V2的12类 → 40类的候选映射 (用于路由)
    V2_TO_FINE_CANDIDATES = {
        0: [37, 38],                                    # battery → 干电池/药膏
        1: [6, 7, 8, 9, 10, 11, 12, 13],            # biological → 厨余系列
        2: [27, 32, 31],                                # brown-glass → 玻璃相关
        3: [30, 20, 39],                                # cardboard → 纸类
        4: [22, 24],                                    # clothes → 织物
        5: [27, 32],                                    # green-glass → 玻璃
        6: [23, 33, 34, 21],                            # metal → 金属
        7: [39, 30],                                    # paper → 纸张
        8: [36, 16, 17, 18, 15, 14, 19, 25, 26, 35], # plastic → 塑料系列
        9: [28],                                       # shoes → 皮鞋
        10: [0, 1, 2, 3, 4, 5],                        # trash → 其他垃圾
        11: [27, 32],                                   # white-glass → 玻璃
    }

    def __init__(self,
                 v2_model_path: str,
                 main_model_path: str,
                 enable_sahi: bool = True):
        """
        初始化最优双层架构

        @param v2_model_path: best v2.pt 路径 (Layer 1 粗分类)
        @param main_model_path: garbage_yolov8m_best.pt 路径 (Layer 2 精细)
        @param enable_sahi: 是否启用SAHI作为辅助层
        """
        logger.info("🚀 初始化最优双层架构融合系统 v2.0...")

        # 导入基础类
        base = _get_base_classes()
        self.BoundingBox = base['BoundingBox']
        self.DetectionResult = base['DetectionResult']
        self.MultiModalResult = base['MultiModalResult']
        self.WasteCategory = base['WasteCategory']
        self.ModelType = base['ModelType']
        self.YOLO_40CLASS_MAP = base['YOLO_40CLASS_MAP']
        self.FINE_CLASSES = base['FINE_CLASSES']
        self.CATEGORY_MAP = base['CATEGORY_MAP']

        # Layer 1: V2高精度粗分类器
        logger.info(f"   📦 加载 Layer 1 (V2粗分类): {Path(v2_model_path).name}")
        self.v2_detector = base['YOLODetector'](
            model_path=v2_model_path,
            conf_threshold=0.25
        )
        self.v2_detector.input_size = (1280, 1280)  # V2的高分辨率
        self.v2_loaded = self.v2_detector.is_loaded

        if self.v2_loaded:
            logger.info(f"      ✅ V2模型加载成功 ({len(self.v2_detector.model.names)} 类)")
        else:
            logger.warning("      ❌ V2模型加载失败，将回退到单模型模式")

        # Layer 2: 主模型精细分类器
        logger.info(f"   📦 加载 Layer 2 (精细分类): {Path(main_model_path).name}")
        self.main_detector = base['YOLODetector'](
            model_path=main_model_path,
            conf_threshold=0.15
        )
        self.main_loaded = self.main_detector.is_loaded

        if self.main_loaded:
            logger.info(f"      ✅ 主模型加载成功 ({len(self.main_detector.model.names)} 类)")
        else:
            logger.error("      ❌ 主模型加载失败!")

        # 可选: SAHI辅助层
        self.sahi_engine = None
        if enable_sahi and self.main_loaded:
            sahi_det = base['YOLODetector'](model_path=main_model_path, conf_threshold=0.10)
            self.sahi_engine = base['SAHIEngine'](
                base_detector=sahi_det,
                slice_size=(320, 320),
                overlap_ratio=0.25,
                conf_threshold=0.05
            )
            logger.info("   🔪 SAHI切片引擎已启用")

        # 双层级联分类器 (复用主模型)
        self.cascade_classifier = base['CascadeFineClassifier'](
            yolo_detector=self.main_detector
        )

        # 融合决策器 (更新权重配置)
        self.fusion_maker = base['FusionDecisionMaker']()

        # 更新权重以反映双层架构的优势
        self.fusion_maker.MODEL_RELIABILITY = {
            self.ModelType.YOLO_DETECTOR: {"weight": 0.45, "calibration": 0.92},  # V2高精度
            self.ModelType.SAHI_SLICER: {"weight": 0.15, "calibration": 0.85},  # 辅助
            self.ModelType.CASCADE_CLASSIFIER: {"weight": 0.40, "calibration": 0.88},  # 主模型精细
        }

        logger.info("🎉 最优双层架构初始化完成!")
        logger.info(f"   模式: {'V2+Main 双层' if self.v2_loaded else '单模型'}")

    def predict(self, image: Image.Image) -> 'MultiModalResult':
        """
        执行最优双层融合推理

        流程：
        1. Layer 1 (V2): 高精度粗分类 → 4大类 + 候选40类ID
        2. Layer 2 (Main): 40类精细识别
        3. Smart Fusion: 映射 + 加权 + 验证
        """
        total_start = time.perf_counter()
        logger.info("🔍 开始最优双层融合推理...")

        results_v2 = []
        results_main = []
        results_sahi = []

        # Layer 1: V2粗分类
        if self.v2_loaded:
            logger.info("  [Layer 1/V2] 高精度粗分类中...")
            results_v2 = self._v2_coarse_classify(image)

        # Layer 2: 主模型精细分类
        if self.main_loaded:
            logger.info("  [Layer 2/Main] 精细分类中...")
            results_main = self.main_detector.detect(image, top_k=5)

        # 可选: SAHI辅助
        if self.sahi_engine:
            logger.info("  [Layer 2.5/SAHI] 切片增强...")
            results_sahi = self.sahi_engine.detect_with_slicing(image, top_k=3)

        # 双层级联补充
        logger.info("  [Layer 3/Cascade] 级联精细化...")
        cascade_results = self.cascade_classifier.classify(
            image, yolo_results=results_main, top_k=3
        )

        # 智能融合
        final_result = self._smart_fusion(
            results_v2, results_main, results_sahi, cascade_results
        )

        final_result.total_inference_time_ms = (time.perf_counter() - total_start) * 1000

        logger.info("=" * 50)
        logger.info("✅ 最优双层融合推理完成")
        logger.info("   最终: %s (%s)",
                   final_result.final_prediction.fine_class_name_cn,
                   final_result.final_prediction.category_name)
        logger.info("   置信度: %.1f%%", final_result.final_prediction.confidence * 100)
        logger.info("   总耗时: %.1fms", final_result.total_inference_time_ms)
        logger.info("=" * 50)

        return final_result

    def _v2_coarse_classify(self, image: Image.Image) -> List['DetectionResult']:
        """
        使用V2模型进行粗分类

        Returns:
            List[DetectionResult]: V2的检测结果 (已转换为统一格式)
        """
        raw_results = self.v2_detector.detect(image, top_k=3)

        converted_results = []
        for det in raw_results:
            v2_class_id = det.bbox.class_id

            # 获取4大类
            cat_4 = self.V2_TO_4CATEGORY.get(v2_class_id, ("Other", "其他垃圾"))
            category_name = cat_4[1]

            # 映射到WasteCategory枚举
            category = self._map_to_waste_category(cat_4[0])

            # 获取候选的40类ID列表
            candidate_ids = self.V2_TO_FINE_CANDIDATES.get(v2_class_id, [])

            # 创建增强的结果对象
            enhanced_det = self.DetectionResult(
                bbox=det.bbox,
                category=category,
                category_name=category_name,
                fine_class_id=det.fine_class_id,
                fine_class_name_cn=f"[V2]{det.fine_class_name_cn}",
                confidence=det.confidence,
                source_model=self.ModelType.YOLO_DETECTOR,
                features={
                    **det.features,
                    'v2_raw_class_id': v2_class_id,
                    'v2_category_4': cat_4[0],
                    'candidate_fine_ids': candidate_ids,
                    'is_coarse_classification': True,
                }
            )
            converted_results.append(enhanced_det)

        return converted_results

    def _map_to_waste_category(self, cat_str: str) -> 'WasteCategory':
        """将字符串映射到WasteCategory枚举"""
        mapping = {
            "Kitchen": self.WasteCategory.KITCHEN_WASTE,
            "Recyclable": self.WasteCategory.RECYCLABLE,
            "Other": self.WasteCategory.OTHER_TRASH,
            "Hazardous": self.WasteCategory.HAZARDOUS,
        }
        return mapping.get(cat_str, self.WasteCategory.OTHER_TRASH)

    def _smart_fusion(self,
                       results_v2: List['DetectionResult'],
                       results_main: List['DetectionResult'],
                       results_sahi: List['DetectionResult'],
                       cascade_results: List['DetectionResult']) -> 'MultiModalResult':
        """
        智能融合策略：

        1. 如果V2高置信度(≥70%) → 以V2为主，用Main验证细节
        2. 如果V2中置信度 → 加权投票，Main提供细粒度
        3. 一致性加成：两个模型预测一致时提升置信度
        """
        best_v2 = results_v2[0] if results_v2 else None
        best_main = results_main[0] if results_main else None
        best_sahi = results_sahi[0] if results_sahi else None
        best_cascade = cascade_results[0] if cascade_results else None

        # 收集投票
        category_votes = {}
        all_dets = []

        # V2投票 (权重0.45)
        if best_v2:
            calib_conf = best_v2.confidence * 0.92
            if best_v2.category not in category_votes:
                category_votes[best_v2.category] = []
            category_votes[best_v2.category].append((calib_conf, "v2", best_v2))
            all_dets.append(("v2", best_v2))

        # Main模型投票 (权重0.40)
        if best_main:
            calib_conf = best_main.confidence * 0.88
            if best_main.category not in category_votes:
                category_votes[best_main.category] = []
            category_votes[best_main.category].append((calib_conf, "main", best_main))
            all_dets.append(("main", best_main))

        # Cascade投票 (包含在main的逻辑中，这里单独记录)
        if best_cascade:
            calib_conf = best_cascade.confidence * 0.88
            if best_cascade.category not in category_votes:
                category_votes[best_cascade.category] = []
            category_votes[best_cascade.category].append((calib_conf, "cascade", best_cascade))

        # SAHI投票 (权重0.15)
        if best_sahi:
            calib_conf = best_sahi.confidence * 0.85
            if best_sahi.category not in category_votes:
                category_votes[best_sahi.category] = []
            category_votes[best_sahi.category].append((calib_conf, "sahi", best_sahi))

        if not category_votes:
            return self._create_default_result()

        # 计算加权得分
        category_scores = []
        for cat, vote_list in category_votes.items():
            weights = {"v2": 0.45, "main": 0.40, "cascade": 0.35, "sahi": 0.15}
            weighted_sum = sum(conf * weights.get(model, 0.3) for conf, model, _ in vote_list)
            best_det = max(vote_list, key=lambda x: x[0])[2]
            vote_count = len(vote_list)
            category_scores.append((cat, weighted_sum, vote_count, best_det))

        # 排序选择最佳
        category_scores.sort(key=lambda x: (x[2], x[1]), reverse=True)
        best_cat, best_score, vote_count, best_det = category_scores[0]

        # 一致性计算
        total_models = sum(1 for x in [best_v2, best_main, best_sahi, best_cascade] if x is not None)
        consistency = vote_count / total_models if total_models > 0 else 0

        # 置信度校准与一致性加成
        final_confidence = min(best_score, 1.0)
        if vote_count >= 2:
            consistency_bonus = 1.0 + (vote_count - 1) * 0.10
            final_confidence = min(final_confidence * consistency_bonus, 1.0)

        # 细粒度类别确定
        final_fine_id = best_det.fine_class_id
        final_fine_name = best_det.fine_class_name_cn

        # 如果是V2的粗分类结果，尝试从Main获取更细的类别
        if best_v2 and best_det == best_v2 and "[V2]" in final_fine_name:
            candidates = best_v2.features.get('candidate_fine_ids', [])
            if candidates and best_main:
                # 在候选列表中找Main也检测到的
                for cand_id in candidates:
                    for main_det in results_main[:3]:
                        if main_det.fine_class_id == cand_id:
                            final_fine_id = cand_id
                            final_fine_name = main_det.fine_class_name_cn
                            break
                    if "[V2]" not in final_fine_name:
                        break

        # 构建最终结果
        final_detection = self.DetectionResult(
            bbox=best_det.bbox,
            category=best_cat,
            category_name=self.CATEGORY_MAP[best_cat]["name"],
            fine_class_id=final_fine_id,
            fine_class_name_cn=final_fine_name.replace("[V2]", ""),
            confidence=final_confidence,
            source_model=self.ModelType.FEATURE_BASED,
            features={
                "vote_count": vote_count,
                "total_models": total_models,
                "consistency": consistency,
                "architecture": "optimal_dual_layer_v2",
                "v2_used": best_v2 is not None,
                "main_used": best_main is not None,
            },
        )

        result = self.MultiModalResult(
            final_prediction=final_detection,
            yolo_result=best_v2,
            sahi_result=best_sahi,
            transformer_result=best_cascade,
            fusion_details={
                "strategy": "optimal_dual_layer_v2",
                "vote_count": vote_count,
                "total_models": total_models,
                "consistency_score": consistency,
                "models_used": {
                    "v2_coarse": best_v2 is not None,
                    "main_fine": best_main is not None,
                    "sahi_aux": best_sahi is not None,
                    "cascade": best_cascade is not None,
                },
            },
            total_inference_time_ms=0.0,
            consistency_score=consistency,
        )

        return result

    def _create_default_result(self) -> 'MultiModalResult':
        """创建默认结果"""
        default_det = self.DetectionResult(
            bbox=self.BoundingBox(0, 0, 100, 100, confidence=0.3),
            category=self.WasteCategory.OTHER_TRASH,
            category_name="其他垃圾",
            fine_class_id=0,
            fine_class_name_cn="一次性快餐盒",
            confidence=0.3,
            source_model=self.ModelType.FEATURE_BASED,
        )
        return self.MultiModalResult(
            final_prediction=default_det,
            fusion_details={"strategy": "default_fallback"},
            consistency_score=0.0,
        )


# 工厂函数
def create_optimal_classifier(auto_mode: bool = True) -> Optional[OptimalDualLayerFusion]:
    """
    工厂函数：创建最优双层架构分类器

    @param auto_mode: 自动检测模型并创建
    @return: 分类器实例或None(如果模型不存在)
    """
    # 修正：optimal_dual_layer.py 在 app/ 目录，项目根目录是上一级
    project_root = Path(__file__).parent.parent

    v2_path = project_root / "models" / "best v2.pt"
    main_path = project_root / "models" / "garbage_yolov8m_best.pt"

    logger.info("🔍 检查模型文件:")
    logger.info(f"   V2模型: {v2_path} (存在: {v2_path.exists()})")
    logger.info(f"   主模型: {main_path} (存在: {main_path.exists()})")

    if not v2_path.exists():
        logger.warning("⚠️ V2模型不存在，无法启用最优双层架构")
        return None

    if not main_path.exists():
        logger.error("❌ 主模型不存在")
        return None

    try:
        classifier = OptimalDualLayerFusion(
            v2_model_path=str(v2_path),
            main_model_path=str(main_path),
            enable_sahi=True
        )
        return classifier
    except Exception as e:
        logger.error(f"❌ 创建最优分类器失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=" * 70)
    print("🧪 最优双层架构测试")
    print("=" * 70)

    classifier = create_optimal_classifier()

    if classifier:
        print("\n✅ 最优双层架构创建成功!")

        # 创建测试图像
        test_img = Image.fromarray(np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))

        print("\n🔍 执行推理测试...")
        result = classifier.predict(test_img)

        print(f"\n📋 结果:")
        print(f"   类别: {result.final_prediction.category_name}")
        print(f"   细类: {result.final_prediction.fine_class_name_cn}")
        print(f"   置信度: {result.final_prediction.confidence:.1%}")
        print(f"   一致性: {result.consistency_score:.0%}")
        print(f"   耗时: {result.total_inference_time_ms:.1f}ms")

        print(f"\n🏗️ 架构信息:")
        for model_name, used in result.fusion_details["models_used"].items():
            status = "✅" if used else "⬜"
            print(f"   {status} {model_name}")
    else:
        print("\n❌ 无法创建最优分类器（缺少模型文件）")

    print("\n" + "=" * 70)
