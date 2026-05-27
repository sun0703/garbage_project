"""应用配置"""

from pathlib import Path
from typing import Optional

# 项目根目录
BASE_DIR = Path(__file__).parent.parent


class Settings:
    """全局配置，从环境变量读取，.env文件兜底"""

    def __init__(self):
        self._load_dotenv_if_available()
        self._load_env_settings()

    def _load_dotenv_if_available(self):
        """加载.env文件（有就用，没有拉倒）"""
        try:
            from dotenv import load_dotenv as _load
            env_path = BASE_DIR / ".env"
            if env_path.exists():
                _load(env_path)
                import logging
                logging.getLogger(__name__).info("已加载 .env 配置文件")
        except ImportError:
            pass

    def _load_env_settings(self):
        import os

        self.host: str = os.getenv("HOST", "0.0.0.0")
        self.port: int = int(os.getenv("PORT", "8001"))
        self.log_level: str = os.getenv("LOG_LEVEL", "info")
        self.reload: bool = os.getenv("RELOAD", "true").lower() == "true"

        self.database_path: str = os.getenv("DATABASE_PATH", "data/app.db")
        # Docker部署时自动注入这个
        self.database_url: str = os.getenv("DATABASE_URL", "")

        self.redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.redis_password: str = os.getenv("REDIS_PASSWORD", "")

        self.enable_metrics: bool = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        self.log_format: str = os.getenv("LOG_FORMAT", "text")  # text 或 json

        self.model_path: Path = Path(os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "garbage_yolov8m_best.pt")))
        self.use_yolo_pt_model: bool = os.getenv("USE_YOLO_PT_MODEL", "true").lower() == "true"
        self.yolo_input_size: int = int(os.getenv("YOLO_INPUT_SIZE", "640"))
        self.confidence_threshold: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))

        self.vocab_path: Path = Path(os.getenv("VOCAB_PATH", str(BASE_DIR / "data" / "waste.json")))
        self.static_dir: Path = Path(os.getenv("STATIC_DIR", str(BASE_DIR / "static")))
        self.index_html_path: Path = self.static_dir / "index.html"

        self.secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")  # 上线前必须换掉
        self.cors_origins: list = self._parse_cors(os.getenv("CORS_ORIGINS", "*"))

        # OAuth配置 — 后面接入微信/GitHub登录时再填
        self.wechat_app_id: str = os.getenv("WECHAT_APP_ID", "")
        self.wechat_app_secret: str = os.getenv("WECHAT_APP_SECRET", "")
        self.wechat_redirect_uri: str = os.getenv("WECHAT_REDIRECT_URI", "")
        self.github_client_id: str = os.getenv("GITHUB_CLIENT_ID", "")
        self.github_client_secret: str = os.getenv("GITHUB_CLIENT_SECRET", "")
        self.github_redirect_uri: str = os.getenv("GITHUB_REDIRECT_URI", "")

        self.cache_max_items: int = int(os.getenv("CACHE_MAX_ITEMS", "500"))
        self.cache_ttl_hours: int = int(os.getenv("CACHE_TTL_HOURS", "24"))

        self.history_max_items: int = int(os.getenv("HISTORY_MAX_ITEMS", "200"))
        self.history_backup_path: Optional[Path] = None
        history_path = os.getenv("HISTORY_BACKUP_PATH", str(BASE_DIR / "data" / "history.json"))
        if history_path:
            self.history_backup_path = Path(history_path)

    @staticmethod
    def _parse_cors(value: str) -> list:
        """解析CORS来源，*表示全部放行"""
        if value == "*":
            return ["*"]
        return [origin.strip() for origin in value.split(",") if origin.strip()]


settings = Settings()
