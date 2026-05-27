"""日志配置，支持text和json两种格式"""

import json
import logging
import os
import time
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """JSON日志格式化器，生产环境配合ELK用"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "lineno": record.lineno,
        }

        # 附加 request_id（如果存在）
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id

        # 附加异常信息
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        # 附加额外字段
        extra_fields = getattr(record, "extra", None)
        if extra_fields and isinstance(extra_fields, dict):
            log_entry.update(extra_fields)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """带颜色的文本格式，开发时看着舒服"""

    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[1;31m" # 加粗红色
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # 添加 request_id 到格式
        request_id = getattr(record, "request_id", "")
        rid_part = f" [{request_id[:8]}]" if request_id else ""

        # 添加颜色
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # 基础格式
        base = (
            f"%(asctime)s {color}%(levelname)-8s{reset} %(name)s{rid_part}: "
            f"%(message)s"
        )
        formatter = logging.Formatter(base, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def setup_logging(log_level: str = "INFO", log_format: str = "text") -> None:
    """配置全局日志，log_format=json给生产用"""
    # 选择格式化器
    if log_format.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter()

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除已有处理器（避免重复输出）
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 降低第三方库日志级别
    for lib in ["uvicorn", "uvicorn.access", "httpx", "httpcore", "PIL", "matplotlib"]:
        logging.getLogger(lib).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "日志系统初始化完成 (级别=%s, 格式=%s)", log_level, log_format
    )
