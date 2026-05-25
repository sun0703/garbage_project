"""FastAPI 测试客户端 fixture"""

import pytest


@pytest.fixture(scope="session")
def client():
    """创建 FastAPI 测试客户端（session级别复用，避免重复启动）

    捕获 ImportError 并输出明确的缺失依赖提示，避免 CI 环境中静默 ERROR。
    """
    import os
    os.environ.setdefault("DATABASE_PATH", "data/test_app.db")

    try:
        from app.main import app
    except ImportError as e:
        pytest.fail(
            f"无法导入 FastAPI 应用，请确认已安装全部依赖:\n"
            f"  pip install -r requirements.txt\n"
            f"  导入错误详情: {e}"
        )

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.fail("缺少 fastapi 依赖，请执行: pip install fastapi")

    with TestClient(app) as c:
        yield c
