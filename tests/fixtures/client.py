"""FastAPI 测试客户端 fixture"""

import traceback

import pytest


@pytest.fixture(scope="session")
def client():
    """创建 FastAPI 测试客户端（session级别复用，避免重复启动）

    宽异常捕获：覆盖 from app.main import app 及 TestClient(app)
    lifespan 启动事件中可能抛出的任何异常，输出完整 traceback 到 pytest 失败信息。
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

    try:
        with TestClient(app) as c:
            yield c
    except Exception:
        tb = traceback.format_exc()
        pytest.fail(
            f"TestClient 启动失败，应用 lifespan 事件可能抛出异常:\n{tb}"
        )
