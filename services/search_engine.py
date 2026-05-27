"""模糊搜索引擎，FuzzyWuzzy+拼音首字母"""

import json
import logging
from pathlib import Path
from typing import Optional
from fuzzywuzzy import process as fuzz_process
from services.asr_correction import correct_asr_text, WASTE_SYNONYMS

# 拼音库导入，没有就用手动映射表兜底
try:
    from pypinyin import lazy_pinyin, Style
    _PINYIN_AVAILABLE = True
except ImportError:
    _PINYIN_AVAILABLE = False
    lazy_pinyin = None  # type: ignore
    Style = None  # type: ignore

logger = logging.getLogger(__name__)


class SearchEngine:
    """FuzzyWuzzy模糊搜索，支持拼音首字母搜索"""

    def __init__(self, vocab_path: str):
        self.vocab: list[dict] = []
        self.vocab_labels: list[str] = []
        self._alias_to_label: dict[str, str] = {}
        self._pinyin_index: dict[str, list[dict]] = {}
        self._load_vocab(vocab_path)

    def _load_vocab(self, vocab_path: str) -> None:
        """加载词库，构建别名索引和拼音索引"""
        vocab_file = Path(vocab_path)
        if not vocab_file.exists():
            logger.warning("词库文件不存在: %s", vocab_path)
            return
        try:
            with open(vocab_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.vocab = data.get("items", [])
            self.vocab_labels = [item["label"] for item in self.vocab]

            # 别名→主标签映射
            self._alias_to_label: dict[str, str] = {}
            for item in self.vocab:
                for alias in item.get("aliases", []):
                    if alias and alias not in self._alias_to_label:
                        self._alias_to_label[alias] = item["label"]

            # 把WASTE_SYNONYMS也加进别名索引
            for main_key, synonyms in WASTE_SYNONYMS.items():
                main_label = None
                for item in self.vocab:
                    if item["label"] == main_key or main_key in item.get("aliases", []):
                        main_label = item["label"]
                        break
                if main_label:
                    for syn in synonyms:
                        if syn and syn not in self._alias_to_label and syn != main_label:
                            self._alias_to_label[syn] = main_label

            self._build_pinyin_index()
            logger.info(
                "词库加载成功: %d 条记录, %d 个别名索引, %d 个拼音索引",
                len(self.vocab), len(self._alias_to_label), len(self._pinyin_index)
            )
        except Exception as e:
            logger.error("词库加载失败: %s", e)

    def _get_pinyin_first_letters(self, text: str) -> str:
        """取中文拼音首字母，如"塑料瓶"→"slp" """
        if not text:
            return ""

        if _PINYIN_AVAILABLE and lazy_pinyin is not None:
            try:
                py_list = lazy_pinyin(text, style=Style.FIRST_LETTER)
                return "".join(py_list).lower()
            except Exception:
                pass

        return self._fallback_pinyin(text)

    @staticmethod
    def _fallback_pinyin(text: str) -> str:
        """pypinyin不可用时的手动映射，覆盖垃圾分类高频字"""
        char_pinyin_map = {
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
        return "".join(result).lower()

    def _build_pinyin_index(self) -> None:
        """构建拼音首字母索引，支持输入'slp'查找'塑料瓶'"""
        self._pinyin_index.clear()
        index_count = 0

        for item in self.vocab:
            label = item.get("label", "")
            if label:
                py_key = self._get_pinyin_first_letters(label)
                if py_key:
                    if py_key not in self._pinyin_index:
                        self._pinyin_index[py_key] = []
                    if not any(existing["label"] == label for existing in self._pinyin_index[py_key]):
                        self._pinyin_index[py_key].append(item)
                        index_count += 1

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
        """搜索入口：纯字母走拼音索引，否则走FuzzyWuzzy模糊匹配"""
        import re

        if not self.vocab_labels:
            return []

        query_stripped = query.strip()
        matched = []
        seen_labels = set()

        # 纯小写字母→拼音搜索模式
        is_pinyin_mode = bool(re.match(r'^[a-z]+$', query_stripped))

        if is_pinyin_mode and self._pinyin_index:
            pinyin_results = self._search_by_pinyin(query_stripped, top_k)

            if pinyin_results:
                logger.info(
                    "拼音搜索命中: query='%s' → %d 条结果 [%s]",
                    query_stripped,
                    len(pinyin_results),
                    ", ".join([r["label"] for r in pinyin_results])
                )

            for item in pinyin_results:
                label = item["label"]
                if label not in seen_labels:
                    seen_labels.add(label)
                    matched.append({**item, "similarity_score": 95, "match_source": "pinyin"})

        # FuzzyWuzzy模糊匹配
        all_searchable = list(self.vocab_labels)
        alias_list = list(self._alias_to_label.keys())
        all_searchable.extend(alias_list)

        raw_results = fuzz_process.extract(query, all_searchable, limit=top_k * 2)

        SIMILARITY_THRESHOLD = 50

        for match_text, score in raw_results:
            if score < SIMILARITY_THRESHOLD:
                continue

            if match_text in self._alias_to_label:
                main_label = self._alias_to_label[match_text]
            else:
                main_label = match_text

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
        """拼音搜索：先精确匹配，不够再前缀匹配"""
        results = []
        seen_labels = set()
        pinyin_query_lower = pinyin_query.lower()

        # 精确匹配
        if pinyin_query_lower in self._pinyin_index:
            for item in self._pinyin_index[pinyin_query_lower]:
                if item["label"] not in seen_labels:
                    results.append(item)
                    seen_labels.add(item["label"])

        # 前缀匹配
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
        """根据yolo标签查词库"""
        for item in self.vocab:
            if item.get("yolo_label") == yolo_label:
                return item
        return None

    def get_items_by_category(self, category_id: int) -> list[dict]:
        """按类别过滤物品"""
        return [item for item in self.vocab if item.get("category_id") == category_id]

    def get_smart_item(self, category_id: int, item_type: str = "unknown",
                      is_metallic: bool = False) -> Optional[dict]:
        """根据类别+物品类型+金属特征智能选择示例物品"""
        items_in_category = self.get_items_by_category(category_id)
        if not items_in_category:
            return None

        # 物品类型→关键词映射
        type_keyword_map = {
            "container_tall": ["塑料杯", "饮料瓶", "矿泉水瓶", "易拉罐", "洗发水瓶", "沐浴露瓶", "保温杯", "水杯"],
            "container_flat": ["塑料袋", "快递纸箱", "包装盒", "泡沫箱", "牛奶盒", "餐盒", "方便面桶"],
            "food": ["剩饭剩菜", "苹果核", "香蕉皮", "橙子皮", "西瓜皮", "面包渣"],
            "plant": ["菜叶菜根", "枯枝落叶", "杂草"],
            "packaging": ["报纸", "书本", "旧衣服", "玻璃瓶", "铝罐"],
            "paper": ["报纸", "书本", "作业本", "打印纸", "用过的纸巾"],
            "misc": None,
            "misc_bright": ["旧衣服", "玩具", "电器"],
            "misc_dark": ["烟蒂", "一次性餐具", "破碎陶瓷", "灰尘"],
            "unknown": None,
        }

        keywords = type_keyword_map.get(item_type)

        if keywords:
            matched_items = []
            for item in items_in_category:
                label = item.get("label", "")
                for kw in keywords:
                    if kw in label:
                        matched_items.append(item)
                        break

            if matched_items:
                # 有金属特征的高形容器优先返回易拉罐
                if is_metallic and item_type == "container_tall":
                    preferred_order = {
                        "container_tall": ["易拉罐", "铝罐", "饮料瓶", "矿泉水瓶"],
                    }
                else:
                    preferred_order = {
                        "container_tall": ["塑料杯", "饮料瓶", "矿泉水瓶"],
                        "container_flat": ["包装盒", "餐盒", "牛奶盒", "方便面桶", "泡沫箱"],
                        "food": ["剩饭剩菜", "苹果核", "香蕉皮"],
                    }

                pref_list = preferred_order.get(item_type, [])

                for pref_name in pref_list:
                    for item in matched_items:
                        if item.get("label") == pref_name:
                            logger.info("优先匹配: 类型=%s → %s", item_type, pref_name)
                            return item

                return matched_items[0]

        # 都没匹配到就随机返回一个
        import random
        return random.choice(items_in_category)
