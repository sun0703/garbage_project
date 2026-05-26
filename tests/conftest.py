"""pytest 全局配置"""

import pytest

from tests.fixtures.client import client  # noqa: F401 — 注册 client fixture 供测试用例使用


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """为每个测试用例设置环境变量，测试结束后自动恢复原始值"""
    monkeypatch.setenv("DATABASE_PATH", "data/test_app.db")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "18001")
