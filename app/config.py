"""
应用配置管理模块
支持从环境变量和 .env 文件读取配置，pydantic-settings 自动加载
"""

from pathlib import Path
from typing import Optional

# 项目根目录（app/ 是子目录，上翻一级）
BASE_DIR = Path(__file__).parent.parent


class Settings:
    """
    应用配置单例
    优先从环境变量读取，支持 .env 文件 fallback

    使用方式：
        from config import settings
        port = settings.port
    """

    def __init__(self):
        self._load_dotenv_if_available()
        self._init_config()

    def _load_dotenv_if_available(self):
        """尝试加载 .env 文件"""
        try:
            from dotenv import load_dotenv as _load
            env_path = BASE_DIR / ".env"
            if env_path.exists():
                _load(env_path)
                import logging
                logging.getLogger(__name__).info("已加载 .env 配置文件")
        except ImportError:
            pass

    def _init_config(self):
        import os

        # ==================== 服务器配置 ====================
        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8001"))
        self.log_level: str = os.getenv("LOG_LEVEL", "info")
        self.reload: bool = os.getenv("RELOAD", "true").lower() == "true"

        # ==================== 数据库配置 ====================
        self.database_path: str = os.getenv("DATABASE_PATH", "data/app.db")

        # ==================== 模型配置 ====================
        self.model_path: Path = Path(os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "garbage_yolov8m_best.pt")))
        self.use_yolo_pt_model: bool = os.getenv("USE_YOLO_PT_MODEL", "true").lower() == "true"
        self.yolo_input_size: int = int(os.getenv("YOLO_INPUT_SIZE", "640"))
        self.confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))

        # ==================== 路径配置 ====================
        self.vocab_path: Path = Path(os.getenv("VOCAB_PATH", str(BASE_DIR / "data" / "waste.json")))
        self.static_dir: Path = Path(os.getenv("STATIC_DIR", str(BASE_DIR / "static")))
        self.index_html_path: Path = self.static_dir / "index.html"

        # ==================== 安全配置 ====================
        self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
        self.cors_origins: list = self._parse_cors(os.getenv("CORS_ORIGINS", "*"))

        # ==================== OAuth 配置 ====================
        self.wechat_app_id: str = os.getenv("WECHAT_APP_ID", "")
        self.wechat_app_secret: str = os.getenv("WECHAT_APP_SECRET", "")
        self.wechat_redirect_uri: str = os.getenv("WECHAT_REDIRECT_URI", "")
        self.github_client_id: str = os.getenv("GITHUB_CLIENT_ID", "")
        self.github_client_secret: str = os.getenv("GITHUB_CLIENT_SECRET", "")
        self.github_redirect_uri: str = os.getenv("GITHUB_REDIRECT_URI", "")

        # ==================== 缓存配置 ====================
        self.cache_max_items: int = int(os.getenv("CACHE_MAX_ITEMS", "500"))
        self.cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "24"))

        # ==================== 历史记录配置 ====================
        self.history_max_items: int = int(os.getenv("HISTORY_MAX_ITEMS", "200"))
        self.history_backup_path: Optional[Path] = None
        history_path = os.getenv("HISTORY_BACKUP_PATH", str(BASE_DIR / "data" / "history.json"))
        if history_path:
            self.history_backup_path = Path(history_path)

    @staticmethod
    def _parse_cors(value: str) -> list:
        """解析 CORS 来源配置"""
        if value == "*":
            return ["*"]
        return [origin.strip() for origin in value.split(",") if origin.strip()]


# 全局配置单例
settings = Settings()
