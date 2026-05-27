"""
Alembic 迁移环境配置
支持 SQLite（开发）和 PostgreSQL（生产）双数据库
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 将项目根目录加入 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Alembic Config 对象
config = context.config

# 解析日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 从环境变量覆盖数据库连接（生产环境使用 PostgreSQL）
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Alembic 需要 sync 驱动，将 asyncpg 替换为 psycopg2
    if "asyncpg" in database_url:
        database_url = database_url.replace("asyncpg", "psycopg2")
    config.set_main_option("sqlalchemy.url", database_url)


def run_migrations_offline() -> None:
    """离线模式：生成 SQL 脚本而不连接数据库"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连接数据库执行迁移"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
