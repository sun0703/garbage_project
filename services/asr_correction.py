"""
语音识别 ASR 纠错模块
从 main.py 提取为独立模块，包含：
- 常见 ASR 错误纠正映射表
- 垃圾分类同义词扩展
- correct_asr_text 纠错函数
- predict_voice 语音预测函数
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fuzzywuzzy import process as fuzz_process

logger = logging.getLogger(__name__)

# ==================== 搜索引擎引用（由主模块注入） ====================
_search_engine = None


def set_search_engine(engine) -> None:
    """
    注入搜索引擎实例，供 correct_asr_text 的模糊匹配使用

    @param engine: SearchEngine 实例（需具备 vocab 和 vocab_labels 属性）
    """
    global _search_engine
    _search_engine = engine


# ==================== ASR错误纠正映射表 ====================

# 常见 ASR（自动语音识别）错误纠正映射表
# 针对 Web Speech API 中文语音识别的常见误识别进行纠正
ASR_CORRECTION_MAP = {
    # ===== 同音字/近音字纠正 =====
    "拉及": "垃圾",
    "拉极": "垃圾",
    "垃极": "垃圾",
    "拉圾": "垃圾",
    "塑料并": "塑料瓶",
    "朔料瓶": "塑料瓶",
    "易拉罐": "易拉罐",
    "易拉灌": "易拉罐",
    # ===== 常见物品名称变体 =====
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
    # ===== 校园特有物品 =====
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

# 垃圾分类关键词同义词扩展（用于模糊匹配）
WASTE_SYNONYMS = {
    "塑料瓶": ["饮料瓶", "矿泉水瓶", "可乐瓶", "雪碧瓶", "水瓶", "PET瓶"],
    "玻璃瓶": ["酒瓶", "调料瓶", "玻璃杯", "镜子"],
    "金属": ["易拉罐", "铝罐", "铁罐", "铜线", "金属盖", "钥匙"],
    "纸张": ["书本", "报纸", "纸板", "纸箱", "作业本", "笔记本", "宣传单"],
    "厨余": ["剩饭", "剩菜", "果皮", "菜叶", "茶叶", "蛋壳", "骨头", "鱼骨"],
    "有害": ["电池", "药品", "灯管", "油漆", "农药", "温度计", "指甲油"],
}


# ==================== ASR纠错函数 ====================

def correct_asr_text(text: str) -> str:
    """
    对 ASR 语音识别结果进行后处理纠错

    处理流程：
    1. 文本标准化（去除多余空格、统一标点）
    2. 查表纠正已知 ASR 错误模式
    3. 模糊匹配词库中的相近词条

    @param text: ASR 原始识别文本
    @return: 纠错后的文本
    """
    if not text or not text.strip():
        return text

    original = text.strip()
    corrected = original

    # 第一步：直接查表纠正（精确匹配）
    if corrected in ASR_CORRECTION_MAP:
        corrected = ASR_CORRECTION_MAP[corrected]
        logger.info("🎤 ASR纠错(精确): '%s' → '%s'", original, corrected)
        return corrected

    # 第二步：去除常见语气词和冗余字符
    for prefix in ["这是", "这个是", "请问", "我想知道", "它是一个", "它是"]:
        if corrected.startswith(prefix):
            corrected = corrected[len(prefix):].strip()

    for suffix in ["吗", "呢", "啊", "吧", "的", "是什么", "属于什么", "怎么分类"]:
        if corrected.endswith(suffix):
            corrected = corrected[:-len(suffix)].strip()

    # 第三步：再次查表（去除语气词后）
    if corrected in ASR_CORRECTION_MAP:
        logger.info("🎤 ASR纠错(去语气): '%s' → '%s'", original, corrected)
        return corrected

    # 第四步：使用 FuzzyWuzzy 模糊匹配词库
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

    # 无法纠错时返回原始文本
    if corrected != original:
        logger.info("🎤 ASR纠错(部分): '%s' → '%s'", original, corrected)

    return corrected or original


def predict_voice(raw_text: str, confidence: float = 0) -> dict:
    """
    语音识别结果纠错处理函数（替代原 FastAPI 端点 voice_correct）

    接收前端 Web Speech API 的识别结果，
    返回经过纠错和标准化的文本及可选搜索建议。

    @param raw_text: ASR原始识别文本
    @param confidence: 识别置信度（可选，默认0）
    @return: 包含纠错结果和搜索建议的字典
    """
    raw_text = raw_text.strip()

    if not raw_text:
        return {
            "success": False,
            "error": {"code": "E001", "message": "识别文本不能为空"},
        }

    # 执行纠错
    corrected = correct_asr_text(raw_text)
    is_changed = corrected != raw_text

    result = {
        "success": True,
        "original": raw_text,
        "corrected": corrected,
        "changed": is_changed,
        "confidence": confidence,
    }

    # 如果纠错成功且词库已加载，顺便返回搜索建议
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
