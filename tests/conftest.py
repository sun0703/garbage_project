"""pytest 全局配置"""

import os
import pytest

from tests.fixtures.client import client  # noqa: F401 — 注册 client fixture 供测试用例使用


@pytest.fixture(autouse=True)
def _setup_env(monkeypatch):
    """为测试设置隔离环境变量"""
    monkeypatch.setenv("DATABASE_PATH", "data/test_app.db")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "18001")
