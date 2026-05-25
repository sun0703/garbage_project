"""FastAPI 测试客户端 fixture"""

import pytest


@pytest.fixture(scope="session")
def client():
    """创建 FastAPI 测试客户端（session级别复用，避免重复启动）"""
    import os
    os.environ.setdefault("DATABASE_PATH", "data/test_app.db")

    from main import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
