"""JSON文件加载，带基于修改时间的缓存"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# {文件路径: (数据字典, 文件修改时间戳)}
_json_cache: dict[str, tuple[dict, float]] = {}


def load_json_data(
    file_path: Path,
    use_cache: bool = True,
    default: Optional[dict] = None,
) -> Optional[dict]:
    """加载JSON文件，文件没变就直接返回缓存"""
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
    """清缓存，指定文件就只清该文件，否则全清"""
    if file_path:
        _json_cache.pop(str(file_path.absolute()), None)
    else:
        _json_cache.clear()
