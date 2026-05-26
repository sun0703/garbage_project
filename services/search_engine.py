"""
模糊搜索引擎
基于FuzzyWuzzy + 拼音首字母索引的智能搜索与物品匹配
"""

import json
import logging
from pathlib import Path
from typing import Optional
from fuzzywuzzy import process as fuzz_process
from services.asr_correction import correct_asr_text

# ==================== 拼音库导入（带 fallback） ====================
try:
    from pypinyin import lazy_pinyin, Style
    _PINYIN_AVAILABLE = True
except ImportError:
    _PINYIN_AVAILABLE = False
    # fallback：当 pypinyin 不可用时，使用手动映射表
    lazy_pinyin = None  # type: ignore
    Style = None  # type: ignore

logger = logging.getLogger(__name__)


# ==================== 模糊搜索引擎 ====================
class SearchEngine:
    """
    基于FuzzyWuzzy的模糊搜索引擎（增强版：支持拼音首字母搜索）
    
    功能特性：
    - FuzzyWuzzy 模糊匹配
    - 别名索引加速
    - 拼音首字母搜索（需求 F-2.2.1）
    """

    def __init__(self, vocab_path: str):
        self.vocab: list[dict] = []
        self.vocab_labels: list[str] = []
        # 别名索引：别名 → 主标签
        self._alias_to_label: dict[str, str] = {}
        # 拼音首字母索引：拼音缩写 → [item, ...]
        self._pinyin_index: dict[str, list[dict]] = {}
        self._load_vocab(vocab_path)

    def _load_vocab(self, vocab_path: str) -> None:
        """
        加载词库并构建索引（别名索引 + 拼音首字母索引）
        
        Args:
            vocab_path: 词库 JSON 文件路径
        """
        vocab_file = Path(vocab_path)
        if not vocab_file.exists():
            logger.warning("词库文件不存在: %s", vocab_path)
            return
        try:
            with open(vocab_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.vocab = data.get("items", [])
            self.vocab_labels = [item["label"] for item in self.vocab]
            # 构建别名到主标签的映射，提升搜索覆盖率
            self._alias_to_label: dict[str, str] = {}
            for item in self.vocab:
                for alias in item.get("aliases", []):
                    if alias and alias not in self._alias_to_label:
                        self._alias_to_label[alias] = item["label"]
            # 构建拼音首字母索引（需求 F-2.2.1）
            self._build_pinyin_index()
            logger.info(
                "词库加载成功: %d 条记录, %d 个别名索引, %d 个拼音索引",
                len(self.vocab), len(self._alias_to_label), len(self._pinyin_index)
            )
        except Exception as e:
            logger.error("词库加载失败: %s", e)

    def _get_pinyin_first_letters(self, text: str) -> str:
        """
        获取中文文本的拼音首字母缩写
        
        Args:
            text: 输入文本（中文/混合）
            
        Returns:
            拼音首字母拼接字符串，如 "slp"（塑料瓶）
        """
        if not text:
            return ""
        
        # 优先使用 pypinyin 库
        if _PINYIN_AVAILABLE and lazy_pinyin is not None:
            try:
                py_list = lazy_pinyin(text, style=Style.FIRST_LETTER)
                return "".join(py_list).lower()
            except Exception:
                pass
        
        # fallback：使用手动映射表（覆盖常见垃圾分类词汇）
        return self._fallback_pinyin(text)

    @staticmethod
    def _fallback_pinyin(text: str) -> str:
        """
        pypinyin 不可用时的手动拼音映射（fallback 方案）
        
        覆盖垃圾分类领域高频词汇，保证核心功能可用性。
        
        Args:
            text: 输入文本
            
        Returns:
            拼音首字母缩写
        """
        # 常用字拼音首字母映射表（按使用频率排序）
        char_pinyin_map = {
            # 垃圾分类高频字
            "塑": "s", "料": "l", "瓶": "p", "袋": "d", "纸": "z", "箱": "x",
            "盒": "h", "罐": "g", "杯": "b", "碗": "w", "筷": "k", "勺": "sh",
            "盘": "p", "碟": "d", "巾": "j", "尿": "n", "布": "b", "鞋": "x",
            "帽": "m", "衣": "y", "裤": "k", "袜": "w", "书": "sh", "本": "b",
            "报": "b", "杂": "z", "志": "z", "电": "d", "池": "ch", "灯": "d",
            "管": "g", "药": "y", "片": "p", "烟": "y", "蒂": "d", "骨": "g",
            "头": "t", "壳": "k", "核": "h", "皮": "p", "叶": "y", "根": "g",
            "菜": "c", "饭": "f", "剩": "sh", "菜": "c", "果": "g", "渣": "zh",
            "茶": "ch", "渣": "zh", "瓷": "c", "陶": "t", "瓦": "w", "灰": "h",
            "土": "t", "尘": "ch", "玻": "b", "璃": "l", "金": "j", "属": "sh",
            "铝": "l", "铁": "t", "铜": "t", "易": "y", "拉": "l", "饮": "y",
            "矿": "k", "泉": "q", "洗": "x", "发": "f", "沐": "m", "露": "l",
            "保": "b", "温": "w", "快": "k", "递": "d", "包": "b", "装": "zh",
            "泡": "p", "沫": "m", "牛": "n", "奶": "n", "方": "f", "便": "b",
            "面": "m", "桶": "t", "苹": "p", "香": "x", "蕉": "j", "橙": "ch",
            "西": "x", "瓜": "g", "面": "m", "包": "b", "枯": "k", "枝": "zh",
            "落": "l", "杂": "z", "草": "c", "旧": "j", "玩": "w", "具": "j",
            "器": "q", "一": "y", "次": "c", "性": "x", "餐": "c", "具": "j",
            "破": "p", "碎": "s", "陶": "t", "用": "y", "过": "g", "的": "d",
            "作": "z", "业": "y", "打": "d", "印": "y", "胶": "j", "带": "d",
            "绳": "sh", "线": "x", "纽": "n", "扣": "k", "拉": "l", "链": "l",
            "牙": "y", "刷": "sh", "膏": "g", "口": "k", "红": "h", "蜡": "l",
            "笔": "b", "橡皮": "xp", "擦": "c", "宠": "ch", "物": "w", "食": "sh",
            "创": "ch", "可": "k", "贴": "t", "图": "t", "画": "h", "复": "f",
            "印": "y", "纸": "z", "受": "sh", "污": "w", "染": "r", "的": "d",
            "废": "f", "旧": "j", "家": "j", "具": "j", "电": "d", "视": "sh",
            "冰": "b", "箱": "x", "空": "k", "调": "d", "洗": "x", "衣": "y",
            "机": "j", "热": "r", "水": "sh", "器": "q", "微": "w", "波": "b",
            "炉": "l", "手": "sh", "机": "j", "计": "j", "算": "s", "机": "j",
        }
        
        result = []
        for char in text:
            if char in char_pinyin_map:
                result.append(char_pinyin_map[char])
            # 跳过非中文字符（标点、数字、英文等）
        return "".join(result).lower()

    def _build_pinyin_index(self) -> None:
        """
        构建拼音首字母索引（需求 F-2.2.1）
        
        遍历词库中所有物品的主标签和别名，
        为每个文本生成拼音首字母缩写作为索引键，
        支持用户通过拼音缩写快速搜索（如输入 'slp' 查找'塑料瓶'）。
        """
        self._pinyin_index.clear()
        index_count = 0
        
        for item in self.vocab:
            # 处理主标签的拼音索引
            label = item.get("label", "")
            if label:
                py_key = self._get_pinyin_first_letters(label)
                if py_key:
                    if py_key not in self._pinyin_index:
                        self._pinyin_index[py_key] = []
                    # 避免重复添加同一 item
                    if not any(existing["label"] == label for existing in self._pinyin_index[py_key]):
                        self._pinyin_index[py_key].append(item)
                        index_count += 1
            
            # 处理别名的拼音索引
            for alias in item.get("aliases", []):
                if alias:
                    alias_py_key = self._get_pinyin_first_letters(alias)
                    if alias_py_key and alias_py_key != py_key:
                        if alias_py_key not in self._pinyin_index:
                            self._pinyin_index[alias_py_key] = []
                        if not any(existing["label"] == item["label"] for existing in self._pinyin_index[alias_py_key]):
                            self._pinyin_index[alias_py_key].append(item)
                            index_count += 1
        
        logger.info("拼音索引构建完成: %d 条索引项, 覆盖 %d 个拼音键", index_count, len(self._pinyin_index))

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        执行智能搜索（支持中文/别名模糊匹配 + 拼音首字母搜索）
        
        搜索策略：
        1. 纯字母模式检测 → 优先走拼音索引
        2. 常规模式 → FuzzyWuzzy 模糊匹配
        3. 结果合并去重，保证向后兼容
        
        Args:
            query: 搜索关键词
            top_k: 返回结果数量上限
            
        Returns:
            匹配的物品列表，按相似度降序排列
        """
        import re
        
        if not self.vocab_labels:
            return []

        query_stripped = query.strip()
        matched = []
        seen_labels = set()
        
        # ========== 拼音首字母搜索（需求 F-2.2.1） ==========
        # 检测纯小写字母输入，触发拼音搜索模式
        is_pinyin_mode = bool(re.match(r'^[a-z]+$', query_stripped))
        
        if is_pinyin_mode and self._pinyin_index:
            pinyin_results = self._search_by_pinyin(query_stripped, top_k)
            
            # 记录拼音匹配日志
            if pinyin_results:
                logger.info(
                    "拼音搜索命中: query='%s' → %d 条结果 [%s]",
                    query_stripped,
                    len(pinyin_results),
                    ", ".join([r["label"] for r in pinyin_results])
                )
            
            # 将拼音结果加入最终结果集（标记为拼音匹配来源）
            for item in pinyin_results:
                label = item["label"]
                if label not in seen_labels:
                    seen_labels.add(label)
                    matched.append({**item, "similarity_score": 95, "match_source": "pinyin"})
        
        # ========== FuzzyWuzzy 模糊匹配（原有逻辑保持不变） ==========
        # 构建合并搜索池：主标签 + 别名
        all_searchable = list(self.vocab_labels)
        alias_list = list(self._alias_to_label.keys())
        all_searchable.extend(alias_list)

        raw_results = fuzz_process.extract(query, all_searchable, limit=top_k * 2)

        # 设置相似度阈值：低于此分数的结果视为无意义匹配
        SIMILARITY_THRESHOLD = 50

        for match_text, score in raw_results:
            # 过滤低质量匹配：相似度低于阈值的不返回
            if score < SIMILARITY_THRESHOLD:
                continue

            # 如果匹配到的是别名，映射回主标签
            if match_text in self._alias_to_label:
                main_label = self._alias_to_label[match_text]
            else:
                main_label = match_text

            # 去重：同一主标签只保留最高分（拼音结果优先）
            if main_label in seen_labels:
                continue
            seen_labels.add(main_label)

            item = next((v for v in self.vocab if v["label"] == main_label), None)
            if item:
                matched.append({**item, "similarity_score": score, "match_source": "fuzzy"})
            if len(matched) >= top_k:
                break

        return matched

    def _search_by_pinyin(self, pinyin_query: str, top_k: int) -> list[dict]:
        """
        通过拼音首字母索引执行精确/前缀匹配
        
        支持两种匹配模式：
        - 精确匹配：查询键完全等于索引键（如 'slp' 匹配 'slp'）
        - 前缀匹配：查询键是索引键的前缀（如 'sl' 匹配 'slp'、'sld'）
        
        Args:
            pinyin_query: 拼音首字母查询字符串（如 'slp'）
            top_k: 返回结果数量上限
            
        Returns:
            匹配的物品列表
        """
        results = []
        seen_labels = set()
        pinyin_query_lower = pinyin_query.lower()
        
        # 第一轮：精确匹配
        if pinyin_query_lower in self._pinyin_index:
            for item in self._pinyin_index[pinyin_query_lower]:
                if item["label"] not in seen_labels:
                    results.append(item)
                    seen_labels.add(item["label"])
        
        # 第二轮：前缀匹配（精确匹配无结果或结果不足时）
        if len(results) < top_k:
            for index_key, items in self._pinyin_index.items():
                if index_key.startswith(pinyin_query_lower) and index_key != pinyin_query_lower:
                    for item in items:
                        if item["label"] not in seen_labels:
                            results.append(item)
                            seen_labels.add(item["label"])
                        if len(results) >= top_k * 2:
                            break
                if len(results) >= top_k * 2:
                    break
        
        return results[:top_k]

    def get_by_yolo_label(self, yolo_label: str) -> Optional[dict]:
        """根据标签查找"""
        for item in self.vocab:
            if item.get("yolo_label") == yolo_label:
                return item
        return None
    
    def get_items_by_category(self, category_id: int) -> list[dict]:
        """获取指定类别的所有物品"""
        return [item for item in self.vocab if item.get("category_id") == category_id]
    
    def get_smart_item(self, category_id: int, item_type: str = "unknown", 
                      is_metallic: bool = False) -> Optional[dict]:
        """
        智能选择物品示例（增强版 v2.1）
        根据类别、物品类型和金属特征选择最合适的示例物品
        解决易拉罐被识别成餐盒的问题
        """
        items_in_category = self.get_items_by_category(category_id)
        if not items_in_category:
            return None
        
        # 物品类型与关键词的映射关系
        type_keyword_map = {
            # 高形容器（杯子、瓶子）→ 优先匹配杯、瓶、饮料相关
            "container_tall": ["塑料杯", "饮料瓶", "矿泉水瓶", "易拉罐", "洗发水瓶", "沐浴露瓶", "保温杯", "水杯"],
            # 扁平容器（袋子、盒子）→ 优先匹配袋、盒、包装相关
            "container_flat": ["塑料袋", "快递纸箱", "包装盒", "泡沫箱", "牛奶盒", "餐盒", "方便面桶"],
            # 食物类 → 优先匹配食物残渣相关
            "food": ["剩饭剩菜", "苹果核", "香蕉皮", "橙子皮", "西瓜皮", "面包渣"],
            # 植物类 → 优先匹配植物相关
            "plant": ["菜叶菜根", "枯枝落叶", "杂草"],
            # 包装材料 → 优先匹配可回收包装
            "packaging": ["报纸", "书本", "旧衣服", "玻璃瓶", "铝罐"],
            # 纸张类 → 优先匹配纸张
            "paper": ["报纸", "书本", "作业本", "打印纸", "用过的纸巾"],
            # 其他情况 → 使用默认匹配
            "misc": None,
            "misc_bright": ["旧衣服", "玩具", "电器"],
            "misc_dark": ["烟蒂", "一次性餐具", "破碎陶瓷", "灰尘"],
            "unknown": None,
        }
        
        # 获取当前类型的关键词列表
        keywords = type_keyword_map.get(item_type)
        
        if keywords:
            # 根据关键词过滤匹配的物品
            matched_items = []
            for item in items_in_category:
                label = item.get("label", "")
                for kw in keywords:
                    if kw in label:
                        matched_items.append(item)
                        break
            
            if matched_items:
                # 从匹配项中优先选择最合适的（而非完全随机）
                # 对于容器类，根据是否有金属特征选择不同的优先级
                if is_metallic and item_type == "container_tall":
                    # 有金属特征 → 优先返回易拉罐/铝罐
                    preferred_order = {
                        "container_tall": ["易拉罐", "铝罐", "饮料瓶", "矿泉水瓶"],
                    }
                else:
                    # 无金属特征 → 使用默认优先级
                    preferred_order = {
                        "container_tall": ["塑料杯", "饮料瓶", "矿泉水瓶"],  # 普通容器
                        "container_flat": ["包装盒", "餐盒", "牛奶盒", "方便面桶", "泡沫箱"],
                        "food": ["剩饭剩菜", "苹果核", "香蕉皮"],
                    }
                
                pref_list = preferred_order.get(item_type, [])
                
                # 优先按顺序返回
                for pref_name in pref_list:
                    for item in matched_items:
                        if item.get("label") == pref_name:
                            logger.info("优先匹配: 类型=%s → %s", item_type, pref_name)
                            return item
                
                # 如果没有优先匹配，返回第一个匹配项（稳定但不是完全随机）
                return matched_items[0]
        
        # 如果没有匹配到，返回该类别中的随机物品
        import random
        return random.choice(items_in_category)
