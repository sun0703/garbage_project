"""
JSON 文件加载工具模块
提供带缓存的 JSON 数据读取，避免重复文件IO
"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# 模块级缓存：{文件路径: (数据字典, 文件修改时间戳)}
_json_cache: dict[str, tuple[dict, float]] = {}


def load_json_data(
    file_path: Path,
    use_cache: bool = True,
    default: Optional[dict] = None,
) -> Optional[dict]:
    """
    安全加载 JSON 文件，支持基于文件修改时间的缓存

    缓存策略：
    - 首次读取写入缓存
    - 后续读取检查文件修改时间，未变化则直接返回缓存
    - 文件不存在返回 default

    :param file_path: JSON 文件路径
    :param use_cache: 是否启用缓存，默认 True
    :param default: 文件不存在时的默认返回值
    :return: 解析后的字典数据，或 default
    """
    if not file_path.exists():
        return default

    cache_key = str(file_path.absolute())
    current_mtime = file_path.stat().st_mtime

    if use_cache and cache_key in _json_cache:
        cached_data, cached_mtime = _json_cache[cache_key]
        if cached_mtime == current_mtime:
            return cached_data

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if use_cache:
            _json_cache[cache_key] = (data, current_mtime)
        return data
    except Exception as e:
        logger.error("JSON 文件读取失败 [%s]: %s", file_path.name, e)
        return default


def clear_cache(file_path: Optional[Path] = None):
    """
    清除 JSON 加载缓存

    :param file_path: 指定文件路径则只清除该文件缓存，否则清除所有缓存
    """
    if file_path:
        _json_cache.pop(str(file_path.absolute()), None)
    else:
        _json_cache.clear()
