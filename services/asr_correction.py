"""ASR语音识别纠错，处理Web Speech API的常见误识别"""

import json
import logging
from pathlib import Path
from typing import Optional

from fuzzywuzzy import process as fuzz_process

logger = logging.getLogger(__name__)

# 搜索引擎实例，由主模块注入
_search_engine = None


def set_search_engine(engine) -> None:
    """注入搜索引擎，给 correct_asr_text 的模糊匹配用"""
    global _search_engine
    _search_engine = engine


# ASR常见误识别纠正表，主要针对Web Speech API中文语音
ASR_CORRECTION_MAP = {
    # 同音字/近音字
    "拉及": "垃圾",
    "拉极": "垃圾",
    "垃极": "垃圾",
    "拉圾": "垃圾",
    "塑料并": "塑料瓶",
    "朔料瓶": "塑料瓶",
    "易拉罐": "易拉罐",
    "易拉灌": "易拉罐",
    # 物品名称变体
    "奶茶杯": "奶茶杯",
    "茶奶杯": "奶茶杯",
    "可乐瓶": "可乐瓶",
    "可了瓶": "可乐瓶",
    "矿泉水瓶": "矿泉水瓶",
    "矿泉水并": "矿泉水瓶",
    "快递盒": "快递盒",
    "快递纸箱": "快递纸箱",
    "外卖盒": "外卖餐盒",
    "外卖盒子": "外卖餐盒",
    "电池": "废电池",
    "干电池": "干电池",
    "充电电池": "充电电池",
    "纽扣电池": "纽扣电池",
    "灯管": "荧光灯管",
    "日光灯": "荧光灯管",
    "药品": "过期药品",
    "过期药": "过期药品",
    "温度计": "水银温度计",
    "体温计": "水银温度计",
    # 校园常见物品
    "剩饭": "剩菜剩饭",
    "剩菜": "剩菜剩饭",
    "果皮": "果皮果核",
    "果核": "果皮果核",
    "茶叶": "茶叶渣",
    "茶叶渣": "茶叶渣",
    "蛋壳": "蛋壳",
    "骨头": "大骨头",
    "大骨头": "大骨头",
    "卫生纸": "用过的卫生纸",
    "纸巾": "用过的卫生纸",
    "湿纸巾": "湿纸巾",
    "烟头": "烟蒂",
    "烟蒂": "烟蒂",
    "牙签": "牙签",
    "一次性筷子": "竹筷",
    "筷子": "竹筷",
}

# 同义词扩展，辅助模糊匹配
WASTE_SYNONYMS = {
    "塑料瓶": ["饮料瓶", "矿泉水瓶", "可乐瓶", "雪碧瓶", "水瓶", "PET瓶"],
    "玻璃瓶": ["酒瓶", "调料瓶", "玻璃杯", "镜子"],
    "金属": ["易拉罐", "铝罐", "铁罐", "铜线", "金属盖", "钥匙"],
    "纸张": ["书本", "报纸", "纸板", "纸箱", "作业本", "笔记本", "宣传单"],
    "厨余": ["剩饭", "剩菜", "果皮", "菜叶", "茶叶", "蛋壳", "骨头", "鱼骨"],
    "有害": ["电池", "药品", "灯管", "油漆", "农药", "温度计", "指甲油"],
}


def correct_asr_text(text: str) -> str:
    """ASR纠错：查表 → 去语气词 → 模糊匹配"""
    if not text or not text.strip():
        return text

    original = text.strip()
    corrected = original

    # 先精确查表
    if corrected in ASR_CORRECTION_MAP:
        corrected = ASR_CORRECTION_MAP[corrected]
        logger.info("🎤 ASR纠错(精确): '%s' → '%s'", original, corrected)
        return corrected

    # 去掉常见语气词和冗余前缀，用户说话习惯千奇百怪
    for prefix in ["这是", "这个是", "请问", "我想知道", "它是一个", "它是"]:
        if corrected.startswith(prefix):
            corrected = corrected[len(prefix):].strip()

    for suffix in ["吗", "呢", "啊", "吧", "的", "是什么", "属于什么", "怎么分类"]:
        if corrected.endswith(suffix):
            corrected = corrected[:-len(suffix)].strip()

    # 去完语气词再查一次
    if corrected in ASR_CORRECTION_MAP:
        logger.info("🎤 ASR纠错(去语气): '%s' → '%s'", original, corrected)
        return corrected

    # 最后走模糊匹配，阈值75分起步
    if _search_engine and _search_engine.vocab:
        result = fuzz_process.extractOne(
            corrected,
            _search_engine.vocab_labels,
            score_cutoff=75
        )
        if result:
            best_match, score = result
            if best_match and score >= 80:
                logger.info("🎤 ASR纠错(模糊): '%s' → '%s' (相似度=%d%%)", original, best_match, score)
                return best_match

    # 实在纠不了就返回原始文本
    if corrected != original:
        logger.info("🎤 ASR纠错(部分): '%s' → '%s'", original, corrected)

    return corrected or original


def predict_voice(raw_text: str, confidence: float = 0) -> dict:
    """语音纠错入口，返回纠错结果和搜索建议"""
    raw_text = raw_text.strip()

    if not raw_text:
        return {
            "success": False,
            "error": {"code": "E001", "message": "识别文本不能为空"},
        }

    corrected = correct_asr_text(raw_text)
    is_changed = corrected != raw_text

    result = {
        "success": True,
        "original": raw_text,
        "corrected": corrected,
        "changed": is_changed,
        "confidence": confidence,
    }

    # 纠错成功的话顺便返回搜索建议，省得前端再请求一次
    if is_changed and _search_engine:
        try:
            search_results = _search_engine.search(corrected, limit=5)
            if search_results:
                result["search_results"] = [
                    {"label": r.get("label"), "category": r.get("category_name"),
                     "guidance": r.get("guidance")}
                    for r in search_results[:3]
                ]
        except Exception as e:
            logger.warning("语音纠错后搜索失败: %s", e)

    logger.info("🎤 语音纠错请求: 原始='%s', 纠错='%s', 变更=%s", raw_text, corrected, is_changed)
    return result
