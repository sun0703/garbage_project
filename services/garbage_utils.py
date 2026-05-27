"""垃圾分类工具 — 投放建议、置信度校准、类别信息"""

import logging

from app.constants import WASTE_CATEGORIES, GARBAGE_40CLASSES

logger = logging.getLogger(__name__)

_search_engine = None


def set_search_engine(engine) -> None:
    """注入搜索引擎实例"""
    global _search_engine
    _search_engine = engine


# 物品差异化投放建议，格式: {物品名: (类别id, [步骤])}
_DISPOSAL_TIPS: dict[str, tuple[int, list[str]]] = {
    "塑料瓶":  (0, ["倒空瓶内残留液体", "简单冲洗瓶身", "压扁瓶身减少体积", "投入蓝色可回收物桶"]),
    "饮料瓶":  (0, ["倒空瓶内残留液体", "简单冲洗瓶身", "压扁瓶身减少体积", "投入蓝色可回收物桶"]),
    "矿泉水瓶": (0, ["倒空瓶内残留液体", "撕掉瓶身塑料标签（如有）", "压扁瓶身", "投入蓝色可回收物桶"]),
    "易拉罐":  (0, ["倒空罐内液体", "轻轻压扁（注意边缘锋利）", "投入蓝色可回收物桶"]),
    "玻璃瓶":  (0, ["清空内容物并冲洗干净", "轻放避免破碎", "投入蓝色可回收物桶（或专用玻璃回收箱）"]),
    "报纸":    (0, ["叠整齐捆扎好", "保持干燥，避免油污污染", "投入蓝色可回收物桶"]),
    "纸箱":    (0, ["拆开压平折叠", "去除胶带和快递面单", "保持干燥无油污", "投入蓝色可回收物桶"]),
    "书本":    (0, ["去除封面硬纸板（如有）", "叠整齐后捆扎或放入回收袋", "投入蓝色可回收物桶"]),
    "旧衣服":  (0, ["清洗干净并晾干", "单独装袋（不要与其他垃圾混投）", "投入旧衣回收箱或蓝色可回收物桶"]),
    "电池":    (0, ["不可与普通垃圾混放", "投入专门的电池回收箱", "或送至电子产品回收点"]),
    "金属":    (0, ["清洁表面污渍", "大件金属需拆解为小块", "投入蓝色可回收物桶"]),
    "废电池":   (1, ["含汞/镉等重金属，切勿随意丢弃", "用绝缘胶带包住正负极防止短路", "投入红色有害垃圾桶"]),
    "蓄电池":   (1, ["含铅酸，具有腐蚀性和毒性", "勿拆解、勿挤压", "投入红色有害垃圾桶或送至专业回收点"]),
    "灯管":     (1, ["含汞，破碎会释放有害气体", "完整包裹防碎（可用原包装）", "投入红色有害垃圾桶"]),
    "荧光灯":   (1, ["含汞蒸气，破损有健康风险", "轻拿轻放，用纸盒包裹", "投入红色有害垃圾桶"]),
    "药品":     (1, ["过期药品可能污染水源和土壤", "连同包装一起投入红色有害垃圾桶", "切勿冲入下水道"]),
    "过期药":   (1, ["化学成分可能危害环境", "保留原包装便于识别", "投入红色有害垃圾桶"]),
    "油漆":     (1, ["含挥发性有机溶剂和重金属", "密封盖紧防止泄漏", "投入红色有害垃圾桶"]),
    "杀虫剂":   (1, ["有毒化学品，远离儿童和食物", "保持原包装密封", "投入红色有害垃圾桶"]),
    "温度计":   (1, ["含水银，破碎后汞蒸气剧毒", "用盒子单独封装", "投入红色有害垃圾桶"]),
    "血压计":   (1, ["水银血压计含剧毒汞", "小心轻放防破碎", "投入红色有害垃圾桶"]),
    "指甲油":   (1, ["含有机溶剂和色素", "盖紧瓶盖防止挥发", "投入红色有害垃圾桶"]),
    "消毒液":   (1, ["强腐蚀性化学制剂", "原瓶密封存放", "投入红色有害垃圾桶"]),
    "剩菜":     (2, ["沥干水分后再投放", "去除大块骨头（属其他垃圾）", "投入绿色厨余垃圾桶"]),
    "剩饭":     (2, ["沥干水分", "投入绿色厨余垃圾桶"]),
    "果皮":     (2, ["直接投入绿色厨余垃圾桶", "大块果皮可适当切碎加速分解"]),
    "果核":     (2, ["小果核（苹果核、葡萄籽等）→ 绿色厨余垃圾桶", "大硬核（榴莲核、椰子壳等）→ 灰色其他垃圾桶"]),
    "菜叶":     (2, ["沥干水分", "投入绿色厨余垃圾桶"]),
    "蛋壳":     (2, ["可直接投入厨余垃圾桶", "无需清洗"]),
    "茶叶渣":   (2, ["沥干茶水", "投入绿色厨余垃圾桶"]),
    "咖啡渣":   (2, ["滤干水分", "可用于堆肥或投入绿色厨余垃圾桶"]),
    "骨头":     (2, ["大块禽畜骨（猪骨、牛骨）→ 灰色其他垃圾桶", "小鱼刺、鸡鸭小骨 → 绿色厨余垃圾桶"]),
    "外壳":     (2, ["虾蟹贝壳、玉米棒 → 灰色其他垃圾桶（难降解）", "瓜子花生壳 → 绿色厨余垃圾桶"]),
    "面包":     (2, ["未过期的可考虑捐赠", "过期的投入绿色厨余垃圾桶"]),
    "餐巾纸":   (3, ["使用过的纸巾已被污染无法回收", "投入灰色其他垃圾桶"]),
    "卫生纸":   (3, ["遇水溶解，无法回收利用", "投入灰色其他垃圾桶"]),
    "烟蒂":     (3, ["确保完全熄灭后再丢弃", "投入灰色其他垃圾桶"]),
    "陶瓷":     (3, ["碎陶瓷片请包裹好防划伤", "投入灰色其他垃圾桶"]),
    "一次性餐具":(3, ["清除食物残渣", "投入灰色其他垃圾桶"]),
    "塑料袋":   (3, ["清洁干净的塑料袋 → 蓝色可回收物桶", "脏污/油污的 → 灰色其他垃圾桶"]),
    "口罩":     (3, ["使用过的口罩可能携带病菌", "投入灰色其他垃圾桶", "疫情期间请按当地规定处置"]),
    "尿布":     (3, ["包好后密封再丢弃", "投入灰色其他垃圾桶"]),
    "猫砂":     (3, ["结团后装入垃圾袋密封", "投入灰色其他垃圾桶", "不可倒入马桶以免堵塞下水道"]),
    "打火机":   (3, ["确保燃气已排空", "投入灰色其他垃圾桶"]),
    "尘土":     (3, ["装袋密封防止扬尘", "投入灰色其他垃圾桶"]),
}

# 没匹配到具体物品时的兜底建议
_FALLBACK_TIPS: dict[int, list[str]] = {
    0: ["清洁干净、干燥无油污", "按材质分类整理后投放", "投入蓝色可回收物桶"],
    1: ["含有毒有害物质，请妥善包装", "投入红色有害垃圾桶", "不确定时咨询社区工作人员"],
    2: ["沥干水分后投放", "去除非有机杂质（如塑料袋、大骨头）", "投入绿色厨余垃圾桶"],
    3: ["确认不属于前三类后再投放", "投入灰色其他垃圾桶"],
}


def _get_disposal_tips(label_cn: str, class_index: int) -> list[str]:
    """按物品名匹配投放建议，匹配不到就用类别兜底"""
    if not label_cn or label_cn == "识别物品":
        return _FALLBACK_TIPS.get(class_index, ["请正确分类后投放"])
    for keyword, (_cat_id, steps) in _DISPOSAL_TIPS.items():
        if keyword in label_cn:
            return steps
    return _FALLBACK_TIPS.get(class_index, ["请正确分类后投放"])


# 40类模型的类别难度系数，根据实际识别效果调的
CLASS_DIFFICULTY_40 = {
    # 容易识别的，系数>1提升置信度
    "易拉罐": 1.08, "饮料瓶": 1.10, "塑料瓶": 1.06,
    "玻璃制品": 1.07, "金属制品": 1.09,

    # 中等
    "一次性餐具": 1.00, "纸巾": 1.00, "塑料袋": 1.00,
    "快递包装": 1.00, "旧书报纸": 1.02,

    # 不好认的，系数<1降低置信度
    "剩菜剩饭": 0.92, "果皮": 0.90, "菜叶菜根": 0.88,
    "蛋壳": 0.85, "骨头": 0.87, "过期食品": 0.89,
}


def _calibrate_confidence_40class(
    raw_confidence: float,
    class_id: int,
    num_detections: int,
    is_demo_mode: bool
) -> float:
    """40类模型置信度校准：难度系数 + 一致性奖励 + 高低置信度保护"""
    if raw_confidence <= 0:
        return 0.0

    class_name_cn = None
    if class_id in GARBAGE_40CLASSES:
        class_name_cn = GARBAGE_40CLASSES[class_id]["name_cn"]

    difficulty_factor = CLASS_DIFFICULTY_40.get(class_name_cn, 1.0)
    calibrated = raw_confidence * difficulty_factor

    # 多个检测框指向同一类，说明更可信
    if num_detections >= 2 and not is_demo_mode:
        consistency_bonus = min(0.05, num_detections * 0.01)
        calibrated += consistency_bonus

    if raw_confidence > 0.90:
        calibrated = max(calibrated, 0.88)
    elif raw_confidence < 0.30:
        calibrated *= 0.8

    calibrated = max(0.25, min(0.98, calibrated))

    return round(calibrated, 4)


def _get_class_info(
    class_index: int,
    is_demo_mode: bool = False,
    item_type: str = "unknown",
    is_metallic: bool = False,
    original_class_name: str | None = None
) -> dict:
    """拼装类别详情，包括桶颜色、投放建议等"""
    base_info = WASTE_CATEGORIES.get(class_index, WASTE_CATEGORIES[2]).copy()

    info = {
        "category": base_info["name"],
        "category_id": class_index,
        "bin_color": base_info["color"],
        "bin_icon": base_info["icon"],
        "guidance": f"请投入{base_info['bin_color']}{base_info['name']}桶",
        "label_cn": original_class_name if original_class_name else "识别物品",
        "tips": None,
    }

    use_vocab_name = (original_class_name is None or original_class_name == "")

    # 有搜索引擎词库的话，尝试智能匹配更具体的物品名
    if _search_engine and _search_engine.vocab and use_vocab_name:
        if is_demo_mode:
            sample_item = _search_engine.get_smart_item(class_index, item_type, is_metallic)
            if sample_item:
                info.update({
                    "label_cn": sample_item.get("label", "示例物品"),
                    "category": sample_item.get("category_name", info["category"]),
                    "bin_color": sample_item.get("bin_color", info["bin_color"]),
                    "bin_icon": sample_item.get("bin_icon", info["bin_icon"]),
                    "guidance": sample_item.get("guidance", info["guidance"]),
                    "yolo_label": sample_item.get("yolo_label", ""),
                })
                logger.info("智能匹配示例: 类别=%d, 类型=%s, 名称=%s",
                           class_index, item_type, sample_item.get("label"))
        else:
            yolo_labels = list(set(item.get("yolo_label", "") for item in _search_engine.vocab))
            if class_index < len(yolo_labels) and yolo_labels[class_index]:
                matched = _search_engine.get_by_yolo_label(yolo_labels[class_index])
                if matched:
                    info.update({
                        "label_cn": matched.get("label", ""),
                        "category": matched.get("category_name", info["category"]),
                        "bin_color": matched.get("bin_color", info["bin_color"]),
                        "bin_icon": matched.get("bin_icon", info["bin_icon"]),
                        "guidance": matched.get("guidance", info["guidance"]),
                        "yolo_label": matched.get("yolo_label", ""),
                    })

    info["tips"] = _get_disposal_tips(info.get("label_cn", ""), class_index)

    return info
