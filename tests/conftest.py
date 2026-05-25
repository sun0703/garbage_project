"""pytest 全局配置"""

import os
import pytest

from tests.fixtures.client import client  # noqa: F401 — 注册 client fixture 供测试用例使用


@pytest.fixture(scope="session", autouse=True)
def _session_env():
    """Session 级别：在 client fixture 之前设置测试专用环境变量"""
    os.environ.setdefault("DATABASE_PATH", "data/test_app.db")
    os.environ.setdefault("HOST", "127.0.0.1")
    os.environ.setdefault("PORT", "18001")
    yield


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """Function 级别：隔离每个测试用例的环境变量修改"""
    monkeypatch.setenv("DATABASE_PATH", "data/test_app.db")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "18001")
